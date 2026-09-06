from __future__ import annotations

from spy_predictor_quant.market_comparison import (
    compare_instrument_bars,
    normalize_alpaca_bars,
)


def normalized_bar(timestamp: str, close: float, volume: float) -> dict[str, object]:
    return {
        "instrument": "SPY",
        "eventTime": timestamp,
        "open": close - 0.1,
        "high": close + 0.2,
        "low": close - 0.2,
        "close": close,
        "volume": volume,
    }


def test_normalizes_alpaca_response_with_point_in_time_metadata() -> None:
    records = normalize_alpaca_bars(
        "SPY",
        [
            {
                "t": "2026-09-04T13:30:00Z",
                "o": 100,
                "h": 101,
                "l": 99,
                "c": 100.5,
                "v": 1000,
                "vw": 100.25,
                "n": 20,
            }
        ],
        "2026-09-05T00:00:00+00:00",
    )
    assert records[0]["source"] == "alpaca-sip"
    assert records[0]["firstSeenAt"] == "2026-09-05T00:00:00+00:00"
    assert records[0]["eventTime"] == "2026-09-04T13:30:00+00:00"
    assert len(str(records[0]["hash"])) == 64


def test_comparison_reports_coverage_alignment_differences_and_outliers() -> None:
    ibkr = [
        normalized_bar("2026-09-04T13:30:00+00:00", 100, 1000),
        normalized_bar("2026-09-04T13:31:00+00:00", 101, 2000),
        normalized_bar("2026-09-04T13:32:00+00:00", 102, 3000),
    ]
    reference = [
        normalized_bar("2026-09-04T13:30:00+00:00", 100, 1000),
        normalized_bar("2026-09-04T13:31:00+00:00", 100, 1000),
        normalized_bar("2026-09-04T13:33:00+00:00", 103, 4000),
    ]
    report = compare_instrument_bars("SPY", ibkr, reference)
    assert report["intersectionBars"] == 2
    assert report["missingFromIbkr"]["count"] == 1
    assert report["missingFromReference"]["count"] == 1
    assert report["timestampAlignment"]["nearestOffsetMinutes"]["0"] == 2
    assert report["closeDifferenceBps"]["maximum"] > 5
    assert report["outliers"]["count"] == 1


def test_comparison_counts_identical_duplicates_without_double_counting() -> None:
    first = normalized_bar("2026-09-04T13:30:00+00:00", 100, 1000)
    report = compare_instrument_bars("SPY", [first, dict(first)], [first])
    assert report["ibkrDuplicateTimestamps"] == 1
    assert report["ibkrBars"] == 1
    assert report["intersectionBars"] == 1
