from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from spy_predictor_quant.cycle1_config import (
    assert_candidate_evaluation_allowed,
    load_cycle1_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "config" / "cycle1.json"
SCHEMA = REPO_ROOT / "schemas" / "cycle1-config.schema.json"


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "cycle1.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _payload() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_frozen_preregistration_allows_exactly_ten_candidates() -> None:
    plan = load_cycle1_plan(CONFIG, schema_path=SCHEMA)
    assert plan.instruments == ("SPY", "QQQ")
    assert plan.hypothesis_count == 10
    assert plan.raw["models"]["hmmIncluded"] is False
    with pytest.raises(RuntimeError, match="suspended for pre-evaluation repair"):
        assert_candidate_evaluation_allowed(plan)


@pytest.mark.parametrize("placeholder", [None, "TBD", "todo", "<TBD>", ""])
def test_placeholders_fail_closed(tmp_path: Path, placeholder: object) -> None:
    payload = _payload()
    payload["targets"]["primary"]["formulaNote"] = placeholder
    with pytest.raises(ValueError, match="null|placeholder|Invalid"):
        load_cycle1_plan(_write(tmp_path, payload), schema_path=SCHEMA)


def test_missing_numeric_gate_fails_closed(tmp_path: Path) -> None:
    payload = _payload()
    del payload["promotionGates"]["returnDistribution"]["minimumRelativeImprovement"]
    with pytest.raises((KeyError, ValueError)):
        load_cycle1_plan(_write(tmp_path, payload), schema_path=SCHEMA)


def test_zero_placeholder_gate_fails_closed(tmp_path: Path) -> None:
    payload = _payload()
    payload["promotionGates"]["returnDistribution"]["minimumRelativeImprovement"] = 0
    with pytest.raises(ValueError, match="explicitly positive"):
        load_cycle1_plan(_write(tmp_path, payload), schema_path=SCHEMA)


def test_hmm_or_extra_candidate_fails_closed(tmp_path: Path) -> None:
    payload = _payload()
    payload["models"]["perInstrument"].append(
        {"id": "hmm-3", "kind": "hidden-markov", "promotionRole": "challenger"}
    )
    payload["models"]["hmmIncluded"] = True
    payload["hypothesisBudget"]["modelsPerInstrument"] = 6
    payload["hypothesisBudget"]["primaryEvaluations"] = 12
    with pytest.raises(ValueError, match="Invalid|HMM|five frozen"):
        load_cycle1_plan(_write(tmp_path, payload), schema_path=SCHEMA)


def test_diagnostic_cannot_become_promotion_eligible(tmp_path: Path) -> None:
    payload = copy.deepcopy(_payload())
    payload["targets"]["diagnostic"]["promotionEligible"] = True
    with pytest.raises(ValueError, match="24-month diagnostic"):
        load_cycle1_plan(_write(tmp_path, payload), schema_path=SCHEMA)


def test_license_incompatible_credit_series_fails_closed(tmp_path: Path) -> None:
    payload = _payload()
    payload["features"]["dimensions"]["stress"]["features"][0]["sources"] = [
        "BAA"
    ]
    with pytest.raises(ValueError, match="license-incompatible"):
        load_cycle1_plan(_write(tmp_path, payload), schema_path=SCHEMA)


@pytest.mark.parametrize(
    "section,key",
    [
        ("states.thresholds", "stressChangeMagnitude"),
        ("partitions.bootstrap", "blockLengthMonths"),
        ("promotionGates.drawdown", "maximumExpectedCalibrationError"),
    ],
)
def test_any_missing_frozen_scientific_field_fails_closed(
    tmp_path: Path, section: str, key: str
) -> None:
    payload = _payload()
    selected = payload
    for part in section.split("."):
        selected = selected[part]
    del selected[key]
    with pytest.raises(ValueError, match="missing required field"):
        load_cycle1_plan(_write(tmp_path, payload), schema_path=SCHEMA)
