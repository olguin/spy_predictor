"""Infrastructure fixtures, not evidence of live multi-agent research quality."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from spy_predictor_quant.investment_research.broker import Broker, LimitReached
from spy_predictor_quant.investment_research.contracts import ROOT, load_mandate, validate_findings
from spy_predictor_quant.investment_research.controller import Controller, subprocess_worker


def mandate():
    return load_mandate(ROOT / "examples/investment-research/mandate-fixture.json")


def findings(task_id="task-1", evidence_ids=()):
    return {"summary": "Issuer exposure is unresolved.", "assessment": "insufficient_evidence",
            "claims": [{"claim_id": task_id + "-claim", "classification": "fact", "text": "Synthetic evidence only.",
                        "evidence_ids": list(evidence_ids)}] if evidence_ids else [],
            "gaps": [{"description": "Current valuation and exposure unavailable", "critical": True}],
            "assumptions": [], "counter_thesis": "Refinancing sensitivity may be immaterial.",
            "review_conditions": [{"kind": "human_review", "description": "Obtain issuer debt schedule"}],
            "objections": [], "dispositions": [], "question_effects": []}


def response(tool, args):
    return {"schema_version": "pi-research-worker-v2", "action": {"tool": tool, "arguments": args},
            "receipt": {"input_tokens": 100, "output_tokens": 50, "catalog_cost_usd": 0.01}}


class FixtureWorker:
    """Action policy exercises routing from tool responses; never used in the CLI."""
    def __init__(self):
        self.calls = []

    def __call__(self, request, runtime, timeout):
        self.calls.append(deepcopy(request))
        context = request["context"]
        task, history = context["task"], context["history"]
        role, stage = task["role"], task["stage"]
        tools = [h["action"]["tool"] for h in history]
        if stage == "triage":
            question = next((q for q in context["questions"] if q["status"] == "PROPOSED"), None)
            if question:
                return response("route_question", {"question_id": question["question_id"], "decision": "approve", "reason": "Material exposure question", "answer_task_id": None})
        if stage == "planning":
            asked = [h["action"]["arguments"]["recipient"] for h in history if h["action"]["tool"] == "ask_specialist"]
            for recipient in ("company", "macro"):
                if recipient not in asked:
                    return response("ask_specialist", {"recipient": recipient, "question": f"Assess {recipient} evidence and material gaps.",
                        "decision_impact": "Could invalidate valuation assumptions", "evidence_ids": []})
        if stage in {"research", "independent"}:
            if "discover_sources" not in tools:
                return response("discover_sources", {"query": role})
            if "read_source" not in tools:
                source = "macro-fixture" if role == "macro" else "company-fixture"
                return response("read_source", {"source_id": source})
            if role == "company" and "ask_specialist" not in tools:
                evidence = next(h["result"] for h in history if h["action"]["tool"] == "read_source")
                if "Debt reprices" in evidence.get("excerpt", ""):
                    return response("ask_specialist", {"recipient": "macro", "question": "Could refinancing rates change this issuer thesis?",
                        "decision_impact": "A measured debt exposure would change the counter-case", "evidence_ids": [evidence["evidence_id"]]})
        result = findings(task["task_id"], list(context["evidence"])[:1])
        if stage == "review":
            result["objections"] = [{"objection_id": task["task_id"] + "-objection", "claim_ids": [], "severity": "critical",
                                     "description": "Issuer debt mix remains unknown"}]
        if stage == "final":
            result["question_effects"] = [{"question_id": q["question_id"], "effect": "unchanged",
                                          "reason": "Answer confirms missing exposure; retain insufficient evidence"} for q in context["questions"]]
            result["dispositions"] = [{"objection_id": o["objection_id"], "decision": "unresolved", "reason": "Coverage gap retained"}
                                      for p in context["prior_findings"] for o in p["result"]["objections"]]
            result["dispositions"] = {d["objection_id"]: {k: v for k, v in d.items() if k != "objection_id"} for d in result["dispositions"]}
            result["question_effects"] = {e["question_id"]: {k: v for k, v in e.items() if k != "question_id"} for e in result["question_effects"]}
        return response("submit_findings", result)


def test_cooperative_draft_is_unpublished_and_resume_is_idempotent(tmp_path):
    worker = FixtureWorker()
    controller = Controller(tmp_path, worker)
    controller.create(mandate())
    state = controller.run()
    assert state["status"] == "DRAFT", state.get("stop_reason")
    questions = state["questions"]
    assert len(questions) == 3 and all(q["status"] == "ANSWERED" for q in questions)
    assert any(q["requester"] == "company" and q["recipient"] == "macro" for q in questions)
    product = controller.store.get("products", state["product_id"])
    assert product["published_at"] is None and product["observation_contract"] is None
    assert product["findings"]["assessment"] == "insufficient_evidence"
    assert len(product["findings"]["question_effects"]) == 3
    assert state["usage"]["source_requests"] == 2  # cross-role acquisition reuse
    assert all(not r["context"]["prior_findings"] for r in worker.calls if r["context"]["task"]["stage"] == "independent")
    before = len(worker.calls)
    assert controller.run()["status"] == "DRAFT" and len(worker.calls) == before
    assert "NOT PUBLISHED" in (tmp_path / "draft.md").read_text()


@pytest.mark.parametrize("attempt_status", ["STARTED", "RECEIVED"])
def test_interrupted_attempt_is_not_repeated(tmp_path, attempt_status):
    worker = FixtureWorker()
    controller = Controller(tmp_path, worker)
    state = controller.create(mandate())
    state["attempts"].append({"attempt_id": "attempt-1", "status": attempt_status})
    controller.store.save(state)
    assert controller.run()["status"] == "INTERRUPTED"
    assert not worker.calls


def test_resume_completed_turn_preserves_acquisition(tmp_path):
    controller = Controller(tmp_path, FixtureWorker())
    state = controller.create(mandate())
    broker = Broker(controller.store, state)
    first = broker.call("read_source", {"source_id": "company-fixture"})
    state = controller.store.load()
    second = Broker(controller.store, state).call("read_source", {"source_id": "company-fixture"})
    assert first["evidence_id"] == second["evidence_id"]
    assert state["usage"]["source_requests"] == 1
    assert controller.run()["status"] == "DRAFT"


@pytest.mark.parametrize("receipt", [None, {"input_tokens": 1, "output_tokens": 2, "catalog_cost_usd": None},
                                     {"input_tokens": float("nan"), "output_tokens": 2, "catalog_cost_usd": 0.01}])
def test_unknown_usage_stops_further_admission(tmp_path, receipt):
    controller = Controller(tmp_path)
    state = controller.create(mandate())
    with pytest.raises(LimitReached):
        controller.account(state, receipt)
    assert state["usage_unknown"]


def test_budget_exhaustion_retains_response_and_does_not_publish(tmp_path):
    def excessive(*args):
        value = response("submit_findings", findings())
        value["receipt"]["output_tokens"] = 200000
        return value
    controller = Controller(tmp_path, excessive)
    controller.create(mandate())
    state = controller.run()
    assert state["status"] == "INCOMPLETE"
    assert state["usage"]["output_tokens"] == 200000
    assert len(state["attempts"]) == 1 and state["attempts"][0]["response_id"]
    assert "product_id" not in state


def test_untrusted_document_cannot_grant_tools(tmp_path):
    controller = Controller(tmp_path)
    state = controller.create(mandate())
    broker = Broker(controller.store, state)
    document = broker.call("read_source", {"source_id": "company-fixture"})
    assert document["trust"] == "UNTRUSTED_SOURCE_DATA" and "shell command" in document["excerpt"]
    with pytest.raises(ValueError):
        broker.call("shell", {"command": "anything"})
    assert broker.call("read_source", {"source_id": "file:///etc/passwd"})["reason"] == "UNREGISTERED_SOURCE"


def test_missing_source_is_typed_gap_and_not_empty_success(tmp_path):
    config = mandate()
    config["sources"][0]["fixture_text"] = None
    controller = Controller(tmp_path)
    state = controller.create(config)
    result = Broker(controller.store, state).call("read_source", {"source_id": "company-fixture"})
    assert result["status"] == "GAP" and state["evidence_ids"] == []


def test_decimal_calculation_preserves_assumptions_and_lineage(tmp_path):
    controller = Controller(tmp_path)
    state = controller.create(mandate())
    broker = Broker(controller.store, state)
    value = broker.call("calculate", {"operation": "percentage_change", "left": "110.01", "right": "100",
        "units": "percent", "assumptions": "Synthetic scenario", "evidence_ids": []})
    assert value["result_decimal"] == "10.0100"
    assert "not a verified numeric extraction" in value["qualification"]
    with pytest.raises(ValueError):
        broker.call("calculate", {"operation": "valuation_multiple", "left": "1", "right": "0",
            "units": "multiple", "assumptions": "scenario", "evidence_ids": []})


def test_question_dedup_and_cycle_detection(tmp_path):
    controller = Controller(tmp_path)
    state = controller.create(mandate())
    director = state["tasks"][1]
    args = {"recipient": "company", "question": "Check debt", "decision_impact": "Changes rates exposure", "evidence_ids": []}
    first = controller.route(state, director, args)
    assert first["status"] == "ACCEPTED"
    assert controller.route(state, director, args)["disposition"] == "DUPLICATE"
    company = state["tasks"][-1]
    macro_question = controller.route(state, company, {**args, "recipient": "macro", "question": "Check rates"})
    assert macro_question["status"] == "PROPOSED"
    triage = controller.add_task(state, "director", "triage", "Prioritize")
    state["followup_round"] = 1
    controller.prioritize(state, triage, {"question_id": macro_question["question_id"], "decision": "approve", "reason": "Material"})
    macro = state["tasks"][-1]
    assert controller.route(state, macro, {**args, "question": "Check another debt detail"})["status"] == "PROPOSED"
    assert controller.route(state, macro, {**args, "question": "Check debt"})["disposition"] == "DUPLICATE"


def test_evidence_tampering_prevents_resume(tmp_path):
    controller = Controller(tmp_path)
    state = controller.create(mandate())
    value = Broker(controller.store, state).call("read_source", {"source_id": "company-fixture"})
    (tmp_path / "evidence" / f"{value['evidence_id']}.json").write_text('{}')
    with pytest.raises(ValueError, match="integrity"):
        controller.run()


def test_claim_and_condition_validation():
    value = findings("task-1", ["missing"])
    with pytest.raises(ValueError, match="Unknown"):
        validate_findings(value, set(), set(), set())
    value = findings()
    value["assessment"] = "attractive_candidate"
    with pytest.raises(ValueError, match="critical"):
        validate_findings(value, set(), set(), set())
    value = findings()
    value["review_conditions"][0]["kind"] = "latest_close"
    with pytest.raises(ValidationError):
        validate_findings(value, set(), set(), set())


def test_worker_pipe_deadline_is_enforced():
    import sys
    with pytest.raises(TimeoutError):
        subprocess_worker({}, {"argv": [sys.executable, "-c", "import time; time.sleep(10)"]}, 0.05)
