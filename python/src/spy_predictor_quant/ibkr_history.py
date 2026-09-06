"""Recent one-minute history downloader for exact IBKR contracts."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import ibapi
from ibapi.contract import Contract

from spy_predictor_quant.ibkr_config import GatewayConfig
from spy_predictor_quant.ibkr_history_config import (
    HistoryPlan,
    find_latest_catalog,
    is_transient_history_error,
    load_history_plan,
    select_catalog_contracts,
    trading_weekday_endpoints,
)
from spy_predictor_quant.ibkr_history_normalize import normalize_historical_events
from spy_predictor_quant.ibkr_session import IbkrRequestError, IbkrSession
from spy_predictor_quant.market_archive import (
    NdjsonWriter,
    create_immutable_run_directory,
    read_ndjson,
    utc_now,
    write_json_exclusive,
    write_ndjson_exclusive,
)
from spy_predictor_quant.request_pacing import PacingController


class HistoricalDataClient(IbkrSession):
    def __init__(
        self,
        config: GatewayConfig,
        raw_writer: NdjsonWriter,
    ) -> None:
        super().__init__(config)
        self.raw_writer = raw_writer
        self._contexts: dict[int, dict[str, object]] = {}
        self._events: list[dict[str, Any]] = []
        self._event_lock = threading.Lock()

    @property
    def events(self) -> list[dict[str, Any]]:
        with self._event_lock:
            return list(self._events)

    def register_context(self, request_id: int, context: dict[str, object]) -> None:
        self._contexts[request_id] = context

    def historicalData(self, reqId: int, bar: object) -> None:  # noqa: N802
        context = self._contexts[reqId]
        event: dict[str, Any] = {
            "schemaVersion": "ibkr-raw-callback-v1",
            "type": "historicalBar",
            "requestId": reqId,
            "receivedAt": utc_now(),
            **context,
            "bar": {
                "date": str(getattr(bar, "date")),
                "open": repr(float(getattr(bar, "open"))),
                "high": repr(float(getattr(bar, "high"))),
                "low": repr(float(getattr(bar, "low"))),
                "close": repr(float(getattr(bar, "close"))),
                "volume": str(getattr(bar, "volume")),
                "weightedAveragePrice": str(getattr(bar, "wap")),
                "tradeCount": int(getattr(bar, "barCount")),
            },
        }
        self.raw_writer.write(event)
        with self._event_lock:
            self._events.append(event)

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:  # noqa: N802
        context = self._contexts.get(reqId, {})
        self.raw_writer.write(
            {
                "schemaVersion": "ibkr-raw-callback-v1",
                "type": "historicalDataEnd",
                "requestId": reqId,
                "receivedAt": utc_now(),
                **context,
                "responseStart": start,
                "responseEnd": end,
            }
        )
        self.complete_request(reqId)

    def error(  # noqa: N802 - IBKR callback
        self,
        reqId: int,
        errorTime: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        self.raw_writer.write(
            {
                "schemaVersion": "ibkr-raw-callback-v1",
                "type": "apiEvent",
                "requestId": reqId,
                "receivedAt": utc_now(),
                "code": errorCode,
                "message": errorString,
                **self._contexts.get(reqId, {}),
            }
        )
        super().error(
            reqId,
            errorTime,
            errorCode,
            errorString,
            advancedOrderRejectJson,
        )


def _make_exact_contract(record: dict[str, object]) -> Contract:
    contract = Contract()
    contract.conId = int(record["conId"])
    contract.symbol = str(record["symbol"])
    contract.secType = str(record["securityType"])
    contract.exchange = str(record["exchange"])
    contract.primaryExchange = str(record.get("primaryExchange", ""))
    contract.currency = str(record["currency"])
    contract.localSymbol = str(record["localSymbol"])
    contract.tradingClass = str(record.get("tradingClass", ""))
    contract.lastTradeDateOrContractMonth = str(record.get("expiration", ""))
    contract.multiplier = str(record.get("multiplier", ""))
    contract.includeExpired = False
    return contract


def _ibkr_end_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%d %H:%M:%S UTC")


def _download_request(
    client: HistoricalDataClient,
    plan: HistoryPlan,
    instrument: str,
    record: dict[str, object],
    end: datetime,
    chunk_index: int,
    pacing: PacingController,
) -> dict[str, object] | None:
    settings = plan.settings
    last_errors: list[dict[str, object]] = []
    for attempt in range(settings.max_retries + 1):
        pacing.wait()
        request_id = client.begin_request()
        context: dict[str, object] = {
            "instrument": instrument,
            "conId": int(record["conId"]),
            "localSymbol": str(record["localSymbol"]),
            "chunkIndex": chunk_index,
            "attempt": attempt,
            "requestedEnd": end.isoformat(),
            "duration": settings.chunk_duration,
            "barSize": settings.bar_size,
            "whatToShow": settings.what_to_show,
            "useRegularTradingHours": settings.use_regular_trading_hours,
        }
        client.register_context(request_id, context)
        client.raw_writer.write(
            {
                "schemaVersion": "ibkr-raw-callback-v1",
                "type": "historicalRequest",
                "requestId": request_id,
                "sentAt": utc_now(),
                **context,
            }
        )
        client.reqHistoricalData(
            request_id,
            _make_exact_contract(record),
            _ibkr_end_time(end),
            settings.chunk_duration,
            settings.bar_size,
            settings.what_to_show,
            int(settings.use_regular_trading_hours),
            settings.format_date,
            False,
            [],
        )
        try:
            client.wait_for_request(
                request_id,
                f"historical bars for {instrument} chunk {chunk_index}",
                settings.request_timeout_seconds,
            )
            return None
        except IbkrRequestError as error:
            last_errors = error.errors
            if (
                not is_transient_history_error(error.errors)
                or attempt >= settings.max_retries
            ):
                break
            time.sleep(settings.retry_base_seconds * (2**attempt))
        except TimeoutError:
            last_errors = [
                {
                    "requestId": request_id,
                    "code": "TIMEOUT",
                    "message": "Historical data request timed out",
                }
            ]
            if attempt >= settings.max_retries:
                break
            time.sleep(settings.retry_base_seconds * (2**attempt))
    return {
        "instrument": instrument,
        "conId": int(record["conId"]),
        "localSymbol": str(record["localSymbol"]),
        "chunkIndex": chunk_index,
        "requestedEnd": end.isoformat(),
        "errors": last_errors,
    }


def run_history_download(
    *,
    plan_path: Path,
    catalog_path: Path,
    output_root: Path,
    end: datetime,
    chunk_override: int | None = None,
) -> dict[str, Any]:
    plan = load_history_plan(plan_path, chunk_override)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    contracts = select_catalog_contracts(catalog, plan)
    run_directory = create_immutable_run_directory(output_root, "history")
    raw_writer = NdjsonWriter(run_directory / "raw-callbacks.ndjson")
    started_at = utc_now()
    failed_chunks: list[dict[str, object]] = []
    client = HistoricalDataClient(
        GatewayConfig.from_environment(os.environ),
        raw_writer,
    )
    fatal_error: str | None = None
    gateway_connection_time: str | None = None
    server_version: int | None = None
    try:
        client.connect_and_start(plan.settings.request_timeout_seconds)
        server_version = client.serverVersion()
        connection_time = client.twsConnectionTime()
        if isinstance(connection_time, bytes):
            connection_time = connection_time.decode("utf-8", errors="replace")
        gateway_connection_time = str(connection_time)
        pacing = PacingController(
            plan.settings.minimum_request_spacing_seconds,
            plan.settings.maximum_requests_per_window,
            plan.settings.pacing_window_seconds,
        )
        endpoints = trading_weekday_endpoints(end, plan.settings.chunk_count)
        for instrument, contract in contracts.items():
            for chunk_index, endpoint in enumerate(endpoints):
                failure = _download_request(
                    client,
                    plan,
                    instrument,
                    contract,
                    endpoint,
                    chunk_index,
                    pacing,
                )
                if failure is not None:
                    failed_chunks.append(failure)
    except Exception as error:
        fatal_error = str(error)
    finally:
        client.close()
        raw_writer.close()

    raw_events = read_ndjson(raw_writer.path)
    try:
        normalized_records, quality = normalize_historical_events(
            raw_events,
            contracts,
            plan.settings,
        )
    except Exception as error:
        fatal_error = fatal_error or f"Normalization failed: {error}"
        normalized_records = []
        quality = {
            instrument: {"bars": 0, "normalizationError": str(error)}
            for instrument in contracts
        }
    for instrument, instrument_quality in quality.items():
        delayed_notices = [
            event
            for event in raw_events
            if event.get("type") == "apiEvent"
            and event.get("instrument") == instrument
            and event.get("code") == 2188
        ]
        instrument_quality["freshness"] = (
            "delayed" if delayed_notices else "as-requested"
        )
        instrument_quality["freshnessNotices"] = delayed_notices
    normalized_count, normalized_hash = write_ndjson_exclusive(
        run_directory / "bars.ndjson",
        normalized_records,
    )
    status = "ok"
    if fatal_error is not None:
        status = "error"
    elif failed_chunks:
        status = "partial"
    manifest: dict[str, Any] = {
        "schemaVersion": "ibkr-history-manifest-v1",
        "status": status,
        "startedAt": started_at,
        "completedAt": utc_now(),
        "mode": "paper",
        "ibapiVersion": ibapi.__version__,
        "serverVersion": server_version,
        "gatewayConnectionTime": gateway_connection_time,
        "catalogPath": str(catalog_path),
        "catalogHash": catalog.get("catalogHash"),
        "plan": {
            "schemaVersion": plan.schema_version,
            "settings": {
                "barSize": plan.settings.bar_size,
                "whatToShow": plan.settings.what_to_show,
                "useRegularTradingHours": plan.settings.use_regular_trading_hours,
                "formatDate": plan.settings.format_date,
                "chunkDuration": plan.settings.chunk_duration,
                "chunkCount": plan.settings.chunk_count,
                "endLagMinutes": plan.settings.end_lag_minutes,
            },
        },
        "contracts": contracts,
        "rawCallbacks": {
            "path": str(raw_writer.path),
            "records": raw_writer.count,
            "sha256": raw_writer.sha256,
        },
        "normalizedBars": {
            "path": str(run_directory / "bars.ndjson"),
            "records": normalized_count,
            "sha256": normalized_hash,
            "provenanceClass": "event-time-only",
        },
        "quality": quality,
        "failedChunks": failed_chunks,
        "fatalError": fatal_error,
        "informationalEvents": client.warnings,
    }
    manifest_path = run_directory / "manifest.json"
    write_json_exclusive(manifest_path, manifest)
    return {**manifest, "manifestPath": str(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("config/ibkr-history.json"),
    )
    parser.add_argument("--catalog", type=Path)
    parser.add_argument(
        "--catalog-root",
        type=Path,
        default=Path("datasets/ibkr/contracts"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("datasets/ibkr/history"),
    )
    parser.add_argument("--end")
    parser.add_argument("--chunks", type=int)
    args = parser.parse_args()

    try:
        catalog_path = args.catalog or find_latest_catalog(args.catalog_root)
        plan = load_history_plan(args.plan, args.chunks)
        end = (
            datetime.fromisoformat(args.end)
            if args.end
            else datetime.now(timezone.utc)
            - timedelta(minutes=plan.settings.end_lag_minutes)
        )
        if end.tzinfo is None:
            raise ValueError("--end must contain an explicit timezone")
        result = run_history_download(
            plan_path=args.plan,
            catalog_path=catalog_path,
            output_root=args.output_root,
            end=end,
            chunk_override=args.chunks,
        )
    except Exception as error:
        print(
            json.dumps({"status": "error", "message": str(error)}, indent=2),
            file=sys.stderr,
        )
        return 1

    compact_quality = {
        instrument: {
            "bars": instrument_quality["bars"],
            "firstTimestamp": instrument_quality.get("firstTimestamp"),
            "lastTimestamp": instrument_quality.get("lastTimestamp"),
            "exactDuplicateBarsRemoved": instrument_quality.get(
                "exactDuplicateBarsRemoved", 0
            ),
            "intradayGapCandidateCount": instrument_quality.get(
                "intradayGapCandidateCount", 0
            ),
            "freshness": instrument_quality.get("freshness"),
            "freshnessNoticeCodes": sorted(
                {
                    int(notice["code"])
                    for notice in instrument_quality.get("freshnessNotices", [])
                }
            ),
        }
        for instrument, instrument_quality in result["quality"].items()
    }
    summary = {
        "status": result["status"],
        "manifestPath": result["manifestPath"],
        "catalogHash": result["catalogHash"],
        "normalizedBars": result["normalizedBars"],
        "quality": compact_quality,
        "failedChunks": result["failedChunks"],
        "fatalError": result["fatalError"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
