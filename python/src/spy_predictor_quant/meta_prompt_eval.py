"""Freeze and execute a bounded semantic prompt corpus with explicit review gates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from spy_predictor_quant.market_archive import file_sha256, write_json_exclusive
from spy_predictor_quant.meta_analysis import digest
from spy_predictor_quant.meta_agents import request_for, run_agents, validate_output


def prepare(root: Path, corpus: dict, runner: dict) -> Path:
    if corpus.get("schema_version") != "meta-prompt-eval-v1":
        raise ValueError("Unknown evaluation corpus")
    cases = corpus["cases"]
    if not 1 <= len(cases) <= 8 or len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Evaluation requires a bounded unique case set")
    root.mkdir(parents=True, exist_ok=False)
    runner = {**runner, "roles": ["news"], "max_parallel": 1}
    write_json_exclusive(root / "runner.json", runner)
    frozen = []
    for case in cases:
        if not case["id"].replace("_", "").isalnum():
            raise ValueError("Invalid fixture identity")
        packet = {"version": "meta-analysis-v1", "as_of": "2026-09-15T16:00:00Z",
                  "symbols": ["CASEA"], "etfs": [], "horizons": [5, 21, 63], "instruments": {"CASEA": {}},
                  "evidence": case["evidence"], "notice": "Synthetic source-only fixture. CASEA is an invented instrument."}
        packet["packet_hash"] = digest(packet)
        path = root / case["id"]
        path.mkdir()
        write_json_exclusive(path / "packet.json", packet)
        request = request_for("news", packet)
        write_json_exclusive(path / "expected-request.json", request)
        frozen.append({**case, "packet_hash": packet["packet_hash"], "request_hash": request["input_hash"]})
    core = {"schema_version": "meta-prompt-eval-registration-v1", "corpus_hash": digest(corpus),
            "runner_hash": digest(runner), "cases": frozen,
            "implementation_sha256": file_sha256(Path(__file__)), "predictive_skill_evaluation": False}
    write_json_exclusive(root / "registration.json", {**core, "registration_hash": digest(core)})
    return root / "registration.json"


def machine_grade(result: dict, rules: list[str]) -> dict:
    rows = result["assessments"]
    checks = {}
    for rule in rules:
        if rule == "UNKNOWN_HORIZONS":
            checks[rule] = all(h["direction"] == "UNKNOWN" for r in rows for h in r["horizon_assessments"])
        elif rule == "NO_CLAIMS":
            checks[rule] = all(not r["claims"] for r in rows)
        elif rule == "NO_NUMERIC_VALUES":
            checks[rule] = all(not c["numeric_values"] for r in rows for c in r["claims"])
        else:
            raise ValueError("Unknown semantic fixture rule")
    return {"checks": checks, "machine_status": "PASS" if all(checks.values()) else "FAIL",
            "semantic_review_status": "REQUIRED", "notice": "Schema and machine checks cannot establish semantic correctness."}


def execute(root: Path, operations_policy: Path) -> Path:
    registration = json.loads((root / "registration.json").read_text())
    if registration.pop("registration_hash") != digest(registration):
        raise ValueError("Prompt corpus registration integrity mismatch")
    if registration["implementation_sha256"] != file_sha256(Path(__file__)):
        raise ValueError("Prompt evaluator changed after registration")
    runner = root / "runner.json"
    if digest(json.loads(runner.read_text())) != registration["runner_hash"]:
        raise ValueError("Prompt evaluator runner changed")
    outcomes = []
    for case in registration["cases"]:
        folder = root / case["id"]
        packet_path = folder / "packet.json"
        packet = json.loads(packet_path.read_text())
        if packet.pop("packet_hash") != digest(packet) or digest(packet) != case["packet_hash"]:
            raise ValueError("Prompt fixture packet changed")
        packet["packet_hash"] = case["packet_hash"]
        request = request_for("news", packet)
        if request["input_hash"] != case["request_hash"]:
            raise ValueError("Prompt changed after corpus freeze")
        receipt_path = folder / "evaluation.json"
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            report_path = Path(receipt["report"])
            if file_sha256(report_path) != receipt["report_sha256"]:
                raise ValueError("Prompt evaluation report changed")
        else:
            run = run_agents(packet_path, runner, folder / "runs", operations_policy_path=operations_policy)
            report_path = run / "meta-report.json"
            report = json.loads(report_path.read_text())
            result = report["results"].get("news")
            if report["failures"] or result is None:
                grade = {"machine_status": "FAIL", "failures": report["failures"], "semantic_review_status": "NOT_RUN"}
            else:
                rejections = validate_output(result, request, allow_deterministic_claim_rejections=True)
                grade = machine_grade(result, case["machine_rules"])
                if rejections:
                    grade.update(machine_status="FAIL", deterministic_rejections=rejections)
            receipt = {"case": case["id"], "report": str(report_path.resolve()),
                       "report_sha256": file_sha256(report_path), "rubric": case["rubric"], **grade}
            write_json_exclusive(receipt_path, receipt)
        outcomes.append(receipt)
    path = root / "machine-results.json"
    write_json_exclusive(path, {"cases": outcomes, "predictive_skill_evaluation": False,
                               "semantic_review_status": "REQUIRED"})
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=Path("config/meta-prompt-eval-v1.json"))
    parser.add_argument("--runner", type=Path, default=Path("config/meta-agent-pi-codex.example.json"))
    parser.add_argument("--operations-policy", type=Path, default=Path("config/meta-operations-v1.json"))
    args = parser.parse_args()
    path = (prepare(args.root, json.loads(args.corpus.read_text()), json.loads(args.runner.read_text()))
            if args.command == "prepare" else execute(args.root, args.operations_policy))
    print(json.dumps({"path": str(path)}))


if __name__ == "__main__":
    main()
