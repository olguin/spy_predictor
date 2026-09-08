"""Immutable read-only IBKR daily-price acquisition for Cycle 1."""

from __future__ import annotations

import json
import math
import os
import threading
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from spy_predictor_quant.cycle1_calendar import is_xnys_session, xnys_session_close
from spy_predictor_quant.historical_http import ArchivedResource
from spy_predictor_quant.ibkr_config import GatewayConfig
from spy_predictor_quant.ibkr_contract_catalog import verify_catalog_hash
from spy_predictor_quant.market_archive import (
    content_hash,
    file_sha256,
    utc_now,
    write_json_exclusive,
)


WHAT_TO_SHOW = ("TRADES", "ADJUSTED_LAST")


@dataclass(frozen=True)
class IbkrCycleCapture:
    resources: list[ArchivedResource]
    daily: dict[str, list[dict[str, Any]]]
    adjusted: dict[str, list[dict[str, Any]]]


def capture_ibkr_cycle_history(
    *,
    catalog_path: Path,
    as_of: date,
    raw_directory: Path,
    offline: bool,
    duration: str = "40 Y",
    timeout_seconds: float = 120,
) -> IbkrCycleCapture:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    verify_catalog_hash(catalog)
    catalog_hash = str(catalog["catalogHash"])
    contracts = _selected_contracts(catalog)
    raw_directory.mkdir(parents=True, exist_ok=True)

    payloads: dict[tuple[str, str], dict[str, Any]] = {}
    missing: list[tuple[str, str]] = []
    for symbol in ("SPY", "QQQ"):
        for kind in WHAT_TO_SHOW:
            path = raw_directory / symbol / f"{kind.lower()}.json"
            if path.exists():
                payloads[(symbol, kind)] = _load_capture(
                    path=path,
                    symbol=symbol,
                    kind=kind,
                    as_of=as_of,
                    duration=duration,
                    catalog_hash=catalog_hash,
                    contract=contracts[symbol],
                )
            else:
                if offline:
                    raise FileNotFoundError(f"Offline run is missing IBKR archive {path}")
                missing.append((symbol, kind))

    if missing:
        payloads.update(
            _capture_missing(
                missing=missing,
                contracts=contracts,
                catalog_hash=catalog_hash,
                as_of=as_of,
                duration=duration,
                timeout_seconds=timeout_seconds,
                raw_directory=raw_directory,
            )
        )

    resources: list[ArchivedResource] = []
    normalized: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for (symbol, kind), payload in sorted(payloads.items()):
        path = raw_directory / symbol / f"{kind.lower()}.json"
        metadata = json.loads(
            path.with_name(path.name + ".meta.json").read_text(encoding="utf-8")
        )
        resources.append(
            ArchivedResource(
                provider="ibkr-historical-data",
                path=path,
                sha256=file_sha256(path),
                received_at=str(payload["receivedAt"]),
                request_url=str(metadata["requestUrl"]),
                records=len(payload["bars"]),
                content_type="application/json",
            )
        )
        normalized[(symbol, kind)] = normalize_ibkr_daily(
            symbol=symbol,
            kind=kind,
            bars=payload["bars"],
            received_at=str(payload["receivedAt"]),
            as_of=as_of,
        )
    return IbkrCycleCapture(
        resources=resources,
        daily={symbol: normalized[(symbol, "TRADES")] for symbol in ("SPY", "QQQ")},
        adjusted={
            symbol: normalized[(symbol, "ADJUSTED_LAST")] for symbol in ("SPY", "QQQ")
        },
    )


def normalize_ibkr_daily(
    *,
    symbol: str,
    kind: str,
    bars: list[dict[str, Any]],
    received_at: str,
    as_of: date,
) -> list[dict[str, Any]]:
    if symbol not in {"SPY", "QQQ"} or kind not in WHAT_TO_SHOW:
        raise ValueError("IBKR Cycle 1 normalization received an unregistered series")
    output: list[dict[str, Any]] = []
    for bar in bars:
        session_date = datetime.strptime(str(bar["date"]), "%Y%m%d").date()
        if session_date > as_of:
            continue
        values = {
            name: _positive_number(bar, name)
            for name in ("open", "high", "low", "close")
        }
        if values["low"] > min(values["open"], values["close"]):
            raise ValueError(f"Invalid IBKR low for {symbol} {session_date}")
        if values["high"] < max(values["open"], values["close"]):
            raise ValueError(f"Invalid IBKR high for {symbol} {session_date}")
        volume = _nonnegative_number(bar, "volume")
        trade_count = int(float(bar.get("tradeCount", 0)))
        if not is_xnys_session(session_date):
            flat_ohlc = len(set(values.values())) == 1
            if volume == 0 and trade_count == 0 and flat_ohlc:
                # IBKR can emit a carry-forward daily placeholder on a closed
                # exchange date. Preserve it in the immutable raw response but
                # never admit it as an XNYS session.
                continue
            raise ValueError(
                f"IBKR {symbol} {kind} has activity on non-session {session_date}"
            )
        core: dict[str, Any] = {
            "schemaVersion": "cycle1-daily-market-v1",
            "provider": (
                "ibkr-trades-split-adjusted"
                if kind == "TRADES"
                else "ibkr-adjusted-last-diagnostic"
            ),
            "provenanceTier": "RECONSTRUCTED_RESEARCH_ONLY",
            "instrument": symbol,
            "sessionDate": session_date.isoformat(),
            "eventTime": xnys_session_close(session_date).isoformat(),
            **values,
            "volume": volume,
            "tradeCount": trade_count,
            "weightedAveragePrice": _optional_number(bar.get("weightedAveragePrice")),
            "ingestedAt": received_at,
        }
        output.append({**core, "hash": content_hash(core)})
    dates = [row["sessionDate"] for row in output]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise ValueError(f"IBKR {symbol} {kind} daily sessions are not unique and ordered")
    if not output:
        raise ValueError(f"IBKR {symbol} {kind} returned no rows through {as_of}")
    return output


def implied_distribution_diagnostics(
    trades: list[dict[str, Any]], adjusted: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Infer rounded cash events for source reconciliation, never target input."""
    trade_by_date = {row["sessionDate"]: row for row in trades}
    adjusted_by_date = {row["sessionDate"]: row for row in adjusted}
    dates = sorted(set(trade_by_date) & set(adjusted_by_date))
    output: list[dict[str, Any]] = []
    for previous, current in zip(dates, dates[1:], strict=False):
        previous_trade = float(trade_by_date[previous]["close"])
        current_trade = float(trade_by_date[current]["close"])
        adjusted_growth = (
            float(adjusted_by_date[current]["close"])
            / float(adjusted_by_date[previous]["close"])
        )
        cash = previous_trade * adjusted_growth - current_trade
        if cash < -0.0001:
            raise ValueError(f"IBKR adjusted reconciliation is negative on {current}")
        if cash > 0.0001:
            output.append(
                {
                    "sessionDate": current,
                    "impliedCash": cash,
                    "diagnosticOnly": True,
                }
            )
    return output


def _capture_missing(
    *,
    missing: list[tuple[str, str]],
    contracts: dict[str, dict[str, object]],
    catalog_hash: str,
    as_of: date,
    duration: str,
    timeout_seconds: float,
    raw_directory: Path,
) -> dict[tuple[str, str], dict[str, Any]]:
    # Keep the optional vendor SDK out of import-time paths used by offline tests.
    from spy_predictor_quant.ibkr_history import _ibkr_end_time, _make_exact_contract
    from spy_predictor_quant.ibkr_session import IbkrSession

    class Client(IbkrSession):
        def __init__(self, config: GatewayConfig) -> None:
            super().__init__(config)
            self.contexts: dict[int, tuple[str, str]] = {}
            self.bars: dict[int, list[dict[str, str | int]]] = {}
            self.response_bounds: dict[int, tuple[str, str]] = {}
            self.lock = threading.Lock()

        def register(self, request_id: int, symbol: str, kind: str) -> None:
            self.contexts[request_id] = (symbol, kind)
            self.bars[request_id] = []

        def historicalData(self, reqId: int, bar: object) -> None:  # noqa: N802
            value: dict[str, str | int] = {
                "date": str(getattr(bar, "date")),
                "open": repr(float(getattr(bar, "open"))),
                "high": repr(float(getattr(bar, "high"))),
                "low": repr(float(getattr(bar, "low"))),
                "close": repr(float(getattr(bar, "close"))),
                "volume": str(getattr(bar, "volume")),
                "weightedAveragePrice": str(getattr(bar, "wap")),
                "tradeCount": int(getattr(bar, "barCount")),
            }
            with self.lock:
                self.bars[reqId].append(value)

        def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:  # noqa: N802
            self.response_bounds[reqId] = (start, end)
            self.complete_request(reqId)

    base = GatewayConfig.from_environment(os.environ)
    config = replace(base, client_id=base.client_id + 2)
    captured: dict[tuple[str, str], dict[str, Any]] = {}
    as_of_time = datetime.combine(as_of, time(23, 59, 59), timezone.utc)
    with Client(config) as client:
        for symbol, kind in missing:
            request_id = client.begin_request()
            client.register(request_id, symbol, kind)
            requested_end = "" if kind == "ADJUSTED_LAST" else _ibkr_end_time(as_of_time)
            client.reqHistoricalData(
                request_id,
                _make_exact_contract(contracts[symbol]),
                requested_end,
                duration,
                "1 day",
                kind,
                1,
                1,
                False,
                [],
            )
            client.wait_for_request(
                request_id,
                f"Cycle 1 {symbol} {kind} immutable history",
                timeout_seconds,
            )
            bars = list(client.bars[request_id])
            if not bars:
                raise ValueError(f"IBKR returned no {symbol} {kind} history")
            response_start, response_end = client.response_bounds[request_id]
            payload = {
                "schemaVersion": "cycle1-ibkr-daily-history-v1",
                "provider": "ibkr-historical-data",
                "instrument": symbol,
                "whatToShow": kind,
                "asOfDate": as_of.isoformat(),
                "requestedEnd": requested_end,
                "duration": duration,
                "barSize": "1 day",
                "useRegularTradingHours": True,
                "formatDate": 1,
                "catalogHash": catalog_hash,
                "contract": contracts[symbol],
                "responseStart": response_start,
                "responseEnd": response_end,
                "receivedAt": utc_now(),
                "bars": bars,
            }
            path = raw_directory / symbol / f"{kind.lower()}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            digest = write_json_exclusive(path, payload)
            write_json_exclusive(
                path.with_name(path.name + ".meta.json"),
                {
                    "schemaVersion": "archived-ibkr-resource-v1",
                    "provider": "ibkr-historical-data",
                    "requestUrl": _request_identity(
                        symbol, kind, as_of, duration, catalog_hash
                    ),
                    "receivedAt": payload["receivedAt"],
                    "records": len(bars),
                    "contentType": "application/json",
                    "sha256": digest,
                },
            )
            captured[(symbol, kind)] = payload
    return captured


def _load_capture(
    *,
    path: Path,
    symbol: str,
    kind: str,
    as_of: date,
    duration: str,
    catalog_hash: str,
    contract: dict[str, object],
) -> dict[str, Any]:
    metadata_path = path.with_name(path.name + ".meta.json")
    if not metadata_path.exists():
        raise ValueError(f"IBKR immutable metadata is missing for {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected = {
        "instrument": symbol,
        "whatToShow": kind,
        "asOfDate": as_of.isoformat(),
        "duration": duration,
        "catalogHash": catalog_hash,
        "contract": contract,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError(f"IBKR archive {key} mismatch for {path}")
    if metadata.get("schemaVersion") != "archived-ibkr-resource-v1":
        raise ValueError(f"Invalid IBKR archive metadata for {path}")
    if metadata.get("requestUrl") != _request_identity(
        symbol, kind, as_of, duration, catalog_hash
    ):
        raise ValueError(f"IBKR archive request identity mismatch for {path}")
    if metadata.get("sha256") != file_sha256(path):
        raise ValueError(f"IBKR archive hash mismatch for {path}")
    bars = payload.get("bars")
    if not isinstance(bars, list) or metadata.get("records") != len(bars):
        raise ValueError(f"IBKR archive record count mismatch for {path}")
    return payload


def _selected_contracts(catalog: dict[str, Any]) -> dict[str, dict[str, object]]:
    contracts = catalog.get("contracts")
    if not isinstance(contracts, dict):
        raise ValueError("IBKR catalog is missing contracts")
    selected: dict[str, dict[str, object]] = {}
    for symbol in ("SPY", "QQQ"):
        matches = contracts.get(symbol)
        if not isinstance(matches, list) or len(matches) != 1:
            raise ValueError(f"IBKR catalog must contain one exact {symbol} contract")
        selected[symbol] = matches[0]
    return selected


def _request_identity(
    symbol: str, kind: str, as_of: date, duration: str, catalog_hash: str
) -> str:
    return "ibkr://historical?" + urlencode(
        {
            "instrument": symbol,
            "whatToShow": kind,
            "asOfDate": as_of.isoformat(),
            "duration": duration,
            "barSize": "1 day",
            "useRth": "1",
            "formatDate": "1",
            "catalogHash": catalog_hash,
        }
    )


def _positive_number(row: dict[str, Any], key: str) -> float:
    value = _number(row, key)
    if value <= 0:
        raise ValueError(f"IBKR {key} must be positive")
    return value


def _nonnegative_number(row: dict[str, Any], key: str) -> float:
    value = _number(row, key)
    if value < 0:
        raise ValueError(f"IBKR {key} must be nonnegative")
    return value


def _number(row: dict[str, Any], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"IBKR {key} must be numeric") from error
    if not math.isfinite(value):
        raise ValueError(f"IBKR {key} must be finite")
    return value


def _optional_number(value: Any) -> float | None:
    if value is None or str(value) in {"", "nan", "NaN"}:
        return None
    result = float(value)
    return result if math.isfinite(result) else None
