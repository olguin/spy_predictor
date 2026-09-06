"""Normalize and quality-check IBKR historical bar callbacks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from spy_predictor_quant.ibkr_history_config import HistorySettings
from spy_predictor_quant.market_archive import content_hash


PRICE_FIELDS = ("open", "high", "low", "close")


def normalize_historical_events(
    events: Iterable[dict[str, Any]],
    contracts: dict[str, dict[str, object]],
    settings: HistorySettings,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    by_key: dict[tuple[int, str], dict[str, object]] = {}
    duplicate_counts: dict[str, int] = {instrument: 0 for instrument in contracts}

    for event in events:
        if event.get("type") != "historicalBar":
            continue
        instrument = str(event["instrument"])
        contract = contracts[instrument]
        bar = event["bar"]
        if not isinstance(bar, dict):
            raise ValueError("Historical callback is missing its bar payload")
        event_time = _epoch_to_iso(bar.get("date"))
        received_at = str(event["receivedAt"])
        record_without_hash: dict[str, object] = {
            "schemaVersion": "market-bar-v1",
            "source": "ibkr-tws-api",
            "sourceTimestamp": event_time,
            "firstSeenAt": received_at,
            "effectiveTimestamp": event_time,
            "ingestionTimestamp": received_at,
            "version": "ibkr-historical-v1",
            "provenanceClass": "event-time-only",
            "instrument": instrument,
            "symbol": instrument,
            "conId": int(contract["conId"]),
            "localSymbol": str(contract["localSymbol"]),
            "eventTime": event_time,
            "open": _finite_float(bar.get("open"), "open"),
            "high": _finite_float(bar.get("high"), "high"),
            "low": _finite_float(bar.get("low"), "low"),
            "close": _finite_float(bar.get("close"), "close"),
            "volume": _finite_float(bar.get("volume"), "volume"),
            "weightedAveragePrice": _finite_float(
                bar.get("weightedAveragePrice"), "weightedAveragePrice"
            ),
            "tradeCount": int(bar.get("tradeCount", 0)),
            "barSize": settings.bar_size,
            "whatToShow": settings.what_to_show,
            "useRegularTradingHours": settings.use_regular_trading_hours,
        }
        if record_without_hash["high"] < record_without_hash["low"]:
            raise ValueError(f"Invalid high/low values for {instrument} {event_time}")
        record = {
            **record_without_hash,
            "hash": content_hash(record_without_hash),
        }
        key = (int(contract["conId"]), event_time)
        previous = by_key.get(key)
        if previous is not None:
            if _bar_values(previous) != _bar_values(record):
                raise ValueError(
                    f"Conflicting duplicate bars for {instrument} at {event_time}"
                )
            duplicate_counts[instrument] += 1
            if str(record["firstSeenAt"]) < str(previous["firstSeenAt"]):
                by_key[key] = record
            continue
        by_key[key] = record

    records = sorted(
        by_key.values(),
        key=lambda record: (str(record["instrument"]), str(record["eventTime"])),
    )
    quality: dict[str, dict[str, object]] = {}
    for instrument in contracts:
        instrument_records = [
            record for record in records if record["instrument"] == instrument
        ]
        quality[instrument] = summarize_bar_quality(
            instrument_records,
            duplicate_counts[instrument],
        )
    return records, quality


def summarize_bar_quality(
    records: list[dict[str, object]],
    exact_duplicate_count: int = 0,
) -> dict[str, object]:
    timestamps = [
        datetime.fromisoformat(str(record["eventTime"])) for record in records
    ]
    gap_candidates: list[dict[str, object]] = []
    for previous, current in zip(timestamps, timestamps[1:]):
        difference_minutes = int((current - previous).total_seconds() // 60)
        if 1 < difference_minutes <= 180:
            gap_candidates.append(
                {
                    "after": previous.isoformat(),
                    "before": current.isoformat(),
                    "missingOneMinuteIntervals": difference_minutes - 1,
                }
            )
    return {
        "bars": len(records),
        "firstTimestamp": timestamps[0].isoformat() if timestamps else None,
        "lastTimestamp": timestamps[-1].isoformat() if timestamps else None,
        "exactDuplicateBarsRemoved": exact_duplicate_count,
        "intradayGapCandidateCount": len(gap_candidates),
        "intradayGapCandidates": gap_candidates[:100],
    }


def _epoch_to_iso(value: object) -> str:
    try:
        timestamp = int(str(value))
    except ValueError as error:
        raise ValueError(f"IBKR bar date is not a UTC epoch value: {value}") from error
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _finite_float(value: object, name: str) -> float:
    try:
        result = float(str(value))
    except ValueError as error:
        raise ValueError(f"IBKR bar {name} is not numeric: {value}") from error
    if result != result or result in {float("inf"), float("-inf")}:
        raise ValueError(f"IBKR bar {name} is not finite: {value}")
    return result


def _bar_values(record: dict[str, object]) -> tuple[object, ...]:
    return tuple(record[field] for field in (*PRICE_FIELDS, "volume", "tradeCount"))
