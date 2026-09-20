"""Deterministic experimental META distributions and decision policy.

The v2 engine consumes horizon-specific specialist records and the critic's
claim decisions. It never asks an LLM for probabilities, excludes rejected
claims mechanically, and exposes coverage rather than a confidence percentage.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import NormalDist, pstdev

from jsonschema import Draft202012Validator

from spy_predictor_quant.market_archive import file_sha256, write_json_exclusive
from spy_predictor_quant.meta_analysis import HORIZONS, digest
from spy_predictor_quant.meta_observation import _verified
from spy_predictor_quant.meta_contracts import (
    audit_trigger, finite, quarantined, reference_contract, require_unique_claims,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY = ROOT / "config/meta-forecast-policy-v2.json"
POLICY_SCHEMAS = {
    "meta-forecast-policy-v1": ROOT / "schemas/meta-forecast-policy-v1.schema.json",
    "meta-forecast-policy-v2": ROOT / "schemas/meta-forecast-policy-v2.schema.json",
}
STRUCTURED_SCHEMA = ROOT / "schemas/meta-structured-forecast-v3.schema.json"
INDEPENDENT_ROLES = ("macro_cycle", "technical", "fundamental", "news", "geopolitical")
QUANTILE_LEVELS = (.05, .10, .25, .50, .75, .90, .95)
VALIDATIONS = {
    "SCHEMA_CLAIM_CITATION_AND_NUMERIC_PATHS;SEMANTIC_CLAIMS_REQUIRE_REVIEW",
    "META_AGENT_V3_HORIZON_DECISIONS_AND_CRITIC_CLAIM_GATES",
        "META_AGENT_V4_OBSERVATIONS_AND_HYPOTHESIS_EDGES",
}


def load_policy(path: Path = DEFAULT_POLICY) -> dict:
    policy = json.loads(path.read_text())
    version = policy.get("schema_version")
    if version not in POLICY_SCHEMAS:
        raise ValueError("Unsupported META forecast policy")
    Draft202012Validator(json.loads(POLICY_SCHEMAS[version].read_text())).validate(policy)
    if not math.isclose(sum(policy["role_weights"].values()), 1, abs_tol=1e-12):
        raise ValueError("META role weights must sum to one")
    combination = policy["combination"]
    if not math.isclose(combination["quant_weight"] + combination["context_weight"], 1,
                        abs_tol=1e-12):
        raise ValueError("META quant/context weights must sum to one")
    if combination["quant_weight"] <= 0:
        raise ValueError("A positive quant weight is required for the fallback baseline")
    rules = policy["recommendation_policy"]
    conditional = rules.get("conditional_entry_probability",
                            rules.get("accumulate_conditionally_probability"))
    if not (rules["bearish_research_probability"] <= rules["reduce_risk_probability"] < .5
            < conditional <= rules["bullish_research_probability"]):
        raise ValueError("META recommendation thresholds are not ordered")
    return policy


def _clip(value: float, low: float = -1, high: float = 1) -> float:
    return min(high, max(low, value))


def _assessment(report: dict, role: str, symbol: str) -> dict | None:
    rows = report.get("results", {}).get(role, {}).get("assessments", [])
    selected = [row for row in rows if row.get("symbol") == symbol]
    return selected[0] if len(selected) == 1 else None


def _horizon_assessment(assessment: dict | None, horizon: int) -> dict | None:
    """Read v3 horizon output, with a bounded adapter for frozen v2 reports."""
    if not assessment:
        return None
    rows = [row for row in assessment.get("horizon_assessments", [])
            if row.get("trading_days") == horizon]
    if "horizon_assessments" in assessment:
        return rows[0] if len(rows) == 1 else None
    claims = [claim for claim in assessment.get("claims", [])
              if horizon in claim.get("horizons", [])]
    if not claims or assessment.get("status") != "SUPPORTED":
        return None
    return {"trading_days": horizon, "status": "SUPPORTED",
            "direction": assessment.get("view", "UNKNOWN"),
            "strongest_support_claim_ids": [claim["claim_id"] for claim in claims[:1]],
            "strongest_opposition_claim_ids": [],
            "action_implication": assessment.get("thesis", ""),
            "confirmation": None, "invalidation_trigger": None,
            "missing_evidence": [{"item": value, "criticality": "ADVISORY"}
                                 for value in assessment.get("missing", [])],
            "review": {"when": "At the next scheduled review", "event": "New evidence"}}


def _claim_decisions(report: dict) -> dict[str, dict]:
    critic = report.get("results", {}).get("critic", {})
    rows = critic.get("claim_decisions", [])
    refs = [row["claim_ref"] for row in rows]
    if len(refs) != len(set(refs)):
        raise ValueError("Critic decisions must be unique")
    return {row["claim_ref"]: row for row in rows}


def _accepted_claims(report: dict, role: str, assessment: dict, horizon: int) -> list[dict]:
    decisions = _claim_decisions(report)
    strict = report.get("validation") in {"META_AGENT_V3_HORIZON_DECISIONS_AND_CRITIC_CLAIM_GATES",
                                           "META_AGENT_V4_OBSERVATIONS_AND_HYPOTHESIS_EDGES"}
    accepted = []
    for claim in assessment.get("claims", []):
        if (quarantined(report, role, assessment["symbol"], horizon, claim["claim_id"])
                or horizon not in claim.get("horizons", [])):
            continue
        decision = decisions.get(f"{role}:{claim['claim_id']}")
        if (decision and decision.get("decision") == "ACCEPT") or (not strict and not decisions):
            accepted.append(claim)
    return accepted


def _context_signals(report: dict, symbol: str, horizon: int, policy: dict,
                     excluded_role: str | None = None) -> dict:
    scores = policy.get("direction_scores", policy.get("view_scores", {}))
    decisions = _claim_decisions(report)
    signals, conflicts, unresolved, coverage = [], [], [], []
    evidence_signatures: dict[frozenset[str], str] = {}
    for role in INDEPENDENT_ROLES:
        if role == excluded_role:
            continue
        assessment = _assessment(report, role, symbol)
        horizon_row = _horizon_assessment(assessment, horizon)
        if quarantined(report, role, symbol, horizon):
            coverage.append({"role": role, "status": "QUARANTINED", "accepted_claims": 0})
            continue
        if not assessment or not horizon_row or horizon_row.get("status") != "SUPPORTED":
            coverage.append({"role": role, "status": "MISSING", "accepted_claims": 0})
            continue
        for claim in assessment.get("claims", []):
            decision = decisions.get(f"{role}:{claim['claim_id']}")
            if (horizon in claim.get("horizons", []) and decision
                    and decision["decision"] == "NEEDS_VERIFICATION"
                    and decision.get("materiality") == "MATERIAL"):
                unresolved.append(f"{role}:{claim['claim_id']}")
        direction = horizon_row.get("direction", assessment.get("view", "UNKNOWN"))
        accepted = _accepted_claims(report, role, assessment, horizon)
        support_refs = set(horizon_row.get("strongest_support_claim_ids", []))
        opposition_refs = set(horizon_row.get("strongest_opposition_claim_ids", []))
        if (support_refs & opposition_refs or not (support_refs | opposition_refs) <=
                {claim["claim_id"] for claim in accepted}):
            coverage.append({"role": role, "status": "UNACCEPTED_HYPOTHESIS_EDGE", "accepted_claims": 0})
            continue
        allowed_stances = ({"SUPPORT"} if direction in {"BULLISH", "BEARISH"}
                           else {"SUPPORT", "CONTEXT"})
        usable = [claim for claim in accepted
                  if ((report.get("validation") == "META_AGENT_V4_OBSERVATIONS_AND_HYPOTHESIS_EDGES"
                       or claim.get("stance", "SUPPORT") in allowed_stances)
                      and (not support_refs or claim["claim_id"] in support_refs))]
        if direction in {"BULLISH", "BEARISH"} and not support_refs:
            usable = []
        if direction == "MIXED":
            conflicts.append(role)
            coverage.append({"role": role, "status": "CONFLICT", "accepted_claims": len(usable)})
            continue
        if direction not in scores or not usable:
            coverage.append({"role": role, "status": "UNSUPPORTED", "accepted_claims": len(usable)})
            continue
        evidence_ids = frozenset(identity for claim in usable for identity in claim.get("evidence_ids", []))
        dependencies = report.get("evidence_dependencies", {})
        signature = frozenset(dependencies.get(identity, identity) for identity in evidence_ids)
        duplicate_role = next((prior_role for prior_ids, prior_role in evidence_signatures.items()
                               if signature & prior_ids), None)
        if signature and duplicate_role:
            coverage.append({"role": role, "status": "CORRELATED_DUPLICATE", "accepted_claims": len(usable),
                             "duplicates_role": duplicate_role})
            continue
        if evidence_ids:
            evidence_signatures[signature] = role
        signals.append({"role": role, "direction": direction, "signal": scores[direction],
                        "configured_weight": policy["role_weights"][role],
                        "accepted_claim_refs": [f"{role}:{claim['claim_id']}" for claim in usable],
                        "evidence_ids": sorted(evidence_ids)})
        coverage.append({"role": role, "status": "ACCEPTED", "accepted_claims": len(usable)})
    denominator = sum(row["configured_weight"] for row in signals)
    score = sum(row["signal"] * row["configured_weight"] for row in signals) / denominator if denominator else None
    values = [row["signal"] for row in signals]
    minimum = policy["combination"].get("minimum_accepted_context_roles",
                                        policy["combination"].get("minimum_supported_context_roles"))
    return {"status": "AVAILABLE" if len(signals) >= minimum else "INSUFFICIENT_ACCEPTED_ROLES",
            "score": score, "accepted_roles": len(signals), "role_signals": signals,
            "evidence_family_coverage": coverage,
            "covered_role_count": sum(row["status"] == "ACCEPTED" for row in coverage),
            "total_role_count": len(coverage), "conflicting_roles": conflicts,
            "unresolved_material_claims": sorted(set(unresolved)),
            "disagreement_range": max(values) - min(values) if len(values) > 1 else None,
            "disagreement_stddev": pstdev(values) if len(values) > 1 else None,
            "excluded_role": excluded_role, "contract": "HORIZON_ACCEPTED_CLAIMS"}


def _quant_signals(packet: dict, symbol: str, horizon: int) -> dict:
    instrument = packet.get("instruments", {}).get(symbol, {})
    if instrument.get("status") != "FRESH":
        return {"status": "MISSING", "score": None, "features": [],
                "reason": "FRESH_COMPLETED_DAILY_TECHNICALS_REQUIRED"}
    annual_vol = instrument.get("realized_vol63_pct")
    if not finite(annual_vol) or annual_vol <= 0:
        return {"status": "MISSING", "score": None, "features": [], "reason": "POSITIVE_RV63_REQUIRED"}
    features, trend_parts = [], []
    for window, scale in ((20, .03), (50, .06), (200, .12)):
        value = instrument.get(f"price_to_sma{window}")
        if finite(value):
            trend_parts.append(_clip((value - 1) / scale))
    if trend_parts:
        features.append({"name": "multi_window_trend", "value": sum(trend_parts) / len(trend_parts),
                         "formula": "mean clip((price/SMA-1)/[3%,6%,12%])"})
    lookback = horizon
    scale = annual_vol * math.sqrt(lookback / 252)
    momentum = instrument.get(f"return{lookback}_pct")
    if finite(momentum) and scale > 0:
        features.append({"name": f"return{lookback}_vol_scaled", "value": _clip(momentum / scale),
                         "formula": f"clip(return{lookback}_pct/(RV63*sqrt({lookback}/252)))"})
    relative = instrument.get("relative_strength_vs_spy", {}).get(f"{lookback}_sessions_percentage_points")
    if finite(relative) and scale > 0:
        features.append({"name": f"relative_strength_vs_spy_{lookback}", "value": _clip(relative / scale),
                         "formula": "clip(asset return minus SPY return / asset volatility scale)"})
    appetite = packet.get("transparent_risk_appetite", {}).get("value")
    if finite(appetite):
        features.append({"name": "transparent_risk_appetite", "value": _clip((appetite - 50) / 50),
                         "formula": "clip((transparent risk appetite-50)/50)"})
    if not features:
        return {"status": "MISSING", "score": None, "features": [], "reason": "NO_QUALIFIED_QUANT_FEATURES"}
    return {"status": "AVAILABLE", "score": sum(row["value"] for row in features) / len(features),
            "features": features, "annual_volatility_pct": annual_vol,
            "feature_coverage": {"available": len(features), "expected": 4}}


def _distribution(price: float, annual_vol_pct: float, horizon: int, score: float,
                  maximum_shift: float, *, variant: str) -> dict:
    sigma = annual_vol_pct / 100 * math.sqrt(horizon / 252)
    mean = _clip(score) * maximum_shift * sigma
    threshold = {5: .02, 21: .05, 63: .10}[horizon]
    normal = NormalDist()
    bear = normal.cdf((math.log1p(-threshold) - mean) / sigma)
    bull = 1 - normal.cdf((math.log1p(threshold) - mean) / sigma)
    return {"variant": variant, "trading_days": horizon, "return_threshold_pct": threshold * 100,
            "event_definitions": {
                "price_up": "terminal completed-session close is above the reference completed-session close",
                "bear": f"terminal completed-session return is below {-100 * threshold:.1f}%",
                "neutral": f"terminal completed-session return is between {-100 * threshold:.1f}% and {100 * threshold:.1f}% inclusive",
                "bull": f"terminal completed-session return is above {100 * threshold:.1f}%",
                "path_exclusion": "These events do not describe touching a target or avoiding a stop before the terminal close."},
            "probabilities": {"bear": bear, "neutral": 1 - bear - bull, "bull": bull},
            "probability_price_up": 1 - normal.cdf(-mean / sigma),
            "expected_simple_return_pct": 100 * (math.exp(mean + sigma * sigma / 2) - 1),
            "median_simple_return_pct": 100 * math.expm1(mean),
            "price_quantiles": {str(level): price * math.exp(mean + normal.inv_cdf(level) * sigma)
                                for level in QUANTILE_LEVELS},
            "distribution_family": "LOG_RETURN_NORMAL", "mean_log_return": mean,
            "sigma_log_return": sigma, "status": "EXPERIMENTAL_UNCALIBRATED",
            "formula": "log(P_h/P_0) ~ Normal(bounded_signal*max_shift*RV63*sqrt(h/252), (RV63/100)^2*h/252)"}


def _conditions(report: dict, packet: dict, symbol: str, horizon: int) -> dict:
    selected = {"confirmation": None, "invalidation_trigger": None}
    audits, reviews = [], []
    for role in ("technical", "macro_cycle", "fundamental", "news", "geopolitical"):
        assessment = _assessment(report, role, symbol)
        row = _horizon_assessment(assessment, horizon)
        if not assessment or not row or quarantined(report, role, symbol, horizon):
            continue
        accepted = _accepted_claims(report, role, assessment, horizon)
        evidence = {key for claim in accepted for key in claim.get("evidence_ids", [])}
        for name in selected:
            audit = audit_trigger(row.get(name), packet, symbol, evidence,
                                  [value for claim in accepted for value in claim.get("numeric_values", [])
                                   if set((row.get(name) or {}).get("evidence_ids", [])) & set(claim.get("evidence_ids", []))])
            audits.append({"source_role": role, "condition": name, **audit})
            if audit["status"] == "AVAILABLE" and selected[name] is None:
                selected[name] = {**audit["trigger"], "source_role": role}
        if row.get("review") and accepted:
            reviews.append({"source_role": role, **row["review"]})
    return {**selected, "audits": audits, "reviews": reviews}


def _gaps(report: dict, symbol: str, horizon: int) -> tuple[list[str], list[str]]:
    critical, advisory = [], []
    for role in INDEPENDENT_ROLES:
        row = _horizon_assessment(_assessment(report, role, symbol), horizon)
        for gap in (row or {}).get("missing_evidence", []):
            item = gap.get("item") if isinstance(gap, dict) else str(gap)
            target = critical if isinstance(gap, dict) and gap.get("criticality") == "CRITICAL" else advisory
            target.append(f"{role}: {item}")
    return sorted(set(critical)), sorted(set(advisory))


def _recommendation(scenario: dict, context: dict, policy: dict, report: dict, symbol: str,
                    packet: dict) -> dict:
    rules = policy["recommendation_policy"]
    p_up, horizon = scenario["probability_price_up"], scenario["trading_days"]
    conditions = _conditions(report, packet, symbol, horizon)
    trigger = conditions["confirmation"]
    critical, advisory = _gaps(report, symbol, horizon)
    reasons, blocked = [], False
    if context["status"] != "AVAILABLE":
        blocked, reasons = True, ["INSUFFICIENT_ACCEPTED_CONTEXT_ROLES"]
    if context["unresolved_material_claims"] and rules.get("unresolved_material_claims_force_wait", True):
        blocked, reasons = True, [*reasons, "UNRESOLVED_MATERIAL_CLAIMS"]
    if critical and rules.get("critical_gaps_force_wait", True):
        blocked, reasons = True, [*reasons, "CRITICAL_EVIDENCE_GAP"]
    max_disagreement = rules.get("maximum_directional_disagreement_range",
                                 rules.get("maximum_disagreement_for_directional_action"))
    if context["conflicting_roles"] or (context["disagreement_range"] is not None
                                         and context["disagreement_range"] > max_disagreement):
        blocked, reasons = True, [*reasons, "SPECIALIST_CONFLICT_OR_DISAGREEMENT"]
    conditional = rules.get("conditional_entry_probability",
                            rules.get("accumulate_conditionally_probability"))
    if blocked:
        action = "WAIT"
    elif p_up >= rules["bullish_research_probability"]:
        action, reasons = "BULLISH_RESEARCH", ["P_UP_AT_OR_ABOVE_BULLISH_RESEARCH_THRESHOLD"]
    elif p_up >= conditional:
        if rules.get("conditional_actions_require_measurable_trigger", True) and trigger is None:
            action, reasons = "WAIT", ["MEASURABLE_ENTRY_TRIGGER_REQUIRED"]
        else:
            action, reasons = "ENTER_IF_CONFIRMED", ["P_UP_AT_OR_ABOVE_CONDITIONAL_THRESHOLD"]
    elif p_up <= rules["bearish_research_probability"]:
        action, reasons = "BEARISH_RESEARCH", ["P_UP_AT_OR_BELOW_BEARISH_RESEARCH_THRESHOLD"]
    elif p_up <= rules["reduce_risk_probability"]:
        action, reasons = "REDUCE_RISK", ["P_UP_AT_OR_BELOW_RISK_REDUCTION_THRESHOLD"]
    else:
        action, reasons = "HOLD_OR_WAIT", ["P_UP_WITHIN_NO_EDGE_BAND"]
    wait_for = []
    if action == "WAIT":
        wait_for = critical + context["unresolved_material_claims"]
        if "MEASURABLE_ENTRY_TRIGGER_REQUIRED" in reasons:
            wait_for.append("a cited measurable confirmation level with comparison, interval, and expiry")
        if context["status"] != "AVAILABLE":
            wait_for.append(f"at least {policy['combination'].get('minimum_accepted_context_roles', 3)} specialist families with critic-accepted horizon claims")
    return {"action_now": action, "new_position_action": action,
            "existing_position_action": "POSITION_CONTEXT_REQUIRED",
            "decision_reason": ("WAIT_DATA" if critical or context["status"] != "AVAILABLE" else
                                "WAIT_PRICE_CONFIRMATION" if "MEASURABLE_ENTRY_TRIGGER_REQUIRED" in reasons else
                                "WAIT_EVENT" if blocked else "NO_MEASURED_EDGE"),
            "measured_edge_status": "UNPROVEN_HEURISTIC_RESEARCH_ONLY",
            "reason_codes": list(dict.fromkeys(reasons)), "conditional_trigger": trigger,
            "invalidation_trigger": conditions["invalidation_trigger"],
            "invalidation_availability": "AVAILABLE" if conditions["invalidation_trigger"] else "UNAVAILABLE",
            "condition_audits": conditions["audits"], "review_events": conditions["reviews"],
            "wait_for": list(dict.fromkeys(wait_for)),
            "next_review": "; ".join(f"{row['source_role']}: {row['when']} — {row['event']}"
                                     for row in conditions["reviews"]) or "UNAVAILABLE: no accepted specialist review event",
            "critical_gaps": critical, "advisory_gaps": advisory, "portfolio_sizing": "OUT_OF_SCOPE",
            "notice": "Deterministic research action from an uncalibrated distribution; no order or personalized sizing is implied."}


def build_structured_forecast(packet: dict, report: dict, policy: dict, *,
                              origin_kind: str = "PRIOR_COMPLETED_CLOSE") -> dict:
    if report.get("packet_hash") != packet.get("packet_hash"):
        raise ValueError("META report belongs to a different packet")
    if report.get("validation") not in VALIDATIONS:
        raise ValueError("Structured META forecast requires a validated claim-level agent contract")
    require_unique_claims(report)
    dependencies = {identity: cluster["event_id"]
                    for cluster in packet.get("event_context", {}).get("clusters", [])
                    for identity in cluster["evidence_ids"]}
    report = {**report, "evidence_dependencies": dependencies}
    symbols = {}
    for symbol in packet["symbols"]:
        instrument = packet.get("instruments", {}).get(symbol, {})
        price, annual_vol = instrument.get("latest_close"), instrument.get("realized_vol63_pct")
        if (instrument.get("status") != "FRESH" or not finite(price) or price <= 0
                or not finite(annual_vol) or annual_vol <= 0):
            symbols[symbol] = {"status": "NO_FORECAST", "reason": "FRESH_PRICE_AND_RV63_REQUIRED"}
            continue
        rows = []
        for horizon in HORIZONS:
            reference = reference_contract(packet, symbol, horizon, origin_kind)
            price = reference["reference_price"]
            quant = _quant_signals(packet, symbol, horizon)
            context = _context_signals(report, symbol, horizon, policy)
            qw = policy["combination"]["quant_weight"]
            cw = policy["combination"]["context_weight"] if context["status"] == "AVAILABLE" and context["score"] is not None else 0
            combined = ((qw * quant["score"] + cw * (context["score"] or 0)) / (qw + cw)
                        if quant.get("score") is not None and qw + cw else None)
            if combined is None:
                rows.append({"trading_days": horizon, "status": "NO_FORECAST", "reason": "NO_QUALIFIED_SIGNAL"})
                continue
            scenario = _distribution(price, annual_vol, horizon, combined,
                                     policy["combination"]["maximum_mean_shift_volatility_units"],
                                     variant="experimental_meta_v3")
            scenario["event_definitions"]["price_up"] = "terminal completed-session close is above the declared reference price"
            ablations = {}
            for role in INDEPENDENT_ROLES:
                reduced = _context_signals(report, symbol, horizon, policy, excluded_role=role)
                rcw = policy["combination"]["context_weight"] if reduced["status"] == "AVAILABLE" and reduced["score"] is not None else 0
                reduced_score = (qw * quant["score"] + rcw * (reduced["score"] or 0)) / (qw + rcw)
                ablations[f"without_{role}"] = _distribution(
                    price, annual_vol, horizon, reduced_score,
                    policy["combination"]["maximum_mean_shift_volatility_units"],
                    variant=f"experimental_meta_v3_without_{role}")
            rows.append({"trading_days": horizon, "status": "EXPERIMENTAL_UNCALIBRATED",
                         "reference": reference,
                         "model_usage": "QUANT_PLUS_AGENT_HEURISTIC" if cw else "QUANT_ONLY_FALLBACK",
                         "quant_signal": quant, "context_signal": context, "combined_signal": combined,
                         "coverage": {"quant_features": quant["feature_coverage"],
                                      "context_roles": {"covered": context["covered_role_count"],
                                                        "total": context["total_role_count"]},
                                      "limitations": context["unresolved_material_claims"] + context["conflicting_roles"]},
                         "distribution": scenario, "ablations": ablations,
                         "recommendation": _recommendation(scenario, context, policy, report, symbol, packet)})
        symbols[symbol] = {"status": "EXPERIMENTAL_UNCALIBRATED" if any(
            row["status"] == "EXPERIMENTAL_UNCALIBRATED" for row in rows) else "NO_FORECAST", "horizons": rows}
    governance = {"policy_schema_version": policy["schema_version"], "policy_hash": digest(policy),
                  "engine_implementation_sha256": file_sha256(Path(__file__)),
                  "contract_implementation_sha256": file_sha256(Path(__file__).with_name("meta_contracts.py")),
                  "event_implementation_sha256": file_sha256(Path(__file__).with_name("meta_events.py")),
                  "runtime_config_hash": report.get("runtime_config_hash"),
                  "agent_harness_sha256": report.get("harness_implementation_sha256"),
                  "packet_implementation_sha256": packet.get("implementation_sha256"),
                  "product_contract": packet.get("product_contract"), "target_origin_kind": origin_kind,
                  "target_contract": "meta-target-v1",
                  "prospective_qualification": policy["prospective_qualification"]}
    governance["cohort_id"] = digest(governance)
    artifact = {"schema_version": "meta-structured-forecast-v3", "created_at": packet.get("as_of"),
            "packet_hash": packet["packet_hash"], "probability_status": "EXPERIMENTAL_UNCALIBRATED",
            "calibration_status": "NOT_QUALIFIED_INSUFFICIENT_PROSPECTIVE_EVIDENCE",
            "probability_semantics": "Terminal completed-session outcomes relative to each row's declared reference price; not executable-entry profitability and not path probabilities.",
            "symbols": symbols, "governance": governance,
            "notice": "Numerical shifts and actions are deterministic policy outputs, not agent confidence and not prospectively calibrated."}
    Draft202012Validator(json.loads(STRUCTURED_SCHEMA.read_text())).validate(artifact)
    return artifact


def create_structured_forecast(packet_path: Path, meta_report_path: Path,
                               output_path: Path, policy_path: Path = DEFAULT_POLICY, *,
                               origin_kind: str = "PRIOR_COMPLETED_CLOSE") -> Path:
    packet = _verified(packet_path, "packet_hash")
    report = json.loads(meta_report_path.read_text())
    artifact = build_structured_forecast(packet, report, load_policy(policy_path), origin_kind=origin_kind)
    artifact["agent_report_sha256"] = file_sha256(meta_report_path)
    artifact["policy_identity"] = policy_path.name
    artifact["artifact_hash"] = digest(artifact)
    Draft202012Validator(json.loads(STRUCTURED_SCHEMA.read_text())).validate(artifact)
    write_json_exclusive(output_path, artifact)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--meta-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--origin-kind", choices=["PRIOR_COMPLETED_CLOSE", "QUALIFIED_CURRENT_TRADE"],
                        default="PRIOR_COMPLETED_CLOSE")
    args = parser.parse_args()
    path = create_structured_forecast(args.packet, args.meta_report, args.output, args.policy, origin_kind=args.origin_kind)
    print(json.dumps({"output": str(path.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
