from datetime import datetime, timezone

import pytest

from spy_predictor_quant.meta_evidence import (
    company_fundamentals, company_market_valuation, etf_overlap, etf_quality_valuation,
    exposure_news_symbols, geopolitical_transmission_coverage, instrument_evidence_profile,
    parse_etf_profile, parse_holdings_csv, primary_source_evidence, recent_filings,
    sec_ticker_map, validate_primary_source_config,
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


def test_primary_rss_is_cutoff_filtered_scoped_and_replayable():
    definition = {
        "id": "issuer-events", "publisher": "Issuer", "kind": "issuer_event",
        "format": "rss_atom", "url": "https://issuer.test/events.xml",
        "publisher_domains": ["issuer.test"], "symbols": ["NVDA"], "maximum_items": 10,
    }
    validate_primary_source_config({"version": "meta-primary-sources-v1", "sources": [definition]})
    raw = b'''<rss><channel>
      <item><title>Investor day</title><link>https://issuer.test/event/1</link><pubDate>Tue, 08 Sep 2026 12:00:00 GMT</pubDate><description>Official event announcement</description></item>
      <item><title>Future item</title><link>https://issuer.test/event/2</link><pubDate>Fri, 11 Sep 2026 12:00:00 GMT</pubDate></item>
    </channel></rss>'''
    rows = primary_source_evidence(raw, definition, CUTOFF, ["SPY", "NVDA"], CUTOFF.isoformat())
    assert len(rows) == 1
    assert rows[0]["symbols"] == ["NVDA"]
    assert rows[0]["kind"] == "news"
    assert rows[0]["primary_kind"] == "issuer_event"
    assert rows == primary_source_evidence(raw, definition, CUTOFF, ["SPY", "NVDA"], CUTOFF.isoformat())


def test_federal_register_policy_feed_is_bounded_and_watchlist_scoped():
    definition = {
        "id": "federal-register-tech", "publisher": "Federal Register", "kind": "sector_release",
        "format": "federal_register_json", "url": "https://www.federalregister.gov/api/v1/documents.json",
        "publisher_domains": ["www.federalregister.gov"], "symbols": ["*"], "maximum_items": 1,
    }
    raw = b'{"results":[{"document_number":"2026-1","title":"Semiconductor rule","abstract":"Notice","publication_date":"2026-09-08","html_url":"https://www.federalregister.gov/documents/2026/1","agencies":[{"name":"Commerce"}]},{"document_number":"2026-2","title":"Ignored by bound","publication_date":"2026-09-08","html_url":"https://www.federalregister.gov/documents/2026/2"}]}'
    rows = primary_source_evidence(raw, definition, CUTOFF, ["SPY", "QQQ"], CUTOFF.isoformat())
    assert [row["id"] for row in rows] == ["primary-federal-register-tech-2026-1"]
    assert rows[0]["symbols"] == ["SPY", "QQQ"]
    assert rows[0]["kind"] == "policy"


def test_fomc_calendar_preserves_announcement_and_scheduled_date_semantics():
    definition = {
        "id": "fomc-calendar", "publisher": "Federal Reserve", "kind": "policy_event",
        "format": "fomc_calendar_html", "url": "https://www.federalreserve.gov/calendar",
        "publisher_domains": ["www.federalreserve.gov"], "symbols": ["*"], "maximum_items": 10,
    }
    raw = b'''<h4>2026 FOMC Meetings</h4>
      <div class="fomc-meeting__month">September</div><div class="fomc-meeting__date">15-16*</div>
      <div class="fomc-meeting__month">October</div><div class="fomc-meeting__date">27-28</div>
      <footer>Last Update: August 19, 2026</footer>'''
    rows = primary_source_evidence(raw, definition, CUTOFF, ["SPY"], CUTOFF.isoformat())
    assert [row["scheduled_for"] for row in rows] == ["2026-09-16", "2026-10-28"]
    assert rows[0]["published_at"] == "2026-08-19T00:00:00+00:00"
    assert rows[0]["temporal_role"].startswith("ANNOUNCED_FUTURE")


def test_etf_sponsor_profile_and_quality_summary_do_not_invent_missing_metrics():
    sponsor = parse_etf_profile({
        "symbol": "QQQ", "as_of": "2026-09-09", "source_url": "https://sponsor.test/qqq",
        "metrics": {"expense_ratio_pct": .2, "pe_ratio": 30.5, "holdings_count": 100},
    }, "QQQ", CUTOFF)
    holdings = parse_holdings_csv(
        b"as_of,source_url,ticker,name,weight_pct,sector\n2026-09-09,https://sponsor.test/qqq,NVDA,Nvidia,9,Technology\n",
        "QQQ", CUTOFF)
    result = etf_quality_valuation(holdings, sponsor)
    assert result["status"] == "COMPLETE_CURRENT_INPUTS"
    assert result["holdings_coverage_pct"] == 9
    assert result["sector_hhi"] == pytest.approx(.0081)
    assert result["sponsor_metrics"] == {"expense_ratio_pct": .2, "pe_ratio": 30.5, "holdings_count": 100}
    assert "price_to_book_ratio" not in result["sponsor_metrics"]


def test_primary_config_rejects_unapproved_domain_and_etf_profile_future_date():
    with pytest.raises(ValueError, match="publisher domain"):
        validate_primary_source_config({"version": "meta-primary-sources-v1", "sources": [{
            "id": "bad-source", "kind": "policy_release", "format": "rss_atom",
            "url": "https://other.test/feed", "publisher_domains": ["publisher.test"], "symbols": ["*"],
        }]})
    with pytest.raises(ValueError, match="nonfuture"):
        parse_etf_profile({"symbol": "QQQ", "as_of": "2026-09-11", "source_url": "https://sponsor.test",
                           "metrics": {"expense_ratio_pct": .2}}, "QQQ", CUTOFF)


def test_company_valuation_requires_traceable_shares_and_same_date_book_value():
    profile = company_fundamentals(companyfacts(), "AAPL", CUTOFF,
                                   recent_filings(submissions(), "AAPL", CUTOFF))
    assert company_market_valuation(profile, {"status": "FRESH", "latest_close": 200,
                                              "price_date": "2026-09-09"})["status"] == "MISSING"
    base = {"value": 10, "end": "2026-07-31", "accession": "a", "unit": "shares"}
    profile["metrics"]["shares_outstanding"] = base
    profile["metrics"]["equity"] = {"value": 500, "end": "2026-07-31",
                                      "accession": "b", "unit": "USD"}
    result = company_market_valuation(profile, {"status": "FRESH", "latest_close": 200,
                                                "price_date": "2026-09-09"})
    assert result["metrics"] == {"market_cap_proxy_usd": 2000, "price_to_book_proxy": 4}
    profile["metrics"]["equity"]["end"] = "2026-06-30"
    assert company_market_valuation(profile, {"status": "FRESH", "latest_close": 200,
                                              "price_date": "2026-09-09"})["status"] == "PARTIAL"


def test_instrument_and_geopolitical_profiles_make_gaps_explicit():
    profile = company_fundamentals(companyfacts(), "AAPL", CUTOFF,
                                   recent_filings(submissions(), "AAPL", CUTOFF))
    company = instrument_evidence_profile(
        "AAPL", False, fundamentals=profile, holdings=None, sponsor_profile=None,
        instrument={"status": "FRESH", "latest_close": 200, "price_date": "2026-09-09"})
    assert company["families"]["latest_10k"] == "AVAILABLE"
    assert company["families"]["country_revenue_and_supply_chain"] == "MISSING"
    evidence = {"policy-1": {"kind": "policy", "symbols": ["AAPL"],
        "event_status": "PROPOSED", "transmission": [{"channel": "TARIFF"}]}}
    coverage = geopolitical_transmission_coverage(evidence, ["AAPL", "QQQ"])
    assert coverage["by_symbol"]["AAPL"]["status"] == "TRACEABLE_TRANSMISSIONS"
    assert coverage["by_symbol"]["AAPL"]["event_status_counts"] == {"PROPOSED": 1}
    assert coverage["by_symbol"]["QQQ"]["status"] == "MISSING"
