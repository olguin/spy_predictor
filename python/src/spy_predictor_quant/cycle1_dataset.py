"""Immutable three-track monthly research dataset for Cycle 1."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from spy_predictor_quant.cycle1_alpaca import capture_alpaca_actions, capture_alpaca_daily
from spy_predictor_quant.cycle1_config import Cycle1Plan
from spy_predictor_quant.cycle1_fred import SERIES_IDS, capture_fred_series
from spy_predictor_quant.cycle1_features import build_cycle_features
from spy_predictor_quant.cycle1_feasibility import selection_feasibility
from spy_predictor_quant.cycle1_ibkr import capture_ibkr_cycle_history
from spy_predictor_quant.cycle1_invesco import import_invesco_qqq_snapshot
from spy_predictor_quant.cycle1_shiller import capture_shiller
from spy_predictor_quant.cycle1_ssga import capture_ssga_spy_distributions
from spy_predictor_quant.cycle1_source_audit import Cycle1SourceAudit
from spy_predictor_quant.cycle1_states import assign_cycle_states
from spy_predictor_quant.cycle1_targets import build_cycle_targets, construct_total_return_index
from spy_predictor_quant.historical_http import ArchivedPage, ArchivedResource, RequestLimiter
from spy_predictor_quant.market_archive import content_hash, file_sha256


@dataclass(frozen=True)
class Cycle1Acquisition:
    raw_resources: dict[str, list[dict[str, Any]]]
    shiller: list[dict[str, Any]]
    macro: list[dict[str, Any]]
    daily: dict[str, list[dict[str, Any]]]
    actions: dict[str, list[dict[str, Any]]]


Acquirer = Callable[[Cycle1Plan, Cycle1SourceAudit, Path, Path, bool], Cycle1Acquisition]


def build_cycle1_dataset(
    *,
    plan: Cycle1Plan,
    audit: Cycle1SourceAudit,
    repo_root: Path,
    offline: bool = False,
    acquirer: Acquirer | None = None,
    schema_root: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    schemas = schema_root or repo_root
    raw_root = repo_root / "datasets" / "cycle1" / "raw" / audit.audit_hash[:16]
    raw_root.mkdir(parents=True, exist_ok=True)
    acquired = (acquirer or acquire_cycle1_sources)(plan, audit, repo_root, raw_root, offline)
    _validate_acquisition(acquired, audit)

    track_inputs = (
        ("discovery-sp500", "RECONSTRUCTED_DISCOVERY", "SP500_COMPOSITE", acquired.shiller, []),
        ("validation-spy", "ACTUAL_ETF_VALIDATION", "SPY", acquired.daily["SPY"], acquired.actions["SPY"]),
        ("validation-qqq", "ACTUAL_ETF_VALIDATION", "QQQ", acquired.daily["QQQ"], acquired.actions["QQQ"]),
    )
    macro_bytes = _ndjson(acquired.macro)
    identities: list[dict[str, Any]] = []
    prepared: list[tuple[str, str, str, list[dict[str, Any]], list[dict[str, Any]], dict[str, bytes], dict[str, Any]]] = []
    for track_id, role, instrument, primary, actions in track_inputs:
        artifacts = {
            "primary.ndjson": _ndjson(primary),
            "macro-vintages.ndjson": macro_bytes,
        }
        if role == "ACTUAL_ETF_VALIDATION":
            artifacts["corporate-actions.ndjson"] = _ndjson(actions)
            total_return_points = construct_total_return_index(primary, actions)
            total_return_rows = [
                {
                    "schemaVersion": "cycle1-total-return-point-v1",
                    "instrument": instrument,
                    "sessionDate": point.session_date.isoformat(),
                    "eventTime": point.event_time.isoformat(),
                    "close": point.close,
                    "totalReturnIndex": point.total_return_index,
                }
                for point in total_return_points
            ]
            targets = build_cycle_targets(
                instrument=instrument,
                daily_points=total_return_points,
                macro_vintages=acquired.macro,
                config=plan.raw,
            )
            features, feature_coverage = build_cycle_features(
                instrument=instrument,
                daily_points=total_return_points,
                macro_vintages=acquired.macro,
                config=plan.raw,
            )
            states = assign_cycle_states(features, plan.raw)
            target_dates = {target["snapshotDate"] for target in targets}
            model_eligible_dates = [
                state["snapshotDate"]
                for state in states
                if state["snapshotDate"] in target_dates
            ]
            model_eligible_rows = len(model_eligible_dates)
            required_model_rows = (
                int(plan.raw["partitions"]["minimumTrainingMonths"])
                + int(plan.raw["partitions"]["selectionConfirmationEmbargoMonths"])
                + int(plan.raw["partitions"]["minimumConfirmationLabeledMonths"])
            )
            if model_eligible_rows < required_model_rows:
                raise ValueError(
                    f"{instrument} has {model_eligible_rows} complete feature/target rows; "
                    f"the frozen protocol requires {required_model_rows}"
                )
            minimum_coverage = float(
                plan.raw["promotionGates"]["minimumCoreFeatureCoveragePercent"]
            )
            if float(feature_coverage["coveragePercent"]) < minimum_coverage:
                raise ValueError(
                    f"{instrument} core-feature coverage is below {minimum_coverage}%"
                )
            resolved_partitions = _resolve_partitions(
                model_eligible_dates, plan.raw["partitions"]
            )
            feasibility = selection_feasibility(
                targets, resolved_partitions["selection"], plan.raw["partitions"]
            )
            if feasibility["status"] == "NO_SELECTION_FORECASTS":
                raise ValueError(
                    f"{instrument} has no selection forecasts with mature training labels: "
                    + json.dumps(feasibility, sort_keys=True)
                )
            resolved_partitions["selectionFeasibility"] = feasibility
            artifacts["total-return-index.ndjson"] = _ndjson(total_return_rows)
            artifacts["targets.ndjson"] = _ndjson(targets)
            artifacts["features-and-states.ndjson"] = _ndjson(states)
        else:
            targets = []
            feature_coverage = {"monthlyCutoffs": len(primary), "featureVectors": 0, "coveragePercent": 0.0, "unavailable": []}
            resolved_partitions = {"status": "NOT_APPLICABLE_DISCOVERY_ONLY"}
        raw_resources = _track_raw_resources(acquired.raw_resources, instrument)
        identity = {
            "schemaVersion": "cycle1-track-identity-v1",
            "trackId": track_id,
            "preregistrationHash": plan.config_hash,
            "sourceAuditHash": audit.audit_hash,
            "rawResources": _identity_resources(raw_resources),
            "normalized": {name: hashlib.sha256(value).hexdigest() for name, value in sorted(artifacts.items())},
            "resolvedPartitions": resolved_partitions,
        }
        identities.append(identity)
        prepared.append((track_id, role, instrument, primary, actions, artifacts, {"rawResources": raw_resources, "identity": identity, "targets": targets, "featureCoverage": feature_coverage, "modelEligibleRows": model_eligible_rows if role == "ACTUAL_ETF_VALIDATION" else 0, "resolvedPartitions": resolved_partitions}))

    dataset_identity = {
        "schemaVersion": "cycle1-dataset-identity-v1",
        "preregistrationHash": plan.config_hash,
        "sourceAuditHash": audit.audit_hash,
        "tracks": identities,
    }
    dataset_hash = content_hash(dataset_identity)
    dataset_version = f"cycle1-monthly-{dataset_hash[:16]}"
    dataset_root = repo_root / "datasets" / "cycle1" / dataset_version
    dataset_root.mkdir(parents=True, exist_ok=True)
    track_entries: list[dict[str, Any]] = []
    track_schema = json.loads((schemas / "schemas" / "cycle1-track-manifest.schema.json").read_text(encoding="utf-8"))

    for track_id, role, instrument, primary, actions, artifacts, extra in prepared:
        track_root = dataset_root / track_id
        track_root.mkdir(parents=True, exist_ok=True)
        artifact_entries: list[dict[str, Any]] = []
        for filename, value in sorted(artifacts.items()):
            path = track_root / filename
            _write_or_verify(path, value)
            artifact_entries.append({
                "kind": filename.removesuffix(".ndjson"),
                "path": str(path.relative_to(repo_root)),
                "records": value.count(b"\n"),
                "sha256": hashlib.sha256(value).hexdigest(),
            })
        coverage = _coverage(
            instrument, primary, acquired.macro, _core_macro_series(audit)
        )
        track_manifest = {
            "schemaVersion": "cycle1-track-manifest-v1",
            "trackId": track_id,
            "role": role,
            "instrument": instrument,
            "evidenceTier": "RECONSTRUCTED_RESEARCH_ONLY",
            "preregistrationHash": plan.config_hash,
            "sourceAuditHash": audit.audit_hash,
            "rawResources": extra["rawResources"],
            "normalizedArtifacts": artifact_entries,
            "coverage": coverage,
            "quality": {
                "primaryRecords": len(primary),
                "macroVintageRecords": len(acquired.macro),
                "corporateActionRecords": len(actions),
                "targetRecords": len(extra["targets"]),
                "featureVectors": extra["featureCoverage"]["featureVectors"],
                "featureCoveragePercent": extra["featureCoverage"]["coveragePercent"],
                "modelEligibleRows": extra["modelEligibleRows"],
                "strictlyOrdered": _strictly_ordered(primary),
                "rawRedistributionAllowed": False,
            },
            "resolvedPartitions": extra["resolvedPartitions"],
            "datasetIdentityHash": content_hash(extra["identity"]),
        }
        Draft202012Validator(track_schema).validate(track_manifest)
        manifest_path = track_root / "manifest.json"
        _write_or_verify(manifest_path, _pretty_json(track_manifest))
        track_entries.append({
            "trackId": track_id,
            "role": role,
            "instrument": instrument,
            "manifestPath": str(manifest_path.relative_to(repo_root)),
            "manifestSha256": file_sha256(manifest_path),
            "datasetIdentityHash": track_manifest["datasetIdentityHash"],
        })

    index = {
        "schemaVersion": "cycle1-dataset-manifest-v1",
        "datasetVersion": dataset_version,
        "preregistrationHash": plan.config_hash,
        "sourceAuditHash": audit.audit_hash,
        "asOfDate": audit.raw["runtimeCoverageGates"]["asOfDate"],
        "tracks": track_entries,
        "datasetIdentityHash": dataset_hash,
    }
    index_schema = json.loads((schemas / "schemas" / "cycle1-dataset-manifest.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(index_schema).validate(index)
    index_path = dataset_root / "manifest.json"
    _write_or_verify(index_path, _pretty_json(index))
    return index_path, index


def acquire_cycle1_sources(plan: Cycle1Plan, audit: Cycle1SourceAudit, repo_root: Path, raw_root: Path, offline: bool) -> Cycle1Acquisition:
    del plan
    source_version = str(audit.raw["schemaVersion"])
    if source_version in {"cycle1-source-audit-v2", "cycle1-source-audit-v3"}:
        manual_path = repo_root / audit.raw["runtimeSourcePlan"]["manualQqqSnapshotPath"]
        archived_manual = any(
            (raw_root / "invesco" / f"qqq-distributions.{suffix}").is_file()
            for suffix in ("csv", "html")
        )
        if not manual_path.is_file() and not archived_manual:
            raise FileNotFoundError(
                "Cycle 1 source audit v2 requires one browser-saved Invesco QQQ "
                f"distribution snapshot at {manual_path}"
            )
    api_key = "" if offline else os.environ.get("FRED_API_KEY", "").strip()
    alpaca_key = "" if offline else os.environ.get("APCA_API_KEY_ID", "").strip()
    alpaca_secret = "" if offline else os.environ.get("APCA_API_SECRET_KEY", "").strip()
    as_of = date.fromisoformat(audit.raw["runtimeCoverageGates"]["asOfDate"])
    starts = {key: date.fromisoformat(value) for key, value in audit.raw["runtimeCoverageGates"]["requestedInstrumentStartDates"].items()}
    raw_resources: dict[str, list[dict[str, Any]]] = {}
    invesco_resource: ArchivedResource | None = None
    preflight_qqq_actions: list[dict[str, Any]] | None = None
    if source_version in {"cycle1-source-audit-v2", "cycle1-source-audit-v3"}:
        source_plan = audit.raw["runtimeSourcePlan"]
        source_path = repo_root / source_plan["manualQqqSnapshotPath"]
        _progress("invesco:QQQ:distributions", "preflight", offline=True)
        invesco_resource, preflight_qqq_actions = import_invesco_qqq_snapshot(
            source_path=source_path if source_path.is_file() else None,
            raw_directory=raw_root / "invesco",
        )
        _validate_distribution_series(
            "QQQ",
            preflight_qqq_actions,
            source_plan["distributionCoverage"]["QQQ"],
        )
        _progress(
            "invesco:QQQ:distributions",
            "preflight-complete",
            records=len(preflight_qqq_actions),
        )
    _progress("shiller", "start", offline=offline)
    shiller_resource, shiller = capture_shiller(raw_directory=raw_root / "shiller", offline=offline)
    raw_resources["shiller"] = [_resource_entry(shiller_resource, raw_root)]
    _progress("shiller", "complete", records=len(shiller))
    macro: list[dict[str, Any]] = []
    fred_limiter = RequestLimiter(60)
    raw_resources["fred"] = []
    for series_id in _core_macro_series(audit):
        _progress(f"fred:{series_id}", "start", offline=offline)
        pages, rows = capture_fred_series(series_id=series_id, as_of=as_of, raw_directory=raw_root / "fred" / series_id, api_key=api_key, offline=offline, limiter=fred_limiter)
        raw_resources["fred"].extend(_page_entries(pages, raw_root))
        macro.extend(rows)
        _progress(f"fred:{series_id}", "complete", pages=len(pages), records=len(rows))
    macro.sort(key=lambda row: (row["seriesId"], row["observationDate"], row["realtimeStart"]))
    daily: dict[str, list[dict[str, Any]]] = {}
    actions: dict[str, list[dict[str, Any]]] = {}
    if source_version == "cycle1-source-audit-v1":
        for symbol in ("SPY", "QQQ"):
            _progress(f"alpaca:{symbol}:daily", "start", offline=offline)
            pages, daily[symbol] = capture_alpaca_daily(symbol=symbol, start=starts[symbol], as_of=as_of, raw_directory=raw_root / "alpaca" / symbol / "daily", key_id=alpaca_key, secret_key=alpaca_secret, offline=offline)
            raw_resources[f"alpaca-{symbol}"] = _page_entries(pages, raw_root)
            _progress(f"alpaca:{symbol}:daily", "complete", pages=len(pages), records=len(daily[symbol]))
            _progress(f"alpaca:{symbol}:actions", "start", offline=offline)
            action_pages, actions[symbol] = capture_alpaca_actions(symbol=symbol, start=starts[symbol], as_of=as_of, raw_directory=raw_root / "alpaca" / symbol / "actions", key_id=alpaca_key, secret_key=alpaca_secret, offline=offline)
            raw_resources[f"alpaca-{symbol}"].extend(_page_entries(action_pages, raw_root))
            _progress(f"alpaca:{symbol}:actions", "complete", pages=len(action_pages), records=len(actions[symbol]))
    elif source_version in {"cycle1-source-audit-v2", "cycle1-source-audit-v3"}:
        source_plan = audit.raw["runtimeSourcePlan"]
        _progress("ibkr:daily", "start", offline=offline)
        ibkr = capture_ibkr_cycle_history(
            catalog_path=repo_root / source_plan["ibkrCatalogPath"],
            as_of=as_of,
            raw_directory=raw_root / "ibkr",
            offline=offline,
            duration=str(source_plan["ibkrDuration"]),
        )
        if not all(
            source_plan["ibkrCatalogHash"] in entry.request_url
            for entry in ibkr.resources
        ):
            raise ValueError("IBKR resource identity does not contain the frozen catalog hash")
        daily = ibkr.daily
        _progress(
            "ibkr:daily", "complete",
            SPY=len(daily["SPY"]), QQQ=len(daily["QQQ"]),
        )
        _progress("ssga:SPY:distributions", "start", offline=offline)
        ssga_resource, actions["SPY"] = capture_ssga_spy_distributions(
            raw_directory=raw_root / "ssga", offline=offline
        )
        _progress(
            "ssga:SPY:distributions", "complete", records=len(actions["SPY"])
        )
        if invesco_resource is None or preflight_qqq_actions is None:
            raise AssertionError("Invesco QQQ preflight did not run")
        actions["QQQ"] = preflight_qqq_actions
        _validate_distribution_coverage(actions, source_plan["distributionCoverage"])
        for symbol in ("SPY", "QQQ"):
            ibkr_entries = [
                _resource_entry(resource, raw_root)
                for resource in ibkr.resources
                if resource.path.parent.name == symbol
            ]
            sponsor = ssga_resource if symbol == "SPY" else invesco_resource
            raw_resources[f"market-{symbol}"] = ibkr_entries + [
                _resource_entry(sponsor, raw_root)
            ]
    else:
        raise ValueError(f"Unsupported Cycle 1 source version {source_version}")
    return Cycle1Acquisition(raw_resources, shiller, macro, daily, actions)


def _progress(source: str, status: str, **details: Any) -> None:
    print(
        json.dumps({"event": "cycle1-source", "source": source, "status": status, **details}, sort_keys=True),
        file=sys.stderr,
        flush=True,
    )


def _validate_acquisition(data: Cycle1Acquisition, audit: Cycle1SourceAudit) -> None:
    if not data.shiller or not data.macro:
        raise ValueError("Cycle 1 discovery and macro sources cannot be empty")
    present_series = {row["seriesId"] for row in data.macro}
    expected_series = set(_core_macro_series(audit))
    if present_series != expected_series:
        raise ValueError("Cycle 1 macro acquisition differs from the audit's core series")
    for symbol in ("SPY", "QQQ"):
        rows = data.daily.get(symbol, [])
        if not rows or any(row["instrument"] != symbol for row in rows):
            raise ValueError(f"Cycle 1 requires nonempty actual {symbol} daily data")
    if audit.raw["containsModelOutput"]:
        raise ValueError("Dataset construction refuses a source audit containing model output")


def _track_raw_resources(resources: dict[str, list[dict[str, Any]]], instrument: str) -> list[dict[str, Any]]:
    market_key = (
        f"market-{instrument}"
        if f"market-{instrument}" in resources
        else f"alpaca-{instrument}"
    )
    keys = ["fred", "shiller"] if instrument == "SP500_COMPOSITE" else ["fred", market_key]
    return [entry for key in keys for entry in resources[key]]


def _validate_distribution_coverage(
    actions: dict[str, list[dict[str, Any]]], expected: dict[str, dict[str, Any]]
) -> None:
    for symbol in ("SPY", "QQQ"):
        _validate_distribution_series(symbol, actions.get(symbol, []), expected[symbol])


def _validate_distribution_series(
    symbol: str, rows: list[dict[str, Any]], contract: dict[str, Any]
) -> None:
    dates = sorted(str(row["effectiveDate"]) for row in rows)
    if (
        len(rows) != int(contract["records"])
        or not dates
        or dates[0] != contract["firstExDate"]
        or dates[-1] != contract["lastExDate"]
    ):
        raise ValueError(
            f"{symbol} sponsor distribution coverage does not match source audit v2"
        )


def _identity_resources(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: entry[key] for key in ("provider", "path", "sha256", "requestUrl", "records")} for entry in resources]


def _page_entries(pages: list[ArchivedPage], raw_root: Path) -> list[dict[str, Any]]:
    return [{"provider": page.provider, "path": str(page.path.relative_to(raw_root)), "sha256": page.sha256, "requestUrl": page.request_url, "receivedAt": page.received_at, "records": page.records} for page in pages]


def _resource_entry(resource: ArchivedResource, raw_root: Path) -> dict[str, Any]:
    return {"provider": resource.provider, "path": str(resource.path.relative_to(raw_root)), "sha256": resource.sha256, "requestUrl": resource.request_url, "receivedAt": resource.received_at, "records": resource.records}


def _coverage(
    instrument: str,
    primary: list[dict[str, Any]],
    macro: list[dict[str, Any]],
    macro_series: tuple[str, ...],
) -> dict[str, Any]:
    key = "observationMonth" if instrument == "SP500_COMPOSITE" else "sessionDate"
    values = sorted(str(row[key]) for row in primary)
    macro_coverage = {}
    for series_id in macro_series:
        dates = sorted(row["observationDate"] for row in macro if row["seriesId"] == series_id)
        macro_coverage[series_id] = {"first": dates[0], "last": dates[-1], "records": len(dates)}
    return {"primary": {"first": values[0], "last": values[-1], "records": len(values)}, "macro": macro_coverage}


def _core_macro_series(audit: Cycle1SourceAudit) -> tuple[str, ...]:
    if audit.raw["schemaVersion"] == "cycle1-source-audit-v3":
        values = tuple(audit.raw["runtimeSourcePlan"]["coreMacroSeries"])
        if values != SERIES_IDS:
            raise ValueError("Source audit core macro order differs from implementation")
        return values
    return ("DGS3MO", "CPIAUCSL", "NFCI", "INDPRO")


def _resolve_partitions(
    eligible_dates: list[str], partitions: dict[str, Any]
) -> dict[str, Any]:
    months = [date.fromisoformat(value).year * 12 + date.fromisoformat(value).month for value in eligible_dates]
    if any(right - left != 1 for left, right in zip(months, months[1:])):
        raise ValueError("Resolved partitions require consecutive calendar months; row counts cannot replace calendar embargo")
    confirmation_count = int(partitions["minimumConfirmationLabeledMonths"])
    embargo_count = int(partitions["selectionConfirmationEmbargoMonths"])
    boundary = len(eligible_dates) - confirmation_count
    selection_end = boundary - embargo_count
    if selection_end < int(partitions["minimumTrainingMonths"]):
        raise ValueError("Resolved Cycle 1 selection partition is below minimum training")
    selection = eligible_dates[:selection_end]
    embargo = eligible_dates[selection_end:boundary]
    confirmation = eligible_dates[boundary:]
    half_count = int(partitions["confirmationHalves"])
    minimum_half = int(partitions["minimumLabeledMonthsPerHalf"])
    if half_count != 2 or len(confirmation) != minimum_half * half_count:
        raise ValueError("Resolved Cycle 1 confirmation halves differ from preregistration")
    halves = [confirmation[:minimum_half], confirmation[minimum_half:]]

    def interval(values: list[str]) -> dict[str, Any]:
        if not values:
            raise ValueError("Resolved Cycle 1 partition cannot be empty")
        return {"start": values[0], "end": values[-1], "labeledMonths": len(values)}

    return {
        "status": "RESOLVED_BEFORE_CANDIDATE_EVALUATION",
        "modelEligible": interval(eligible_dates),
        "selection": interval(selection),
        "embargo": interval(embargo),
        "confirmation": {
            **interval(confirmation),
            "halves": [interval(values) for values in halves],
        },
    }


def _strictly_ordered(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return False
    key = "observationMonth" if "observationMonth" in rows[0] else "sessionDate"
    values = [str(row[key]) for row in rows]
    return values == sorted(values) and len(values) == len(set(values))


def _ndjson(records: list[dict[str, Any]]) -> bytes:
    return b"".join(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n" for record in records)


def _pretty_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _write_or_verify(path: Path, value: bytes) -> None:
    if path.exists():
        if path.read_bytes() != value:
            raise ValueError(f"Immutable artifact mismatch at {path}")
        return
    with path.open("xb") as output:
        output.write(value)
