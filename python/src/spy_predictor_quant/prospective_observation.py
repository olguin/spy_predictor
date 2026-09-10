"""Immutable observation-only registry for a static prospective SPY baseline."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

from spy_predictor_quant import historical_development as dev
from spy_predictor_quant.cycle1_calendar import xnys_month_end, xnys_next_session_open, xnys_session_close
from spy_predictor_quant.cycle1_models import distribution_scores

CONFIG = 'config/prospective-observation-v1.json'


def authority(root):
    config = json.loads((root / CONFIG).read_text())
    required = {'schemaVersion': 'prospective-observation-v1', 'status': 'FROZEN_OBSERVATION_ONLY',
                'instrument': 'SPY', 'modelId': 'unconditional-history-expanding-static',
                'fitCutoff': '2016-06-30', 'fitMode': 'expanding', 'minimumTrainingLabels': 120,
                'horizonMonths': 12, 'minimumMatureOutcomesBeforeReview': 12,
                'interimPerformanceTestingAllowed': False, 'tradingAllowed': False,
                'allocationAllowed': False, 'deploymentQualified': False,
                'finalEvaluationAccessAllowed': False,
                'reservedHistoricalPeriod': {'start': '2017-07-31', 'end': '2025-07-31'}}
    if any(config.get(k) != v for k, v in required.items()):
        raise ValueError('Prospective authority differs from frozen observation contract')
    if config['scheduledOrigins'] != dev.calendar('2026-09-30', '2027-08-31'):
        raise ValueError('Prospective schedule differs from literal XNYS month ends')
    source_manifest = json.loads((root / config['sourceDatasetManifest']).read_text())
    if source_manifest['datasetHash'] != config['sourceDatasetHash'] or dev.content_hash(source_manifest['identity']) != config['sourceDatasetHash']:
        raise ValueError('Source dataset identity changed')
    dev.verify(root, source_manifest['artifacts'])
    dev.verify(root, source_manifest['identity']['sourceHashes'])
    report = json.loads((root / config['sourceDevelopmentReport']).read_text())
    if report['reportHash'] != config['sourceDevelopmentReportHash'] or dev.content_hash({k: v for k, v in report.items() if k != 'reportHash'}) != config['sourceDevelopmentReportHash']:
        raise ValueError('Source development report identity changed')
    dev.verify(root, report['artifacts'])
    dev.verify(root, config['stoppedDecisions'])
    return config, source_manifest


def frozen_distribution(root, config, manifest):
    rows = [json.loads(line) for line in (root / manifest['dataPath']).read_text().splitlines()]
    dev.validate_rows(rows, json.loads((root / 'config/historical-development-v1.json').read_text()))
    index = next(i for i, row in enumerate(rows) if row['snapshotDate'] == config['fitCutoff'])
    indices = dev.train_indices(rows, index, config['fitMode'],
                                json.loads((root / 'config/historical-development-v1.json').read_text()))
    if len(indices) < config['minimumTrainingLabels']:
        raise ValueError('Frozen reference lacks training support')
    samples = np.asarray([rows[i]['outcome'] for i in indices], dtype=float)
    if len(samples) != 161 or not np.isfinite(samples).all():
        raise ValueError('Frozen reference distribution identity changed')
    return samples, [rows[i]['snapshotDate'] for i in indices]


def register(root):
    config, manifest = authority(root)
    samples, origins = frozen_distribution(root, config, manifest)
    identity = {'contractSha256': dev.file_sha256(root / CONFIG),
                'sourceDatasetHash': config['sourceDatasetHash'],
                'sourceDevelopmentReportHash': config['sourceDevelopmentReportHash'],
                'runnerSha256': dev.file_sha256(Path(__file__)),
                'samplesHash': dev.content_hash(samples.tolist())}
    cohort_hash = dev.content_hash(identity)
    folder = root / 'experiments' / f'prospective-observation-{cohort_hash[:16]}'
    registration = {'schemaVersion': 'prospective-observation-registration-v1',
                    'cohortHash': cohort_hash, 'identity': identity,
                    'status': 'REGISTERED_OBSERVATION_ONLY',
                    'modelId': config['modelId'], 'sampleCount': len(samples),
                    'trainingOrigins': origins, 'scheduledOrigins': config['scheduledOrigins'],
                    'forecastsIssued': 0, 'matureOutcomes': 0,
                    'performanceReviewAllowed': False, 'tradingAllowed': False,
                    'finalEvaluationOpened': False}
    dev.write_once(folder / 'registration.json', dev.encode(registration))
    dev.write_once(folder / 'distribution.json', dev.encode({'samples': samples.tolist(),
                    'sampleCount': len(samples), 'samplesHash': identity['samplesHash']}))
    return folder, registration


def schedule_state(folder, registration, config, now):
    now = now.astimezone(timezone.utc)
    issued = sorted(p.stem for p in (folder / 'forecasts').glob('*.json')) if (folder/'forecasts').exists() else []
    due = []
    missed = []
    for origin in config['scheduledOrigins']:
        close = xnys_session_close(date.fromisoformat(origin))
        _, next_open = xnys_next_session_open(date.fromisoformat(origin))
        if close <= now < next_open and origin not in issued:
            due.append(origin)
        if next_open <= now and origin not in issued:
            missed.append(origin)
    future = [o for o in config['scheduledOrigins'] if xnys_session_close(date.fromisoformat(o)) > now]
    return {'dueOrigins': due, 'missedOrigins': missed,
            'nextOrigin': future[0] if future else None, 'issuedOrigins': issued}


def issue(root, now):
    folder, registration = register(root)
    config, _ = authority(root)
    state = schedule_state(folder, registration, config, now)
    due = state['dueOrigins']
    if not due:
        return {'status': 'NOT_DUE', 'cohortHash': registration['cohortHash'],
                'nextOrigin': state['nextOrigin'], 'issuedOrigins': state['issuedOrigins'],
                'missedOrigins': state['missedOrigins'],
                'performanceReviewAllowed': False, 'finalEvaluationOpened': False}
    if len(due) != 1:
        raise ValueError('Expected at most one due monthly origin')
    origin = due[0]
    distribution = json.loads((folder / 'distribution.json').read_text())
    samples = np.asarray(distribution['samples'], dtype=float)
    forecast = {'schemaVersion': 'prospective-observation-forecast-v1',
                'cohortHash': registration['cohortHash'], 'instrument': 'SPY',
                'modelId': config['modelId'], 'origin': origin,
                'forecastCutoff': xnys_session_close(date.fromisoformat(origin)).isoformat(),
                'issuedAt': now.isoformat(), 'horizonMonths': 12,
                'targetEndDate': xnys_month_end(date.fromisoformat(origin).year + 1,
                                                date.fromisoformat(origin).month).isoformat(),
                'samplesHash': distribution['samplesHash'], 'sampleCount': len(samples),
                'predictiveMean': float(samples.mean()),
                'quantiles': {str(q): float(np.quantile(samples, q, method='inverted_cdf')) for q in (.05, .25, .5, .75, .95)},
                'outcomeAttached': False, 'performanceMetricsAvailable': False,
                'tradingAllowed': False, 'finalEvaluationOpened': False}
    dev.write_once(folder / 'forecasts' / f'{origin}.json', dev.encode(forecast))
    return {'status': 'ISSUED', **forecast}


def attach_outcome(root, origin, outcome, available_at, now):
    folder, registration = register(root)
    config, _ = authority(root)
    if origin not in config['scheduledOrigins']:
        raise ValueError('Origin is outside the frozen cohort')
    forecast_path = folder / 'forecasts' / f'{origin}.json'
    if not forecast_path.exists():
        raise ValueError('Forecast must be issued before an outcome can be attached')
    now, available_at = now.astimezone(timezone.utc), available_at.astimezone(timezone.utc)
    if now < available_at:
        raise ValueError('Outcome is not available yet')
    forecast = json.loads(forecast_path.read_text())
    distribution = json.loads((folder / 'distribution.json').read_text())
    scores = distribution_scores(np.asarray(distribution['samples']), outcome)
    record = {'schemaVersion': 'prospective-observation-outcome-v1',
              'cohortHash': registration['cohortHash'], 'origin': origin,
              'outcome': outcome, 'availableAt': available_at.isoformat(), 'attachedAt': now.isoformat(),
              'crps': scores[0], 'squaredError': scores[1], 'covered90': scores[2],
              'intervalWidth90': scores[3], 'interimAggregatePerformanceHidden': True,
              'performanceReviewAllowed': False}
    dev.write_once(folder / 'outcomes' / f'{origin}.json', dev.encode(record))
    return {'status': 'OUTCOME_ATTACHED_NO_INTERIM_REVIEW', 'origin': origin}


def status(root, now):
    folder, registration = register(root)
    config, _ = authority(root)
    state = schedule_state(folder, registration, config, now)
    issued = list((folder/'forecasts').glob('*.json')) if (folder/'forecasts').exists() else []
    outcomes = list((folder/'outcomes').glob('*.json')) if (folder/'outcomes').exists() else []
    return {'status': 'DUE' if state['dueOrigins'] else 'NOT_DUE',
            'cohortHash': registration['cohortHash'], **state,
            'registrationPath': str(folder/'registration.json'), 'issuedCount': len(issued),
            'matureOutcomeCount': len(outcomes), 'reviewThreshold': 12,
            'performanceReviewAllowed': len(outcomes) >= 12,
            'finalEvaluationOpened': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('register', 'issue', 'status'))
    parser.add_argument('--now', type=datetime.fromisoformat)
    args = parser.parse_args()
    root = Path('.').resolve()
    now = args.now or datetime.now(timezone.utc)
    if args.action == 'register':
        folder, registration = register(root)
        result = {'status': registration['status'], 'cohortHash': registration['cohortHash'],
                  'registrationPath': str(folder/'registration.json')}
    elif args.action == 'issue':
        result = issue(root, now)
    else:
        result = status(root, now)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
