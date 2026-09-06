"""Immutable Alpaca/Massive dataset construction for TARGET-TOURNAMENT-001."""

from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.parse
from datetime import date, datetime, time as wall_time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator

from spy_predictor_quant.historical_http import (
    ArchivedPage,
    RequestLimiter,
    capture_pages,
)
from spy_predictor_quant.market_archive import content_hash, file_sha256
from spy_predictor_quant.phase1_config import Phase1Plan, RollMapping


NY = ZoneInfo("America/New_York")
PRICE_FIELDS = ("open", "high", "low", "close")


def build_phase1_dataset(
    plan: Phase1Plan,
    repo_root: Path,
    *,
    offline: bool = False,
) -> tuple[Path, dict[str, Any]]:
    credentials = _credentials(offline)
    raw_root = (
        repo_root
        / "datasets"
        / "phase1"
        / "raw"
        / str(plan.dataset["rawArchiveId"])
    )
    raw_root.mkdir(parents=True, exist_ok=True)
    page_entries: list[dict[str, Any]] = []
    normalized: list[dict[str, object]] = []

    alpaca_settings = plan.dataset["alpaca"]
    alpaca_limiter = RequestLimiter(
        int(alpaca_settings["maximumRequestsPerMinute"])
    )
    for symbol in alpaca_settings["symbols"]:
        pages, records = _capture_alpaca(
            symbol,
            plan,
            raw_root / "alpaca" / symbol,
            credentials.get("alpacaKey", ""),
            credentials.get("alpacaSecret", ""),
            alpaca_limiter,
            offline,
        )
        page_entries.extend(_page_manifest(repo_root, pages))
        normalized.extend(
            _normalize_alpaca(symbol, pages, records, plan)
        )

    massive_settings = plan.dataset["massive"]
    research_dates = {
        str(record["sessionDate"])
        for record in normalized
        if record["instrument"] == "SPY"
    }
    if not research_dates:
        raise ValueError("Alpaca SPY archive produced no research sessions")
    massive_limiter = RequestLimiter(
        int(massive_settings["maximumRequestsPerMinute"])
    )
    contract_records: dict[str, dict[str, Any]] = {}
    schedule_records: dict[str, list[dict[str, Any]]] = {}
    for product in massive_settings["products"]:
        indexed: dict[str, dict[str, Any]] = {}
        for mapping in plan.roll_mappings[product]:
            pages, records = _capture_massive_contract(
                mapping,
                raw_root / "massive" / "contracts" / mapping.ticker,
                credentials.get("massiveKey", ""),
                massive_limiter,
                offline,
            )
            page_entries.extend(_page_manifest(repo_root, pages))
            matches = [
                record for record in records if record.get("ticker") == mapping.ticker
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"Massive point-in-time catalog returned {len(matches)} "
                    f"matches for explicit contract {mapping.ticker}"
                )
            record = matches[0]
            if record.get("active") is not True:
                raise ValueError(
                    f"Massive reports {mapping.ticker} inactive on {mapping.end_date}"
                )
            if record.get("product_code") != product:
                raise ValueError(f"Massive returned wrong product for {mapping.ticker}")
            actual_last_trade = record.get("last_trade_date")
            if actual_last_trade != mapping.last_trade_date.isoformat():
                raise ValueError(
                    f"Configured last trade date for {mapping.ticker} is "
                    f"{mapping.last_trade_date}, Massive reports {actual_last_trade}"
                )
            indexed[mapping.ticker] = record
        contract_records.update(indexed)

        pages, records = _capture_massive_schedules(
            product,
            plan,
            raw_root / "massive" / "schedules" / product,
            credentials.get("massiveKey", ""),
            massive_limiter,
            offline,
        )
        page_entries.extend(_page_manifest(repo_root, pages))
        schedule_records[product] = records

        for mapping in plan.roll_mappings[product]:
            pages, records = _capture_massive_aggregates(
                mapping,
                plan,
                raw_root / "massive" / "aggregates" / mapping.ticker,
                credentials.get("massiveKey", ""),
                massive_limiter,
                offline,
            )
            page_entries.extend(_page_manifest(repo_root, pages))
            normalized.extend(
                _normalize_massive(
                    mapping,
                    pages,
                    records,
                    plan,
                    research_dates,
                )
            )

    normalized, duplicate_counts = _deduplicate(normalized)
    normalized.sort(
        key=lambda record: (str(record["instrument"]), str(record["eventTime"]))
    )
    quality = _quality(normalized, duplicate_counts, plan)
    schedule_quality = _schedule_quality(schedule_records, plan)
    normalized_bytes = b"".join(
        json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
        for record in normalized
    )
    normalized_hash = hashlib.sha256(normalized_bytes).hexdigest()
    page_identity = [
        {
            "provider": entry["provider"],
            "path": entry["path"],
            "sha256": entry["sha256"],
            "records": entry["records"],
            "requestUrl": entry["requestUrl"],
        }
        for entry in page_entries
    ]
    roll_policy = plan.dataset["futuresRollPolicy"]
    dataset_identity = {
        "schemaVersion": "phase1-dataset-identity-v1",
        "planHash": plan.config_hash,
        "rawPages": page_identity,
        "normalizedBarsSha256": normalized_hash,
        "rollPolicyHash": content_hash(roll_policy),
    }
    dataset_version = f"phase1-market-{content_hash(dataset_identity)[:16]}"
    dataset_root = repo_root / "datasets" / "phase1" / dataset_version
    dataset_root.mkdir(parents=True, exist_ok=True)
    bars_path = dataset_root / "bars.ndjson"
    _write_or_link_existing(
        bars_path,
        normalized_bytes,
        normalized_hash,
        repo_root / "datasets" / "phase1",
    )

    receipts = sorted(entry["receivedAt"] for entry in page_entries)
    manifest: dict[str, Any] = {
        "schemaVersion": "phase1-dataset-manifest-v1",
        "datasetVersion": dataset_version,
        "planHash": plan.config_hash,
        "dateRange": {
            "start": plan.start_date.isoformat(),
            "end": plan.end_date.isoformat(),
        },
        "barSemantics": {
            "resolution": "1 minute",
            "timestamp": "UTC interval start",
            "barEnd": "eventTime plus one minute",
            "researchSession": plan.dataset["researchSession"],
        },
        "provenance": {
            "class": "event-time-only",
            "targetSelectionAdmissible": True,
            "replaySafeFirstSeen": False,
            "limitation": (
                "Historical aggregate providers do not expose original receive or "
                "revision lineage; immutable retrieval bytes and cross-provider "
                "comparison support target selection only."
            ),
        },
        "captureReceiptRange": [receipts[0], receipts[-1]],
        "rawPages": page_entries,
        "normalizedBars": {
            "path": str(bars_path.relative_to(repo_root)),
            "records": len(normalized),
            "sha256": normalized_hash,
        },
        "contracts": {
            ticker: contract_records[ticker] for ticker in sorted(contract_records)
        },
        "futuresRollPolicy": roll_policy,
        "futuresRollPolicyHash": content_hash(roll_policy),
        "scheduleQuality": schedule_quality,
        "quality": quality,
        "datasetIdentityHash": content_hash(dataset_identity),
    }
    schema = json.loads(
        (repo_root / "schemas" / "phase1-dataset-manifest.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(manifest)
    manifest_path = dataset_root / "manifest.json"
    manifest_bytes = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    _write_or_verify(manifest_path, manifest_bytes)
    return manifest_path, manifest


def _capture_alpaca(
    symbol: str,
    plan: Phase1Plan,
    raw_directory: Path,
    key_id: str,
    secret_key: str,
    limiter: RequestLimiter,
    offline: bool,
) -> tuple[list[ArchivedPage], list[dict[str, Any]]]:
    settings = plan.dataset["alpaca"]
    parameters = {
        "timeframe": "1Min",
        "start": f"{plan.start_date.isoformat()}T00:00:00Z",
        "end": f"{(plan.end_date + timedelta(days=1)).isoformat()}T00:00:00Z",
        "adjustment": settings["adjustment"],
        "asof": settings["asOf"],
        "feed": settings["feed"],
        "sort": "asc",
        "limit": str(settings["pageLimit"]),
    }
    initial_url = (
        f"https://data.alpaca.markets/v2/stocks/{symbol}/bars?"
        f"{urllib.parse.urlencode(parameters)}"
    )
    headers = (
        {
            "APCA-API-KEY-ID": key_id,
            "APCA-API-SECRET-KEY": secret_key,
            "Accept": "application/json",
        }
        if not offline
        else {}
    )

    def next_page(payload: dict[str, Any], current_url: str) -> str | None:
        token = payload.get("next_page_token")
        if not token:
            return None
        parsed = urllib.parse.urlsplit(current_url)
        query = dict(urllib.parse.parse_qsl(parsed.query))
        query["page_token"] = str(token)
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), "")
        )

    return _capture(
        provider="alpaca-sip",
        initial_url=initial_url,
        raw_directory=raw_directory,
        headers=headers,
        limiter=limiter,
        next_url=next_page,
        extract_records=lambda payload: _list(payload, "bars", "Alpaca"),
        offline=offline,
    )


def _capture_massive_contract(
    mapping: RollMapping,
    raw_directory: Path,
    api_key: str,
    limiter: RequestLimiter,
    offline: bool,
) -> tuple[list[ArchivedPage], list[dict[str, Any]]]:
    parameters = {
        "date": mapping.end_date.isoformat(),
        "ticker": mapping.ticker,
        "active": "true",
        "limit": "10",
        "sort": "ticker.asc",
    }
    return _capture_massive(
        "contracts",
        parameters,
        raw_directory,
        api_key,
        limiter,
        offline,
    )


def _capture_massive_schedules(
    product: str,
    plan: Phase1Plan,
    raw_directory: Path,
    api_key: str,
    limiter: RequestLimiter,
    offline: bool,
) -> tuple[list[ArchivedPage], list[dict[str, Any]]]:
    parameters = {
        "product_code": product,
        "session_end_date.gte": plan.start_date.isoformat(),
        "session_end_date.lte": plan.end_date.isoformat(),
        "limit": "1000",
        "sort": "session_end_date.asc",
    }
    return _capture_massive(
        "schedules",
        parameters,
        raw_directory,
        api_key,
        limiter,
        offline,
    )


def _capture_massive_aggregates(
    mapping: RollMapping,
    plan: Phase1Plan,
    raw_directory: Path,
    api_key: str,
    limiter: RequestLimiter,
    offline: bool,
) -> tuple[list[ArchivedPage], list[dict[str, Any]]]:
    settings = plan.dataset["massive"]
    parameters = {
        "resolution": settings["resolution"],
        "window_start.gte": mapping.start_date.isoformat(),
        "window_start.lt": (mapping.end_date + timedelta(days=1)).isoformat(),
        "limit": str(settings["pageLimit"]),
        "sort": "window_start.asc",
    }
    initial_url = (
        f"https://api.massive.com/futures/v1/aggs/{mapping.ticker}?"
        f"{urllib.parse.urlencode(parameters)}"
    )
    return _capture_massive_url(
        provider="massive-futures-aggregates",
        initial_url=initial_url,
        raw_directory=raw_directory,
        api_key=api_key,
        limiter=limiter,
        offline=offline,
    )


def _capture_massive(
    endpoint: str,
    parameters: dict[str, str],
    raw_directory: Path,
    api_key: str,
    limiter: RequestLimiter,
    offline: bool,
) -> tuple[list[ArchivedPage], list[dict[str, Any]]]:
    initial_url = (
        f"https://api.massive.com/futures/v1/{endpoint}?"
        f"{urllib.parse.urlencode(parameters)}"
    )
    return _capture_massive_url(
        provider=f"massive-futures-{endpoint}",
        initial_url=initial_url,
        raw_directory=raw_directory,
        api_key=api_key,
        limiter=limiter,
        offline=offline,
    )


def _capture_massive_url(
    *,
    provider: str,
    initial_url: str,
    raw_directory: Path,
    api_key: str,
    limiter: RequestLimiter,
    offline: bool,
) -> tuple[list[ArchivedPage], list[dict[str, Any]]]:
    return _capture(
        provider=provider,
        initial_url=initial_url,
        raw_directory=raw_directory,
        headers={"Authorization": f"Bearer {api_key}"} if not offline else {},
        limiter=limiter,
        next_url=lambda payload, _current: payload.get("next_url"),
        extract_records=lambda payload: _list(payload, "results", "Massive"),
        offline=offline,
    )


def _capture(
    *,
    provider: str,
    initial_url: str,
    raw_directory: Path,
    headers: dict[str, str],
    limiter: RequestLimiter,
    next_url: Any,
    extract_records: Any,
    offline: bool,
) -> tuple[list[ArchivedPage], list[dict[str, Any]]]:
    if offline and not (raw_directory / "page-0000.json").exists():
        raise FileNotFoundError(f"Offline run is missing raw archive {raw_directory}")
    return capture_pages(
        provider=provider,
        initial_url=initial_url,
        raw_directory=raw_directory,
        headers=headers,
        limiter=limiter,
        next_url=next_url,
        extract_records=extract_records,
        allow_network=not offline,
    )


def _normalize_alpaca(
    symbol: str,
    pages: list[ArchivedPage],
    records: list[dict[str, Any]],
    plan: Phase1Plan,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for raw, received_at in _records_with_receipts(pages, records):
        event_time = _parse_instant(raw.get("t"))
        if not _in_research_session(event_time, plan):
            continue
        values = {
            "open": _number(raw, "o"),
            "high": _number(raw, "h"),
            "low": _number(raw, "l"),
            "close": _number(raw, "c"),
            "volume": _number(raw, "v"),
        }
        _validate_ohlc(symbol, event_time, values)
        local = datetime.fromisoformat(event_time).astimezone(NY)
        core: dict[str, object] = {
            "schemaVersion": "market-bar-v2",
            "source": "alpaca-sip",
            "sourceTimestamp": event_time,
            "firstSeenAt": received_at,
            "effectiveTimestamp": event_time,
            "ingestionTimestamp": received_at,
            "version": "alpaca-v2-stock-bars-v1",
            "provenanceClass": "event-time-only",
            "instrument": symbol,
            "symbol": symbol,
            "contractTicker": None,
            "sessionDate": local.date().isoformat(),
            "eventTime": event_time,
            "barEndTime": (datetime.fromisoformat(event_time) + timedelta(minutes=1)).isoformat(),
            **values,
            "weightedAveragePrice": _optional_number(raw.get("vw")),
            "tradeCount": int(raw.get("n", 0)),
        }
        normalized.append({**core, "hash": content_hash(core)})
    return normalized


def _normalize_massive(
    mapping: RollMapping,
    pages: list[ArchivedPage],
    records: list[dict[str, Any]],
    plan: Phase1Plan,
    research_dates: set[str],
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for raw, received_at in _records_with_receipts(pages, records):
        if raw.get("ticker") != mapping.ticker:
            raise ValueError(
                f"Massive aggregate requested {mapping.ticker} but returned {raw.get('ticker')}"
            )
        event_time = _nanoseconds_to_iso(raw.get("window_start"))
        if not _in_research_session(event_time, plan):
            continue
        local_date = datetime.fromisoformat(event_time).astimezone(NY).date()
        if not (mapping.start_date <= local_date <= mapping.end_date):
            continue
        if local_date.isoformat() not in research_dates:
            continue
        session_end_date = date.fromisoformat(str(raw.get("session_end_date")))
        values = {
            "open": _number(raw, "open"),
            "high": _number(raw, "high"),
            "low": _number(raw, "low"),
            "close": _number(raw, "close"),
            "volume": _number(raw, "volume"),
        }
        _validate_ohlc(mapping.instrument, event_time, values)
        dollar_volume = _optional_number(raw.get("dollar_volume"))
        volume = values["volume"]
        core: dict[str, object] = {
            "schemaVersion": "market-bar-v2",
            "source": "massive-futures",
            "sourceTimestamp": event_time,
            "firstSeenAt": received_at,
            "effectiveTimestamp": event_time,
            "ingestionTimestamp": received_at,
            "version": "massive-futures-v1-aggs-v1",
            "provenanceClass": "event-time-only",
            "instrument": mapping.instrument,
            "symbol": mapping.instrument,
            "contractTicker": mapping.ticker,
            "sessionDate": local_date.isoformat(),
            "providerSessionDate": session_end_date.isoformat(),
            "eventTime": event_time,
            "barEndTime": (datetime.fromisoformat(event_time) + timedelta(minutes=1)).isoformat(),
            **values,
            "weightedAveragePrice": (
                dollar_volume / volume if dollar_volume is not None and volume else None
            ),
            "tradeCount": int(raw.get("transactions", 0)),
        }
        normalized.append({**core, "hash": content_hash(core)})
    return normalized


def _records_with_receipts(
    pages: list[ArchivedPage], records: list[dict[str, Any]]
) -> Iterable[tuple[dict[str, Any], str]]:
    index = 0
    for page in pages:
        for record in records[index : index + page.records]:
            yield record, page.received_at
        index += page.records
    if index != len(records):
        raise ValueError("Archived page record accounting mismatch")


def _deduplicate(
    records: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    indexed: dict[tuple[str, str], dict[str, object]] = {}
    duplicates = {instrument: 0 for instrument in ("SPY", "QQQ", "ES", "NQ")}
    for record in records:
        key = (str(record["instrument"]), str(record["eventTime"]))
        previous = indexed.get(key)
        if previous is None:
            indexed[key] = record
            continue
        fields = (*PRICE_FIELDS, "volume", "contractTicker")
        if any(previous[field] != record[field] for field in fields):
            raise ValueError(f"Conflicting normalized bars for {key}")
        duplicates[key[0]] += 1
        if str(record["firstSeenAt"]) < str(previous["firstSeenAt"]):
            indexed[key] = record
    return list(indexed.values()), duplicates


def _quality(
    records: list[dict[str, object]],
    duplicates: dict[str, int],
    plan: Phase1Plan,
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for instrument in ("SPY", "QQQ", "ES", "NQ"):
        selected = [item for item in records if item["instrument"] == instrument]
        sessions: dict[str, int] = {}
        session_volume: dict[str, float] = {}
        contracts: set[str] = set()
        for item in selected:
            session = str(item["sessionDate"])
            sessions[session] = sessions.get(session, 0) + 1
            session_volume[session] = session_volume.get(session, 0.0) + float(
                item["volume"]
            )
            if item["contractTicker"]:
                contracts.add(str(item["contractTicker"]))
        complete_sessions = sum(count == 390 for count in sessions.values())
        volumes = sorted(session_volume.values())
        median_volume = (
            volumes[len(volumes) // 2] if volumes else 0.0
        )
        result[instrument] = {
            "bars": len(selected),
            "firstTimestamp": selected[0]["eventTime"] if selected else None,
            "lastTimestamp": selected[-1]["eventTime"] if selected else None,
            "sessions": len(sessions),
            "completeSessions": complete_sessions,
            "completeSessionPercent": (
                complete_sessions / len(sessions) * 100 if sessions else 0.0
            ),
            "minimumBarsPerSession": min(sessions.values()) if sessions else 0,
            "maximumBarsPerSession": max(sessions.values()) if sessions else 0,
            "medianSessionVolume": median_volume,
            "exactDuplicatesRemoved": duplicates[instrument],
            "contracts": sorted(contracts),
        }
    return result


def _schedule_quality(
    schedules: dict[str, list[dict[str, Any]]], plan: Phase1Plan
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for product, records in schedules.items():
        dates = {
            str(record["session_end_date"])
            for record in records
            if record.get("session_end_date")
        }
        events = sorted({str(record.get("event")) for record in records})
        result[product] = {
            "records": len(records),
            "sessions": len(dates),
            "firstSession": min(dates) if dates else None,
            "lastSession": max(dates) if dates else None,
            "events": events,
            "coversConfiguredStart": plan.start_date.isoformat() in dates,
            "coversConfiguredEnd": plan.end_date.isoformat() in dates,
        }
    return result


def _page_manifest(repo_root: Path, pages: list[ArchivedPage]) -> list[dict[str, Any]]:
    return [
        {
            "provider": page.provider,
            "page": page.page,
            "path": str(page.path.relative_to(repo_root)),
            "sha256": page.sha256,
            "receivedAt": page.received_at,
            "requestUrl": page.request_url,
            "records": page.records,
        }
        for page in pages
    ]


def _write_or_verify(path: Path, value: bytes) -> None:
    if path.exists():
        actual = path.read_bytes()
        if actual != value:
            raise ValueError(f"Immutable artifact mismatch at {path}")
        return
    with path.open("xb") as output:
        output.write(value)


def _write_or_link_existing(
    path: Path,
    value: bytes,
    expected_hash: str,
    phase1_root: Path,
) -> None:
    if path.exists():
        if file_sha256(path) != expected_hash:
            raise ValueError(f"Immutable artifact mismatch at {path}")
        return
    for candidate in sorted(phase1_root.glob("phase1-market-*/bars.ndjson")):
        if candidate == path:
            continue
        if file_sha256(candidate) == expected_hash:
            os.link(candidate, path)
            return
    with path.open("xb") as output:
        output.write(value)


def _credentials(offline: bool) -> dict[str, str]:
    if offline:
        return {}
    values = {
        "alpacaKey": os.environ.get("APCA_API_KEY_ID", "").strip(),
        "alpacaSecret": os.environ.get("APCA_API_SECRET_KEY", "").strip(),
        "massiveKey": os.environ.get("MASSIVE_API_KEY", "").strip(),
    }
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError(f"Missing Phase 1 credentials: {', '.join(missing)}")
    return values


def _list(payload: dict[str, Any], key: str, provider: str) -> list[dict[str, Any]]:
    if payload.get("status") not in {None, "OK"}:
        raise ValueError(f"{provider} returned status {payload.get('status')}")
    value = payload.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{provider} response field {key} must be a list of objects")
    return value


def _parse_instant(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Timestamp must be text: {value}")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp requires a timezone: {value}")
    return parsed.astimezone(timezone.utc).isoformat()


def _nanoseconds_to_iso(value: object) -> str:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Massive window_start must be integer nanoseconds: {value}")
    seconds, nanoseconds = divmod(value, 1_000_000_000)
    if nanoseconds and nanoseconds % 1000:
        raise ValueError(f"One-minute aggregate timestamp is not microsecond-aligned: {value}")
    return datetime.fromtimestamp(
        seconds + nanoseconds / 1_000_000_000, timezone.utc
    ).isoformat()


def _in_research_session(value: str, plan: Phase1Plan) -> bool:
    local = datetime.fromisoformat(value).astimezone(NY)
    session = plan.dataset["researchSession"]
    start = wall_time.fromisoformat(session["start"])
    end = wall_time.fromisoformat(session["endExclusive"])
    return (
        plan.start_date <= local.date() <= plan.end_date
        and start <= local.timetz().replace(tzinfo=None) < end
    )


def _number(raw: dict[str, Any], key: str) -> float:
    value = raw.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Market bar field {key} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Market bar field {key} must be finite")
    return result


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("Optional market-bar numeric field is invalid")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Optional market-bar numeric field must be finite")
    return result


def _validate_ohlc(
    instrument: str, event_time: str, values: dict[str, float]
) -> None:
    if min(values["open"], values["close"]) < values["low"]:
        raise ValueError(f"Invalid low for {instrument} at {event_time}")
    if max(values["open"], values["close"]) > values["high"]:
        raise ValueError(f"Invalid high for {instrument} at {event_time}")
    if values["volume"] < 0:
        raise ValueError(f"Negative volume for {instrument} at {event_time}")
