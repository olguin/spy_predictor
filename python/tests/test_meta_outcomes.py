from datetime import datetime, timezone
import json

import pytest

from spy_predictor_quant.meta_analysis import digest, reference_scenarios
from spy_predictor_quant.meta_observation import register
from spy_predictor_quant.meta_outcomes import (
    capture_due_outcomes,
    evaluation_status,
    load_outcome,
    load_score,
    score_ready_outcomes,
    update,
)


def _forecast(tmp_path):
    packet = {
        "version": "meta-analysis-v1",
        "as_of": "2026-09-10T02:00:00+00:00",
        "symbols": ["SPY"],
        "instruments": {
            "SPY": {
                "status": "FRESH",
                "price_date": "2026-09-09",
                "latest_close": 100.0,
                "reference_scenarios": reference_scenarios(100, 20),
            }
        },
    }
    packet["packet_hash"] = digest(packet)
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet))
    return register(
        packet_path,
        tmp_path / "forecasts",
        now=datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
    )


def test_maturity_states_use_target_close_plus_data_buffer(tmp_path):
    _forecast(tmp_path)
    before = evaluation_status(
        tmp_path / "forecasts", tmp_path / "outcomes", tmp_path / "scores",
        datetime(2026, 9, 16, 20, 19, tzinfo=timezone.utc),
    )
    assert before["counts"] == {"NOT_DUE": 3, "WAITING_FOR_DATA": 0, "READY": 0, "SCORED": 0}
    due = evaluation_status(
        tmp_path / "forecasts", tmp_path / "outcomes", tmp_path / "scores",
        datetime(2026, 9, 16, 20, 20, tzinfo=timezone.utc),
    )
    assert due["counts"] == {"NOT_DUE": 2, "WAITING_FOR_DATA": 1, "READY": 0, "SCORED": 0}
    assert due["records"][0]["target_session"] == "2026-09-16"


def test_outcome_capture_and_scoring_are_separate_immutable_records(tmp_path):
    forecast_path = _forecast(tmp_path)
    original = forecast_path.read_bytes()

    def fetch(url, headers):
        assert headers == {"APCA-API-KEY-ID": "key", "APCA-API-SECRET-KEY": "secret"}
        return json.dumps({
            "symbol": "SPY",
            "bars": [{"t": "2026-09-16T13:30:00Z", "c": 106.0}],
            "next_page_token": None,
        }).encode()

    captured = capture_due_outcomes(
        tmp_path / "forecasts", tmp_path / "outcomes", tmp_path / "scores",
        tmp_path / "captures", datetime(2026, 9, 16, 21, tzinfo=timezone.utc),
        fetch=fetch, environ={"APCA_API_KEY_ID": "key", "APCA_API_SECRET_KEY": "secret"},
    )
    assert captured["status"] == "CAPTURED"
    assert captured["captured"] == 1
    outcome = load_outcome(tmp_path / "outcomes" / json.loads(original)["forecast_hash"] / "SPY-005.json")
    assert outcome["target_close"] == 106
    assert outcome["simple_return"] == pytest.approx(.06)
    assert forecast_path.read_bytes() == original

    scored = score_ready_outcomes(
        tmp_path / "forecasts", tmp_path / "outcomes", tmp_path / "scores",
        tmp_path / "reports", datetime(2026, 9, 16, 21, 1, tzinfo=timezone.utc),
    )
    assert scored["status"] == "SCORED"
    score = load_score(tmp_path / "scores" / outcome["forecast_hash"] / "SPY-005.json")
    assert score["actual"]["event_class"] == "bull"
    assert score["direction_scores"]["call"] == "NO_CALL"
    assert score["direction_scores"]["correct"] is None
    assert score["distribution_scores"]["lognormal_crps"] > 0
    assert forecast_path.read_bytes() == original
    final = evaluation_status(
        tmp_path / "forecasts", tmp_path / "outcomes", tmp_path / "scores",
        datetime(2026, 9, 16, 21, 2, tzinfo=timezone.utc),
    )
    assert final["counts"] == {"NOT_DUE": 2, "WAITING_FOR_DATA": 0, "READY": 0, "SCORED": 1}


def test_no_due_outcomes_do_not_need_credentials_or_write_capture(tmp_path):
    _forecast(tmp_path)
    result = capture_due_outcomes(
        tmp_path / "forecasts", tmp_path / "outcomes", tmp_path / "scores",
        tmp_path / "captures", datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
        environ={},
    )
    assert result["status"] == "NOT_DUE"
    assert not (tmp_path / "captures").exists()
    combined = update(
        tmp_path / "forecasts", tmp_path / "outcomes", tmp_path / "scores",
        tmp_path / "captures", tmp_path / "reports",
        datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
    )
    assert combined["evaluation"]["counts"]["NOT_DUE"] == 3
    assert "records" not in combined["evaluation"]


def test_tampered_forecast_is_rejected_before_maturity_evaluation(tmp_path):
    forecast_path = _forecast(tmp_path)
    value = json.loads(forecast_path.read_text())
    value["symbols"]["SPY"]["origin_close"] = 1
    forecast_path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="integrity"):
        evaluation_status(tmp_path / "forecasts", tmp_path / "outcomes", tmp_path / "scores")
