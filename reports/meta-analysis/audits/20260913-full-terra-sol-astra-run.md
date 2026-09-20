# September 13 full Terra/Sol/Astra run audit

## Decision

`PASS_AS_UNCALIBRATED_RESEARCH_OUTPUT` for the complete seven-stage transport,
schema, citation-membership and reviewed semantic-evidence gates. This does not
qualify a forecast, establish calibration, or authorize a retrospective META
observation for the September 11 origin.

## Immutable identities

- Source packet: `reports/meta-analysis/analysis-20260911T205359598727Z-0cf0208e/packet.json`
- Packet hash: `59d8445181abcf42785c1bc4022920ec1a89dae6b49dc9d3bb948891e9a4ec31`
- Agent run: `reports/meta-analysis/agents-20260913T070543331922Z-888dea7c`
- Harness implementation SHA-256: `1b00ac3fa7fff5813e97271240206aad55ae6a3009c80caa5832144346b37c9b`
- Runtime configuration hash: `209bde1470b18899b36e5a2a2fa35eadcf28b55db40557baf4d042c371d9bb14`
- Meta-report SHA-256: `721278b46cf75bc9849680d60eda1b5684d9d822b10f52ce38d9222993a52d7b`
- Critic-result SHA-256: `7cf7fac9cb412e74535eb0e50e7b9d2b602c9e0267aed912dd5a40325c0c239b`
- Synthesis-result SHA-256: `52f72ce2186fff44cd869778688c791460fc7940e28150d276bed2c4a032b051`
- Completion: `2026-09-13T07:11:17.853188+00:00`

The report status is `COMPLETED_UNCALIBRATED_RESEARCH`; all seven configured
roles executed, with no failures or skipped roles. `on_stage_failure` was `stop`.

## Model and usage receipts

All requested and responding model identities match: Terra handled the five
independent roles, Sol handled the critic, and Astra handled synthesis. Every
receipt reports a normal `stop` at medium reasoning effort.

| Stage | Model | Input | Output | Total | Latency ms |
|---|---|---:|---:|---:|---:|
| macro cycle | `gpt-5.6-terra` | 23,601 | 1,437 | 25,038 | 28,175 |
| technical | `gpt-5.6-terra` | 7,332 | 2,130 | 9,462 | 39,989 |
| fundamental | `gpt-5.6-terra` | 22,800 | 1,883 | 24,683 | 36,087 |
| news | `gpt-5.6-terra` | 26,238 | 1,728 | 27,966 | 32,784 |
| geopolitical | `gpt-5.6-terra` | 54,813 | 1,460 | 56,273 | 27,861 |
| critic | `gpt-5.6-sol` | 68,300 | 3,326 | 71,626 | 103,445 |
| synthesis | `gpt-6-astra` | 43,716 | 2,929 | 46,645 | 115,340 |
| **Total** |  | **246,800** | **14,893** | **261,693** | **383,681 stage-ms** |

Pi's catalog cost estimate totals `$1.398114`; this is receipt metadata, not an
API invoice for the authenticated Plus-plan workflow.

## Astra synthesis citation and claim audit

All 50 citation occurrences (36 unique source IDs) resolve inside Astra's
deterministic synthesis projection. The evidence timestamps are at or before the
packet cutoff. Each assessment was checked against its cited price panel, macro
panel, filing facts, holdings table, supplied article text and/or primary release.

| Symbol | Citation occurrences | Reviewed support |
|---|---:|---|
| SPY | 15 | Price is below SMA20 and above SMA50/SMA200; NFCI/STLFSI4 are negative; INDPRO growth is modest and lagged; SPY's dated partial top-ten table reports 38% and identifies AAPL/MSFT/NVDA; the September 16 FOMC event is scheduled. Conflicting inflation/flow stories are explicitly treated as secondary and unresolved. |
| QQQ | 8 | Price is just below SMA20 and above SMA50/SMA200; 21- and 63-session returns are slightly negative; supplied reports support the opposing futures-positioning and QQQ-purchase narratives. Missing holdings, valuation and primary flow evidence remain explicit. |
| AAPL | 10 | Price is above all supplied moving averages, 21-/63-session returns are positive and RSI14 is above 70. Filing-derived YTD margins and operating cash flow support profitability. Product, pricing, market-share and leadership reports are correctly qualified as secondary or uncorroborated. |
| MSFT | 8 | Price is near SMA20 and above SMA50/SMA200; the 21-session return is near flat and the 63-session return is strong. FY2026 filing facts support high margins, operating cash flow above capital expenditure, and equity above liabilities. AI-capacity claims remain labeled secondary and project economics missing. |
| NVDA | 9 | Price is below SMA20 and above SMA50/SMA200, with negative 21-session return and elevated realized volatility. Filing facts support strong YTD profitability. NVIDIA's primary release reports Q2 FY2027 revenue of $96.2B, +18% sequentially and +106% year over year; other issuer releases establish announcements, not completed deployment or guaranteed revenue. |

The synthesis consistently labels conditional interpretations as inference,
preserves contrary evidence, names missing inputs, avoids numeric confidence and
does not alter the code-generated uncalibrated quantitative reference. Its five
views are all `MIXED`, which is a qualitative research conclusion rather than a
tradable direction or a calibrated probability.

## Operational notes

The earlier partial run at
`reports/meta-analysis/agents-20260913T033409060631Z-5a6bd550` remains an aborted
artifact. It was not merged with this run. Before this clean rerun, the model-
visible schema gained cross-field abstention constraints and the harness gained
process-group timeout/operator cancellation, bounded SIGKILL escalation,
`cancellation.json`, accurate executed/skipped-role reporting and fail-closed
dependent-stage gating. The focused 31-test META suite and the repository-wide
18 TypeScript plus 371 Python tests passed.
