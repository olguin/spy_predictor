from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time as wall_time
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np
from jsonschema import Draft202012Validator
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

NY = ZoneInfo("America/New_York")
LABELS = ("DOWN", "NEUTRAL", "UP")


@dataclass(frozen=True)
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    contract_ticker: str | None = None
    session_date: str | None = None


@dataclass(frozen=True)
class Observation:
    symbol: str
    horizon: str
    date: str
    target_return: float
    label: str
    realized_volatility: float
    features: tuple[float, ...]


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def download_yahoo(symbol: str, settings: dict[str, Any], destination: Path) -> bytes:
    if destination.exists():
        return destination.read_bytes()
    query = urllib.parse.urlencode(
        {
            "range": settings["range"],
            "interval": settings["interval"],
            "includePrePost": str(settings["includePrePost"]).lower(),
            "events": "div,splits",
        }
    )
    encoded_symbol = urllib.parse.quote(symbol, safe="")
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 spy-predictor-research/0.1"})
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            return payload
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            time.sleep(2**attempt)
    raise RuntimeError(f"Unable to download {symbol}: {last_error}")


def parse_yahoo(payload: bytes, normalized_symbol: str) -> list[Bar]:
    document = json.loads(payload)
    chart = document.get("chart", {})
    if chart.get("error"):
        raise ValueError(f"Yahoo returned an error for {normalized_symbol}: {chart['error']}")
    result = (chart.get("result") or [None])[0]
    if not result:
        raise ValueError(f"Yahoo returned no data for {normalized_symbol}")
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    bars: list[Bar] = []
    for index, epoch in enumerate(timestamps):
        values = {key: (quote.get(key) or [None] * len(timestamps))[index] for key in ("open", "high", "low", "close", "volume")}
        if any(values[key] is None for key in ("open", "high", "low", "close")):
            continue
        bars.append(
            Bar(
                symbol=normalized_symbol,
                timestamp=datetime.fromtimestamp(epoch, tz=NY),
                open=float(values["open"]),
                high=float(values["high"]),
                low=float(values["low"]),
                close=float(values["close"]),
                volume=float(values["volume"] or 0),
            )
        )
    return sorted(bars, key=lambda bar: bar.timestamp)


def regular_sessions(bars: Iterable[Bar]) -> dict[str, list[Bar]]:
    sessions: dict[str, list[Bar]] = defaultdict(list)
    for bar in bars:
        local_time = bar.timestamp.timetz().replace(tzinfo=None)
        if wall_time(9, 30) <= local_time <= wall_time(16, 0):
            sessions[bar.timestamp.date().isoformat()].append(bar)
    return {date: sorted(values, key=lambda bar: bar.timestamp) for date, values in sessions.items() if len(values) >= 2}


def log_return(end: float, start: float) -> float:
    return math.log(end / start)


def direction(value: float, threshold: float) -> str:
    if value > threshold:
        return "UP"
    if value < -threshold:
        return "DOWN"
    return "NEUTRAL"


def realized_volatility(bars: list[Bar]) -> float:
    returns = [log_return(bar.close, previous.close) for previous, bar in zip(bars, bars[1:])]
    return math.sqrt(sum(value * value for value in returns))


def bar_at_or_after(bars: list[Bar], hour: int, minute: int) -> Bar | None:
    target = wall_time(hour, minute)
    return next((bar for bar in bars if bar.timestamp.timetz().replace(tzinfo=None) >= target), None)


def build_observations(symbol: str, bars: list[Bar], config: dict[str, Any]) -> list[Observation]:
    sessions = regular_sessions(bars)
    dates = sorted(sessions)
    threshold = float(config["neutralThreshold"])
    observations: list[Observation] = []
    prior_returns: list[float] = []
    ewma_variance = 0.0
    for index in range(1, len(dates)):
        date = dates[index]
        previous = sessions[dates[index - 1]]
        current = sessions[date]
        current_open = current[0].open
        previous_close = previous[-1].close
        previous_return = log_return(previous[-1].close, previous[0].open)
        overnight = log_return(current_open, previous_close)
        ewma_variance = 0.94 * ewma_variance + 0.06 * previous_return * previous_return
        features = (overnight, previous_return, abs(previous_return), math.sqrt(ewma_variance))
        targets: dict[str, tuple[float, list[Bar]]] = {}
        for horizon, minutes in (("open-15m", 15), ("open-30m", 30), ("open-60m", 60)):
            exit_hour, exit_minute = divmod(9 * 60 + 30 + minutes, 60)
            exit_bar = bar_at_or_after(current, exit_hour, exit_minute)
            if exit_bar:
                selected = [bar for bar in current if bar.timestamp <= exit_bar.timestamp]
                targets[horizon] = (log_return(exit_bar.close, current_open), selected)
        targets["previous-close-next-open"] = (overnight, [previous[-1], current[0]])
        targets["open-close"] = (log_return(current[-1].close, current_open), current)
        if index + 1 < len(dates):
            following = sessions[dates[index + 1]]
            targets["close-next-close"] = (
                log_return(following[-1].close, current[-1].close),
                [current[-1], *following],
            )
        for horizon in config["horizons"]:
            if horizon not in targets:
                continue
            target_return, target_bars = targets[horizon]
            horizon_features = features
            if horizon == "previous-close-next-open":
                horizon_features = (0.0, previous_return, abs(previous_return), math.sqrt(ewma_variance))
            elif horizon == "close-next-close":
                current_return = log_return(current[-1].close, current_open)
                horizon_features = (overnight, current_return, abs(current_return), math.sqrt(ewma_variance))
            observations.append(
                Observation(symbol, horizon, date, target_return, direction(target_return, threshold), realized_volatility(target_bars), horizon_features)
            )
        prior_returns.append(previous_return)
    return observations


def class_frequencies(labels: list[str]) -> np.ndarray:
    counts = np.ones(3, dtype=float)
    for label in labels:
        counts[LABELS.index(label)] += 1
    return counts / counts.sum()


def rule_probability(label: str) -> np.ndarray:
    result = np.full(3, 0.001)
    result[LABELS.index(label)] = 0.998
    return result


def model_probability(name: str, train: list[Observation], current: Observation, seed: int) -> np.ndarray:
    labels = [item.label for item in train]
    frequencies = class_frequencies(labels)
    if name == "historical-frequency":
        return frequencies
    if name == "always-up":
        return rule_probability("UP")
    if name == "always-down":
        return rule_probability("DOWN")
    if name == "random-calibrated":
        rng = np.random.default_rng(seed + int(current.date.replace("-", "")))
        return rng.dirichlet(1 + frequencies * 9)
    value = current.features[0] if name.startswith("overnight") else current.features[1]
    if name in {"overnight-reversal", "mean-reversion"}:
        value = -value
    if name in {"overnight-continuation", "overnight-reversal", "momentum", "mean-reversion"}:
        return rule_probability(direction(value, 0.0))
    x_train = np.asarray([item.features for item in train])
    y_train = np.asarray([LABELS.index(item.label) for item in train])
    if len(set(y_train.tolist())) < 2:
        return frequencies
    if name == "logistic-l2":
        estimator = LogisticRegression(C=0.25, max_iter=500, random_state=seed)
    elif name == "tree-depth-3":
        estimator = DecisionTreeClassifier(max_depth=3, min_samples_leaf=3, class_weight="balanced", random_state=seed)
    else:
        raise ValueError(f"Unknown model {name}")
    estimator.fit(x_train, y_train)
    raw = estimator.predict_proba(np.asarray([current.features]))[0]
    probabilities = np.zeros(3)
    for class_value, probability in zip(estimator.classes_, raw):
        probabilities[int(class_value)] = probability
    return np.clip(probabilities, 1e-6, 1.0) / np.clip(probabilities, 1e-6, 1.0).sum()


def summarize_predictions(
    predictions: list[dict[str, Any]], cost_bps: float, include_breakdowns: bool = True
) -> dict[str, Any]:
    if not predictions:
        return {"observations": 0}
    brier = log_loss = correct = economic_return = 0.0
    calibration_bins: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for prediction in predictions:
        probabilities = prediction["probabilities"]
        actual = LABELS.index(prediction["label"])
        brier += sum((probabilities[index] - (1 if index == actual else 0)) ** 2 for index in range(3))
        log_loss -= math.log(max(probabilities[actual], 1e-15))
        predicted = int(np.argmax(probabilities))
        correct += predicted == actual
        confidence = float(max(probabilities))
        calibration_bins[min(9, int(confidence * 10))].append((confidence, float(predicted == actual)))
        position = 1 if predicted == 2 else -1 if predicted == 0 else 0
        economic_return += position * prediction["return"] - (cost_bps / 10_000 if position else 0)
    count = len(predictions)
    ece = sum(
        len(values) / count * abs(np.mean([value[0] for value in values]) - np.mean([value[1] for value in values]))
        for values in calibration_bins.values()
    )
    summary: dict[str, Any] = {
        "observations": count,
        "brierScore": brier / count,
        "logLoss": log_loss / count,
        "accuracy": correct / count,
        "expectedCalibrationError": float(ece),
        "netReturnAfterCosts": economic_return,
        "meanNetReturnAfterCosts": economic_return / count,
    }
    if include_breakdowns:
        by_year: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for prediction in predictions:
            by_year[prediction["date"][:4]].append(prediction)
        median_volatility = float(np.median([item["realizedVolatility"] for item in predictions]))
        regimes = {
            "lower-volatility": [item for item in predictions if item["realizedVolatility"] <= median_volatility],
            "higher-volatility": [item for item in predictions if item["realizedVolatility"] > median_volatility],
        }
        summary["yearBreakdown"] = {
            year: summarize_predictions(values, cost_bps, False)
            for year, values in sorted(by_year.items())
        }
        summary["volatilityRegimeBreakdown"] = {
            regime: summarize_predictions(values, cost_bps, False)
            for regime, values in regimes.items()
        }
    return summary


def evaluate_group(observations: list[Observation], config: dict[str, Any]) -> dict[str, Any]:
    observations = sorted(observations, key=lambda item: item.date)
    minimum = int(config["minimumTrainingObservations"])
    rolling_window = int(config["rollingWindow"])
    models = (
        "historical-frequency", "always-up", "always-down", "random-calibrated",
        "overnight-continuation", "overnight-reversal", "momentum", "mean-reversion",
        "logistic-l2", "tree-depth-3",
    )
    results: dict[str, Any] = {}
    cost = float(config["transactionCostBps"][observations[0].symbol])
    for mode in ("expanding", "rolling"):
        by_model: dict[str, list[dict[str, Any]]] = {model: [] for model in models}
        volatility_predictions = {"historical-mean": [], "ewma": []}
        for index in range(minimum, len(observations)):
            start = 0 if mode == "expanding" else max(0, index - rolling_window)
            train = observations[start:index]
            current = observations[index]
            for model in models:
                probabilities = model_probability(model, train, current, int(config["randomSeed"]))
                by_model[model].append({
                    "date": current.date,
                    "label": current.label,
                    "return": current.target_return,
                    "realizedVolatility": current.realized_volatility,
                    "probabilities": probabilities.tolist(),
                })
            vols = [item.realized_volatility for item in train]
            ewma = 0.0
            for value in vols:
                ewma = 0.94 * ewma + 0.06 * value * value
            volatility_predictions["historical-mean"].append((sum(vols) / len(vols), current.realized_volatility))
            volatility_predictions["ewma"].append((math.sqrt(ewma), current.realized_volatility))
        volatility = {
            name: {
                "observations": len(values),
                "mae": sum(abs(predicted - actual) for predicted, actual in values) / len(values) if values else None,
                "rmse": math.sqrt(sum((predicted - actual) ** 2 for predicted, actual in values) / len(values)) if values else None,
            }
            for name, values in volatility_predictions.items()
        }
        results[mode] = {
            "directional": {model: summarize_predictions(values, cost) for model, values in by_model.items()},
            "volatility": volatility,
        }
    label_counts = {label: sum(item.label == label for item in observations) for label in LABELS}
    years = sorted({item.date[:4] for item in observations})
    return {
        "totalObservations": len(observations),
        "dateRange": [observations[0].date, observations[-1].date],
        "labelCounts": label_counts,
        "years": years,
        "evaluation": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# TARGET-TOURNAMENT-001 qualification report",
        "",
        f"Dataset version: `{report['datasetVersion']}`",
        "",
        f"Decision: **{report['decision']}**",
        "",
        report["decisionReason"],
        "",
        "| Instrument | Horizon | Samples | OOS samples | Best expanding Brier | Best net return |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, result in sorted(report["results"].items()):
        directional = result["evaluation"]["expanding"]["directional"]
        eligible = [(name, values) for name, values in directional.items() if values.get("observations", 0)]
        if eligible:
            best_brier = min(values["brierScore"] for _, values in eligible)
            best_net = max(values["netReturnAfterCosts"] for _, values in eligible)
            oos = eligible[0][1]["observations"]
        else:
            best_brier = best_net = 0
            oos = 0
        symbol, horizon = key.split("/", 1)
        lines.append(f"| {symbol} | {horizon} | {result['totalObservations']} | {oos} | {best_brier:.6f} | {best_net:.6f} |")
    lines.extend(["", "## Data-quality gate", "", report["providerLimitation"], "", "No LLM calls were made."])
    return "\n".join(lines) + "\n"


def run(config_path: Path, repo_root: Path, refresh: bool = False) -> dict[str, Any]:
    config = json.loads(config_path.read_text())
    provider = config["provider"]
    raw_root = repo_root / "datasets" / "tournament" / "raw"
    if refresh and raw_root.exists():
        raise ValueError("--refresh requires removing or archiving the pinned raw directory explicitly")
    raw_hashes: dict[str, str] = {}
    all_observations: list[Observation] = []
    quality: dict[str, Any] = {}
    for symbol, vendor_symbol in provider["symbols"].items():
        path = raw_root / f"{symbol}.json"
        payload = download_yahoo(vendor_symbol, provider, path)
        raw_hashes[symbol] = hashlib.sha256(payload).hexdigest()
        bars = parse_yahoo(payload, symbol)
        sessions = regular_sessions(bars)
        quality[symbol] = {
            "bars": len(bars),
            "regularSessions": len(sessions),
            "medianRegularSessionVolume": float(np.median([sum(bar.volume for bar in session) for session in sessions.values()])),
            "firstTimestamp": bars[0].timestamp.isoformat(),
            "lastTimestamp": bars[-1].timestamp.isoformat(),
        }
        all_observations.extend(build_observations(symbol, bars, config))
    dataset_version = f"yahoo-chart-{canonical_hash({'config': provider, 'rawHashes': raw_hashes})[:16]}"
    grouped: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    for observation in all_observations:
        grouped[(observation.symbol, observation.horizon)].append(observation)
    results = {f"{symbol}/{horizon}": evaluate_group(values, config) for (symbol, horizon), values in sorted(grouped.items())}
    minimum = int(config["minimumPromotionObservations"])
    adequate_sample = bool(results) and all(
        result["evaluation"]["expanding"]["directional"]["historical-frequency"].get("observations", 0) >= minimum
        for result in results.values()
    )
    point_in_time_safe = bool(provider["pointInTimeSafe"])
    promoted = point_in_time_safe and adequate_sample
    reason_parts = []
    if not point_in_time_safe:
        reason_parts.append("the provider lacks first-seen/revision provenance")
    if not adequate_sample:
        reason_parts.append(f"one or more candidates have fewer than {minimum} out-of-sample observations")
    report = {
        "reportVersion": "target-tournament-report-v1",
        "datasetVersion": dataset_version,
        "configHash": canonical_hash(config),
        "rawHashes": raw_hashes,
        "noLlmCalls": True,
        "pointInTimeSafe": point_in_time_safe,
        "providerLimitation": provider["limitation"],
        "normalization": {
            "symbols": provider["symbols"],
            "timezone": "America/New_York from timezone-aware UTC epochs",
            "prices": "vendor raw OHLC; no split/dividend back-adjustment",
            "futures": "vendor continuous symbols; rollover series is not back-adjusted",
        },
        "dataQuality": quality,
        "decision": "FREEZE_TARGET" if promoted else "NO_TARGET_ADEQUATE",
        "decisionReason": "Promotion gates passed." if promoted else "No V1 target is frozen because " + " and ".join(reason_parts) + ".",
        "results": results,
    }
    report_schema = json.loads(
        (repo_root / "schemas" / "target-tournament-report.schema.json").read_text()
    )
    Draft202012Validator(report_schema).validate(report)
    report_root = repo_root / "reports" / dataset_version
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (report_root / "report.md").write_text(render_markdown(report))
    manifest = {
        "datasetVersion": dataset_version,
        "provider": provider,
        "rawHashes": raw_hashes,
        "configHash": report["configHash"],
        "reportHash": hashlib.sha256((report_root / "report.json").read_bytes()).hexdigest(),
    }
    (report_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {"datasetVersion": dataset_version, "decision": report["decision"], "report": str(report_root / "report.md")}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the no-LLM target tournament qualification pipeline")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.config, args.repo_root, args.refresh), indent=2))


if __name__ == "__main__":
    main()
