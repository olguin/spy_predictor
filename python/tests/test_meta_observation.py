from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from spy_predictor_quant.meta_analysis import digest, reference_scenarios
from spy_predictor_quant.meta_observation import register, target_sessions


def packet():
    value = {"version": "meta-analysis-v1", "as_of": "2026-09-10T02:00:00+00:00",
             "symbols": ["SPY", "MISSING"], "instruments": {
                 "SPY": {"status": "FRESH", "price_date": "2026-09-09", "latest_close": 100,
                         "reference_scenarios": reference_scenarios(100, 20)},
                 "MISSING": {"status": "MISSING"}}}
    value["packet_hash"] = digest(value)
    return value


def test_target_sessions_are_exact_future_xnys_counts():
    endpoints = target_sessions("2026-09-09")
    assert endpoints == {"5": "2026-09-16", "21": "2026-10-08", "63": "2026-12-08"}
    with pytest.raises(ValueError, match="XNYS"):
        target_sessions("2026-09-12")


def test_registers_quant_reference_and_preserves_missing(tmp_path):
    packet_path = tmp_path/"packet.json"
    packet_path.write_text(json.dumps(packet()))
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    result = register(packet_path, tmp_path/"ledger", now=now)
    record = json.loads(result.read_text())
    assert record["symbols"]["SPY"]["status"] == "ISSUED"
    assert record["symbols"]["SPY"]["target_sessions"]["63"] == "2026-12-08"
    assert record["symbols"]["MISSING"]["status"] == "NO_FORECAST"
    assert record["forecast_status"] == "QUANT_ONLY"
    assert record["calibrated_meta_forecast"] is None
    with pytest.raises(FileExistsError):
        register(packet_path, tmp_path/"ledger", now=now)


def test_rejects_packet_tampering_and_wrong_agent_packet(tmp_path):
    value = packet()
    packet_path = tmp_path/"packet.json"
    packet_path.write_text(json.dumps(value))
    report_path = tmp_path/"meta.json"
    report_path.write_text(json.dumps({"packet_hash": "wrong", "results": {}}))
    with pytest.raises(ValueError, match="different packet"):
        register(packet_path, tmp_path/"ledger", report_path, now=datetime(2026, 9, 10, 12, tzinfo=timezone.utc))
    bad = deepcopy(value)
    bad["symbols"].append("LATE")
    packet_path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="integrity"):
        register(packet_path, tmp_path/"other", now=datetime(2026, 9, 10, 12, tzinfo=timezone.utc))


def test_late_registration_and_precutoff_registration_rejected(tmp_path):
    packet_path = tmp_path/"packet.json"
    packet_path.write_text(json.dumps(packet()))
    with pytest.raises(ValueError, match="before the next"):
        register(packet_path, tmp_path/"late", now=datetime(2026, 9, 10, 14, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="after packet cutoff"):
        register(packet_path, tmp_path/"early", now=datetime(2026, 9, 10, 1, tzinfo=timezone.utc))
