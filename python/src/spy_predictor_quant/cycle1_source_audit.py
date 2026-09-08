"""Immutable source-qualification contract for CYCLE-ASYMMETRY-001."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from spy_predictor_quant.cycle1_config import Cycle1Plan
from spy_predictor_quant.market_archive import content_hash


@dataclass(frozen=True)
class Cycle1SourceAudit:
    raw: dict[str, Any]
    audit_hash: str
    accepted_series: tuple[str, ...]
    excluded_series: tuple[str, ...]


def audit_identity(payload: dict[str, Any]) -> str:
    core = {key: value for key, value in payload.items() if key != "auditHash"}
    return content_hash(core)


def load_cycle1_source_audit(
    path: Path,
    *,
    plan: Cycle1Plan,
    schema_path: Path | None = None,
) -> Cycle1SourceAudit:
    return _load_cycle1_source_audit(
        path, plan=plan, schema_path=schema_path, require_plan_match=True
    )


def _load_cycle1_source_audit(
    path: Path,
    *,
    plan: Cycle1Plan,
    schema_path: Path | None = None,
    require_plan_match: bool,
) -> Cycle1SourceAudit:
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = str(payload.get("schemaVersion", ""))
    schema_file = schema_path or _default_schema_path(path, version)
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise ValueError(
            "Invalid Cycle 1 source audit: "
            + "; ".join(error.message for error in errors)
        )
    if require_plan_match and payload["preregistrationHash"] != plan.config_hash:
        raise ValueError("Source audit preregistration hash does not match the plan")
    expected_hash = audit_identity(payload)
    if payload["auditHash"] != expected_hash:
        raise ValueError("Cycle 1 source audit hash mismatch")
    if payload["containsModelOutput"] or payload["paidSubscriptionRequired"]:
        raise ValueError("Source audit must contain no model output and require no paid data")

    series = [entry for provider in payload["providers"] for entry in provider["series"]]
    ids = [entry["seriesId"] for entry in series]
    if len(ids) != len(set(ids)):
        raise ValueError("Source audit series identifiers must be unique")
    v1_required = {
        "SHILLER_IE_DATA_CAPE", "DGS3MO", "CPIAUCSL", "NFCI", "INDPRO",
        "BAA", "ALPACA_SPY_QQQ_DAILY_SIP_RAW",
        "ALPACA_SPY_QQQ_CORPORATE_ACTIONS", "QQQ_SPECIFIC_HISTORICAL_VALUATION",
    }
    decisions = {entry["seriesId"]: entry["decision"] for entry in series}
    if version == "cycle1-source-audit-v1":
        if set(ids) != v1_required:
            raise ValueError(
                "Source audit does not cover the complete frozen source inventory"
            )
        if decisions["BAA"] != "EXCLUDED" or decisions[
            "QQQ_SPECIFIC_HISTORICAL_VALUATION"
        ] != "EXCLUDED":
            raise ValueError(
                "License-incompatible BAA and unproven QQQ valuation must be excluded"
            )
        accepted_set = {
            key for key, value in decisions.items() if value != "EXCLUDED"
        }
        excluded_set = {
            key for key, value in decisions.items() if value == "EXCLUDED"
        }
    elif version == "cycle1-source-audit-v2":
        required_delta = {
            "IBKR_SPY_QQQ_DAILY_TRADES",
            "IBKR_SPY_QQQ_DAILY_ADJUSTED_LAST",
            "SSGA_SPY_HISTORICAL_DISTRIBUTIONS",
            "INVESCO_QQQ_HISTORICAL_DISTRIBUTIONS",
            "TIINGO_SPY_QQQ_EOD_STARTER",
        }
        if set(ids) != required_delta:
            raise ValueError("Source audit v2 replacement inventory is incomplete")
        unchanged = set(payload["baseAudit"]["unchangedSeries"])
        if unchanged != v1_required:
            raise ValueError("Source audit v2 base inventory does not match v1")
        base_path = _repo_relative(path, str(payload["baseAudit"]["path"]))
        base = _load_cycle1_source_audit(
            base_path, plan=plan, require_plan_match=False
        )
        if base.audit_hash != payload["baseAudit"]["auditHash"]:
            raise ValueError("Source audit v2 base-audit hash mismatch")
        if decisions["TIINGO_SPY_QQQ_EOD_STARTER"] != "EXCLUDED":
            raise ValueError("Tiingo Starter storage-incompatible data must be excluded")
        for required_id in required_delta - {"TIINGO_SPY_QQQ_EOD_STARTER"}:
            if decisions[required_id] == "EXCLUDED":
                raise ValueError(f"Source audit v2 unexpectedly excludes {required_id}")
        accepted_set = set(base.accepted_series) | {
            key for key, value in decisions.items() if value != "EXCLUDED"
        }
        excluded_set = set(base.excluded_series) | {
            key for key, value in decisions.items() if value == "EXCLUDED"
        }
    elif version == "cycle1-source-audit-v3":
        required_delta = {"MPRIME", "GS3M", "NFCI"}
        if set(ids) != required_delta:
            raise ValueError("Source audit v3 credit amendment inventory is incomplete")
        base_path = _repo_relative(path, str(payload["baseAudit"]["path"]))
        base = _load_cycle1_source_audit(
            base_path, plan=plan, require_plan_match=False
        )
        if base.audit_hash != payload["baseAudit"]["auditHash"]:
            raise ValueError("Source audit v3 base-audit hash mismatch")
        base_inventory = set(base.accepted_series) | set(base.excluded_series)
        unchanged = set(payload["baseAudit"]["unchangedSeries"])
        if unchanged != base_inventory - {"NFCI"}:
            raise ValueError("Source audit v3 unchanged inventory does not match v2")
        if decisions != {
            "MPRIME": "ACCEPTED",
            "GS3M": "ACCEPTED",
            "NFCI": "ACCEPTED_DIAGNOSTIC_ONLY",
        }:
            raise ValueError("Source audit v3 credit decisions differ from qualification")
        source_plan = payload["runtimeSourcePlan"]
        if source_plan.get("coreMacroSeries") != [
            "DGS3MO", "CPIAUCSL", "INDPRO", "MPRIME", "GS3M"
        ]:
            raise ValueError("Source audit v3 core macro series are not frozen")
        spread = source_plan.get("creditSpread", {})
        if spread != {
            "numeratorSeries": "MPRIME",
            "denominatorSeries": "GS3M",
            "formula": "MPRIME_t-GS3M_t",
            "alignment": "latest-common-observation-month-whose-both-vintages-were-published-by-cutoff",
        }:
            raise ValueError("Source audit v3 credit spread contract differs")
        accepted_set = (set(base.accepted_series) - {"NFCI"}) | set(required_delta)
        excluded_set = set(base.excluded_series)
    else:
        raise ValueError(f"Unsupported Cycle 1 source audit version {version}")
    accepted = tuple(sorted(accepted_set))
    excluded = tuple(sorted(excluded_set))
    return Cycle1SourceAudit(payload, expected_hash, accepted, excluded)


def _default_schema_path(path: Path, version: str) -> Path:
    filenames = {
        "cycle1-source-audit-v1": "cycle1-source-audit.schema.json",
        "cycle1-source-audit-v2": "cycle1-source-audit-v2.schema.json",
        "cycle1-source-audit-v3": "cycle1-source-audit-v3.schema.json",
    }
    filename = filenames.get(version, "cycle1-source-audit.schema.json")
    for parent in path.resolve().parents:
        candidate = parent / "schemas" / filename
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Cannot locate Cycle 1 source-audit schema")


def _repo_relative(path: Path, relative: str) -> Path:
    for parent in path.resolve().parents:
        candidate = parent / relative
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Cannot locate source-audit dependency {relative}")
