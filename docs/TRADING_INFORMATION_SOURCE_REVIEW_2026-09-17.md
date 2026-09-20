Trading information sources: verified access and project fit
==========================================================

Reviewed September 17, 2026, America/Argentina/Buenos_Aires. This is a research
assessment, not an implementation or a subscription purchase.

I read the [shared conversation](https://chatgpt.com/share/6aac9f5d-2738-83e9-a006-cd9dc9249423),
checked current official documentation, inspected the relevant project code,
and downloaded and parsed two public State Street workbooks. Paid APIs and
authenticated MCP tools were not exercised; account entitlements remain unverified.

The chat's proposed division of sources is useful, but its TradingView conclusion
is incomplete, its Finviz API claim is stronger than the public documentation,
and its retry example accidentally retries permanent HTTP errors.

| Source | Access established in this review | Recommended project role |
|---|---|---|
| State Street / Sector SPDRs | Public XLSX downloads; two files successfully parsed | Dated ETF composition, concentration, exposure and constituent-news mapping |
| Trading Economics | Documented authenticated REST and calendar streaming | Scheduled macro events, consensus snapshots and release surprises |
| Benzinga | Documented authenticated APIs; news already available through the project's Alpaca collector | Improve existing news coverage; consider direct structured event products separately |
| Finviz | Elite CSV/Excel exports and automated workflows advertised | Optional daily candidate discovery when expanding beyond a fixed watchlist |
| TradingView | Official authenticated MCP documented | Interactive research, subject to applicable data-use rights |

**State Street / Sector SPDRs**

The [official XLK page](https://www.ssga.com/us/en/institutional/etfs/state-street-technology-select-sector-spdr-etf-xlk)
links both [daily holdings](https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-xlk.xlsx)
and [US product data](https://www.ssga.com/library-content/products/fund-data/etfs/us/spdr-product-data-us-en.xlsx).
Both downloads succeeded without authentication. The parsed files carried
September 16, 2026 dates. The product workbook is US product data, not a global
holdings database.

Observed import details: holdings have metadata above the header and disclosures
below the table; weights are percentage points. XLK includes cash and money-market
rows with ticker `-`, a negative-weight futures row, and `-` sector values.

Recommended adapter behavior:

- Archive original bytes, download time, sponsor as-of date and SHA-256.
- Preserve all positions in the raw/normalized archive. Produce an explicitly
  scoped equity view for the existing parser; disclose excluded positions and
  covered weight instead of silently renormalizing to 100%.
- Convert missing sector labels to null. Obtain classifications separately
  when needed for industry breadth.
- Check daily after close and again next morning if the sponsor date is stale.
  Discover each fund's official link; XLK's successful download does not verify
  every other sector file.

Useful derived features include top-ten concentration, overlapping constituent
exposure, and constituent-weighted news. Sector relative strength and breadth
also require price histories. Forward earnings revisions require a separate
estimates source; these workbooks alone do not supply them.

The integration target is `meta_evidence.py::parse_holdings_csv`, whose current
contract requires `as_of,source_url,ticker,name,weight_pct` and optionally `sector`.
It rejects negative weights and invalid tickers. Current composition must never
be reused as historical membership in a backtest.

**Trading Economics**

Use its calendar to capture release schedules, consensus and actual values.
[Authentication](https://docs.tradingeconomics.com/get_started/authentication/)
supports an `Authorization` header containing the API credential. A documented
request shape is:

```text
GET https://api.tradingeconomics.com/calendar/country/united%20states/indicator/initial%20jobless%20claims/{start}/{end}?f=json
Authorization: <credential>
```

The [documented limits](https://docs.tradingeconomics.com/get_started/rate-limits/)
are generally two requests/second, 1,000 calendar rows/request and 10,000 historical
rows/request, with plan-specific allowances. Split large requests into bounded
date windows and operate below the applicable ceiling. Proposed cadence: a daily
calendar refresh, pre-release consensus snapshots, then release-time collection;
[calendar streaming](https://docs.tradingeconomics.com/economic_calendar/streaming/)
is documented for subscriptions that support it.

There is a material qualification issue. The
[point-in-time page](https://docs.tradingeconomics.com/economic_calendar/point-in-time/)
claims preservation of original values, but its examples expose event date
ranges and fields such as `LastUpdate` and `Revised`, without demonstrating an
arbitrary historical retrieval cutoff or every consensus revision. That is not
enough evidence to certify the project's historical reconstruction requirements.
Verify vintage semantics and subscription coverage with sample responses before
admitting these records to historical features.

For prospective research, freeze consensus before the announcement. Calculate
`actual - frozen_consensus` after receipt, preserving units and release identity.
Any surprise standardization must use only earlier observations. Store scheduled
future events separately from realized macro observations. Keep existing
ALFRED-based reconstruction for the history it already qualifies.

**Benzinga and the existing Alpaca integration**

[Alpaca documents Benzinga as its news provider](https://docs.alpaca.markets/us/docs/historical-news-data).
The project already calls `/v1beta1/news` in `meta_analysis.py::news_source`.
It requests the latest 50 items across seven days with `include_content=false`,
records whether another page exists, and does not follow that page in this path.
This is bounded evidence for a report, not a complete news archive.

First improve this collector: process pagination within a budget, persist a
cursor, retain article updates, and distinguish complete coverage from truncated
coverage. Query ETF constituents as well as ETF symbols; the current code already
has exposure mapping to extend. Avoid counting the same syndicated article as
independent corroboration across providers.

Direct Benzinga becomes more attractive when structured earnings, guidance or
analyst events add information beyond the existing feed. API access is
subscription-specific. The [authentication documentation](https://docs.benzinga.com/api-reference/authentication)
describes `Authorization: token <KEY>`; do not assume a Pro interface subscription
includes every API product.

The [news endpoint](https://docs.benzinga.com/api-reference/news-api/get-news-items)
is `/api/v2/news`, supports ticker filters and `updatedSince`, and allows up to
100 records/page. [Benzinga's ingestion guidance](https://docs.benzinga.com/home)
recommends deltas, including `parameters[updated]` for Calendar/Signals.
Use an overlap window plus deduplication, preserve revisions, and advance the
cursor only after the entire batch is durable. Proposed features include dated
earnings surprises, guidance changes, rating changes and recent catalyst counts.
Article updates fetched today do not prove that today's article body existed
at its original publication time.

**Finviz**

The [official API-and-exports link](https://finviz.com/api-and-exports) redirects
to Elite marketing. It advertises CSV/Excel exports and automated workflows,
but the inspected page does not establish a public REST specification, API
authentication or machine-access quotas. Treat this as confirmed export support,
with an authenticated export contract still to inspect. Listed prices are
$39.50/month or $299.50/year at review time.

Recommended use: capture one daily screener export for candidate generation,
preserve the screen definition and its timestamp, and rank within that captured
universe. Do not invent endpoint URLs or build production ingestion around an
unofficial scraping library. For the existing small watchlist this is lower
priority than holdings and event coverage. Current screener values and surviving
symbols cannot reconstruct a historical investment universe.

**TradingView**

The chat's “UI only” conclusion misses the
[official MCP server](https://www.tradingview.com/mcp/docs):
`https://mcp.tradingview.com/mcp`, using OAuth 2.1 and Streamable HTTP. Documentation
lists Essential or higher, excluding trials, approximately 100 calls/minute,
and tools for OHLCV, screening, news, fundamentals and calendars. OHLCV requests
allow up to 5,000 bars. This was documentation verification, not an authenticated
service test.

However, [the general terms](https://www.tradingview.com/policies/) still restrict
non-display and algorithmic uses. The reviewed documents do not resolve how those
restrictions interact with MCP. My recommendation is interactive research within
the permitted scope; establish applicable rights before treating it as the
automated forecast engine's data feed. Retain the existing price providers for
the reproducible research archive.

**Shared collection design**

Preserve the project's separation between captured-live evidence and verified
historical reconstruction. `meta_research_data.py` currently admits only
`SEC_ACCEPTANCE` and `ALFRED_VINTAGE` evidence kinds for reconstruction; a new
provider cannot simply be relabeled as one of those.

For each adapter, retain source identity, record identity, economic/effective
date, publication time when known, provider update time, first receipt time,
usable-at time, revision ID, raw hash, parser version and quality flags. Unknown
availability should remain unknown. Event schedules need their own versioned
records because future scheduled time differs from present knowledge of it.

Normalize deterministically before passing compact evidence to research agents.
Compute price indicators from the existing price archive. Keep raw material
available for audits and replay subject to the provider's storage rights.

The shared chat's retry function throws on 400/401/403 inside a broad `try`, then
catches and retries those errors. Its comment and behavior therefore disagree.
A correct transport should:

- Retry transient network failures, 429 and selected 5xx responses with bounded
  exponential backoff and jitter.
- Stop on permanent request/entitlement errors; classify them separately from
  temporary outages.
- Honor both numeric and HTTP-date `Retry-After` values, impose request timeouts
  and an overall deadline, and release failed response bodies.
- Rate-limit across workers sharing credentials, checkpoint complete pages,
  redact credentials from logs, and avoid advancing cursors after partial failure.

**Recommended sequence and acceptance evidence**

1. Build State Street ingestion into the existing holdings workflow. Verify dates,
   weight units, cash/derivative treatment, coverage and repeatable offline replay.
2. Expand the existing Alpaca news collector. Demonstrate complete pagination for
   a bounded interval, deduplication, update retention and visible gaps.
3. Pilot Trading Economics for prospective events and consensus snapshots.
   Prove pre-release and post-release availability separately before backtesting.
4. Add direct Benzinga only for specifically missing structured products; consider
   Finviz when candidate discovery becomes a project requirement.
5. Evaluate TradingView MCP for interactive research under its applicable terms.

These priorities reflect integration cost and the gaps visible in the repository.
They are not claims that adding a source improves forecasting. Evaluate each
feature family against the existing baseline using frozen inputs, chronological
holdouts and the project's established qualification gates.
