#!/usr/bin/env python3
"""Read-only structural M1 acceptance audit. Semantic review remains separate."""
import argparse
import hashlib
import json
from pathlib import Path


def artifact(root, kind, identity):
    value = json.loads((root / kind / f"{identity}.json").read_text())
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    if hashlib.sha256(encoded).hexdigest() != identity:
        raise ValueError(f"Invalid {kind} artifact hash")
    return value


def audit(root: Path):
    state = json.loads((root / "state.json").read_text())
    responses = [artifact(root, "responses", a["response_id"]) for a in state["attempts"] if a.get("response_id")]
    requests = [artifact(root, "requests", a["request_id"]) for a in state["attempts"]]
    tasks = {t["task_id"]: t for t in state["tasks"]}
    product = artifact(root, "products", state["product_id"]) if state.get("product_id") else None
    questions = [q for q in state["questions"] if q["requester"] in {"company", "macro"} and q["status"] == "ANSWERED"]
    ids = {q["question_id"] for q in questions}
    final_effects = product["findings"]["question_effects"] if product else []
    checks = {
        "unpublished_completed_draft": bool(product and product["publication_status"] == "NOT_PUBLISHED" and product["published_at"] is None and product["observation_contract"] is None),
        "real_model_receipts": bool(responses) and all(r.get("receipt", {}).get("pi_version") and r["receipt"].get("model") == state["mandate"]["runtime"]["model"] for r in responses),
        "all_attempts_accounted": all(a["status"] in {"ACCEPTED", "REJECTED_VALIDATION"} for a in state["attempts"]) and not state["usage_unknown"],
        "model_selected_source_retrieval": any(r.get("action", {}).get("tool") == "read_source" for r in responses),
        "cross_specialist_answer": bool(questions),
        "director_prioritized_answered_followups": bool(questions) and all(q.get("director_disposition", {}).get("decision") == "approve" for q in questions),
        "director_explained_question_effect": bool(ids) and ids <= {e["question_id"] for e in final_effects if e["reason"]},
        "initial_specialists_independent": all(not r["context"]["prior_findings"] for r in requests if tasks[r["task_id"]]["stage"] in {"planning", "independent"} or
            (tasks[r["task_id"]]["stage"] == "research" and tasks[r["task_id"]]["round"] == 0)),
        "declared_manifest_matches_visible_evidence": all(set(artifact(root, "manifests", r["context"]["manifest_id"])["evidence_ids"]) == set(r["context"]["evidence"]) for r in requests),
        "source_code_archived": all((root / "code" / p).exists() and hashlib.sha256((root / "code" / p).read_bytes()).hexdigest() == h for p, h in state["source_identity"].items()),
    }
    return {"version": "investment-research-m1-acceptance-v1", "run_id": state["run_id"], "run_directory": str(root),
            "structural_status": "PASS" if all(checks.values()) else "INCOMPLETE", "checks": checks,
            "usage": state["usage"], "cross_specialist_questions": questions,
            "semantic_review": "REQUIRED_SEPARATELY", "release_status": "M0_M4_NOT_COMPLETE"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.run), indent=2))
