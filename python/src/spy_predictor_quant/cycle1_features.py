"""Trailing-only point-in-time features for CYCLE-ASYMMETRY-001."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from statistics import median
from typing import Any

import numpy as np

from spy_predictor_quant.cycle1_targets import TotalReturnPoint, month_end_points
from spy_predictor_quant.market_archive import content_hash


FEATURE_IDS = (
    "real-price-trend-deviation",
    "bank-prime-minus-treasury-credit-spread",
    "realized-volatility-3m",
    "drawdown-from-trailing-high-12m",
    "momentum-6m",
    "momentum-12m",
    "price-versus-moving-average-10m",
    "bank-prime-minus-treasury-credit-spread-change-3m",
    "industrial-production-growth-6m",
)


@dataclass(frozen=True)
class FoldStandardizer:
    feature_ids: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]

    def transform(self, row: dict[str, Any]) -> tuple[float, ...]:
        return tuple(
            (float(row["normalizedFeatures"][feature]) - mean) / scale
            for feature, mean, scale in zip(
                self.feature_ids, self.means, self.scales, strict=True
            )
        )


def fit_fold_standardizer(
    training_rows: list[dict[str, Any]], feature_ids: tuple[str, ...] = FEATURE_IDS
) -> FoldStandardizer:
    if not training_rows:
        raise ValueError("Fold preprocessing requires nonempty training rows")
    matrix = np.asarray(
        [[float(row["normalizedFeatures"][feature]) for feature in feature_ids] for row in training_rows],
        dtype=float,
    )
    means = np.mean(matrix, axis=0)
    scales = np.std(matrix, axis=0)
    scales = np.where(scales > 1e-12, scales, 1.0)
    return FoldStandardizer(feature_ids, tuple(float(value) for value in means), tuple(float(value) for value in scales))


def build_cycle_features(
    *,
    instrument: str,
    daily_points: list[TotalReturnPoint],
    macro_vintages: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    monthly = month_end_points(daily_points)
    vintage_index = _VintageIndex(
        macro_vintages, ("CPIAUCSL", "INDPRO", "MPRIME", "GS3M")
    )
    raw_rows: list[dict[str, Any]] = []
    unavailable: list[dict[str, str]] = []
    for point in monthly:
        macro_as_of = vintage_index.values_as_of(point.event_time)
        raw, missing = _raw_features(
            point, daily_points, monthly, macro_as_of, config
        )
        if missing:
            unavailable.append({"snapshotDate": point.session_date.isoformat(), "reason": ",".join(sorted(missing))})
            continue
        raw_rows.append({"point": point, "raw": raw})

    minimum_scale = int(config["features"]["normalization"]["percentileMinimumHistoryMonths"])
    history: dict[str, list[float]] = {feature: [] for feature in FEATURE_IDS}
    output: list[dict[str, Any]] = []
    signs = _economic_signs(config)
    dimension_features = {
        "valuation": ("real-price-trend-deviation",),
        "stress": (
            "bank-prime-minus-treasury-credit-spread", "realized-volatility-3m",
            "drawdown-from-trailing-high-12m",
        ),
        "direction": (
            "momentum-6m", "momentum-12m", "price-versus-moving-average-10m",
            "bank-prime-minus-treasury-credit-spread-change-3m",
            "industrial-production-growth-6m",
        ),
    }
    for item in raw_rows:
        raw = item["raw"]
        for feature in FEATURE_IDS:
            history[feature].append(float(raw[feature]))
        if any(len(history[feature]) < minimum_scale for feature in FEATURE_IDS):
            unavailable.append({"snapshotDate": item["point"].session_date.isoformat(), "reason": "normalization-warmup"})
            continue
        normalized = {
            feature: signs[feature] * expanding_midrank(raw[feature], history[feature])
            for feature in FEATURE_IDS
        }
        dimensions = {
            dimension: sum(normalized[feature] for feature in features) / len(features)
            for dimension, features in dimension_features.items()
        }
        cycle_score = sum(dimensions.values()) / 3
        point = item["point"]
        core: dict[str, Any] = {
            "schemaVersion": "cycle1-feature-vector-v1",
            "instrument": instrument,
            "snapshotDate": point.session_date.isoformat(),
            "snapshotCutoff": point.event_time.isoformat(),
            "rawFeatures": raw,
            "normalizedFeatures": normalized,
            "dimensionScores": dimensions,
            "cycleScore": cycle_score,
            "evidenceTier": "RECONSTRUCTED_RESEARCH_ONLY",
            "componentEvidenceTiers": {
                "market": "RECONSTRUCTED_RESEARCH_ONLY",
                "macro": "POINT_IN_TIME_ADMISSIBLE",
            },
            "qualityFlags": [],
        }
        output.append({**core, "hash": content_hash(core)})
    warmup_months = int(config["features"]["minimumRawHistoryMonths"]) + minimum_scale - 1
    eligible_cutoffs = max(0, len(monthly) - warmup_months + 1)
    return output, {
        "monthlyCutoffs": len(monthly),
        "warmupMonths": warmup_months,
        "eligibleMonthlyCutoffs": eligible_cutoffs,
        "featureVectors": len(output),
        "coveragePercent": len(output) / eligible_cutoffs * 100 if eligible_cutoffs else 0.0,
        "unavailable": unavailable,
    }


def expanding_midrank(current: float, history: list[float]) -> float:
    if not history:
        raise ValueError("Expanding percentile history cannot be empty")
    less = sum(value < current for value in history)
    equal = sum(value == current for value in history)
    percentile = (less + 0.5 * equal) / len(history)
    return min(1.0, max(-1.0, 2 * percentile - 1))


def vintage_values_as_of(
    records: list[dict[str, Any]], series_id: str, cutoff: datetime
) -> dict[date, float]:
    selected: dict[date, tuple[str, float]] = {}
    for record in records:
        if record["seriesId"] != series_id or record["missing"]:
            continue
        if datetime.fromisoformat(record["availableAt"]) > cutoff:
            continue
        observation = date.fromisoformat(record["observationDate"])
        candidate = (str(record["realtimeStart"]), float(record["value"]))
        if observation not in selected or candidate[0] > selected[observation][0]:
            selected[observation] = candidate
    return {key: value[1] for key, value in selected.items()}


class _VintageIndex:
    """Advance point-in-time macro state once for chronological cutoffs."""

    def __init__(
        self, records: list[dict[str, Any]], series_ids: tuple[str, ...]
    ) -> None:
        self._events: dict[str, list[tuple[datetime, dict[str, Any]]]] = {}
        self._positions: dict[str, int] = {}
        self._selected: dict[str, dict[date, tuple[str, float]]] = {}
        for series_id in series_ids:
            events = [
                (datetime.fromisoformat(str(record["availableAt"])), record)
                for record in records
                if record["seriesId"] == series_id and not record["missing"]
            ]
            events.sort(key=lambda item: (item[0], str(item[1]["realtimeStart"])))
            self._events[series_id] = events
            self._positions[series_id] = 0
            self._selected[series_id] = {}
        self._last_cutoff: datetime | None = None

    def values_as_of(self, cutoff: datetime) -> dict[str, dict[date, float]]:
        if self._last_cutoff is not None and cutoff <= self._last_cutoff:
            raise ValueError("Vintage cutoffs must be strictly chronological")
        self._last_cutoff = cutoff
        output: dict[str, dict[date, float]] = {}
        for series_id, events in self._events.items():
            position = self._positions[series_id]
            selected = self._selected[series_id]
            while position < len(events) and events[position][0] <= cutoff:
                record = events[position][1]
                observation = date.fromisoformat(str(record["observationDate"]))
                candidate = (str(record["realtimeStart"]), float(record["value"]))
                if observation not in selected or candidate[0] > selected[observation][0]:
                    selected[observation] = candidate
                position += 1
            self._positions[series_id] = position
            output[series_id] = {
                observation: candidate[1]
                for observation, candidate in selected.items()
            }
        return output


def exact_theil_sen_deviation(values: list[float], consistency: float, floor: float) -> float:
    if len(values) < 2 or any(value <= 0 or not math.isfinite(value) for value in values):
        raise ValueError("Trend requires at least two positive finite levels")
    y = [math.log(value) for value in values]
    slopes = [(y[right] - y[left]) / (right - left) for left in range(len(y)) for right in range(left + 1, len(y))]
    slope = median(slopes)
    intercept = median([value - slope * index for index, value in enumerate(y)])
    residuals = [value - (intercept + slope * index) for index, value in enumerate(y)]
    center = median(residuals)
    scale = max(floor, consistency * median([abs(value - center) for value in residuals]))
    return (residuals[-1] - center) / scale


def _raw_features(point: TotalReturnPoint, daily: list[TotalReturnPoint], monthly: list[TotalReturnPoint], macro: dict[str, dict[date, float]], config: dict[str, Any]) -> tuple[dict[str, float], set[str]]:
    cutoff = point.event_time
    missing: set[str] = set()
    cpi = macro["CPIAUCSL"]
    indpro = macro["INDPRO"]
    prime = macro["MPRIME"]
    treasury = macro["GS3M"]
    monthly_before = [value for value in monthly if value.session_date <= point.session_date]
    trend_window = int(config["features"]["dimensions"]["valuation"]["features"][0]["windowMonths"])
    real_levels: list[float] = []
    for value in monthly_before[-trend_window:]:
        deflator = _same_month_value(cpi, value.session_date)
        if deflator is not None and deflator > 0:
            real_levels.append(value.total_return_index / deflator)
    raw: dict[str, float] = {}
    if len(real_levels) == trend_window:
        feature = config["features"]["dimensions"]["valuation"]["features"][0]
        raw["real-price-trend-deviation"] = exact_theil_sen_deviation(real_levels, float(feature["madConsistencyFactor"]), float(feature["madFloor"]))
    else:
        missing.add("real-price-trend-deviation")

    latest_spread = _latest_common_spread(prime, treasury, point.session_date)
    if latest_spread is None:
        missing.add("bank-prime-minus-treasury-credit-spread")
    else:
        raw["bank-prime-minus-treasury-credit-spread"] = latest_spread[1]
    old_spread = _exact_lagged_spread(prime, treasury, latest_spread, 3)
    if latest_spread is None or old_spread is None:
        missing.add("bank-prime-minus-treasury-credit-spread-change-3m")
    else:
        raw["bank-prime-minus-treasury-credit-spread-change-3m"] = (
            latest_spread[1] - old_spread[1]
        )

    daily_before = [value for value in daily if value.session_date <= point.session_date]
    vol_start = _month_floor(point.session_date, 3)
    vol_points = [value for value in daily_before if value.session_date > vol_start]
    if len(vol_points) < 2:
        missing.add("realized-volatility-3m")
    else:
        returns = [math.log(right.total_return_index / left.total_return_index) for left, right in zip(vol_points, vol_points[1:], strict=False)]
        raw["realized-volatility-3m"] = float(np.std(returns, ddof=1) * math.sqrt(252)) if len(returns) > 1 else abs(returns[0]) * math.sqrt(252)
    drawdown_points = [value for value in daily_before if value.session_date > _month_floor(point.session_date, 12)]
    if not drawdown_points:
        missing.add("drawdown-from-trailing-high-12m")
    else:
        peak = max(value.total_return_index for value in drawdown_points)
        raw["drawdown-from-trailing-high-12m"] = 1 - point.total_return_index / peak

    by_month = {(value.session_date.year, value.session_date.month): value for value in monthly_before}
    for months, feature_id in ((6, "momentum-6m"), (12, "momentum-12m")):
        old = by_month.get(_add_months(point.session_date, -months))
        if old is None:
            missing.add(feature_id)
        else:
            raw[feature_id] = math.log(point.total_return_index / old.total_return_index)
    real_ma: list[float] = []
    for value in monthly_before[-10:]:
        deflator = _same_month_value(cpi, value.session_date)
        if deflator is not None and deflator > 0:
            real_ma.append(value.total_return_index / deflator)
    current_cpi = _same_month_value(cpi, point.session_date)
    if len(real_ma) != 10 or current_cpi is None:
        missing.add("price-versus-moving-average-10m")
    else:
        current_real = point.total_return_index / current_cpi
        raw["price-versus-moving-average-10m"] = math.log(current_real / (sum(real_ma) / len(real_ma)))
    latest_ip = _latest(indpro, point.session_date)
    old_ip = _latest(indpro, _month_floor(latest_ip[0], 6)) if latest_ip else None
    if latest_ip is None or old_ip is None or latest_ip[1] <= 0 or old_ip[1] <= 0:
        missing.add("industrial-production-growth-6m")
    else:
        raw["industrial-production-growth-6m"] = math.log(latest_ip[1] / old_ip[1])
    return raw, missing


def _economic_signs(config: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for dimension in config["features"]["dimensions"].values():
        for feature in dimension["features"]:
            result[feature["id"]] = int(feature["economicSign"])
    if set(result) != set(FEATURE_IDS):
        raise ValueError("Configured feature signs do not match the frozen feature set")
    return result


def _latest(values: dict[date, float], cutoff: date) -> tuple[date, float] | None:
    eligible = [key for key in values if key <= cutoff]
    if not eligible:
        return None
    selected = max(eligible)
    return selected, values[selected]


def _latest_common_spread(
    numerator: dict[date, float], denominator: dict[date, float], cutoff: date
) -> tuple[date, float] | None:
    common = [key for key in numerator.keys() & denominator.keys() if key <= cutoff]
    if not common:
        return None
    selected = max(common)
    return selected, numerator[selected] - denominator[selected]


def _exact_lagged_spread(
    numerator: dict[date, float], denominator: dict[date, float],
    latest: tuple[date, float] | None, months: int,
) -> tuple[date, float] | None:
    """Lag the common observation month, never the later snapshot month."""
    if latest is None:
        return None
    observation = _month_floor(latest[0], months)
    if observation not in numerator or observation not in denominator:
        return None
    return observation, numerator[observation] - denominator[observation]


def _same_month_value(values: dict[date, float], point: date) -> float | None:
    matching = [value for key, value in values.items() if key.year == point.year and key.month == point.month]
    if matching:
        return matching[-1]
    earlier = [key for key in values if key <= point]
    return values[max(earlier)] if earlier else None


def _month_floor(value: date, months_back: int) -> date:
    year, month = _add_months(value, -months_back)
    return date(year, month, 1)


def _add_months(value: date, months: int) -> tuple[int, int]:
    ordinal = value.year * 12 + value.month - 1 + months
    return ordinal // 12, ordinal % 12 + 1
