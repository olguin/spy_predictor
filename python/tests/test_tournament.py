from __future__ import annotations

from datetime import datetime, timedelta

from spy_predictor_quant.tournament import Bar, build_observations, evaluate_group
from zoneinfo import ZoneInfo


def fixture_bars(days: int = 25) -> list[Bar]:
    timezone = ZoneInfo("America/New_York")
    bars: list[Bar] = []
    date = datetime(2024, 1, 2, 9, 30, tzinfo=timezone)
    price = 100.0
    created = 0
    while created < days:
        if date.weekday() < 5:
            for offset in range(0, 391, 5):
                timestamp = date + timedelta(minutes=offset)
                next_price = price * (1 + (((created % 5) - 2) * 0.00002))
                bars.append(Bar("SPY", timestamp, price, max(price, next_price), min(price, next_price), next_price, 1000))
                price = next_price
            created += 1
        date = (date + timedelta(days=1)).replace(hour=9, minute=30)
    return bars


def config() -> dict:
    return {
        "horizons": ["open-15m", "open-30m", "open-60m", "previous-close-next-open", "open-close", "close-next-close"],
        "neutralThreshold": 0.00001,
        "minimumTrainingObservations": 10,
        "rollingWindow": 12,
        "randomSeed": 42,
        "transactionCostBps": {"SPY": 1.0},
    }


def test_generates_all_horizons_without_future_open_feature_leakage() -> None:
    observations = build_observations("SPY", fixture_bars(), config())
    horizons = {observation.horizon for observation in observations}
    assert horizons == set(config()["horizons"])
    overnight = next(item for item in observations if item.horizon == "previous-close-next-open")
    assert overnight.features[0] == 0.0


def test_runs_expanding_and_rolling_mandatory_baselines() -> None:
    observations = [item for item in build_observations("SPY", fixture_bars(), config()) if item.horizon == "open-30m"]
    result = evaluate_group(observations, config())
    for mode in ("expanding", "rolling"):
        directional = result["evaluation"][mode]["directional"]
        assert {"historical-frequency", "always-up", "always-down", "random-calibrated", "logistic-l2", "tree-depth-3"} <= set(directional)
        assert result["evaluation"][mode]["volatility"]["ewma"]["observations"] > 0
