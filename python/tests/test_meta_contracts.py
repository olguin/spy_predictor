from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from spy_predictor_quant.meta_contracts import audit_trigger, price_state, reference_contract
from spy_predictor_quant.meta_forecast import build_structured_forecast, load_policy
from test_meta_forecast import packet, report


@pytest.mark.parametrize("flattened", [False, True])
@pytest.mark.parametrize("claim_ref", [None, "technical:technical-claim"])
def test_deterministic_quarantine_precedes_accept_and_ablation(flattened, claim_ref):
    value = report()
    finding = {"claim_ref": claim_ref, "symbol": "SPY", "trading_days": 5,
               "reason": "INCOMPATIBLE_OPPOSITION", "role": "technical"}
    value["deterministic_claim_rejections"] = ([finding] if flattened else {"technical": [finding]})
    rows = build_structured_forecast(packet(), value, load_policy())["symbols"]["SPY"]["horizons"]
    assert "technical" not in {r["role"] for r in rows[0]["context_signal"]["role_signals"]}
    assert rows[0]["distribution"]["probability_price_up"] == rows[0]["ablations"]["without_technical"]["probability_price_up"]
    if claim_ref is None:
        assert "technical" in {r["role"] for r in rows[1]["context_signal"]["role_signals"]}


def test_ambiguous_cross_symbol_claims_and_duplicate_critic_decisions_fail_closed():
    value = report()
    copy = deepcopy(value["results"]["technical"]["assessments"][0])
    copy["symbol"] = "QQQ"
    value["results"]["technical"]["assessments"].append(copy)
    with pytest.raises(ValueError, match="Ambiguous"):
        build_structured_forecast(packet(), value, load_policy())
    value = report()
    value["results"]["critic"]["claim_decisions"].append(value["results"]["critic"]["claim_decisions"][0])
    with pytest.raises(ValueError, match="unique"):
        build_structured_forecast(packet(), value, load_policy())


def test_v4_horizon_edges_do_not_inherit_a_global_fact_stance():
    value = report()
    value["validation"] = "META_AGENT_V4_OBSERVATIONS_AND_HYPOTHESIS_EDGES"
    claim = value["results"]["technical"]["assessments"][0]["claims"][0]
    claim["classification"], claim["stance"] = "FACT", "CONTEXT"
    row = value["results"]["technical"]["assessments"][0]["horizon_assessments"][1]
    row["direction"] = "BEARISH"
    rows = build_structured_forecast(packet(), value, load_policy())["symbols"]["SPY"]["horizons"]
    signals = [next(s for s in row["context_signal"]["role_signals"] if s["role"] == "technical") for row in rows]
    assert signals[0]["signal"] == 1 and signals[1]["signal"] == -1


@pytest.mark.parametrize("field,value,reason", [
    ("level", float("nan"), "INVALID_LEVEL"), ("level", True, "INVALID_LEVEL"),
    ("units", "percent", "UNSUPPORTED_UNITS"),
    ("expiry", "next review", "UNRESOLVED_EXPIRY"),
    ("expiry", "2026-09-14T20:00:00Z", "EXPIRED"),
    ("comparison", "UNAVAILABLE", "INVALID_COMPARISON"),
    ("confirmation_interval", "five minutes", "UNSUPPORTED_CONFIRMATION_INTERVAL"),
    ("evidence_ids", ["not-reviewed"], "UNACCEPTED_PROVENANCE"),
])
def test_trigger_audit_rejects_unqualified_conditions(field, value, reason):
    trigger = deepcopy(report(trigger=True)["results"]["technical"]["assessments"][0]["horizon_assessments"][0]["confirmation"])
    trigger[field] = value
    audit = audit_trigger(trigger, packet(), "SPY", {"technical-evidence"})
    assert audit["status"] == "REJECTED" and reason in audit["reason_codes"]


def test_invalidation_and_exact_review_survive_but_met_trigger_is_not_future_setup():
    value = report(view="NEUTRAL", trigger=True)
    specialist = value["results"]["technical"]["assessments"][0]["horizon_assessments"][0]
    invalidation = {**specialist["confirmation"], "comparison": "BELOW", "level": 95}
    specialist["invalidation_trigger"] = invalidation
    specialist["confirmation"]["level"] = 95
    row = build_structured_forecast(packet(), value, load_policy())["symbols"]["SPY"]["horizons"][0]
    decision = row["recommendation"]
    assert decision["conditional_trigger"] is None and decision["action_now"] == "WAIT"
    assert decision["invalidation_trigger"]["level"] == 95
    assert "technical: next close — new evidence" in decision["next_review"]
    assert any(audit["status"] == "ALREADY_SATISFIED" for audit in decision["condition_audits"])


def test_current_trade_target_is_distinct_and_midpoint_is_never_substituted():
    value = packet()
    value["as_of"] = "2026-09-15T15:00:00Z"
    value["evidence"]["trade"] = {"kind": "alpaca_intraday_snapshot", "symbols": ["SPY"]}
    value["intraday"] = {"SPY": {"status": "AVAILABLE", "evidence_state": "REAL_TIME",
        "exchange_coverage": "IEX_ONLY", "latest_trade": {"price": 103, "timestamp": "2026-09-15T14:59:00Z",
                                                           "available_at": "2026-09-15T14:59:01Z"},
        "latest_quote": {"bid": 102, "ask": 104, "timestamp": "2026-09-15T14:59:00Z"}}}
    close = reference_contract(value, "SPY", 5)
    current = reference_contract(value, "SPY", 5, "QUALIFIED_CURRENT_TRADE")
    assert close["reference_price"] == 100 and current["reference_price"] == 103
    assert close["target_timestamp"] != current["target_timestamp"]
    del value["intraday"]["SPY"]["latest_trade"]
    with pytest.raises(ValueError, match="qualified current trade"):
        reference_contract(value, "SPY", 5, "QUALIFIED_CURRENT_TRADE")


@pytest.mark.parametrize("observed,status", [
    ("2026-09-15T13:59:00Z", "STALE_AT_PUBLICATION"),
    ("2026-09-15T15:01:00Z", "INELIGIBLE_TIMESTAMP"),
    (None, "UNKNOWN_TIMESTAMP"), ("2026-09-15T14:59:00", "UNKNOWN_TIMESTAMP"),
])
def test_value_bound_freshness_cannot_report_live(observed, status):
    state = price_state(100, observed, "2026-09-15T15:00:00Z", "2026-09-15T15:00:00Z", "REAL_TIME")
    assert state["status"] == status and not state["publication_eligible"]


def test_fallback_is_explicit_and_bad_reference_cannot_forecast():
    rows = build_structured_forecast(packet(), report(supported_roles=1), load_policy())["symbols"]["SPY"]["horizons"]
    assert all(row["model_usage"] == "QUANT_ONLY_FALLBACK" for row in rows)
    value = packet()
    value["as_of"] = "2026-09-14T18:00:00Z"
    with pytest.raises(ValueError, match="after information cutoff"):
        build_structured_forecast(value, report(), load_policy())


def test_no_qualified_features_is_schema_valid_missingness():
    value = packet()
    value["instruments"]["SPY"] = {"status": "FRESH", "latest_close": 100,
                                    "price_date": "2026-09-14", "realized_vol63_pct": 20}
    value.pop("transparent_risk_appetite")
    result = build_structured_forecast(value, report(), load_policy())
    assert result["symbols"]["SPY"]["status"] == "NO_FORECAST"
    assert all(row["status"] == "NO_FORECAST" for row in result["symbols"]["SPY"]["horizons"])


def test_material_unverified_hypothesis_still_blocks_after_edge_exclusion():
    value = report()
    value["results"]["critic"]["claim_decisions"][0]["decision"] = "NEEDS_VERIFICATION"
    row = build_structured_forecast(packet(), value, load_policy())["symbols"]["SPY"]["horizons"][0]
    assert row["context_signal"]["accepted_roles"] == 4
    assert "UNRESOLVED_MATERIAL_CLAIMS" in row["recommendation"]["reason_codes"]
    assert row["recommendation"]["action_now"] == "WAIT"
