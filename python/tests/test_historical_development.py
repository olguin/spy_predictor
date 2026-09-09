from copy import deepcopy
from datetime import date, datetime, timedelta
import json
import math
from pathlib import Path

import numpy as np
import pytest

from spy_predictor_quant import historical_development as dev

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def contract():
    return json.loads((ROOT / 'config/historical-development-v1.json').read_text())


@pytest.fixture(scope='module')
def fixture(contract):
    spec = json.loads((ROOT / 'config/cycle1-v5-draft.json').read_text())
    daily = []
    for i, s in enumerate(dev._xnys().sessions_in_range('1993-01-29', '2017-06-30')):
        day = s.date()
        if day.isoformat() in contract['missingDailySessions']:
            continue
        close = 100*math.exp(i*.0001 + .02*math.sin(i/23))
        daily.append({'instrument': 'SPY', 'sessionDate': day.isoformat(),
                      'eventTime': dev.xnys_session_close(day).isoformat(),
                      'provider': 'ibkr-trades-split-adjusted',
                      'open': close, 'close': close, 'low': close*.99, 'high': close*1.01})
    macro = []
    for i, m in enumerate(np.arange(np.datetime64('1991-01', 'M'), np.datetime64('2017-07', 'M'))):
        year, month = int(str(m)[:4]), int(str(m)[5:7])
        published = dev.xnys_session_close(dev.xnys_month_end(year, month))-timedelta(days=1)
        for series, value in [('CPIAUCSL', 100+i*.1), ('INDPRO', 90+i*.1+math.sin(i/5)),
                              ('MPRIME', 5+math.sin(i/8)), ('GS3M', 3+.3*math.cos(i/7))]:
            macro.append({'seriesId': series, 'observationDate': f'{m}-01',
                          'availableAt': published.isoformat(), 'realtimeStart': published.date().isoformat(),
                          'value': value, 'missing': False})
    sources = {'primary': daily, 'corporate-actions': [], 'macro-vintages': macro}
    rows, audit = dev.build_rows(sources, spec, contract)
    return sources, spec, rows, audit


def test_missing_revision_and_equal_timestamp_are_not_admitted():
    first = {'seriesId': 'GS3M', 'observationDate': '2000-01-01', 'realtimeStart': '2000-02-01',
             'availableAt': '2000-02-01T00:00:00+00:00', 'missing': False, 'value': 5}
    missing = {**first, 'availableAt': '2000-03-01T00:00:00+00:00', 'realtimeStart': '2000-03-01', 'missing': True, 'value': None}
    state = dev.VintageState([first, missing])
    assert not state.at(datetime.fromisoformat(first['availableAt']))['GS3M']
    assert state.at(datetime.fromisoformat(missing['availableAt']))['GS3M'][date(2000, 1, 1)] == 5
    assert not state.at(datetime.fromisoformat(missing['availableAt'])+timedelta(seconds=1))['GS3M']


def test_missingness_retains_calendar_and_blocks_incomplete_training(fixture, contract):
    _, _, rows, audit = fixture
    assert len(rows) == 200
    assert len(audit['unavailableFeatureOrigins']) == 26
    assert audit['monthlyCashPathChecks'] == 2400
    for mode in contract['modes']:
        eligible = 0
        for i, row in enumerate(rows):
            if row['snapshotDate'] < contract['forecastStart']:
                continue
            indices = dev.train_indices(rows, i, mode, contract)
            eligible += len(indices) >= 120
            assert all(rows[j]['dimensions'] is not None for j in indices)
            assert all(rows[j]['targetEndDate'] < row['snapshotDate'] for j in indices)
        assert eligible == 42


def test_future_prices_vintages_and_outcomes_leave_earlier_forecasts_unchanged(fixture, contract):
    sources, spec, rows, _ = fixture
    changed = deepcopy(sources)
    for r in changed['primary']:
        if r['sessionDate'] > '2014-12-31':
            for k in ('open', 'high', 'low', 'close'):
                r[k] *= 2
    for r in changed['macro-vintages']:
        if r['availableAt'] > '2014-12-31':
            r['value'] *= 1.2
    altered, _ = dev.build_rows(changed, spec, contract)
    i = next(i for i, r in enumerate(rows) if r['snapshotDate'] == '2014-12-31')
    assert rows[i]['dimensions'] == altered[i]['dimensions']
    for mode in contract['modes']:
        indices = dev.train_indices(rows, i, mode, contract)
        assert indices == dev.train_indices(altered, i, mode, contract)
        assert [rows[j] for j in indices] == [altered[j] for j in indices]
        def predict(data):
            fits = dev.fit_roster(np.array([data[j]['dimensions'] for j in indices]),
                np.array([data[j]['rawFeatures']['realized-volatility-3m'] for j in indices]),
                np.array([data[j]['outcome'] for j in indices]), spec['models']['perInstrument'])
            return {k: v.predict(np.array(data[i]['dimensions']), data[i]['rawFeatures']['realized-volatility-3m'])
                    for k, v in fits.items() if v is not None}
        before, after = predict(rows), predict(altered)
        assert before.keys() == after.keys()
        for model in before:
            np.testing.assert_array_equal(before[model], after[model])


def test_new_gap_or_distribution_on_missing_session_fails(fixture, contract):
    sources, spec, _, _ = fixture
    changed = {**sources, 'primary': sources['primary'][1:]}
    # Removing a first session changes the allowed warmup source, so remove an internal one.
    changed['primary'] = sources['primary'][:100]+sources['primary'][101:]
    with pytest.raises(ValueError, match='internal XNYS'):
        dev.build_rows(changed, spec, contract)
    changed = {**sources, 'corporate-actions': [{'actionId': 'missing', 'effectiveDate': '2004-07-12',
                'actionType': 'cash_dividend', 'raw': {'cash': 1}}]}
    with pytest.raises(ValueError, match='ex-session'):
        dev.build_rows(changed, spec, contract)


def test_final_evaluation_and_same_cutoff_label_are_excluded(fixture, contract):
    _, _, rows, _ = fixture
    changed = deepcopy(rows)
    changed[-1]['targetEndDate'] = '2017-07-31'
    with pytest.raises(ValueError, match='development path'):
        dev.validate_rows(changed, contract)
    i = len(rows)-1
    j = 0
    changed = deepcopy(rows)
    changed[j]['labelAvailableAt'] = changed[i]['snapshotCutoff']
    assert j not in dev.train_indices(changed, i, 'expanding', contract)


def test_immutable_outputs_and_confined_paths(tmp_path):
    path = tmp_path / 'test.json'
    dev.write_once(path, b'first')
    dev.write_once(path, b'first')
    with pytest.raises(ValueError, match='Immutable'):
        dev.write_once(path, b'changed')
    with pytest.raises(ValueError, match='escapes'):
        dev.confined(tmp_path, '../outside.json')
    with pytest.raises(ValueError, match='Hash mismatch'):
        dev.verify(tmp_path, {'test.json': 'bad'})


def test_training_requires_qualified_current_code(tmp_path, contract):
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps({'status': 'UNQUALIFIED', 'finalEvaluationIncluded': False}))
    with pytest.raises(ValueError, match='not qualified'):
        dev.train(tmp_path, path, contract, {})
    path.write_text(json.dumps({'status': 'QUALIFIED_FOR_DEVELOPMENT_ONLY', 'finalEvaluationIncluded': False,
                               'identity': {}, 'datasetHash': 'wrong'}))
    with pytest.raises(ValueError, match='authority mismatch'):
        dev.train(tmp_path, path, contract, {})


def test_training_outputs_keep_missing_dates_and_resume_exactly(tmp_path, fixture, contract, monkeypatch):
    _, spec, rows, _ = fixture
    monkeypatch.setattr(dev, 'code_hashes', lambda root: {})
    data = tmp_path/'development.ndjson'
    data.write_bytes(dev.ndjson(rows))
    identity = {'contractHash': dev.content_hash(contract), 'codeHashes': {},
                'sourceHashes': {}, 'rowsHash': dev.content_hash(rows)}
    manifest = {'identity': identity, 'datasetHash': dev.content_hash(identity),
                'status': 'QUALIFIED_FOR_DEVELOPMENT_ONLY', 'finalEvaluationIncluded': False,
                'artifacts': {'development.ndjson': dev.file_sha256(data)},
                'dataPath': 'development.ndjson', 'stoppedExperimentHashes': {}}
    path = tmp_path/'manifest.json'
    path.write_bytes(dev.encode(manifest))
    report = dev.train(tmp_path, path, contract, spec)
    first = report.read_bytes()
    result = json.loads(first)
    assert not result['researchQualified']
    assert not result['finalEvaluation']['opened']
    forecasts = [json.loads(line) for line in (report.parent/'forecasts.ndjson').read_text().splitlines()]
    assert len(forecasts) == 68*2*7
    assert max(r['date'] for r in forecasts) == '2016-06-30'
    for mode in contract['modes']:
        for model in dev.MODEL_IDS:
            assert sum(r['status'] == 'SCORED' for r in forecasts if r['mode'] == mode and r['modelId'] == model) == 42
    assert dev.train(tmp_path, path, contract, spec).read_bytes() == first
    data.write_bytes(data.read_bytes()+b'\n')
    with pytest.raises(ValueError, match='Hash mismatch'):
        dev.train(tmp_path, path, contract, spec)
