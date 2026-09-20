"""Bounded synthesis recovery from verified completed specialists and critic.

Projects redundant context, never recalculates numerical decisions. Every parent
artifact and the exact projected model request remain separately hash-bound.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess

from spy_predictor_quant.market_archive import create_immutable_run_directory, file_sha256, utc_now, write_json_exclusive
from spy_predictor_quant.meta_analysis import digest
from spy_predictor_quant.meta_agents import (
    INDEPENDENT, _reusable_role, _terminate_process_group, _verified_run_manifest,
    output_schema, validate_output,
)


def _retain_pointer(source, target, tokens: list[str]):
    """Preserve original JSON Pointer indexes, including sparse array positions."""
    key = int(tokens[0]) if isinstance(source, list) else tokens[0]
    value = source[key]
    if isinstance(target, list):
        while len(target) <= key:
            target.append(None)
    if len(tokens) == 1:
        target[key] = deepcopy(value)
        return
    if (isinstance(target, list) and target[key] is None) or (isinstance(target, dict) and key not in target):
        target[key] = [] if isinstance(value, list) else {}
    _retain_pointer(value, target[key], tokens[1:])


def compact_request(original: dict) -> dict:
    if original["role"] != "synthesis":
        raise ValueError("Recovery projection is synthesis-only")
    prior = deepcopy(original["prior_results"])
    forecast = prior["numerical_forecast"]
    original_forecast_hash = digest(forecast)
    for symbol in forecast["symbols"].values():
        for horizon in symbol["horizons"]:
            # Keep distributions, references and every recommendation field exact.
            for key in ("ablations", "context_signal", "quant_signal", "combined_signal"):
                horizon.pop(key, None)
    for role, result in prior["results"].items():
        for row in result.get("assessments", []):
            if role == "critic":
                # Its exhaustive claim_decisions and audit_summary remain intact.
                for key in ("horizon_assessments", "claims"):
                    row.pop(key, None)
            else:
                row["horizon_assessments"] = [{k: v for k, v in h.items() if k in (
                    "trading_days", "status", "direction", "strongest_support_claim_ids",
                    "strongest_opposition_claim_ids", "missing_evidence")} for h in row.get("horizon_assessments", [])]
    source = original["packet"]
    packet = {key: deepcopy(source[key]) for key in ("version", "as_of", "symbols", "etfs", "horizons",
        "notice", "source_packet_hash", "product_contract", "operating_context", "quantitative_forecast_status",
        "acquisition_errors", "supplemental_acquisition_errors") if key in source}
    packet["instruments"] = {symbol: {k: deepcopy(v) for k, v in values.items() if k in (
        "status", "latest_close", "price_date", "available_at", "feed", "adjustment", "realized_vol63_pct")}
        for symbol, values in source.get("instruments", {}).items()}
    cited = set()
    for result in original["prior_results"]["results"].values():
        for row in result.get("assessments", []):
            for claim in row.get("claims", []):
                cited.update(claim["evidence_ids"])
                for numeric in claim["numeric_values"]:
                    tokens = [t.replace("~1", "/").replace("~0", "~") for t in numeric["packet_path"].lstrip("/").split("/")]
                    try:
                        _retain_pointer(source, packet, tokens)
                    except (KeyError, IndexError, TypeError, ValueError):
                        # Quarantined numeric defects remain in critic decisions.
                        continue
    packet["evidence"] = {key: deepcopy(value) for key, value in source["evidence"].items() if key in cited}
    packet["projection"] = {"version": "meta-synthesis-recovery-v1", "role": "synthesis",
        "parent_input_hash": original["input_hash"], "source_packet_hash": source.get("source_packet_hash"),
        "numerical_forecast_parent_hash": original_forecast_hash,
        "omitted": ["uncited packet context", "redundant horizon prose", "numerical ablation distributions", "intermediate heuristic signals"],
        "preserved": ["all specialist claims", "critic claim decisions", "accepted claim references",
                      "numeric JSON Pointer paths", "frozen distributions, references and complete recommendations"]}
    content = {"role": "synthesis", "packet": packet, "prior_results": prior,
        "instructions": original["instructions"] + "\nThis recovery projection omits redundant source context. Use critic decisions and preserved claims; omitted fields are not newly missing evidence. Frozen recommendations, references and distributions are copied exactly from the original numerical forecast.",
        "agent_contract_version": original["agent_contract_version"],
        "implementation_sha256": original["implementation_sha256"],
        "recovery_implementation_sha256": file_sha256(Path(__file__)), "parent_input_hash": original["input_hash"]}
    identity = digest(content)
    return {**content, "input_hash": identity, "runtime": deepcopy(original["runtime"]),
            "output_schema": output_schema("synthesis", identity, packet["symbols"], sorted(packet["evidence"]), prior)}


def diagnostic_request(original: dict) -> dict:
    """One archived symbol, three frozen decisions; tests transport/contract only."""
    if original["role"] != "synthesis" or original["agent_contract_version"] != "meta-agent-output-v4":
        raise ValueError("Diagnostic requires a v4 synthesis parent")
    symbol = sorted(original["prior_results"]["numerical_forecast"]["symbols"])[0]
    numerical = original["prior_results"]["numerical_forecast"]
    horizons = [{k: deepcopy(h[k]) for k in ("trading_days", "status", "distribution", "reference", "recommendation")}
                for h in numerical["symbols"][symbol]["horizons"]]
    prior = {"results": {}, "numerical_forecast": {"schema_version": numerical["schema_version"],
        "symbols": {symbol: {"horizons": horizons}}}}
    packet = {"version": original["packet"]["version"], "symbols": [symbol], "evidence": {},
        "as_of": original["packet"]["as_of"], "instruments": {},
        "notice": "Archived numerical-only synthesis diagnostic. No current-operation or full-chain qualification."}
    content = {"role": "synthesis", "packet": packet, "prior_results": prior,
        "agent_contract_version": "meta-agent-output-v4", "parent_input_hash": original["input_hash"],
        "implementation_sha256": original["implementation_sha256"],
        "recovery_implementation_sha256": file_sha256(Path(__file__)),
        "instructions": "This is a small archived numerical-parity diagnostic, not a market assessment. "
            "Call submit_result once using the v4 schema. Give one assessment with INSUFFICIENT_EVIDENCE, "
            "UNKNOWN view, named missing specialist evidence, empty claims, and exactly 5/21/63 horizon assessments. "
            "Use INSUFFICIENT_EVIDENCE and UNKNOWN on each horizon, empty support/opposition arrays, "
            "UNAVAILABLE confirmation/invalidation triggers with null level and no evidence IDs. "
            "Copy all three golden decision rows exactly from the supplied numerical forecast, using "
            "forecast_ref /symbols/" + symbol + "/horizons/0, /1, /2 respectively. "
            "Keep explanations short. Research priority is not buy attractiveness. "
            "Set new_material_contradiction to null. Do not invent claims or current facts."}
    identity = digest(content)
    runtime = {**deepcopy(original["runtime"]), "transport": "sse", "max_output_tokens": 5000}
    return {**content, "input_hash": identity, "runtime": runtime,
        "output_schema": output_schema("synthesis", identity, [symbol], [], prior)}


def prepare(source: Path, output: Path, model: str | None = None, *, diagnostic: bool = False) -> Path:
    manifest = _verified_run_manifest(source)
    report_path = source / "meta-report.json"
    report = json.loads(report_path.read_text())
    if report["packet_hash"] != manifest["packet_hash"] or report["harness_implementation_sha256"] != manifest["harness_implementation_sha256"]:
        raise ValueError("Recovery source report identity mismatch")
    if set(report.get("failures", {})) - {"synthesis"}:
        raise ValueError("Recovery requires all independent roles and critic completed")
    hashes = {}
    for role in (*INDEPENDENT, "critic"):
        request = json.loads((source / f"{role}-request.json").read_text())
        verified = _reusable_role(source, role, request)
        if verified is None or verified[0] != report["results"][role]:
            raise ValueError("Incomplete or mismatched completed role")
        hashes[role] = file_sha256(source / f"{role}-completion.json")
    original = json.loads((source / "synthesis-request.json").read_text())
    content = {k: v for k, v in original.items() if k not in {"input_hash", "output_schema", "runtime"}}
    if digest(content) != original["input_hash"]:
        raise ValueError("Original synthesis request integrity mismatch")
    if original["prior_results"]["results"] != report["results"]:
        raise ValueError("Original synthesis dependencies differ from verified roles")
    request = diagnostic_request(original) if diagnostic else compact_request(original)
    request["runtime"]["transport"] = "sse"
    runner = json.loads((source / "runner-config.json").read_text())
    if model is not None:
        if diagnostic:
            raise ValueError("Diagnostic preserves the configured synthesis model")
        if model not in {runner["model"], *runner.get("models", {}).values()}:
            raise ValueError("Recovery model must be one of the already configured research models")
        request["runtime"]["model"] = model
    run = create_immutable_run_directory(output, "synthesis-diagnostic" if diagnostic else "synthesis-recovery")
    write_json_exclusive(run / "request.json", request)
    core = {"source_run": str(source.resolve()), "source_report_sha256": file_sha256(report_path),
        "parent_request_sha256": file_sha256(source / "synthesis-request.json"), "completion_hashes": hashes,
        "request_sha256": file_sha256(run / "request.json"), "request_hash": request["input_hash"],
        "runner": runner, "timeout_seconds": 180 if diagnostic else 900, "attempts": 1,
        "purpose": "ARCHIVED_SMALL_CONTRACT_DIAGNOSTIC" if diagnostic else "FULL_SYNTHESIS_RECOVERY",
        "original_synthesis_model": original["runtime"]["model"], "recovery_model": request["runtime"]["model"],
        "model_override": model,
        "runtime_dependencies": {str(p): file_sha256(p) for p in (
            Path("packages/agent-runtime/src/pi-codex-adapter.ts"),
            Path("packages/agent-runtime/src/pi-codex-contract.ts"),
            Path("packages/agent-runtime/src/pi-codex-progress.ts"),
            Path("packages/agent-runtime/bin/pi-codex-adapter"),
            Path("python/src/spy_predictor_quant/meta_agents.py"), Path("package-lock.json"))},
        "original_compact_json_bytes": len(json.dumps(original).encode()),
        "projected_compact_json_bytes": len(json.dumps(request).encode()),
        "implementation_sha256": file_sha256(Path(__file__)), "created_at": utc_now()}
    write_json_exclusive(run / "registration.json", {**core, "registration_hash": digest(core)})
    return run


def execute(run: Path) -> Path:
    registration = json.loads((run / "registration.json").read_text())
    if registration.pop("registration_hash") != digest(registration) or registration["implementation_sha256"] != file_sha256(Path(__file__)):
        raise ValueError("Synthesis recovery registration changed")
    if file_sha256(run / "request.json") != registration["request_sha256"]:
        raise ValueError("Synthesis recovery request changed")
    if any(file_sha256(Path(path)) != value for path, value in registration["runtime_dependencies"].items()):
        raise ValueError("Synthesis recovery runtime changed")
    source = Path(registration["source_run"])
    if file_sha256(source / "meta-report.json") != registration["source_report_sha256"]:
        raise ValueError("Synthesis recovery parent report changed")
    request = json.loads((run / "request.json").read_text())
    write_json_exclusive(run / "started.json", {"started_at": utc_now(), "request_hash": request["input_hash"]})
    try:
        with (run / "stdout.txt").open("xb") as out, (run / "stderr.txt").open("xb") as err:
            process = subprocess.Popen(registration["runner"]["argv"], stdin=subprocess.PIPE,
                stdout=out, stderr=err, start_new_session=True)
            try:
                process.communicate(json.dumps(request).encode(), timeout=registration["timeout_seconds"])
            except BaseException:
                _terminate_process_group(process)
                raise
            if process.returncode:
                raise ValueError(f"Synthesis adapter exited {process.returncode}")
        if (run / "stdout.txt").stat().st_size > 200_000:
            raise ValueError("Synthesis response exceeds bounded output limit")
        envelope = json.loads((run / "stdout.txt").read_text())
        result, receipt = envelope["result"], envelope["receipt"]
        if receipt.get("provider") != "openai-codex" or receipt.get("requested_model") != request["runtime"]["model"] or receipt.get("response_model") != request["runtime"]["model"]:
            raise ValueError("Synthesis receipt provider/model mismatch")
        validate_output(result, request)
        write_json_exclusive(run / "synthesis-result.json", result)
        write_json_exclusive(run / "synthesis-receipt.json", receipt)
        if registration.get("purpose") == "ARCHIVED_SMALL_CONTRACT_DIAGNOSTIC":
            write_json_exclusive(run / "completed.json", {"completed_at": utc_now(),
                "purpose": registration["purpose"], "full_chain_qualified": False,
                "current_operation_qualified": False, "contract_valid": True,
                "registration_sha256": file_sha256(run / "registration.json"),
                "result_sha256": file_sha256(run / "synthesis-result.json"),
                "receipt_sha256": file_sha256(run / "synthesis-receipt.json")})
            return run / "completed.json"
        report = json.loads((source / "meta-report.json").read_text())
        report["results"]["synthesis"] = result
        report["source_operational_budget"] = report.get("operational_budget")
        report["operational_budget"] = None
        report.update(failures={}, status="COMPLETED_UNCALIBRATED_RESEARCH", completed_at=utc_now(),
            resumed_from=str(source), reused_roles=[*INDEPENDENT, "critic"], newly_executed_roles=["synthesis"],
            synthesis_recovery={"registration_sha256": file_sha256(run / "registration.json"),
                                "request_sha256": registration["request_sha256"], "parent_report_sha256": registration["source_report_sha256"],
                                "receipt_sha256": file_sha256(run / "synthesis-receipt.json"),
                                "usage_status": "RECOVERY_RECEIPT_AVAILABLE_PRIOR_TIMEOUT_USAGE_UNKNOWN",
                                "actual_model": receipt["response_model"],
                                "requested_transport": receipt.get("requested_transport"),
                                "original_synthesis_model": registration["original_synthesis_model"],
                                "bounded_calls": 1, "timeout_seconds": registration["timeout_seconds"]})
        # The synthesis request carries the authoritative numerical artifact.
        original = json.loads((source / "synthesis-request.json").read_text())
        numerical = deepcopy(original["prior_results"]["numerical_forecast"])
        write_json_exclusive(run / "meta-report.json", report)
        numerical.update(agent_report_sha256=file_sha256(run / "meta-report.json"))
        numerical.pop("artifact_hash", None)
        numerical["artifact_hash"] = digest(numerical)
        write_json_exclusive(run / "structured-forecast.json", numerical)
        return run / "meta-report.json"
    except Exception as exc:
        write_json_exclusive(run / "failed.json", {"error_type": type(exc).__name__, "reason": str(exc)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "prepare-diagnostic", "run"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--model")
    args = parser.parse_args()
    if args.command in {"prepare", "prepare-diagnostic"}:
        if not args.source or not args.output:
            parser.error("prepare requires --source and --output")
        path = prepare(args.source, args.output, args.model, diagnostic=args.command == "prepare-diagnostic")
    else:
        if not args.run:
            parser.error("run requires --run")
        path = execute(args.run)
    print(json.dumps({"path": str(path)}))


if __name__ == "__main__":
    main()
