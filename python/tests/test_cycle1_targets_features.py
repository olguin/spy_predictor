from __future__ import annotations

import math
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from spy_predictor_quant.cycle1_calendar import xnys_month_end, xnys_session_close
from spy_predictor_quant.cycle1_config import load_cycle1_plan
from spy_predictor_quant.cycle1_features import (
    _VintageIndex,
    _latest_common_spread,
    _exact_lagged_spread,
    build_cycle_features,
    fit_fold_standardizer,
    vintage_values_as_of,
)
from spy_predictor_quant.cycle1_fred import normalize_fred_observation
from spy_predictor_quant.cycle1_states import assign_cycle_states
from spy_predictor_quant.cycle1_targets import (
    TotalReturnPoint,
    build_cycle_targets,
    construct_total_return_index,
    eligible_training_targets,
    max_drawdown,
    month_end_points,
    observable_cash_rates,
    rolled_cash_log_return,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_cycle1_plan(REPO_ROOT / "config" / "cycle1.json").raw


def _month(index: int) -> date:
    ordinal = 2000 * 12 + index
    return xnys_month_end(ordinal // 12, ordinal % 12 + 1)


def _points(months: int = 150) -> list[TotalReturnPoint]:
    return [
        TotalReturnPoint(
            session_date=_month(index),
            event_time=xnys_session_close(_month(index)),
            close=100 * math.exp(index * 0.005),
            total_return_index=math.exp(index * 0.005 + 0.03 * math.sin(index / 5)),
        )
        for index in range(months)
    ]


def _macro(months: int = 150) -> list[dict]:
    records = []
    for index in range(months):
        observation = _month(index).replace(day=1)
        release = _month(index + 1).replace(day=10)
        for series, value in (
            ("CPIAUCSL", 100 + index * 0.2),
            ("DGS3MO", 2 + index * 0.001),
            ("INDPRO", 90 + index * 0.1),
            ("MPRIME", 5 + 0.4 * math.sin(index / 7)),
            ("GS3M", 2 + 0.2 * math.sin(index / 9)),
        ):
            available = observation if series == "DGS3MO" else release
            records.append(
                normalize_fred_observation(
                    series,
                    {
                        "date": observation.isoformat(),
                        "realtime_start": available.isoformat(),
                        "realtime_end": "9999-12-31",
                        "value": str(value),
                    },
                    "2026-09-06T00:00:00+00:00",
                )
            )
    return records


def test_month_end_uses_final_observed_session_not_calendar_day() -> None:
    points = [
        TotalReturnPoint(date(2024, 3, 27), datetime(2024, 3, 27, 20, tzinfo=timezone.utc), 100, 1.0),
        TotalReturnPoint(date(2024, 3, 28), datetime(2024, 3, 28, 17, tzinfo=timezone.utc), 101, 1.01),
        TotalReturnPoint(date(2024, 4, 1), datetime(2024, 4, 1, 20, tzinfo=timezone.utc), 102, 1.02),
    ]
    assert [point.session_date for point in month_end_points(points)] == [date(2024, 3, 28)]


def test_month_end_rejects_a_missing_completed_final_session() -> None:
    points = [
        TotalReturnPoint(
            date(2024, 4, 29),
            datetime(2024, 4, 29, 20, tzinfo=timezone.utc),
            100,
            1.0,
        ),
        TotalReturnPoint(
            date(2024, 5, 1),
            datetime(2024, 5, 1, 20, tzinfo=timezone.utc),
            101,
            1.01,
        ),
    ]
    with pytest.raises(ValueError, match="Missing final scheduled XNYS session"):
        month_end_points(points)


def test_total_return_index_handles_split_and_cash_distribution() -> None:
    rows = [
        {"sessionDate": "2024-01-02", "eventTime": "2024-01-02T21:00:00+00:00", "close": 100},
        {"sessionDate": "2024-01-03", "eventTime": "2024-01-03T21:00:00+00:00", "close": 51},
    ]
    actions = [
        {"effectiveDate": "2024-01-03", "actionType": "forward_split", "raw": {"old_rate": 1, "new_rate": 2}},
        {"effectiveDate": "2024-01-03", "actionType": "cash_dividend", "raw": {"cash": 1}},
    ]
    result = construct_total_return_index(rows, actions)
    assert math.isclose(result[-1].total_return_index, 1.03)


def test_targets_freeze_real_excess_drawdown_and_next_session_execution() -> None:
    points = _points(30)
    targets = build_cycle_targets(
        instrument="SPY", daily_points=points, macro_vintages=_macro(32), config=CONFIG
    )
    first = targets[0]
    assert math.isclose(
        first["realExcessLogReturn12m"],
        first["nominalEquityLogReturn12m"] - first["nominalCashLogReturn12m"],
    )
    assert first["diagnosticPromotionEligible"] is False
    assert first["earliestPolicyExecution"].endswith("14:30:00+00:00")
    assert first["targetEndDate"] == _month(12).isoformat()
    path = [
        TotalReturnPoint(date(2024, 1, index + 1), datetime(2024, 1, index + 1, tzinfo=timezone.utc), 100, level)
        for index, level in enumerate((1.0, 1.2, 0.9, 1.1))
    ]
    assert math.isclose(max_drawdown(path), -0.25)


def test_unmatured_target_is_never_available_for_training() -> None:
    targets = build_cycle_targets(
        instrument="SPY", daily_points=_points(30), macro_vintages=_macro(32), config=CONFIG
    )
    target = targets[0]
    before = datetime.fromisoformat(target["labelAvailableAt"])
    assert target not in eligible_training_targets(targets, before)
    after = datetime(2002, 1, 1, tzinfo=timezone.utc)
    assert target in eligible_training_targets(targets, after)


def test_future_prices_and_macro_revisions_cannot_change_old_feature_vectors() -> None:
    points = _points(150)
    macro = _macro(152)
    original, _ = build_cycle_features(
        instrument="SPY", daily_points=points, macro_vintages=macro, config=CONFIG
    )
    assert original
    old = original[-1]
    revised = list(macro)
    revised.append(
        normalize_fred_observation(
            "INDPRO",
            {"date": "2005-01-01", "realtime_start": "2099-01-01", "realtime_end": "9999-12-31", "value": "9999"},
            "2099-01-01T00:00:00+00:00",
        )
    )
    extended, _ = build_cycle_features(
        instrument="SPY", daily_points=points + _points(151)[-1:], macro_vintages=revised, config=CONFIG
    )
    same = next(row for row in extended if row["snapshotDate"] == old["snapshotDate"])
    assert same["hash"] == old["hash"]
    assert same["componentEvidenceTiers"] == {
        "market": "RECONSTRUCTED_RESEARCH_ONLY",
        "macro": "POINT_IN_TIME_ADMISSIBLE",
    }


def test_incremental_vintage_index_matches_reference_cutoff_selection() -> None:
    records = _macro(36)
    index = _VintageIndex(records, ("CPIAUCSL", "INDPRO", "MPRIME", "GS3M"))
    for cutoff in (xnys_session_close(_month(value)) for value in (12, 24, 35)):
        actual = index.values_as_of(cutoff)
        for series_id in actual:
            assert actual[series_id] == vintage_values_as_of(
                records, series_id, cutoff
            )


def test_credit_spread_uses_latest_common_published_observation_month() -> None:
    prime = {date(2024, 1, 1): 8.5, date(2024, 2, 1): 8.5}
    treasury = {date(2024, 1, 1): 5.4}
    spread = _latest_common_spread(prime, treasury, date(2024, 2, 29))
    assert spread is not None
    assert spread[0] == date(2024, 1, 1)
    assert math.isclose(spread[1], 3.1)


def test_fold_standardization_uses_training_rows_only() -> None:
    rows, _ = build_cycle_features(
        instrument="SPY", daily_points=_points(), macro_vintages=_macro(152), config=CONFIG
    )
    training = rows[:-1]
    fitted = fit_fold_standardizer(training)
    changed_test = {**rows[-1], "normalizedFeatures": {key: 999 for key in rows[-1]["normalizedFeatures"]}}
    refitted = fit_fold_standardizer(training)
    assert fitted == refitted
    assert fitted.transform(changed_test) != fitted.transform(rows[-1])


def test_cash_accrual_cannot_see_later_revisions_or_same_day_releases() -> None:
    points = _points(2)
    first = normalize_fred_observation("DGS3MO", {
        "date": "2000-01-27", "realtime_start": "2000-01-28",
        "realtime_end": "2000-02-29", "value": "2",
    }, "2026-09-07T00:00:00+00:00")
    later = normalize_fred_observation("DGS3MO", {
        "date": "2000-01-27", "realtime_start": "2000-03-01",
        "realtime_end": "9999-12-31", "value": "9",
    }, "2026-09-07T00:00:00+00:00")
    same_day = normalize_fred_observation("DGS3MO", {
        "date": "2000-01-31", "realtime_start": "2000-01-31",
        "realtime_end": "9999-12-31", "value": "7",
    }, "2026-09-07T00:00:00+00:00")
    rates = observable_cash_rates(points, [later, same_day, first], "DGS3MO")
    assert rates[points[0].event_time] == 2
    assert rates[points[1].event_time] == 7
    expected = math.log(1 + 0.02 * 29 / 365)
    assert rolled_cash_log_return(points[0], points[1], points, rates) == pytest.approx(expected)
    assert observable_cash_rates(points, [later]) == {}
    with pytest.raises(ValueError, match="No publication-admissible cash rate"):
        rolled_cash_log_return(points[0], points[1], points, {})


def test_cash_missing_revision_does_not_resurrect_withdrawn_value() -> None:
    points = _points(2)
    records = [normalize_fred_observation("DGS3MO", {
        "date": "2000-01-01", "realtime_start": release,
        "realtime_end": "9999-12-31", "value": value,
    }, "2026-09-07T00:00:00+00:00") for release, value in (("2000-01-02", "2"), ("2000-02-01", "."))]
    rates = observable_cash_rates(points, records)
    assert rates == {points[0].event_time: 2.0}


def test_spread_lag_is_exactly_three_observation_months_and_requires_both_series() -> None:
    prime = {date(2020, month, 1): float(month) for month in range(1, 6)}
    treasury = {observation: 0.0 for observation in prime}
    latest = _latest_common_spread(prime, treasury, date(2020, 6, 30))
    assert latest == (date(2020, 5, 1), 5.0)
    assert _exact_lagged_spread(prime, treasury, latest, 3) == (date(2020, 2, 1), 2.0)
    del treasury[date(2020, 2, 1)]
    assert _exact_lagged_spread(prime, treasury, latest, 3) is None
    assert _exact_lagged_spread(prime, treasury, None, 3) is None


def test_state_rules_are_deterministic_and_precedence_ordered() -> None:
    rows = []
    for index, (valuation, stress, direction) in enumerate(
        ((0.0, 1.0, 0.0), (0.0, 0.9, 0.0), (0.0, 0.8, 0.0), (0.6, 0.7, 0.4))
    ):
        rows.append({
            "schemaVersion": "cycle1-feature-vector-v1", "instrument": "SPY",
            "snapshotDate": _month(index).isoformat(), "snapshotCutoff": xnys_session_close(_month(index)).isoformat(),
            "rawFeatures": {}, "normalizedFeatures": {},
            "dimensionScores": {"valuation": valuation, "stress": stress, "direction": direction},
            "cycleScore": (valuation + stress + direction) / 3,
            "evidenceTier": "RECONSTRUCTED_RESEARCH_ONLY", "componentEvidenceTiers": {}, "qualityFlags": [],
        })
    assigned = assign_cycle_states(rows, CONFIG)
    assert assigned[-1]["state"] == "EARLY_RECOVERY"
    assert assigned[-1]["stateFlags"]["stressDeclining"] is True
