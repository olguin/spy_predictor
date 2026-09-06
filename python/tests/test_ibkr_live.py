from __future__ import annotations

from pathlib import Path

from spy_predictor_quant.ibkr_live_aggregate import (
    LiveCaptureState,
    aggregate_realtime_events,
)
from spy_predictor_quant.ibkr_live_config import load_live_capture_plan
from spy_predictor_quant.market_archive import (
    LiveSessionArchiveWriter,
    read_ndjson,
)


def event(epoch: int, price: float, received_at: str) -> dict[str, object]:
    return {
        "type": "realtimeBar",
        "instrument": "SPY",
        "conId": 756733,
        "receivedAt": received_at,
        "bar": {
            "time": epoch,
            "open": str(price),
            "high": str(price + 1),
            "low": str(price - 1),
            "close": str(price + 0.5),
            "volume": "10",
            "weightedAveragePrice": str(price + 0.25),
            "tradeCount": 2,
        },
    }


def test_live_plan_requires_exact_five_second_trade_bars() -> None:
    path = Path(__file__).parents[2] / "config" / "ibkr-live.json"
    plan = load_live_capture_plan(path, duration_override=10)
    assert plan.settings.bar_size_seconds == 5
    assert plan.settings.duration_seconds == 10
    assert {item.instrument for item in plan.selections} == {"SPY", "QQQ", "ES", "NQ"}


def test_aggregates_five_second_bars_with_local_first_seen_timestamp() -> None:
    start = 1_700_000_040
    events = [
        event(
            start + offset,
            100 + index,
            f"2026-09-04T20:00:{index * 5:02d}+00:00",
        )
        for index, offset in enumerate(range(0, 60, 5))
    ]
    contracts = {"SPY": {"conId": 756733, "localSymbol": "SPY"}}
    records, quality = aggregate_realtime_events(events, contracts)
    assert len(records) == 1
    assert records[0]["open"] == 100
    assert records[0]["close"] == 111.5
    assert records[0]["high"] == 112
    assert records[0]["low"] == 99
    assert records[0]["volume"] == 120
    assert records[0]["componentBars"] == 12
    assert records[0]["complete"] is True
    assert records[0]["provenanceClass"] == "locally-first-seen"
    assert records[0]["firstSeenAt"] == "2026-09-04T20:00:55+00:00"
    assert records[0]["firstComponentSeenAt"] == "2026-09-04T20:00:00+00:00"
    assert records[0]["lastComponentSeenAt"] == "2026-09-04T20:00:55+00:00"
    assert quality["SPY"]["completeOneMinuteBars"] == 1


def test_marks_incomplete_minute_without_fabricating_components() -> None:
    contracts = {"SPY": {"conId": 756733, "localSymbol": "SPY"}}
    records, quality = aggregate_realtime_events(
        [event(1_700_000_040, 100, "2026-09-04T20:00:00+00:00")],
        contracts,
    )
    assert records[0]["complete"] is False
    assert quality["SPY"]["partialOneMinuteBars"] == 1


def test_suppresses_reconnect_duplicates_and_stops_on_conflict(tmp_path) -> None:
    writer = LiveSessionArchiveWriter(tmp_path)
    state = LiveCaptureState(writer)
    first = event(1_700_000_040, 100, "2026-09-04T20:00:00+00:00")
    state.record_bar(first)
    state.record_bar(first)
    assert len(state.events) == 1
    assert state.duplicates["SPY"] == 1

    conflict = event(1_700_000_040, 101, "2026-09-04T20:00:01+00:00")
    state.record_bar(conflict)
    assert state.stop_requested.is_set()
    assert len(state.callback_errors) == 1
    writer.close()
    session_files = [
        entry for entry in writer.file_manifest() if entry["kind"] == "session"
    ]
    assert len(session_files) == 1
    assert len(read_ndjson(Path(session_files[0]["path"]))) == 1


def test_live_archive_rotates_stock_and_futures_trading_sessions(tmp_path) -> None:
    writer = LiveSessionArchiveWriter(tmp_path)
    stock = event(1_700_000_040, 100, "2026-09-04T20:00:00+00:00")
    future = {**stock, "instrument": "ES", "conId": 649180671}
    writer.write(stock)
    writer.write(future)
    writer.close()
    sessions = [
        (entry["instrument"], entry["sessionDate"])
        for entry in writer.file_manifest()
        if entry["kind"] == "session"
    ]
    assert len(sessions) == 2
    assert {instrument for instrument, _ in sessions} == {"SPY", "ES"}
