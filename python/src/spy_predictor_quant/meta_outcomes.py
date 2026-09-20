"""Immutable maturity, outcome acquisition, and scoring for META observations."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
from statistics import NormalDist
from typing import Callable
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

from spy_predictor_quant.market_archive import (
    create_immutable_run_directory,
    file_sha256,
    write_bytes_exclusive,
    write_json_exclusive,
)
from spy_predictor_quant.meta_analysis import digest, get_raw


OUTCOME_VERSION = "meta-outcome-v1"
SCORE_VERSION = "meta-score-v1"
CAPTURE_VERSION = "meta-outcome-capture-v1"
DATA_DELAY = timedelta(minutes=20)
ROOT = Path(__file__).resolve().parents[3]


def _instant(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _verified(path: Path, hash_field: str, version_field: str, version: str) -> dict:
    value = json.loads(path.read_text())
    if value.get(version_field) != version or not isinstance(value.get(hash_field), str):
        raise ValueError(f"Unexpected {version_field} or missing {hash_field}: {path}")
    core = {key: item for key, item in value.items() if key != hash_field}
    if digest(core) != value[hash_field]:
        raise ValueError(f"{hash_field} integrity mismatch: {path}")
    return value


def load_forecast(path: Path) -> dict:
    return _verified(path, "forecast_hash", "version", "meta-observation-v1")


def load_outcome(path: Path) -> dict:
    return _verified(path, "outcome_hash", "schemaVersion", OUTCOME_VERSION)


def load_score(path: Path) -> dict:
    return _verified(path, "score_hash", "schemaVersion", SCORE_VERSION)


def _record_path(root: Path, forecast_hash: str, symbol: str, horizon: int) -> Path:
    return root / forecast_hash / f"{symbol}-{horizon:03d}.json"


def _availability(target_session: str) -> datetime:
    close = xcals.get_calendar("XNYS").session_close(target_session).to_pydatetime()
    return close + DATA_DELAY


def evaluation_status(
    forecast_root: Path,
    outcome_root: Path,
    score_root: Path,
    now: datetime | None = None,
) -> dict:
    cutoff = _instant(now or datetime.now(timezone.utc))
    rows = []
    for path in sorted(forecast_root.glob("*.json")):
        forecast = load_forecast(path)
        for symbol, issued in sorted(forecast["symbols"].items()):
            if issued.get("status") != "ISSUED":
                continue
            scenarios = {int(row["trading_days"]): row for row in issued["quantitative_reference"]}
            targets = {int(key): value for key, value in issued["target_sessions"].items()}
            if scenarios.keys() != targets.keys():
                raise ValueError(f"Forecast scenarios and targets differ: {path}")
            for horizon, target in sorted(targets.items()):
                outcome_path = _record_path(outcome_root, forecast["forecast_hash"], symbol, horizon)
                score_path = _record_path(score_root, forecast["forecast_hash"], symbol, horizon)
                available_at = _availability(target)
                if score_path.exists():
                    score = load_score(score_path)
                    if score["forecast_hash"] != forecast["forecast_hash"]:
                        raise ValueError("Score points to a different forecast")
                    state = "SCORED"
                elif outcome_path.exists():
                    outcome = load_outcome(outcome_path)
                    if outcome["forecast_hash"] != forecast["forecast_hash"]:
                        raise ValueError("Outcome points to a different forecast")
                    state = "READY"
                elif cutoff >= available_at:
                    state = "WAITING_FOR_DATA"
                else:
                    state = "NOT_DUE"
                rows.append({
                    "state": state,
                    "forecast_hash": forecast["forecast_hash"],
                    "forecast_path": str(path.resolve()),
                    "symbol": symbol,
                    "horizon_sessions": horizon,
                    "origin_session": issued["origin_session"],
                    "target_session": target,
                    "available_at": available_at.isoformat(),
                    "outcome_path": str(outcome_path.resolve()),
                    "score_path": str(score_path.resolve()),
                })
    counts = {state: sum(row["state"] == state for row in rows)
              for state in ("NOT_DUE", "WAITING_FOR_DATA", "READY", "SCORED")}
    return {"schemaVersion": "meta-evaluation-status-v1", "asOf": cutoff.isoformat(),
            "counts": counts, "records": rows}


def _alpaca_prices(
    symbol: str,
    targets: set[str],
    headers: dict[str, str],
    feed: str,
    now: datetime,
    fetch: Callable[[str, dict | None], bytes],
) -> tuple[str, bytes, dict[str, float]]:
    start = min(targets)
    data_end = now - DATA_DELAY
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars?" + urlencode({
        "timeframe": "1Day", "start": f"{start}T00:00:00Z",
        "end": data_end.isoformat(), "adjustment": "split", "feed": feed,
        "sort": "asc", "limit": 1000,
    })
    raw = fetch(url, headers)
    payload = json.loads(raw)
    if payload.get("symbol") != symbol or payload.get("next_page_token"):
        raise ValueError(f"Incomplete or mismatched Alpaca outcome response for {symbol}")
    closes: dict[str, float] = {}
    for bar in payload.get("bars") or []:
        session = _instant(bar["t"]).astimezone(ZoneInfo("America/New_York")).date().isoformat()
        close = float(bar["c"])
        if not math.isfinite(close) or close <= 0 or session in closes:
            raise ValueError(f"Invalid or duplicate outcome close for {symbol}")
        closes[session] = close
    missing = sorted(targets - closes.keys())
    if missing:
        raise ValueError(f"Alpaca outcome response lacks {symbol} sessions: {','.join(missing)}")
    return url, raw, {target: closes[target] for target in targets}


def capture_due_outcomes(
    forecast_root: Path,
    outcome_root: Path,
    score_root: Path,
    capture_root: Path,
    now: datetime | None = None,
    *,
    fetch: Callable[[str, dict | None], bytes] = get_raw,
    environ: dict[str, str] | None = None,
) -> dict:
    captured_at = _instant(now or datetime.now(timezone.utc))
    state = evaluation_status(forecast_root, outcome_root, score_root, captured_at)
    waiting = [row for row in state["records"] if row["state"] == "WAITING_FOR_DATA"]
    if not waiting:
        return {"status": "NOT_DUE", "captured": 0, "evaluation": state}
    env = environ if environ is not None else os.environ
    key, secret = env.get("APCA_API_KEY_ID"), env.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise ValueError("Alpaca credentials are required to acquire due META outcomes")
    feed = env.get("ALPACA_DATA_FEED", "sip")
    if feed not in {"sip", "iex"}:
        raise ValueError("ALPACA_DATA_FEED must be sip or iex; no silent feed fallback")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    targets_by_symbol: dict[str, set[str]] = {}
    for row in waiting:
        targets_by_symbol.setdefault(row["symbol"], set()).add(row["target_session"])
    downloads = {symbol: _alpaca_prices(symbol, targets, headers, feed, captured_at, fetch)
                 for symbol, targets in sorted(targets_by_symbol.items())}

    run = create_immutable_run_directory(capture_root, "capture")
    (run / "raw").mkdir()
    sources = {}
    for symbol, (url, raw, _) in downloads.items():
        raw_path = run / "raw" / f"{symbol}.json"
        write_bytes_exclusive(raw_path, raw)
        sources[symbol] = {"url": url, "path": str(raw_path.resolve()),
                           "sha256": file_sha256(raw_path), "feed": feed,
                           "adjustment": "split;cash-dividends-excluded"}
    written = []
    for row in waiting:
        forecast = load_forecast(Path(row["forecast_path"]))
        issued = forecast["symbols"][row["symbol"]]
        close = downloads[row["symbol"]][2][row["target_session"]]
        origin_close = float(issued["origin_close"])
        core = {
            "schemaVersion": OUTCOME_VERSION,
            "forecast_hash": forecast["forecast_hash"],
            "forecast_path": row["forecast_path"],
            "symbol": row["symbol"],
            "horizon_sessions": row["horizon_sessions"],
            "origin_session": row["origin_session"],
            "target_session": row["target_session"],
            "origin_close": origin_close,
            "target_close": close,
            "simple_return": close / origin_close - 1,
            "log_return": math.log(close / origin_close),
            "available_at": row["available_at"],
            "captured_at": captured_at.isoformat(),
            "price_convention": "terminal split-adjusted close; cash dividends excluded",
            "source": sources[row["symbol"]],
        }
        core["outcome_hash"] = digest(core)
        path = Path(row["outcome_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_exclusive(path, core)
        written.append({"path": str(path.resolve()), "outcome_hash": core["outcome_hash"]})
    manifest = {"schemaVersion": CAPTURE_VERSION, "capturedAt": captured_at.isoformat(),
                "sources": sources, "outcomes": written}
    manifest["capture_hash"] = digest(manifest)
    manifest_path = run / "manifest.json"
    write_json_exclusive(manifest_path, manifest)
    return {"status": "CAPTURED", "captured": len(written),
            "manifestPath": str(manifest_path.resolve()), "outcomes": written}


def _pinball(actual: float, forecast: float, quantile: float) -> float:
    error = actual - forecast
    return (quantile if error >= 0 else quantile - 1) * error


def _lognormal_crps(actual: float, median: float, q90: float) -> float | None:
    sigma = math.log(q90 / median) / NormalDist().inv_cdf(.9)
    if sigma <= 0:
        return None
    standard = NormalDist()
    z = math.log(actual / median) / sigma
    mean = median * math.exp(sigma * sigma / 2)
    return actual * (2 * standard.cdf(z) - 1) - 2 * mean * (
        standard.cdf(z - sigma) + standard.cdf(sigma / math.sqrt(2)) - 1
    )


def _score_scenario(scenario: dict, outcome: dict) -> dict:
    threshold = float(scenario["return_threshold_pct"]) / 100
    realized = float(outcome["simple_return"])
    actual_class = "bear" if realized <= -threshold else "bull" if realized >= threshold else "neutral"
    probabilities = {key: float(scenario["probabilities"][key])
                     for key in ("bear", "neutral", "bull")}
    if not math.isclose(sum(probabilities.values()), 1, abs_tol=1e-12):
        raise ValueError("Forecast event probabilities do not sum to one")
    event_brier = sum((probabilities[key] - (key == actual_class)) ** 2 for key in probabilities)
    event_log_loss = -math.log(max(probabilities[actual_class], 1e-15))
    probability_up = float(scenario["probability_price_up"])
    actual_up = realized > 0
    quantiles = {float(key): float(value) for key, value in scenario["price_quantiles"].items()}
    if sorted(quantiles) != list(quantiles) or any(not 0 < q < 1 for q in quantiles):
        raise ValueError("Forecast price quantiles are invalid or unordered")
    target_close = float(outcome["target_close"])
    pinball = {str(q): _pinball(target_close, value, q) for q, value in quantiles.items()}
    median = quantiles[.5]
    direction_call = "UP" if probability_up > .5 else "DOWN" if probability_up < .5 else "NO_CALL"
    return {
        "actual": {"target_close": target_close, "simple_return": realized,
                   "log_return": float(outcome["log_return"]), "event_class": actual_class,
                   "price_up": actual_up},
        "event_scores": {"multiclass_brier": event_brier, "log_loss": event_log_loss,
                         "probabilities": probabilities},
        "direction_scores": {"probability_up": probability_up,
                             "brier": (probability_up - float(actual_up)) ** 2,
                             "call": direction_call,
                             "correct": None if direction_call == "NO_CALL" else
                             (direction_call == ("UP" if actual_up else "DOWN"))},
        "distribution_scores": {
            "median_absolute_error": abs(target_close - median),
            "median_absolute_percentage_error": abs(target_close / median - 1),
            "pinball_by_quantile": pinball,
            "mean_pinball": sum(pinball.values()) / len(pinball),
            "covered_central_80": quantiles[.1] <= target_close <= quantiles[.9],
            "covered_central_90": quantiles[.05] <= target_close <= quantiles[.95],
            "central_80_range_miss": max(quantiles[.1] - target_close, 0,
                                         target_close - quantiles[.9]),
            "lognormal_crps": _lognormal_crps(target_close, median, quantiles[.9])
                if (scenario.get("distribution_family") == "LOG_RETURN_NORMAL"
                    or scenario.get("formula", "").startswith("log(P_h/P_0) ~ Normal")) else None,
        },
    }


def score_record(forecast: dict, outcome: dict, scored_at: datetime) -> dict:
    symbol, horizon = outcome["symbol"], int(outcome["horizon_sessions"])
    issued = forecast["symbols"][symbol]
    matches = [row for row in issued["quantitative_reference"]
               if int(row["trading_days"]) == horizon]
    if len(matches) != 1:
        raise ValueError("Expected one quantitative scenario for outcome")
    if (outcome.get("forecast_hash") != forecast["forecast_hash"]
            or outcome["origin_session"] != issued["origin_session"]
            or outcome["target_session"] != issued["target_sessions"][str(horizon)]
            or outcome.get("origin_close", issued["origin_close"]) != issued["origin_close"]):
        raise ValueError("Outcome is incompatible with forecast origin/target")
    baseline = _score_scenario(matches[0], outcome)
    variants = {"quantitative_reference": baseline}
    recommendations = {}
    variant_metadata = {}
    structured = [row for row in issued.get("structured_meta_forecast", [])
                  if int(row.get("trading_days", -1)) == horizon
                  and row.get("status") == "EXPERIMENTAL_UNCALIBRATED"]
    if len(structured) > 1:
        raise ValueError("Duplicate structured META horizon")
    if structured:
        row = structured[0]
        reference = row.get("reference", {})
        if reference and (reference.get("reference_price_basis") != "LATEST_COMPLETED_SESSION_CLOSE"
                or reference.get("reference_price") != issued["origin_close"]
                or reference.get("origin_session", issued["origin_session"]) != issued["origin_session"]
                or reference.get("target_trading_session") != outcome["target_session"]
                or reference.get("return_basis", "PRICE_RETURN") != "PRICE_RETURN"):
            raise ValueError("Cannot pair incompatible forecast target/reference")
        variant_name = row["distribution"].get("variant", "experimental_meta_v1")
        variants[variant_name] = _score_scenario(row["distribution"], outcome)
        recommendations[variant_name] = row["recommendation"]
        variant_metadata[variant_name] = {
            "origin_kind": reference.get("origin_kind", "LEGACY_COMPLETED_CLOSE"),
            "target_contract": reference.get("contract_version", "LEGACY"),
            "return_basis": reference.get("return_basis", "PRICE_RETURN"),
            "model_usage": row.get("model_usage", "LEGACY_UNKNOWN"),
        }
        for label, scenario in sorted(row.get("ablations", {}).items()):
            if label in variants:
                raise ValueError("Ablation cannot replace a primary comparison variant")
            variants[label] = _score_scenario(scenario, outcome)
    recommendation_scores = {}
    for label, recommendation in recommendations.items():
        action = recommendation.get("action_now", recommendation.get("action"))
        call = ("UP" if action in {"BULLISH_RESEARCH", "ACCUMULATE_CONDITIONALLY"} else
                "DOWN" if action in {"BEARISH_RESEARCH", "REDUCE_RISK"} else "NO_CALL")
        actual_up = float(outcome["simple_return"]) > 0
        recommendation_scores[label] = {
            "action": action, "call": call,
            "correct": None if call == "NO_CALL" else call == ("UP" if actual_up else "DOWN"),
            "realized_simple_return": float(outcome["simple_return"]),
        }
    core = {
        "schemaVersion": SCORE_VERSION,
        "forecast_hash": forecast["forecast_hash"],
        "outcome_hash": outcome["outcome_hash"],
        "symbol": symbol,
        "horizon_sessions": horizon,
        "origin_session": outcome["origin_session"],
        "target_session": outcome["target_session"],
        "scored_at": scored_at.isoformat(),
        "actual": baseline["actual"],
        "event_scores": baseline["event_scores"],
        "direction_scores": baseline["direction_scores"],
        "distribution_scores": baseline["distribution_scores"],
        "variant_scores": variants,
        "variant_metadata": variant_metadata,
        "recommendations": recommendations,
        "recommendation_scores": recommendation_scores,
        "governance_cohort_id": (forecast.get("governance") or {}).get("cohort_id"),
        "qualification_criteria": (forecast.get("governance") or {}).get("prospective_qualification"),
        "qualification_notice": "Descriptive prospective score; overlapping horizons require origin-clustered/time-block uncertainty and do not establish skill.",
    }
    core["score_hash"] = digest(core)
    return core


def _aggregate(score_root: Path) -> dict:
    scores = [load_score(path) for path in sorted(score_root.glob("*/*.json"))]
    groups = {}
    for label, rows in [("all", scores), *[(str(h), [s for s in scores if s["horizon_sessions"] == h])
                                             for h in (5, 21, 63)]]:
        if not rows:
            continue
        called = [r for r in rows if r["direction_scores"]["correct"] is not None]
        groups[label] = {
            "count": len(rows),
            "mean_multiclass_brier": sum(r["event_scores"]["multiclass_brier"] for r in rows) / len(rows),
            "mean_log_loss": sum(r["event_scores"]["log_loss"] for r in rows) / len(rows),
            "mean_direction_brier": sum(r["direction_scores"]["brier"] for r in rows) / len(rows),
            "direction_accuracy_when_called": (sum(r["direction_scores"]["correct"] for r in called) / len(called)
                                                if called else None),
            "central_80_coverage": sum(r["distribution_scores"]["covered_central_80"] for r in rows) / len(rows),
            "central_90_coverage": sum(r["distribution_scores"]["covered_central_90"] for r in rows) / len(rows),
            "mean_median_absolute_percentage_error": sum(
                r["distribution_scores"]["median_absolute_percentage_error"] for r in rows) / len(rows),
            "calibration": {event: {"mean_probability": sum(r["event_scores"]["probabilities"][event] for r in rows) / len(rows),
                                     "observed_frequency": sum(r["actual"]["event_class"] == event for r in rows) / len(rows)}
                            for event in ("bear", "neutral", "bull")},
        }
    variant_groups = {}
    labels = sorted({label for score in scores for label in score.get("variant_scores", {})})
    for label in labels:
        rows = [(score, score["variant_scores"][label]) for score in scores
                if label in score.get("variant_scores", {})]
        called = [metrics for _, metrics in rows if metrics["direction_scores"]["correct"] is not None]
        variant_groups[label] = {
            "count": len(rows),
            "mean_multiclass_brier": sum(metrics["event_scores"]["multiclass_brier"] for _, metrics in rows) / len(rows),
            "mean_log_loss": sum(metrics["event_scores"]["log_loss"] for _, metrics in rows) / len(rows),
            "mean_direction_brier": sum(metrics["direction_scores"]["brier"] for _, metrics in rows) / len(rows),
            "direction_accuracy_when_called": (sum(metrics["direction_scores"]["correct"] for metrics in called) / len(called)
                                                if called else None),
            "central_80_coverage": sum(metrics["distribution_scores"]["covered_central_80"] for _, metrics in rows) / len(rows),
            "mean_pinball": sum(metrics["distribution_scores"]["mean_pinball"] for _, metrics in rows) / len(rows),
        }
    paired_groups = {}
    for score in scores:
        variants = score.get("variant_scores", {})
        if "quantitative_reference" not in variants:
            continue
        for variant in variants:
            if not variant.startswith("experimental_meta_v") or "_without_" in variant:
                continue
            metadata = score.get("variant_metadata", {}).get(variant, {})
            key = json.dumps([score.get("governance_cohort_id") or "LEGACY_UNSPECIFIED",
                              score["horizon_sessions"], variant,
                              metadata.get("origin_kind", "LEGACY_COMPLETED_CLOSE"),
                              metadata.get("target_contract", "LEGACY"),
                              metadata.get("return_basis", "PRICE_RETURN"),
                              metadata.get("model_usage", "LEGACY_UNKNOWN")])
            paired_groups.setdefault(key, []).append((score, variant))
    comparisons = {}
    for key, rows in paired_groups.items():
        origins = {score["origin_session"] for score, _ in rows}
        comparisons[key] = {
            "identity": json.loads(key), "count": len(rows), "distinct_origins": len(origins),
            "mean_meta_minus_reference_multiclass_brier": sum(
                score["variant_scores"][variant]["event_scores"]["multiclass_brier"]
                - score["variant_scores"]["quantitative_reference"]["event_scores"]["multiclass_brier"]
                for score, variant in rows) / len(rows),
            "mean_meta_minus_reference_direction_brier": sum(
                score["variant_scores"][variant]["direction_scores"]["brier"]
                - score["variant_scores"]["quantitative_reference"]["direction_scores"]["brier"]
                for score, variant in rows) / len(rows),
            "interpretation": "Descriptive paired deltas only; dependence-aware uncertainty is required.",
        }
    comparison = (next(iter(comparisons.values())) if len(comparisons) == 1 else {
        "count": 0, "mean_meta_minus_reference_multiclass_brier": None,
        "mean_meta_minus_reference_direction_brier": None,
        "interpretation": "Select one cohort/horizon/variant/origin/model-usage group; incompatible groups are not pooled.",
    })
    recommendation_rows = [row for score in scores
                           for row in score.get("recommendation_scores", {}).values()]
    called_recommendations = [row for row in recommendation_rows if row["correct"] is not None]
    recommendation_summary = {
        "count": len(recommendation_rows), "called": len(called_recommendations),
        "accuracy_when_called": (sum(row["correct"] for row in called_recommendations)
                                 / len(called_recommendations) if called_recommendations else None),
        "by_action": {action: {
            "count": sum(row["action"] == action for row in recommendation_rows),
            "mean_realized_return": (sum(row["realized_simple_return"] for row in recommendation_rows
                                          if row["action"] == action)
                                     / sum(row["action"] == action for row in recommendation_rows))}
            for action in sorted({row["action"] for row in recommendation_rows})},
        "notice": "Research-action outcomes are descriptive and exclude sizing, costs and path-dependent risk.",
    }
    cohorts = {}
    for cohort in sorted({score.get("governance_cohort_id") for score in scores
                          if score.get("governance_cohort_id")}):
        rows = [score for score in scores if score.get("governance_cohort_id") == cohort]
        criteria = next((score.get("qualification_criteria") for score in rows
                         if score.get("qualification_criteria")), None)
        origins = {score["origin_session"] for score in rows}
        horizon_counts = {str(horizon): sum(score["horizon_sessions"] == horizon for score in rows)
                          for horizon in (5, 21, 63)}
        qualified = bool(criteria and len(rows) >= criteria["minimum_scored_records"]
                         and len(origins) >= criteria["minimum_distinct_origins"]
                         and all(count >= criteria["minimum_records_per_horizon"]
                                 for count in horizon_counts.values()))
        cohorts[cohort] = {
            "scored_records": len(rows), "distinct_origins": len(origins),
            "records_per_horizon": horizon_counts, "criteria": criteria,
            "paired_comparisons": {key: value for key, value in comparisons.items()
                                   if value["identity"][0] == cohort},
            "qualification_status": ("SAMPLE_SIZE_GATE_PASSED_REQUIRES_STATISTICAL_REVIEW"
                                     if qualified else "INSUFFICIENT_PROSPECTIVE_SAMPLE"),
            "overlap_control": "Treat origin sessions as dependence clusters; use time-block inference before qualification.",
        }
    return {"scoreCount": len(scores), "groups": groups,
            "variantGroups": variant_groups, "pairedMetaVsReference": comparison,
            "pairedComparisons": comparisons,
            "recommendationOutcomes": recommendation_summary,
            "governanceCohorts": cohorts,
            "notice": "Descriptive only; no minimum sample size or independence claim is implied."}


def score_ready_outcomes(
    forecast_root: Path,
    outcome_root: Path,
    score_root: Path,
    report_root: Path,
    now: datetime | None = None,
) -> dict:
    scored_at = _instant(now or datetime.now(timezone.utc))
    state = evaluation_status(forecast_root, outcome_root, score_root, scored_at)
    ready = [row for row in state["records"] if row["state"] == "READY"]
    if not ready:
        return {"status": "NOT_READY", "scored": 0, "evaluation": state}
    written = []
    for row in ready:
        forecast = load_forecast(Path(row["forecast_path"]))
        outcome = load_outcome(Path(row["outcome_path"]))
        score = score_record(forecast, outcome, scored_at)
        path = Path(row["score_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_exclusive(path, score)
        written.append({"path": str(path.resolve()), "score_hash": score["score_hash"]})
    run = create_immutable_run_directory(report_root, "score")
    summary = {"schemaVersion": "meta-score-summary-v1", "scoredAt": scored_at.isoformat(),
               "newScores": written, "aggregate": _aggregate(score_root)}
    summary["summary_hash"] = digest(summary)
    summary_path = run / "summary.json"
    write_json_exclusive(summary_path, summary)
    return {"status": "SCORED", "scored": len(written),
            "summaryPath": str(summary_path.resolve()), "scores": written}


def update(
    forecast_root: Path,
    outcome_root: Path,
    score_root: Path,
    capture_root: Path,
    report_root: Path,
    now: datetime | None = None,
) -> dict:
    instant = _instant(now or datetime.now(timezone.utc))
    capture_result = capture_due_outcomes(
        forecast_root, outcome_root, score_root, capture_root, instant
    )
    score_result = score_ready_outcomes(
        forecast_root, outcome_root, score_root, report_root, instant
    )
    final = evaluation_status(forecast_root, outcome_root, score_root, instant)
    pending = [row["available_at"] for row in final["records"] if row["state"] == "NOT_DUE"]
    return {"status": "UPDATED",
            "capture": {key: value for key, value in capture_result.items() if key != "evaluation"},
            "score": {key: value for key, value in score_result.items() if key != "evaluation"},
            "evaluation": {"asOf": final["asOf"], "counts": final["counts"],
                           "nextAvailableAt": min(pending) if pending else None}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "capture", "score", "update"))
    parser.add_argument("--forecasts", type=Path, default=ROOT / "datasets/meta-observation/forecasts")
    parser.add_argument("--outcomes", type=Path, default=ROOT / "datasets/meta-observation/outcomes")
    parser.add_argument("--scores", type=Path, default=ROOT / "datasets/meta-observation/scores")
    parser.add_argument("--captures", type=Path, default=ROOT / "datasets/meta-observation/outcome-captures")
    parser.add_argument("--reports", type=Path, default=ROOT / "reports/meta-observation")
    parser.add_argument("--now", type=datetime.fromisoformat)
    args = parser.parse_args()
    now = args.now or datetime.now(timezone.utc)
    if args.action == "status":
        result = evaluation_status(args.forecasts, args.outcomes, args.scores, now)
    elif args.action == "capture":
        result = capture_due_outcomes(args.forecasts, args.outcomes, args.scores, args.captures, now)
    elif args.action == "score":
        result = score_ready_outcomes(args.forecasts, args.outcomes, args.scores, args.reports, now)
    else:
        result = update(args.forecasts, args.outcomes, args.scores, args.captures, args.reports, now)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
