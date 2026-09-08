"""Immutable actual-SPY/QQQ daily data acquisition for Cycle 1."""

from __future__ import annotations

import math
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from spy_predictor_quant.cycle1_calendar import xnys_session_close
from spy_predictor_quant.historical_http import ArchivedPage, RequestLimiter, capture_pages
from spy_predictor_quant.market_archive import content_hash


INSTRUMENTS = ("SPY", "QQQ")
ACTION_TYPES = (
    "forward_split", "reverse_split", "cash_dividend", "stock_dividend",
    "capital_gains_distribution",
)
ACTION_GROUP_TYPES = {
    "forward_splits": "forward_split",
    "reverse_splits": "reverse_split",
    "cash_dividends": "cash_dividend",
    "stock_dividends": "stock_dividend",
    "capital_gains_distributions": "capital_gains_distribution",
}


def capture_alpaca_daily(
    *,
    symbol: str,
    start: date,
    as_of: date,
    raw_directory: Path,
    key_id: str,
    secret_key: str,
    offline: bool,
    limiter: RequestLimiter | None = None,
) -> tuple[list[ArchivedPage], list[dict[str, Any]]]:
    _validate_symbol_and_credentials(symbol, key_id, secret_key, offline)
    parameters = {
        "timeframe": "1Day",
        "start": f"{start.isoformat()}T00:00:00Z",
        "end": f"{(as_of + timedelta(days=1)).isoformat()}T00:00:00Z",
        "adjustment": "raw",
        "asof": as_of.isoformat(),
        "feed": "sip",
        "sort": "asc",
        "limit": "10000",
    }
    url = (
        f"https://data.alpaca.markets/v2/stocks/{symbol}/bars?"
        + urllib.parse.urlencode(parameters)
    )
    pages, records = _capture_alpaca_pages(
        provider="alpaca-daily-sip-raw",
        initial_url=url,
        raw_directory=raw_directory,
        key_id=key_id,
        secret_key=secret_key,
        offline=offline,
        limiter=limiter,
        extract=lambda payload: _list(payload, "bars"),
    )
    receipts = _receipts(pages)
    return pages, [
        normalize_alpaca_daily(symbol, raw, receipt)
        for raw, receipt in zip(records, receipts, strict=True)
    ]


def capture_alpaca_actions(
    *,
    symbol: str,
    start: date,
    as_of: date,
    raw_directory: Path,
    key_id: str,
    secret_key: str,
    offline: bool,
    limiter: RequestLimiter | None = None,
) -> tuple[list[ArchivedPage], list[dict[str, Any]]]:
    _validate_symbol_and_credentials(symbol, key_id, secret_key, offline)
    parameters = {
        "symbols": symbol,
        "types": ",".join(ACTION_TYPES),
        "start": start.isoformat(),
        "end": as_of.isoformat(),
        "limit": "1000",
        "sort": "asc",
    }
    url = "https://data.alpaca.markets/v1/corporate-actions?" + urllib.parse.urlencode(parameters)
    pages, records = _capture_alpaca_pages(
        provider="alpaca-corporate-actions",
        initial_url=url,
        raw_directory=raw_directory,
        key_id=key_id,
        secret_key=secret_key,
        offline=offline,
        limiter=limiter,
        extract=_action_records,
    )
    receipts = _receipts(pages)
    return pages, [
        normalize_alpaca_action(symbol, raw, receipt)
        for raw, receipt in zip(records, receipts, strict=True)
    ]


def normalize_alpaca_daily(symbol: str, raw: dict[str, Any], received_at: str) -> dict[str, Any]:
    timestamp = datetime.fromisoformat(str(raw["t"]).replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("Alpaca daily timestamp must be timezone-aware")
    values = {name: _number(raw, key) for name, key in (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"), ("volume", "v"))}
    if values["low"] > min(values["open"], values["close"]) or values["high"] < max(values["open"], values["close"]):
        raise ValueError(f"Invalid daily OHLC for {symbol} {timestamp.date()}")
    session_date = timestamp.date()
    core: dict[str, Any] = {
        "schemaVersion": "cycle1-daily-market-v1",
        "provider": "alpaca-sip",
        "provenanceTier": "RECONSTRUCTED_RESEARCH_ONLY",
        "instrument": symbol,
        "sessionDate": session_date.isoformat(),
        "eventTime": xnys_session_close(session_date).astimezone(timezone.utc).isoformat(),
        **values,
        "tradeCount": int(raw.get("n", 0)),
        "weightedAveragePrice": _optional_number(raw.get("vw")),
        "ingestedAt": received_at,
    }
    return {**core, "hash": content_hash(core)}


def normalize_alpaca_action(symbol: str, raw: dict[str, Any], received_at: str) -> dict[str, Any]:
    returned_symbol = str(raw.get("symbol", raw.get("old_symbol", symbol)))
    if returned_symbol != symbol and str(raw.get("new_symbol", "")) != symbol:
        raise ValueError(f"Corporate action returned an unexpected symbol {returned_symbol}")
    action_type = str(raw.get("ca_type", raw.get("type", raw.get("action_type", "unknown"))))
    action_id = str(raw.get("id", raw.get("corporate_action_id", "")))
    if not action_id:
        action_id = content_hash(raw)
    effective_date = raw.get("ex_date", raw.get("effective_date", raw.get("process_date")))
    if not isinstance(effective_date, str):
        raise ValueError(f"Corporate action {action_id} lacks an effective/ex date")
    date.fromisoformat(effective_date[:10])
    core: dict[str, Any] = {
        "schemaVersion": "cycle1-corporate-action-v1",
        "provider": "alpaca-market-data",
        "provenanceTier": "RECONSTRUCTED_RESEARCH_ONLY",
        "instrument": symbol,
        "actionId": action_id,
        "actionType": action_type,
        "effectiveDate": effective_date[:10],
        "raw": raw,
        "ingestedAt": received_at,
    }
    return {**core, "hash": content_hash(core)}


def _capture_alpaca_pages(*, provider: str, initial_url: str, raw_directory: Path, key_id: str, secret_key: str, offline: bool, limiter: RequestLimiter | None, extract: Any) -> tuple[list[ArchivedPage], list[dict[str, Any]]]:
    def next_page(payload: dict[str, Any], current_url: str) -> str | None:
        token = payload.get("next_page_token")
        if not token:
            return None
        parsed = urllib.parse.urlsplit(current_url)
        query = dict(urllib.parse.parse_qsl(parsed.query))
        query["page_token"] = str(token)
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), ""))

    return capture_pages(
        provider=provider,
        initial_url=initial_url,
        raw_directory=raw_directory,
        headers={"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret_key, "Accept": "application/json"} if not offline else {},
        limiter=limiter or RequestLimiter(180),
        next_url=next_page,
        extract_records=extract,
        allow_network=not offline,
        record_extraction_version=(
            "alpaca-grouped-actions-v2"
            if provider == "alpaca-corporate-actions"
            else "v1"
        ),
    )


def _action_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    direct = payload.get("corporate_actions")
    if isinstance(direct, list):
        return [item for item in direct if isinstance(item, dict)]
    if isinstance(direct, dict):
        records: list[dict[str, Any]] = []
        for group, values in sorted(direct.items()):
            if group not in ACTION_GROUP_TYPES:
                raise ValueError(f"Unknown Alpaca corporate-action group {group}")
            if not isinstance(values, list) or any(
                not isinstance(item, dict) for item in values
            ):
                raise ValueError(
                    f"Alpaca corporate-action group {group} must be a list of objects"
                )
            records.extend(
                {**item, "ca_type": ACTION_GROUP_TYPES[group]} for item in values
            )
        return records
    records: list[dict[str, Any]] = []
    for key, value in payload.items():
        if key == "next_page_token" or not isinstance(value, list):
            continue
        records.extend(item for item in value if isinstance(item, dict))
    return records


def _list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"Alpaca response {key} must be a list of objects")
    return value


def _receipts(pages: list[ArchivedPage]) -> list[str]:
    return [page.received_at for page in pages for _ in range(page.records)]


def _validate_symbol_and_credentials(symbol: str, key: str, secret: str, offline: bool) -> None:
    if symbol not in INSTRUMENTS:
        raise ValueError(f"Unpreregistered instrument {symbol}")
    if not offline and (not key or not secret):
        raise ValueError("Alpaca market-data credentials are required")


def _number(raw: dict[str, Any], key: str) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Alpaca field {key} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Alpaca field {key} must be finite")
    return result


def _optional_number(value: Any) -> float | None:
    return None if value is None else float(value)
