"""Frozen total-return, cash, inflation and drawdown targets for Cycle 1."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable
from spy_predictor_quant.cycle1_calendar import (
    xnys_month_end,
    xnys_next_session_open,
)
from spy_predictor_quant.market_archive import content_hash


@dataclass(frozen=True)
class TotalReturnPoint:
    session_date: date
    event_time: datetime
    close: float
    total_return_index: float


def construct_total_return_index(
    daily_rows: list[dict[str, Any]], action_rows: list[dict[str, Any]]
) -> list[TotalReturnPoint]:
    rows = sorted(daily_rows, key=lambda row: row["sessionDate"])
    if not rows:
        raise ValueError("Cannot construct a total-return index without daily prices")
    if len({row["sessionDate"] for row in rows}) != len(rows):
        raise ValueError("Daily prices contain duplicate sessions")
    actions: dict[date, list[dict[str, Any]]] = {}
    for action in action_rows:
        actions.setdefault(date.fromisoformat(action["effectiveDate"]), []).append(action)
    result: list[TotalReturnPoint] = []
    index_level = 1.0
    previous_close: float | None = None
    for row in rows:
        session_date = date.fromisoformat(row["sessionDate"])
        close = float(row["close"])
        if not math.isfinite(close) or close <= 0:
            raise ValueError(f"Invalid close for {session_date}")
        if previous_close is not None:
            split_factor = 1.0
            cash_distribution = 0.0
            for action in actions.get(session_date, []):
                kind = str(action["actionType"]).lower()
                raw = action["raw"]
                if "split" in kind or kind == "stock_dividend":
                    split_factor *= _split_factor(raw, kind)
                if kind in {"cash_dividend", "capital_gains_distribution"}:
                    cash_distribution += _cash_amount(raw)
            growth = (close * split_factor + cash_distribution) / previous_close
            if not math.isfinite(growth) or growth <= 0:
                raise ValueError(f"Invalid total-return growth on {session_date}")
            index_level *= growth
        event_time = datetime.fromisoformat(str(row["eventTime"]))
        result.append(TotalReturnPoint(session_date, event_time, close, index_level))
        previous_close = close
    return result


def month_end_points(points: Iterable[TotalReturnPoint]) -> list[TotalReturnPoint]:
    selected: dict[tuple[int, int], TotalReturnPoint] = {}
    for point in sorted(points, key=lambda value: value.session_date):
        selected[(point.session_date.year, point.session_date.month)] = point
    if not selected:
        return []
    latest_session = max(point.session_date for point in selected.values())
    output: list[TotalReturnPoint] = []
    for year, month in sorted(selected):
        expected = xnys_month_end(year, month)
        if expected > latest_session:
            continue
        point = selected[(year, month)]
        if point.session_date != expected:
            raise ValueError(
                f"Missing final scheduled XNYS session {expected} for {year:04d}-{month:02d}"
            )
        output.append(point)
    return output


def build_cycle_targets(
    *,
    instrument: str,
    daily_points: list[TotalReturnPoint],
    macro_vintages: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    monthly = month_end_points(daily_points)
    by_month = {(point.session_date.year, point.session_date.month): point for point in monthly}
    cash_series = str(config["targets"]["primary"]["cashReturn"]["seriesId"])
    rates = observable_cash_rates(monthly, macro_vintages, cash_series)
    cpi = _latest_pinned_series(macro_vintages, "CPIAUCSL")
    cpi_release = _first_release_by_observation(macro_vintages, "CPIAUCSL")
    primary_months = int(config["targets"]["primary"]["horizonMonths"])
    diagnostic_months = int(config["targets"]["diagnostic"]["horizonMonths"])
    drawdown_threshold = float(config["targets"]["secondary"]["eventThreshold"])
    targets: list[dict[str, Any]] = []
    for start in monthly:
        end = by_month.get(_add_months(start.session_date, primary_months))
        if end is None:
            continue
        start_cpi = _month_value(cpi, start.session_date)
        end_cpi = _month_value(cpi, end.session_date)
        if start_cpi is None or end_cpi is None or start_cpi <= 0 or end_cpi <= 0:
            continue
        equity_nominal = math.log(end.total_return_index / start.total_return_index)
        inflation = math.log(end_cpi / start_cpi)
        cash_nominal = rolled_cash_log_return(start, end, monthly, rates)
        path = [
            point for point in daily_points
            if start.session_date <= point.session_date <= end.session_date
        ]
        maximum_drawdown = max_drawdown(path)
        diagnostic_end = by_month.get(_add_months(start.session_date, diagnostic_months))
        diagnostic_excess: float | None = None
        if diagnostic_end is not None:
            diagnostic_cash = rolled_cash_log_return(start, diagnostic_end, monthly, rates)
            diagnostic_excess = math.log(
                diagnostic_end.total_return_index / start.total_return_index
            ) - diagnostic_cash
        cpi_key = (end.session_date.year, end.session_date.month)
        available_at = max(
            end.event_time,
            cpi_release.get(cpi_key, end.event_time),
        )
        _, next_session_open = xnys_next_session_open(start.session_date)
        core: dict[str, Any] = {
            "schemaVersion": "cycle1-target-v1",
            "instrument": instrument,
            "snapshotDate": start.session_date.isoformat(),
            "snapshotCutoff": start.event_time.isoformat(),
            "earliestPolicyExecution": next_session_open.isoformat(),
            "targetEndDate": end.session_date.isoformat(),
            "labelAvailableAt": available_at.isoformat(),
            "nominalEquityLogReturn12m": equity_nominal,
            "inflationLogChange12m": inflation,
            "realEquityLogReturn12m": equity_nominal - inflation,
            "nominalCashLogReturn12m": cash_nominal,
            "realCashLogReturn12m": cash_nominal - inflation,
            "realExcessLogReturn12m": equity_nominal - cash_nominal,
            "maximumDrawdown12m": maximum_drawdown,
            "drawdownEvent12m": maximum_drawdown <= drawdown_threshold,
            "realExcessLogReturn24mDiagnostic": diagnostic_excess,
            "diagnosticPromotionEligible": False,
        }
        targets.append({**core, "hash": content_hash(core)})
    return targets


def eligible_training_targets(
    targets: list[dict[str, Any]], forecast_cutoff: datetime
) -> list[dict[str, Any]]:
    return [
        target for target in targets
        if datetime.fromisoformat(target["labelAvailableAt"]) < forecast_cutoff
        and datetime.fromisoformat(target["targetEndDate"] + "T23:59:59+00:00")
        < forecast_cutoff
    ]


def rolled_cash_log_return(
    start: TotalReturnPoint,
    end: TotalReturnPoint,
    monthly: list[TotalReturnPoint],
    rates_by_cutoff: dict[datetime, float],
) -> float:
    boundaries = [point for point in monthly if start.session_date <= point.session_date <= end.session_date]
    if not boundaries or boundaries[0].session_date != start.session_date or boundaries[-1].session_date != end.session_date:
        raise ValueError("Cash target boundaries are incomplete")
    total = 0.0
    for left, right in zip(boundaries, boundaries[1:], strict=False):
        if left.event_time not in rates_by_cutoff:
            raise ValueError(
                f"No publication-admissible cash rate at {left.event_time.isoformat()}; "
                "observation history is not publication history. Source qualification is required."
            )
        annual_percent = rates_by_cutoff[left.event_time]
        days = (right.session_date - left.session_date).days
        accrual = 1 + annual_percent / 100 * days / 365
        if accrual <= 0:
            raise ValueError("Cash accrual is nonpositive")
        total += math.log(accrual)
    return total


def observable_cash_rates(
    monthly: list[TotalReturnPoint], records: list[dict[str, Any]],
    series_id: str = "DGS3MO",
) -> dict[datetime, float]:
    """Freeze each holding-period rate using only vintages published by its start.

    Missing publication coverage stays absent. A later revision can change a
    later holding period, but never an already fixed cash accrual. Missing-value
    revisions replace older values instead of resurrecting them.
    """
    events = sorted(
        (record for record in records if record["seriesId"] == series_id),
        key=lambda record: (datetime.fromisoformat(record["availableAt"]), record["realtimeStart"]),
    )
    selected: dict[date, dict[str, Any]] = {}
    position = 0
    output: dict[datetime, float] = {}
    for point in sorted(monthly, key=lambda item: item.event_time):
        while position < len(events) and datetime.fromisoformat(events[position]["availableAt"]) <= point.event_time:
            record = events[position]
            observation = date.fromisoformat(record["observationDate"])
            previous = selected.get(observation)
            if previous is None or record["realtimeStart"] >= previous["realtimeStart"]:
                selected[observation] = record
            position += 1
        available = [
            observation for observation, record in selected.items()
            if observation <= point.session_date and not record["missing"]
        ]
        if available:
            output[point.event_time] = float(selected[max(available)]["value"])
    return output


def max_drawdown(path: list[TotalReturnPoint]) -> float:
    if not path:
        raise ValueError("Drawdown path cannot be empty")
    peak = path[0].total_return_index
    worst = 0.0
    for point in path:
        peak = max(peak, point.total_return_index)
        worst = min(worst, point.total_return_index / peak - 1)
    return worst


def _latest_pinned_series(records: list[dict[str, Any]], series_id: str) -> dict[date, float]:
    selected: dict[date, tuple[str, float]] = {}
    for record in records:
        if record["seriesId"] != series_id or record["missing"]:
            continue
        observation = date.fromisoformat(record["observationDate"])
        candidate = (record["realtimeStart"], float(record["value"]))
        if observation not in selected or candidate[0] > selected[observation][0]:
            selected[observation] = candidate
    return {key: value[1] for key, value in selected.items()}


def _first_release_by_observation(records: list[dict[str, Any]], series_id: str) -> dict[tuple[int, int], datetime]:
    selected: dict[tuple[int, int], datetime] = {}
    for record in records:
        if record["seriesId"] != series_id or record["missing"]:
            continue
        observation = date.fromisoformat(record["observationDate"])
        key = (observation.year, observation.month)
        available = datetime.fromisoformat(record["availableAt"])
        if key not in selected or available < selected[key]:
            selected[key] = available
    return selected


def _month_value(values: dict[date, float], point: date) -> float | None:
    exact = [value for key, value in values.items() if key.year == point.year and key.month == point.month]
    return exact[-1] if exact else None


def _add_months(value: date, months: int) -> tuple[int, int]:
    ordinal = value.year * 12 + value.month - 1 + months
    return ordinal // 12, ordinal % 12 + 1


def _cash_amount(raw: dict[str, Any]) -> float:
    for key in ("cash", "cash_amount", "amount", "rate"):
        value = raw.get(key)
        if isinstance(value, (int, float, str)) and str(value).strip():
            amount = float(value)
            if amount < 0:
                raise ValueError("Cash distribution cannot be negative")
            return amount
    raise ValueError("Cash distribution lacks a numeric amount")


def _split_factor(raw: dict[str, Any], kind: str) -> float:
    if kind == "stock_dividend":
        for key in ("rate", "shares", "stock_rate"):
            if key in raw:
                return 1 + float(raw[key])
    pairs = (("new_rate", "old_rate"), ("split_to", "split_from"), ("to", "from"))
    for numerator, denominator in pairs:
        if numerator in raw and denominator in raw:
            factor = float(raw[numerator]) / float(raw[denominator])
            if factor > 0:
                return factor
    ratio = raw.get("ratio")
    if ratio is not None and float(ratio) > 0:
        return float(ratio)
    raise ValueError("Split or stock dividend lacks a usable ratio")
