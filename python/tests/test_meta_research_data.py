from copy import deepcopy
import json

import pytest

from spy_predictor_quant.meta_analysis import digest
from spy_predictor_quant.meta_research_data import (
    append_observation, as_of, coverage_audit, freeze_features, load_observations,
    ingest_packet, quarterly_flows, release_surprise, trailing_four_quarters, validate_observation,
)


def observation(**kwargs):
    row = {"schema_version": "meta-pit-observation-v1", "entity": "SPY", "metric": "revenue",
           "value": 100, "units": "USD", "source_version": "source-v1", "revision_id": "original",
           "source_hash": "a" * 64, "quality_flags": [],
           "period_start": "2026-01-01", "period_end": "2026-03-31",
           "effective_at": "2026-03-31T20:00:00Z", "published_at": "2026-04-20T20:30:00Z",
           "first_seen_at": "2026-04-20T20:31:00Z", "available_at": "2026-04-20T20:31:00Z",
           "captured_at": "2026-04-20T20:31:00Z"}
    row.update(kwargs)
    return row


def test_revision_after_close_and_unknown_availability_cannot_rewrite_frozen_features(tmp_path):
    first = append_observation(tmp_path, observation())
    original = first.read_bytes()
    registry = {"schema_version": "meta-feature-registry-v1", "features": [{"entity": "SPY",
                "name": "revenue", "inputs": ["revenue"], "input_units": ["USD"],
                "formula": "LATEST", "units": "USD"}]}
    assert not as_of(load_observations(tmp_path), "2026-04-20T20:00:00Z")
    frozen = freeze_features(tmp_path, "2026-04-21T13:00:00Z", registry)
    frozen_bytes = frozen.read_bytes()
    append_observation(tmp_path, observation(value=500, revision_id="amended",
        published_at="2026-05-01T20:00:00Z", first_seen_at="2026-05-01T20:01:00Z",
        available_at="2026-05-01T20:01:00Z", captured_at="2026-05-01T20:01:00Z"))
    append_observation(tmp_path, observation(value=900, revision_id="unknown", available_at=None))
    assert first.read_bytes() == original and frozen.read_bytes() == frozen_bytes
    assert as_of(load_observations(tmp_path), "2026-04-21T13:00:00Z")[0]["value"] == 100
    assert as_of(load_observations(tmp_path), "2026-05-02T13:00:00Z")[0]["value"] == 500
    assert coverage_audit(tmp_path)["unknown_availability_records"] == 1
    with pytest.raises(FileExistsError):
        freeze_features(tmp_path, "2026-04-21T13:00:00Z", registry)


def test_share_bases_and_ytd_quarter_reconstruction_do_not_mix_splits(tmp_path):
    for end, value in [("2026-03-31", 100), ("2026-06-30", 230), ("2026-09-30", 380), ("2026-12-31", 550)]:
        append_observation(tmp_path, observation(period_end=end, value=value,
            effective_at=end + "T20:00:00Z", published_at="2027-02-01T21:00:00Z",
            first_seen_at="2027-02-01T21:01:00Z", available_at="2027-02-01T21:01:00Z",
            captured_at="2027-02-01T21:01:00Z", share_basis="UNADJUSTED"))
    rows = load_observations(tmp_path)
    quarters = quarterly_flows(rows, "2027-02-02T00:00:00Z", "2026-01-01")
    assert [r["value"] for r in quarters] == [100, 130, 150, 170]
    assert trailing_four_quarters(quarters)["value"] == 550
    assert trailing_four_quarters(quarters[:3])["status"] == "MISSING"
    rows[-1]["share_basis"] = "SPLIT_ADJUSTED"
    with pytest.raises(ValueError, match="share basis"):
        quarterly_flows(rows, "2027-02-02T00:00:00Z", "2026-01-01")


def test_surprise_requires_pre_release_expectations_and_comparable_units():
    actual = observation(record_hash="actual")
    assert release_surprise(actual, None)["status"] == "MISSING"
    expected = observation(value=90, record_hash="expected", published_at="2026-04-19T20:00:00Z",
                           first_seen_at="2026-04-19T20:01:00Z", available_at="2026-04-19T20:01:00Z",
                           captured_at="2026-04-19T20:01:00Z")
    assert release_surprise(actual, expected)["value"] == 10
    with pytest.raises(ValueError, match="before the release"):
        release_surprise(actual, observation(record_hash="late"))
    with pytest.raises(ValueError):
        release_surprise(actual, {**expected, "units": "USD/share"})


def test_temporal_and_integrity_defects_fail_closed(tmp_path):
    with pytest.raises(ValueError, match="timing"):
        validate_observation(observation(available_at="2026-04-19T20:00:00Z"))
    with pytest.raises(ValueError, match="timezone"):
        validate_observation(observation(published_at="2026-04-20T20:30:00"))
    path = append_observation(tmp_path, observation())
    row = json.loads(path.read_text())
    row["value"] = 999
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="integrity"):
        load_observations(tmp_path)


def test_imported_archival_packet_does_not_backdate_first_seen_or_duplicate_records(tmp_path):
    packet = {"version": "meta-analysis-v1", "as_of": "2020-09-14T20:00:00Z",
              "instruments": {"SPY": {"status": "FRESH", "latest_close": 100, "price_date": "2020-09-14"}}}
    packet["packet_hash"] = digest(packet)
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(packet))
    first = ingest_packet(tmp_path, path)
    assert ingest_packet(tmp_path, path) == first
    rows = load_observations(tmp_path)
    assert len(rows) == 1
    assert not as_of(rows, "2020-09-15T00:00:00Z")
    assert rows[0]["first_seen_at"] > "2020-09-15"


def test_reconstructed_vintage_is_separate_and_preserves_actual_retrieval(tmp_path):
    from spy_predictor_quant.meta_research_sources import reconstructed
    row = reconstructed(entity="CPI", metric="level", value=100, units="index",
        effective="2026-01-01T00:00:00Z", published="2026-02-14T05:00:00Z",
        available="2026-02-14T05:00:00Z", captured="2026-09-16T12:00:00Z",
        source_hash="a" * 64, kind="ALFRED_VINTAGE", locator="2026-01/2026-02-13", revision="initial")
    append_observation(tmp_path, row)
    rows = load_observations(tmp_path)
    assert not as_of(rows, "2026-03-01T00:00:00Z")
    assert not as_of(rows, "2026-02-14T04:59:00Z", lane="HISTORICAL_RECONSTRUCTION")
    assert as_of(rows, "2026-03-01T00:00:00Z", lane="HISTORICAL_RECONSTRUCTION")[0]["first_seen_at"] == row["captured_at"]
    revised = deepcopy(row)
    revised.update(value=200, revision_id="revision", published_at="2026-04-01T04:00:00Z", available_at="2026-04-01T04:00:00Z")
    revised["availability_evidence"]["available_at"] = revised["available_at"]
    append_observation(tmp_path, revised)
    assert as_of(load_observations(tmp_path), "2026-03-01T00:00:00Z", lane="HISTORICAL_RECONSTRUCTION")[0]["value"] == 100
    with pytest.raises(ValueError, match="evidence"):
        validate_observation({**row, "availability_evidence": {}})
    with pytest.raises(ValueError, match="Unknown availability lane"):
        as_of(rows, "2026-03-01T00:00:00Z", lane="typo")
