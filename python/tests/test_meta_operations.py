from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from spy_predictor_quant.meta_analysis import digest
from spy_predictor_quant.meta_operations import (
    AlertLedger, BudgetExceeded, BudgetLedger, OperationLedger, ReleaseCache,
    load_operations_policy, schedule_decision,
)
from spy_predictor_quant.meta_scheduler import run_outcomes, run_prospective


NOW = datetime(2026, 9, 14, 20, 25, tzinfo=timezone.utc)


def ready_decision(*args, **kwargs):
    return {"status": "READY", "origin_session": "2026-09-14",
            "as_of": NOW.isoformat(), "next_open": "2026-09-15T13:30:00+00:00",
            "duplicates": [], "mode": "PROSPECTIVE", "registration": True,
            "scheduled_at": NOW.isoformat()}


def test_operations_policy_is_schema_validated_and_safety_bounded(tmp_path):
    policy = load_operations_policy()
    assert policy["dashboard"]["bind_host"] == "127.0.0.1"
    assert policy["budgets"]["prospective_attempts_per_role"] == 1
    assert policy["scheduler"]["allow_model_retry"] is False
    bad = deepcopy(policy)
    bad["dashboard"]["bind_host"] = "0.0.0.0"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(Exception):
        load_operations_policy(path)


def test_budget_warns_then_fails_before_excess_work():
    policy = load_operations_policy()
    budget = BudgetLedger(policy, started_at=0)
    budget.consume("source_requests", 175)
    assert budget.snapshot(now_monotonic=0)["metrics"]["source_requests"]["status"] == "WARNING"
    budget.consume("source_requests", 75)
    assert budget.snapshot(now_monotonic=0)["metrics"]["source_requests"]["status"] == "EXHAUSTED"
    with pytest.raises(BudgetExceeded, match="source_requests"):
        budget.consume("source_requests")
    receipt_budget = BudgetLedger(policy, started_at=0)
    receipt_budget.account_receipt({"input_tokens": 100, "output_tokens": 20,
                                    "catalog_cost_estimate_usd": .25})
    assert receipt_budget.used["agent_calls"] == 1
    assert receipt_budget.used["catalog_cost_estimate_usd"] == .25


def test_release_cache_hits_by_identity_paces_and_detects_tampering(tmp_path):
    policy = load_operations_policy()
    budget = BudgetLedger(policy, started_at=0)
    clock = type("Clock", (), {"now": 0.0, "monotonic": lambda self: self.now,
                               "sleep": lambda self, seconds: setattr(self, "now", self.now + seconds)})()
    cache = ReleaseCache(tmp_path, policy, budget, clock.monotonic, clock.sleep)
    calls = []
    first = cache.fetch("completed_close", "alpaca:SPY", "2026-09-14:iex",
                        lambda: calls.append(1) or b"payload", NOW)
    second = cache.fetch("completed_close", "alpaca:SPY", "2026-09-14:iex",
                         lambda: calls.append(2) or b"other", NOW)
    assert first["status"] == "STORED"
    assert second["status"] == "HIT"
    assert second["payload"] == b"payload"
    assert calls == [1]
    assert budget.used["source_requests"] == 1
    Path(first["path"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity"):
        cache.lookup("completed_close", "alpaca:SPY", "2026-09-14:iex", NOW)


def test_ttl_cache_expires_without_calling_stale_data_fresh(tmp_path):
    policy = load_operations_policy()
    cache = ReleaseCache(tmp_path, policy)
    cache.store("intraday_market", "alpaca:SPY", "2026-09-14T20:25:00Z", b"one", NOW)
    assert cache.lookup("intraday_market", "alpaca:SPY", "2026-09-14T20:25:00Z",
                        NOW + timedelta(seconds=60)) is not None
    assert cache.lookup("intraday_market", "alpaca:SPY", "2026-09-14T20:25:00Z",
                        NOW + timedelta(seconds=61)) is None


def test_alerts_are_append_only_deduplicated_and_resolvable(tmp_path):
    ledger = AlertLedger(tmp_path)
    opened = ledger.emit("qqq-holdings-stale", "WARNING", "Refresh QQQ", NOW)
    duplicate = ledger.emit("qqq-holdings-stale", "WARNING", "Refresh QQQ", NOW)
    assert opened["status"] == "OPENED"
    assert duplicate["status"] == "DEDUPLICATED"
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert ledger.resolve("qqq-holdings-stale", NOW + timedelta(minutes=1))["status"] == "RESOLVED"
    assert ledger.open_conditions() == {}
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_operation_attempt_identity_prevents_replacement_and_terminal_mutation(tmp_path):
    ledger = OperationLedger(tmp_path)
    policy_hash = digest({"policy": 1})
    first = ledger.create("PROSPECTIVE", "2026-09-14", ["SPY"], policy_hash, NOW)
    second = ledger.create("PROSPECTIVE", "2026-09-14", ["SPY"], policy_hash, NOW)
    assert first["status"] == "CREATED"
    assert second["status"] == "EXISTING"
    assert first["path"] == second["path"]
    ledger.transition(first["path"], "PREFLIGHT", NOW)
    ledger.transition(first["path"], "BLOCKED", NOW, {"reason": "fixture"})
    with pytest.raises(ValueError, match="terminal"):
        ledger.transition(first["path"], "ACQUIRING", NOW)


def test_scheduler_is_calendar_aware_waits_until_25_minutes_and_detects_duplicate(tmp_path):
    policy = load_operations_policy()
    early = schedule_decision(["SPY"], tmp_path, policy,
                              datetime(2026, 9, 14, 20, 22, tzinfo=timezone.utc))
    assert early["status"] == "WAIT_UNTIL_SCHEDULED"
    assert early["scheduled_at"] == "2026-09-14T20:25:00+00:00"
    ready = schedule_decision(["SPY"], tmp_path, policy, NOW)
    assert ready["status"] == "READY"
    weekend = schedule_decision(["SPY"], tmp_path, policy,
                                datetime(2026, 9, 13, 12, tzinfo=timezone.utc))
    assert weekend["status"] == "READY"
    assert weekend["origin_session"] == "2026-09-11"
    assert weekend["next_open"] == "2026-09-14T13:30:00+00:00"
    forecast = {"version": "meta-observation-v1", "symbols": {
        "SPY": {"status": "ISSUED", "origin_session": "2026-09-14"}}}
    forecast["forecast_hash"] = digest(forecast)
    (tmp_path / "duplicate.json").write_text(json.dumps(forecast))
    assert schedule_decision(["SPY"], tmp_path, policy, NOW)["status"] == "DUPLICATE_ORIGIN"


def test_scheduler_uses_exchange_time_across_dst_and_early_close(tmp_path):
    policy = load_operations_policy()
    after_dst = schedule_decision(["SPY"], tmp_path, policy,
                                  datetime(2026, 11, 2, 21, 25, tzinfo=timezone.utc))
    assert after_dst["status"] == "READY"
    assert after_dst["scheduled_at"] == "2026-11-02T21:25:00+00:00"
    black_friday = schedule_decision(["SPY"], tmp_path, policy,
                                     datetime(2026, 11, 27, 18, 25, tzinfo=timezone.utc))
    assert black_friday["status"] == "READY"
    assert black_friday["scheduled_at"] == "2026-11-27T18:25:00+00:00"


def test_prospective_scheduler_dry_run_writes_nothing(tmp_path):
    result = run_prospective(
        targets=["SPY"], etfs=[], capture_root=tmp_path / "captures",
        analysis_root=tmp_path / "analysis", forecast_root=tmp_path / "forecasts",
        ledger_root=tmp_path / "ledger", alert_root=tmp_path / "alerts",
        operations_policy_path=Path("config/meta-operations-v1.json"), now=NOW)
    assert result["status"] == "DRY_RUN"
    assert result["would_execute"] is True
    assert not (tmp_path / "ledger").exists()


def test_prospective_scheduler_records_all_stages_and_degraded_completion(tmp_path):
    def runner(*args, **kwargs):
        for state in ("ACQUIRING", "VALIDATING", "AGENTS", "FORECASTING", "REGISTERING", "RENDERING"):
            kwargs["operation_callback"](state, {"fixture": True})
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "summary.json").write_text(json.dumps({"run_status": "DEGRADED"}))
        receipt = tmp_path / "receipt.json"
        receipt.write_text("{}")
        return {"product_bundle": str(bundle), "receipt_path": str(receipt)}

    result = run_prospective(
        targets=["SPY"], etfs=[], capture_root=tmp_path / "captures",
        analysis_root=tmp_path / "analysis", forecast_root=tmp_path / "forecasts",
        ledger_root=tmp_path / "ledger", alert_root=tmp_path / "alerts",
        operations_policy_path=Path("config/meta-operations-v1.json"), execute=True,
        runner=runner, decision_fn=ready_decision,
        product_loader=lambda path: json.loads(path.read_text()))
    assert result["status"] == "DEGRADED"
    states = OperationLedger(Path(result["attempt"])).states(Path(result["attempt"]))
    assert [row["state"] for row in states] == [
        "PLANNED", "PREFLIGHT", "ACQUIRING", "VALIDATING", "AGENTS",
        "FORECASTING", "REGISTERING", "RENDERING", "DEGRADED"]
    assert AlertLedger(tmp_path / "alerts").open_conditions()


def test_scheduler_failure_is_visible_and_cannot_be_replaced(tmp_path):
    def failing(*args, **kwargs):
        kwargs["operation_callback"]("ACQUIRING", {})
        raise RuntimeError("network fixture")

    kwargs = dict(
        targets=["SPY"], etfs=[], capture_root=tmp_path / "captures",
        analysis_root=tmp_path / "analysis", forecast_root=tmp_path / "forecasts",
        ledger_root=tmp_path / "ledger", alert_root=tmp_path / "alerts",
        operations_policy_path=Path("config/meta-operations-v1.json"), execute=True,
        runner=failing, decision_fn=ready_decision)
    with pytest.raises(RuntimeError, match="network fixture"):
        run_prospective(**kwargs)
    second = run_prospective(**kwargs)
    assert second["status"] == "ALREADY_TERMINAL"
    assert second["last_state"] == "BLOCKED"
    assert len(AlertLedger(tmp_path / "alerts").open_conditions()) == 1


def test_scheduler_restart_detects_nonterminal_attempt_without_replacement(tmp_path):
    policy = load_operations_policy()
    ledger = OperationLedger(tmp_path / "ledger")
    attempt = ledger.create("PROSPECTIVE", "2026-09-14", ["SPY"], digest(policy), NOW)
    ledger.transition(attempt["path"], "PREFLIGHT", NOW)
    result = run_prospective(
        targets=["SPY"], etfs=[], capture_root=tmp_path / "captures",
        analysis_root=tmp_path / "analysis", forecast_root=tmp_path / "forecasts",
        ledger_root=tmp_path / "ledger", alert_root=tmp_path / "alerts",
        operations_policy_path=Path("config/meta-operations-v1.json"), execute=True,
        runner=lambda *args, **kwargs: pytest.fail("must not create a replacement"),
        decision_fn=ready_decision)
    assert result["status"] == "EXISTING_NONTERMINAL_REQUIRES_RESUME"
    assert len(list((tmp_path / "ledger").glob("attempt-*"))) == 1


def test_operation_state_tampering_is_detected(tmp_path):
    policy_hash = digest({"policy": 1})
    ledger = OperationLedger(tmp_path)
    attempt = ledger.create("PROSPECTIVE", "2026-09-14", ["SPY"], policy_hash, NOW)
    state_path = next((attempt["path"] / "states").glob("*.json"))
    state = json.loads(state_path.read_text())
    state["details"]["hidden"] = True
    state_path.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="integrity"):
        ledger.states(attempt["path"])


def test_outcome_scheduler_defaults_to_no_write_dry_run(tmp_path):
    result = run_outcomes(
        forecast_root=tmp_path / "forecasts", outcome_root=tmp_path / "outcomes",
        score_root=tmp_path / "scores", capture_root=tmp_path / "captures",
        report_root=tmp_path / "reports", ledger_root=tmp_path / "ledger",
        alert_root=tmp_path / "alerts",
        operations_policy_path=Path("config/meta-operations-v1.json"), now=NOW)
    assert result == {"status": "DRY_RUN", "would_execute": True,
                      "as_of": NOW.isoformat(), "writes": False}
    assert not (tmp_path / "ledger").exists()
