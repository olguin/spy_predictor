"""Regression boundaries found by the full V1 plan audit."""
from copy import deepcopy
import json

import pytest

from spy_predictor_quant.investment_research.broker import Broker
from spy_predictor_quant.investment_research.controller import Controller
from spy_predictor_quant.investment_research.sources import child_source, evidence_number
from test_investment_research import FixtureWorker, findings, mandate, response


def test_initial_specialists_do_not_see_director_or_peer_findings(tmp_path):
    worker = FixtureWorker()
    controller = Controller(tmp_path, worker)
    controller.create(mandate())
    state = controller.run()
    assert state["status"] == "DRAFT", state.get("stop_reason")
    for request in worker.calls:
        task = next(t for t in state["tasks"] if t["task_id"] == request["task_id"])
        if task["stage"] == "research" and task["round"] == 0:
            assert request["context"]["prior_findings"] == []
            assert request["context"]["questions"] == []
        if task["stage"] != "triage":
            assert "route_question" not in request["tool_schemas"]
    question = next(q for q in state["questions"] if q["requester"] == "company")
    assert question["director_disposition"]["decision"] == "approve"


def test_challenge_question_is_answered_before_final_under_shared_round_limit(tmp_path):
    class ChallengeWorker(FixtureWorker):
        def __call__(self, request, runtime, timeout):
            task = request["context"]["task"]
            history = request["context"]["history"]
            if task["stage"] == "review" and not history:
                return response("ask_specialist", {"recipient": "macro", "question": "Can the counter-case be resolved with a debt schedule?",
                    "decision_impact": "Could invalidate the counter-case", "evidence_ids": []})
            return super().__call__(request, runtime, timeout)
    controller = Controller(tmp_path, ChallengeWorker())
    controller.create(mandate())
    state = controller.run()
    assert state["status"] == "DRAFT", state.get("stop_reason")
    question = next(q for q in state["questions"] if q["requester"] == "challenger")
    assert question["status"] == "ANSWERED"
    assert state["followup_round"] == 2
    final_request = [controller.store.get("requests", a["request_id"]) for a in state["attempts"]][-1]
    assert question["answer_task_id"] in {t["task_id"] for t in final_request["context"]["prior_findings"]}


def test_zero_followup_budget_declines_proposals_without_extra_research(tmp_path):
    config = mandate()
    config["budgets"]["followup_rounds"] = 0
    controller = Controller(tmp_path, FixtureWorker())
    controller.create(config)
    state = controller.run()
    assert state["status"] == "DRAFT"
    assert all(q["status"] == "DECLINED" for q in state["questions"] if q["requester"] == "company")
    assert not any(t["stage"] == "triage" for t in state["tasks"])


def test_feed_discovery_retains_publication_but_not_invented_availability(tmp_path):
    config = mandate()
    config["sources"] = [{**config["sources"][0], "source_id": "issuer-feed", "url": "https://issuer.example/feed.xml",
        "fixture_text": '<rss><channel><item><title>Quarterly results</title><link>https://issuer.example/results</link><pubDate>Mon, 01 Sep 2025 12:00:00 GMT</pubDate><description>Read full filing</description></item><item><title>Injected target</title><link>https://evil.example/tool</link><pubDate>Mon, 01 Sep 2025 12:00:00 GMT</pubDate></item></channel></rss>'}]
    controller = Controller(tmp_path)
    state = controller.create(config)
    result = Broker(controller.store, state).call("discover_sources", {"query": "results"})
    child = next(s for s in result["sources"] if s["source_id"].startswith("discovered"))
    assert child["url"] == "https://issuer.example/results" and child["read"] is False
    assert len(state["discovered_sources"]) == 1
    registered = state["discovered_sources"][child["source_id"]]
    assert registered["available_at"] is None and registered["published_at"] == "2025-09-01T12:00:00+00:00"
    assert registered["parent_evidence_id"] in state["evidence_ids"]


def test_discovered_url_cannot_cross_domain_or_add_credentials():
    parent = {"source_id": "issuer-feed", "url": "https://issuer.example/feed.xml", "publisher": "Issuer", "kind": "company"}
    for url in ("https://evil.example/doc", "https://secret@issuer.example/doc", "http://issuer.example/doc", "https://issuer.example:8080/doc"):
        with pytest.raises(ValueError):
            child_source(parent, {"url": url, "title": "Doc", "published_at": None}, "a" * 64)


def test_calculation_resolves_values_in_evidence_without_model_copying(tmp_path):
    controller = Controller(tmp_path)
    state = controller.create(mandate())
    broker = Broker(controller.store, state)
    evidence = broker.record({"kind": "source", "data": {"a": 110.01, "b": 100}})
    identity = evidence["evidence_id"]
    value = broker.call("calculate", {"operation": "percentage_change", "left": identity + "#/data/a",
        "right": identity + "#/data/b", "units": "percent", "assumptions": "Matched scenario periods", "evidence_ids": [identity]})
    assert value["result_decimal"] == "10.0100"
    assert len(value["input_references"]) == 2
    assert value["qualification"].startswith("Deterministically")
    with pytest.raises(ValueError):
        evidence_number({"not_numeric": "110"}, "/not_numeric")


def test_failure_is_cached_and_retains_attempt_count(tmp_path):
    config = mandate()
    config["sources"][0]["fixture_text"] = None
    controller = Controller(tmp_path)
    state = controller.create(config)
    broker = Broker(controller.store, state)
    for _ in range(2):
        assert broker.call("read_source", {"source_id": "company-fixture"})["status"] == "GAP"
    assert state["usage"]["source_requests"] == 1


def test_visible_task_manifest_matches_request_evidence(tmp_path):
    worker = FixtureWorker()
    controller = Controller(tmp_path, worker)
    controller.create(mandate())
    assert controller.run()["status"] == "DRAFT"
    for request in worker.calls:
        manifest = controller.store.get("manifests", request["context"]["manifest_id"])
        assert set(manifest["evidence_ids"]) == set(request["context"]["evidence"])


def test_source_code_is_archived_for_dirty_worktree_reproduction(tmp_path):
    controller = Controller(tmp_path)
    state = controller.create(mandate())
    assert (tmp_path / "code/python/src/spy_predictor_quant/investment_research/controller.py").exists()
    assert state["runtime_policy_version"] == "investment-research-m1-v4"
    assert all(t["prompt_version"].endswith("v1.2") for t in state["tasks"])


def test_final_response_identity_map_cannot_replace_objection_ids(tmp_path):
    from spy_predictor_quant.investment_research.contracts import ROOT, PROMPT_VERSION
    from spy_predictor_quant.investment_research.result_transport import tool_schemas, restore_action
    from jsonschema import ValidationError
    controller = Controller(tmp_path)
    state = controller.create(mandate())
    state["tasks"][0]["result"] = findings()
    state["tasks"][0]["result"]["objections"] = [{"objection_id": "original", "claim_ids": [], "severity": "critical", "description": "Gap"}]
    task = controller.add_task(state, "director", "final", "Final")
    tools = tool_schemas(json.loads((ROOT / f"prompts/investment-research/{PROMPT_VERSION}/tools.json").read_text()), task, state, 1)
    assert set(tools) == {"submit_findings"}
    value = findings()
    value["dispositions"] = {"replacement": {"decision": "unresolved", "reason": "Unknown"}}
    value["question_effects"] = {}
    with pytest.raises(ValidationError):
        restore_action({"tool": "submit_findings", "arguments": value}, tools, "final")
    value["dispositions"] = {"original": {"decision": "unresolved", "reason": "Unknown"}}
    restored = restore_action({"tool": "submit_findings", "arguments": value}, tools, "final")
    assert restored["arguments"]["dispositions"] == [{"objection_id": "original", "decision": "unresolved", "reason": "Unknown"}]


def test_director_can_reuse_existing_specialist_answer_without_another_task(tmp_path):
    controller = Controller(tmp_path)
    state = controller.create(mandate())
    company = controller.add_task(state, "company", "research", "Issuer exposure")
    macro = controller.add_task(state, "macro", "research", "Rates channel")
    macro.update(status="COMPLETE", result=findings())
    question = controller.route(state, company, {"recipient": "macro", "question": "What is the rates channel?", "decision_impact": "Changes thesis", "evidence_ids": []})
    triage = controller.add_task(state, "director", "triage", "Prioritize")
    count = len(state["tasks"])
    answer = controller.prioritize(state, triage, {"question_id": question["question_id"], "decision": "approve",
        "reason": "Existing macro finding directly answers this channel", "answer_task_id": macro["task_id"]})
    assert answer["status"] == "ANSWERED" and answer["answer_reused"]
    assert len(state["tasks"]) == count


def test_rejected_submission_gets_explicit_receipted_feedback_within_task_limit(tmp_path):
    class CorrectingWorker(FixtureWorker):
        def __call__(self, request, runtime, timeout):
            history = request["context"]["history"]
            if request["task_id"] == "task-1" and not history:
                result = findings()
                result["assessment"] = "watch"
                return response("submit_findings", result)
            if request["task_id"] == "task-1":
                assert history[0]["result"]["status"] == "REJECTED_VALIDATION"
                return response("submit_findings", findings())
            return super().__call__(request, runtime, timeout)
    controller = Controller(tmp_path, CorrectingWorker())
    controller.create(mandate())
    state = controller.run()
    assert state["status"] == "DRAFT", state.get("stop_reason")
    assert state["attempts"][0]["status"] == "REJECTED_VALIDATION"
    assert state["attempts"][0]["response_id"]
    assert len([a for a in state["attempts"] if a["task_id"] == "task-1"]) == 2


def test_invalid_submissions_cannot_expand_task_turn_budget(tmp_path):
    def invalid(*args):
        result = findings()
        result["assessment"] = "watch"
        return response("submit_findings", result)
    controller = Controller(tmp_path, invalid)
    controller.create(mandate())
    state = controller.run()
    assert state["status"] == "INCOMPLETE"
    assert state["usage"]["model_calls"] == state["stage_turn_limits"]["independent"]
    assert all(a["status"] == "REJECTED_VALIDATION" for a in state["attempts"])
