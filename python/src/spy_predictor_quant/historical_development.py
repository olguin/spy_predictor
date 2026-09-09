"""Separately authorized development only; never opens archived target artifacts.

No Cycle 1 gates or stopped authorities are changed. The loader emits a bounded
SPY dataset; the trainer accepts only its qualified, hash-verified manifest.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime
from pathlib import Path

import numpy as np

from spy_predictor_quant.cycle1_calendar import _xnys, xnys_month_end, xnys_session_close
from spy_predictor_quant.cycle1_features import FEATURE_IDS, _economic_signs, _raw_features, _month_floor, expanding_midrank
from spy_predictor_quant.cycle1_models import MODEL_IDS, UnavailableFold, distribution_scores, fit_roster
from spy_predictor_quant.cycle1_targets import construct_total_return_index, month_end_points, rolled_cash_log_return
from spy_predictor_quant.market_archive import content_hash, file_sha256


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def ndjson(rows):
    return b''.join((json.dumps(r, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode() for r in rows)


def write_once(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f'Immutable artifact mismatch: {path}')
    else:
        with path.open('xb') as stream:
            stream.write(data)


def confined(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Path escapes repository')
    return path


def verify(root, hashes):
    for name, expected in hashes.items():
        if file_sha256(confined(root, name)) != expected:
            raise ValueError(f'Hash mismatch: {name}')


def load_contract(root):
    contract = json.loads((root / 'config/historical-development-v1.json').read_text())
    verify(root, {contract['specificationPath']: contract['specificationSha256'],
                  contract['sourceManifestPath']: contract['sourceManifestSha256'],
                  **contract['stoppedDecisions']})
    # Literal boundaries are also enforced in executable code, not just flags.
    required = {'instrument': 'SPY', 'originStart': '1999-11-30', 'originEnd': '2016-06-30',
                'forecastStart': '2010-11-30', 'outcomePathEnd': '2017-06-30',
                'finalEvaluationStart': '2017-07-31', 'finalEvaluationEnd': '2025-07-31',
                'expectedOrigins': 200, 'expectedForecastsPerMode': 68,
                'expectedEligibleForecastsPerMode': 42, 'expectedCompleteFeatureOrigins': 174,
                'minimumTrainingLabels': 120, 'rollingWindowMonths': 180,
                'cashSeries': 'GS3M', 'modes': ['expanding', 'rolling'],
                'finalEvaluationAllowed': False, 'researchPromotionAllowed': False,
                'hyperparameterSearch': False, 'modelIds': list(MODEL_IDS)}
    if any(contract.get(k) != v for k, v in required.items()):
        raise ValueError('Development contract changes require a new versioned runner')
    if contract['missingDailySessions'] != ['2004-07-12', '2007-07-02']:
        raise ValueError('Unexpected missing-session amendment')
    return contract, json.loads((root / contract['specificationPath']).read_text())


def code_hashes(root):
    names = ['historical_development', 'cycle1_features', 'cycle1_targets', 'cycle1_models',
             'cycle1_calendar', 'market_archive']
    paths = [f'python/src/spy_predictor_quant/{n}.py' for n in names] + ['python/uv.lock']
    return {p: file_sha256(root / p) for p in paths}


def stopped_inventory(root):
    return {str(p.relative_to(root)): file_sha256(p)
            for folder in ('experiments/cycle1-power-v1', 'experiments/cycle1-power-v2')
            for p in sorted((root / folder).rglob('*')) if p.is_file()}


def load_sources(root, contract):
    manifest = json.loads((root / contract['sourceManifestPath']).read_text())
    raw_root = root / 'datasets/cycle1/raw' / manifest['sourceAuditHash'][:16]
    raw_hashes = {str((raw_root / r['path']).relative_to(root)): r['sha256']
                  for r in manifest['rawResources']}
    verify(root, raw_hashes)
    # Deliberate allowlist: never deserialize legacy features, targets or scores.
    artifacts = {a['kind']: a for a in manifest['normalizedArtifacts']}
    sources, hashes = {}, dict(raw_hashes)
    for kind in ('primary', 'corporate-actions', 'macro-vintages'):
        entry = artifacts[kind]
        verify(root, {entry['path']: entry['sha256']})
        hashes[entry['path']] = entry['sha256']
        rows = []
        with confined(root, entry['path']).open() as stream:
            for line in stream:
                r = json.loads(line)
                if kind == 'macro-vintages':
                    keep = r['seriesId'] in ('CPIAUCSL', 'INDPRO', 'MPRIME', 'GS3M') and r['availableAt'][:10] <= contract['outcomePathEnd']
                else:
                    keep = r['instrument'] == 'SPY' and r['sessionDate' if kind == 'primary' else 'effectiveDate'] <= contract['outcomePathEnd']
                if keep:
                    rows.append(r)
        sources[kind] = rows
    return sources, hashes


class VintageState:
    """Strict publication timing, including missing-value tombstones."""
    def __init__(self, rows):
        self.events = sorted(rows, key=lambda r: (datetime.fromisoformat(r['availableAt']), r['realtimeStart']))
        self.position = 0
        self.selected = {}

    def at(self, cutoff):
        while self.position < len(self.events):
            r = self.events[self.position]
            if datetime.fromisoformat(r['availableAt']) >= cutoff:
                break
            key = (r['seriesId'], r['observationDate'])
            old = self.selected.get(key)
            if old is None or r['realtimeStart'] >= old['realtimeStart']:
                self.selected[key] = r
            self.position += 1
        values = {s: {} for s in ('CPIAUCSL', 'INDPRO', 'MPRIME', 'GS3M')}
        for (series, observation), r in self.selected.items():
            if not r['missing'] and observation <= cutoff.date().isoformat():
                value = float(r['value'])
                if not math.isfinite(value):
                    raise ValueError('Nonfinite macro observation')
                values[series][date.fromisoformat(observation)] = value
        return values


def build_rows(sources, spec, contract):
    daily, actions, macro = (sources[k] for k in ('primary', 'corporate-actions', 'macro-vintages'))
    sessions = [r['sessionDate'] for r in daily]
    expected = [s.date().isoformat() for s in _xnys().sessions_in_range(sessions[0], contract['outcomePathEnd'])]
    gaps = sorted(set(expected)-set(sessions))
    if sessions != sorted(set(sessions)) or set(sessions)-set(expected) or gaps != contract['missingDailySessions']:
        raise ValueError('Unexpected missing, duplicate or unordered internal XNYS session')
    for r in daily:
        if datetime.fromisoformat(r['eventTime']) != xnys_session_close(date.fromisoformat(r['sessionDate'])):
            raise ValueError('Price timestamp differs from XNYS close')
        if r['provider'] != 'ibkr-trades-split-adjusted':
            raise ValueError('Unqualified price adjustment units')
        if not all(math.isfinite(float(r[k])) and float(r[k]) > 0 for k in ('open', 'high', 'low', 'close')):
            raise ValueError('Nonpositive or nonfinite market price')
        if not float(r['low']) <= min(float(r['open']), float(r['close'])) <= max(float(r['open']), float(r['close'])) <= float(r['high']):
            raise ValueError('Invalid OHLC ordering')
    if len({r['actionId'] for r in actions}) != len(actions):
        raise ValueError('Duplicate corporate action')
    for r in actions:
        if r['effectiveDate'] not in sessions or r['actionType'] not in ('cash_dividend', 'capital_gains_distribution'):
            raise ValueError('Unsupported action units or ex-session')
        if not math.isfinite(float(r['raw']['cash'])) or float(r['raw']['cash']) < 0:
            raise ValueError('Invalid distribution cash')
    points = construct_total_return_index(daily, actions)
    monthly = month_end_points(points)
    vintage = VintageState(macro)
    signs = _economic_signs(spec)
    history = {f: [] for f in FEATURE_IDS}
    dimensions = {name: [f['id'] for f in definition['features']]
                  for name, definition in spec['features']['dimensions'].items()}
    features, excluded, cash, cash_audit = {}, [], {}, []
    for p in monthly:
        values = vintage.at(p.event_time)
        rates = values['GS3M']
        if rates:
            observation = max(rates)
            cash[p.event_time] = rates[observation]
            record = vintage.selected[('GS3M', observation.isoformat())]
            cash_audit.append({'snapshotDate': p.session_date.isoformat(), 'observationDate': observation.isoformat(),
                               'availableAt': record['availableAt'], 'realtimeStart': record['realtimeStart'], 'annualPercent': rates[observation]})
        if p.session_date.isoformat() > contract['originEnd']:
            continue
        affected = [g for g in gaps if _month_floor(p.session_date, 12).isoformat() < g <= p.session_date.isoformat()]
        if affected:
            features[p.session_date.isoformat()] = {'rawFeatures': {}, 'normalizedFeatures': {},
                'dimensions': None, 'unavailableReason': 'missing-daily-feature-session:' + ','.join(affected)}
            continue
        raw, missing = _raw_features(p, points, monthly, values, spec)
        if missing:
            excluded.append({'date': p.session_date.isoformat(), 'reason': ','.join(sorted(missing))})
            continue
        for f in FEATURE_IDS:
            history[f].append(raw[f])
        if min(map(len, history.values())) < spec['features']['normalization']['percentileMinimumHistoryMonths']:
            excluded.append({'date': p.session_date.isoformat(), 'reason': 'normalization-warmup'})
            continue
        normal = {f: signs[f] * expanding_midrank(raw[f], history[f]) for f in FEATURE_IDS}
        features[p.session_date.isoformat()] = {'rawFeatures': raw, 'normalizedFeatures': normal,
            'dimensions': [sum(normal[f] for f in dimensions[d])/len(dimensions[d]) for d in ('valuation', 'stress', 'direction')]}
    by_month = {p.session_date.strftime('%Y-%m'): p for p in monthly}
    output = []
    for p in monthly:
        origin = p.session_date.isoformat()
        if not contract['originStart'] <= origin <= contract['originEnd']:
            continue
        if origin not in features:
            raise ValueError(f'Missing internal development feature: {origin}')
        end = by_month[f'{p.session_date.year+1:04d}-{p.session_date.month:02d}']
        cash_return = rolled_cash_log_return(p, end, monthly, cash)
        equity = math.log(end.total_return_index/p.total_return_index)
        output.append({'instrument': 'SPY', 'snapshotDate': origin, 'snapshotCutoff': p.event_time.isoformat(),
                       'targetEndDate': end.session_date.isoformat(), 'labelAvailableAt': end.event_time.isoformat(),
                       **features[origin], 'outcome': equity-cash_return,
                       'equityLogReturn': equity, 'cashProxyLogReturn': cash_return})
    validate_rows(output, contract)
    return output, {'excludedWarmup': excluded, 'cashAccrualInputs': cash_audit,
                    'missingDailySessions': gaps,
                    'unavailableFeatureOrigins': [r['snapshotDate'] for r in output if r['dimensions'] is None],
                    'dailySessions': len(daily), 'corporateActions': len(actions),
                    'monthlyCashPathChecks': len(output)*12,
                    'featureCoveragePercent': 100*sum(r['dimensions'] is not None for r in output)/len(output), 'rawArchiveReuse': True,
                    'missingRevisionRule': 'tombstone-removes-observation',
                    'spreadLag': 'exact-common-observation-month-minus-three',
                    'marketUnits': 'SPY-split-adjusted-trades-plus-sponsor-cash-per-share;no-split-reapplication',
                    'QQQ': 'NOT_LOADED_TRANSFER_ONLY', 'diagnostics24m': 'NOT_BUILT',
                    'finalEvaluation': 'NOT_BUILT_NOT_SCORED'}


def calendar(start, end):
    months = np.arange(np.datetime64(start[:7], 'M'), np.datetime64(end[:7], 'M')+np.timedelta64(1, 'M'))
    return [xnys_month_end(int(str(m)[:4]), int(str(m)[5:7])).isoformat() for m in months]


def validate_rows(rows, c):
    if [r['snapshotDate'] for r in rows] != calendar(c['originStart'], c['originEnd']):
        raise ValueError('Development origins differ from literal calendar')
    if len(rows) != c['expectedOrigins']:
        raise ValueError('Development origin count changed')
    for r in rows:
        origin = date.fromisoformat(r['snapshotDate'])
        end = xnys_month_end(origin.year+1, origin.month)
        if r['instrument'] != 'SPY' or r['targetEndDate'] != end.isoformat() or r['targetEndDate'] > c['outcomePathEnd']:
            raise ValueError('Target extends beyond permitted development path')
        if datetime.fromisoformat(r['snapshotCutoff']) != xnys_session_close(origin) or datetime.fromisoformat(r['labelAvailableAt']) != xnys_session_close(end):
            raise ValueError('Incorrect feature or label availability')
        if not math.isfinite(r['outcome']):
            raise ValueError('Invalid primary outcome')
        if r['dimensions'] is None:
            if not r.get('unavailableReason', '').startswith('missing-daily-feature-session:'):
                raise ValueError('Unexplained missing feature')
            continue
        if len(r['dimensions']) != 3 or not np.isfinite([*r['dimensions'], r['outcome'], *r['rawFeatures'].values()]).all():
            raise ValueError('Invalid development values')


def train_indices(rows, index, mode, c):
    if mode not in c['modes']:
        raise ValueError('Unknown training mode')
    cutoff = datetime.fromisoformat(rows[index]['snapshotCutoff'])
    lower = np.datetime64(rows[index]['snapshotDate'][:7], 'M') - np.timedelta64(c['rollingWindowMonths'], 'M')
    return [i for i, r in enumerate(rows) if r['snapshotDate'] <= c['originEnd']
            and r['dimensions'] is not None
            and datetime.fromisoformat(r['labelAvailableAt']) < cutoff
            and r['targetEndDate'] < rows[index]['snapshotDate']
            and (mode == 'expanding' or np.datetime64(r['snapshotDate'][:7], 'M') > lower)]


def qualify(root, c, spec):
    preserved = stopped_inventory(root)
    sources, source_hashes = load_sources(root, c)
    rows, audit = build_rows(sources, spec, c)
    # Independent deserialization and rebuild from the bounded, lossless inputs.
    bounded = {k: ndjson(v) for k, v in sources.items()}
    restored = {k: [json.loads(line) for line in data.splitlines()] for k, data in bounded.items()}
    rebuilt, second_audit = build_rows(restored, spec, c)
    if ndjson(rebuilt) != ndjson(rows) or encode(second_audit) != encode(audit):
        raise ValueError('Offline reconstruction identity mismatch')
    counts = {mode: [len(train_indices(rows, i, mode, c)) for i, r in enumerate(rows)
                    if r['snapshotDate'] >= c['forecastStart']] for mode in c['modes']}
    if any(len(v) != c['expectedForecastsPerMode'] or max(v) < c['minimumTrainingLabels'] for v in counts.values()):
        raise ValueError('Mature-label feasibility differs from plan; no fitting allowed')
    if sum(r['dimensions'] is not None for r in rows) != c['expectedCompleteFeatureOrigins'] or any(
        sum(n >= c['minimumTrainingLabels'] for n in v) != c['expectedEligibleForecastsPerMode'] for v in counts.values()
    ):
        raise ValueError('Missingness differs from pre-output development amendment')
    identity = {'contractHash': content_hash(c), 'codeHashes': code_hashes(root),
                'sourceHashes': source_hashes, 'rowsHash': content_hash(rows),
                'boundedSourceHashes': {k: content_hash(v) for k, v in sources.items()}}
    digest = content_hash(identity)
    folder = root / 'datasets/historical-development' / digest[:16]
    for kind, data in bounded.items():
        write_once(folder / f'{kind}.ndjson', data)
    write_once(folder / 'development.ndjson', ndjson(rows))
    write_once(folder / 'qualification.json', encode({**audit, 'trainingCounts': counts,
               'offlineRebuildIdentical': True, 'independentDurableBackupVerified': False,
               'scope': 'development-only;no-source-migration;no-Cycle1-research-qualification'}))
    artifacts = {str(p.relative_to(root)): file_sha256(p) for p in sorted(folder.glob('*')) if p.name != 'manifest.json'}
    manifest = {'schemaVersion': 'historical-development-dataset-v1', 'identity': identity,
                'datasetHash': digest, 'status': 'QUALIFIED_FOR_DEVELOPMENT_ONLY',
                'evidenceTier': 'RECONSTRUCTED_RESEARCH_ONLY', 'artifacts': artifacts,
                'dataPath': str((folder / 'development.ndjson').relative_to(root)),
                'originCount': len(rows), 'finalEvaluationIncluded': False,
                'stoppedExperimentHashes': preserved}
    if stopped_inventory(root) != preserved:
        raise ValueError('Stopped experiment changed during qualification')
    write_once(folder / 'manifest.json', encode(manifest))
    return folder / 'manifest.json'


def train(root, manifest_path, c, spec):
    manifest = json.loads(manifest_path.read_text())
    if manifest['status'] != 'QUALIFIED_FOR_DEVELOPMENT_ONLY' or manifest['finalEvaluationIncluded']:
        raise ValueError('Dataset is not qualified for development')
    identity = manifest['identity']
    if content_hash(identity) != manifest['datasetHash'] or identity['contractHash'] != content_hash(c) or identity['codeHashes'] != code_hashes(root):
        raise ValueError('Dataset authority mismatch')
    verify(root, manifest['artifacts'])
    verify(root, identity['sourceHashes'])
    verify(root, manifest['stoppedExperimentHashes'])
    if manifest['dataPath'] not in manifest['artifacts']:
        raise ValueError('Unhashed dataset path')
    rows = [json.loads(line) for line in confined(root, manifest['dataPath']).read_text().splitlines()]
    if content_hash(rows) != identity['rowsHash']:
        raise ValueError('Dataset row identity mismatch')
    validate_rows(rows, c)
    run_identity = {'datasetHash': manifest['datasetHash'], 'manifestSha256': file_sha256(manifest_path),
                    'contractHash': content_hash(c), 'codeHashes': code_hashes(root)}
    folder = root / 'reports/historical-development' / content_hash(run_identity)[:16]
    ledger = {'identity': run_identity, 'purpose': 'DEVELOPMENT_ONLY', 'finalEvaluationOpened': False,
              'entries': [{'modelId': model, 'mode': mode, 'status': 'PLANNED'} for model in MODEL_IDS for mode in c['modes']]}
    write_once(folder / 'ledger.json', encode(ledger))  # Persist before the first fit.
    if (folder / 'report.json').exists():
        result = json.loads((folder / 'report.json').read_text())
        if result['identity'] != run_identity or result.get('reportHash') != content_hash({k: v for k, v in result.items() if k != 'reportHash'}):
            raise ValueError('Existing report identity mismatch')
        verify(root, result['artifacts'])
        return folder / 'report.json'
    x = np.array([r['dimensions'] if r['dimensions'] is not None else [np.nan]*3 for r in rows])
    v = np.array([r['rawFeatures'].get('realized-volatility-3m', np.nan) for r in rows])
    y = np.array([r['outcome'] for r in rows])
    forecasts, folds = [], []
    for index, r in enumerate(rows):
        if r['snapshotDate'] < c['forecastStart']:
            continue
        for mode in c['modes']:
            indices = train_indices(rows, index, mode, c)
            folds.append({'date': r['snapshotDate'], 'mode': mode, 'trainingCount': len(indices),
                          'trainingOrigins': [rows[i]['snapshotDate'] for i in indices],
                          'latestTrainingAvailability': max((rows[i]['labelAvailableAt'] for i in indices), default=None)})
            if len(indices) < c['minimumTrainingLabels'] or r['dimensions'] is None:
                forecasts.extend({'date': r['snapshotDate'], 'mode': mode, 'modelId': model,
                                  'status': 'UNAVAILABLE', 'reason': 'insufficient-mature-complete-labels-or-missing-feature',
                                  'trainingCount': len(indices)} for model in MODEL_IDS)
                continue
            models = fit_roster(x[indices], v[indices], y[indices], spec['models']['perInstrument'],
                                minimum=c['minimumTrainingLabels'],
                                minimum_bin=spec['evaluationContract']['tertiles']['minimumBinObservations'])
            for model_id, model in models.items():
                record = {'date': r['snapshotDate'], 'mode': mode, 'modelId': model_id, 'status': 'UNAVAILABLE'}
                try:
                    if model is None:
                        raise UnavailableFold('Insufficient bin support')
                    samples = model.predict(x[index], v[index])
                    loss, error, coverage, width = distribution_scores(samples, y[index])
                    record.update(status='SCORED', samples=samples.tolist(), outcome=float(y[index]),
                                  crps=loss, squaredError=error, covered90=coverage, intervalWidth90=width)
                except UnavailableFold as exc:
                    record['reason'] = str(exc)
                forecasts.append(record)
    summary, paired = [], []
    for mode in c['modes']:
        for model in MODEL_IDS:
            eligible = [r for r in forecasts if r['mode'] == mode and r['modelId'] == model and r['status'] == 'SCORED']
            summary.append({'mode': mode, 'modelId': model, 'forecasts': len(eligible),
                            'calendarForecasts': c['expectedForecastsPerMode'],
                            'meanCrps': float(np.mean([r['crps'] for r in eligible])) if eligible else None,
                            'rmse': float(np.sqrt(np.mean([r['squaredError'] for r in eligible]))) if eligible else None,
                            'coverage90': float(np.mean([r['covered90'] for r in eligible])) if eligible else None})
        common = {r['date'] for r in forecasts if r['mode'] == mode}
        for model in MODEL_IDS:
            common &= {r['date'] for r in forecasts if r['mode'] == mode and r['modelId'] == model and r['status'] == 'SCORED'}
        losses = {(r['date'], r['modelId']): r['crps'] for r in forecasts if r['mode'] == mode and r['status'] == 'SCORED'}
        for challenger in MODEL_IDS[5:]:
            for baseline in MODEL_IDS[:5]:
                delta = [losses[(d, baseline)]-losses[(d, challenger)] for d in sorted(common)]
                paired.append({'mode': mode, 'challenger': challenger, 'baseline': baseline,
                               'commonDates': len(common), 'meanCrpsImprovement': float(np.mean(delta)) if delta else None})
    write_once(folder / 'forecasts.ndjson', ndjson(forecasts))
    write_once(folder / 'folds.json', encode(folds))
    result = {'identity': run_identity, 'status': 'DEVELOPMENT_WALK_FORWARD_COMPLETED',
              'evidenceTier': 'RECONSTRUCTED_RESEARCH_ONLY', 'summary': summary, 'pairedComparisons': paired,
              'forecastStart': c['forecastStart'], 'forecastEnd': c['originEnd'],
              'finalEvaluation': {'start': c['finalEvaluationStart'], 'end': c['finalEvaluationEnd'], 'opened': False},
              'researchQualified': False, 'deploymentQualified': False, 'hyperparameterSearch': False,
              'inference': 'descriptive-development-scores;no-significance-or-power-claim',
              'artifacts': {str(p.relative_to(root)): file_sha256(p) for p in sorted(folder.glob('*'))},
              'completedLedger': [{**entry, 'status': 'COMPLETED'} for entry in ledger['entries']]}
    verify(root, manifest['stoppedExperimentHashes'])
    result['reportHash'] = content_hash(result)
    write_once(folder / 'report.json', encode(result))
    return folder / 'report.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['qualify', 'train', 'run'])
    parser.add_argument('--repo-root', type=Path, default=Path('.'))
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    contract, spec = load_contract(root)
    manifest = qualify(root, contract, spec) if args.command in ('qualify', 'run') else args.manifest
    if manifest is None:
        parser.error('train requires --manifest')
    print(json.dumps({'datasetManifest': str(manifest)}, sort_keys=True), flush=True)
    if args.command in ('train', 'run'):
        report = train(root, manifest, contract, spec)
        print(json.dumps({'report': str(report), 'finalEvaluationOpened': False}, sort_keys=True))


if __name__ == '__main__':
    main()
