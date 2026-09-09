"""Hash-locked synthetic design loader; this authority cannot authorize real data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from spy_predictor_quant.cycle1_config import load_cycle1_plan
from spy_predictor_quant.market_archive import content_hash


def load_design(path: Path, *, repo_root: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text())
    schema = json.loads((repo_root / 'schemas/cycle1-simulation-v1.schema.json').read_text())
    errors = list(Draft202012Validator(schema).iter_errors(raw))
    if errors:
        raise ValueError('Invalid simulation design: ' + errors[0].message)
    core = {k: v for k, v in raw.items() if k != 'designHash'}
    if content_hash(core) != raw['designHash']:
        raise ValueError('Simulation design hash mismatch')
    plan = load_cycle1_plan(repo_root / raw['preregistrationPath'])
    if plan.config_hash != raw['preregistrationHash']:
        raise ValueError('Simulation design preregistration hash mismatch')
    if raw['streams']['developmentEntropy'] == raw['streams']['validationEntropy']:
        raise ValueError('Development and validation streams must differ')
    return raw
