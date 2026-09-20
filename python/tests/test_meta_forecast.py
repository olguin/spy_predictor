from copy import deepcopy
import json

import pytest
from jsonschema import Draft202012Validator

from spy_predictor_quant.meta_analysis import digest
from spy_predictor_quant.meta_forecast import (
    STRUCTURED_SCHEMA, build_structured_forecast, create_structured_forecast, load_policy,
)


def packet():
    value = {
        "packet_hash": "packet-fixture",
        "version": "meta-analysis-v1",
        "as_of": "2026-09-14T20:25:00+00:00",
        "symbols": ["SPY"],
        "evidence": {f"{role}-evidence": {"kind": "test", "symbols": ["SPY"]}
                     for role in ("macro_cycle", "technical", "fundamental", "news", "geopolitical")},
        "instruments": {"SPY": {
            "status": "FRESH", "price_date": "2026-09-14",
            "latest_close": 100.0, "realized_vol63_pct": 20.0,
            "support_resistance_candidates": {"20_session": {"support_close": 95.0, "resistance_close": 101.0}},
            "price_to_sma20": 1.03, "price_to_sma50": 1.06, "price_to_sma200": 1.12,
            "return5_pct": 3.0, "return21_pct": 6.0, "return63_pct": 14.0,
            "relative_strength_vs_spy": {
                "5_sessions_percentage_points": 0.0,
                "21_sessions_percentage_points": 0.0,
                "63_sessions_percentage_points": 0.0,
            },
        }},
        "transparent_risk_appetite": {"value": 70.0},
    }
    return value


def assessment(role, view="BULLISH", supported=True, trigger=False):
    claims = ([{"claim_id": f"{role}-claim", "classification": "INFERENCE",
                "stance": "SUPPORT", "evidence_family": role,
                "statement": f"{role} supports the scenario", "evidence_ids": [f"{role}-evidence"],
                "horizons": [5, 21, 63], "invalidation": "New evidence", "numeric_values": [
                    {"packet_path": "/instruments/SPY/support_resistance_candidates/20_session/resistance_close", "value": 101.0},
                    {"packet_path": "/instruments/SPY/support_resistance_candidates/20_session/support_close", "value": 95.0}]}]
              if supported else [])
    confirmation = ({"availability": "AVAILABLE", "field": "completed close", "comparison": "ABOVE", "level": 101.0,
                     "units": "USD", "confirmation_interval": "one completed session",
                     "expiry": "2026-09-18T20:00:00+00:00", "evidence_ids": [f"{role}-evidence"]}
                    if trigger else None)
    return {
        "symbol": "SPY", "status": "SUPPORTED" if supported else "INSUFFICIENT_EVIDENCE",
        "view": view if supported else "UNKNOWN", "thesis": "Fixture",
        "counterevidence": ["Downside case"], "invalidation": ["Trend breaks"],
        "missing": [] if supported else ["evidence"],
        "claims": claims,
        "horizon_assessments": [{"trading_days": horizon,
            "status": "SUPPORTED" if supported else "INSUFFICIENT_EVIDENCE",
            "direction": view if supported else "UNKNOWN",
            "strongest_support_claim_ids": [f"{role}-claim"] if supported else [],
            "strongest_opposition_claim_ids": [], "action_implication": "Fixture implication",
            "confirmation": confirmation, "invalidation_trigger": None,
            "missing_evidence": [] if supported else [{"item": "evidence", "criticality": "CRITICAL"}],
            "review": {"when": "next close", "event": "new evidence"}}
            for horizon in (5, 21, 63)],
    }


def report(*, supported_roles=5, view="BULLISH", trigger=False):
    roles = ("macro_cycle", "technical", "fundamental", "news", "geopolitical")
    results = {role: {"assessments": [assessment(role, view=view,
               supported=index < supported_roles, trigger=trigger and role == "technical")]}
               for index, role in enumerate(roles)}
    results["critic"] = {"assessments": [assessment("critic", view="NEUTRAL")],
        "claim_decisions": [{"claim_ref": f"{role}:{role}-claim", "decision": "ACCEPT",
                             "materiality": "MATERIAL", "reason": "verified", "correction": None}
                            for role in roles[:supported_roles]]}
    return {"packet_hash": "packet-fixture", "completed_at": "2026-09-13T20:00:00+00:00",
            "runtime_config_hash": "runtime", "harness_implementation_sha256": "harness",
            "validation": "META_AGENT_V3_HORIZON_DECISIONS_AND_CRITIC_CLAIM_GATES",
            "results": results, "failures": {}}


def test_structured_forecast_is_deterministic_horizon_scoped_and_uncalibrated():
    policy = load_policy()
    first = build_structured_forecast(packet(), report(), policy)
    second = build_structured_forecast(packet(), report(), policy)
    assert first == second
    assert first["calibration_status"] == "NOT_QUALIFIED_INSUFFICIENT_PROSPECTIVE_EVIDENCE"
    rows = first["symbols"]["SPY"]["horizons"]
    assert [row["trading_days"] for row in rows] == [5, 21, 63]
    for row in rows:
        distribution = row["distribution"]
        assert sum(distribution["probabilities"].values()) == pytest.approx(1)
        assert distribution["probability_price_up"] > .5
        assert distribution["status"] == "EXPERIMENTAL_UNCALIBRATED"
        assert set(row["ablations"]) == {
            "without_macro_cycle", "without_technical", "without_fundamental",
            "without_news", "without_geopolitical"}
        assert row["recommendation"]["portfolio_sizing"] == "OUT_OF_SCOPE"
        assert row["recommendation"]["action_now"] == "BULLISH_RESEARCH"
        assert row["reference"]["reference_price"] == 100
        assert row["reference"]["reference_price_basis"] == "LATEST_COMPLETED_SESSION_CLOSE"
        assert row["reference"]["target_trading_session"] is not None
        assert "intraday entry" in row["reference"]["entry_basis_warning"]
        assert "evidence_quality" not in row


def test_persisted_structured_forecast_validates_after_provenance_is_added(tmp_path):
    packet_value = packet()
    packet_value.pop("packet_hash")
    packet_value["packet_hash"] = digest(packet_value)
    report_value = report()
    report_value["packet_hash"] = packet_value["packet_hash"]
    packet_path = tmp_path / "packet.json"
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "forecast.json"
    packet_path.write_text(json.dumps(packet_value))
    report_path.write_text(json.dumps(report_value))
    create_structured_forecast(packet_path, report_path, output_path)
    persisted = json.loads(output_path.read_text())
    Draft202012Validator(json.loads(STRUCTURED_SCHEMA.read_text())).validate(persisted)
    assert persisted["agent_report_sha256"]
    assert persisted["policy_identity"] == "meta-forecast-policy-v2.json"
    assert persisted["artifact_hash"]


def test_context_abstention_blocks_recommendation_when_evidence_quality_is_low():
    result = build_structured_forecast(packet(), report(supported_roles=0), load_policy())
    row = result["symbols"]["SPY"]["horizons"][0]
    assert row["context_signal"]["status"] == "INSUFFICIENT_ACCEPTED_ROLES"
    assert row["recommendation"]["action_now"] == "WAIT"

    one_role = build_structured_forecast(packet(), report(supported_roles=1), load_policy())
    context = one_role["symbols"]["SPY"]["horizons"][0]["context_signal"]
    assert context["covered_role_count"] == 1
    assert context["disagreement_range"] is None
    assert context["disagreement_stddev"] is None


def test_policy_rejects_weight_and_threshold_drift(tmp_path):
    policy = load_policy()
    bad = deepcopy(policy)
    bad["role_weights"]["technical"] = .9
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="weights"):
        load_policy(path)
    bad = deepcopy(policy)
    bad["recommendation_policy"]["bearish_research_probability"] = .49
    bad["recommendation_policy"]["reduce_risk_probability"] = .40
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="thresholds"):
        load_policy(path)


def test_structured_forecast_rejects_pre_claim_level_agent_report():
    old = report()
    old["validation"] = "SCHEMA_AND_CITATION_MEMBERSHIP_ONLY;SEMANTIC_CLAIMS_REQUIRE_REVIEW"
    with pytest.raises(ValueError, match="claim-level"):
        build_structured_forecast(packet(), old, load_policy())


def test_rejected_and_duplicated_claims_cannot_change_probabilities():
    baseline_report = report()
    baseline = build_structured_forecast(packet(), baseline_report, load_policy())
    changed = deepcopy(baseline_report)
    extra = deepcopy(changed["results"]["news"]["assessments"][0]["claims"][0])
    extra["claim_id"] = "duplicated-opposite"
    extra["stance"] = "OPPOSE"
    changed["results"]["news"]["assessments"][0]["claims"].append(extra)
    changed["results"]["critic"]["claim_decisions"].append({
        "claim_ref": "news:duplicated-opposite", "decision": "REJECT",
        "materiality": "MATERIAL", "reason": "duplicate", "correction": None})
    assert (build_structured_forecast(packet(), changed, load_policy())["symbols"]["SPY"]["horizons"][0]
            ["distribution"]["probability_price_up"]
            == baseline["symbols"]["SPY"]["horizons"][0]["distribution"]["probability_price_up"])


def test_mixed_is_conflict_and_conditional_action_requires_measurable_trigger():
    mixed = build_structured_forecast(packet(), report(view="MIXED"), load_policy())
    assert mixed["symbols"]["SPY"]["horizons"][0]["recommendation"]["action_now"] == "WAIT"
    no_trigger = build_structured_forecast(packet(), report(view="NEUTRAL"), load_policy())
    row = no_trigger["symbols"]["SPY"]["horizons"][0]
    assert .55 <= row["distribution"]["probability_price_up"] < .60
    assert row["recommendation"]["action_now"] == "WAIT"
    assert "MEASURABLE_ENTRY_TRIGGER_REQUIRED" in row["recommendation"]["reason_codes"]
    confirmed = build_structured_forecast(packet(), report(view="NEUTRAL", trigger=True), load_policy())
    assert confirmed["symbols"]["SPY"]["horizons"][0]["recommendation"]["action_now"] == "ENTER_IF_CONFIRMED"
