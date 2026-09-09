from dataclasses import replace
from datetime import date

import pytest

from spy_predictor_quant.cycle1_calendar import _xnys
from spy_predictor_quant.cycle1_path_evidence import (
    SyntheticSessionLevels, derive_market_evidence,
)

ORIGIN = date(2020, 1, 31)


def tape():
    sessions = tuple(x.date() for x in _xnys().sessions_in_range('2020-01-02', '2021-02-26'))
    return SyntheticSessionLevels('SPY', sessions, (100.0,) * len(sessions), (100.0,) * len(sessions))


def test_daily_drawdown_and_open_policy_are_not_monthly_or_annual_labels():
    path = tape()
    closes = list(path.close_total_return_levels)
    opens = list(path.open_total_return_levels)
    # Intramonth loss disappears by month end, but must remain a downside event.
    closes[path.sessions.index(date(2020, 2, 12))] = 75.0
    # Entry gap differs from the close-to-close equity leg.
    opens[path.sessions.index(date(2020, 2, 3))] = 80.0
    result, = derive_market_evidence(replace(path, close_total_return_levels=tuple(closes),
                                            open_total_return_levels=tuple(opens)), (ORIGIN,))
    assert result['annualEquityLogReturn'] == 0
    assert result['maximumDailyCloseDrawdown'] == -0.25
    assert result['drawdownEvent'] is True
    assert result['monthlyExecutionEquityReturn'] == 0.25
    assert result['executionStart'] == '2020-02-03T14:30:00+00:00'
    assert result['executionEnd'] == '2020-03-02T14:30:00+00:00'
    assert result['completePrimaryTarget'] is False
    assert result['realDataApproval'] is False


def test_interior_missing_session_cannot_be_hidden_by_complete_endpoints():
    path = tape()
    index = path.sessions.index(date(2020, 2, 12))
    with pytest.raises(ValueError, match='Incomplete scheduled'):
        derive_market_evidence(replace(path, sessions=path.sessions[:index] + path.sessions[index + 1:],
                                      open_total_return_levels=path.open_total_return_levels[:-1],
                                      close_total_return_levels=path.close_total_return_levels[:-1]), (ORIGIN,))


def test_endpoint_missing_and_shifted_month_end_are_invalid():
    path = tape()
    with pytest.raises(ValueError, match='final scheduled'):
        derive_market_evidence(path, (date(2020, 1, 30),))
    length = path.sessions.index(date(2021, 1, 29))
    with pytest.raises(ValueError, match='endpoint is absent'):
        derive_market_evidence(replace(path, sessions=path.sessions[:length],
                                      open_total_return_levels=path.open_total_return_levels[:length],
                                      close_total_return_levels=path.close_total_return_levels[:length]), (ORIGIN,))


def test_future_levels_after_target_end_cannot_change_earlier_evidence():
    path = tape()
    baseline = derive_market_evidence(path, (ORIGIN,))
    closes = tuple(value * 7 if session > date(2021, 1, 29) else value
                   for session, value in zip(path.sessions, path.close_total_return_levels, strict=True))
    assert derive_market_evidence(replace(path, close_total_return_levels=closes), (ORIGIN,)) == baseline


@pytest.mark.parametrize('change', [
    {'evidence_tier': 'RECONSTRUCTED_RESEARCH_ONLY'},
    {'units': 'RAW_PRICES'},
    {'close_total_return_levels': ()},
])
def test_unqualified_inputs_are_rejected(change):
    with pytest.raises(ValueError):
        derive_market_evidence(replace(tape(), **change), (ORIGIN,))
