"""Locally timestamped, reconnecting IBKR five-second bar capture."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

import ibapi

from spy_predictor_quant.ibkr_config import GatewayConfig
from spy_predictor_quant.ibkr_history import _make_exact_contract
from spy_predictor_quant.ibkr_history_config import (
    find_latest_catalog,
    select_contract_records,
)
from spy_predictor_quant.ibkr_live_aggregate import (
    LiveCaptureState,
    aggregate_realtime_events,
)
from spy_predictor_quant.ibkr_live_config import LiveCapturePlan, load_live_capture_plan
from spy_predictor_quant.ibkr_session import INFORMATIONAL_CODES, IbkrSession
from spy_predictor_quant.market_archive import (
    LiveSessionArchiveWriter,
    create_immutable_run_directory,
    utc_now,
    write_json_exclusive,
    write_ndjson_exclusive,
)


class LiveDataClient(IbkrSession):
    def __init__(
        self,
        config: GatewayConfig,
        state: LiveCaptureState,
        connection_attempt: int,
    ) -> None:
        super().__init__(config)
        self.state = state
        self.connection_attempt = connection_attempt
        self.contexts: dict[int, dict[str, object]] = {}
        self.subscription_ids: list[int] = []

    def subscribe(
        self,
        plan: LiveCapturePlan,
        contracts: dict[str, dict[str, object]],
    ) -> None:
        for instrument, contract in contracts.items():
            request_id = self.begin_request()
            context = {
                "instrument": instrument,
                "conId": int(contract["conId"]),
                "localSymbol": str(contract["localSymbol"]),
                "connectionAttempt": self.connection_attempt,
            }
            self.contexts[request_id] = context
            self.subscription_ids.append(request_id)
            self.state.raw_writer.write(
                {
                    "schemaVersion": "ibkr-raw-callback-v1",
                    "type": "realtimeBarSubscription",
                    "requestId": request_id,
                    "sentAt": utc_now(),
                    **context,
                    "barSizeSeconds": plan.settings.bar_size_seconds,
                    "whatToShow": plan.settings.what_to_show,
                    "useRegularTradingHours": plan.settings.use_regular_trading_hours,
                }
            )
            self.reqRealTimeBars(
                request_id,
                _make_exact_contract(contract),
                plan.settings.bar_size_seconds,
                plan.settings.what_to_show,
                plan.settings.use_regular_trading_hours,
                [],
            )

    def realtimeBar(  # noqa: N802 - IBKR callback
        self,
        reqId: int,
        time: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: object,
        wap: object,
        count: int,
    ) -> None:
        received_at = utc_now()
        context = self.contexts[reqId]
        self.state.record_bar(
            {
                "schemaVersion": "ibkr-raw-callback-v1",
                "type": "realtimeBar",
                "requestId": reqId,
                "receivedAt": received_at,
                **context,
                "bar": {
                    "time": int(time),
                    "open": repr(float(open_)),
                    "high": repr(float(high)),
                    "low": repr(float(low)),
                    "close": repr(float(close)),
                    "volume": str(volume),
                    "weightedAveragePrice": str(wap),
                    "tradeCount": int(count),
                },
            }
        )

    def error(  # noqa: N802 - IBKR callback
        self,
        reqId: int,
        errorTime: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        self.state.record_api_event(
            {
                "schemaVersion": "ibkr-raw-callback-v1",
                "type": "apiEvent",
                "requestId": reqId,
                "receivedAt": utc_now(),
                "code": errorCode,
                "message": errorString,
                "connectionAttempt": self.connection_attempt,
                **self.contexts.get(reqId, {}),
            }
        )
        super().error(
            reqId,
            errorTime,
            errorCode,
            errorString,
            advancedOrderRejectJson,
        )

    def cancel_subscriptions(self) -> None:
        if self.isConnected():
            for request_id in self.subscription_ids:
                self.state.raw_writer.write(
                    {
                        "schemaVersion": "ibkr-raw-callback-v1",
                        "type": "realtimeBarCancellation",
                        "requestId": request_id,
                        "sentAt": utc_now(),
                        "connectionAttempt": self.connection_attempt,
                        **self.contexts[request_id],
                    }
                )
                self.cancelRealTimeBars(request_id)
        for request_id in self.subscription_ids:
            self.discard_request(request_id)


def _wait_for_capture(
    client: LiveDataClient,
    state: LiveCaptureState,
    deadline: float | None,
) -> str:
    while not state.stop_requested.is_set():
        if client.closed.is_set():
            return "disconnected"
        rejected_ids = {
            int(event["requestId"])
            for event in state.api_events
            if int(event.get("requestId", -1)) in client.subscription_ids
            and int(event.get("connectionAttempt", -1))
            == client.connection_attempt
            and int(event.get("code", 0)) not in INFORMATIONAL_CODES
        }
        if client.subscription_ids and rejected_ids == set(client.subscription_ids):
            return "subscriptions-rejected"
        if deadline is not None and time.monotonic() >= deadline:
            return "duration-complete"
        state.stop_requested.wait(0.25)
    return "stop-requested"


def run_live_capture(
    *,
    plan_path: Path,
    catalog_path: Path,
    output_root: Path,
    duration_override: float | None = None,
) -> dict[str, Any]:
    plan = load_live_capture_plan(plan_path, duration_override)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    contracts = select_contract_records(catalog, plan.selections)
    run_directory = create_immutable_run_directory(output_root, "live")
    raw_writer = LiveSessionArchiveWriter(run_directory)
    state = LiveCaptureState(raw_writer)
    started_at = utc_now()
    deadline = (
        time.monotonic() + plan.settings.duration_seconds
        if plan.settings.duration_seconds > 0
        else None
    )
    connection_attempts: list[dict[str, object]] = []
    fatal_error: str | None = None
    server_version: int | None = None
    gateway_connection_time: str | None = None

    previous_handlers: dict[int, Any] = {}

    def request_stop(signum: int, frame: object) -> None:
        state.stop_requested.set()

    for signal_number in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signal_number] = signal.getsignal(signal_number)
        signal.signal(signal_number, request_stop)

    try:
        for attempt in range(plan.settings.maximum_reconnect_attempts + 1):
            if state.stop_requested.is_set():
                break
            if deadline is not None and time.monotonic() >= deadline:
                break
            client = LiveDataClient(
                GatewayConfig.from_environment(os.environ),
                state,
                attempt,
            )
            attempt_record: dict[str, object] = {
                "attempt": attempt,
                "startedAt": utc_now(),
            }
            connection_attempts.append(attempt_record)
            try:
                client.connect_and_start(plan.settings.connection_timeout_seconds)
                server_version = client.serverVersion()
                connection_time = client.twsConnectionTime()
                if isinstance(connection_time, bytes):
                    connection_time = connection_time.decode(
                        "utf-8", errors="replace"
                    )
                gateway_connection_time = str(connection_time)
                client.subscribe(plan, contracts)
                reason = _wait_for_capture(client, state, deadline)
                attempt_record["endReason"] = reason
                attempt_record["completedAt"] = utc_now()
                client.cancel_subscriptions()
            except Exception as error:
                attempt_record["endReason"] = "error"
                attempt_record["error"] = str(error)
                attempt_record["completedAt"] = utc_now()
                reason = "disconnected"
            finally:
                client.close()

            if reason != "disconnected" or state.stop_requested.is_set():
                break
            if attempt >= plan.settings.maximum_reconnect_attempts:
                fatal_error = "IB Gateway disconnected and reconnect attempts were exhausted"
                break
            state.raw_writer.write(
                {
                    "schemaVersion": "ibkr-raw-callback-v1",
                    "type": "reconnectScheduled",
                    "receivedAt": utc_now(),
                    "afterAttempt": attempt,
                    "delaySeconds": plan.settings.reconnect_delay_seconds,
                }
            )
            state.stop_requested.wait(plan.settings.reconnect_delay_seconds)
    except Exception as error:
        fatal_error = str(error)
    finally:
        for signal_number, handler in previous_handlers.items():
            signal.signal(signal_number, handler)
        raw_writer.close()

    try:
        normalized_records, quality = aggregate_realtime_events(
            state.events,
            contracts,
        )
    except Exception as error:
        fatal_error = fatal_error or f"Aggregation failed: {error}"
        normalized_records = []
        quality = {
            instrument: {
                "fiveSecondBars": 0,
                "oneMinuteBars": 0,
                "aggregationError": str(error),
            }
            for instrument in contracts
        }
    for instrument, instrument_quality in quality.items():
        instrument_quality["duplicatesSuppressedAcrossReconnects"] = state.duplicates[
            instrument
        ]
        instrument_quality["apiErrors"] = [
            event
            for event in state.api_events
            if event.get("requestId", -1) >= 0
            and event.get("instrument") == instrument
        ]

    normalized_count, normalized_hash = write_ndjson_exclusive(
        run_directory / "bars.ndjson",
        normalized_records,
    )
    instruments_with_bars = sum(
        1 for value in quality.values() if int(value["fiveSecondBars"]) > 0
    )
    request_errors = [
        event
        for event in state.api_events
        if int(event.get("requestId", -1)) >= 0
    ]
    if fatal_error or state.callback_errors:
        status = "error"
    elif request_errors or 0 < instruments_with_bars < len(contracts):
        status = "partial"
    elif instruments_with_bars == 0:
        status = "no-data"
    else:
        status = "ok"

    manifest: dict[str, Any] = {
        "schemaVersion": "ibkr-live-capture-manifest-v1",
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
            "barSizeSeconds": plan.settings.bar_size_seconds,
            "whatToShow": plan.settings.what_to_show,
            "useRegularTradingHours": plan.settings.use_regular_trading_hours,
            "durationSeconds": plan.settings.duration_seconds,
            "maximumReconnectAttempts": plan.settings.maximum_reconnect_attempts,
        },
        "contracts": contracts,
        "connectionAttempts": connection_attempts,
        "rawCallbacks": {
            "records": raw_writer.count,
            "sha256": raw_writer.sha256,
            "files": raw_writer.file_manifest(),
        },
        "normalizedBars": {
            "path": str(run_directory / "bars.ndjson"),
            "records": normalized_count,
            "sha256": normalized_hash,
            "provenanceClass": "locally-first-seen",
        },
        "quality": quality,
        "apiEvents": state.api_events,
        "callbackErrors": state.callback_errors,
        "fatalError": fatal_error,
    }
    manifest_path = run_directory / "manifest.json"
    write_json_exclusive(manifest_path, manifest)
    return {**manifest, "manifestPath": str(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("config/ibkr-live.json"),
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
        default=Path("datasets/ibkr/live"),
    )
    parser.add_argument("--duration-seconds", type=float)
    args = parser.parse_args()

    try:
        catalog_path = args.catalog or find_latest_catalog(args.catalog_root)
        result = run_live_capture(
            plan_path=args.plan,
            catalog_path=catalog_path,
            output_root=args.output_root,
            duration_override=args.duration_seconds,
        )
    except Exception as error:
        print(
            json.dumps({"status": "error", "message": str(error)}, indent=2),
            file=sys.stderr,
        )
        return 1

    compact_quality = {
        instrument: {
            "fiveSecondBars": instrument_quality["fiveSecondBars"],
            "oneMinuteBars": instrument_quality["oneMinuteBars"],
            "completeOneMinuteBars": instrument_quality.get(
                "completeOneMinuteBars", 0
            ),
            "partialOneMinuteBars": instrument_quality.get(
                "partialOneMinuteBars", 0
            ),
            "duplicatesSuppressedAcrossReconnects": instrument_quality.get(
                "duplicatesSuppressedAcrossReconnects", 0
            ),
            "apiErrorCodes": sorted(
                {
                    int(event["code"])
                    for event in instrument_quality.get("apiErrors", [])
                }
            ),
            "apiErrorMessages": sorted(
                {
                    str(event["message"])
                    for event in instrument_quality.get("apiErrors", [])
                }
            ),
        }
        for instrument, instrument_quality in result["quality"].items()
    }
    print(
        json.dumps(
            {
                "status": result["status"],
                "manifestPath": result["manifestPath"],
                "normalizedBars": result["normalizedBars"],
                "quality": compact_quality,
                "connectionAttempts": result["connectionAttempts"],
                "fatalError": result["fatalError"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result["status"] in {"ok", "no-data"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
