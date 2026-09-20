"""Shared controller/worker contracts, with fail-closed reference validation."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[4]
ROLES = ("director", "company", "macro", "challenger")
TOOLS = ("discover_sources", "read_source", "inspect_evidence", "calculate", "ask_specialist", "submit_findings", "route_question")
PROMPT_VERSION = "v1.2"
WORKER_PROTOCOL = "pi-research-worker-v2"


def schema(name: str) -> dict:
    version = "v3" if name == "action" else "v2" if name in {"findings", "product"} else "v1"
    return json.loads((ROOT / "schemas" / f"investment-research-{name}-{version}.schema.json").read_text())


def validate(name: str, value: dict) -> None:
    definition = schema(name)
    if name == "mandate" and value.get("schema_version") == "investment-research-mandate-v2":
        definition = json.loads((ROOT / "schemas/investment-research-mandate-v2.schema.json").read_text())
    Draft202012Validator(definition, format_checker=FormatChecker()).validate(value)


def load_mandate(path: Path) -> dict:
    value = json.loads(path.read_text())
    validate("mandate", value)
    if len(value["watchlist"]) != 1:
        raise ValueError("M1 supports exactly one instrument; multi-symbol scheduling belongs to M2")
    ids = [s["source_id"] for s in value["sources"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source identity")
    if value["budgets"]["model_calls"] < value["budgets"]["reserved_final_calls"] + 2:
        raise ValueError("Model budget must leave capacity for research and final challenge/synthesis")
    return value


def validate_findings(result: dict, evidence_ids: set[str], claim_ids: set[str], question_ids: set[str]) -> None:
    validate("findings", result)
    own_ids = [c["claim_id"] for c in result["claims"]]
    if len(own_ids) != len(set(own_ids)) or set(own_ids) & claim_ids:
        raise ValueError("Claim identities must be unique across the run")
    for claim in result["claims"]:
        if not set(claim["evidence_ids"]) <= evidence_ids:
            raise ValueError("Unknown or unread evidence reference")
        if claim["classification"] == "fact" and not claim["evidence_ids"]:
            raise ValueError("A fact requires retrieved evidence")
    for objection in result["objections"]:
        if not set(objection["claim_ids"]) <= claim_ids | set(own_ids):
            raise ValueError("Unknown objection claim reference")
    for effect in result["question_effects"]:
        if effect["question_id"] not in question_ids:
            raise ValueError("Unknown question effect")
    if any(g["critical"] for g in result["gaps"]) and result["assessment"] != "insufficient_evidence":
        raise ValueError("A critical gap blocks the affected instrument assessment")
