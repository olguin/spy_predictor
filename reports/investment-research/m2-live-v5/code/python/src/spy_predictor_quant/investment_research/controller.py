"""Sequential, resumable controller for the first one-instrument research slice.

Workers select one action per subprocess invocation. Intentional subsequent model
turns receive the frozen task plus prior tool results; every invocation is paid
and receipted separately. No worker holds a slot while awaiting another role.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import selectors
import subprocess
import tempfile
import time
import uuid

from jsonschema import ValidationError

from spy_predictor_quant.market_archive import content_hash, utc_now
from .broker import Broker, LimitReached, consume, remaining_seconds
from .capabilities import inventory
from .contracts import ROOT, ROLES, M2_ROLES, TOOLS, PROMPT_VERSION, WORKER_PROTOCOL, validate, validate_findings, is_m2
from .store import Store
from .result_transport import tool_schemas, restore_action


def subprocess_worker(request: dict, runtime: dict, timeout: float) -> dict:
    """Bound both pipes, wall time and process lifetime; never log raw stderr."""
    request_file = tempfile.TemporaryFile()
    request_file.write(json.dumps(request).encode() + b"\n")
    request_file.seek(0)
    process = subprocess.Popen(runtime["argv"], cwd=ROOT, stdin=request_file,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, errors = bytearray(), bytearray()
    try:
        deadline = time.monotonic() + timeout
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, output)
            selector.register(process.stderr, selectors.EVENT_READ, errors)
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise TimeoutError("Worker deadline exceeded")
                for key, _ in selector.select(min(0.2, max(0, deadline - time.monotonic()))):
                    chunk = key.fileobj.read1(8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        key.data.extend(chunk)
                    if len(output) > 1_000_000 or len(errors) > 32_000:
                        raise ValueError("Worker output byte ceiling exceeded")
        if process.wait(timeout=max(0.01, deadline - time.monotonic())) != 0:
            raise RuntimeError("Worker failed; no automatic retry")
        return json.loads(output)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        request_file.close()
        for pipe in (process.stdout, process.stderr):
            pipe.close()


def source_identity() -> dict:
    paths = list((ROOT / "python/src/spy_predictor_quant/investment_research").glob("*.py"))
    paths += list((ROOT / "prompts/investment-research").glob("*/*"))
    paths += list((ROOT / "schemas").glob("investment-research-*.json"))
    paths += [ROOT / "packages/agent-runtime/src/pi-research-worker.ts",
              ROOT / "packages/agent-runtime/src/pi-research-contract.ts", ROOT / "package-lock.json",
              ROOT / "packages/agent-runtime/src/pi-codex-contract.ts",
              ROOT / "python/src/spy_predictor_quant/meta_evidence.py",
              ROOT / "python/src/spy_predictor_quant/meta_analysis.py"]
    import hashlib
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


class Controller:
    def __init__(self, root: Path, worker=subprocess_worker):
        self.store = Store(root)
        self.worker = worker

    def create(self, mandate: dict) -> dict:
        validate("mandate", mandate)
        source_ids = [s["source_id"] for s in mandate["sources"]]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("Duplicate source identity")
        if mandate["budgets"]["model_calls"] < mandate["budgets"]["reserved_final_calls"] + 2:
            raise ValueError("Model budget must leave capacity for research and final challenge/synthesis")
        if not is_m2(mandate) and (len(mandate["watchlist"]) != 1 or mandate["watchlist"][0]["kind"] != "company"):
            raise ValueError("M1 only supports one company; ETF/multi-symbol workflows are pending M2")
        if is_m2(mandate):
            from .multi_instrument import validate_mandate
            validate_mandate(mandate)
        prompt_version = "v2.3" if is_m2(mandate) else PROMPT_VERSION
        roles = M2_ROLES if is_m2(mandate) else ROLES
        with self.store.lock():
            if (self.store.root / "state.json").exists():
                raise ValueError("Run exists; use resume")
            prompts = {role: (ROOT / f"prompts/investment-research/{prompt_version}/shared.md").read_text() + "\n" +
                       (ROOT / f"prompts/investment-research/{prompt_version}/{role}.md").read_text() for role in roles}
            state = {"schema_version": "investment-research-run-v1", "run_id": str(uuid.uuid4()),
                "mandate": mandate, "mandate_hash": content_hash(mandate), "source_identity": source_identity(),
                "prompts": prompts, "started_at": utc_now(), "status": "READY", "phase": "research",
                "capabilities": inventory(mandate),
                "runtime_policy_version": "investment-research-m1-v4", "followup_round": 0,
                "validation_feedback_policy": "Receipted rejected submissions may use remaining task turns; no added calls or retries",
                "stage_turn_limits": {"independent": 4, "planning": 4, "research": 6,
                                      "followup": 4, "triage": 5, "draft": 2, "review": 3, "final": 3},
                "limits": {**mandate["budgets"], "download_bytes": 50_000_000},
                "reservations": {"input_tokens": min(50000, mandate["budgets"]["input_tokens"] // 4),
                    "output_tokens": min(3 * mandate["runtime"]["max_output_tokens"], mandate["budgets"]["output_tokens"] // 4),
                    "tool_calls": min(6, mandate["budgets"]["tool_calls"] // 4),
                    "source_requests": min(3, mandate["budgets"]["source_requests"] // 4)},
                "tasks": [], "questions": [], "attempts": [], "events": [], "evidence_ids": [],
                "source_cache": {}, "source_failures": {}, "discovered_sources": {}, "usage_unknown": False,
                "usage": {k: 0 for k in ("task_attempts", "model_calls", "source_requests", "tool_calls",
                                         "input_tokens", "output_tokens", "catalog_cost_usd", "download_bytes")}}
            state['prompt_version'] = prompt_version
            if is_m2(mandate):
                state['runtime_policy_version'] = 'investment-research-m2-v5'
                state['reservations']['input_tokens'] = min(300000, mandate['budgets']['input_tokens'] // 3)
                state['stage_turn_limits'].update(independent=3, planning=6, research=5)
                state['seed_complete'] = False
                state['market_context'] = {'symbols': mandate['market_context_symbols'], 'inputs': {},
                    'qualification': 'Fixed declared benchmark observations, not selected-watchlist breadth'}
            for name in state["source_identity"]:
                path = self.store.root / "code" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / name).read_bytes())
            state["manifest_id"] = self.store.put("manifests", {"parent": None, "evidence_ids": [], "created_at": utc_now()})
            self.add_task(state, "challenger", "independent", "Form an independent initial risk view from the mandate and evidence.")
            self.add_task(state, "director", "planning", "Define the decision. Assign neutral grouped research to company, macro, technical and geopolitics; optionally commodities. Use ask_specialist, then submit findings. Share the single global budget across all symbols." if is_m2(mandate) else "Define the decision. Assign neutral, material research questions to Company and Macro using ask_specialist, then submit an initial research plan.", round_number=-1)
            self.store.event(state, "RUN_CREATED")
            return state

    def add_task(self, state, role, stage, question, *, round_number=0, parent=None, question_id=None):
        task = {"task_id": f"task-{len(state['tasks']) + 1}", "role": role, "stage": stage,
                "question": question, "round": round_number, "parent_task_id": parent,
                "question_id": question_id, "status": "PENDING", "history": [], "result": None,
                "prompt_version": "investment-research/" + state.get("prompt_version", PROMPT_VERSION),
                "created_at": utc_now(), "symbols": [i["symbol"] for i in state["mandate"]["watchlist"]],
                "permitted_tools": [name for name in TOOLS if name != "route_question" or stage == "triage"],
                "model": state["mandate"]["runtime"]["model"]}
        if is_m2(state["mandate"]) and stage in {"independent", "final", "triage"}:
            task["permitted_tools"].remove("ask_specialist")
        task["model_turn_limit"] = state["stage_turn_limits"]["followup" if stage == "research" and round_number > 0 else stage]
        state["tasks"].append(task)
        self.store.event(state, "TASK_CREATED", task_id=task["task_id"], parent_task_id=parent,
                         model_turn_limit=task["model_turn_limit"], worker_timeout_seconds=state["mandate"]["runtime"]["timeout_seconds"])
        return task

    def run(self) -> dict:
        with self.store.lock():
            state = self.store.load()
            if content_hash(state["mandate"]) != state["mandate_hash"]:
                raise ValueError("Frozen mandate integrity mismatch")
            if source_identity() != state["source_identity"]:
                raise ValueError("Runtime source identity changed; start a new run")
            for identity in state["evidence_ids"]:
                self.store.get("evidence", identity)
            self.store.get("manifests", state["manifest_id"])
            if state["status"] in {"DRAFT", "INCOMPLETE", "INTERRUPTED", "FAILED"}:
                return state
            if any(a["status"] in {"STARTED", "RECEIVED", "FAILED"} for a in state["attempts"]):
                for attempt in state["attempts"]:
                    if attempt["status"] in {"STARTED", "RECEIVED", "FAILED"}:
                        attempt["status"] = "INTERRUPTED"
                state["status"] = "INTERRUPTED"
                state["usage_unknown"] = True
                self.store.event(state, "INTERRUPTED_ATTEMPT_NOT_RETRIED")
                for task in state["tasks"]:
                    if task["status"] in {"PENDING", "RUNNING"}:
                        task["status"] = "INTERRUPTED"
                state["stop_reason"] = "Interrupted or failed model attempt requires a new run; no automatic retry"
                self.store.save(state)
                self.render_incomplete(state)
                return state
            state["status"] = "RUNNING"
            self.store.save(state)
            try:
                if is_m2(state['mandate']) and not state['seed_complete']:
                    broker = Broker(self.store, state)
                    for source_id in state['mandate']['seed_source_ids']:
                        result = broker.call('read_source', {'source_id': source_id})
                        self.store.event(state, 'SEED_SOURCE_READ', source_id=source_id, status=result['status'])
                    from .panels import seed_panels
                    seed_panels(broker)
                    state['seed_complete'] = True
                    self.store.save(state)
                while True:
                    remaining_seconds(state)
                    pending = next((t for t in state["tasks"] if t["status"] in {"PENDING", "RUNNING"}), None)
                    if pending:
                        self.execute_task(state, pending)
                        continue
                    proposed = [q for q in state["questions"] if q["status"] == "PROPOSED"]
                    if proposed:
                        if state["followup_round"] >= state["mandate"]["budgets"]["followup_rounds"]:
                            for question in proposed:
                                question.update(status="DECLINED", disposition="FOLLOWUP_LIMIT")
                        else:
                            state["followup_round"] += 1
                            self.add_task(state, "director", "triage",
                                "Prioritize all PROPOSED questions. Use route_question for each, approving only material resolvable work; then submit findings.",
                                round_number=state["followup_round"])
                            self.store.save(state)
                            continue
                    if state["phase"] == "research":
                        completed_roles = {t["role"] for t in state["tasks"] if t["status"] == "COMPLETE"}
                        if not is_m2(state["mandate"]) and not {"company", "macro"} <= completed_roles:
                            raise ValueError("Director did not obtain Company and Macro findings")
                        state["phase"] = "draft"
                        self.add_task(state, "director", "draft", "Synthesize specialist findings and explain the effect of every question. Account for the independent risk view.")
                    elif state["phase"] == "draft":
                        state["phase"] = "review"
                        self.add_task(state, "challenger", "review", "Review the Director draft against your independent risk view. Return claim-specific objections.")
                    elif state["phase"] == "review":
                        state["phase"] = "final"
                        self.add_task(state, "director", "final", "Produce the final research draft. Explain every question's effect and give a disposition for every objection. Publication is unavailable.")
                    else:
                        self.finish(state)
                        return state
                    self.store.save(state)
            except (LimitReached, ValueError, RuntimeError, TimeoutError, OSError, ValidationError, KeyError) as error:
                state["status"] = "INCOMPLETE"
                state["stop_reason"] = str(error) if isinstance(error, (LimitReached, ValueError)) else type(error).__name__
                for task in state["tasks"]:
                    if task["status"] in {"PENDING", "RUNNING"}:
                        task["status"] = "INCOMPLETE"
                for question in state["questions"]:
                    if question["status"] in {"ACCEPTED", "PROPOSED"}:
                        question["status"] = "UNANSWERED"
                self.store.event(state, "RUN_STOPPED", reason=state["stop_reason"])
                self.render_incomplete(state)
                return state

    def execute_task(self, state, task):
        if task["status"] == "PENDING":
            consume(state, "task_attempts")
            task["status"] = "RUNNING"
            task["started_at"] = utc_now()
            task["manifest_id"] = state["manifest_id"]
            task["visible_evidence_ids"] = state["evidence_ids"][:]
            task["visible_results"] = self.prior_results(state, task)
            self.store.event(state, "TASK_STARTED", task_id=task["task_id"])
        while task["status"] == "RUNNING":
            remaining_turns = task["model_turn_limit"] - len(task["history"])
            if remaining_turns <= 0:
                raise LimitReached("Task model-turn budget exhausted")
            if state["usage_unknown"]:
                raise LimitReached("Unknown usage prevents admission of another model call")
            budget = state["mandate"]["budgets"]
            if state["usage"]["catalog_cost_usd"] >= budget["catalog_cost_usd"]:
                raise LimitReached("catalog_cost_usd ceiling reached")
            if state["phase"] == "research" and state["usage"]["model_calls"] >= budget["model_calls"] - budget["reserved_final_calls"]:
                # Preserve completed findings and final capacity. A task without
                # findings is explicitly omitted rather than silently completed.
                task["status"] = "OMITTED_BUDGET"
                if task['question_id']:
                    question = next(q for q in state['questions'] if q['question_id'] == task['question_id'])
                    question.update(status='UNANSWERED', disposition='Final model-call capacity reserved')
                self.store.event(state, "RESEARCH_RESERVE_REACHED", task_id=task["task_id"])
                return
            runtime = state["mandate"]["runtime"]
            if task["stage"] == "research" and task["round"] > 0:
                if any(state["usage"][key] >= state["limits"][key] - amount
                       for key, amount in state["reservations"].items()):
                    task["status"] = "OMITTED_BUDGET"
                    question = next(q for q in state["questions"] if q["question_id"] == task["question_id"])
                    question.update(status="UNANSWERED", disposition="Final research capacity reserved")
                    self.store.event(state, "FINAL_CAPACITY_RESERVED", task_id=task["task_id"])
                    return
            previous = task["visible_results"]
            request = {"schema_version": WORKER_PROTOCOL, "task_id": task["task_id"],
                "instructions": state["prompts"][task["role"]], "runtime": runtime,
                "context": {"mandate": {k: state["mandate"][k] for k in ("watchlist", "objective", "horizon_sessions", "mode")},
                    "task": {k: task[k] for k in ("task_id", "role", "stage", "question", "symbols")},
                    "manifest_id": task["manifest_id"],
                    "evidence": {i: self.context_evidence(state, task, self.store.get("evidence", i)) for i in task["visible_evidence_ids"]},
                    "prior_findings": previous, "questions": self.visible_questions(state, task),
                    "history": task["history"], "remaining_model_calls": budget["model_calls"] - state["usage"]["model_calls"],
                    "followup_rounds_remaining": budget["followup_rounds"] - state["followup_round"]},
                "tool_schemas": tool_schemas(json.loads((ROOT / f"prompts/investment-research/{state.get('prompt_version', PROMPT_VERSION)}/tools.json").read_text()), task, state, remaining_turns)}
            if is_m2(state['mandate']):
                request['context']['budget'] = {
                    'remaining': {key: state['limits'][key] - value for key, value in state['usage'].items()},
                    'wall_seconds_remaining': remaining_seconds(state),
                    'final_reservations': state['reservations'],
                    'final_model_calls_reserved': budget['reserved_final_calls'],
                    'qualification': 'Shared across all symbols/tasks. Preserve final synthesis; optional research may be omitted before consuming the reserve.'}
                request['context']['market_context'] = {**state['market_context'], 'inputs': {symbol: {'evidence_id': value['evidence_id']} for symbol, value in state['market_context']['inputs'].items()}}
                request['context']['registered_sources'] = [{k: source[k] for k in ('source_id', 'title', 'symbols', 'adapter', 'critical')} for source in state['mandate']['sources']]
                request['context']['role_task_status'] = [{'role': t['role'], 'stage': t['stage'], 'status': t['status']} for t in state['tasks']]
            request["context"]["task_model_turns_remaining"] = remaining_turns
            request["context"]["response_transport"] = "final_identity_maps_v1" if task["stage"] == "final" else "findings_lists_v1"
            if task["stage"] == "final":
                if is_m2(state["mandate"]):
                    request["context"]["response_transport"] = "final_scoped_identity_maps_v2"
                request["context"]["required_objection_dispositions"] = [o for t in state["tasks"] if t["result"] for o in t["result"]["objections"]]
            # UTF-8 byte count is a conservative admission bound, not token usage.
            if len(json.dumps(request).encode()) + state["usage"]["input_tokens"] > budget["input_tokens"]:
                raise LimitReached("input_tokens admission ceiling exceeded")
            if state["usage"]["output_tokens"] + runtime["max_output_tokens"] > budget["output_tokens"]:
                raise LimitReached("output_tokens admission ceiling exceeded")
            consume(state, "model_calls")
            attempt = {"attempt_id": f"attempt-{len(state['attempts']) + 1}", "task_id": task["task_id"],
                       "request_id": self.store.put("requests", request), "started_at": utc_now(), "status": "STARTED"}
            state["attempts"].append(attempt)
            self.store.save(state)  # Persist before crossing the paid model boundary.
            try:
                response = self.worker(request, runtime, min(runtime["timeout_seconds"], remaining_seconds(state)))
                attempt["response_id"] = self.store.put("responses", response)
                attempt["status"] = "RECEIVED"
                self.account(state, response.get("receipt"))
                self.store.save(state)
                if response.get("schema_version") != WORKER_PROTOCOL:
                    raise ValueError("Wrong worker protocol version")
                try:
                    action = restore_action(response["action"], request["tool_schemas"], task["stage"])
                    validate("action", action, m2=is_m2(state["mandate"]))
                    result = self.action(state, task, action)
                except (ValidationError, ValueError) as error:
                    # No tool side effects have occurred for a rejected submission.
                    # This is a new, receipted model/tool turn with explicit feedback,
                    # not an unrecorded replay or provider retry. Other tool failures
                    # remain terminal unless the broker itself returns a typed gap.
                    if not isinstance(response.get("action"), dict) or response["action"].get("tool") != "submit_findings":
                        raise
                    reason = ("Schema violation at " + "/".join(map(str, error.absolute_path)) + ": " + str(error.validator)) if isinstance(error, ValidationError) else str(error)
                    task["history"].append({"action": response["action"], "result": {"status": "REJECTED_VALIDATION", "reason": reason,
                        "instruction": "Correct the rejected submission within the remaining task budget. Critical gaps require insufficient_evidence. Preserve every required identity."},
                        "manifest_id": task["manifest_id"]})
                    attempt["status"] = "REJECTED_VALIDATION"
                    attempt["completed_at"] = utc_now()
                    self.store.event(state, "SUBMISSION_REJECTED", attempt_id=attempt["attempt_id"], reason=reason)
                    continue
                task["history"].append({"action": action, "result": result, "manifest_id": state["manifest_id"]})
                attempt["status"] = "ACCEPTED"
                attempt["completed_at"] = utc_now()
                self.store.event(state, "TURN_ACCEPTED", attempt_id=attempt["attempt_id"], tool=action["tool"])
            except BaseException:
                if attempt["status"] == "STARTED":
                    state["usage_unknown"] = True
                attempt["status"] = "FAILED"
                self.store.save(state)
                raise

    def context_evidence(self, state, task, value):
        if is_m2(state['mandate']):
            from .context import compact
            return compact(value, catalog_only=task['stage'] == 'planning')
        return self.compact_evidence(value)

    @staticmethod
    def compact_evidence(value):
        result = {k: v for k, v in value.items() if k != "excerpt"}
        if "excerpt" in value:
            result["excerpt"] = value["excerpt"][:2000]
            result["context_excerpt_truncated"] = len(value["excerpt"]) > 2000
        return result

    @staticmethod
    def prior_results(state, task):
        if task["stage"] in {"independent", "planning"} or (task["stage"] == "research" and task["round"] == 0):
            return []
        rows = [t for t in state["tasks"] if t["status"] == "COMPLETE"]
        if task["stage"] == "research":
            rows = [t for t in rows if t["task_id"] == task["parent_task_id"]]
        return [{"task_id": t["task_id"], "role": t["role"], "result": t["result"]} for t in rows]

    @staticmethod
    def visible_questions(state, task):
        if task["stage"] in {"independent", "planning"} or (task["stage"] == "research" and task["round"] == 0):
            return []
        if task["stage"] == "research":
            return [q for q in state["questions"] if q["question_id"] == task["question_id"]]
        return state["questions"]

    def account(self, state, receipt):
        if not isinstance(receipt, dict):
            state["usage_unknown"] = True
            raise LimitReached("Worker omitted usage receipt")
        for key in ("input_tokens", "output_tokens", "catalog_cost_usd"):
            amount = receipt.get(key)
            if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount) or amount < 0:
                state["usage_unknown"] = True
                continue
            state["usage"][key] += amount  # Retain overages, including failed turns.
        if state["usage_unknown"]:
            raise LimitReached("Unknown usage or catalog price; further work stopped")
        for key in ("input_tokens", "output_tokens", "catalog_cost_usd"):
            if state["usage"][key] > state["mandate"]["budgets"][key]:
                raise LimitReached(f"Observed {key} exceeded post-response ceiling")

    def action(self, state, task, action):
        name, args = action["tool"], action["arguments"]
        if name not in task["permitted_tools"]:
            raise ValueError("Tool not permitted for this task")
        if name == "route_question":
            consume(state, "tool_calls")
            return self.prioritize(state, task, args)
        if name == "ask_specialist":
            consume(state, "tool_calls")
            return self.route(state, task, args)
        if name == "submit_findings":
            consume(state, "tool_calls")
            prior = [t["result"] for t in state["tasks"] if t["result"]]
            claims = {c["claim_id"] for r in prior for c in r["claims"]}
            validate_findings(args, set(task["visible_evidence_ids"]), claims, {q["question_id"] for q in state["questions"]}, m2=is_m2(state["mandate"]))
            if is_m2(state["mandate"]):
                from .multi_instrument import validate_scoped
                validate_scoped(state, task, args)
            if task["stage"] == "triage" and any(q["status"] == "PROPOSED" for q in state["questions"]):
                raise ValueError("Director triage must dispose of every proposed question")
            task["result"] = args
            task["status"] = "COMPLETE"
            task["completed_at"] = utc_now()
            self.store.event(state, "TASK_COMPLETED", task_id=task["task_id"])
            task["accepted_manifest_id"] = task["manifest_id"]
            if task["question_id"]:
                question = next(q for q in state["questions"] if q["question_id"] == task["question_id"])
                question["status"] = "ANSWERED"
                question["answer_task_id"] = task["task_id"]
            return {"status": "ACCEPTED"}
        result = Broker(self.store, state).call(name, args)
        # Only acquisition/inspection performed by this worker extends its snapshot.
        new_ids = [result["evidence_id"]] if result.get("evidence_id") else []
        if name == "discover_sources":
            new_ids += [i for i in state["source_cache"].values() if i not in task["visible_evidence_ids"]]
        task["visible_evidence_ids"] = list(dict.fromkeys(task["visible_evidence_ids"] + new_ids))
        task["manifest_id"] = self.store.put("manifests", {"parent": task["manifest_id"],
            "evidence_ids": task["visible_evidence_ids"][:], "created_at": utc_now()})
        return result

    def route(self, state, task, args):
        if not set(args["evidence_ids"]) <= set(state["evidence_ids"]):
            raise ValueError("Unknown question evidence")
        if is_m2(state['mandate']) and not set(args['symbols']) <= {i['symbol'] for i in state['mandate']['watchlist']}:
            raise ValueError('Unknown question instrument')
        key = content_hash({"recipient": args["recipient"], "question": " ".join(args["question"].lower().split()),
                            "symbols": sorted(args.get('symbols', []))})
        duplicate = next((q for q in state["questions"] if q["dedup_key"] == key), None)
        question = {"question_id": f"question-{len(state['questions']) + 1}", "parent_task_id": task["task_id"],
            "thesis_id": None, "requester": task["role"], **args, "dedup_key": key,
            "symbol": None if is_m2(state["mandate"]) else state["mandate"]["watchlist"][0]["symbol"], "horizon_sessions": state["mandate"]["horizon_sessions"],
            "round": 0 if task["stage"] == "planning" else state["followup_round"] + 1,
            "status": "PROPOSED", "disposition": "Awaiting Director materiality decision",
            "deadline_seconds_remaining": remaining_seconds(state),
            "remaining_model_calls": state["mandate"]["budgets"]["model_calls"] - state["usage"]["model_calls"]}
        question["model_turn_budget"] = state["stage_turn_limits"]["research" if task["stage"] == "planning" else "followup"]
        reason = None
        if duplicate:
            reason = "DUPLICATE"
            question["duplicate_of"] = duplicate["question_id"]
        elif task["stage"] not in {"planning", "research", "draft", "review"}:
            reason = "RESEARCH_CLOSED_FOR_STAGE"
        elif question["round"] > state["mandate"]["budgets"]["followup_rounds"]:
            reason = "FOLLOWUP_LIMIT"
        elif len(state["tasks"]) >= state["mandate"]["budgets"]["task_attempts"] - 3:
            reason = "TASK_RESERVE"
        if reason:
            question["status"], question["disposition"] = "DECLINED", reason
        elif task["stage"] == "planning":
            child = self.add_task(state, args["recipient"], "research", args["question"],
                round_number=question["round"], parent=task["task_id"], question_id=question["question_id"])
            child["symbols"] = args.get("symbols", child["symbols"])
            question["answer_task_id"] = child["task_id"]
            question.update(status="ACCEPTED", disposition="Director initial research assignment")
        state["questions"].append(question)
        self.store.event(state, "QUESTION_ROUTED", question_id=question["question_id"], status=question["status"])
        return question

    def prioritize(self, state, task, args):
        if task["role"] != "director" or task["stage"] != "triage":
            raise ValueError("Only Director triage can prioritize questions")
        question = next((q for q in state["questions"] if q["question_id"] == args["question_id"]), None)
        if question is None or question["status"] != "PROPOSED":
            raise ValueError("Question is not awaiting prioritization")
        question["director_disposition"] = args
        answer_id = args.get("answer_task_id")
        if args["decision"] == "approve" and answer_id:
            answer = next((t for t in state["tasks"] if t["task_id"] == answer_id), None)
            if answer is None or answer["status"] != "COMPLETE" or answer["role"] != question["recipient"]:
                raise ValueError("Reused answer must be a completed task by the requested specialist")
            if not set(question.get("symbols", [])) <= set(answer.get("symbols", [])):
                raise ValueError("Reused answer must cover the requested instrument scope")
            question.update(status="ANSWERED", disposition=args["reason"], answer_task_id=answer_id, answer_reused=True)
            self.store.event(state, "QUESTION_ANSWER_REUSED", question_id=question["question_id"], answer_task_id=answer_id)
            return question
        reserve = 3 if state["phase"] == "research" else 1
        if args["decision"] == "decline" or len(state["tasks"]) >= state["limits"]["task_attempts"] - reserve:
            question.update(status="DECLINED", disposition=args["reason"] if args["decision"] == "decline" else "TASK_RESERVE")
        else:
            child = self.add_task(state, question["recipient"], "research", question["question"],
                round_number=state["followup_round"], parent=question["parent_task_id"], question_id=question["question_id"])
            child["symbols"] = question.get("symbols", child["symbols"])
            question.update(status="ACCEPTED", disposition=args["reason"], answer_task_id=child["task_id"])
        self.store.event(state, "QUESTION_PRIORITIZED", question_id=question["question_id"], status=question["status"])
        return question

    def finish(self, state):
        if is_m2(state["mandate"]):
            from .multi_instrument import finish
            return finish(self, state)
        final = next(t["result"] for t in reversed(state["tasks"]) if t["stage"] == "final")
        objections = {o["objection_id"]: o for t in state["tasks"] if t["result"] for o in t["result"]["objections"]}
        if len(objections) != sum(len(t["result"]["objections"]) for t in state["tasks"] if t["result"]):
            raise ValueError("Objection identities must be unique across the run")
        dispositions = final["dispositions"]
        if len({d["objection_id"] for d in dispositions}) != len(dispositions) or {d["objection_id"] for d in dispositions} != set(objections):
            raise ValueError("Final Director must dispose of every objection exactly once")
        for d in dispositions:
            if objections[d["objection_id"]]["severity"] == "critical" and d["decision"] == "unresolved" and final["assessment"] != "insufficient_evidence":
                raise ValueError("Unresolved critical objection blocks the assessment")
        effects = final["question_effects"]
        if len({q["question_id"] for q in effects}) != len(effects) or {q["question_id"] for q in effects} != {q["question_id"] for q in state["questions"]}:
            raise ValueError("Final Director must explain the effect of every question exactly once")
        missing = [s["source_id"] for s in state["mandate"]["sources"] if s["critical"] and s["source_id"] not in state["source_cache"]]
        if missing and final["assessment"] != "insufficient_evidence":
            raise ValueError("Unretrieved critical source blocks assessment")
        state["status"] = "DRAFT"
        state["completed_at"] = utc_now()
        product = {"schema_version": "investment-research-product-v2", "run_id": state["run_id"],
            "status": "DRAFT", "publication_status": "NOT_PUBLISHED", "research_started_at": state["started_at"],
            "research_completed_at": state["completed_at"], "published_at": None, "observation_contract": None,
            "symbol": state["mandate"]["watchlist"][0]["symbol"], "horizon_sessions": state["mandate"]["horizon_sessions"],
            "evidence_ids": state["evidence_ids"], "task_ids": [t["task_id"] for t in state["tasks"]], "findings": final,
            "limitations": ["Unpublished research draft; no final market/event refresh or return scoring.",
                "Coverage is limited to the configured source index; linked articles are not automatically read.",
                "Numerical inputs are declared scenarios unless independently verified.",
                "Cost and output-token ceilings may be enforced after a response; catalog cost is an estimate."]}
        validate("product", product)
        state["product_id"] = self.store.put("products", product)
        self.store.event(state, "DRAFT_COMPLETED", product_id=state["product_id"])
        lines = [f"# {product['symbol']} — research draft", "", "NOT PUBLISHED · no observation issued", "",
                 f"Assessment: {final['assessment']}", "", final["summary"], "", "## Counter-thesis", "", final["counter_thesis"], "", "## Claims", ""]
        for claim in final["claims"]:
            refs = ", ".join(f"[{i[:12]}](evidence/{i}.json)" for i in claim["evidence_ids"])
            lines.append(f"- {claim['classification']}: {claim['text']} ({refs or 'assumption/inference'})")
        for heading, entries in (("Assumptions", final["assumptions"]), ("Evidence gaps", [g["description"] for g in final["gaps"]]),
                                 ("Question effects", [f"{e['question_id']} ({e['effect']}): {e['reason']}" for e in effects]),
                                 ("Challenge dispositions", [f"{d['objection_id']} ({d['decision']}): {d['reason']}" for d in dispositions]),
                                 ("Review conditions", [c["description"] for c in final["review_conditions"]]),
                                 ("Coverage and limitations", product["limitations"])):
            lines += ["", f"## {heading}", ""] + [f"- {entry}" for entry in entries]
        calculations = [(i, self.store.get("evidence", i)) for i in state["evidence_ids"]]
        lines += ["", "## Deterministic calculations", ""]
        for identity, value in calculations:
            if value["kind"] == "calculation":
                lines.append(f"- [{identity[:12]}](evidence/{identity}.json): {value['formula']} = `{value['result_decimal']}` {value['units']}; {value['assumptions']}")
        (self.store.root / "draft.md").write_text("\n".join(lines) + "\n")

    def render_incomplete(self, state):
        lines = ["# Incomplete research draft", "", "NOT PUBLISHED · no observation issued", "", state["stop_reason"], ""]
        for task in state["tasks"]:
            if task["result"]:
                lines += [f"## {task['task_id']} / {task['role']}", "", task["result"]["summary"], ""]
        (self.store.root / "draft.md").write_text("\n".join(lines))
