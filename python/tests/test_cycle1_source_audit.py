from __future__ import annotations

import json
from pathlib import Path

import pytest

from spy_predictor_quant.cycle1_config import load_cycle1_plan
from spy_predictor_quant.cycle1_source_audit import (
    audit_identity,
    load_cycle1_source_audit,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "config" / "cycle1.json"
AUDIT = REPO_ROOT / "config" / "cycle1-source-audit.json"
AUDIT_V2 = REPO_ROOT / "config" / "cycle1-source-audit-v2.json"
AUDIT_V3 = REPO_ROOT / "config" / "cycle1-source-audit-v3.json"
CONFIG_SCHEMA = REPO_ROOT / "schemas" / "cycle1-config.schema.json"
AUDIT_SCHEMA = REPO_ROOT / "schemas" / "cycle1-source-audit.schema.json"


def test_source_audit_is_pinned_complete_and_contains_no_results() -> None:
    plan = load_cycle1_plan(CONFIG)
    audit = load_cycle1_source_audit(AUDIT_V3, plan=plan)
    assert audit.raw["containsModelOutput"] is False
    assert audit.raw["paidSubscriptionRequired"] is False
    assert "BAA" in audit.excluded_series
    assert "QQQ_SPECIFIC_HISTORICAL_VALUATION" in audit.excluded_series
    assert {"DGS3MO", "CPIAUCSL", "NFCI", "INDPRO", "MPRIME", "GS3M"} <= set(
        audit.accepted_series
    )


def test_audit_hash_detects_mutation(tmp_path: Path) -> None:
    plan = load_cycle1_plan(CONFIG)
    payload = json.loads(AUDIT_V3.read_text(encoding="utf-8"))
    payload["providers"][0]["series"][0]["decisionReason"] += " changed"
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_cycle1_source_audit(
            path,
            plan=plan,
            schema_path=REPO_ROOT / "schemas/cycle1-source-audit-v3.schema.json",
        )


def test_audit_is_invalidated_by_preregistration_change(tmp_path: Path) -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    payload["promotionGates"]["returnDistribution"]["minimumRelativeImprovement"] = 0.03
    config = tmp_path / "cycle1.json"
    config.write_text(json.dumps(payload), encoding="utf-8")
    changed_plan = load_cycle1_plan(config, schema_path=CONFIG_SCHEMA)
    with pytest.raises(ValueError, match="preregistration hash"):
        load_cycle1_source_audit(AUDIT_V3, plan=changed_plan)


def test_every_series_records_required_qualification_fields() -> None:
    payload = json.loads(AUDIT_V3.read_text(encoding="utf-8"))
    required = {
        "seriesId", "requestUrl", "endpointSemantics", "fieldSemantics",
        "coverageStart", "coverageEndRule", "frequency", "publicationBehavior",
        "revisionBehavior", "pointInTimeTier", "licenseRestriction",
        "missingnessPolicy", "releaseLagRule", "decision", "decisionReason",
    }
    for provider in payload["providers"]:
        for series in provider["series"]:
            assert required == set(series)


def test_source_audit_v3_preserves_v2_and_freezes_credit_amendment() -> None:
    plan = load_cycle1_plan(CONFIG)
    audit = load_cycle1_source_audit(AUDIT_V3, plan=plan)
    base_payload = json.loads(AUDIT_V2.read_text(encoding="utf-8"))
    assert audit.raw["baseAudit"]["auditHash"] == audit_identity(base_payload)
    assert "TIINGO_SPY_QQQ_EOD_STARTER" in audit.excluded_series
    assert {
        "IBKR_SPY_QQQ_DAILY_TRADES",
        "SSGA_SPY_HISTORICAL_DISTRIBUTIONS",
        "INVESCO_QQQ_HISTORICAL_DISTRIBUTIONS",
        "MPRIME",
        "GS3M",
    } <= set(audit.accepted_series)
    decisions = {
        series["seriesId"]: series["decision"]
        for provider in audit.raw["providers"]
        for series in provider["series"]
    }
    assert decisions["NFCI"] == "ACCEPTED_DIAGNOSTIC_ONLY"
    assert audit.raw["containsModelOutput"] is False
