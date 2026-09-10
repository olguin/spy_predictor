from __future__ import annotations

from datetime import date

from spy_predictor_quant.ibkr_contract_catalog import build_catalog
from spy_predictor_quant.ibkr_delayed import select_delayed_contracts, summarize_delayed_quotes
from spy_predictor_quant.ibkr_history_config import ContractSelection


def test_summarizes_latest_delayed_ticks_and_age() -> None:
    events = [
        {
            "type": "marketDataType",
            "instrument": "SPY",
            "marketDataType": 3,
        },
        {
            "type": "tick",
            "instrument": "SPY",
            "tickName": "DELAYED_LAST",
            "value": "100.0",
            "receivedAt": "2026-09-10T18:05:00+00:00",
        },
        {
            "type": "tick",
            "instrument": "SPY",
            "tickName": "DELAYED_LAST",
            "value": "101.0",
            "receivedAt": "2026-09-10T18:05:01+00:00",
        },
        {
            "type": "tick",
            "instrument": "SPY",
            "tickName": "DELAYED_LAST_TIMESTAMP",
            "value": "1789062600",
            "receivedAt": "2026-09-10T18:05:01+00:00",
        },
    ]
    result = summarize_delayed_quotes(events, "2026-09-10T18:05:00+00:00")
    assert result["SPY"]["marketDataType"] == 3
    assert result["SPY"]["ticks"]["DELAYED_LAST"]["value"] == "101.0"
    assert result["SPY"]["lastAsOf"] == "2026-09-10T17:50:00+00:00"
    assert result["SPY"]["lastAgeSeconds"] == 900


def test_allows_quote_without_exchange_timestamp() -> None:
    events = [
        {
            "type": "marketDataType",
            "instrument": "ES",
            "marketDataType": 3,
        },
        {
            "type": "tick",
            "instrument": "ES",
            "tickName": "DELAYED_BID",
            "value": "7600.0",
            "receivedAt": "2026-09-10T18:05:00+00:00",
        },
    ]
    result = summarize_delayed_quotes(events, "2026-09-10T18:05:00+00:00")
    assert result["ES"]["lastAsOf"] is None
    assert result["ES"]["lastAgeSeconds"] is None


def test_explicit_futures_roll_policy_selects_first_expiry_after_buffer() -> None:
    records = {
        "SPY": [{"conId": 1, "localSymbol": "SPY"}],
        "QQQ": [{"conId": 2, "localSymbol": "QQQ"}],
        "ES": [{"conId": 3, "localSymbol": "ESU6", "expiration": "20260918"},
               {"conId": 4, "localSymbol": "ESZ6", "expiration": "20261218"}],
        "NQ": [{"conId": 5, "localSymbol": "NQU6", "expiration": "20260918"},
               {"conId": 6, "localSymbol": "NQZ6", "expiration": "20261218"}],
    }
    catalog = build_catalog(query_schema_version="test", queries=[], contracts=records,
                            ibapi_version="test", server_version=1,
                            gateway_connection_time="test", warnings=[])
    selections = tuple(ContractSelection(symbol, rows[0]["conId"], rows[0]["localSymbol"])
                       for symbol, rows in records.items())
    selected, policy = select_delayed_contracts(
        catalog, selections, date(2026, 9, 10), True, 10)
    assert selected["ES"]["localSymbol"] == "ESZ6"
    assert selected["NQ"]["localSymbol"] == "NQZ6"
    assert policy["mode"] == "FIRST_EXPIRY_AFTER_BUFFER"
    assert policy["decisions"]["ES"]["daysToExpiry"] == 99
