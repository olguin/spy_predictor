from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from spy_predictor_quant.cycle1 import run


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "config" / "cycle1.json"
AUDIT = REPO_ROOT / "config" / "cycle1-source-audit-v3.json"


def test_runner_requires_explicit_dataset_only_before_acquisition() -> None:
    called = False

    def builder(**_: Any) -> tuple[Path, dict[str, Any]]:
        nonlocal called
        called = True
        raise AssertionError("dataset builder must not run")

    with pytest.raises(RuntimeError, match="suspended for pre-evaluation repair"):
        run(
            config_path=CONFIG,
            source_audit_path=AUDIT,
            repo_root=REPO_ROOT,
            dataset_builder=builder,
        )
    assert called is False


def test_dataset_only_runner_returns_safe_reproducibility_summary() -> None:
    seen: dict[str, Any] = {}

    def builder(**kwargs: Any) -> tuple[Path, dict[str, Any]]:
        seen.update(kwargs)
        return REPO_ROOT / "datasets/cycle1/example/manifest.json", {
            "datasetVersion": "cycle1-monthly-example",
            "datasetIdentityHash": "d" * 64,
            "tracks": [
                {
                    "trackId": "validation-spy",
                    "role": "ACTUAL_ETF_VALIDATION",
                    "instrument": "SPY",
                    "manifestPath": "datasets/cycle1/example/validation-spy/manifest.json",
                    "datasetIdentityHash": "e" * 64,
                }
            ],
        }

    result = run(
        config_path=CONFIG,
        source_audit_path=AUDIT,
        repo_root=REPO_ROOT,
        offline=True,
        dataset_only=True,
        dataset_builder=builder,
    )

    assert seen["offline"] is True
    assert result["status"] == "dataset-ready"
    assert result["mode"] == "offline"
    assert result["hypothesesEvaluated"] == 0
    assert result["tracks"][0]["instrument"] == "SPY"
    assert "FRED_API_KEY" not in str(result)
    assert "APCA_API_SECRET_KEY" not in str(result)
