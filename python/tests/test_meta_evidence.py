from datetime import datetime, timezone

import pytest

from spy_predictor_quant.meta_evidence import (
    company_fundamentals, etf_overlap, exposure_news_symbols, parse_holdings_csv,
    recent_filings, sec_ticker_map,
)

CUTOFF = datetime(2026, 9, 10, tzinfo=timezone.utc)


def submissions():
    return {"cik": "320193", "name": "Apple Inc.", "sic": "3571", "sicDescription": "Electronic Computers",
            "filings": {"recent": {
                "accessionNumber": ["0000320193-26-000100", "0000320193-26-000090", "0000320193-26-000080", "0000320193-26-000070"],
                "filingDate": ["2026-08-01", "2026-07-25", "2025-10-31", "2026-09-11"],
                "reportDate": ["2026-07-31", "2026-07-20", "2025-09-30", "2026-09-10"],
                "acceptanceDateTime": ["2026-08-01T12:00:00.000Z", "2026-07-25T12:00:00.000Z", "2025-10-31T12:00:00.000Z", "2026-09-11T12:00:00.000Z"],
                "form": ["10-Q", "8-K", "10-K", "8-K"],
                "primaryDocument": ["aapl-20260731.htm", "event.htm", "aapl-20250930.htm", "future.htm"]}}}


def companyfacts():
    def concept(label, observations, unit="USD"):
        return {"label": label, "units": {unit: observations}}
    return {"cik": 320193, "entityName": "Apple Inc.", "facts": {"us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": concept("Revenue", [
            {"val": 100, "start": "2026-05-01", "end": "2026-07-31", "filed": "2026-08-01", "form": "10-Q", "fy": 2026, "fp": "Q3", "accn": "0000320193-26-000100"},
            {"val": 999, "start": "2026-08-01", "end": "2026-10-31", "filed": "2026-09-11", "form": "10-Q", "fy": 2026, "fp": "Q4", "accn": "future"}],
        ),
        "OperatingIncomeLoss": concept("Operating income", [
            {"val": 25, "start": "2026-05-01", "end": "2026-07-31", "filed": "2026-08-01", "form": "10-Q", "fy": 2026, "fp": "Q3", "accn": "0000320193-26-000100"}]),
        "Assets": concept("Assets", [
            {"val": 500, "end": "2026-07-31", "filed": "2026-08-01", "form": "10-Q", "fy": 2026, "fp": "Q3", "accn": "0000320193-26-000100"}]),
        "EarningsPerShareDiluted": concept("EPS", [
            {"val": 1.5, "start": "2026-05-01", "end": "2026-07-31", "filed": "2026-08-01", "form": "10-Q", "fy": 2026, "fp": "Q3", "accn": "0000320193-26-000100"}], "USD/shares"),
    }}}


def test_sec_identity_filings_cutoff_and_fundamental_period_matching():
    mapping = sec_ticker_map({"0": {"cik_str": 320193, "ticker": "aapl", "title": "Apple Inc."}})
    assert mapping["AAPL"]["cik"] == "0000320193"
    filings = recent_filings(submissions(), "AAPL", CUTOFF)
    assert [r["form"] for r in filings["periodic"]] == ["10-Q", "10-K"]
    assert [r["form"] for r in filings["recent_events"]] == ["8-K"]
    assert filings["periodic"][0]["url"].endswith("/aapl-20260731.htm")
    profile = company_fundamentals(companyfacts(), "AAPL", CUTOFF, filings)
    assert profile["metrics"]["revenue"]["value"] == 100
    assert profile["metrics"]["assets"]["value"] == 500
    assert profile["metrics"]["diluted_eps"]["unit"] == "USD/shares"
    assert profile["derived"]["operating_margin_pct"] == 25
    assert "market-derived valuation multiple" in profile["limitations"][2]


def test_companyfacts_must_match_submissions_identity_and_accession():
    filings = recent_filings(submissions(), "AAPL", CUTOFF)
    wrong = companyfacts()
    wrong["cik"] = 1
    with pytest.raises(ValueError, match="identity mismatch"):
        company_fundamentals(wrong, "AAPL", CUTOFF, filings)
    unlinked = companyfacts()
    unlinked["facts"]["us-gaap"]["Assets"]["units"]["USD"][0]["accn"] = "unseen"
    assert "assets" not in company_fundamentals(unlinked, "AAPL", CUTOFF, filings)["metrics"]


def test_companyfacts_does_not_divide_different_periods():
    payload = companyfacts()
    observation = payload["facts"]["us-gaap"]["OperatingIncomeLoss"]["units"]["USD"][0]
    observation["start"] = "2025-08-01"
    profile = company_fundamentals(payload, "AAPL", CUTOFF, recent_filings(submissions(), "AAPL", CUTOFF))
    assert "operating_margin_pct" not in profile["derived"]


def test_holdings_profiles_exposure_expansion_and_overlap():
    left = parse_holdings_csv(
        b"as_of,source_url,ticker,name,weight_pct,sector\n2026-09-09,https://sponsor.test/spy,NVDA,Nvidia,8,Technology\n2026-09-09,https://sponsor.test/spy,AAPL,Apple,7,Technology\n",
        "SPY", CUTOFF)
    right = parse_holdings_csv(
        b"as_of,source_url,ticker,name,weight_pct,sector\n2026-09-09,https://sponsor.test/qqq,NVDA,Nvidia,9,Technology\n2026-09-09,https://sponsor.test/qqq,MSFT,Microsoft,8,Technology\n",
        "QQQ", CUTOFF)
    symbols, mapping = exposure_news_symbols({"SPY": left, "QQQ": right})
    assert symbols[0] == "NVDA"
    assert mapping["NVDA"] == {"SPY": 8, "QQQ": 9}
    overlap = etf_overlap(left, right)
    assert overlap["overlap_min_weight_pct"] == 8
    assert overlap["common_holdings"][0]["ticker"] == "NVDA"


@pytest.mark.parametrize("raw", [
    b"ticker,name,weight_pct\nAAPL,Apple,5\n",
    b"as_of,source_url,ticker,name,weight_pct\n2026-09-11,https://sponsor.test,AAPL,Apple,5\n",
    b"as_of,source_url,ticker,name,weight_pct\n2026-09-09,https://sponsor.test,AAPL,Apple,60\n2026-09-09,https://sponsor.test,MSFT,Microsoft,60\n",
    b"as_of,source_url,ticker,name,weight_pct\n2026-09-09,https://sponsor.test,AAPL,Apple,5\n2026-09-09,https://sponsor.test,AAPL,Apple,4\n",
])
def test_invalid_holdings_fail_closed(raw):
    with pytest.raises(ValueError):
        parse_holdings_csv(raw, "SPY", CUTOFF)
