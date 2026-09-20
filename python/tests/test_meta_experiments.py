from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pytest

from spy_predictor_quant.market_archive import file_sha256
from spy_predictor_quant.meta_experiments import (
    CANDIDATES, evaluate, fit_predict, paired_block_comparison, preregister,
    run_registered, score_predictions, validate_panel, walk_forward_folds,
)


def protocol():
    value = json.loads((Path(__file__).parents[2] / "config/meta-experiment-protocol-v1.json").read_text())
    return {**value, "minimum_train_origins": 40, "test_origins_per_fold": 30,
            "bootstrap_resamples": 300, "minimum_effective_blocks": 10,
            "final_holdout_start": "2021-01-01T00:00:00Z"}


def panel(n=170):
    rng = np.random.default_rng(31)
    cal = xcals.get_calendar("XNYS")
    sessions = cal.sessions_in_range("2018-01-02", "2020-12-31")
    rows = []
    for index, day in enumerate(sessions[:n]):
        origin = cal.session_close(day).to_pydatetime()
        for symbol in ("SPY", "QQQ"):
            features = {name: float(rng.normal()) for name in
                        ("market_return_pct", "sector_return_pct", "momentum_pct", "quant_score",
                         "event_novelty", "verified_exposure", "claim_disagreement")}
            features["annual_volatility_pct"] = 20
            for horizon in (5, 21, 63):
                end = cal.session_close(sessions[index + horizon]).to_pydatetime()
                rows.append({"symbol": symbol, "origin_at": origin.isoformat(),
                    "horizon_sessions": horizon, "reference_session": day.date().isoformat(), "label_end_at": end.isoformat(),
                    "label_available_at": (end + timedelta(minutes=20)).isoformat(),
                    "feature_available_at": origin.isoformat(), "universe_member_available_at": "2017-01-01T00:00:00Z",
                    "simple_return": float(rng.normal(0, .03)), "features": features,
                    "origin_kind": "PRIOR_COMPLETED_CLOSE", "return_basis": "PRICE_RETURN",
                    "target_contract": "meta-target-v1", "universe_version": "SYNTHETIC_ONLY",
                    "quality_flags": [], "availability_status": "QUALIFIED",
                    "feature_snapshot_hash": "a" * 64})
    return rows


def test_synthetic_leakage_and_mixed_targets_are_rejected():
    rows, config = panel(10), protocol()
    rows[0]["feature_available_at"] = rows[0]["label_end_at"]
    with pytest.raises(ValueError, match="leakage"):
        validate_panel(rows, config)
    rows = panel(10)
    rows[0]["origin_kind"] = "QUALIFIED_CURRENT_TRADE"
    with pytest.raises(ValueError, match="Incompatible"):
        validate_panel(rows, config)


def test_walk_forward_keeps_symbols_together_and_purges_unavailable_labels():
    config = protocol()
    config["final_holdout_start"] = "2018-08-01T00:00:00Z"
    folds = walk_forward_folds(panel(), config, 21)
    assert folds
    for train, test in folds:
        first_test = min(row["origin_at"] for row in test)
        assert all(row["label_available_at"] < first_test for row in train)
        assert {row["symbol"] for row in test} == {"SPY", "QQQ"}
        assert not ({row["origin_at"] for row in train} & {row["origin_at"] for row in test})
        assert all(row["label_available_at"] < config["final_holdout_start"] for row in test)


def test_train_only_transform_and_exact_additive_attribution():
    config = protocol()
    train, test = walk_forward_folds(panel(), config, 5)[-1]
    initial = fit_predict("regularized_quant", train, test, config)
    changed_test = deepcopy(test)
    changed_test[-1]["features"]["momentum_pct"] = 100000
    changed = fit_predict("regularized_quant", train, changed_test, config)
    assert initial[0] == changed[0]  # Test observations do not fit the transform/calibrator.
    for row in initial:
        attribution = row["attribution"]
        assert attribution["intercept"] + sum(attribution["contributions"].values()) == pytest.approx(row["expected_return"])
        assert list(row["return_quantiles"].values()) == sorted(row["return_quantiles"].values())


def test_final_holdout_perturbation_does_not_change_development_results():
    config, rows = protocol(), panel(90)
    config["final_holdout_start"] = "2018-05-01T00:00:00Z"
    first = evaluate(rows, config)
    changed = deepcopy(rows)
    for row in changed:
        if row["origin_at"] >= config["final_holdout_start"]:
            row["simple_return"] = 1000
            row["features"] = {"hindsight": 1000}
    assert evaluate(changed, config) == first
    assert first["promotion_status"] == "NOT_PROMOTED"


def test_null_predictions_cannot_pass_by_count_and_pairing_is_exact():
    config = protocol()
    predictions = [{"symbol": row["symbol"], "origin_at": row["origin_at"], "horizon_sessions": 5,
                    "probability_up": .5, "actual_return": row["simple_return"]}
                   for row in panel(150) if row["horizon_sessions"] == 5]
    result = paired_block_comparison(predictions, predictions, 5, config)
    assert result["confidence_interval"] == [0, 0]
    assert result["status"] == "INCONCLUSIVE_OR_NO_MATERIAL_IMPROVEMENT"
    with pytest.raises(ValueError, match="same unique observations"):
        paired_block_comparison(predictions[:-1], predictions, 5, config)
    small = paired_block_comparison(predictions[:15], predictions[:15], 5, config)
    assert small["status"] == "INCONCLUSIVE" and small["effective_blocks"] < 2


def test_registration_and_failure_ledger_are_append_only(tmp_path):
    data = tmp_path / "panel.json"
    data.write_text("[]")
    manifest = {"schema_version": "meta-research-panel-manifest-v1",
                "research_track": "IMPROVEMENT_PLAN_3_NEW_COHORT", "panel_sha256": file_sha256(data)}
    registration = preregister(tmp_path, protocol(), manifest)
    before = registration.read_bytes()
    with pytest.raises(FileExistsError):
        preregister(tmp_path, protocol(), manifest)
    with pytest.raises(ValueError, match="audits are required"):
        run_registered(tmp_path, data)
    assert registration.read_bytes() == before
    assert len(list((tmp_path / "trials").glob("*/failed.json"))) == 1
    assert len(list((tmp_path / "trials").glob("*/started.json"))) == 1


def test_shuffled_label_control_does_not_establish_agent_edge():
    rows = panel(170)
    labels = np.array([row["simple_return"] for row in rows])
    np.random.default_rng(916).shuffle(labels)
    for row, label in zip(rows, labels):
        row["simple_return"] = float(label)
    result = evaluate(rows, protocol())
    assert result["promotion_status"] == "NOT_PROMOTED"
    assert all(value["development_gate"] == "INCONCLUSIVE_OR_FAILED" for value in result["horizons"].values())
    assert result["horizons"]["5"]["metrics"]["quant_plus_agent"]["count"] > 0


def test_quant_only_protocol_does_not_require_agent_history_and_preserves_pairing():
    config = protocol()
    config.update(schema_version="meta-experiment-protocol-v2", challenger="regularized_quant")
    config["candidates"].remove("quant_plus_agent")
    agent_features = config["feature_groups"].pop("agent")
    rows = panel(170)
    for row in rows:
        for name in agent_features:
            row["features"].pop(name, None)
    result = evaluate(rows, config)
    horizon = result["horizons"]["5"]
    assert "quant_plus_agent" not in horizon["metrics"]
    assert horizon["metrics"]["regularized_quant"]["count"] > 0
    assert len({v["count"] for v in horizon["metrics"].values()}) == 1
    assert result["promotion_status"] == "NOT_PROMOTED"


def test_feasibility_reads_metadata_only_and_cannot_invent_long_horizon_power():
    from spy_predictor_quant.meta_experiments import feasibility
    rows, config = panel(170), protocol()
    first = feasibility(rows, config)
    for row in rows:
        del row["simple_return"]
        del row["features"]
    assert feasibility(rows, config) == first
    assert first["outcomes_inspected"] is False
    assert first["horizons"]["63"]["status"] == "INCONCLUSIVE_INSUFFICIENT_BLOCKS"


def test_diagnostic_prices_never_pass_qualified_gate():
    config = protocol()
    config.update(schema_version="meta-experiment-protocol-v2", challenger="regularized_quant", research_mode="DIAGNOSTIC_REVISED_PRICES")
    config["candidates"].remove("quant_plus_agent")
    rows = panel(150)
    with pytest.raises(ValueError, match="unqualified"):
        evaluate(rows, config)
    for row in rows:
        row.update(availability_status="REVISED_HISTORY_DIAGNOSTIC", quality_flags=["HISTORICAL_PRICE_VINTAGE_UNVERIFIED"])
    result = evaluate(rows, config)
    assert all(h["development_gate"] == "DISABLED_UNQUALIFIED_PRICE_VINTAGES" for h in result["horizons"].values())
