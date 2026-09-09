"""Post-output descriptive diagnostics on the immutable first development run."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from spy_predictor_quant import historical_development as dev

SOURCE = 'reports/historical-development/5ffd4a7b879d3237/report.json'
SOURCE_HASH = '9beaf08eb44d589c48622516bf09aa9847b11e9f94dc78acc45814b5a886a8a2'


def summarize(rows):
    available = [r for r in rows if r['status'] == 'SCORED']
    if not available:
        return {'scheduled': len(rows), 'scored': 0}
    bias, pit, cover50, cover90, widths, brier = [], [], [], [], [], []
    for r in available:
        samples = np.asarray(r['samples'], dtype=float)
        y = float(r['outcome'])
        if samples.size == 0 or not np.isfinite(samples).all() or not np.isfinite(y):
            raise ValueError('Invalid forecast distribution')
        quantiles = np.quantile(samples, [.05, .25, .75, .95], method='inverted_cdf')
        bias.append(float(samples.mean()-y))
        pit.append(float(np.mean(samples < y)+.5*np.mean(samples == y)))
        cover50.append(bool(quantiles[1] <= y <= quantiles[2]))
        cover90.append(bool(quantiles[0] <= y <= quantiles[3]))
        widths.append(float(quantiles[3]-quantiles[0]))
        brier.append(float((np.mean(samples > 0)-(y > 0))**2))
    return {'scheduled': len(rows), 'scored': len(available),
            'meanCrps': float(np.mean([r['crps'] for r in available])),
            'rmse': float(np.sqrt(np.mean([r['squaredError'] for r in available]))),
            'meanForecastMinusOutcome': float(np.mean(bias)),
            'coverage50': float(np.mean(cover50)), 'coverage90': float(np.mean(cover90)),
            'meanWidth90': float(np.mean(widths)),
            'pitHistogramFiveBins': np.histogram(pit, bins=np.linspace(0, 1, 6))[0].tolist(),
            'positiveExcessReturnBrier': float(np.mean(brier))}


def validate_calendar(rows):
    expected = {(d, mode, model) for d in dev.calendar('2010-11-30', '2016-06-30')
                for mode in ('expanding', 'rolling') for model in dev.MODEL_IDS}
    keys = [(r['date'], r['mode'], r['modelId']) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('Forecasts differ from the development-only calendar')
    if any(r['status'] not in ('SCORED', 'UNAVAILABLE') for r in rows):
        raise ValueError('Unknown forecast status')


def diagnose(rows):
    validate_calendar(rows)
    summaries, eras, sensitivity = [], [], []
    for mode in ('expanding', 'rolling'):
        mode_rows = [r for r in rows if r['mode'] == mode]
        date_sets = [{r['date'] for r in mode_rows if r['modelId'] == model and r['status'] == 'SCORED'}
                     for model in dev.MODEL_IDS]
        if any(s != date_sets[0] for s in date_sets):
            raise ValueError('Model dates differ; paired diagnostics would be misleading')
        for model in dev.MODEL_IDS:
            subset = [r for r in mode_rows if r['modelId'] == model]
            summaries.append({'mode': mode, 'modelId': model, **summarize(subset)})
            for year in ('2013', '2014', '2015', '2016'):
                eras.append({'mode': mode, 'modelId': model, 'year': year,
                             **summarize([r for r in subset if r['date'].startswith(year)])})
                sensitivity.append({'mode': mode, 'modelId': model, 'excludedYear': year,
                                    **summarize([r for r in subset if not r['date'].startswith(year)])})
    return {'summary': summaries, 'calendarYearDiagnostics': eras,
            'leaveOneYearOutDiagnostics': sensitivity,
            'interpretation': 'Post-output descriptive analysis; annual forecasts overlap; years are not independent tests; no refitting or tuning.',
            'partialYear': '2016 contains January-June origins only',
            'modelsRefitted': False, 'modelPromoted': False, 'finalEvaluationOpened': False}


def run(root):
    source_path = root / SOURCE
    source = json.loads(source_path.read_text())
    if source['reportHash'] != SOURCE_HASH or dev.content_hash({k: v for k, v in source.items() if k != 'reportHash'}) != SOURCE_HASH:
        raise ValueError('First run identity changed')
    dev.verify(root, source['artifacts'])
    dev.verify(root, source['identity']['codeHashes'])
    c, _ = dev.load_contract(root)
    forecast_path = source_path.parent / 'forecasts.ndjson'
    rows = [json.loads(line) for line in forecast_path.read_text().splitlines()]
    report = diagnose(rows)
    report['identity'] = {'sourceReportHash': SOURCE_HASH, 'sourceFileSha256': dev.file_sha256(source_path),
                          'forecastSha256': dev.file_sha256(forecast_path),
                          'diagnosticCodeSha256': dev.file_sha256(Path(__file__)),
                          'purpose': 'User directed moving forward with existing development evidence; gap work deferred.'}
    report['reportHash'] = dev.content_hash(report)
    folder = root / 'reports/historical-development' / f"diagnostics-{report['reportHash'][:16]}"
    dev.write_once(folder / 'report.json', dev.encode(report))
    lines = ['# Development diagnostics', '',
             'Post-output review of the first run. No new fitting, parameter search, promotion, or final evaluation.', '',
             'All seven models use the same 42 scored forecast dates per mode. The other 26 dates remain unavailable.', '',
             'CRPS and bias are in annual excess log-return units. Bias = forecast mean minus realized outcome.', '',
             '| Mode | Model | CRPS | Mean bias | 50% coverage | 90% coverage | Mean 90% width |',
             '|---|---|---:|---:|---:|---:|---:|']
    for r in report['summary']:
        lines.append(f"| {r['mode']} | {r['modelId']} | {r['meanCrps']:.6f} | {r['meanForecastMinusOutcome']:.4f} | {r['coverage50']:.1%} | {r['coverage90']:.1%} | {r['meanWidth90']:.4f} |")
    lines += ['', '## Stability across forecast-origin years', '',
              'The table shows the lowest CRPS in each slice. This is a diagnostic, not a model-selection rule. Annual targets overlap; 2016 covers six months.', '',
              '| Mode | Origin year | Lowest-CRPS model | CRPS |', '|---|---|---|---:|']
    for mode in ('expanding', 'rolling'):
        for year in ('2013', '2014', '2015', '2016'):
            records = [r for r in report['calendarYearDiagnostics'] if r['mode'] == mode and r['year'] == year]
            best = min(records, key=lambda r: r['meanCrps'])
            lines.append(f"| {mode} | {year} | {best['modelId']} | {best['meanCrps']:.6f} |")
    lines += ['', '## Sensitivity to excluding a year', '',
              'These calculations reuse saved forecasts; they do not retrain models. They are post-output sensitivity checks, not additional validation samples.', '',
              '| Mode | Excluded origin year | Lowest-CRPS model on remaining dates | CRPS |', '|---|---|---|---:|']
    for mode in ('expanding', 'rolling'):
        for year in ('2013', '2014', '2015', '2016'):
            records = [r for r in report['leaveOneYearOutDiagnostics'] if r['mode'] == mode and r['excludedYear'] == year]
            best = min(records, key=lambda r: r['meanCrps'])
            lines.append(f"| {mode} | {year} | {best['modelId']} | {best['meanCrps']:.6f} |")
    lines += ['', 'PIT histograms, positive-excess-return Brier scores, and every model/year result are in [report.json](report.json). Positive excess return is not a drawdown event or a policy backtest.', '',
              'Coverage alone does not establish calibration: wide intervals can cover nearly every outcome. No interval rescaling is selected from this small sample.', '']
    dev.write_once(folder / 'summary.md', '\n'.join(lines).encode())
    dev.verify(root, c['stoppedDecisions'])
    dev.verify(root, source['artifacts'])
    print(folder / 'summary.md')
    return folder


if __name__ == '__main__':
    run(Path('.').resolve())
