from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from spy_predictor_quant.ibkr_history_config import (
    ContractSelection,
    HistoryPlan,
    HistorySettings,
    load_history_plan,
    is_transient_history_error,
    select_catalog_contracts,
    trading_weekday_endpoints,
)
from spy_predictor_quant.ibkr_history_normalize import normalize_historical_events
from spy_predictor_quant.market_archive import NdjsonWriter, read_ndjson
from spy_predictor_quant.request_pacing import PacingController
from spy_predictor_quant.ibkr_config import ContractQuery
from spy_predictor_quant.ibkr_contract_catalog import build_catalog


def settings() -> HistorySettings:
    return HistorySettings(
        bar_size="1 min",
        what_to_show="TRADES",
        use_regular_trading_hours=False,
        format_date=2,
        chunk_duration="1 D",
        chunk_count=1,
        end_lag_minutes=20,
        request_timeout_seconds=10,
        max_retries=0,
        retry_base_seconds=0,
        minimum_request_spacing_seconds=0,
        maximum_requests_per_window=55,
        pacing_window_seconds=600,
    )


def contract(instrument: str, contract_id: int, local_symbol: str) -> dict[str, object]:
    return {
        "instrument": instrument,
        "conId": contract_id,
        "symbol": instrument,
        "securityType": "STK" if instrument in {"SPY", "QQQ"} else "FUT",
        "exchange": "SMART" if instrument in {"SPY", "QQQ"} else "CME",
        "currency": "USD",
        "localSymbol": local_symbol,
    }


def bar_event(
    instrument: str,
    contract_id: int,
    epoch: int,
    close: str = "101",
) -> dict[str, object]:
    return {
        "type": "historicalBar",
        "instrument": instrument,
        "conId": contract_id,
        "receivedAt": "2026-09-04T20:00:00+00:00",
        "bar": {
            "date": str(epoch),
            "open": "100",
            "high": "102",
            "low": "99",
            "close": close,
            "volume": "1000",
            "weightedAveragePrice": "100.5",
            "tradeCount": 20,
        },
    }


def test_history_plan_requires_safe_one_minute_settings() -> None:
    path = Path(__file__).parents[2] / "config" / "ibkr-history.json"
    plan = load_history_plan(path, chunk_override=1)
    assert plan.settings.chunk_count == 1
    assert {item.instrument for item in plan.selections} == {"SPY", "QQQ", "ES", "NQ"}


def test_contract_selection_requires_exact_id_and_local_symbol() -> None:
    plan = HistoryPlan(
        "ibkr-history-request-v1",
        settings(),
        (ContractSelection("SPY", 756733, "SPY"),),
    )
    catalog = build_catalog(
        query_schema_version="ibkr-contract-query-v1",
        queries=[ContractQuery("SPY", "SPY", "STK", "SMART", "USD")],
        contracts={"SPY": [contract("SPY", 756733, "SPY")]},
        ibapi_version="10.50.1",
        server_version=226,
        gateway_connection_time="test",
        warnings=[],
    )
    selected = select_catalog_contracts(catalog, plan)
    assert selected["SPY"]["conId"] == 756733
    with pytest.raises(ValueError, match="does not contain exactly one"):
        select_catalog_contracts(
            catalog,
            replace(
                plan,
                selections=(ContractSelection("SPY", 999, "SPY"),),
            ),
        )


def test_normalization_deduplicates_exact_overlap_and_reports_gaps() -> None:
    contracts = {"SPY": contract("SPY", 756733, "SPY")}
    events = [
        bar_event("SPY", 756733, 1_700_000_000),
        bar_event("SPY", 756733, 1_700_000_000),
        bar_event("SPY", 756733, 1_700_000_120),
    ]
    records, quality = normalize_historical_events(events, contracts, settings())
    assert len(records) == 2
    assert records[0]["provenanceClass"] == "event-time-only"
    assert quality["SPY"]["exactDuplicateBarsRemoved"] == 1
    assert quality["SPY"]["intradayGapCandidateCount"] == 1


def test_normalization_rejects_conflicting_overlap() -> None:
    contracts = {"SPY": contract("SPY", 756733, "SPY")}
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        normalize_historical_events(
            [
                bar_event("SPY", 756733, 1_700_000_000),
                bar_event("SPY", 756733, 1_700_000_000, close="103"),
            ],
            contracts,
            settings(),
        )


def test_ndjson_writer_is_append_only_and_hashes_exact_bytes(tmp_path) -> None:
    path = tmp_path / "events.ndjson"
    writer = NdjsonWriter(path)
    writer.write({"event": 1})
    writer.close()
    assert writer.count == 1
    assert len(writer.sha256) == 64
    assert read_ndjson(path) == [{"event": 1}]
    with pytest.raises(FileExistsError):
        NdjsonWriter(path)


def test_pacing_controller_enforces_spacing_and_rolling_window() -> None:
    current = [0.0]
    sleeps: list[float] = []

    def clock() -> float:
        return current[0]

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        current[0] += seconds

    pacing = PacingController(1, 2, 10, clock=clock, sleeper=sleeper)
    pacing.wait()
    pacing.wait()
    pacing.wait()
    assert sleeps == [1.0, 9.0]


def test_retry_classification_is_limited_to_transient_conditions() -> None:
    assert is_transient_history_error([{"code": 1100, "message": "lost"}])
    assert is_transient_history_error(
        [{"code": 162, "message": "Historical pacing violation"}]
    )
    assert not is_transient_history_error(
        [{"code": 200, "message": "No security definition"}]
    )


def test_history_endpoints_skip_weekends() -> None:
    from datetime import datetime, timezone

    endpoints = trading_weekday_endpoints(
        datetime(2026, 9, 7, 20, tzinfo=timezone.utc),
        3,
    )
    assert [value.date().isoformat() for value in endpoints] == [
        "2026-09-07",
        "2026-09-04",
        "2026-09-03",
    ]
