from dataclasses import replace
from datetime import date
from fractions import Fraction
import json
import math
from pathlib import Path

import pytest

from spy_predictor_quant.cycle1_calendar import _xnys
from spy_predictor_quant.cycle1_null_law import MarkedKernel, Transition, audit_conditional_law
from spy_predictor_quant.cycle1_successor_equations import (
    MonthInnovations, SessionInnovations, run_equations, derive_successor_targets,
)
from spy_predictor_quant.cycle1_successor_laws import (
    NULL_IDS, reserve_distribution, compensate_distribution, partial_null_mean,
    validate_repair_scenario, iid_null_log_scale,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / 'config/cycle1-v5-draft.json').read_text())
SCENARIOS = json.loads((ROOT / 'config/cycle1-simulation-v1.json').read_text())['scenarios']


def inputs(start, end):
    first, last = start.year * 12 + start.month - 3, end.year * 12 + end.month - 1
    monthly = tuple(MonthInnovations(date(i // 12, i % 12 + 1, 1)) for i in range(first, last + 1))
    daily = tuple(SessionInnovations(row.date()) for row in _xnys().sessions_in_range(start.isoformat(), end.isoformat())[1:])
    return monthly, daily


@pytest.mark.parametrize('overnight,intraday', [(-12., 0.), (0., -12.), (3., -5.), (.1, .2)])
def test_reserved_distribution_is_positive_and_conserves_holder_wealth(overnight, intraday):
    op, cl, cash, correction = reserve_distribution(100., .0025, overnight, intraday)
    assert min(op, cl, cash) > 0
    assert cash == .25  # fixed before the shock
    assert cl + cash == pytest.approx(99.75 * math.exp(overnight + intraday) + .25)
    increments = [overnight, intraday, .03, -.01, .02, -.04]
    original = math.fsum(increments)
    compensate_distribution(increments, 2, correction)
    assert math.log((cl + cash) / 100) + math.fsum(increments[2:]) == pytest.approx(original)


def test_unrepresentable_path_invalidates_without_clipping():
    with pytest.raises(ArithmeticError, match='never redraw'):
        reserve_distribution(100., .0025, -1000., 0.)


def test_supported_shock_that_failed_old_engine_now_preserves_annual_target():
    start, end = date(2019, 12, 31), date(2020, 12, 31)
    monthly, daily = inputs(start, end)
    daily = tuple(replace(row, spy_overnight=-2000.) if row.session == date(2020, 3, 2) else row for row in daily)
    with pytest.raises(ValueError, match='must be positive'):
        run_equations(start=start, end=end, monthly=monthly, daily=daily, scenario=SCENARIOS[0], config=CONFIG)
    result = run_equations(start=start, end=end, monthly=monthly, daily=daily, scenario=SCENARIOS[0], config=CONFIG, repaired=True)
    for bars in result['bars'].values():
        assert all(row.raw_open > 0 and row.raw_close > 0 for row in bars)
    targets = derive_successor_targets(result, (start,))
    assert targets[0]['annualExcessLogReturn'] == pytest.approx(.04, abs=1e-12)
    assert targets[1]['annualExcessLogReturn'] == pytest.approx(.048, abs=1e-12)


@pytest.mark.parametrize('scenario', [s for s in SCENARIOS if s['id'] in NULL_IDS], ids=lambda s: s['id'])
def test_required_null_roles_and_stationary_marginal_scale_are_preserved(scenario):
    validate_repair_scenario(scenario)
    scale = scenario['volatilityInnovationSd'] / math.sqrt(1 - scenario['volatilityPersistence'] ** 2)
    assert iid_null_log_scale(scenario, 1.) == pytest.approx(scale)
    assert scenario['requirement'] == 'false-qualification-upper-bound'


def test_mutated_null_loading_is_rejected():
    with pytest.raises(ValueError, match='annual-null'):
        validate_repair_scenario({**SCENARIOS[0], 'logScaleLoading': .2})
    with pytest.raises(ValueError, match='annual-null'):
        validate_repair_scenario({**SCENARIOS[2], 'missingProbability': .02})


def test_actual_partial_null_marked_kernel_has_equal_full_annual_laws():
    # Current R determines the reward; the next R obeys the declared transition.
    # Extra state can persist without changing the joint next-R/reward kernel.
    stay = (1 + Fraction(str(SCENARIOS[2]['predictorPersistence']))) / 2
    groups = {f'{r}:{x}': str(r) for r in (-1, 1) for x in (0, 1)}
    rows = {key: tuple(Transition(f'{nxt}:{x}', r, prob * xp)
                      for nxt, prob in ((r, stay), (-r, 1 - stay))
                      for x, xp in ((extra, Fraction(99, 100)), (1 - extra, Fraction(1, 100))))
            for r in (-1, 1) for extra in (0, 1) for key in (f'{r}:{extra}',)}
    result = audit_conditional_law(MarkedKernel(groups, rows))
    assert result['sufficientAllHorizonCondition']
    assert all(p['equalTargetLaw'] for p in result['statePairs'])
    assert result['targetLaws']['-1:0'] != result['targetLaws']['1:0']
    for r in (-1, 1):
        law = result['targetLaws'][f'{r}:0']
        expected_sum = sum(int(reward) * Fraction(prob) for reward, prob in law.items())
        assert .04 + .08 / 12 * float(expected_sum) == pytest.approx(partial_null_mean(r, SCENARIOS[2]))


@pytest.fixture(scope='module')
def partial_paths():
    start, end = date(1999, 12, 31), date(2008, 12, 31)
    monthly, daily = inputs(start, end)
    monthly = tuple(replace(row, spy_student=math.sin(i), qqq_student=math.cos(i),
                            macro_normals=(math.sin(i), math.cos(i), .1, -.1),
                            baseline_uniform=0. if i % 9 == 0 else .5)
                    for i, row in enumerate(monthly))
    baseline = run_equations(start=start, end=end, monthly=monthly, daily=daily,
                            scenario=SCENARIOS[2], config=CONFIG, repaired=True)
    changed_daily = tuple(replace(row, spy_overnight=(-1.) ** i * 3.)
                          if row.session.year == 2007 else row for i, row in enumerate(daily))
    changed = run_equations(start=start, end=end, monthly=monthly, daily=changed_daily,
                           scenario=SCENARIOS[2], config=CONFIG, repaired=True)
    return baseline, changed


def test_actual_nine_feature_path_reveals_both_baseline_regimes(partial_paths):
    baseline, _ = partial_paths
    states = [s for s in baseline['features']['SPY'] if s['status'] == 'AVAILABLE']
    assert len(states) > 24
    assert {math.copysign(1, s['dimensionScores']['valuation']) for s in states} == {-1., 1.}
    for state in states:
        assert len(state['rawFeatures']) == len(state['normalizedFeatures']) == 9
        n = state['normalizationHistoryMonths']
        assert abs(state['dimensionScores']['valuation']) == pytest.approx((n - 1) / n)
    spy = [p for p in baseline['parameters'] if p['instrument'] == 'SPY' and p['featureStatus'] == 'AVAILABLE']
    assert {p['signal'] for p in spy} == {-1., 1.}
    assert all(p['monthlyMean'] == pytest.approx(.04 / 12 + .08 / 12 * p['signal']) for p in spy)


def test_different_observed_stress_cannot_change_partial_null_annual_return(partial_paths):
    baseline, changed = partial_paths
    origin = date(2007, 12, 31)
    states = [next(s for s in p['features']['SPY'] if s['origin'] == origin.isoformat()) for p in partial_paths]
    assert states[0]['dimensionScores']['stress'] != states[1]['dimensionScores']['stress']
    assert states[0]['dimensionScores']['valuation'] == states[1]['dimensionScores']['valuation']
    targets = [derive_successor_targets(p, (origin,))[0] for p in partial_paths]
    assert targets[0]['annualExcessLogReturn'] == pytest.approx(targets[1]['annualExcessLogReturn'], abs=1e-12)
    assert baseline['annualNullProven'] and changed['annualNullProven']


def test_past_volatility_state_cannot_change_null_monthly_endpoints():
    start, end = date(2019, 12, 31), date(2021, 12, 31)
    monthly, daily = inputs(start, end)
    monthly = tuple(replace(row, spy_student=.3, qqq_student=-.2) for row in monthly)
    changed_monthly = tuple(replace(row, volatility_normal=2.) if row.month.year == 2020 else row for row in monthly)
    paths = [run_equations(start=start, end=end, monthly=m, daily=daily, scenario=SCENARIOS[0], config=CONFIG, repaired=True)
             for m in (monthly, changed_monthly)]
    parameters = [[p for p in path['parameters'] if p['instrument'] == 'SPY' and p['month'] >= '2021'] for path in paths]
    assert parameters[0][0]['bridgeSigma'] != parameters[1][0]['bridgeSigma']
    assert [p['monthlyExcessLogReturn'] for p in parameters[0]] == [p['monthlyExcessLogReturn'] for p in parameters[1]]


def test_future_regime_marker_does_not_rewrite_earlier_features():
    start, end = date(2019, 12, 31), date(2020, 3, 31)
    monthly, daily = inputs(start, end)
    altered = tuple(replace(row, baseline_uniform=0., spy_student=2.) if row.month == date(2020, 3, 1) else row for row in monthly)
    paths = [run_equations(start=start, end=end, monthly=m, daily=daily, scenario=SCENARIOS[2], config=CONFIG, repaired=True)
             for m in (monthly, altered)]
    for instrument in ('SPY', 'QQQ'):
        assert paths[0]['features'][instrument][:-1] == paths[1]['features'][instrument][:-1]


@pytest.mark.parametrize('scenario', SCENARIOS, ids=lambda s: s['id'])
def test_each_scenario_keeps_monthly_cash_and_excess_accounting(scenario):
    start, end = date(2019, 12, 31), date(2020, 3, 31)
    monthly, daily = inputs(start, end)
    monthly = tuple(replace(row, spy_student=.7, qqq_student=-.4, volatility_normal=.3,
                            crash_uniform=0.) for row in monthly)
    daily = tuple(replace(row, spy_overnight=(-1.) ** i, spy_intraday=.2) for i, row in enumerate(daily))
    result = run_equations(start=start, end=end, monthly=monthly, daily=daily,
                          scenario=scenario, config=CONFIG, repaired=True)
    for p in result['parameters']:
        bars = result['bars'][p['instrument']]
        rows = [r for r in bars if r.session.isoformat()[:7] == p['month'][:7]]
        prior = bars[bars.index(rows[0]) - 1]
        realized = math.log(rows[-1].close_total_return_level / prior.close_total_return_level)
        assert realized == pytest.approx(p['monthlyExcessLogReturn'] + p['monthlyCashLogReturn'], abs=1e-12)
    assert result['annualNullProven'] == (scenario['id'] in NULL_IDS)
