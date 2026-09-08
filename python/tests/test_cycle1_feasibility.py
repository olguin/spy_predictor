from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from spy_predictor_quant.cycle1_calendar import xnys_month_end, xnys_session_close
from spy_predictor_quant.cycle1_feasibility import (
    audit_dataset, confirmation_start_feasibility, selection_feasibility,
)
from spy_predictor_quant.cycle1_config import load_cycle1_plan


def _rows(count: int) -> list[dict]:
    rows = []
    for index in range(count):
        year, month = 2006 + index // 12, index % 12 + 1
        snapshot = xnys_month_end(year, month)
        endpoint = xnys_month_end(year + 1, month)
        release_year, release_month = (year + 2, 1) if month == 12 else (year + 1, month + 1)
        rows.append({
            "snapshotDate": snapshot.isoformat(),
            "snapshotCutoff": xnys_session_close(snapshot).isoformat(),
            "targetEndDate": endpoint.isoformat(),
            "labelAvailableAt": f"{release_year:04d}-{release_month:02d}-15T23:59:59+00:00",
        })
    return rows


CONFIG = {"modes": ["expanding", "rolling"], "rollingWindowMonths": 180, "minimumTrainingMonths": 120}


def test_126_selection_rows_cannot_train_120_matured_annual_labels() -> None:
    rows = _rows(126)
    result = selection_feasibility(rows, {"start": rows[0]["snapshotDate"], "end": rows[-1]["snapshotDate"]}, CONFIG)
    assert result["status"] == "NO_SELECTION_FORECASTS"
    for mode in result["modes"].values():
        assert mode["eligibleForecasts"] == 0
        assert mode["maximumMaturedTrainingLabels"] == 113


def test_200_selection_rows_provide_68_forecasts_and_ignore_confirmation_rows() -> None:
    rows = _rows(240)
    selection = {"start": rows[0]["snapshotDate"], "end": rows[199]["snapshotDate"]}
    full = selection_feasibility(rows, selection, CONFIG)
    assert full == selection_feasibility(rows[:200], selection, CONFIG)
    assert full["modes"]["expanding"]["eligibleForecasts"] == 68
    assert full["modes"]["rolling"]["eligibleForecasts"] == 68
    assert full["modes"]["rolling"]["maximumMaturedTrainingLabels"] == 167


def test_delayed_publication_and_calendar_rolling_window_reduce_eligible_training() -> None:
    rows = _rows(200)
    selection = {"start": rows[0]["snapshotDate"], "end": rows[-1]["snapshotDate"]}
    for row in rows:
        row["labelAvailableAt"] = "2099-01-01T00:00:00+00:00"
    result = selection_feasibility(rows, selection, CONFIG)
    assert result["modes"]["expanding"]["eligibleForecasts"] == 0
    assert result["modes"]["rolling"]["maximumMaturedTrainingLabels"] == 0


def test_external_transfer_can_start_when_selection_labels_mature_by_confirmation() -> None:
    rows = _rows(222)
    selection = {"start": rows[0]["snapshotDate"], "end": rows[125]["snapshotDate"]}
    confirmation = {"start": rows[138]["snapshotDate"]}
    result = confirmation_start_feasibility(rows, selection, confirmation, 120)
    assert result["matureSelectionLabelsAtStart"] == 126
    assert result["status"] == "FEASIBLE"


def test_audit_is_reproducible_ignores_confirmation_values_and_checks_hashes(tmp_path: Path) -> None:
    config = Path(__file__).resolve().parents[2] / "config/cycle1.json"
    plan = load_cycle1_plan(config)
    rows = _rows(126)
    selection = {"start": rows[0]["snapshotDate"], "end": rows[-1]["snapshotDate"]}
    # A confirmation record deliberately has no numeric outcomes or metadata
    # beyond its date. The audit must not attempt to score or train on it.
    rows.append({
        "snapshotDate": "2017-07-31",
        "snapshotCutoff": "2017-07-31T20:00:00+00:00",
        "targetEndDate": "2018-07-31",
        "labelAvailableAt": "2018-08-15T23:59:59+00:00",
        "forbiddenOutcome": "sentinel",
    })
    macro = [{"seriesId": "DGS3MO", "observationDate": "2005-06-01", "availableAt": "2005-06-28T23:59:59+00:00", "realtimeStart": "2005-06-28", "value": 2.0, "missing": False}]
    artifacts = []
    for kind, values in (("targets", rows), ("macro-vintages", macro)):
        data = "".join(json.dumps(row) + "\n" for row in values).encode()
        (tmp_path / f"{kind}.ndjson").write_bytes(data)
        artifacts.append({"kind": kind, "path": f"{kind}.ndjson", "sha256": hashlib.sha256(data).hexdigest(), "records": len(values)})
    track = {"preregistrationHash": plan.config_hash, "datasetIdentityHash": "a" * 64, "instrument": "QQQ", "evidenceTier": "RECONSTRUCTED_RESEARCH_ONLY", "normalizedArtifacts": artifacts, "resolvedPartitions": {"selection": selection, "confirmation": {"start": "2017-07-31"}}}
    data = json.dumps(track).encode()
    (tmp_path / "track.json").write_bytes(data)
    manifest = {"datasetVersion": "cycle1-monthly-19ccd95384e690de", "preregistrationHash": plan.config_hash, "tracks": [{"role": "ACTUAL_ETF_VALIDATION", "manifestPath": "track.json", "manifestSha256": hashlib.sha256(data).hexdigest(), "datasetIdentityHash": "a" * 64}]}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    report = audit_dataset(tmp_path, path, config)
    assert report == audit_dataset(tmp_path, path, config)
    assert report["tracks"][0]["archivedSelection"]["selectionRows"] == 126
    assert report["candidateMetricsComputed"] is False
    assert "sentinel" not in json.dumps(report)
    (tmp_path / "macro-vintages.ndjson").write_text("corrupt")
    with pytest.raises(ValueError, match="Artifact hash mismatch"):
        audit_dataset(tmp_path, path, config)
