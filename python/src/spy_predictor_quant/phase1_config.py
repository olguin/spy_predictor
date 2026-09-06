"""Validated configuration for the Phase 1 historical dataset and tournament."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from spy_predictor_quant.market_archive import content_hash


@dataclass(frozen=True)
class RollMapping:
    instrument: str
    start_date: date
    end_date: date
    ticker: str
    last_trade_date: date


@dataclass(frozen=True)
class Phase1Plan:
    raw: dict[str, Any]
    dataset: dict[str, Any]
    tournament: dict[str, Any]
    start_date: date
    end_date: date
    roll_mappings: dict[str, tuple[RollMapping, ...]]
    config_hash: str


def load_phase1_plan(path: Path) -> Phase1Plan:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "phase1-plan-v1":
        raise ValueError("Phase 1 config schemaVersion must be phase1-plan-v1")
    dataset = _mapping(payload, "dataset")
    tournament = _mapping(payload, "tournament")
    start = date.fromisoformat(_text(dataset, "startDate"))
    end = date.fromisoformat(_text(dataset, "endDate"))
    if start >= end:
        raise ValueError("Phase 1 dataset startDate must precede endDate")
    if _text(dataset, "barSize") != "1Min":
        raise ValueError("Phase 1 requires one-minute bars")
    raw_archive_id = _text(dataset, "rawArchiveId")
    if not raw_archive_id.startswith("phase1-plan-") or "/" in raw_archive_id:
        raise ValueError("dataset.rawArchiveId must be a safe phase1-plan identifier")

    alpaca = _mapping(dataset, "alpaca")
    if alpaca.get("symbols") != ["SPY", "QQQ"]:
        raise ValueError("Alpaca symbols must be exactly SPY and QQQ")
    if alpaca.get("feed") != "sip" or alpaca.get("adjustment") != "raw":
        raise ValueError("Phase 1 requires raw Alpaca SIP bars")
    massive = _mapping(dataset, "massive")
    if massive.get("products") != ["ES", "NQ"]:
        raise ValueError("Massive products must be exactly ES and NQ")
    if massive.get("resolution") != "1min":
        raise ValueError("Phase 1 requires one-minute Massive aggregates")

    policy = _mapping(dataset, "futuresRollPolicy")
    if policy.get("schemaVersion") != "explicit-futures-roll-v1":
        raise ValueError("Unsupported futures roll policy")
    raw_mappings = _mapping(policy, "mappings")
    mappings: dict[str, tuple[RollMapping, ...]] = {}
    for instrument in ("ES", "NQ"):
        values = raw_mappings.get(instrument)
        if not isinstance(values, list) or not values:
            raise ValueError(f"Missing explicit {instrument} roll mappings")
        parsed = tuple(
            RollMapping(
                instrument=instrument,
                start_date=date.fromisoformat(_text(item, "startDate")),
                end_date=date.fromisoformat(_text(item, "endDate")),
                ticker=_text(item, "ticker"),
                last_trade_date=date.fromisoformat(_text(item, "lastTradeDate")),
            )
            for item in values
            if isinstance(item, dict)
        )
        if len(parsed) != len(values):
            raise ValueError(f"Every {instrument} roll mapping must be an object")
        _validate_roll_sequence(instrument, parsed, start, end)
        mappings[instrument] = parsed

    horizons = tournament.get("horizons")
    expected_horizons = {
        "open-15m",
        "open-30m",
        "open-60m",
        "previous-close-next-open",
        "open-close",
        "close-next-close",
    }
    if not isinstance(horizons, list) or set(horizons) != expected_horizons:
        raise ValueError("Phase 1 tournament must contain all six target horizons")
    confirmation = _positive_int(tournament, "confirmationObservations")
    minimum_confirmation = _positive_int(
        tournament, "minimumConfirmationObservations"
    )
    if confirmation < minimum_confirmation:
        raise ValueError(
            "confirmationObservations must meet minimumConfirmationObservations"
        )
    _positive_int(tournament, "minimumTrainingObservations")
    _positive_int(tournament, "rollingWindow")
    _positive_number(tournament, "minimumCoveragePercent")
    promotion = _mapping(tournament, "promotion")
    if not promotion.get("eligibleModels"):
        raise ValueError("promotion.eligibleModels cannot be empty")
    _positive_number(promotion, "minimumBrierImprovement")
    _positive_number(promotion, "minimumIncrementalNetReturn")

    return Phase1Plan(
        raw=payload,
        dataset=dataset,
        tournament=tournament,
        start_date=start,
        end_date=end,
        roll_mappings=mappings,
        config_hash=content_hash(payload),
    )


def mapping_for_session(
    mappings: tuple[RollMapping, ...], session_date: date
) -> RollMapping | None:
    return next(
        (
            mapping
            for mapping in mappings
            if mapping.start_date <= session_date <= mapping.end_date
        ),
        None,
    )


def _validate_roll_sequence(
    instrument: str,
    mappings: tuple[RollMapping, ...],
    dataset_start: date,
    dataset_end: date,
) -> None:
    if mappings[0].start_date != dataset_start:
        raise ValueError(f"{instrument} roll mappings do not start at dataset start")
    if mappings[-1].end_date != dataset_end:
        raise ValueError(f"{instrument} roll mappings do not end at dataset end")
    seen: set[str] = set()
    for index, mapping in enumerate(mappings):
        if mapping.ticker in seen:
            raise ValueError(f"Duplicate {instrument} contract {mapping.ticker}")
        seen.add(mapping.ticker)
        if mapping.start_date > mapping.end_date:
            raise ValueError(f"Invalid mapping range for {mapping.ticker}")
        if mapping.end_date >= mapping.last_trade_date:
            raise ValueError(
                f"{mapping.ticker} mapping must end before its last trade date"
            )
        if index and mappings[index - 1].end_date + timedelta(days=1) != mapping.start_date:
            raise ValueError(f"{instrument} roll mappings must be calendar-contiguous")


def _mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Phase 1 field {key} must be an object")
    return value


def _text(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Phase 1 field {key} must be non-empty text")
    return value.strip()


def _positive_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"Phase 1 field {key} must be a positive integer")
    return value


def _positive_number(raw: dict[str, Any], key: str) -> float:
    value = raw.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"Phase 1 field {key} must be positive")
    return float(value)
