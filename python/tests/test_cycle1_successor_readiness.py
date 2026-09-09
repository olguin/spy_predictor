import json
import shutil
from pathlib import Path

import pytest

from spy_predictor_quant.cycle1_successor_readiness import annual_variance, review_readiness
from spy_predictor_quant.market_archive import content_hash

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = json.loads((ROOT / 'config/cycle1-simulation-v1.json').read_text())['scenarios'][0]


def test_constant_volatility_recovers_twelve_independent_months():
    scenario = {**SCENARIO, 'volatilityPersistence': 0., 'volatilityInnovationSd': 0.}
    assert annual_variance(-.5, scenario) == pytest.approx(.15 ** 2)
    assert annual_variance(.5, scenario) == pytest.approx(.15 ** 2)


def test_persistent_scale_changes_annual_variance_even_without_direct_skill():
    values = [annual_variance(g, SCENARIO) for g in (-.5, 0., .5)]
    assert 0 < values[0] < values[1] < values[2]


def test_analytic_variance_refuses_signal_or_crash_cases():
    for change in ({'signal': 'cycle'}, {'crashProbability': .01}, {'logScaleLoading': .2}):
        with pytest.raises(ValueError, match='no-loading, no-crash'):
            annual_variance(0., {**SCENARIO, **change})


def test_readiness_reproduces_support_failure_without_rng_or_registration(monkeypatch, tmp_path):
    import numpy as np
    def forbidden(*args, **kwargs):
        raise AssertionError('Readiness cannot open a random stream')
    monkeypatch.setattr(np.random, 'default_rng', forbidden)
    monkeypatch.setattr(np.random, 'Generator', forbidden)
    # Historical review is exercised on its unregistered authority snapshot,
    # independently of whether the real successor has since been registered.
    for directory in ('config', 'schemas'):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    decision_path = Path('experiments/cycle1-power-v1/decision.json')
    decision = json.loads((ROOT / decision_path).read_text())
    for path in (decision_path, Path(decision['reportPath'])):
        (tmp_path / path.parent).mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, tmp_path / path)
    report = review_readiness(tmp_path)
    assert report['status'] == 'NOT_READY_TO_FREEZE'
    assert report['dividendSupport']['status'] == 'POSITIVE_PRICE_SUPPORT_FAILURE'
    assert report['randomDraws'] == report['redesignSlotsConsumedByReview'] == 0
    assert report['runtimeProfile']['status'] == 'NOT_RUN'
    assert not report['annualNullProven'] and not report['realDataApproval']
    assert report['reportHash'] == content_hash({k: v for k, v in report.items() if k != 'reportHash'})
