from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from spy_predictor_quant.cycle1_successor_config import load_successor_config, STREAM_LAWS
from spy_predictor_quant.cycle1_successor_pipeline import adapt_evidence, evaluate_evidence
from spy_predictor_quant.cycle1_evaluator import score_partition
from spy_predictor_quant.cycle1_downside import event_forecasts

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / 'config/cycle1-v5-draft.json').read_text())


@pytest.fixture(scope='module')
def evidence():
    from spy_predictor_quant.cycle1_successor_fixture import deterministic_evidence
    return deterministic_evidence(load_successor_config(ROOT), CONFIG)


def test_final_configuration_preserves_authorities_and_independent_primitive_laws():
    design = load_successor_config(ROOT)
    proposal = json.loads((ROOT / 'config/cycle1-simulation-v2-proposal.json').read_text())
    assert all(design[key] == value for key, value in proposal['preserved'].items())
    assert design['acceptance'] == proposal['acceptance']
    assert not any(design['permissions'].values())
    fields = {row['field']: row for row in design['streams']['substreams']}
    assert set(fields) == set(STREAM_LAWS)
    assert len({row['ordinal'] for row in fields.values()}) == len(fields)
    assert fields['spy_student']['ordinal'] != fields['spy_overnight']['ordinal']
    assert fields['spy_student']['ordinal'] != fields['qqq_student']['ordinal']
    assert fields['baseline_uniform']['law'] == 'uniform-[0,1)'


@pytest.mark.parametrize('mutation', ['threshold', 'stream', 'repair'])
def test_rehashed_mutation_cannot_change_final_laws(tmp_path, monkeypatch, mutation):
    import spy_predictor_quant.cycle1_successor_config as authority
    from spy_predictor_quant.market_archive import content_hash
    design = deepcopy(load_successor_config(ROOT))
    proposal = json.loads((ROOT / 'config/cycle1-simulation-v2-proposal.json').read_text())
    if mutation == 'threshold':
        design['acceptance']['powerLowerMinimum'] = .5
    elif mutation == 'stream':
        design['streams']['substreams'][7]['ordinal'] = 6
    else:
        design['equations']['repaired'] = False
    design['designHash'] = content_hash({k: v for k, v in design.items() if k != 'designHash'})
    (tmp_path / 'config').mkdir()
    (tmp_path / 'schemas').mkdir()
    (tmp_path / authority.CONFIG_PATH).write_text(json.dumps(design))
    # Even a replaced permissive schema cannot bypass semantic authorities.
    (tmp_path / authority.SCHEMA_PATH).write_text('{}')
    monkeypatch.setattr(authority, 'load_proposal', lambda root: proposal)
    with pytest.raises(ValueError, match='linked final laws'):
        authority.load_successor_config(tmp_path)


def test_daily_evidence_feeds_real_features_and_exact_endpoints(evidence):
    paths, extra = adapt_evidence(evidence, CONFIG)
    for name, path in paths.items():
        assert len(path.months) == 439
        for i, row in enumerate(evidence['features'][name]):
            if row['status'] == 'AVAILABLE':
                np.testing.assert_array_equal(path.dimensions[i], [row['dimensionScores'][k] for k in ('valuation', 'stress', 'direction')])
                assert path.volatility[i] == row['rawFeatures']['realized-volatility-3m']
        np.testing.assert_allclose(path.outcomes[:-12], [path.monthly_returns[i+1:i+13].sum() for i in range(len(path.months)-12)], atol=1e-10)
    assert extra['selectionTape'].equity_returns.shape == (68,)
    assert extra['confirmationTape'].equity_returns.shape == (97,)
    assert np.isfinite(extra['drawdownEvents'][:-12]).all()
    assert not np.array_equal(paths['SPY'].dimensions, paths['QQQ'].dimensions, equal_nan=True)
    # Annual labels cannot masquerade as a monthly executable tape.
    selected = (paths['SPY'].months >= np.datetime64('2010-11')) & (paths['SPY'].months <= np.datetime64('2016-06'))
    assert not np.allclose(extra['selectionTape'].equity_returns, np.expm1(paths['SPY'].outcomes[selected]))


def test_complete_procedure_and_conditional_exercises_preserve_qualification(evidence):
    report = evaluate_evidence(evidence, CONFIG, exercise_branches=True)
    plain = evaluate_evidence(evidence, CONFIG)
    assert report['primary'] == plain['primary']
    assert len(report['ledger']) == 10
    assert not report['realDataApproval']
    assert report['downsideBranchExerciseOnly']['status'] == 'INSUFFICIENT_SUPPORT'
    for entry in report['transferBranchExerciseOnly']['entries']:
        assert entry['pairedMonths'] == 97
        assert entry['parametersRefittedOnQqq'] is False
    for entry in report['policyBranchExerciseOnly']:
        assert len(entry['costCases']) == 2
        assert [case['costMultiplier'] for case in entry['costCases']] == [1, CONFIG['promotionGates']['economicPolicy']['stressCostMultiplier']]
    paths, extra = adapt_evidence(evidence, CONFIG)
    scores = score_partition(paths['SPY'], CONFIG, 'confirmation', retain_fits=True)
    predictions = [event_forecasts(cache, paths['SPY'], extra['drawdownEvents'], CONFIG)
                   for cache in scores.fitted.values()]
    assert any(np.isfinite(row).all() for row in predictions)


def test_rejects_legacy_identity_and_internal_session_gap(evidence):
    invalid = {**evidence, 'equationHash': 'legacy'}
    with pytest.raises(ValueError, match='repaired'):
        adapt_evidence(invalid, CONFIG)
    invalid = {**evidence, 'bars': dict(evidence['bars'])}
    bars = evidence['bars']['SPY']
    invalid['bars']['SPY'] = bars[:3000] + bars[3001:]
    with pytest.raises(ValueError, match='gap|boundaries'):
        adapt_evidence(invalid, CONFIG)
