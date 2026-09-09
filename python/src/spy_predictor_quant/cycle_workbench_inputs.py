"""Validate local source-extract manifests and map raw metrics to workbench inputs.

Validation establishes schema, integrity, timing and declared measurement identity,
not publisher authenticity, independent verification of extraction, or predictive
validity. There is no network access or Cycle 1 dataset adapter. Transformations
are versioned illustrative choices, not Maru Cape's undisclosed indicator rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from spy_predictor_quant.cycle_workbench import ComponentObservation, _instant

TRANSFORM_VERSION = "illustrative-raw-metrics-v1"
# metric -> (component, unit, reference, scale, sign)
METRICS = {
    "growth_yoy_pct": ("growth", "percent", 0.0, 5.0, 1.0),
    "credit_spread_bps": ("credit", "basis_points", 300.0, 300.0, -1.0),
    "bullish_survey_pct": ("psychology", "percent", 50.0, 50.0, 1.0),
    "realized_vol_pct": ("stress", "percent", 20.0, 40.0, 1.0),
    "operating_margin_pct": ("quality", "percent", 10.0, 20.0, 1.0),
    "trailing_pe": ("valuation", "multiple", 20.0, 20.0, -1.0),
    "price_to_ma200_ratio": ("timing", "ratio", 1.0, 0.15, 1.0),
}
SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas/cycle-workbench-inputs-v1.schema.json"


@dataclass(frozen=True)
class ValidatedWorkbenchInputs:
    observations: tuple[ComponentObservation, ...]
    metadata: dict[str, Any]
    audit: dict[str, Any]


def _hash_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _identity(value: Any) -> str:
    return _hash_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def _parse(raw: bytes) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def finite(value):
        raise ValueError(f"Non-finite JSON value: {value}")
    return json.loads(raw, object_pairs_hook=unique, parse_constant=finite)


def _confined(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("Input path escapes allowed_root")
    if any(part.lower() == "cycle1" or part.lower().startswith("cycle1-") for part in resolved.parts):
        raise ValueError("Cycle 1 data/output paths are not secondary workbench inputs")
    if not resolved.is_file():
        raise ValueError("Expected local input file")
    return resolved


def _validate(value: Any, schema: dict) -> None:
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), key=lambda error: str(error.path))
    if errors:
        error = errors[0]
        raise ValueError(f"Input schema violation at {list(error.path)}: {error.message}")


def _score(metric: str, value: float) -> float:
    if isinstance(value, bool) or not math.isfinite(value):
        raise ValueError("Raw metric must be finite and numeric")
    if metric in {"credit_spread_bps", "realized_vol_pct"} and value < 0:
        raise ValueError(f"{metric} must be nonnegative")
    if metric == "bullish_survey_pct" and not 0 <= value <= 100:
        raise ValueError("Survey percentage must be in [0,100]")
    if metric in {"trailing_pe", "price_to_ma200_ratio"} and value <= 0:
        raise ValueError(f"{metric} must be positive; unavailable denominators require withdrawal")
    _, _, reference, scale, sign = METRICS[metric]
    return max(-1.0, min(1.0, sign * (value - reference) / scale))


def load_workbench_inputs(manifest_path: str | Path, *, as_of: datetime | str,
                          allowed_root: str | Path) -> ValidatedWorkbenchInputs:
    """Load a confined hashed raw-metric snapshot; later rows cannot alter selections.

    The required allowed_root must be a dedicated workbench input directory,
    not the repository root or an ancestor. Only its regular local JSON files
    are loaded. Missing components abstain upstream; later withdrawals remain
    tombstones so stale earlier values cannot reappear.
    """
    cutoff = _instant(as_of)
    root = Path(allowed_root).resolve(strict=True)
    if not root.is_dir() or root.name in {"", "datasets", "reports", "examples", "fixtures"}:
        raise ValueError("allowed_root must identify a dedicated workbench input directory")
    # Explicit repository/root rejection also protects callers passing cwd.
    if root == Path(root.anchor) or (root / "config/cycle1.json").exists():
        raise ValueError("allowed_root cannot be filesystem/repository root")
    manifest_file = _confined(Path(manifest_path), root)
    raw_manifest = manifest_file.read_bytes()
    manifest = _parse(raw_manifest)
    schema = _parse(SCHEMA_PATH.read_bytes())
    _validate(manifest, schema)
    relative = Path(manifest["snapshot"]["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Snapshot path must be confined and relative")
    snapshot_file = _confined(manifest_file.parent / relative, root)
    raw_snapshot = snapshot_file.read_bytes()
    snapshot_hash = _hash_bytes(raw_snapshot)
    if snapshot_hash != manifest["snapshot"]["sha256"]:
        raise ValueError("Snapshot SHA256 mismatch")
    snapshot = _parse(raw_snapshot)
    _validate(snapshot, schema["$defs"]["snapshot"])
    eligible = []
    unique_records = set()
    unique_revisions = set()
    for row in snapshot["observations"]:
        metric = row["metric"]
        component, unit, _, _, _ = METRICS[metric]
        if row["unit"] != unit:
            raise ValueError(f"Unit mismatch for {metric}: expected {unit}")
        if row["evidence"] != manifest["evidence"]:
            raise ValueError("Mixed evidence tiers are not admitted in one manifest")
        expected_id = manifest["market_id"] if component in {"growth", "credit", "psychology", "stress"} else manifest["instrument_id"]
        if row["instrument_id"] != expected_id:
            raise ValueError(f"Instrument/market identity mismatch for {metric}")
        if manifest["instrument_type"] == "etf" and component in {"quality", "valuation"}:
            raise ValueError("Company margin/P-E transformations are not qualified ETF fundamentals")
        parsed = {name: _instant(row[name]) for name in ("observed_at", "published_at", "first_seen_at", "retrieved_at")}
        if not parsed["observed_at"] <= parsed["published_at"] <= parsed["first_seen_at"] <= parsed["retrieved_at"]:
            raise ValueError("Expected observed <= published <= first_seen <= retrieved")
        url = urlsplit(row["source_url"])
        if row["evidence"] == "SYNTHETIC":
            if url.scheme != "synthetic" or not url.netloc:
                raise ValueError("Synthetic fixtures require synthetic:// source URLs")
        elif url.scheme not in {"http", "https"} or not url.netloc or url.username or url.password:
            raise ValueError("Real source extracts require credential-free http(s) source URLs")
        key = (metric, parsed["observed_at"], parsed["published_at"], parsed["first_seen_at"])
        if key in unique_records:
            raise ValueError("Duplicate or ambiguous metric vintage")
        unique_records.add(key)
        revision_key = (metric, parsed["observed_at"], row["revision"])
        if revision_key in unique_revisions:
            raise ValueError("Duplicate revision identity for metric observation")
        unique_revisions.add(revision_key)
        if (row["status"] == "WITHDRAWN") != (row["value"] is None):
            raise ValueError("WITHDRAWN requires null raw value; AVAILABLE requires measured value")
        if row["value"] is not None:
            _score(metric, row["value"])
        # retrieval is the file archival event, not when evidence first existed.
        if max(parsed[name] for name in ("observed_at", "published_at", "first_seen_at")) <= cutoff:
            eligible.append((row, parsed))
    selected = {}
    for row, times in eligible:
        component = METRICS[row["metric"]][0]
        key = tuple(times[name] for name in ("observed_at", "published_at", "first_seen_at"))
        if component not in selected or key > selected[component][0]:
            selected[component] = (key, row, times)
    observations = []
    selected_provenance = {}
    for component in manifest["required_components"]:
        if component not in selected:
            selected_provenance[component] = {"status": "MISSING", "reason": "NO_ADMISSIBLE_RAW_METRIC"}
            continue
        _, row, times = selected[component]
        metric = row["metric"]
        _, unit, reference, scale, sign = METRICS[metric]
        transformation = f"{TRANSFORM_VERSION}:{metric}:clip({sign:g}*(x-{reference:g})/{scale:g},-1,1)"
        provenance_hash = _identity(row)
        observations.append(ComponentObservation(component=component,
            score=None if row["value"] is None else _score(metric, row["value"]),
            observed_at=times["observed_at"], published_at=times["published_at"],
            first_seen_at=times["first_seen_at"], source=row["source_url"], revision=row["revision"],
            max_age_days=row["max_age_days"], evidence=row["evidence"], raw_metric=metric,
            raw_value=row["value"], raw_unit=unit, transform=transformation, provenance_hash=provenance_hash))
        age = (cutoff-times["observed_at"]).total_seconds()/86400
        selected_provenance[component] = {**row, "status": "MISSING" if row["value"] is None else ("STALE" if age > row["max_age_days"] else "FRESH"),
                                           "transform": transformation, "provenance_hash": provenance_hash}
    metadata = {
        "input_contract": manifest["schema_version"], "transformation_version": TRANSFORM_VERSION,
        "adapter_sha256": _hash_bytes(Path(__file__).read_bytes()),
        "schema_sha256": _hash_bytes(SCHEMA_PATH.read_bytes()),
        "symbol": manifest["instrument_id"], "evidence_tier": manifest["evidence"], "validated": True,
        "instrument_id": manifest["instrument_id"], "instrument_type": manifest["instrument_type"],
        "market_id": manifest["market_id"], "evidence": manifest["evidence"],
        "as_of": cutoff.isoformat(), "required_components": manifest["required_components"],
        "validation_scope": "SCHEMA_INTEGRITY_IDENTITY_TIMING_UNITS; SOURCE_AUTHENTICITY_AND_EXTRACTION_NOT_INDEPENDENTLY_VERIFIED",
        "interpretation": "ILLUSTRATIVE_TRANSFORMS_NOT_CALIBRATED; SINGLE_METRIC_PROXIES_NOT_COMPLETE_QUALITY_OR_FAIR_VALUE",
        "selected_provenance": selected_provenance,
    }
    metadata["selected_input_hash"] = _identity(metadata)
    audit = {"manifest_path": str(manifest_file), "manifest_sha256": _hash_bytes(raw_manifest),
             "snapshot_path": str(snapshot_file), "snapshot_sha256": snapshot_hash,
             "note": "Whole-file integrity identities may change when future records are appended; selected_input_hash must not."}
    return ValidatedWorkbenchInputs(tuple(observations), metadata, audit)
