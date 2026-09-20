"""Preregistered, purged META comparisons. Never writes production forecasts.

All fitted transforms and calibration are confined to training data. The final
period is excluded from development evaluation. Passing an engineering fixture
or a development comparison cannot promote a model.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import NormalDist
import uuid
from zoneinfo import ZoneInfo

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from spy_predictor_quant.market_archive import file_sha256, write_json_exclusive
from spy_predictor_quant.meta_analysis import digest
from spy_predictor_quant.meta_contracts import finite, instant

CANDIDATES = ("historical_frequency", "market_sector", "momentum", "regularized_quant",
              "current_heuristic", "quant_plus_agent")
BASELINES = CANDIDATES[:-1]


def validate_protocol(protocol: dict) -> None:
    version = protocol.get("schema_version")
    if version not in {"meta-experiment-protocol-v1", "meta-experiment-protocol-v2"}:
        raise ValueError("Unsupported experiment protocol")
    if protocol.get("research_mode") not in {None, "QUALIFIED_RESEARCH", "DIAGNOSTIC_REVISED_PRICES"}:
        raise ValueError("Unknown research qualification mode")
    if version == "meta-experiment-protocol-v1" and protocol.get("research_mode") == "DIAGNOSTIC_REVISED_PRICES":
        raise ValueError("Diagnostic data requires a separately registered v2 protocol")
    if version == "meta-experiment-protocol-v1" and (tuple(protocol["candidates"]) != CANDIDATES or protocol["horizons"] != [5, 21, 63]):
        raise ValueError("Candidate set and horizon targets must be preregistered exactly")
    candidates = protocol["candidates"]
    if (len(candidates) < 2 or len(set(candidates)) != len(candidates)
            or not set(candidates) <= set(CANDIDATES)
            or challenger_name(protocol) not in candidates
            or not protocol["horizons"] or len(set(protocol["horizons"])) != len(protocol["horizons"])
            or not set(protocol["horizons"]) <= {5, 21, 63}):
        raise ValueError("Invalid preregistered candidates, challenger or horizons")
    instant(protocol["final_holdout_start"])
    if (protocol["minimum_train_origins"] < 30 or protocol["test_origins_per_fold"] < 1
            or protocol["minimum_effective_blocks"] < 10 or protocol["bootstrap_resamples"] < 200
            or protocol["minimum_material_brier_improvement"] <= 0
            or not 0 < protocol["familywise_alpha"] < .5
            or protocol["max_log_loss_regression"] < 0 or protocol["max_pinball_regression"] < 0):
        raise ValueError("Invalid preregistered statistical or sample requirements")
    if protocol["primary_metric"] != "direction_brier" or protocol["block_length_multiplier"] < 1:
        raise ValueError("Invalid primary metric or overlapping-horizon block length")
    groups = ["quant"] + (["market_sector"] if "market_sector" in candidates else []) + (["agent"] if "quant_plus_agent" in candidates else [])
    for group in groups:
        features = protocol["feature_groups"][group]
        if not features or len(features) != len(set(features)):
            raise ValueError("Feature groups require unique preregistered inputs")
    quant, agent = protocol["feature_groups"]["quant"], protocol["feature_groups"].get("agent", [])
    if set(quant) & set(agent):
        raise ValueError("Quantitative and agent groups must be disjoint")


def challenger_name(protocol: dict) -> str:
    return protocol.get("challenger", "quant_plus_agent")


def baseline_names(protocol: dict) -> list[str]:
    return [name for name in protocol["candidates"] if name != challenger_name(protocol)]


def feasibility(rows: list[dict], protocol: dict) -> dict:
    """Count date/availability metadata only; never read returns or feature values.

    Block-count eligibility is not a power guarantee. The sensitivity grid states
    assumed block-level SDs, rather than estimating them from protected outcomes.
    """
    validate_protocol(protocol)
    alpha = protocol["familywise_alpha"] / (len(baseline_names(protocol)) * len(protocol["horizons"]))
    z = NormalDist().inv_cdf(1 - alpha / 2) + NormalDist().inv_cdf(.8)
    horizons = {}
    for horizon in protocol["horizons"]:
        folds = walk_forward_folds(rows, protocol, horizon)
        dates = {origin_group(row) for _, test in folds for row in test}
        block = horizon * protocol["block_length_multiplier"]
        required = block * protocol["minimum_effective_blocks"]
        effective = len(dates) // block
        horizons[str(horizon)] = {
            "test_origins": len(dates), "folds": len(folds), "block_length_origins": block,
            "effective_blocks": effective, "required_test_origins": required,
            "additional_test_origins_required": max(0, required - len(dates)),
            "status": "BLOCK_COUNT_ELIGIBLE_POWER_NOT_ESTABLISHED" if len(dates) >= required else "INCONCLUSIVE_INSUFFICIENT_BLOCKS",
            "power_sensitivity_80pct": [{"assumed_block_delta_sd": sd,
                "detectable_improvement_beyond_material_threshold": z * sd / math.sqrt(effective) if effective else None,
                "blocks_for_material_sized_excess": math.ceil((z * sd / protocol["minimum_material_brier_improvement"]) ** 2)}
                for sd in (.01, .025, .05, .1)]}
    return {"schema_version": "meta-experiment-feasibility-v1", "protocol_hash": digest(protocol),
            "outcomes_inspected": False, "comparison_alpha": alpha, "horizons": horizons,
            "notice": "Normal-approximation sensitivity under assumed independent block means; neither measured power nor authorization to weaken gates."}


def origin_group(row: dict) -> str:
    return instant(row["origin_at"]).astimezone(ZoneInfo("America/New_York")).date().isoformat()


def validate_panel(rows: list[dict], protocol: dict) -> None:
    identities, contracts = set(), set()
    for row in rows:
        key = (row["symbol"], row["origin_at"], row["horizon_sessions"])
        if key in identities:
            raise ValueError("Duplicate symbol/origin/horizon observation")
        identities.add(key)
        if row["horizon_sessions"] not in protocol["horizons"]:
            raise ValueError("Unexpected panel horizon")
        origin, end = instant(row["origin_at"]), instant(row["label_end_at"])
        from spy_predictor_quant.meta_observation import target_sessions
        import exchange_calendars as xcals
        reference_session = row.get("reference_session")
        if not reference_session:
            raise ValueError("Research panel requires an explicit reference session")
        expected_session = target_sessions(reference_session)[str(row["horizon_sessions"])]
        if end != xcals.get_calendar("XNYS").session_close(expected_session).to_pydatetime():
            raise ValueError("Label timestamp does not match the registered session horizon")
        if (instant(row["feature_available_at"]) > origin
                or instant(row["universe_member_available_at"]) > origin
                or not origin < end <= instant(row["label_available_at"])):
            raise ValueError("Synthetic leakage or invalid label/universe timing detected")
        if not finite(row["simple_return"]) or row["simple_return"] <= -1:
            raise ValueError("Invalid return label")
        diagnostic = protocol.get("research_mode") == "DIAGNOSTIC_REVISED_PRICES"
        expected_availability = "REVISED_HISTORY_DIAGNOSTIC" if diagnostic else "QUALIFIED"
        expected_flags = ["HISTORICAL_PRICE_VINTAGE_UNVERIFIED"] if diagnostic else []
        if row.get("quality_flags") != expected_flags or row.get("availability_status") != expected_availability:
            raise ValueError("Research panel contains unqualified source availability")
        if not isinstance(row.get("feature_snapshot_hash"), str) or len(row["feature_snapshot_hash"]) != 64:
            raise ValueError("Panel must bind a frozen feature snapshot")
        for value in row["features"].values():
            if value is not None and not finite(value):
                raise ValueError("Feature values must be finite or explicitly missing")
        contracts.add((row["origin_kind"], row["return_basis"], row["target_contract"], row["universe_version"]))
    if len(contracts) > 1:
        raise ValueError("Incompatible origins/return bases/targets/universes require separate experiments")


def walk_forward_folds(rows: list[dict], protocol: dict, horizon: int) -> list[tuple[list[dict], list[dict]]]:
    available = [row for row in rows if row["horizon_sessions"] == horizon
                 and instant(row["origin_at"]) < instant(protocol["final_holdout_start"])
                 and instant(row["label_available_at"]) < instant(protocol["final_holdout_start"])]
    # Every instrument at an origin stays in the same partition.
    origins = sorted({origin_group(row) for row in available})
    folds = []
    step = protocol["test_origins_per_fold"]
    for start in range(protocol["minimum_train_origins"], len(origins), step):
        test_origins = set(origins[start:start + step])
        boundary = min(instant(row["origin_at"]) for row in available if origin_group(row) == origins[start])
        train = [row for row in available if origin_group(row) < origins[start]
                 and instant(row["label_available_at"]) < boundary]
        if len({origin_group(row) for row in train}) < protocol["minimum_train_origins"]:
            continue
        test = [row for row in available if origin_group(row) in test_origins]
        folds.append((train, test))
    return folds


def _matrix(rows: list[dict], features: list[str]) -> np.ndarray:
    return np.array([[row["features"].get(name) if row["features"].get(name) is not None else np.nan
                      for name in features] for row in rows], dtype=float)


def _features(candidate: str, protocol: dict) -> list[str]:
    groups = protocol["feature_groups"]
    if candidate == "market_sector":
        return groups["market_sector"]
    if candidate == "momentum":
        return [protocol["momentum_feature"]]
    return groups["quant"] + (groups["agent"] if candidate == "quant_plus_agent" else [])


def fit_predict(candidate: str, train: list[dict], test: list[dict], protocol: dict) -> list[dict]:
    returns = np.array([row["simple_return"] for row in train])
    labels = returns > 0
    frequency = float((labels.sum() + 1) / (len(labels) + 2))
    calibration_status = "NOT_CALIBRATED"
    coefficients = None
    heuristic_distributions = None
    if candidate == "historical_frequency":
        probabilities = np.full(len(test), frequency)
        centers = np.full(len(test), float(np.mean(returns)))
        residuals = returns - np.mean(returns)
    elif candidate == "current_heuristic":
        scores = [row["features"].get(protocol["heuristic_score_feature"]) for row in test]
        if any(not finite(value) for value in scores):
            raise ValueError("Heuristic baseline requires its frozen quantitative score on every paired observation")
        probabilities = np.array([NormalDist().cdf(.35 * max(-1, min(1, value))) for value in scores])
        vols = [row["features"].get(protocol["volatility_feature"]) for row in test]
        if any(not finite(value) or value <= 0 for value in vols):
            raise ValueError("Heuristic baseline requires qualified volatility")
        from spy_predictor_quant.meta_forecast import _distribution
        heuristic_distributions = [_distribution(1, vol, row["horizon_sessions"], score, .35,
                                                 variant="quant_only_heuristic")
                                   for score, vol, row in zip(scores, vols, test)]
        probabilities = np.array([row["probability_price_up"] for row in heuristic_distributions])
        centers = np.array([row["expected_simple_return_pct"] / 100 for row in heuristic_distributions])
        residuals = returns - np.mean(returns)
    else:
        names = _features(candidate, protocol)
        origins = sorted({origin_group(row) for row in train})
        calibration_start = origins[max(1, int(len(origins) * .75))]
        boundary = min(instant(row["origin_at"]) for row in train if origin_group(row) == calibration_start)
        fit = [row for row in train if instant(row["label_available_at"]) < boundary]
        calibrate = [row for row in train if origin_group(row) >= calibration_start]
        if len(fit) < 10 or len({row["simple_return"] > 0 for row in fit}) < 2:
            raise ValueError("Insufficient purged training classes for fitted candidate")
        x, y = _matrix(fit, names), np.array([row["simple_return"] for row in fit])
        if np.isnan(x).all(axis=0).any():
            raise ValueError("A preregistered feature is entirely missing in the training window")
        classifier = make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(),
                                   LogisticRegression(C=1.0, max_iter=1000, random_state=protocol["seed"]))
        regressor = make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(),
                                  Ridge(alpha=1.0))
        classifier.fit(x, y > 0)
        regressor.fit(x, y)
        probabilities = classifier.predict_proba(_matrix(test, names))[:, 1]
        centers = regressor.predict(_matrix(test, names))
        if not calibrate:
            raise ValueError("A trailing training-only calibration window is required")
        calibration_x = _matrix(calibrate, names)
        calibration_returns = np.array([row["simple_return"] for row in calibrate])
        residuals = calibration_returns - regressor.predict(calibration_x)
        if len(calibrate) >= 30 and len(set(calibration_returns > 0)) == 2:
            raw = classifier.decision_function(calibration_x).reshape(-1, 1)
            calibrator = LogisticRegression(C=1.0, max_iter=1000)
            calibrator.fit(raw, calibration_returns > 0)
            probabilities = calibrator.predict_proba(classifier.decision_function(_matrix(test, names)).reshape(-1, 1))[:, 1]
            calibration_status = "TRAINING_ONLY_TEMPORAL_CALIBRATION_EXPERIMENTAL"
        # Exact ridge additive contributions, in return units; never causal percentages.
        transformed = regressor[:-1].transform(_matrix(test, names))
        contributions = transformed * regressor[-1].coef_
        output_names = regressor[0].get_feature_names_out(names).tolist()
        coefficients = [{"intercept": float(regressor[-1].intercept_),
                         "contributions": dict(zip(output_names, map(float, values))),
                         "method": "ADDITIVE_RIDGE_RETURN_UNITS_NOT_CAUSAL"} for values in contributions]
    quantile_levels = [.05, .1, .5, .9, .95]
    residual_quantiles = np.quantile(residuals, quantile_levels)
    result = []
    for index, (row, probability, center) in enumerate(zip(test, probabilities, centers)):
        quantiles = {str(q): max(-.999999, float(center + residual))
                     for q, residual in zip(quantile_levels, residual_quantiles)}
        if heuristic_distributions:
            quantiles = {str(q): heuristic_distributions[index]["price_quantiles"][str(q)] - 1
                         for q in quantile_levels}
        result.append({"symbol": row["symbol"], "origin_at": row["origin_at"],
                       "horizon_sessions": row["horizon_sessions"], "candidate": candidate,
                       "probability_up": float(probability), "expected_return": float(center),
                       "return_quantiles": quantiles, "actual_return": row["simple_return"],
                       "calibration_status": calibration_status,
                       "attribution": coefficients[index] if coefficients else None,
                       "feature_snapshot_hash": row["feature_snapshot_hash"],
                       "training_origins": len({r["origin_at"] for r in train})})
    return result


def score_predictions(predictions: list[dict]) -> dict:
    if not predictions:
        return {"count": 0}
    probabilities = np.array([row["probability_up"] for row in predictions])
    actual = np.array([row["actual_return"] for row in predictions])
    labels = actual > 0
    clipped = np.clip(probabilities, 1e-15, 1 - 1e-15)
    pinball = []
    for row in predictions:
        for q, predicted in row["return_quantiles"].items():
            error = row["actual_return"] - predicted
            pinball.append(max(float(q) * error, (float(q) - 1) * error))
    called = np.abs(probabilities - .5) >= .05
    return {"count": len(predictions), "distinct_origins": len({row["origin_at"] for row in predictions}),
            "direction_brier": float(np.mean((probabilities - labels) ** 2)),
            "log_loss": float(np.mean(-labels.astype(float) * np.log(clipped) - (~labels) * np.log(1 - clipped))),
            "direction_accuracy": float(np.mean((probabilities > .5) == labels)),
            "base_rate_up": float(labels.mean()), "majority_base_rate_accuracy": float(max(labels.mean(), 1-labels.mean())),
            "abstention_coverage": float(called.mean()),
            "accuracy_when_called": float(np.mean((probabilities[called] > .5) == labels[called])) if called.any() else None,
            "mean_pinball": float(np.mean(pinball)),
            "interval_80_coverage": float(np.mean([row["return_quantiles"]["0.1"] <= row["actual_return"] <=
                                                   row["return_quantiles"]["0.9"] for row in predictions])),
            "interval_80_width": float(np.mean([row["return_quantiles"]["0.9"] - row["return_quantiles"]["0.1"]
                                                for row in predictions]))}


def paired_block_comparison(challenger: list[dict], baseline: list[dict], horizon: int, protocol: dict) -> dict:
    key = lambda row: (row["symbol"], row["origin_at"], row["horizon_sessions"])
    left, right = {key(row): row for row in challenger}, {key(row): row for row in baseline}
    if set(left) != set(right) or len(left) != len(challenger) or len(right) != len(baseline):
        raise ValueError("Paired comparison requires exactly the same unique observations")
    by_origin = {}
    for identity, row in left.items():
        actual = row["actual_return"]
        if actual != right[identity]["actual_return"]:
            raise ValueError("Paired outcomes differ")
        difference = (row["probability_up"] - (actual > 0)) ** 2 - (right[identity]["probability_up"] - (actual > 0)) ** 2
        by_origin.setdefault(origin_group(row), []).append(difference)
    deltas = np.array([np.mean(by_origin[origin]) for origin in sorted(by_origin)])
    block = horizon * protocol["block_length_multiplier"]
    effective = len(deltas) // block
    result = {"paired_rows": len(left), "distinct_origins": len(deltas), "block_length_origins": block,
              "effective_blocks": effective,
              "effective_sample_method": "floor(distinct origins / block length); conservative block-count diagnostic, not an independent-row estimate",
              "mean_brier_delta": float(deltas.mean()) if len(deltas) else None,
              "status": "INCONCLUSIVE", "confidence_interval": None}
    if effective < protocol["minimum_effective_blocks"]:
        return result
    rng = np.random.default_rng(protocol["seed"])
    means = []
    for _ in range(protocol["bootstrap_resamples"]):
        starts = rng.integers(0, len(deltas) - block + 1, size=math.ceil(len(deltas) / block))
        sample = np.concatenate([deltas[start:start+block] for start in starts])[:len(deltas)]
        means.append(float(sample.mean()))
    # Freeze multiplicity before looking at any baseline or horizon results.
    alpha = protocol["familywise_alpha"] / (len(baseline_names(protocol)) * len(protocol["horizons"]))
    low, high = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    result["confidence_interval"] = [float(low), float(high)]
    result["status"] = ("DEVELOPMENT_PRIMARY_GATE_PASSED" if high < -protocol["minimum_material_brier_improvement"]
                        else "INCONCLUSIVE_OR_NO_MATERIAL_IMPROVEMENT")
    return result


def evaluate(rows: list[dict], protocol: dict) -> dict:
    validate_protocol(protocol)
    # Do not calculate even descriptive label statistics on the final period.
    development = [row for row in rows if instant(row["origin_at"]) < instant(protocol["final_holdout_start"])]
    validate_panel(development, protocol)
    horizons = {}
    candidates, challenger, baselines = protocol["candidates"], challenger_name(protocol), baseline_names(protocol)
    for horizon in protocol["horizons"]:
        folds = walk_forward_folds(development, protocol, horizon)
        predictions = {candidate: [] for candidate in candidates}
        failed_folds = []
        for index, (train, test) in enumerate(folds):
            current = {}
            try:
                for candidate in candidates:
                    current[candidate] = fit_predict(candidate, train, test, protocol)
            except ValueError as exc:
                # A failed candidate cannot gain apparent performance by selecting
                # a different test subset. Record and remove the entire paired fold.
                failed_folds.append({"fold": index, "candidate": candidate, "reason": str(exc),
                                     "test_origins": sorted({row["origin_at"] for row in test})})
                continue
            for candidate in candidates:
                predictions[candidate].extend(current[candidate])
        metrics = {name: score_predictions(values) for name, values in predictions.items()}
        comparisons = {name: paired_block_comparison(predictions[challenger], predictions[name], horizon, protocol)
                       for name in baselines}
        secondary = bool(predictions[challenger]) and all(
            metrics[challenger]["log_loss"] <= metrics[name]["log_loss"] + protocol["max_log_loss_regression"]
            and metrics[challenger]["mean_pinball"] <= metrics[name]["mean_pinball"] + protocol["max_pinball_regression"]
            for name in baselines)
        horizons[str(horizon)] = {"folds": len(folds), "failed_folds": failed_folds,
            "metrics": metrics, "paired_comparisons": comparisons,
            "predictions": predictions,
            "development_gate": "PASSED_REQUIRES_NEW_HOLDOUT_AND_PROSPECTIVE_CONFIRMATION" if
                secondary and not failed_folds and all(row["status"] == "DEVELOPMENT_PRIMARY_GATE_PASSED"
                                                      for row in comparisons.values()) else "INCONCLUSIVE_OR_FAILED"}
        if protocol.get("research_mode") == "DIAGNOSTIC_REVISED_PRICES":
            horizons[str(horizon)]["development_gate"] = "DISABLED_UNQUALIFIED_PRICE_VINTAGES"
            for comparison in comparisons.values():
                comparison["statistical_diagnostic_status"] = comparison["status"]
                comparison["status"] = "DIAGNOSTIC_ONLY_NOT_QUALIFIED"
    return {"schema_version": "meta-experiment-result-v1", "protocol_hash": digest(protocol),
            "horizons": horizons, "final_holdout_status": "UNTOUCHED",
            "promotion_status": "NOT_PROMOTED", "production_model_changed": False,
            "notice": "Development comparisons and source-only historical LLM extraction cannot establish prospective skill or absence of temporal contamination."}


def preregister(root: Path, protocol: dict, manifest: dict) -> Path:
    validate_protocol(protocol)
    if manifest.get("schema_version") != "meta-research-panel-manifest-v1":
        raise ValueError("Qualified research panel manifest is required")
    if manifest.get("research_track") != "IMPROVEMENT_PLAN_3_NEW_COHORT":
        raise ValueError("Closed research tracks cannot be reused as this cohort")
    root.mkdir(parents=True, exist_ok=True)
    path = root / "registration.json"
    core = {"protocol": protocol, "manifest": manifest,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "implementation_sha256": file_sha256(Path(__file__))}
    if protocol["schema_version"] == "meta-experiment-protocol-v2":
        core["dependency_hashes"] = implementation_hashes()
    write_json_exclusive(path, {**core, "registration_hash": digest(core)})
    return path


def implementation_hashes() -> dict:
    return {name: file_sha256(Path(__file__).with_name(name + ".py")) for name in (
        "meta_research_data", "meta_research_sources", "meta_research_panel", "meta_forecast",
        "meta_contracts", "meta_observation", "meta_analysis")}


def run_registered(root: Path, panel_path: Path) -> Path:
    registration = json.loads((root / "registration.json").read_text())
    if registration.pop("registration_hash") != digest(registration):
        raise ValueError("Experiment registration integrity mismatch")
    if registration["implementation_sha256"] != file_sha256(Path(__file__)):
        raise ValueError("Experiment implementation changed; preregister a new trial")
    if registration.get("dependency_hashes") is not None and registration["dependency_hashes"] != implementation_hashes():
        raise ValueError("Experiment dependency changed; preregister a new trial")
    if file_sha256(panel_path) != registration["manifest"]["panel_sha256"]:
        raise ValueError("Panel differs from preregistered dataset")
    run = root / "trials" / uuid.uuid4().hex
    run.mkdir(parents=True, exist_ok=False)
    write_json_exclusive(run / "started.json", {"started_at": datetime.now(timezone.utc).isoformat(),
                                                "registration_hash": digest(registration)})
    try:
        manifest = registration["manifest"]
        diagnostic = registration["protocol"].get("research_mode") == "DIAGNOSTIC_REVISED_PRICES"
        if diagnostic:
            if (manifest.get("dataset_kind") != "REVISED_PRICE_DIAGNOSTIC"
                    or manifest.get("availability_audited") is not False
                    or manifest.get("qualification_status") != "NOT_QUALIFIED"
                    or not manifest.get("audit_restrictions")):
                raise ValueError("Diagnostic registration must explicitly retain failed qualification audits")
        elif not all(manifest.get(name) is True for name in (
                "availability_audited", "survivorship_audited", "corporate_actions_audited", "license_audited")):
            raise ValueError("Historical availability, universe, corporate action and license audits are required")
        panel = json.loads(panel_path.read_text())
        if manifest.get("dataset_kind") != "SYNTHETIC_CONTROL":
            snapshots = manifest.get("feature_snapshots_root")
            if not snapshots:
                raise ValueError("Real research panels require verifiable frozen feature snapshots")
            snapshot_root = (root / snapshots).resolve()
            for row in panel:
                # The final period is neither inspected nor opened here.
                if instant(row["origin_at"]) >= instant(registration["protocol"]["final_holdout_start"]):
                    continue
                snapshot = json.loads((snapshot_root / f"{row['feature_snapshot_hash']}.json").read_text())
                identity = snapshot.pop("snapshot_hash")
                if identity != row["feature_snapshot_hash"] or identity != digest(snapshot):
                    raise ValueError("Research feature snapshot integrity mismatch")
                if instant(snapshot["cutoff"]) > instant(row["origin_at"]):
                    raise ValueError("Research snapshot is later than the prediction origin")
                source_features = {value["name"]: value for value in snapshot["features"]
                                   if value["entity"] == row["symbol"]}
                for name, value in row["features"].items():
                    feature = source_features.get(name)
                    if feature is None or feature["value"] != value:
                        raise ValueError("Panel features differ from the frozen point-in-time vector")
                    if value is not None and (not feature["available_at"] or
                                             instant(feature["available_at"]) > instant(row["origin_at"])):
                        raise ValueError("Panel feature is not available at the origin")
        result = evaluate(panel, registration["protocol"])
        result["dataset_kind"] = manifest["dataset_kind"]
        if diagnostic:
            result["qualification_status"] = "NOT_QUALIFIED"
            result["audit_restrictions"] = manifest["audit_restrictions"]
        result["result_hash"] = digest(result)
        target = run / "result.json"
        write_json_exclusive(target, result)
    except Exception as exc:
        write_json_exclusive(run / "failed.json", {"error_type": type(exc).__name__, "reason": str(exc)})
        raise
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preregister", "run", "feasibility"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--panel", type=Path)
    args = parser.parse_args()
    if args.command == "preregister":
        if not args.protocol or not args.manifest:
            parser.error("preregister requires --protocol and --manifest")
        path = preregister(args.root, json.loads(args.protocol.read_text()), json.loads(args.manifest.read_text()))
    elif args.command == "feasibility":
        if not args.panel or not args.protocol:
            parser.error("feasibility requires --panel and --protocol")
        path = args.root / "feasibility.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_exclusive(path, feasibility(json.loads(args.panel.read_text()), json.loads(args.protocol.read_text())))
    else:
        if not args.panel:
            parser.error("run requires --panel")
        path = run_registered(args.root, args.panel)
    print(json.dumps({"path": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
