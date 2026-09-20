from copy import deepcopy
import json
from pathlib import Path
import pytest

from spy_predictor_quant.meta_analysis import digest
from spy_predictor_quant.meta_synthesis_recovery import compact_request, diagnostic_request
from spy_predictor_quant.meta_agents import validate_output, _decision_rows_from_forecast
from spy_predictor_quant import meta_synthesis_recovery as recovery
from spy_predictor_quant.market_archive import file_sha256


def test_synthesis_projection_preserves_decisions_and_sparse_numeric_paths():
    horizon = {"trading_days": 5, "status": "EXPERIMENTAL_UNCALIBRATED",
        "distribution": {"probability_price_up": .58}, "reference": {"reference_price": 100},
        "recommendation": {"action_now": "WAIT", "new_position_action": "WAIT",
                           "existing_position_action": "POSITION_CONTEXT_REQUIRED", "invalidation": "test"},
        "ablations": {"without_news": {"probability_price_up": .9}}, "quant_signal": {"score": .2}}
    claim = {"evidence_ids": ["source"], "numeric_values": [{"packet_path": "/observations/2/value", "value": 100}]}
    original = {"role": "synthesis", "input_hash": "parent", "instructions": "fixture",
        "agent_contract_version": "meta-agent-output-v4", "implementation_sha256": "a" * 64,
        "runtime": {"model": "example"}, "packet": {"version": "meta-analysis-v1", "symbols": ["SPY"],
            "as_of": "2026-09-16T00:00:00Z", "source_packet_hash": "p", "instruments": {"SPY": {}},
            "observations": [{"value": 20}, {"value": 30}, {"value": 100}],
            "evidence": {"source": {"kind": "news"}, "unused": {"kind": "news"}}},
        "prior_results": {"accepted_claim_refs": ["technical:fact"], "deterministic_claim_rejections": [],
            "numerical_forecast": {"schema_version": "meta-structured-forecast-v3", "symbols": {"SPY": {"horizons": [horizon]}}},
            "results": {"technical": {"assessments": [{"claims": [claim], "horizon_assessments": []}]},
                        "critic": {"assessments": [], "claim_decisions": [{"claim_ref": "technical:fact", "decision": "ACCEPT"}]}}}}
    before = deepcopy(original)
    request = compact_request(original)
    projected = request["prior_results"]["numerical_forecast"]["symbols"]["SPY"]["horizons"][0]
    assert original == before
    for key in ("distribution", "reference", "recommendation"):
        assert projected[key] == horizon[key]
    assert "ablations" not in projected
    assert request["packet"]["observations"] == [None, None, {"value": 100}]
    assert set(request["packet"]["evidence"]) == {"source"}
    assert request["prior_results"]["results"]["critic"]["claim_decisions"] == original["prior_results"]["results"]["critic"]["claim_decisions"]
    assert request["parent_input_hash"] == "parent"
    assert request["input_hash"] == digest({k: v for k, v in request.items() if k not in {"runtime", "input_hash", "output_schema"}})


def test_small_diagnostic_preserves_frozen_rows_and_actual_v4_validation():
    horizons = [{"trading_days": days, "status": "EXPERIMENTAL_UNCALIBRATED",
        "distribution": {"probability_price_up": .58}, "reference": {"reference_price": 100},
        "recommendation": {"action_now": "WAIT", "new_position_action": "WAIT",
            "existing_position_action": "POSITION_CONTEXT_REQUIRED"}} for days in (5, 21, 63)]
    original = {"role": "synthesis", "input_hash": "parent", "agent_contract_version": "meta-agent-output-v4",
        "implementation_sha256": "a" * 64, "runtime": {"model": "openai-codex/gpt-6-astra"},
        "packet": {"version": "meta-analysis-v1", "as_of": "2026-09-16T00:00:00Z"},
        "prior_results": {"numerical_forecast": {"schema_version": "meta-structured-forecast-v3",
            "symbols": {s: {"horizons": deepcopy(horizons)} for s in ("SPY", "QQQ")}}}}
    before = deepcopy(original)
    request = diagnostic_request(original)
    assert original == before
    assert request["runtime"]["model"] == "openai-codex/gpt-6-astra"
    assert request["packet"]["symbols"] == ["QQQ"]
    assert diagnostic_request(original, "SPY")["packet"]["symbols"] == ["SPY"]
    with pytest.raises(ValueError, match="frozen parent"):
        diagnostic_request(original, "INVALID")
    assert request["prior_results"]["numerical_forecast"]["symbols"]["QQQ"]["horizons"] == horizons
    assert request["input_hash"] == digest({k: v for k, v in request.items() if k not in {"runtime", "input_hash", "output_schema"}})
    trigger = {"availability": "UNAVAILABLE", "field": "close", "comparison": "UNAVAILABLE", "level": None,
        "units": "USD", "confirmation_interval": "unavailable", "expiry": "unavailable", "evidence_ids": []}
    result = {"role": "synthesis", "input_hash": request["input_hash"], "assessments": [{
        "symbol": "QQQ", "status": "INSUFFICIENT_EVIDENCE", "view": "UNKNOWN", "thesis": "Diagnostic",
        "counterevidence": [], "invalidation": [], "missing": ["Specialists"], "claims": [],
        "horizon_assessments": [{"trading_days": days, "status": "INSUFFICIENT_EVIDENCE", "direction": "UNKNOWN",
            "strongest_support_claim_ids": [], "strongest_opposition_claim_ids": [], "action_implication": "WAIT",
            "confirmation": trigger, "invalidation_trigger": trigger,
            "missing_evidence": [{"item": "Specialists", "criticality": "CRITICAL"}],
            "review": {"when": "next capture", "event": "full analysis"}} for days in (5, 21, 63)]}],
        "golden_conclusions": {"overall_conclusion": "Diagnostic", "market_regime": "Unknown", "critical_findings": [],
            "decision_rows": [{**row, "explanation": "Frozen", "what_changes_action": "Fresh evidence",
                "what_could_go_wrong": "Uncalibrated"} for row in _decision_rows_from_forecast(request["prior_results"])],
            "research_priorities": [{"symbol": "QQQ", "priority": 1, "buy_attractiveness": "UNKNOWN", "rationale": "Diagnostic"}],
            "immediate_review_triggers": ["Fresh capture"], "evidence_limitations": ["No specialist evidence"],
            "new_material_contradiction": None}}
    assert validate_output(result, request) == []
    result["golden_conclusions"]["decision_rows"][0]["forecast_ref"] = "/symbols/QQQ/horizons/1"
    with pytest.raises(ValueError, match="frozen numerical"):
        validate_output(result, request)


def registered_execution(tmp_path):
    source = tmp_path / "parent"
    source.mkdir()
    (source / "meta-report.json").write_text('{}')
    run = tmp_path / "run"
    run.mkdir()
    (run / "request.json").write_text('{"input_hash":"test"}')
    dependency = tmp_path / "adapter.ts"
    dependency.write_text('original')
    registration = {"source_run": str(source), "source_report_sha256": file_sha256(source / "meta-report.json"),
        "implementation_sha256": file_sha256(Path(recovery.__file__)),
        "request_sha256": file_sha256(run / "request.json"),
        "runtime_dependencies": {str(dependency): file_sha256(dependency)},
        "runner": {"argv": ["never-execute"]}, "timeout_seconds": 1}
    (run / "registration.json").write_text(json.dumps({**registration, "registration_hash": digest(registration)}))
    return run, source, dependency


@pytest.mark.parametrize("changed", ["request", "runtime", "parent", "registration"])
def test_recovery_rejects_mutation_before_dispatch(tmp_path, monkeypatch, changed):
    run, source, dependency = registered_execution(tmp_path)
    targets = {"request": run / "request.json", "runtime": dependency,
        "parent": source / "meta-report.json", "registration": run / "registration.json"}
    target = targets[changed]
    target.write_text(target.read_text().replace('original', 'changed') if changed == "runtime" else '{"changed":true}')
    monkeypatch.setattr(recovery.subprocess, "Popen", lambda *a, **k: pytest.fail("Dispatched changed registration"))
    with pytest.raises((ValueError, KeyError)):
        recovery.execute(run)
    assert not (run / "started.json").exists()


def test_terminal_attempt_cannot_dispatch_again(tmp_path, monkeypatch):
    run, _, _ = registered_execution(tmp_path)
    (run / "started.json").write_text('{"preserved":true}')
    (run / "failed.json").write_text('{"preserved":true}')
    monkeypatch.setattr(recovery.subprocess, "Popen", lambda *a, **k: pytest.fail("Repeated terminal attempt"))
    with pytest.raises(FileExistsError):
        recovery.execute(run)
    assert (run / "failed.json").read_text() == '{"preserved":true}'
