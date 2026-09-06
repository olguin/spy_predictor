"""Cross-provider one-minute bar comparison and quality reporting."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from spy_predictor_quant.market_archive import (
    content_hash,
    create_immutable_run_directory,
    file_sha256,
    read_ndjson,
    utc_now,
    write_bytes_exclusive,
    write_json_exclusive,
    write_ndjson_exclusive,
)


PRICE_FIELDS = ("open", "high", "low", "close")


def normalize_alpaca_bars(
    instrument: str,
    bars: Iterable[dict[str, object]],
    received_at: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for bar in bars:
        event_time = _parse_instant(bar.get("t"))
        without_hash: dict[str, object] = {
            "schemaVersion": "market-bar-v1",
            "source": "alpaca-sip",
            "sourceTimestamp": event_time,
            "firstSeenAt": received_at,
            "effectiveTimestamp": event_time,
            "ingestionTimestamp": received_at,
            "version": "alpaca-v2-stock-bars-v1",
            "provenanceClass": "event-time-only",
            "instrument": instrument,
            "symbol": instrument,
            "eventTime": event_time,
            "open": _number(bar, "o"),
            "high": _number(bar, "h"),
            "low": _number(bar, "l"),
            "close": _number(bar, "c"),
            "volume": _number(bar, "v"),
            "weightedAveragePrice": _number(bar, "vw"),
            "tradeCount": int(bar.get("n", 0)),
            "barSize": "1 min",
            "whatToShow": "TRADES",
        }
        records.append({**without_hash, "hash": content_hash(without_hash)})
    return sorted(records, key=lambda record: str(record["eventTime"]))


def compare_instrument_bars(
    instrument: str,
    ibkr_bars: list[dict[str, object]],
    reference_bars: list[dict[str, object]],
    *,
    price_outlier_bps: float = 5.0,
    volume_outlier_percent: float = 25.0,
) -> dict[str, Any]:
    ibkr_duplicates = _duplicate_count(ibkr_bars)
    reference_duplicates = _duplicate_count(reference_bars)
    ibkr_by_time = _index_unique(ibkr_bars, "IBKR")
    reference_by_time = _index_unique(reference_bars, "reference")
    ibkr_times = set(ibkr_by_time)
    reference_times = set(reference_by_time)
    intersection = sorted(ibkr_times & reference_times)
    missing_from_ibkr = sorted(reference_times - ibkr_times)
    missing_from_reference = sorted(ibkr_times - reference_times)
    union_size = len(ibkr_times | reference_times)

    field_differences: dict[str, list[float]] = {
        field: [] for field in PRICE_FIELDS
    }
    close_bps: list[float] = []
    volume_absolute: list[float] = []
    volume_percent: list[float] = []
    outliers: list[dict[str, object]] = []
    for timestamp in intersection:
        left = ibkr_by_time[timestamp]
        right = reference_by_time[timestamp]
        for field in PRICE_FIELDS:
            field_differences[field].append(
                abs(float(left[field]) - float(right[field]))
            )
        reference_close = float(right["close"])
        close_difference_bps = (
            abs(float(left["close"]) - reference_close)
            / reference_close
            * 10_000
            if reference_close
            else 0.0
        )
        close_bps.append(close_difference_bps)
        absolute_volume_difference = abs(
            float(left["volume"]) - float(right["volume"])
        )
        volume_absolute.append(absolute_volume_difference)
        reference_volume = float(right["volume"])
        volume_difference_percent = (
            absolute_volume_difference / reference_volume * 100
            if reference_volume
            else 0.0
        )
        volume_percent.append(volume_difference_percent)
        if (
            close_difference_bps > price_outlier_bps
            or volume_difference_percent > volume_outlier_percent
        ):
            outliers.append(
                {
                    "eventTime": timestamp,
                    "ibkrClose": left["close"],
                    "referenceClose": right["close"],
                    "closeDifferenceBps": close_difference_bps,
                    "ibkrVolume": left["volume"],
                    "referenceVolume": right["volume"],
                    "volumeDifferencePercent": volume_difference_percent,
                }
            )

    return {
        "instrument": instrument,
        "ibkrBars": len(ibkr_by_time),
        "referenceBars": len(reference_by_time),
        "ibkrDuplicateTimestamps": ibkr_duplicates,
        "referenceDuplicateTimestamps": reference_duplicates,
        "intersectionBars": len(intersection),
        "unionBars": union_size,
        "intersectionCoveragePercent": (
            len(intersection) / union_size * 100 if union_size else 0.0
        ),
        "referenceCoverageByIbkrPercent": (
            len(intersection) / len(reference_by_time) * 100
            if reference_by_time
            else 0.0
        ),
        "ibkrCoverageByReferencePercent": (
            len(intersection) / len(ibkr_by_time) * 100 if ibkr_by_time else 0.0
        ),
        "missingFromIbkr": {
            "count": len(missing_from_ibkr),
            "sample": missing_from_ibkr[:100],
        },
        "missingFromReference": {
            "count": len(missing_from_reference),
            "sample": missing_from_reference[:100],
        },
        "timestampAlignment": _timestamp_alignment(ibkr_times, reference_times),
        "priceAbsoluteDifferences": {
            field: _summary(values) for field, values in field_differences.items()
        },
        "closeDifferenceBps": _summary(close_bps),
        "volumeAbsoluteDifference": _summary(volume_absolute),
        "volumeDifferencePercent": _summary(volume_percent),
        "sessionBoundaries": _compare_session_boundaries(
            ibkr_by_time,
            reference_by_time,
        ),
        "outlierThresholds": {
            "priceBps": price_outlier_bps,
            "volumePercent": volume_outlier_percent,
        },
        "outliers": {"count": len(outliers), "sample": outliers[:100]},
    }


def _summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "p95": None, "maximum": None}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, int((len(ordered) - 1) * 0.95))
    return {
        "count": len(values),
        "mean": sum(values) / len(values),
        "p95": ordered[p95_index],
        "maximum": ordered[-1],
    }


def _timestamp_alignment(
    ibkr_times: set[str],
    reference_times: set[str],
) -> dict[str, object]:
    reference_datetimes = {
        datetime.fromisoformat(timestamp): timestamp for timestamp in reference_times
    }
    offsets: Counter[int | str] = Counter()
    for timestamp in ibkr_times:
        parsed = datetime.fromisoformat(timestamp)
        if parsed in reference_datetimes:
            offsets[0] += 1
            continue
        matched = False
        for distance in range(1, 6):
            for offset in (-distance, distance):
                if parsed + timedelta(minutes=offset) in reference_datetimes:
                    offsets[offset] += 1
                    matched = True
                    break
            if matched:
                break
        if not matched:
            offsets["unmatched"] += 1
    return {
        "nearestOffsetMinutes": {
            str(key): value
            for key, value in sorted(offsets.items(), key=lambda item: str(item[0]))
        },
        "exactMatchPercentOfIbkr": (
            offsets[0] / len(ibkr_times) * 100 if ibkr_times else 0.0
        ),
    }


def _compare_session_boundaries(
    ibkr_by_time: dict[str, dict[str, object]],
    reference_by_time: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    ibkr_sessions = _session_boundaries(ibkr_by_time)
    reference_sessions = _session_boundaries(reference_by_time)
    return [
        {
            "sessionDate": date,
            "ibkr": ibkr_sessions.get(date),
            "reference": reference_sessions.get(date),
        }
        for date in sorted(set(ibkr_sessions) | set(reference_sessions))
    ]


def _session_boundaries(
    bars: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    eastern = ZoneInfo("America/New_York")
    sessions: dict[str, list[datetime]] = {}
    for timestamp in bars:
        local = datetime.fromisoformat(timestamp).astimezone(eastern)
        sessions.setdefault(local.date().isoformat(), []).append(local)
    return {
        date: {
            "first": min(values).isoformat(),
            "last": max(values).isoformat(),
            "bars": len(values),
        }
        for date, values in sessions.items()
    }


def _duplicate_count(bars: list[dict[str, object]]) -> int:
    timestamps = [str(bar["eventTime"]) for bar in bars]
    return len(timestamps) - len(set(timestamps))


def _index_unique(
    bars: list[dict[str, object]],
    source: str,
) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    for bar in bars:
        timestamp = str(bar["eventTime"])
        previous = indexed.get(timestamp)
        if previous is not None:
            fields = (*PRICE_FIELDS, "volume")
            if any(float(previous[field]) != float(bar[field]) for field in fields):
                raise ValueError(
                    f"{source} contains conflicting duplicate bar timestamp "
                    f"{timestamp}"
                )
            continue
        indexed[timestamp] = bar
    return indexed


def _fetch_alpaca_pages(
    instrument: str,
    start: str,
    end: str,
    raw_directory: Path,
    key_id: str,
    secret_key: str,
    feed: str,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[tuple[int, int, str]],
]:
    bars: list[dict[str, object]] = []
    pages: list[dict[str, object]] = []
    receipt_ranges: list[tuple[int, int, str]] = []
    page_token: str | None = None
    page_number = 0
    while True:
        parameters = {
            "timeframe": "1Min",
            "start": start,
            "end": end,
            "adjustment": "raw",
            "feed": feed,
            "sort": "asc",
            "limit": "10000",
        }
        if page_token:
            parameters["page_token"] = page_token
        url = (
            f"https://data.alpaca.markets/v2/stocks/{instrument}/bars?"
            f"{urllib.parse.urlencode(parameters)}"
        )
        request = urllib.request.Request(
            url,
            headers={
                "APCA-API-KEY-ID": key_id,
                "APCA-API-SECRET-KEY": secret_key,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                status = response.status
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(
                f"Alpaca history request for {instrument} failed with "
                f"HTTP {error.code}: {detail}"
            ) from error
        received_at = utc_now()
        page_path = raw_directory / f"{instrument}-page-{page_number:04d}.json"
        page_hash = write_bytes_exclusive(page_path, raw)
        payload = json.loads(raw)
        raw_bars = payload.get("bars", [])
        if not isinstance(raw_bars, list):
            raise ValueError(f"Alpaca returned invalid bars for {instrument}")
        start_index = len(bars)
        bars.extend(raw_bars)
        end_index = len(bars)
        receipt_ranges.append((start_index, end_index, received_at))
        pages.append(
            {
                "instrument": instrument,
                "page": page_number,
                "path": str(page_path),
                "sha256": page_hash,
                "httpStatus": status,
                "receivedAt": received_at,
                "bars": len(raw_bars),
            }
        )
        page_token = payload.get("next_page_token")
        if not page_token:
            break
        page_number += 1
    return bars, pages, receipt_ranges


def find_latest_history_manifest(root: Path) -> Path:
    candidates = sorted(root.glob("history-*/manifest.json"))
    if not candidates:
        raise FileNotFoundError(f"No IBKR history manifest found under {root}")
    successful = [
        candidate
        for candidate in candidates
        if json.loads(candidate.read_text(encoding="utf-8")).get("status") == "ok"
    ]
    if not successful:
        raise FileNotFoundError(f"No successful IBKR history run found under {root}")
    return successful[-1]


def run_comparison(
    ibkr_manifest_path: Path,
    output_root: Path,
    key_id: str,
    secret_key: str,
    feed: str,
) -> dict[str, Any]:
    ibkr_manifest = json.loads(ibkr_manifest_path.read_text(encoding="utf-8"))
    if ibkr_manifest.get("status") != "ok":
        raise ValueError("Comparison requires a successful IBKR history run")
    bars_path = Path(ibkr_manifest["normalizedBars"]["path"])
    expected_ibkr_hash = str(ibkr_manifest["normalizedBars"]["sha256"])
    actual_ibkr_hash = file_sha256(bars_path)
    if actual_ibkr_hash != expected_ibkr_hash:
        raise ValueError(
            f"IBKR normalized bars hash mismatch: expected {expected_ibkr_hash}, "
            f"got {actual_ibkr_hash}"
        )
    ibkr_records = read_ndjson(bars_path)
    run_directory = create_immutable_run_directory(output_root, "comparison")
    raw_directory = run_directory / "alpaca-raw"
    raw_directory.mkdir()

    all_alpaca_records: list[dict[str, object]] = []
    pages: list[dict[str, object]] = []
    comparisons: dict[str, Any] = {}
    for instrument in ("SPY", "QQQ"):
        ibkr_bars = [
            record
            for record in ibkr_records
            if record.get("instrument") == instrument
        ]
        if not ibkr_bars:
            raise ValueError(f"IBKR history contains no {instrument} bars")
        start = min(str(record["eventTime"]) for record in ibkr_bars)
        end = max(str(record["eventTime"]) for record in ibkr_bars)
        alpaca_bars, instrument_pages, receipt_ranges = _fetch_alpaca_pages(
            instrument,
            start,
            end,
            raw_directory,
            key_id,
            secret_key,
            feed,
        )
        alpaca_records = [
            record
            for start_index, end_index, received_at in receipt_ranges
            for record in normalize_alpaca_bars(
                instrument,
                alpaca_bars[start_index:end_index],
                received_at,
            )
        ]
        all_alpaca_records.extend(alpaca_records)
        pages.extend(instrument_pages)
        comparisons[instrument] = compare_instrument_bars(
            instrument,
            ibkr_bars,
            alpaca_records,
        )

    alpaca_count, alpaca_hash = write_ndjson_exclusive(
        run_directory / "alpaca-bars.ndjson",
        sorted(
            all_alpaca_records,
            key=lambda record: (
                str(record["instrument"]),
                str(record["eventTime"]),
            ),
        ),
    )
    futures_comparison = {
        "ES": {
            "status": "not-configured",
            "reason": "Massive futures reference data is not integrated yet",
        },
        "NQ": {
            "status": "not-configured",
            "reason": "Massive futures reference data is not integrated yet",
        },
    }
    report_core: dict[str, Any] = {
        "schemaVersion": "market-data-comparison-v1",
        "ibkr": {
            "manifestPath": str(ibkr_manifest_path),
            "barsPath": str(bars_path),
            "barsSha256": ibkr_manifest["normalizedBars"]["sha256"],
            "catalogHash": ibkr_manifest["catalogHash"],
        },
        "reference": {
            "provider": "alpaca",
            "feed": feed,
            "adjustment": "raw",
            "pages": pages,
            "normalizedBarsPath": str(run_directory / "alpaca-bars.ndjson"),
            "normalizedBars": alpaca_count,
            "normalizedBarsSha256": alpaca_hash,
        },
        "comparisons": comparisons,
        "futuresComparison": futures_comparison,
    }
    report_identity = {
        "schemaVersion": report_core["schemaVersion"],
        "ibkr": {
            "barsSha256": expected_ibkr_hash,
            "catalogHash": ibkr_manifest["catalogHash"],
        },
        "reference": {
            "provider": "alpaca",
            "feed": feed,
            "adjustment": "raw",
            "pageHashes": [
                {
                    "instrument": page["instrument"],
                    "page": page["page"],
                    "sha256": page["sha256"],
                    "bars": page["bars"],
                }
                for page in pages
            ],
            "normalizedBarsSha256": alpaca_hash,
        },
        "comparisons": comparisons,
        "futuresComparison": futures_comparison,
    }
    report = {
        **report_core,
        "generatedAt": utc_now(),
        "reportHash": content_hash(report_identity),
    }
    report_path = run_directory / "report.json"
    write_json_exclusive(report_path, report)
    return {**report, "reportPath": str(report_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ibkr-manifest", type=Path)
    parser.add_argument(
        "--ibkr-history-root",
        type=Path,
        default=Path("datasets/ibkr/history"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("datasets/comparisons"),
    )
    args = parser.parse_args()

    try:
        key_id = os.environ.get("APCA_API_KEY_ID", "").strip()
        secret_key = os.environ.get("APCA_API_SECRET_KEY", "").strip()
        if not key_id or not secret_key:
            raise ValueError("Alpaca API credentials are missing from .env")
        feed = os.environ.get("ALPACA_DATA_FEED", "sip").strip() or "sip"
        manifest_path = args.ibkr_manifest or find_latest_history_manifest(
            args.ibkr_history_root
        )
        result = run_comparison(
            manifest_path,
            args.output_root,
            key_id,
            secret_key,
            feed,
        )
    except Exception as error:
        print(
            json.dumps({"status": "error", "message": str(error)}, indent=2),
            file=sys.stderr,
        )
        return 1

    compact_comparisons = {
        instrument: {
            "ibkrBars": comparison["ibkrBars"],
            "referenceBars": comparison["referenceBars"],
            "intersectionBars": comparison["intersectionBars"],
            "intersectionCoveragePercent": comparison[
                "intersectionCoveragePercent"
            ],
            "maximumCloseDifferenceBps": comparison["closeDifferenceBps"][
                "maximum"
            ],
            "meanVolumeDifferencePercent": comparison[
                "volumeDifferencePercent"
            ]["mean"],
            "outliers": comparison["outliers"]["count"],
        }
        for instrument, comparison in result["comparisons"].items()
    }
    print(
        json.dumps(
            {
                "status": "ok",
                "reportPath": result["reportPath"],
                "reportHash": result["reportHash"],
                "comparisons": compact_comparisons,
                "futuresComparison": result["futuresComparison"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _parse_instant(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Market bar timestamp must be a string: {value}")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Market bar timestamp requires a timezone: {value}")
    return parsed.astimezone(timezone.utc).isoformat()


def _number(bar: dict[str, object], key: str) -> float:
    value = bar.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Alpaca bar field {key} must be numeric")
    return float(value)


if __name__ == "__main__":
    raise SystemExit(main())
