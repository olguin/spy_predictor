"""Bounded, read-only delayed quote capture through IB Gateway."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import ibapi

from spy_predictor_quant.ibkr_config import GatewayConfig
from spy_predictor_quant.ibkr_history import _make_exact_contract
from spy_predictor_quant.ibkr_history_config import (
    find_latest_catalog,
    select_contract_records,
)
from spy_predictor_quant.ibkr_live_config import load_live_capture_plan
from spy_predictor_quant.ibkr_session import IbkrSession
from spy_predictor_quant.market_archive import (
    NdjsonWriter,
    create_immutable_run_directory,
    utc_now,
    write_json_exclusive,
)


DELAYED_MARKET_DATA_TYPE = 3
DELAYED_INFORMATIONAL_CODES = {10167, 2119}
TICK_NAMES = {
    37: "MARK_PRICE",
    66: "DELAYED_BID",
    67: "DELAYED_ASK",
    68: "DELAYED_LAST",
    69: "DELAYED_BID_SIZE",
    70: "DELAYED_ASK_SIZE",
    71: "DELAYED_LAST_SIZE",
    72: "DELAYED_HIGH",
    73: "DELAYED_LOW",
    74: "DELAYED_VOLUME",
    75: "DELAYED_CLOSE",
    76: "DELAYED_OPEN",
    88: "DELAYED_LAST_TIMESTAMP",
}


class DelayedQuoteClient(IbkrSession):
    def __init__(self, config: GatewayConfig, raw_writer: NdjsonWriter) -> None:
        super().__init__(config)
        self.raw_writer = raw_writer
        self.contexts: dict[int, dict[str, object]] = {}
        self.events: list[dict[str, object]] = []
        self.event_lock = threading.Lock()

    def subscribe(self, contracts: dict[str, dict[str, object]]) -> list[int]:
        self.reqMarketDataType(DELAYED_MARKET_DATA_TYPE)
        request_ids: list[int] = []
        for instrument, contract in contracts.items():
            request_id = self.begin_request()
            context = {
                "instrument": instrument,
                "conId": int(contract["conId"]),
                "localSymbol": str(contract["localSymbol"]),
            }
            self.contexts[request_id] = context
            request_ids.append(request_id)
            self.raw_writer.write(
                {
                    "schemaVersion": "ibkr-delayed-callback-v1",
                    "type": "marketDataRequest",
                    "requestId": request_id,
                    "sentAt": utc_now(),
                    "requestedMarketDataType": DELAYED_MARKET_DATA_TYPE,
                    "genericTicks": "232",
                    **context,
                }
            )
            self.reqMktData(
                request_id,
                _make_exact_contract(contract),
                "232",
                False,
                False,
                [],
            )
        return request_ids

    def _record(self, event: dict[str, object]) -> None:
        self.raw_writer.write(event)
        with self.event_lock:
            self.events.append(event)

    def marketDataType(self, reqId: int, marketDataType: int) -> None:  # noqa: N802
        self._record(
            {
                "schemaVersion": "ibkr-delayed-callback-v1",
                "type": "marketDataType",
                "requestId": reqId,
                "receivedAt": utc_now(),
                "marketDataType": marketDataType,
                **self.contexts.get(reqId, {}),
            }
        )

    def tickPrice(  # noqa: N802
        self, reqId: int, tickType: int, price: float, attrib: object
    ) -> None:
        self._record_tick(reqId, tickType, repr(float(price)))

    def tickSize(self, reqId: int, tickType: int, size: object) -> None:  # noqa: N802
        self._record_tick(reqId, tickType, str(size))

    def tickString(self, reqId: int, tickType: int, value: str) -> None:  # noqa: N802
        self._record_tick(reqId, tickType, value)

    def _record_tick(self, request_id: int, tick_type: int, value: str) -> None:
        self._record(
            {
                "schemaVersion": "ibkr-delayed-callback-v1",
                "type": "tick",
                "requestId": request_id,
                "receivedAt": utc_now(),
                "tickType": tick_type,
                "tickName": TICK_NAMES.get(tick_type, f"TICK_{tick_type}"),
                "value": value,
                **self.contexts.get(request_id, {}),
            }
        )

    def error(  # noqa: N802
        self,
        reqId: int,
        errorTime: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        event = {
            "schemaVersion": "ibkr-delayed-callback-v1",
            "type": "apiEvent",
            "requestId": reqId,
            "receivedAt": utc_now(),
            "code": errorCode,
            "message": errorString,
            **self.contexts.get(reqId, {}),
        }
        self.raw_writer.write(event)
        if errorCode in DELAYED_INFORMATIONAL_CODES:
            self.warnings.append(event)
            return
        super().error(
            reqId,
            errorTime,
            errorCode,
            errorString,
            advancedOrderRejectJson,
        )

    def cancel(self, request_ids: list[int]) -> None:
        if self.isConnected():
            for request_id in request_ids:
                self.cancelMktData(request_id)
        for request_id in request_ids:
            self.discard_request(request_id)


def summarize_delayed_quotes(
    events: list[dict[str, object]], observed_at: str
) -> dict[str, dict[str, object]]:
    observed = datetime.fromisoformat(observed_at)
    if observed.tzinfo is None:
        raise ValueError("observed_at must include a timezone")
    instruments = sorted(
        {str(event["instrument"]) for event in events if "instrument" in event}
    )
    result: dict[str, dict[str, object]] = {}
    for instrument in instruments:
        matching = [event for event in events if event.get("instrument") == instrument]
        data_types = [
            int(event["marketDataType"])
            for event in matching
            if event.get("type") == "marketDataType"
        ]
        ticks: dict[str, dict[str, str]] = {}
        for event in matching:
            if event.get("type") != "tick":
                continue
            ticks[str(event["tickName"])] = {
                "value": str(event["value"]),
                "receivedAt": str(event["receivedAt"]),
            }
        timestamp = ticks.get("DELAYED_LAST_TIMESTAMP")
        last_as_of = None
        age_seconds = None
        if timestamp is not None:
            epoch = int(timestamp["value"])
            last_as_of_value = datetime.fromtimestamp(epoch, timezone.utc)
            last_as_of = last_as_of_value.isoformat()
            age_seconds = max(0, round((observed - last_as_of_value).total_seconds()))
        result[instrument] = {
            "marketDataType": data_types[-1] if data_types else None,
            "conId": next((event.get("conId") for event in matching if event.get("conId")), None),
            "localSymbol": next((event.get("localSymbol") for event in matching if event.get("localSymbol")), None),
            "lastAsOf": last_as_of,
            "lastAgeSeconds": age_seconds,
            "ticks": ticks,
        }
    return result


def select_delayed_contracts(catalog: dict[str, Any], selections: tuple,
                             as_of: date, auto_roll_futures: bool,
                             minimum_days_to_expiry: int) -> tuple[dict[str, dict[str, object]], dict]:
    if minimum_days_to_expiry < 0:
        raise ValueError("Minimum futures days to expiry cannot be negative")
    selected = select_contract_records(catalog, selections)
    decisions = {}
    if auto_roll_futures:
        for instrument in ("ES", "NQ"):
            eligible = []
            for candidate in catalog["contracts"].get(instrument, []):
                try:
                    expiration = datetime.strptime(str(candidate["expiration"]), "%Y%m%d").date()
                except (KeyError, ValueError) as error:
                    raise ValueError(f"Invalid {instrument} futures expiration in catalog") from error
                if expiration >= as_of + timedelta(days=minimum_days_to_expiry):
                    eligible.append((expiration, int(candidate["conId"]), candidate))
            if not eligible:
                raise ValueError(f"No {instrument} contract satisfies the explicit rollover buffer")
            expiration, _, candidate = min(eligible)
            selected[instrument] = dict(candidate)
            decisions[instrument] = {"localSymbol": candidate["localSymbol"],
                                     "conId": candidate["conId"],
                                     "expiration": expiration.isoformat(),
                                     "daysToExpiry": (expiration-as_of).days}
    return selected, {"mode": "FIRST_EXPIRY_AFTER_BUFFER" if auto_roll_futures else "PINNED_PLAN",
                      "minimumDaysToExpiry": minimum_days_to_expiry if auto_roll_futures else None,
                      "asOf": as_of.isoformat(), "decisions": decisions}


def capture_delayed_quotes(
    *,
    plan_path: Path,
    catalog_path: Path,
    output_root: Path,
    duration_seconds: float,
    auto_roll_futures: bool = False,
    minimum_days_to_expiry: int = 10,
) -> dict[str, Any]:
    if duration_seconds <= 0:
        raise ValueError("Delayed quote duration must be positive")
    plan = load_live_capture_plan(plan_path, duration_override=duration_seconds)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    contracts, roll_policy = select_delayed_contracts(
        catalog, plan.selections, datetime.now(timezone.utc).date(),
        auto_roll_futures, minimum_days_to_expiry)
    run_directory = create_immutable_run_directory(output_root, "delayed")
    raw_path = run_directory / "raw.ndjson"
    raw_writer = NdjsonWriter(raw_path)
    client = DelayedQuoteClient(GatewayConfig.from_environment(os.environ), raw_writer)
    request_ids: list[int] = []
    try:
        client.connect_and_start(plan.settings.connection_timeout_seconds)
        request_ids = client.subscribe(contracts)
        time.sleep(duration_seconds)
        observed_at = utc_now()
        summary = summarize_delayed_quotes(client.events, observed_at)
        client.cancel(request_ids)
    finally:
        client.close()
        raw_writer.close()

    expected = set(contracts)
    usable = {
        instrument
        for instrument, quote in summary.items()
        if quote["marketDataType"] == DELAYED_MARKET_DATA_TYPE
        and any(name in quote["ticks"] for name in ("DELAYED_BID", "DELAYED_ASK", "DELAYED_LAST"))
    }
    quotes = {
        "schemaVersion": "ibkr-delayed-quotes-v1",
        "status": "ok" if usable == expected else "partial",
        "observedAt": observed_at,
        "requestedDurationSeconds": duration_seconds,
        "quotes": summary,
        "warnings": client.warnings,
        "errors": client.errors,
    }
    quotes_path = run_directory / "quotes.json"
    quotes_hash = write_json_exclusive(quotes_path, quotes)
    manifest = {
        "schemaVersion": "ibkr-delayed-manifest-v1",
        "status": quotes["status"],
        "marketDataType": "DELAYED",
        "marketDataTypeId": DELAYED_MARKET_DATA_TYPE,
        "ibapiVersion": ibapi.__version__,
        "catalogPath": str(catalog_path),
        "planPath": str(plan_path),
        "selectedContracts": {instrument: {key: contract.get(key) for key in
                              ("conId", "localSymbol", "expiration")}
                              for instrument, contract in contracts.items()},
        "futuresRollPolicy": roll_policy,
        "raw": {"path": str(raw_path), "records": raw_writer.count, "sha256": raw_writer.sha256},
        "quotes": {"path": str(quotes_path), "sha256": quotes_hash},
    }
    manifest_path = run_directory / "manifest.json"
    write_json_exclusive(manifest_path, manifest)
    return {**quotes, "manifestPath": str(manifest_path), "quotesPath": str(quotes_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=Path("config/ibkr-live.json"))
    parser.add_argument("--catalog", type=Path)
    parser.add_argument(
        "--catalog-root", type=Path, default=Path("datasets/ibkr/contracts")
    )
    parser.add_argument(
        "--output-root", type=Path, default=Path("datasets/ibkr/delayed")
    )
    parser.add_argument("--duration-seconds", type=float, default=15.0)
    parser.add_argument("--auto-roll-futures", action="store_true")
    parser.add_argument("--minimum-days-to-expiry", type=int, default=10)
    args = parser.parse_args()
    try:
        catalog = args.catalog or find_latest_catalog(args.catalog_root)
        result = capture_delayed_quotes(
            plan_path=args.plan,
            catalog_path=catalog,
            output_root=args.output_root,
            duration_seconds=args.duration_seconds,
            auto_roll_futures=args.auto_roll_futures,
            minimum_days_to_expiry=args.minimum_days_to_expiry,
        )
    except Exception as error:
        print(json.dumps({"status": "error", "message": str(error)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
