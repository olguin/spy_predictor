"""Calendar and publication preflight; never fits models or scores outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from spy_predictor_quant.cycle1_config import load_cycle1_plan
from spy_predictor_quant.cycle1_targets import TotalReturnPoint, observable_cash_rates
from spy_predictor_quant.market_archive import content_hash


def selection_feasibility(
    targets: list[dict[str, Any]], selection: dict[str, Any], config: dict[str, Any],
) -> dict[str, Any]:
    """Count forecasts with mature labels; inputs need only date metadata.

    The rolling window is counted in calendar months ending at the forecast
    month. These are necessary mechanical checks, not a statistical-power gate.
    No extra purge is stacked on top of the same 12-month label maturity rule.
    """
    rows = sorted(
        (row for row in targets if selection["start"] <= row["snapshotDate"] <= selection["end"]),
        key=lambda row: row["snapshotDate"],
    )
    counts: dict[str, list[dict[str, Any]]] = {mode: [] for mode in config["modes"]}
    for forecast in rows:
        cutoff = datetime.fromisoformat(forecast["snapshotCutoff"])
        forecast_date = date.fromisoformat(forecast["snapshotDate"])
        ordinal = forecast_date.year * 12 + forecast_date.month
        for mode in counts:
            training = []
            for row in rows:
                start = date.fromisoformat(row["snapshotDate"])
                if mode == "rolling" and start.year * 12 + start.month <= ordinal - config["rollingWindowMonths"]:
                    continue
                if (
                    datetime.fromisoformat(row["labelAvailableAt"]) < cutoff
                    and datetime.fromisoformat(row["targetEndDate"] + "T23:59:59+00:00") < cutoff
                ):
                    training.append(row)
            counts[mode].append({"date": forecast["snapshotDate"], "trainingLabels": len(training)})
    modes = {}
    for mode, forecasts in counts.items():
        eligible = [row for row in forecasts if row["trainingLabels"] >= config["minimumTrainingMonths"]]
        modes[mode] = {
            "eligibleForecasts": len(eligible),
            "firstEligibleForecast": eligible[0]["date"] if eligible else None,
            "maximumMaturedTrainingLabels": max((row["trainingLabels"] for row in forecasts), default=0),
        }
    return {
        "status": "NO_SELECTION_FORECASTS" if any(value["eligibleForecasts"] == 0 for value in modes.values()) else "MECHANICALLY_FEASIBLE_POWER_NOT_ESTABLISHED",
        "selectionRows": len(rows),
        "modes": modes,
    }


def confirmation_start_feasibility(
    targets: list[dict[str, Any]], selection: dict[str, Any],
    confirmation: dict[str, Any], minimum_training: int,
) -> dict[str, Any]:
    """Check training maturity at the sealed boundary without reading outcomes."""
    first_cutoff = next(
        datetime.fromisoformat(row["snapshotCutoff"])
        for row in sorted(targets, key=lambda row: row["snapshotDate"])
        if row["snapshotDate"] == confirmation["start"]
    )
    usable = [
        row for row in targets
        if selection["start"] <= row["snapshotDate"] <= selection["end"]
        and datetime.fromisoformat(row["labelAvailableAt"]) < first_cutoff
        and datetime.fromisoformat(row["targetEndDate"] + "T23:59:59+00:00") < first_cutoff
    ]
    return {
        "firstConfirmationDate": confirmation["start"],
        "matureSelectionLabelsAtStart": len(usable),
        "minimumTrainingLabels": minimum_training,
        "status": "FEASIBLE" if len(usable) >= minimum_training else "INSUFFICIENT",
    }


def _verified(repo_root: Path, relative: str, expected_hash: str) -> bytes:
    path = (repo_root / relative).resolve()
    if not path.is_relative_to(repo_root.resolve()):
        raise ValueError("Artifact path escapes repository")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError(f"Artifact hash mismatch: {relative}")
    return data


def audit_dataset(repo_root: Path, manifest_path: Path, config_path: Path) -> dict[str, Any]:
    """Read verified archive metadata, projecting selection rows to dates only.

    Existing confirmation labels are not scored or emitted. Their bytes are
    covered by artifact verification; only selection date metadata is retained.
    """
    plan = load_cycle1_plan(config_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["datasetVersion"] != "cycle1-monthly-19ccd95384e690de":
        raise ValueError("This repair audit applies only to the archived v4 dataset 19ccd95384e690de")
    if manifest["preregistrationHash"] != plan.config_hash:
        raise ValueError("Dataset and preregistration identities differ")
    tracks = []
    for entry in manifest["tracks"]:
        if entry["role"] != "ACTUAL_ETF_VALIDATION":
            continue
        track = json.loads(_verified(repo_root, entry["manifestPath"], entry["manifestSha256"]))
        if track["preregistrationHash"] != plan.config_hash or track["datasetIdentityHash"] != entry["datasetIdentityHash"]:
            raise ValueError("Track authority mismatch")
        artifacts = {artifact["kind"]: artifact for artifact in track["normalizedArtifacts"]}

        def read(kind: str) -> list[dict[str, Any]]:
            artifact = artifacts[kind]
            rows = [json.loads(line) for line in _verified(repo_root, artifact["path"], artifact["sha256"]).splitlines()]
            if len(rows) != artifact["records"]:
                raise ValueError(f"Artifact count mismatch: {kind}")
            return rows

        selection = track["resolvedPartitions"]["selection"]
        dates = [
            {key: row[key] for key in ("snapshotDate", "snapshotCutoff", "labelAvailableAt", "targetEndDate")}
            for row in read("targets")
            if selection["start"] <= row["snapshotDate"] <= selection["end"]
        ]
        macro = read("macro-vintages")
        points = [TotalReturnPoint(date.fromisoformat(row["snapshotDate"]), datetime.fromisoformat(row["snapshotCutoff"]), 1.0, 1.0) for row in dates]
        cash_alternatives = {}
        for series_id in ("DGS3MO", "GS3M"):
            rates = observable_cash_rates(points, macro, series_id)
            admissible_dates = [row for row in dates if datetime.fromisoformat(row["snapshotCutoff"]) in rates]
            first_release = min((row["availableAt"] for row in macro if row["seriesId"] == series_id and not row["missing"]), default=None)
            cash_alternatives[series_id] = {
                "earliestPublication": first_release,
                "selectionStartsWithoutObservableRate": len(dates) - len(admissible_dates),
                "selectionAfterStartFilter": selection_feasibility(admissible_dates, selection, plan.raw["partitions"]),
            }
        tracks.append({
            "instrument": track["instrument"],
            "evidenceTier": track["evidenceTier"],
            "archivedSelection": selection_feasibility(dates, selection, plan.raw["partitions"]),
            "cashSeriesAlternatives": cash_alternatives,
            "externalTransferAtConfirmationStart": confirmation_start_feasibility(
                read("targets"), selection, track["resolvedPartitions"]["confirmation"],
                int(plan.raw["partitions"]["minimumTrainingMonths"]),
            ),
            "cashFilterScope": "holding-period-start-only; full-path qualification is still required",
        })
    core = {
        "schemaVersion": "cycle1-pre-evaluation-audit-v1",
        "status": "BLOCKED_REPAIR_REQUIRED",
        "datasetVersion": manifest["datasetVersion"],
        "preregistrationHash": plan.config_hash,
        "implementationHashes": {
            name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
            for name in ("cycle1_feasibility.py", "cycle1_targets.py", "cycle1_features.py")
        },
        "candidateMetricsComputed": False,
        "confirmationMetricsOpened": False,
        "tracks": tracks,
        "blockingReasons": ["V5_AMENDMENT_NOT_YET_FROZEN", "EVALUATION_CONTRACT_INCOMPLETE", "ARCHIVED_SPREAD_LAG_REQUIRES_REBUILD"],
        "recommendedUnblock": {
            "cashSeries": "GS3M",
            "developmentInstrument": "SPY",
            "externalTransferInstrument": "QQQ",
            "independentQqqQualificationAllowed": False,
        },
    }
    return {**core, "reportHash": content_hash(core)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config/cycle1.json"))
    args = parser.parse_args()
    try:
        report = audit_dataset(args.repo_root.resolve(), args.manifest, args.config)
    except (ValueError, KeyError, OSError) as error:
        print(json.dumps({"status": "INVALID_AUDIT_INPUT", "message": str(error)}))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if report["status"] == "BLOCKED_REPAIR_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
