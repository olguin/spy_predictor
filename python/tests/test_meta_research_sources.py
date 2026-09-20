from copy import deepcopy

import pytest

from spy_predictor_quant.meta_research_data import as_of
from spy_predictor_quant.meta_research_sources import alfred_observations, next_day, sec_observations


def test_alfred_revisions_date_precision_missing_values_and_latest_only_rejected():
    payload = {"output_type": 1, "units": "lin", "observations": [
        {"date": "2026-01-01", "realtime_start": "2026-02-13", "value": "100"},
        {"date": "2026-01-01", "realtime_start": "2026-03-13", "value": "101"},
        {"date": "2026-02-01", "realtime_start": "2026-03-13", "value": "."}]}
    rows = alfred_observations(payload, "CPI", "index", "2026-09-16T12:00:00Z", "a" * 64)
    assert len(rows) == 2
    assert not as_of(rows, "2026-02-13T23:59:00-05:00", lane="HISTORICAL_RECONSTRUCTION")
    assert as_of(rows, "2026-02-14T05:00:00Z", lane="HISTORICAL_RECONSTRUCTION")[0]["value"] == 100
    assert as_of(rows, "2026-04-01T00:00:00Z", lane="HISTORICAL_RECONSTRUCTION")[0]["value"] == 101
    assert next_day("2026-03-08") == "2026-03-09T04:00:00+00:00"
    with pytest.raises(ValueError, match="untransformed"):
        alfred_observations({**payload, "output_type": 4}, "CPI", "index", "2026-09-16T12:00:00Z", "a" * 64)


def bundle():
    return {"submissions": {"cik": "1", "filings": {"recent": {
        "accessionNumber": ["original", "amendment"], "acceptanceDateTime": ["2026-04-20T20:30:00Z", "2026-05-01T12:00:00Z"],
        "filingDate": ["2026-04-20", "2026-05-01"], "form": ["10-Q", "10-Q/A"]}}},
        "companyfacts": {"cik": 1, "facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            {"accn": "original", "filed": "2026-04-20", "form": "10-Q", "start": "2026-01-01", "end": "2026-03-31", "val": 100},
            {"accn": "amendment", "filed": "2026-05-01", "form": "10-Q/A", "start": "2026-01-01", "end": "2026-03-31", "val": 150},
            {"accn": "unknown", "filed": "2026-06-01", "form": "10-Q", "end": "2026-03-31", "val": 999}]}}}}}}


def test_sec_joins_accession_and_retains_amendments_unknown_acceptance_and_conflicts():
    payload = bundle()
    rows, audit = sec_observations(payload, "TEST", "2026-09-16T12:00:00Z", "a" * 64)
    assert audit["unmatched_accession_facts"] == 1
    assert as_of(rows, "2026-04-22T00:00:00Z", lane="HISTORICAL_RECONSTRUCTION")[0]["value"] == 100
    assert as_of(rows, "2026-05-03T00:00:00Z", lane="HISTORICAL_RECONSTRUCTION")[0]["value"] == 150
    facts = payload["companyfacts"]["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    facts.append({**facts[0], "val": 666})
    rows, audit = sec_observations(payload, "TEST", "2026-09-16T12:00:00Z", "a" * 64)
    assert audit["conflicting_facts"] == 1
    assert not as_of(rows, "2026-04-22T00:00:00Z", lane="HISTORICAL_RECONSTRUCTION")
    payload = bundle()
    payload["companyfacts"]["cik"] = 2
    with pytest.raises(ValueError, match="CIK"):
        sec_observations(payload, "TEST", "2026-09-16T12:00:00Z", "a" * 64)
