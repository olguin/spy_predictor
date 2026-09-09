from dataclasses import replace
from datetime import date, timedelta
import json
import math
from pathlib import Path

import pytest

from spy_predictor_quant.cycle1_calendar import _xnys, xnys_session_close
from spy_predictor_quant.cycle1_successor_inputs import select_vintages
from spy_predictor_quant.cycle1_successor_equations import (
    EQUATION_SPEC, EQUATION_HASH, MonthInnovations, SessionInnovations, RawSession,
    macro_path, run_equations, derive_successor_targets, execution_equity_return,
)
from spy_predictor_quant.market_archive import content_hash

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / 'config/cycle1-v5-draft.json').read_text())
SCENARIOS = json.loads((ROOT / 'config/cycle1-simulation-v1.json').read_text())['scenarios']


def inputs(start, end):
    first = start.year * 12 + start.month - 3
    last = end.year * 12 + end.month - 1
    monthly = tuple(MonthInnovations(date(index // 12, index % 12 + 1, 1)) for index in range(first, last + 1))
    daily = tuple(SessionInnovations(row.date()) for row in _xnys().sessions_in_range(start.isoformat(), end.isoformat())[1:])
    return monthly, daily


def run(start=date(2019, 12, 31), end=date(2020, 3, 31), scenario=SCENARIOS[0], monthly=None, daily=None):
    m, d = inputs(start, end)
    return run_equations(start=start, end=end, monthly=m if monthly is None else monthly,
                         daily=d if daily is None else daily, scenario=scenario, config=CONFIG)


def test_defaults_are_identity_bound_and_no_stream_or_approval_exists(monkeypatch):
    import numpy as np
    def prohibited(*args, **kwargs):
        raise AssertionError('Equation fixtures cannot draw randomness')
    monkeypatch.setattr(np.random, 'default_rng', prohibited)
    monkeypatch.setattr(np.random, 'Generator', prohibited)
    result = run()
    assert result['equationHash'] == content_hash(EQUATION_SPEC) == EQUATION_HASH
    assert result['randomDraws'] == 0
    assert result['annualNullProven'] is False
    assert result['fullProcedureQualified'] is False
    assert result['realDataApproval'] is False


def test_monthly_total_keeps_excess_effect_and_adds_observable_cash():
    result = run()
    for parameter in result['parameters']:
        instrument = parameter['instrument']
        month = parameter['month'][:7]
        bars = result['bars'][instrument]
        rows = [row for row in bars if row.session.isoformat()[:7] == month]
        prior = bars[bars.index(rows[0]) - 1]
        nominal = math.log(rows[-1].close_total_return_level / prior.close_total_return_level)
        multiplier = 1 if instrument == 'SPY' else 1.2
        assert parameter['monthlyExcessLogReturn'] == pytest.approx(multiplier * .04 / 12)
        assert nominal == pytest.approx(parameter['monthlyExcessLogReturn'] + parameter['monthlyCashLogReturn'], abs=1e-13)
        assert parameter['featureCutoff'] < rows[0].open_time.isoformat()
        assert parameter['signal'] == 0  # unavailable full nine-feature warmup


def test_nonzero_bridges_preserve_monthly_student_total_and_qqq_correlation():
    start, end = date(2019, 12, 31), date(2020, 1, 31)
    monthly, daily = inputs(start, end)
    monthly = tuple(replace(row, spy_student=1., qqq_student=-2.) if row.month == date(2020, 1, 1) else row for row in monthly)
    daily = tuple(replace(row, spy_overnight=(-1.) ** index, spy_intraday=.3,
                          qqq_intraday=-.4) for index, row in enumerate(daily))
    result = run(start, end, monthly=monthly, daily=daily)
    eps, other = 1 / math.sqrt(8 / 6), -2 / math.sqrt(8 / 6)
    expected = {'SPY': .04 / 12 + .15 / math.sqrt(12) * eps,
                'QQQ': 1.2 * (.04 / 12 + .15 / math.sqrt(12) * (.8 * eps + .6 * other))}
    for parameter in result['parameters']:
        bars = result['bars'][parameter['instrument']]
        assert math.log(bars[-1].close_total_return_level) - parameter['monthlyCashLogReturn'] == pytest.approx(expected[parameter['instrument']], abs=1e-13)


def test_macro_positive_equations_release_timing_revisions_and_tombstones():
    rows = (MonthInnovations(date(2020, 1, 1), revision_uniforms=(0., .5, .5, .5)),)
    records = macro_path(rows, .95)
    first = next(row for row in records if row.series == 'CPIAUCSL' and row.revision == 0)
    revised = next(row for row in records if row.series == 'CPIAUCSL' and row.revision == 1)
    assert first.value == pytest.approx(100 * math.exp(.02 / 12))
    assert first.published.isoformat() == '2020-02-15T13:30:00+00:00'
    assert revised.published.isoformat() == '2020-03-16T13:30:00+00:00'
    assert not select_vintages(records, 'CPIAUCSL', first.published - timedelta(seconds=1))
    assert select_vintages(records, 'CPIAUCSL', first.published)[date(2020, 1, 1)] == first
    assert select_vintages(records, 'CPIAUCSL', revised.published)[date(2020, 1, 1)].value is None
    assert all(row.value is None or row.value > 0 for row in records)


def test_future_supplied_innovations_cannot_change_completed_history():
    start, end = date(2019, 12, 31), date(2020, 3, 31)
    monthly, daily = inputs(start, end)
    baseline = run(start, end, monthly=monthly, daily=daily)
    changed_monthly = tuple(replace(row, spy_student=7., volatility_normal=2., macro_normals=(2., 2., 2., 2.))
                            if row.month >= date(2020, 3, 1) else row for row in monthly)
    changed_daily = tuple(replace(row, spy_overnight=1.) if row.session >= date(2020, 3, 1) else row for row in daily)
    changed = run(start, end, monthly=changed_monthly, daily=changed_daily)
    for instrument in ('SPY', 'QQQ'):
        assert [row for row in baseline['bars'][instrument] if row.session < date(2020, 3, 1)] == [row for row in changed['bars'][instrument] if row.session < date(2020, 3, 1)]
        assert baseline['features'][instrument][:-1] == changed['features'][instrument][:-1]


def test_actual_scheduled_early_close_and_session_gaps():
    start, end = date(2020, 10, 30), date(2020, 11, 30)
    monthly, daily = inputs(start, end)
    result = run(start, end, monthly=monthly, daily=daily)
    black_friday = next(row for row in result['bars']['SPY'] if row.session == date(2020, 11, 27))
    assert black_friday.close_time.hour == 18
    with pytest.raises(ValueError, match='Every following scheduled'):
        run(start, end, monthly=monthly, daily=daily[:3] + daily[4:])


def bar(day, opened, closed, split=1., dividend=0., level=1.):
    return RawSession('SPY', day, _xnys().session_open(day.isoformat()).to_pydatetime(),
                      xnys_session_close(day), opened, closed, split, dividend, level,
                      _xnys().session_open(day.isoformat()).to_pydatetime() - timedelta(days=1))


def test_open_execution_respects_entry_and_exit_dividend_entitlements():
    # Buy the ex-dividend share at 90: yesterday's 10 distribution is not yours.
    rows = (bar(date(2020, 3, 2), 90, 90, dividend=10), bar(date(2020, 3, 3), 99, 99))
    assert execution_equity_return(rows, rows[0].session, rows[-1].session) == pytest.approx(.1)
    # Hold yesterday's share through the next ex open: 90 sale + 10 entitlement.
    rows = (bar(date(2020, 3, 2), 100, 100), bar(date(2020, 3, 3), 90, 90, dividend=10))
    assert execution_equity_return(rows, rows[0].session, rows[-1].session) == pytest.approx(0.)


def test_split_same_day_distribution_uses_post_split_units_and_close_reinvestment():
    rows = (bar(date(2020, 3, 2), 100, 100),
            bar(date(2020, 3, 3), 45, 45, split=2, dividend=5),
            bar(date(2020, 3, 4), 49.5, 49.5))
    # 0.01 old shares -> 0.02 shares + 0.10 cash -> .022222 shares at close.
    assert execution_equity_return(rows, rows[0].session, rows[-1].session) == pytest.approx(.1)


def test_raw_split_and_dividend_construction_matches_close_total_return():
    result = run()
    rows = result['bars']['SPY']
    assert rows[1].split_factor == 2
    assert rows[1].raw_close < 51
    assert any(row.dividend_per_post_split_share > 0 for row in rows)
    for before, after in zip(rows, rows[1:]):
        growth = after.split_factor * (after.raw_close + after.dividend_per_post_split_share) / before.raw_close
        assert after.close_total_return_level / before.close_total_return_level == pytest.approx(growth)


def test_crash_occurs_in_one_shared_overnight_and_retains_monthly_total():
    monthly, daily = inputs(date(2019, 12, 31), date(2020, 1, 31))
    monthly = tuple(replace(row, crash_uniform=0., crash_timing_uniform=.5) for row in monthly)
    result = run(end=date(2020, 1, 31), scenario=SCENARIOS[8], monthly=monthly, daily=daily)
    dates = [parameter['crashSession'] for parameter in result['parameters']]
    assert dates[0] == dates[1] and dates[0] is not None
    for parameter in result['parameters']:
        multiplier = 1 if parameter['instrument'] == 'SPY' else 1.2
        assert parameter['monthlyExcessLogReturn'] == pytest.approx(multiplier * .04 / 12 - .25)


def test_annual_label_cash_cancels_and_missing_cpi_does_not_gate_target():
    result = run(end=date(2020, 12, 31))
    result['macroVintages'] = tuple(row for row in result['macroVintages'] if row.series != 'CPIAUCSL')
    targets = derive_successor_targets(result, (date(2019, 12, 31),))
    assert len(targets) == 2
    assert targets[0]['annualExcessLogReturn'] == pytest.approx(.04, abs=1e-12)
    assert targets[1]['annualExcessLogReturn'] == pytest.approx(.048, abs=1e-12)
    assert all(row['cpiRequired'] is False and row['realDataApproval'] is False for row in targets)
    assert targets[0]['labelAvailableAt'] == xnys_session_close(date(2020, 12, 31)).isoformat()


def test_invalid_innovations_rejected_before_equations():
    with pytest.raises(ValueError, match='finite'):
        SessionInnovations(date(2020, 1, 2), spy_intraday=float('nan'))
    with pytest.raises(ValueError, match='Uniform'):
        MonthInnovations(date(2020, 1, 1), crash_uniform=1.)
    with pytest.raises(ValueError, match='complete and chronological'):
        macro_path((MonthInnovations(date(2020, 1, 1)), MonthInnovations(date(2020, 3, 1))), .95)


def test_break_is_applied_at_origin_and_january1990_anchor_is_supported():
    result = run(scenario=SCENARIOS[7])
    spy = [p for p in result['parameters'] if p['instrument'] == 'SPY']
    assert [p['regimeMultiplier'] for p in spy] == [1, -1, -1]
    early = run(start=date(1990, 1, 31), end=date(1990, 2, 28))
    assert early['bars']['SPY'][0].session == date(1990, 1, 31)


def test_target_rejects_duplicate_day_and_inconsistent_action_level():
    result = run(end=date(2020, 12, 31))
    original = result['bars']['SPY']
    result['bars']['SPY'] = original[:4] + (original[3],) + original[5:]
    with pytest.raises(ValueError, match='daily session gap'):
        derive_successor_targets(result, (date(2019, 12, 31),))
    result['bars']['SPY'] = original[:4] + (replace(original[4], close_total_return_level=7),) + original[5:]
    with pytest.raises(ValueError, match='corporate-action units'):
        derive_successor_targets(result, (date(2019, 12, 31),))


def test_full_actual_nine_features_drive_next_month_own_instrument_parameters():
    # Long hand-constructed path, not a development replication. No RNG values.
    start, end = date(1999, 1, 29), date(2006, 3, 31)
    monthly, daily = inputs(start, end)
    monthly = tuple(replace(row, spy_student=math.sin(index), qqq_student=math.cos(index),
                            macro_normals=(math.sin(index), math.cos(index), .1, -.1))
                    for index, row in enumerate(monthly))
    result = run(start, end, scenario=SCENARIOS[4], monthly=monthly, daily=daily)
    by_key = {(row['instrument'], row['featureCutoff']): row for row in result['parameters']}
    for instrument, states in result['features'].items():
        available = [state for state in states[:-1] if state['status'] == 'AVAILABLE']
        assert available, 'Frozen 60-month raw + 24-month normalized warmup must finish'
        for state in available:
            assert len(state['rawFeatures']) == len(state['normalizedFeatures']) == 9
            parameter = by_key[(instrument, state['cutoff'])]
            assert parameter['signal'] == pytest.approx(sum(state['dimensionScores'].values()) / 3)
            assert parameter['monthlyMean'] == pytest.approx(.04 / 12 + .08 / 12 * parameter['signal'])
    assert result['features']['SPY'][-1]['dimensionScores'] != result['features']['QQQ'][-1]['dimensionScores']
