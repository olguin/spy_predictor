from __future__ import annotations

import json

import pytest

from spy_predictor_quant.ibkr_config import (
    ContractQuery,
    GatewayConfig,
    load_contract_queries,
)
from spy_predictor_quant.ibkr_contract_catalog import (
    build_catalog,
    validate_resolved_contracts,
    verify_catalog_hash,
)


def safe_environment() -> dict[str, str]:
    return {
        "IBKR_HOST": "127.0.0.1",
        "IBKR_PORT": "4002",
        "IBKR_CLIENT_ID": "71",
        "IBKR_MODE": "paper",
        "IBKR_READ_ONLY": "true",
    }


def test_gateway_configuration_requires_safe_paper_settings() -> None:
    config = GatewayConfig.from_environment(safe_environment())
    assert config.port == 4002
    assert config.read_only is True

    for key, unsafe_value in (
        ("IBKR_HOST", "192.0.2.10"),
        ("IBKR_PORT", "4001"),
        ("IBKR_MODE", "live"),
        ("IBKR_READ_ONLY", "false"),
    ):
        environment = safe_environment()
        environment[key] = unsafe_value
        with pytest.raises(ValueError):
            GatewayConfig.from_environment(environment)


def test_loads_only_the_required_contract_query_set(tmp_path) -> None:
    source = tmp_path / "contracts.json"
    source.write_text(
        json.dumps(
            {
                "schemaVersion": "ibkr-contract-query-v1",
                "instruments": [
                    {
                        "instrument": instrument,
                        "symbol": instrument,
                        "securityType": "STK" if instrument in {"SPY", "QQQ"} else "FUT",
                        "exchange": "SMART" if instrument in {"SPY", "QQQ"} else "CME",
                        "currency": "USD",
                    }
                    for instrument in ("SPY", "QQQ", "ES", "NQ")
                ],
            }
        ),
        encoding="utf-8",
    )
    schema_version, queries = load_contract_queries(source)
    assert schema_version == "ibkr-contract-query-v1"
    assert [query.instrument for query in queries] == ["SPY", "QQQ", "ES", "NQ"]


def test_contract_validation_rejects_ambiguous_stock_and_incomplete_future() -> None:
    stock = ContractQuery("SPY", "SPY", "STK", "SMART", "USD")
    duplicate_stock = [
        {
            "conId": 1,
            "symbol": "SPY",
            "securityType": "STK",
            "currency": "USD",
            "exchange": "SMART",
        },
        {
            "conId": 2,
            "symbol": "SPY",
            "securityType": "STK",
            "currency": "USD",
            "exchange": "SMART",
        },
    ]
    with pytest.raises(ValueError, match="expected exactly one"):
        validate_resolved_contracts(stock, duplicate_stock)

    future = ContractQuery("ES", "ES", "FUT", "CME", "USD")
    incomplete_future = [
        {
            "conId": 3,
            "symbol": "ES",
            "securityType": "FUT",
            "currency": "USD",
            "exchange": "CME",
            "expiration": "",
            "localSymbol": "ESZ6",
        }
    ]
    with pytest.raises(ValueError, match="without an expiration"):
        validate_resolved_contracts(future, incomplete_future)


def test_catalog_hash_excludes_capture_time_and_warnings() -> None:
    queries = [ContractQuery("SPY", "SPY", "STK", "SMART", "USD")]
    contracts = {
        "SPY": [
            {
                "conId": 756733,
                "symbol": "SPY",
                "securityType": "STK",
                "currency": "USD",
                "exchange": "SMART",
            }
        ]
    }
    first = build_catalog(
        query_schema_version="ibkr-contract-query-v1",
        queries=queries,
        contracts=contracts,
        ibapi_version="10.50.1",
        server_version=226,
        gateway_connection_time="first login",
        warnings=[],
        captured_at="2026-09-04T00:00:00+00:00",
    )
    second = build_catalog(
        query_schema_version="ibkr-contract-query-v1",
        queries=queries,
        contracts=contracts,
        ibapi_version="10.50.1",
        server_version=226,
        gateway_connection_time="second login",
        warnings=[{"code": 2104}],
        captured_at="2026-09-04T01:00:00+00:00",
    )
    assert first["catalogHash"] == second["catalogHash"]
    verify_catalog_hash(first)
    first["contracts"]["SPY"][0]["conId"] = 1
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_catalog_hash(first)
