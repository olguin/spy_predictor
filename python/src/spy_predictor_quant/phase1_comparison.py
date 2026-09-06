"""Deterministic four-instrument comparison against pinned IBKR history."""

from __future__ import annotations

import json
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from spy_predictor_quant.historical_http import ArchivedPage, RequestLimiter, capture_pages
from spy_predictor_quant.market_archive import content_hash, file_sha256, read_ndjson
from spy_predictor_quant.market_comparison import (
    compare_instrument_bars,
    find_latest_history_manifest,
    normalize_alpaca_bars,
)


def build_phase1_comparison(
    *,
    dataset_manifest_path: Path,
    repo_root: Path,
    tournament_config: dict[str, Any],
    ibkr_manifest_path: Path | None = None,
    offline: bool = False,
) -> tuple[Path, dict[str, Any]]:
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    bars_path = repo_root / dataset_manifest["normalizedBars"]["path"]
    _verify_hash(bars_path, dataset_manifest["normalizedBars"]["sha256"])
    ibkr_path = ibkr_manifest_path or find_latest_history_manifest(
        repo_root / "datasets" / "ibkr" / "history"
    )
    ibkr_manifest = json.loads(ibkr_path.read_text(encoding="utf-8"))
    if ibkr_manifest.get("status") != "ok":
        raise ValueError("Phase 1 comparison requires a successful IBKR history run")
    ibkr_bars_path = Path(str(ibkr_manifest["normalizedBars"]["path"]))
    if not ibkr_bars_path.is_absolute():
        ibkr_bars_path = repo_root / ibkr_bars_path
    _verify_hash(ibkr_bars_path, ibkr_manifest["normalizedBars"]["sha256"])

    ibkr = read_ndjson(ibkr_bars_path)
    validation_root = (
        repo_root
        / "datasets"
        / "phase1"
        / "validation"
        / str(ibkr_manifest["normalizedBars"]["sha256"])[:16]
    )
    references, validation_pages = _validation_references(
        ibkr,
        dataset_manifest,
        validation_root,
        offline,
        repo_root,
    )
    comparisons: dict[str, Any] = {}
    gates: dict[str, Any] = {}
    settings = tournament_config["crossProvider"]
    minimum_intersection = int(settings["minimumIntersectionBars"])
    maximum_difference = float(settings["maximumCloseDifferenceBps"])
    roll_mappings = dataset_manifest["futuresRollPolicy"]["mappings"]
    expected_contracts = {
        instrument: roll_mappings[instrument][-1]["ticker"]
        for instrument in ("ES", "NQ")
    }
    for instrument in ("SPY", "QQQ", "ES", "NQ"):
        left = [item for item in ibkr if item.get("instrument") == instrument]
        right = references[instrument]
        if instrument in {"ES", "NQ"}:
            local_symbols = {str(item.get("localSymbol")) for item in left}
            if local_symbols != {expected_contracts[instrument]}:
                raise ValueError(
                    f"IBKR {instrument} comparison contract {sorted(local_symbols)} "
                    f"does not match {expected_contracts[instrument]}"
                )
        comparison = compare_instrument_bars(
            instrument,
            left,
            right,
            price_outlier_bps=maximum_difference,
        )
        comparisons[instrument] = comparison
        maximum = comparison["closeDifferenceBps"]["maximum"]
        gates[instrument] = {
            "minimumIntersectionBars": {
                "threshold": minimum_intersection,
                "value": comparison["intersectionBars"],
                "passed": comparison["intersectionBars"] >= minimum_intersection,
            },
            "maximumCloseDifferenceBps": {
                "threshold": maximum_difference,
                "value": maximum,
                "passed": maximum is not None and maximum <= maximum_difference,
            },
        }
        gates[instrument]["passed"] = all(
            item["passed"]
            for key, item in gates[instrument].items()
            if key != "passed"
        )

    identity = {
        "schemaVersion": "phase1-cross-provider-v1",
        "datasetVersion": dataset_manifest["datasetVersion"],
        "datasetBarsSha256": dataset_manifest["normalizedBars"]["sha256"],
        "ibkrBarsSha256": ibkr_manifest["normalizedBars"]["sha256"],
        "ibkrCatalogHash": ibkr_manifest["catalogHash"],
        "validationPages": validation_pages,
        "comparisons": comparisons,
        "gates": gates,
    }
    report = {**identity, "comparisonHash": content_hash(identity)}
    output_path = (
        dataset_manifest_path.parent
        / f"cross-provider-{report['comparisonHash'][:16]}.json"
    )
    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_or_verify(output_path, encoded)
    return output_path, report


def _validation_references(
    ibkr: list[dict[str, Any]],
    dataset_manifest: dict[str, Any],
    validation_root: Path,
    offline: bool,
    repo_root: Path,
) -> tuple[dict[str, list[dict[str, object]]], list[dict[str, object]]]:
    alpaca_key = os.environ.get("APCA_API_KEY_ID", "").strip()
    alpaca_secret = os.environ.get("APCA_API_SECRET_KEY", "").strip()
    massive_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if not offline and (not alpaca_key or not alpaca_secret or not massive_key):
        raise ValueError("Cross-provider validation credentials are missing")
    references: dict[str, list[dict[str, object]]] = {}
    page_manifest: list[dict[str, object]] = []
    alpaca_limiter = RequestLimiter(180)
    massive_limiter = RequestLimiter(5)
    roll_mappings = dataset_manifest["futuresRollPolicy"]["mappings"]
    for instrument in ("SPY", "QQQ", "ES", "NQ"):
        selected = [item for item in ibkr if item.get("instrument") == instrument]
        if not selected:
            raise ValueError(f"IBKR history contains no {instrument} bars")
        start = min(datetime.fromisoformat(str(item["eventTime"])) for item in selected)
        end = max(datetime.fromisoformat(str(item["eventTime"])) for item in selected)
        if instrument in {"SPY", "QQQ"}:
            parameters = {
                "timeframe": "1Min",
                "start": start.astimezone(timezone.utc).isoformat(),
                "end": (end + timedelta(minutes=1)).astimezone(timezone.utc).isoformat(),
                "adjustment": "raw",
                "feed": "sip",
                "sort": "asc",
                "limit": "10000",
            }
            url = (
                f"https://data.alpaca.markets/v2/stocks/{instrument}/bars?"
                f"{urllib.parse.urlencode(parameters)}"
            )

            def alpaca_next(payload: dict[str, Any], current: str) -> str | None:
                token = payload.get("next_page_token")
                if not token:
                    return None
                parsed = urllib.parse.urlsplit(current)
                query = dict(urllib.parse.parse_qsl(parsed.query))
                query["page_token"] = str(token)
                return urllib.parse.urlunsplit(
                    (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), "")
                )

            pages, records = capture_pages(
                provider="alpaca-sip-validation",
                initial_url=url,
                raw_directory=validation_root / "alpaca" / instrument,
                headers=(
                    {
                        "APCA-API-KEY-ID": alpaca_key,
                        "APCA-API-SECRET-KEY": alpaca_secret,
                    }
                    if not offline
                    else {}
                ),
                limiter=alpaca_limiter,
                next_url=alpaca_next,
                extract_records=lambda payload: _records(payload, "bars"),
                allow_network=not offline,
            )
            normalized: list[dict[str, object]] = []
            for page, page_records in _page_records(pages, records):
                normalized.extend(
                    normalize_alpaca_bars(instrument, page_records, page.received_at)
                )
            references[instrument] = normalized
        else:
            expected_ticker = roll_mappings[instrument][-1]["ticker"]
            nanosecond_start = int(start.timestamp() * 1_000_000_000)
            nanosecond_end = int((end + timedelta(minutes=1)).timestamp() * 1_000_000_000)
            parameters = {
                "resolution": "1min",
                "window_start.gte": str(nanosecond_start),
                "window_start.lt": str(nanosecond_end),
                "limit": "50000",
                "sort": "window_start.asc",
            }
            url = (
                f"https://api.massive.com/futures/v1/aggs/{expected_ticker}?"
                f"{urllib.parse.urlencode(parameters)}"
            )
            pages, records = capture_pages(
                provider="massive-futures-validation",
                initial_url=url,
                raw_directory=validation_root / "massive" / expected_ticker,
                headers=(
                    {"Authorization": f"Bearer {massive_key}"} if not offline else {}
                ),
                limiter=massive_limiter,
                next_url=lambda payload, _current: payload.get("next_url"),
                extract_records=lambda payload: _records(payload, "results"),
                allow_network=not offline,
            )
            references[instrument] = [
                _normalize_massive_validation(instrument, expected_ticker, record)
                for record in records
            ]
        page_manifest.extend(
            {
                "provider": page.provider,
                "path": str(page.path.relative_to(repo_root)),
                "sha256": page.sha256,
                "records": page.records,
                "requestUrl": page.request_url,
            }
            for page in pages
        )
    return references, page_manifest


def _page_records(
    pages: list[ArchivedPage], records: list[dict[str, Any]]
) -> list[tuple[ArchivedPage, list[dict[str, Any]]]]:
    result: list[tuple[ArchivedPage, list[dict[str, Any]]]] = []
    index = 0
    for page in pages:
        result.append((page, records[index : index + page.records]))
        index += page.records
    if index != len(records):
        raise ValueError("Validation page record accounting mismatch")
    return result


def _records(payload: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = payload.get(field, [])
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"Validation response {field} must be a list of objects")
    return value


def _normalize_massive_validation(
    instrument: str, ticker: str, record: dict[str, Any]
) -> dict[str, object]:
    if record.get("ticker") != ticker:
        raise ValueError(f"Massive validation returned the wrong {instrument} contract")
    raw_timestamp = record.get("window_start")
    if not isinstance(raw_timestamp, int) or isinstance(raw_timestamp, bool):
        raise ValueError("Massive validation timestamp must be integer nanoseconds")
    seconds, nanoseconds = divmod(raw_timestamp, 1_000_000_000)
    event_time = datetime.fromtimestamp(
        seconds + nanoseconds / 1_000_000_000, timezone.utc
    ).isoformat()
    return {
        "instrument": instrument,
        "contractTicker": ticker,
        "eventTime": event_time,
        "open": float(record["open"]),
        "high": float(record["high"]),
        "low": float(record["low"]),
        "close": float(record["close"]),
        "volume": float(record["volume"]),
    }


def _verify_hash(path: Path, expected: str) -> None:
    actual = file_sha256(path)
    if actual != expected:
        raise ValueError(f"Hash mismatch for {path}: expected {expected}, got {actual}")


def _write_or_verify(path: Path, value: bytes) -> None:
    if path.exists():
        if path.read_bytes() != value:
            raise ValueError(f"Immutable comparison mismatch at {path}")
        return
    with path.open("xb") as output:
        output.write(value)
