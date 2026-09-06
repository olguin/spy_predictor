"""Resolve SPY, QQQ, ES, and NQ through the official IBKR Python API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

import ibapi
from ibapi.contract import Contract, ContractDetails

from spy_predictor_quant.ibkr_config import (
    ContractQuery,
    GatewayConfig,
    load_contract_queries,
)
from spy_predictor_quant.ibkr_contract_catalog import (
    build_catalog,
    validate_resolved_contracts,
    write_immutable_catalog,
)
from spy_predictor_quant.ibkr_session import IbkrSession


class ContractResolver(IbkrSession):
    def __init__(self, config: GatewayConfig) -> None:
        super().__init__(config)
        self._contract_details: dict[int, list[ContractDetails]] = {}
        self._contract_details_lock = threading.Lock()

    def contractDetails(  # noqa: N802 - IBKR callback
        self,
        reqId: int,
        contractDetails: ContractDetails,
    ) -> None:
        with self._contract_details_lock:
            self._contract_details.setdefault(reqId, []).append(contractDetails)

    def contractDetailsEnd(self, reqId: int) -> None:  # noqa: N802
        self.complete_request(reqId)

    def resolve(
        self,
        query: ContractQuery,
        timeout_seconds: float,
    ) -> list[dict[str, object]]:
        request_id = self.begin_request()
        with self._contract_details_lock:
            self._contract_details[request_id] = []
        self.reqContractDetails(request_id, _make_contract(query))
        try:
            self.wait_for_request(
                request_id,
                f"contract details for {query.instrument}",
                timeout_seconds,
            )
        finally:
            with self._contract_details_lock:
                details = self._contract_details.pop(request_id, [])
        records = [_serialize_contract_details(query.instrument, item) for item in details]
        return validate_resolved_contracts(query, records)


def _make_contract(query: ContractQuery) -> Contract:
    contract = Contract()
    contract.symbol = query.symbol
    contract.secType = query.security_type
    contract.exchange = query.exchange
    contract.currency = query.currency
    contract.includeExpired = False
    if query.primary_exchange is not None:
        contract.primaryExchange = query.primary_exchange
    return contract


def _serialize_contract_details(
    instrument: str,
    details: ContractDetails,
) -> dict[str, object]:
    contract = details.contract
    return {
        "instrument": instrument,
        "conId": int(contract.conId),
        "symbol": str(contract.symbol),
        "securityType": str(contract.secType),
        "currency": str(contract.currency),
        "exchange": str(contract.exchange),
        "primaryExchange": str(contract.primaryExchange),
        "localSymbol": str(contract.localSymbol),
        "tradingClass": str(contract.tradingClass),
        "expiration": str(contract.lastTradeDateOrContractMonth),
        "realExpirationDate": str(details.realExpirationDate),
        "lastTradeTime": str(details.lastTradeTime),
        "multiplier": str(contract.multiplier),
        "minimumTick": float(details.minTick),
        "marketName": str(details.marketName),
        "validExchanges": str(details.validExchanges),
        "timeZoneId": str(details.timeZoneId),
        "tradingHours": str(details.tradingHours),
        "liquidHours": str(details.liquidHours),
        "longName": str(details.longName),
        "stockType": str(details.stockType),
    }


def resolve_catalog(
    config_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    query_schema_version, queries = load_contract_queries(config_path)
    gateway_config = GatewayConfig.from_environment(os.environ)
    resolver = ContractResolver(gateway_config)
    try:
        resolver.connect_and_start(timeout_seconds)
        contracts = {
            query.instrument: resolver.resolve(query, timeout_seconds)
            for query in queries
        }
        connection_time = resolver.twsConnectionTime()
        if isinstance(connection_time, bytes):
            connection_time = connection_time.decode("utf-8", errors="replace")
        return build_catalog(
            query_schema_version=query_schema_version,
            queries=queries,
            contracts=contracts,
            ibapi_version=ibapi.__version__,
            server_version=resolver.serverVersion(),
            gateway_connection_time=str(connection_time),
            warnings=resolver.warnings,
        )
    finally:
        resolver.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/ibkr-contracts.json"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("datasets/ibkr/contracts"),
    )
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--stdout-only", action="store_true")
    args = parser.parse_args()

    try:
        catalog = resolve_catalog(args.config, args.timeout_seconds)
        output_path = None
        if not args.stdout_only:
            output_path = write_immutable_catalog(catalog, args.output_root)
        result = {
            "status": "ok",
            "catalogPath": str(output_path) if output_path else None,
            **catalog,
        }
    except Exception as error:  # boundary converts SDK failures to CLI output
        print(
            json.dumps({"status": "error", "message": str(error)}, indent=2),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
