from copy import deepcopy
import json
from pathlib import Path

import pytest

from spy_predictor_quant.meta_prompt_eval import machine_grade, prepare, execute


def test_missing_news_machine_gate_does_not_certify_semantics_or_allow_direction():
    response = {"assessments": [{"claims": [], "horizon_assessments": [{"direction": "UNKNOWN"} for _ in range(3)]}]}
    result = machine_grade(response, ["UNKNOWN_HORIZONS", "NO_CLAIMS"])
    assert result["machine_status"] == "PASS"
    assert result["semantic_review_status"] == "REQUIRED"
    response["assessments"][0]["horizon_assessments"][0]["direction"] = "BULLISH"
    assert machine_grade(response, ["UNKNOWN_HORIZONS"])["machine_status"] == "FAIL"


def test_prompt_corpus_is_frozen_before_requests_and_tampering_prevents_model_calls(tmp_path):
    root = tmp_path / "eval"
    corpus = json.loads(Path("config/meta-prompt-eval-v1.json").read_text())
    runner = {"argv": ["this-must-never-run"], "model": "test"}
    prepare(root, corpus, runner)
    with pytest.raises(FileExistsError):
        prepare(root, corpus, runner)
    path = root / "absent_news" / "packet.json"
    value = json.loads(path.read_text())
    value["symbols"] = ["TAMPERED"]
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="packet changed"):
        execute(root, Path("config/meta-operations-v1.json"))
