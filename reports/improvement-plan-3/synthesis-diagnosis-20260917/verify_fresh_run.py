"""Verify a newly completed run without issuing forecasts or changing inputs."""
import json
from pathlib import Path
import subprocess
import sys

from spy_predictor_quant.market_archive import file_sha256, utc_now, write_json_exclusive
from spy_predictor_quant.meta_analysis import digest
from spy_predictor_quant.meta_agents import ROLES, _reusable_role, _verified_run_manifest, validate_output

run = Path(sys.argv[1])
output = Path(sys.argv[2])
recovery = Path(sys.argv[3]) if len(sys.argv) > 3 else None
final_run = recovery or run
load = lambda path: json.loads(path.read_text())
manifest = _verified_run_manifest(run)
packet_path = Path(manifest["packet_path"])
packet = load(packet_path)
assert packet["packet_hash"] == digest({k: v for k, v in packet.items() if k != "packet_hash"})
assert manifest["packet_hash"] == packet["packet_hash"]
config = load(run / "runner-config.json")
assert manifest["runtime_config_hash"] == digest(config)
report = load(run / "meta-report.json")
if recovery:
    assert report["status"] == "PARTIAL" and set(report["failures"]) == {"synthesis"}
    registration = load(recovery / "registration.json")
    assert registration["registration_hash"] == digest({k: v for k, v in registration.items() if k != "registration_hash"})
    assert Path(registration["source_run"]).resolve() == run.resolve()
    assert registration["source_report_sha256"] == file_sha256(run / "meta-report.json")
    final_report = load(recovery / "meta-report.json")
    assert final_report["status"] == "COMPLETED_UNCALIBRATED_RESEARCH" and not final_report["failures"]
else:
    assert report["status"] == "COMPLETED_UNCALIBRATED_RESEARCH" and not report["failures"]
assert not report["reused_roles"] and not report["resumed_from"]
assert set(report["newly_executed_roles"]) == set(ROLES)
roles = []
for role in ROLES:
    if recovery and role == "synthesis":
        request = load(recovery / "request.json")
        assert file_sha256(recovery / "request.json") == registration["request_sha256"]
        envelope = load(recovery / "stdout.txt")
        assert "failure" not in envelope
        validate_output(envelope["result"], request)
        assert envelope["result"] == final_report["results"][role]
        assert envelope["receipt"]["requested_model"] == envelope["receipt"]["response_model"] == config["models"][role]
        roles.append({"role": role, "model": envelope["receipt"]["response_model"],
            "input_tokens": envelope["receipt"]["input_tokens"], "output_tokens": envelope["receipt"]["output_tokens"],
            "latency_ms": envelope["receipt"]["latency_ms"],
            "receipt_sha256": file_sha256(recovery / "synthesis-receipt.json"), "source": "REGISTERED_SYNTHESIS_RECOVERY"})
        continue
    request = load(run / f"{role}-request.json")
    assert request["input_hash"] == digest({k: v for k, v in request.items()
        if k not in {"input_hash", "output_schema", "runtime"}})
    assert request["agent_contract_version"] == "meta-agent-output-v4"
    verified = _reusable_role(run, role, request)
    assert verified is not None and verified[0] == report["results"][role]
    if recovery:
        assert verified[0] == final_report["results"][role]
    receipt = verified[1]
    model = config.get("models", {}).get(role, config["model"])
    assert receipt["requested_model"] == receipt["response_model"] == model
    assert receipt["thinking_level"] == config["reasoning_effort"]
    assert receipt["numeric_enum_transport"] == "exact_decimal_strings_v1"
    roles.append({"role": role, "model": model, "input_tokens": receipt["input_tokens"],
        "output_tokens": receipt["output_tokens"], "latency_ms": receipt["latency_ms"],
        "receipt_sha256": file_sha256(run / f"{role}-receipt.json")})
on_demand = load(run / "on-demand-receipt.json")
assert on_demand["receipt_hash"] == digest({k: v for k, v in on_demand.items() if k != "receipt_hash"})
assert on_demand["status"] == ("PARTIAL" if recovery else "COMPLETED") and not on_demand["prospective_registration"]
assert on_demand["information_cutoff"] == packet["as_of"]
subprocess.run([sys.executable,
    "reports/improvement-plan-3/handoff-20260917/verify_product_parity.py",
    str(final_run / "product"), str(final_run / "structured-forecast.json"), str(final_run / "product"),
    str(run / "synthesis-request.json")], check=True)
product = load(final_run / "product/summary.json")
assert product["as_of"] == packet["as_of"]
receipt = {"checked_at": utc_now(), "status": "PASS",
    "scope": "FRESH_CAPTURE_CHAIN_WITH_REGISTERED_RECOVERY" if recovery else "FRESH_SEVEN_ROLE_ENGINEERING_VERIFICATION",
    "single_pass_completed": recovery is None,
    "source_attempt_calls": 7, "additional_recovery_calls": 1 if recovery else 0,
    "packet_path": str(packet_path), "packet_sha256": file_sha256(packet_path),
    "cutoff": packet["as_of"], "roles": roles, "recovery_reused_roles": list(ROLES)[:-1] if recovery else [],
    "frozen_decision_rows": 15, "prospective_registration": False,
    "product_status": product["run_status"], "publication_lag_seconds": product["publication_lag_seconds"],
    "primary_acquisition_errors": sorted(packet["acquisition_errors"]),
    "supplemental_acquisition_errors": sorted(packet["supplemental_acquisition_errors"]),
    "product_parity_sha256": file_sha256(final_run / "product/product-parity-verification.json"),
    "report_sha256": file_sha256(final_run / "meta-report.json"),
    "on_demand_receipt_sha256": file_sha256(run / "on-demand-receipt.json"),
    "notice": "Engineering verification only. The initial partial run remains partial; its interrupted synthesis usage is unknown. Retains cutoff/publication gates; no calibrated accuracy, historical qualification, forecast issuance or trading is implied."}
write_json_exclusive(output, receipt)
print(json.dumps({"status": "PASS", "roles": len(roles), "frozen_rows": 15, "receipt": str(output)}))
