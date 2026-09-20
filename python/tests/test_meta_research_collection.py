from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from spy_predictor_quant.meta_research_collection import prepare, validate_config


def config():
    return json.loads(Path("config/meta-research-collection-v1.json").read_text())


def test_collection_cannot_write_closed_cohorts_or_forecast_ledgers():
    value = config()
    for path in ("datasets/meta-observation/forecasts", "datasets/cycle1", "datasets/meta-research/../../outside"):
        value["store_root"] = path
        with pytest.raises(ValueError, match="cannot write"):
            validate_config(value)


def test_collection_preparation_uses_exchange_close_and_never_issues_forecasts():
    # Friday following Thanksgiving: XNYS closes at 13:00 Eastern.
    result = prepare(config(), datetime(2026, 11, 27, 17, tzinfo=timezone.utc))
    assert result["next_completed_close_collection_at"] == "2026-11-27T18:20:00+00:00"
    assert result["writes"] is False
    assert result["forecast_registration"] is False
    assert result["scheduler_installed"] is False
    with pytest.raises(ValueError, match="timezone"):
        prepare(config(), datetime(2026, 11, 27, 17))


def test_empty_collection_is_visible_to_shell_automation(monkeypatch, capsys):
    import sys
    from spy_predictor_quant import meta_research_collection as module
    monkeypatch.setattr(sys, "argv", ["collection", "collect"])
    monkeypatch.setattr(module, "collect", lambda *args: {"status": "NO_QUALIFIED_NUMERIC_OBSERVATIONS"})
    assert module.main() == 2
    assert "NO_QUALIFIED_NUMERIC_OBSERVATIONS" in capsys.readouterr().out
