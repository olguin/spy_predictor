"""Append-only point-in-time observations, frozen features and coverage audits.

Availability is a source assertion, never inferred from the economic period.
Unknown timestamps and unqualified revisions remain stored but cannot enter an
as-of feature vector. These records belong to a new research lane.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path

from spy_predictor_quant.market_archive import write_json_exclusive
from spy_predictor_quant.meta_analysis import digest
from spy_predictor_quant.meta_contracts import finite, instant

VERSION = "meta-pit-observation-v1"
RECONSTRUCTED_VERSION = "meta-pit-observation-v2"
LANES = ("CAPTURED_LIVE", "HISTORICAL_RECONSTRUCTION")
TIMES = ("effective_at", "published_at", "first_seen_at", "available_at", "captured_at")
REQUIRED = {"schema_version", "entity", "metric", "value", "units", "source_version",
            "revision_id", "source_hash", "quality_flags", "period_start", "period_end", *TIMES}


def validate_observation(row: dict) -> None:
    if not REQUIRED <= row.keys() or row["schema_version"] not in {VERSION, RECONSTRUCTED_VERSION}:
        raise ValueError("Incomplete point-in-time observation contract")
    if not finite(row["value"]):
        raise ValueError("Observation value must be finite")
    for name in ("entity", "metric", "units", "source_version", "revision_id", "source_hash"):
        if not isinstance(row[name], str) or not row[name]:
            raise ValueError(f"Missing observation {name}")
    if len(row["source_hash"]) != 64 or any(c not in "0123456789abcdef" for c in row["source_hash"]):
        raise ValueError("Observation requires a source SHA-256")
    if not isinstance(row["quality_flags"], list) or any(not isinstance(flag, str) for flag in row["quality_flags"]):
        raise ValueError("Quality flags must be a list of named restrictions")
    parsed = {key: instant(row[key]) for key in TIMES if row[key] is not None}
    if not {"effective_at", "captured_at"} <= parsed.keys():
        raise ValueError("Effective and capture timestamps are required")
    if parsed["effective_at"] > parsed["captured_at"]:
        raise ValueError("Observation effective time follows capture")
    reconstructed = row["schema_version"] == RECONSTRUCTED_VERSION
    if reconstructed:
        proof = row.get("availability_evidence", {})
        if (row.get("availability_lane") != "HISTORICAL_RECONSTRUCTION"
                or proof.get("kind") not in {"SEC_ACCEPTANCE", "ALFRED_VINTAGE"}
                or proof.get("source_hash") != row["source_hash"]
                or not isinstance(proof.get("locator"), str) or not proof["locator"]
                or proof.get("available_at") != row["available_at"]
                or proof.get("precision") not in {"SECOND", "DAY_CONSERVATIVE_NEXT_DAY"}
                or len(parsed) != len(TIMES)):
            raise ValueError("Historical reconstruction requires source-bound availability evidence")
        if not (parsed["effective_at"] <= parsed["published_at"] <= parsed["available_at"]
                <= parsed["first_seen_at"] <= parsed["captured_at"]):
            raise ValueError("Reconstructed timing must preserve publication and actual retrieval")
    elif all(key in parsed for key in TIMES):
        if not (parsed["effective_at"] <= parsed["published_at"] <= parsed["first_seen_at"]
                <= parsed["available_at"] <= parsed["captured_at"]):
            raise ValueError("Observation timing must be effective <= published <= first_seen <= available <= captured")
    if (row["period_start"] is None) != (row["period_end"] is None):
        raise ValueError("Both fiscal period boundaries are required together")
    if row["period_start"] is not None:
        if date.fromisoformat(row["period_start"]) > date.fromisoformat(row["period_end"]):
            raise ValueError("Fiscal period ends before it starts")


def append_observation(root: Path, row: dict) -> Path:
    validate_observation(row)
    core = {key: value for key, value in row.items() if key != "record_hash"}
    identity = digest(core)
    if row.get("record_hash", identity) != identity:
        raise ValueError("Observation integrity mismatch")
    path = root / "observations" / f"{identity}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if json.loads(path.read_text()) != {**core, "record_hash": identity}:
            raise ValueError("Existing observation integrity mismatch")
        return path
    write_json_exclusive(path, {**core, "record_hash": identity})
    return path


def load_observations(root: Path) -> list[dict]:
    rows = []
    for path in sorted((root / "observations").glob("*.json")):
        row = json.loads(path.read_text())
        validate_observation(row)
        if row.get("record_hash") != digest({k: v for k, v in row.items() if k != "record_hash"}):
            raise ValueError("Observation integrity mismatch")
        rows.append(row)
    return rows


def as_of(rows: list[dict], cutoff: str, *, lane: str = "CAPTURED_LIVE") -> list[dict]:
    if lane not in LANES:
        raise ValueError("Unknown availability lane")
    at = instant(cutoff)
    selected = {}
    for row in rows:
        validate_observation(row)
        row_lane = "HISTORICAL_RECONSTRUCTION" if row["schema_version"] == RECONSTRUCTED_VERSION else "CAPTURED_LIVE"
        if row_lane != lane:
            continue
        if row["quality_flags"] or any(row.get(key) is None for key in TIMES):
            continue
        cutoff_times = ("effective_at", "published_at", "available_at") if lane == "HISTORICAL_RECONSTRUCTION" else TIMES
        if any(instant(row[key]) > at for key in cutoff_times):
            continue
        key = tuple(row[name] for name in ("entity", "metric", "units", "effective_at", "period_start", "period_end"))
        prior = selected.get(key)
        if prior and instant(prior["available_at"]) == instant(row["available_at"]) and prior != row:
            raise ValueError("Conflicting simultaneous source revisions require explicit resolution")
        if prior is None or instant(row["available_at"]) > instant(prior["available_at"]):
            selected[key] = row
    return sorted(selected.values(), key=lambda row: (row["entity"], row["metric"], row["effective_at"]))


def freeze_features(root: Path, cutoff: str, registry: dict, *, lane: str = "CAPTURED_LIVE") -> Path:
    if registry.get("schema_version") != "meta-feature-registry-v1":
        raise ValueError("Unsupported feature registry")
    observations = as_of(load_observations(root), cutoff, lane=lane)
    features = []
    seen = set()
    for spec in registry["features"]:
        key = (spec["entity"], spec["name"])
        if key in seen:
            raise ValueError("Duplicate feature definition")
        seen.add(key)
        inputs = []
        for metric in spec["inputs"]:
            matches = [row for row in observations if row["entity"] == spec["entity"] and row["metric"] == metric]
            inputs.append(max(matches, key=lambda row: instant(row["effective_at"])) if matches else None)
        value, reason = None, None
        if not inputs or any(row is None for row in inputs):
            reason = "MISSING_QUALIFIED_INPUT"
        elif [row["units"] for row in inputs] != spec["input_units"]:
            reason = "INCOMPATIBLE_UNITS"
        elif spec["formula"] == "LATEST" and len(inputs) == 1:
            value = inputs[0]["value"]
        elif spec["formula"] in {"RATIO", "DIFFERENCE"} and len(inputs) == 2:
            if any(inputs[0][key] != inputs[1][key] for key in ("effective_at", "period_start", "period_end")):
                reason = "INCOMPARABLE_PERIODS"
            elif spec["formula"] == "RATIO":
                value = inputs[0]["value"] / inputs[1]["value"] if inputs[1]["value"] else None
                reason = "ZERO_DENOMINATOR" if value is None else None
            else:
                value = inputs[0]["value"] - inputs[1]["value"]
        else:
            raise ValueError("Unregistered feature formula or arity")
        features.append({"entity": spec["entity"], "name": spec["name"], "value": value,
                         "units": spec["units"], "formula": spec["formula"],
                         "status": "AVAILABLE" if value is not None else "MISSING", "reason": reason,
                         "input_hashes": [row["record_hash"] for row in inputs if row],
                         "available_at": max((row["available_at"] for row in inputs if row), default=None)})
    core = {"schema_version": "meta-feature-snapshot-v1", "cutoff": cutoff,
            "registry_hash": digest(registry), "features": features}
    if lane != "CAPTURED_LIVE":
        core.update(schema_version="meta-feature-snapshot-v2", availability_lane=lane)
    identity = digest(core)
    target = root / "features" / f"{identity}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json_exclusive(target, {**core, "snapshot_hash": identity})
    return target


def quarterly_flows(rows: list[dict], cutoff: str, fiscal_start: str, *, lane: str = "CAPTURED_LIVE") -> list[dict]:
    """Derive one comparable fiscal year's quarters from direct or YTD flows.

    The caller supplies one entity/metric/unit/share basis. Restated share bases
    are never mixed. This does not infer missing periods or annualize stubs.
    """
    eligible = [row for row in as_of(rows, cutoff, lane=lane) if row["period_start"] is not None]
    identities = {(row["entity"], row["metric"], row["units"], row.get("share_basis")) for row in eligible}
    if len(identities) > 1:
        raise ValueError("Quarter reconstruction requires one entity/metric/unit/share basis")
    result, previous_ytd = [], None
    for row in sorted(eligible, key=lambda row: (row["period_end"], row["period_start"])):
        start, end = date.fromisoformat(row["period_start"]), date.fromisoformat(row["period_end"])
        if start < date.fromisoformat(fiscal_start):
            continue
        days = (end - start).days + 1
        if 75 <= days <= 105:
            result.append({**row, "derivation": "DIRECT_QUARTER", "input_hashes": [row["record_hash"]]})
        elif row["period_start"] == fiscal_start and previous_ytd:
            prior_end = date.fromisoformat(previous_ytd["period_end"])
            if 75 <= (end - prior_end).days <= 105:
                result.append({**row, "period_start": (prior_end + timedelta(days=1)).isoformat(),
                               "value": row["value"] - previous_ytd["value"],
                               "derivation": "YTD_DIFFERENCE", "record_hash": None,
                               "input_hashes": [previous_ytd["record_hash"], row["record_hash"]]})
        if row["period_start"] == fiscal_start:
            previous_ytd = row
    unique = {}
    for row in result:
        key = row["period_end"]
        if key in unique and abs(unique[key]["value"] - row["value"]) > 1e-9:
            raise ValueError("Direct quarter and YTD difference disagree")
        unique[key] = row
    return sorted(unique.values(), key=lambda row: row["period_end"])


def trailing_four_quarters(quarters: list[dict]) -> dict:
    rows = sorted(quarters, key=lambda row: row["period_end"])[-4:]
    if len({(row["entity"], row["metric"], row["units"], row.get("share_basis")) for row in rows}) > 1:
        raise ValueError("Trailing quarters must share entity, metric, units and share basis")
    if len(rows) != 4 or any(date.fromisoformat(right["period_start"]) !=
                            date.fromisoformat(left["period_end"]) + timedelta(days=1)
                            for left, right in zip(rows, rows[1:])):
        return {"status": "MISSING", "value": None, "reason": "FOUR_COMPARABLE_CONTIGUOUS_QUARTERS_REQUIRED"}
    return {"status": "AVAILABLE", "value": sum(row["value"] for row in rows),
            "period_start": rows[0]["period_start"], "period_end": rows[-1]["period_end"],
            "available_at": max(row["available_at"] for row in rows),
            "input_hashes": sorted({key for row in rows for key in row["input_hashes"]})}


def release_surprise(actual: dict, expectation: dict | None) -> dict:
    validate_observation(actual)
    if expectation is None:
        return {"status": "MISSING", "value": None, "reason": "QUALIFIED_CONTEMPORANEOUS_EXPECTATION_REQUIRED"}
    validate_observation(expectation)
    if (any(actual[key] is None or expectation[key] is None for key in TIMES)
            or actual["quality_flags"] or expectation["quality_flags"]
            or (actual["entity"], actual["metric"], actual["units"], actual["period_end"]) !=
               (expectation["entity"], expectation["metric"], expectation["units"], expectation["period_end"])
            or instant(expectation["captured_at"]) >= instant(actual["published_at"])):
        raise ValueError("Surprise requires a comparable expectation available before the release")
    return {"status": "AVAILABLE", "value": actual["value"] - expectation["value"],
            "units": actual["units"], "available_at": actual["available_at"],
            "input_hashes": [actual["record_hash"], expectation["record_hash"]]}


def coverage_audit(root: Path) -> dict:
    rows = load_observations(root)
    qualified = [row for row in rows if not row["quality_flags"] and all(row[key] is not None for key in TIMES)]
    return {"schema_version": "meta-research-coverage-v1", "records": len(rows),
            "qualified_records": len(qualified), "unknown_availability_records": sum(
                any(row[key] is None for key in TIMES) for row in rows),
            "entities": sorted({row["entity"] for row in qualified}),
            "source_versions": sorted({row["source_version"] for row in rows}),
            "availability_lanes": {lane: sum((row["schema_version"] == RECONSTRUCTED_VERSION) ==
                (lane == "HISTORICAL_RECONSTRUCTION") for row in qualified) for lane in LANES},
            "dataset_hash": digest(sorted(row["record_hash"] for row in rows)),
            "training_status": "REQUIRES_UNIVERSE_LABEL_AND_LICENSE_AUDIT" if qualified else "BLOCKED_NO_QUALIFIED_HISTORY"}


def ingest_packet(root: Path, packet_path: Path) -> list[Path]:
    """Start new research observations at their actual captured cutoff.

    Historical price histories inside this packet are not backdated. A derived
    feature is conservatively available only when ingested by this research store;
    the original packet cutoff is retained separately. No historical first-seen
    time is inferred from a saved report.
    """
    from spy_predictor_quant.meta_observation import _verified

    packet = _verified(packet_path, "packet_hash")
    timestamp = datetime.now(timezone.utc).isoformat()
    paths = []
    existing = {(row["entity"], row["metric"], row["revision_id"]): row["record_hash"]
                for row in load_observations(root)}
    for entity, instrument in packet.get("instruments", {}).items():
        for name, units in (("latest_close", "USD"), ("return5_pct", "percent"),
                            ("return21_pct", "percent"), ("return63_pct", "percent"),
                            ("realized_vol63_pct", "percent"), ("price_to_sma20", "ratio"),
                            ("price_to_sma50", "ratio"), ("price_to_sma200", "ratio")):
            value = instrument.get(name)
            if not finite(value):
                continue
            row = {"schema_version": VERSION, "entity": entity, "metric": name,
                   "value": value, "units": units, "source_version": packet["version"],
                   "revision_id": packet["packet_hash"], "source_hash": packet["packet_hash"],
                   "quality_flags": [] if instrument.get("status") == "FRESH" else ["UNQUALIFIED_PRICE_HISTORY"],
                   "period_start": None, "period_end": None,
                   **{name: timestamp for name in TIMES}, "effective_at": packet["as_of"],
                   "availability_basis": "CONSERVATIVE_FIRST_RESEARCH_INGESTION_TIME",
                   "source_period_end": instrument.get("price_date"),
                   "historical_reconstruction": False, "original_packet_cutoff": packet["as_of"]}
            prior = existing.get((entity, name, packet["packet_hash"]))
            paths.append(root / "observations" / f"{prior}.json" if prior else append_observation(root, row))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["ingest", "ingest-packet", "freeze", "audit"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--cutoff")
    parser.add_argument("--lane", choices=LANES, default="CAPTURED_LIVE")
    args = parser.parse_args()
    if args.command == "ingest":
        if not args.input:
            parser.error("ingest requires --input (JSON list of observations)")
        rows = json.loads(args.input.read_text())
        for row in rows:
            validate_observation(row)
        result = {"paths": [str(append_observation(args.root, row)) for row in rows]}
    elif args.command == "ingest-packet":
        if not args.input:
            parser.error("ingest-packet requires --input (immutable packet)")
        result = {"paths": [str(path) for path in ingest_packet(args.root, args.input)]}
    elif args.command == "freeze":
        if not args.input or not args.cutoff:
            parser.error("freeze requires --input (feature registry) and --cutoff")
        result = {"path": str(freeze_features(args.root, args.cutoff, json.loads(args.input.read_text()), lane=args.lane))}
    else:
        result = coverage_audit(args.root)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
