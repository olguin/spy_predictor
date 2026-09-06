"""Sealed-confirmation target tournament over the Phase 1 market dataset."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime, time as wall_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator

from spy_predictor_quant.market_archive import content_hash, file_sha256
from spy_predictor_quant.phase1_config import Phase1Plan
from spy_predictor_quant.tournament import (
    LABELS,
    Bar,
    Observation,
    model_probability,
    realized_volatility,
    summarize_predictions,
)


MODELS = (
    "historical-frequency",
    "always-up",
    "always-down",
    "random-calibrated",
    "overnight-continuation",
    "overnight-reversal",
    "momentum",
    "mean-reversion",
    "logistic-l2",
    "tree-depth-3",
)


def run_phase1_tournament(
    *,
    plan: Phase1Plan,
    dataset_manifest_path: Path,
    comparison_path: Path,
    repo_root: Path,
) -> tuple[Path, dict[str, Any]]:
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    bars = load_phase1_bars(dataset_manifest, repo_root)
    grouped_bars: dict[str, list[Bar]] = defaultdict(list)
    for bar in bars:
        grouped_bars[bar.symbol].append(bar)

    results: dict[str, Any] = {}
    for instrument in ("SPY", "QQQ", "ES", "NQ"):
        observations, coverage = build_phase1_observations(
            instrument,
            grouped_bars[instrument],
            plan.tournament,
        )
        grouped_observations: dict[str, list[Observation]] = defaultdict(list)
        for observation in observations:
            grouped_observations[observation.horizon].append(observation)
        for horizon in plan.tournament["horizons"]:
            values = grouped_observations[horizon]
            results[f"{instrument}/{horizon}"] = evaluate_phase1_candidate(
                values,
                coverage[horizon],
                plan.tournament,
                dataset_manifest,
                comparison,
            )

    eligible = [
        (key, value)
        for key, value in results.items()
        if value["promotion"]["passed"]
    ]
    eligible.sort(
        key=lambda item: (
            -float(item[1]["promotion"]["selectionBrierImprovement"]),
            item[0],
        )
    )
    selected_key = eligible[0][0] if eligible else None
    target_definition = (
        _target_definition(selected_key, plan.tournament) if selected_key else None
    )
    source_hash = research_source_hash(repo_root)
    report_core: dict[str, Any] = {
        "schemaVersion": "target-tournament-report-v2",
        "datasetVersion": dataset_manifest["datasetVersion"],
        "datasetIdentityHash": dataset_manifest["datasetIdentityHash"],
        "datasetManifestSha256": file_sha256(dataset_manifest_path),
        "comparisonHash": comparison["comparisonHash"],
        "configHash": plan.config_hash,
        "researchSourceHash": source_hash,
        "noLlmCalls": True,
        "noOrderSubmission": True,
        "provenance": dataset_manifest["provenance"],
        "targetSemantics": _target_semantics(),
        "hypothesesEvaluated": len(results),
        "decision": "FREEZE_TARGET" if selected_key else "NO_TARGET_ADEQUATE",
        "decisionReason": (
            f"All preregistered gates passed for {selected_key}."
            if selected_key
            else "No instrument/horizon candidate passed every preregistered gate on the sealed confirmation sample."
        ),
        "selectedCandidate": selected_key,
        "targetDefinition": target_definition,
        "results": results,
    }
    report_hash = content_hash(report_core)
    report = {**report_core, "reportHash": report_hash}
    schema = json.loads(
        (repo_root / "schemas" / "target-tournament-report-v2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(report)
    report_root = repo_root / "reports" / f"phase1-{report_hash[:16]}"
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "report.json"
    _write_or_verify(
        report_path,
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    markdown_path = report_root / "report.md"
    _write_or_verify(markdown_path, render_phase1_markdown(report).encode("utf-8"))
    return report_path, report


def load_phase1_bars(
    manifest: dict[str, Any], repo_root: Path
) -> list[Bar]:
    path = repo_root / manifest["normalizedBars"]["path"]
    expected_hash = manifest["normalizedBars"]["sha256"]
    if file_sha256(path) != expected_hash:
        raise ValueError(f"Phase 1 normalized bar hash mismatch for {path}")
    bars: list[Bar] = []
    previous_key: tuple[str, str] | None = None
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            record_hash = record.pop("hash", None)
            if record_hash != content_hash(record):
                raise ValueError(f"Market bar record hash mismatch at {path}:{line_number}")
            key = (str(record["instrument"]), str(record["eventTime"]))
            if previous_key is not None and key <= previous_key:
                raise ValueError(f"Market bars are not strictly sorted at {path}:{line_number}")
            previous_key = key
            bars.append(
                Bar(
                    symbol=str(record["instrument"]),
                    timestamp=datetime.fromisoformat(str(record["eventTime"])),
                    open=float(record["open"]),
                    high=float(record["high"]),
                    low=float(record["low"]),
                    close=float(record["close"]),
                    volume=float(record["volume"]),
                    contract_ticker=(
                        str(record["contractTicker"])
                        if record.get("contractTicker")
                        else None
                    ),
                    session_date=str(record["sessionDate"]),
                )
            )
    if len(bars) != manifest["normalizedBars"]["records"]:
        raise ValueError("Phase 1 normalized bar count mismatch")
    return bars


def build_phase1_observations(
    instrument: str,
    bars: list[Bar],
    config: dict[str, Any],
) -> tuple[list[Observation], dict[str, dict[str, Any]]]:
    sessions: dict[str, dict[wall_time, Bar]] = defaultdict(dict)
    for bar in bars:
        if bar.session_date is None:
            raise ValueError("Phase 1 bar is missing session_date")
        local_time = bar.timestamp.astimezone(ZoneInfo("America/New_York"))
        key = local_time.timetz().replace(tzinfo=None)
        if key in sessions[bar.session_date]:
            raise ValueError(
                f"Duplicate research-session bar for {instrument} {bar.session_date} {key}"
            )
        sessions[bar.session_date][key] = bar
    dates = sorted(sessions)
    horizons = list(config["horizons"])
    coverage: dict[str, dict[str, Any]] = {
        horizon: {"expected": 0, "observed": 0, "missingSample": []}
        for horizon in horizons
    }
    observations: list[Observation] = []
    ewma_variance = 0.0
    threshold = float(config["neutralThreshold"])
    for index in range(1, len(dates)):
        previous_date = dates[index - 1]
        current_date = dates[index]
        previous = sessions[previous_date]
        current = sessions[current_date]
        following = sessions[dates[index + 1]] if index + 1 < len(dates) else None
        previous_start = previous.get(wall_time(9, 30))
        previous_close = previous.get(wall_time(15, 59))
        current_start = current.get(wall_time(9, 30))
        current_close = current.get(wall_time(15, 59))
        base_ready = all(
            value is not None
            for value in (previous_start, previous_close, current_start, current_close)
        )
        same_previous_contract = _same_contract(previous_close, current_start)
        if base_ready:
            assert previous_start and previous_close and current_start and current_close
            previous_return = math.log(previous_close.close / previous_start.close)
            ewma_variance = (
                0.94 * ewma_variance + 0.06 * previous_return * previous_return
            )
            overnight = math.log(current_start.close / previous_close.close)
            base_features = (
                overnight,
                previous_return,
                abs(previous_return),
                math.sqrt(ewma_variance),
            )
        else:
            previous_return = overnight = 0.0
            base_features = (0.0, 0.0, 0.0, math.sqrt(ewma_variance))

        endpoint_times = {
            "open-15m": wall_time(9, 44),
            "open-30m": wall_time(9, 59),
            "open-60m": wall_time(10, 29),
            "open-close": wall_time(15, 59),
        }
        for horizon, endpoint_time in endpoint_times.items():
            coverage[horizon]["expected"] += int(same_previous_contract)
            endpoint = current.get(endpoint_time)
            if not base_ready or not same_previous_contract or endpoint is None:
                _missing(coverage[horizon], current_date)
                continue
            assert current_start
            target_bars = [
                bar
                for timestamp, bar in sorted(current.items())
                if wall_time(9, 30) <= timestamp <= endpoint_time
            ]
            observations.append(
                _observation(
                    instrument,
                    horizon,
                    current_date,
                    current_start.close,
                    endpoint.close,
                    target_bars,
                    base_features,
                    threshold,
                )
            )
            coverage[horizon]["observed"] += 1

        horizon = "previous-close-next-open"
        coverage[horizon]["expected"] += int(same_previous_contract)
        if not base_ready or not same_previous_contract:
            _missing(coverage[horizon], current_date)
        else:
            assert previous_close and current_start
            observations.append(
                _observation(
                    instrument,
                    horizon,
                    current_date,
                    previous_close.close,
                    current_start.open,
                    [previous_close, current_start],
                    (0.0, previous_return, abs(previous_return), math.sqrt(ewma_variance)),
                    threshold,
                )
            )
            coverage[horizon]["observed"] += 1

        horizon = "close-next-close"
        following_close = following.get(wall_time(15, 59)) if following else None
        same_following_contract = _same_contract(current_close, following_close)
        structurally_expected = same_previous_contract and same_following_contract
        coverage[horizon]["expected"] += int(structurally_expected)
        if (
            not base_ready
            or following_close is None
            or not structurally_expected
        ):
            _missing(coverage[horizon], current_date)
        else:
            assert current_start and current_close
            current_return = math.log(current_close.close / current_start.close)
            observations.append(
                _observation(
                    instrument,
                    horizon,
                    current_date,
                    current_close.close,
                    following_close.close,
                    [current_close, following_close],
                    (
                        overnight,
                        current_return,
                        abs(current_return),
                        math.sqrt(ewma_variance),
                    ),
                    threshold,
                )
            )
            coverage[horizon]["observed"] += 1

    for value in coverage.values():
        expected = value["expected"]
        value["percent"] = value["observed"] / expected * 100 if expected else 0.0
    return observations, coverage


def evaluate_phase1_candidate(
    observations: list[Observation],
    coverage: dict[str, Any],
    config: dict[str, Any],
    dataset_manifest: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    observations = sorted(observations, key=lambda item: item.date)
    if not observations:
        raise ValueError("Every Phase 1 candidate must have observations")
    instrument = observations[0].symbol
    predictions, volatility = _walk_forward(observations, config)
    confirmation_count = int(config["confirmationObservations"])
    summaries: dict[str, Any] = {}
    for mode in ("expanding", "rolling"):
        summaries[mode] = {"directional": {}, "volatility": {}}
        for model, values in predictions[mode].items():
            selection = values[:-confirmation_count]
            confirmation = values[-confirmation_count:]
            summaries[mode]["directional"][model] = {
                "full": summarize_predictions(values, _cost(config, instrument), False),
                "selection": summarize_predictions(selection, _cost(config, instrument), False),
                "confirmation": summarize_predictions(confirmation, _cost(config, instrument), False),
            }
        for model, values in volatility[mode].items():
            summaries[mode]["volatility"][model] = {
                "full": _summarize_volatility(values),
                "selection": _summarize_volatility(values[:-confirmation_count]),
                "confirmation": _summarize_volatility(values[-confirmation_count:]),
            }

    eligible_models = list(config["promotion"]["eligibleModels"])
    selection_summaries = summaries["expanding"]["directional"]
    champion = min(
        eligible_models,
        key=lambda model: selection_summaries[model]["selection"]["brierScore"],
    )
    baseline = "historical-frequency"
    selection_improvement = (
        selection_summaries[baseline]["selection"]["brierScore"]
        - selection_summaries[champion]["selection"]["brierScore"]
    )
    promotion = _promotion_gates(
        instrument,
        champion,
        predictions,
        summaries,
        coverage,
        config,
        dataset_manifest,
        comparison,
    )
    promotion["selectionBrierImprovement"] = selection_improvement
    label_counts = {
        label: sum(item.label == label for item in observations) for label in LABELS
    }
    return {
        "totalObservations": len(observations),
        "dateRange": [observations[0].date, observations[-1].date],
        "labelCounts": label_counts,
        "coverage": coverage,
        "evaluation": summaries,
        "promotion": promotion,
    }


def _walk_forward(
    observations: list[Observation], config: dict[str, Any]
) -> tuple[
    dict[str, dict[str, list[dict[str, Any]]]],
    dict[str, dict[str, list[tuple[float, float]]]],
]:
    minimum = int(config["minimumTrainingObservations"])
    rolling_window = int(config["rollingWindow"])
    seed = int(config["randomSeed"])
    predictions: dict[str, dict[str, list[dict[str, Any]]]] = {}
    volatility: dict[str, dict[str, list[tuple[float, float]]]] = {}
    for mode in ("expanding", "rolling"):
        predictions[mode] = {model: [] for model in MODELS}
        volatility[mode] = {"historical-mean": [], "ewma": []}
        for index in range(minimum, len(observations)):
            start = 0 if mode == "expanding" else max(0, index - rolling_window)
            train = observations[start:index]
            current = observations[index]
            for model in MODELS:
                probabilities = model_probability(model, train, current, seed)
                predictions[mode][model].append(
                    {
                        "date": current.date,
                        "label": current.label,
                        "return": current.target_return,
                        "realizedVolatility": current.realized_volatility,
                        "probabilities": probabilities.tolist(),
                    }
                )
            vols = [item.realized_volatility for item in train]
            ewma = 0.0
            for value in vols:
                ewma = 0.94 * ewma + 0.06 * value * value
            volatility[mode]["historical-mean"].append(
                (sum(vols) / len(vols), current.realized_volatility)
            )
            volatility[mode]["ewma"].append(
                (math.sqrt(ewma), current.realized_volatility)
            )
    return predictions, volatility


def _promotion_gates(
    instrument: str,
    champion: str,
    predictions: dict[str, dict[str, list[dict[str, Any]]]],
    summaries: dict[str, Any],
    coverage: dict[str, Any],
    config: dict[str, Any],
    dataset_manifest: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    confirmation_count = int(config["confirmationObservations"])
    minimum_confirmation = int(config["minimumConfirmationObservations"])
    promotion = config["promotion"]
    minimum_improvement = float(promotion["minimumBrierImprovement"])
    minimum_incremental_return = float(promotion["minimumIncrementalNetReturn"])
    baseline = "historical-frequency"
    mode_improvements: dict[str, float] = {}
    for mode in ("expanding", "rolling"):
        directional = summaries[mode]["directional"]
        mode_improvements[mode] = (
            directional[baseline]["confirmation"]["brierScore"]
            - directional[champion]["confirmation"]["brierScore"]
        )
    champion_confirmation = summaries["expanding"]["directional"][champion][
        "confirmation"
    ]
    baseline_confirmation = summaries["expanding"]["directional"][baseline][
        "confirmation"
    ]
    confirmation_predictions = predictions["expanding"][champion][
        -confirmation_count:
    ]
    baseline_predictions = predictions["expanding"][baseline][
        -confirmation_count:
    ]
    midpoint = len(confirmation_predictions) // 2
    half_improvements = []
    for start, end in ((0, midpoint), (midpoint, len(confirmation_predictions))):
        champion_half = summarize_predictions(
            confirmation_predictions[start:end], _cost(config, instrument), False
        )
        baseline_half = summarize_predictions(
            baseline_predictions[start:end], _cost(config, instrument), False
        )
        half_improvements.append(
            baseline_half["brierScore"] - champion_half["brierScore"]
        )
    stressed = summarize_predictions(
        confirmation_predictions,
        _cost(config, instrument) * float(config["stressCostMultiplier"]),
        False,
    )
    gates: dict[str, Any] = {
        "provenance": {
            "value": dataset_manifest["provenance"]["targetSelectionAdmissible"],
            "passed": bool(dataset_manifest["provenance"]["targetSelectionAdmissible"]),
        },
        "sample": {
            "threshold": minimum_confirmation,
            "value": champion_confirmation["observations"],
            "passed": champion_confirmation["observations"] >= minimum_confirmation,
        },
        "coverage": {
            "thresholdPercent": float(config["minimumCoveragePercent"]),
            "valuePercent": coverage["percent"],
            "passed": coverage["percent"] >= float(config["minimumCoveragePercent"]),
        },
        "crossProvider": {
            "value": comparison["gates"][instrument]["passed"],
            "passed": bool(comparison["gates"][instrument]["passed"]),
        },
        "liquidity": {
            "medianSessionVolume": dataset_manifest["quality"][instrument]["medianSessionVolume"],
            "passed": dataset_manifest["quality"][instrument]["medianSessionVolume"] > 0,
        },
        "forecastImprovement": {
            "minimumBrierImprovement": minimum_improvement,
            "values": mode_improvements,
            "passed": (
                all(value > minimum_improvement for value in mode_improvements.values())
                if promotion["requireBothWalkForwardModes"]
                else mode_improvements["expanding"] > minimum_improvement
            ),
        },
        "selectionForecastImprovement": {
            "minimumBrierImprovement": minimum_improvement,
            "value": (
                summaries["expanding"]["directional"][baseline]["selection"]["brierScore"]
                - summaries["expanding"]["directional"][champion]["selection"]["brierScore"]
            ),
            "passed": (
                summaries["expanding"]["directional"][baseline]["selection"]["brierScore"]
                - summaries["expanding"]["directional"][champion]["selection"]["brierScore"]
                > minimum_improvement
            ),
        },
        "calibration": {
            "maximumEce": float(promotion["maximumExpectedCalibrationError"]),
            "maximumDegradation": float(promotion["maximumCalibrationDegradation"]),
            "championEce": champion_confirmation["expectedCalibrationError"],
            "baselineEce": baseline_confirmation["expectedCalibrationError"],
            "passed": (
                champion_confirmation["expectedCalibrationError"]
                <= float(promotion["maximumExpectedCalibrationError"])
                and champion_confirmation["expectedCalibrationError"]
                <= baseline_confirmation["expectedCalibrationError"]
                + float(promotion["maximumCalibrationDegradation"])
            ),
        },
        "stability": {
            "confirmationHalfBrierImprovements": half_improvements,
            "passed": (
                all(value > minimum_improvement for value in half_improvements)
                if promotion["requireBothConfirmationHalves"]
                else sum(half_improvements) > 0
            ),
        },
        "economicValue": {
            "netReturnAfterCosts": champion_confirmation["netReturnAfterCosts"],
            "baselineNetReturnAfterCosts": baseline_confirmation["netReturnAfterCosts"],
            "minimumIncrementalNetReturn": minimum_incremental_return,
            "incrementalNetReturn": (
                champion_confirmation["netReturnAfterCosts"]
                - baseline_confirmation["netReturnAfterCosts"]
            ),
            "passed": (
                champion_confirmation["netReturnAfterCosts"] > 0
                and champion_confirmation["netReturnAfterCosts"]
                - baseline_confirmation["netReturnAfterCosts"]
                > minimum_incremental_return
                if promotion["requirePositiveNetReturn"]
                else True
            ),
        },
        "costSensitivity": {
            "stressCostMultiplier": float(config["stressCostMultiplier"]),
            "stressNetReturn": stressed["netReturnAfterCosts"],
            "baselineStressNetReturn": summarize_predictions(
                baseline_predictions,
                _cost(config, instrument) * float(config["stressCostMultiplier"]),
                False,
            )["netReturnAfterCosts"],
            "passed": (
                stressed["netReturnAfterCosts"] > 0
                and stressed["netReturnAfterCosts"]
                - summarize_predictions(
                    baseline_predictions,
                    _cost(config, instrument) * float(config["stressCostMultiplier"]),
                    False,
                )["netReturnAfterCosts"]
                > minimum_incremental_return
                if promotion["requirePositiveStressNetReturn"]
                else True
            ),
        },
    }
    return {
        "championModelSelectedOnSelectionOnly": champion,
        "gates": gates,
        "passed": all(gate["passed"] for gate in gates.values()),
    }


def _observation(
    instrument: str,
    horizon: str,
    session_date: str,
    start_price: float,
    end_price: float,
    bars: list[Bar],
    features: tuple[float, ...],
    threshold: float,
) -> Observation:
    target_return = math.log(end_price / start_price)
    label = "UP" if target_return > threshold else "DOWN" if target_return < -threshold else "NEUTRAL"
    return Observation(
        instrument,
        horizon,
        session_date,
        target_return,
        label,
        realized_volatility(bars),
        features,
    )


def _same_contract(left: Bar | None, right: Bar | None) -> bool:
    if left is None or right is None:
        return False
    return left.contract_ticker == right.contract_ticker


def _missing(coverage: dict[str, Any], session_date: str) -> None:
    sample = coverage["missingSample"]
    if len(sample) < 100:
        sample.append(session_date)


def _summarize_volatility(values: list[tuple[float, float]]) -> dict[str, Any]:
    if not values:
        return {"observations": 0, "mae": None, "rmse": None}
    return {
        "observations": len(values),
        "mae": sum(abs(predicted - actual) for predicted, actual in values) / len(values),
        "rmse": math.sqrt(
            sum((predicted - actual) ** 2 for predicted, actual in values) / len(values)
        ),
    }


def _cost(config: dict[str, Any], instrument: str) -> float:
    return float(config["transactionCostBps"][instrument])


def _target_semantics() -> dict[str, Any]:
    return {
        "schemaVersion": "target-semantics-v2",
        "barTimestamp": "UTC interval start; one-minute close is knowable at eventTime plus one minute",
        "openHorizons": {
            "predictionCutoff": "09:31 America/New_York",
            "targetStart": "09:31 price (09:30 one-minute close)",
            "open-15m": "09:45 price (09:44 one-minute close)",
            "open-30m": "10:00 price (09:59 one-minute close)",
            "open-60m": "10:30 price (10:29 one-minute close)",
            "open-close": "16:00 price (15:59 one-minute close)",
        },
        "previous-close-next-open": {
            "predictionCutoff": "previous 16:00 America/New_York",
            "target": "previous 15:59 bar close to current 09:30 bar open",
        },
        "close-next-close": {
            "predictionCutoff": "current 16:00 America/New_York",
            "target": "current 15:59 bar close to next-session 15:59 bar close",
        },
        "rollHandling": "Observations whose required feature or target prices cross a futures contract roll are excluded.",
    }


def _target_definition(key: str, config: dict[str, Any]) -> dict[str, Any]:
    instrument, horizon = key.split("/", 1)
    return {
        "schemaVersion": "frozen-target-v1",
        "instrument": instrument,
        "horizon": horizon,
        "targetSemanticsVersion": config["targetSemanticsVersion"],
        "neutralThreshold": config["neutralThreshold"],
    }


def research_source_hash(repo_root: Path) -> str:
    listed = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    prefixes = ("apps/", "packages/", "python/src/", "config/", "schemas/")
    root_files = {"package.json", "package-lock.json", "python/pyproject.toml", "uv.lock"}
    paths = sorted(
        path
        for path in listed.split("\0")
        if path and (path.startswith(prefixes) or path in root_files)
    )
    hasher = hashlib.sha256()
    for relative in paths:
        content = (repo_root / relative).read_bytes()
        hasher.update(f"{len(relative)}:{relative}:{len(content)}:".encode("utf-8"))
        hasher.update(content)
    return hasher.hexdigest()


def render_phase1_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# TARGET-TOURNAMENT-001 final report",
        "",
        f"Dataset: `{report['datasetVersion']}`",
        "",
        f"Decision: **{report['decision']}**",
        "",
        report["decisionReason"],
        "",
        "| Candidate | Samples | Confirmation | Coverage | Champion | Passed gates | Result |",
        "|---|---:|---:|---:|---|---:|---|",
    ]
    for key, result in sorted(report["results"].items()):
        promotion = result["promotion"]
        gates = promotion["gates"]
        passed = sum(gate["passed"] for gate in gates.values())
        confirmation = result["evaluation"]["expanding"]["directional"][
            promotion["championModelSelectedOnSelectionOnly"]
        ]["confirmation"]["observations"]
        lines.append(
            f"| {key} | {result['totalObservations']} | {confirmation} | "
            f"{result['coverage']['percent']:.2f}% | "
            f"{promotion['championModelSelectedOnSelectionOnly']} | "
            f"{passed}/{len(gates)} | "
            f"{'PASS' if promotion['passed'] else 'REJECT'} |"
        )
    lines.extend(
        [
            "",
            "The champion model for each target was selected using the selection period only.",
            "All promotion gates were then evaluated on the final sealed chronological sample.",
            "No LLM calls or order-submission code were used.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_or_verify(path: Path, value: bytes) -> None:
    if path.exists():
        if path.read_bytes() != value:
            raise ValueError(f"Immutable tournament artifact mismatch at {path}")
        return
    with path.open("xb") as output:
        output.write(value)
