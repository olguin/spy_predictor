from __future__ import annotations

import math
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from spy_predictor_quant.phase1_config import load_phase1_plan, mapping_for_session
from spy_predictor_quant.historical_http import RequestLimiter, capture_pages
from spy_predictor_quant.phase1_tournament import build_phase1_observations
from spy_predictor_quant.phase1_tournament import evaluate_phase1_candidate
from spy_predictor_quant.tournament import Bar, Observation


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_archived_pages_are_reused_without_network(tmp_path: Path) -> None:
    request_url = "https://example.test/bars?symbol=SPY"
    payload = {"bars": [{"t": "2026-09-03T13:30:00Z"}], "next_page_token": None}
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    raw_path = tmp_path / "page-0000.json"
    raw_path.write_bytes(encoded)
    metadata = {
        "schemaVersion": "archived-http-page-v1",
        "provider": "fixture",
        "page": 0,
        "requestUrl": request_url,
        "httpStatus": 200,
        "receivedAt": "2026-09-05T00:00:00+00:00",
        "records": 1,
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }
    (tmp_path / "page-0000.meta.json").write_text(json.dumps(metadata))
    pages, records = capture_pages(
        provider="fixture",
        initial_url=request_url,
        raw_directory=tmp_path,
        headers={},
        limiter=RequestLimiter(5),
        next_url=lambda document, _url: document.get("next_page_token"),
        extract_records=lambda document: document["bars"],
        allow_network=False,
    )
    assert len(pages) == 1
    assert records == payload["bars"]


def test_archived_page_parser_migration_uses_hash_linked_sidecar(
    tmp_path: Path,
) -> None:
    request_url = "https://example.test/actions"
    payload = {"group": [{"x": 1}]}
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    raw_path = tmp_path / "page-0000.json"
    raw_path.write_bytes(encoded)
    metadata_path = tmp_path / "page-0000.meta.json"
    metadata = {
        "schemaVersion": "archived-http-page-v1",
        "provider": "fixture",
        "page": 0,
        "requestUrl": request_url,
        "httpStatus": 200,
        "receivedAt": "2026-09-05T00:00:00+00:00",
        "records": 0,
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }
    metadata_path.write_text(json.dumps(metadata))

    pages, records = capture_pages(
        provider="fixture",
        initial_url=request_url,
        raw_directory=tmp_path,
        headers={},
        limiter=RequestLimiter(5),
        next_url=lambda _document, _url: None,
        extract_records=lambda document: document["group"],
        allow_network=False,
        record_extraction_version="grouped-v2",
    )

    assert records == [{"x": 1}]
    assert pages[0].records == 1
    assert json.loads(metadata_path.read_text())["records"] == 0
    sidecar = tmp_path / "page-0000.extraction-grouped-v2.meta.json"
    migrated = json.loads(sidecar.read_text())
    assert migrated["records"] == 1
    assert migrated["baseMetadataSha256"] == hashlib.sha256(
        metadata_path.read_bytes()
    ).hexdigest()


def test_phase1_plan_has_contiguous_explicit_rolls() -> None:
    plan = load_phase1_plan(REPO_ROOT / "config" / "phase1.json")
    assert plan.start_date.isoformat() == "2024-09-03"
    assert plan.end_date.isoformat() == "2026-09-03"
    assert len(plan.roll_mappings["ES"]) == 9
    assert len(plan.roll_mappings["NQ"]) == 9
    selected = mapping_for_session(
        plan.roll_mappings["ES"],
        datetime.fromisoformat("2025-09-11").date(),
    )
    assert selected is not None
    assert selected.ticker == "ESZ5"


def test_phase1_target_semantics_use_completed_minute_and_exclude_rolls() -> None:
    timezone = ZoneInfo("America/New_York")
    bars: list[Bar] = []
    session = datetime(2026, 6, 8, 9, 30, tzinfo=timezone)
    created = 0
    while created < 8:
        if session.weekday() < 5:
            contract = "ESM6" if created < 4 else "ESU6"
            base = 6000 + created * 10
            for minute in range(390):
                timestamp = session + timedelta(minutes=minute)
                close = base + minute / 100
                bars.append(
                    Bar(
                        "ES",
                        timestamp,
                        base if minute == 0 else close - 0.01,
                        close + 0.02,
                        close - 0.02,
                        close,
                        100,
                        contract,
                        session.date().isoformat(),
                    )
                )
            created += 1
        session = (session + timedelta(days=1)).replace(hour=9, minute=30)

    config = {
        "horizons": [
            "open-15m",
            "open-30m",
            "open-60m",
            "previous-close-next-open",
            "open-close",
            "close-next-close",
        ],
        "neutralThreshold": 0.0005,
    }
    observations, coverage = build_phase1_observations("ES", bars, config)
    first = next(item for item in observations if item.horizon == "open-30m")
    expected = math.log((6010 + 29 / 100) / (6010 + 0 / 100))
    assert first.target_return == expected
    roll_date = sorted({bar.session_date for bar in bars})[4]
    assert not any(item.date == roll_date for item in observations)
    assert coverage["open-30m"]["percent"] == 100.0


def test_candidate_reports_every_preregistered_gate() -> None:
    observations: list[Observation] = []
    start = datetime(2025, 1, 2)
    for index in range(70):
        value = ((index % 5) - 2) * 0.0006
        label = "UP" if value > 0.0005 else "DOWN" if value < -0.0005 else "NEUTRAL"
        observations.append(
            Observation(
                "SPY",
                "open-30m",
                (start + timedelta(days=index)).date().isoformat(),
                value,
                label,
                abs(value),
                (value / 2, -value, abs(value), 0.001),
            )
        )
    config = {
        "minimumTrainingObservations": 20,
        "rollingWindow": 30,
        "confirmationObservations": 20,
        "minimumConfirmationObservations": 20,
        "minimumCoveragePercent": 95,
        "randomSeed": 42,
        "transactionCostBps": {"SPY": 1.0},
        "stressCostMultiplier": 2,
        "promotion": {
            "minimumBrierImprovement": 0,
            "minimumIncrementalNetReturn": 0.001,
            "maximumExpectedCalibrationError": 0.2,
            "maximumCalibrationDegradation": 0.02,
            "requirePositiveNetReturn": True,
            "requirePositiveStressNetReturn": True,
            "requireBothWalkForwardModes": True,
            "requireBothConfirmationHalves": True,
            "eligibleModels": [
                "overnight-continuation",
                "overnight-reversal",
                "momentum",
                "mean-reversion",
                "logistic-l2",
                "tree-depth-3",
            ],
        },
    }
    result = evaluate_phase1_candidate(
        observations,
        {"expected": 70, "observed": 70, "missingSample": [], "percent": 100.0},
        config,
        {
            "provenance": {"targetSelectionAdmissible": True},
            "quality": {"SPY": {"medianSessionVolume": 1_000_000}},
        },
        {"gates": {"SPY": {"passed": True}}},
    )
    gates = result["promotion"]["gates"]
    assert set(gates) == {
        "provenance",
        "sample",
        "coverage",
        "crossProvider",
        "liquidity",
        "forecastImprovement",
        "selectionForecastImprovement",
        "calibration",
        "stability",
        "economicValue",
        "costSensitivity",
    }
    champion = result["promotion"]["championModelSelectedOnSelectionOnly"]
    assert result["evaluation"]["expanding"]["directional"][champion][
        "confirmation"
    ]["observations"] == 20
