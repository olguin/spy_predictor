"""Deterministically aggregate IBKR five-second callbacks into one-minute bars."""

from __future__ import annotations

import threading
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

from spy_predictor_quant.market_archive import LiveSessionArchiveWriter, content_hash


class LiveCaptureState:
    """Deduplicate live callbacks across reconnects before raw persistence."""

    def __init__(self, raw_writer: LiveSessionArchiveWriter) -> None:
        self.raw_writer = raw_writer
        self.stop_requested = threading.Event()
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []
        self._seen: dict[tuple[int, int], tuple[object, ...]] = {}
        self.duplicates: Counter[str] = Counter()
        self.callback_errors: list[str] = []
        self.api_events: list[dict[str, object]] = []

    @property
    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)

    def record_bar(self, event: dict[str, Any]) -> None:
        bar = event["bar"]
        key = (int(event["conId"]), int(bar["time"]))
        values = (
            bar["open"],
            bar["high"],
            bar["low"],
            bar["close"],
            bar["volume"],
            bar["weightedAveragePrice"],
            bar["tradeCount"],
        )
        with self._lock:
            previous = self._seen.get(key)
            if previous is not None:
                if previous != values:
                    message = (
                        f"Conflicting live duplicate for {event['instrument']} "
                        f"at {bar['time']}"
                    )
                    self.callback_errors.append(message)
                    self.stop_requested.set()
                else:
                    self.duplicates[str(event["instrument"])] += 1
                return
            self._seen[key] = values
            self._events.append(event)
        self.raw_writer.write(event)

    def record_api_event(self, event: dict[str, object]) -> None:
        with self._lock:
            self.api_events.append(event)
        self.raw_writer.write(event)


def aggregate_realtime_events(
    events: Iterable[dict[str, Any]],
    contracts: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    buckets: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for event in events:
        if event.get("type") != "realtimeBar":
            continue
        instrument = str(event["instrument"])
        epoch = int(event["bar"]["time"])
        minute_epoch = epoch - (epoch % 60)
        buckets.setdefault((instrument, minute_epoch), []).append(event)

    records: list[dict[str, object]] = []
    for (instrument, minute_epoch), components in sorted(buckets.items()):
        ordered = sorted(
            components,
            key=lambda event: (
                int(event["bar"]["time"]),
                str(event["receivedAt"]),
            ),
        )
        unique_components: dict[int, dict[str, Any]] = {}
        for event in ordered:
            component_time = int(event["bar"]["time"])
            previous = unique_components.get(component_time)
            if previous is not None and previous["bar"] != event["bar"]:
                raise ValueError(
                    f"Conflicting five-second components for {instrument} "
                    f"at {component_time}"
                )
            unique_components.setdefault(component_time, event)
        ordered = [unique_components[key] for key in sorted(unique_components)]
        unique_times = set(unique_components)
        expected_times = set(range(minute_epoch, minute_epoch + 60, 5))
        contract = contracts[instrument]
        volume = sum(float(event["bar"]["volume"]) for event in ordered)
        weighted_numerator = sum(
            float(event["bar"]["weightedAveragePrice"])
            * float(event["bar"]["volume"])
            for event in ordered
        )
        event_time = datetime.fromtimestamp(minute_epoch, timezone.utc).isoformat()
        first_component_seen_at = min(
            str(event["receivedAt"]) for event in ordered
        )
        last_component_seen_at = max(str(event["receivedAt"]) for event in ordered)
        without_hash: dict[str, object] = {
            "schemaVersion": "market-bar-v1",
            "source": "ibkr-tws-api",
            "sourceTimestamp": event_time,
            "firstSeenAt": last_component_seen_at,
            "effectiveTimestamp": event_time,
            "ingestionTimestamp": last_component_seen_at,
            "version": "ibkr-live-aggregate-v1",
            "provenanceClass": "locally-first-seen",
            "instrument": instrument,
            "symbol": instrument,
            "conId": int(contract["conId"]),
            "localSymbol": str(contract["localSymbol"]),
            "eventTime": event_time,
            "open": float(ordered[0]["bar"]["open"]),
            "high": max(float(event["bar"]["high"]) for event in ordered),
            "low": min(float(event["bar"]["low"]) for event in ordered),
            "close": float(ordered[-1]["bar"]["close"]),
            "volume": volume,
            "weightedAveragePrice": (
                weighted_numerator / volume
                if volume
                else float(ordered[-1]["bar"]["weightedAveragePrice"])
            ),
            "tradeCount": sum(int(event["bar"]["tradeCount"]) for event in ordered),
            "barSize": "1 min",
            "componentBarSizeSeconds": 5,
            "componentBars": len(unique_times),
            "complete": unique_times == expected_times,
            "firstComponentSeenAt": first_component_seen_at,
            "lastComponentSeenAt": last_component_seen_at,
            "whatToShow": "TRADES",
        }
        records.append({**without_hash, "hash": content_hash(without_hash)})

    quality: dict[str, dict[str, object]] = {}
    for instrument in contracts:
        instrument_components = [
            event
            for events_in_bucket in buckets.values()
            for event in events_in_bucket
            if event["instrument"] == instrument
        ]
        instrument_records = [
            record for record in records if record["instrument"] == instrument
        ]
        quality[instrument] = {
            "fiveSecondBars": len(instrument_components),
            "oneMinuteBars": len(instrument_records),
            "completeOneMinuteBars": sum(
                1 for record in instrument_records if record["complete"]
            ),
            "partialOneMinuteBars": sum(
                1 for record in instrument_records if not record["complete"]
            ),
            "firstTimestamp": (
                instrument_records[0]["eventTime"] if instrument_records else None
            ),
            "lastTimestamp": (
                instrument_records[-1]["eventTime"] if instrument_records else None
            ),
        }
    return records, quality
