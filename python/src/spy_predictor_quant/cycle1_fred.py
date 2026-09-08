"""Immutable FRED/ALFRED acquisition and vintage normalization for Cycle 1."""

from __future__ import annotations

import math
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from spy_predictor_quant.historical_http import ArchivedPage, RequestLimiter, capture_pages
from spy_predictor_quant.market_archive import content_hash


SERIES_IDS = ("DGS3MO", "CPIAUCSL", "INDPRO", "MPRIME", "GS3M")
SUPPORTED_SERIES_IDS = (*SERIES_IDS, "NFCI")
VINTAGE_BATCH_SIZES = {
    "DGS3MO": 100,
    "CPIAUCSL": 100,
    "INDPRO": 10,
    "MPRIME": 100,
    "GS3M": 100,
    "NFCI": 10,
}


def capture_fred_series(
    *,
    series_id: str,
    as_of: date,
    raw_directory: Path,
    api_key: str,
    offline: bool,
    limiter: RequestLimiter | None = None,
) -> tuple[list[ArchivedPage], list[dict[str, Any]]]:
    if series_id not in SUPPORTED_SERIES_IDS:
        raise ValueError(f"Unpreregistered FRED series {series_id}")
    if not offline and not api_key:
        raise ValueError("FRED_API_KEY is required for vintage acquisition")
    page_limit = 100_000
    vintage_parameters = {
        "series_id": series_id,
        "file_type": "json",
        "sort_order": "asc",
        "realtime_start": "1776-07-04",
        "realtime_end": as_of.isoformat(),
        "limit": "10000",
        "offset": "0",
    }
    vintage_url = (
        "https://api.stlouisfed.org/fred/series/vintagedates?"
        + urllib.parse.urlencode(vintage_parameters)
    )
    pages, raw_vintage_dates = capture_pages(
        provider=f"fred-alfred-{series_id}-vintage-dates",
        initial_url=vintage_url,
        raw_directory=raw_directory / "vintage-dates",
        headers={"Accept": "application/json"},
        limiter=limiter or RequestLimiter(60),
        next_url=_next_page,
        extract_records=_vintage_dates,
        allow_network=not offline,
        secret_query={"api_key": api_key} if not offline else None,
    )
    vintage_dates = [str(item["vintage_date"]) for item in raw_vintage_dates]
    _validate_vintage_dates(vintage_dates, as_of)

    change_records: list[dict[str, Any]] = []
    for batch_index, batch in enumerate(
        _batches(vintage_dates, VINTAGE_BATCH_SIZES[series_id])
    ):
        parameters = {
            "series_id": series_id,
            "file_type": "json",
            "units": "lin",
            "sort_order": "asc",
            "output_type": "3",
            "vintage_dates": ",".join(batch),
            "observation_end": as_of.isoformat(),
            "limit": str(page_limit),
            "offset": "0",
        }
        initial_url = (
            "https://api.stlouisfed.org/fred/series/observations?"
            + urllib.parse.urlencode(parameters)
        )
        batch_pages, batch_records = capture_pages(
            provider=f"fred-alfred-{series_id}-changes",
            initial_url=initial_url,
            raw_directory=raw_directory / f"changes-{batch_index:04d}",
            headers={"Accept": "application/json"},
            limiter=limiter or RequestLimiter(60),
            next_url=_next_page,
            extract_records=lambda payload: _changed_observations(payload, series_id),
            maximum_retries=2,
            allow_network=not offline,
            secret_query={"api_key": api_key} if not offline else None,
            request_timeout_seconds=180,
        )
        receipts = _receipts(batch_pages, batch_records)
        change_records.extend(
            {**record, "_received_at": receipt}
            for record, receipt in zip(batch_records, receipts, strict=True)
        )
        pages.extend(batch_pages)

    interval_records = reconstruct_vintage_intervals(change_records)
    normalized = [
        normalize_fred_observation(series_id, raw, str(raw["_received_at"]))
        for raw in interval_records
    ]
    return pages, normalized


def normalize_fred_observation(
    series_id: str, raw: dict[str, Any], received_at: str
) -> dict[str, Any]:
    observation_date = date.fromisoformat(str(raw["date"]))
    realtime_start = date.fromisoformat(str(raw["realtime_start"]))
    realtime_end = date.fromisoformat(str(raw["realtime_end"]))
    raw_value = raw.get("value")
    value = None if raw_value in {None, ".", ""} else float(raw_value)
    if value is not None and not math.isfinite(value):
        raise ValueError(f"Non-finite FRED value for {series_id} {observation_date}")
    # ALFRED exposes a release date, not a time. End-of-UTC-day admission is
    # deliberately conservative: a same-day value cannot enter a US close.
    available_at = datetime.combine(
        realtime_start, time(23, 59, 59, 999999), timezone.utc
    ).isoformat()
    core: dict[str, Any] = {
        "schemaVersion": "cycle1-macro-vintage-v1",
        "provider": "fred-alfred",
        "seriesId": series_id,
        "observationDate": observation_date.isoformat(),
        "realtimeStart": realtime_start.isoformat(),
        "realtimeEnd": realtime_end.isoformat(),
        "availableAt": available_at,
        "value": value,
        "missing": value is None,
        "ingestedAt": received_at,
    }
    return {**core, "hash": content_hash(core)}


def reconstruct_vintage_intervals(
    changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert ALFRED output-type-3 change events into real-time intervals."""
    by_observation: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for change in changes:
        observation_date = date.fromisoformat(str(change["date"])).isoformat()
        realtime_start = date.fromisoformat(
            str(change["realtime_start"])
        ).isoformat()
        existing = by_observation[observation_date].get(realtime_start)
        if existing is not None and existing.get("value") != change.get("value"):
            raise ValueError(
                "Conflicting FRED values for one observation and vintage date"
            )
        by_observation[observation_date][realtime_start] = change

    intervals: list[dict[str, Any]] = []
    for observation_date, event_map in sorted(by_observation.items()):
        starts = sorted(event_map)
        for index, start in enumerate(starts):
            realtime_end = "9999-12-31"
            if index + 1 < len(starts):
                end = date.fromisoformat(starts[index + 1]) - timedelta(days=1)
                realtime_end = end.isoformat()
            intervals.append(
                {
                    **event_map[start],
                    "date": observation_date,
                    "realtime_start": start,
                    "realtime_end": realtime_end,
                }
            )
    return intervals


def _changed_observations(
    payload: dict[str, Any], series_id: str
) -> list[dict[str, Any]]:
    observations = payload.get("observations")
    if not isinstance(observations, list) or any(
        not isinstance(item, dict) for item in observations
    ):
        raise ValueError("FRED observations must be a list of objects")
    prefix = f"{series_id}_"
    changes: list[dict[str, Any]] = []
    for observation in observations:
        observation_date = str(observation.get("date", ""))
        date.fromisoformat(observation_date)
        fields = sorted(key for key in observation if key.startswith(prefix))
        if not fields:
            # output_type=3 can include a date-only row when none of the
            # requested vintages introduced or revised that observation.
            continue
        for field in fields:
            compact_date = field.removeprefix(prefix)
            if len(compact_date) != 8 or not compact_date.isdigit():
                raise ValueError(f"Invalid FRED vintage field {field}")
            realtime_start = datetime.strptime(compact_date, "%Y%m%d").date()
            changes.append(
                {
                    "date": observation_date,
                    "realtime_start": realtime_start.isoformat(),
                    "value": observation[field],
                }
            )
    return changes


def _vintage_dates(payload: dict[str, Any]) -> list[dict[str, str]]:
    values = payload.get("vintage_dates")
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise ValueError("FRED vintage_dates must be a list of dates")
    return [{"vintage_date": item} for item in values]


def _validate_vintage_dates(values: list[str], as_of: date) -> None:
    parsed = [date.fromisoformat(value) for value in values]
    if not parsed or parsed != sorted(set(parsed)):
        raise ValueError("FRED vintage dates must be nonempty, unique, and sorted")
    if parsed[-1] > as_of:
        raise ValueError("FRED returned a vintage date after the frozen as-of date")


def _batches(values: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        raise ValueError("FRED vintage batch size must be positive")
    return [values[index : index + size] for index in range(0, len(values), size)]


def _next_page(payload: dict[str, Any], current_url: str) -> str | None:
    count = int(payload.get("count", 0))
    offset = int(payload.get("offset", 0))
    limit = int(payload.get("limit", 100_000))
    if offset + limit >= count:
        return None
    parsed = urllib.parse.urlsplit(current_url)
    query = dict(urllib.parse.parse_qsl(parsed.query))
    query["offset"] = str(offset + limit)
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), "")
    )


def _receipts(pages: list[ArchivedPage], records: list[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for page in pages:
        result.extend([page.received_at] * page.records)
    if len(result) != len(records):
        raise ValueError("FRED page receipt accounting mismatch")
    return result
