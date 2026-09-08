"""Frozen deterministic descriptive cycle-state assignment."""

from __future__ import annotations

from datetime import date
from typing import Any

from spy_predictor_quant.market_archive import content_hash


def assign_cycle_states(feature_rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = sorted(feature_rows, key=lambda row: row["snapshotDate"])
    thresholds = config["states"]["thresholds"]
    precedence = config["states"]["precedence"]
    expected = ["EUPHORIA", "EARLY_RECOVERY", "CRISIS", "CORRECTION", "GREED", "NORMAL"]
    if precedence != expected:
        raise ValueError("Cycle state precedence differs from preregistration")
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        valuation = float(row["dimensionScores"]["valuation"])
        stress = float(row["dimensionScores"]["stress"])
        direction = float(row["dimensionScores"]["direction"])
        old_stress = _lagged_dimension(rows, index, "stress", 3)
        stress_change = stress - old_stress if old_stress is not None else 0.0
        lookback = int(thresholds["formerlyExpensiveLookbackMonths"])
        start = _month_floor(date.fromisoformat(row["snapshotDate"]), lookback)
        formerly_expensive = any(
            date.fromisoformat(previous["snapshotDate"]) >= start
            and float(previous["dimensionScores"]["valuation"]) <= float(thresholds["expensiveValuationMaximum"])
            for previous in rows[: index + 1]
        )
        flags = {
            "cheap": valuation >= float(thresholds["cheapValuationMinimum"]),
            "expensive": valuation <= float(thresholds["expensiveValuationMaximum"]),
            "highStress": stress >= float(thresholds["highStressMinimum"]),
            "easyStress": stress <= float(thresholds["easyStressMaximum"]),
            "positiveDirection": direction >= float(thresholds["positiveDirectionMinimum"]),
            "weakDirection": direction <= float(thresholds["weakDirectionMaximum"]),
            "stressRising": stress_change >= float(thresholds["stressChangeMagnitude"]),
            "stressDeclining": stress_change <= -float(thresholds["stressChangeMagnitude"]),
            "formerlyExpensive": formerly_expensive,
        }
        conditions = {
            "EUPHORIA": flags["expensive"] and flags["easyStress"] and flags["positiveDirection"],
            "EARLY_RECOVERY": flags["cheap"] and flags["highStress"] and flags["stressDeclining"] and flags["positiveDirection"],
            "CRISIS": flags["cheap"] and flags["highStress"] and flags["weakDirection"],
            "CORRECTION": flags["formerlyExpensive"] and (flags["weakDirection"] or flags["stressRising"]),
            "GREED": flags["expensive"] and flags["positiveDirection"],
            "NORMAL": True,
        }
        state = next(name for name in precedence if conditions[name])
        core = {**{key: value for key, value in row.items() if key != "hash"}, "state": state, "stateFlags": flags, "stressScoreChange3m": stress_change}
        result.append({**core, "hash": content_hash(core)})
    return result


def _lagged_dimension(rows: list[dict[str, Any]], index: int, dimension: str, months: int) -> float | None:
    current = date.fromisoformat(rows[index]["snapshotDate"])
    target = _month_floor(current, months)
    matches = [row for row in rows[:index] if date.fromisoformat(row["snapshotDate"]).year == target.year and date.fromisoformat(row["snapshotDate"]).month == target.month]
    return float(matches[-1]["dimensionScores"][dimension]) if matches else None


def _month_floor(value: date, months_back: int) -> date:
    ordinal = value.year * 12 + value.month - 1 - months_back
    return date(ordinal // 12, ordinal % 12 + 1, 1)
