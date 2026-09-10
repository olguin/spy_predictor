# Parallel plan: practical cycle-investing analysis

New requested extension, 2026-09-09: [META analysis plan and runnable starter](META_ANALYSIS_PLAN.md)
adds a current watchlist indicator packet, specialist prompt contracts and a
staged implementation plan. The [orchestrating prompt](META_ANALYSIS_PROMPT.md)
describes source retrieval, calculations, specialist analysis and synthesis.
This is a secondary application extension, not a change to Cycle 1 authorities.

Update 2026-09-10: both notebooks use the verified September 9 current snapshot,
and the separate META workbench has now produced and prospectively registered a
fresh September 10 five-symbol quant-only packet. SEC submissions/company facts
are present for AAPL/MSFT/NVDA; SPY holdings are partial and QQQ holdings remain
missing. Paper/read-only IBKR delayed quotes are verified for SPY/QQQ/ES/NQ, while
paid real-time API entitlement is absent. The META outcome/scoring loop, guarded
post-close command, delayed-context importer, VIX/VIX3M proxy, transparent
risk-appetite components and explicit ES/NQ rollover rule are now implemented;
all 15 first-observation targets remain `NOT_DUE`. See
[current snapshot](WORKBENCH_CURRENT_SNAPSHOT.md), [META plan](META_ANALYSIS_PLAN.md)
and [operations runbook](META_OBSERVATION_OPERATIONS.md); remaining coverage is explicit. The
original implementation-stage description below is historical context.

Plan and public-source review: 2026-09-08. Current implementation status:
**M1 is complete and substantial M2/M3 evidence plumbing is operational**. The
input schema, integrity/timing/unit checks and explicit metric transforms exist;
qualified current snapshots, SEC evidence, manual ETF holdings and prospective
META registration and outcome evaluation now run. Broader ETF/issuer/event
evidence, derived valuation and production agents remain pending. Owner: the secondary
application workstream, separate from the stopped Cycle 1 audit.

## Objective and relationship to the main goal

Current runnable increment: [notebook instructions](../notebooks/README.md) and
[shared workbench module](../python/src/spy_predictor_quant/cycle_workbench.py).
Both notebooks now provide scenario/cutoff controls, market and instrument
assessments, reasons/counterevidence, source freshness, a component comparison
chart and optional JSON/HTML export. Six handcrafted scenarios exercise the
rules; they are not current observations or values derived from the notebooks'
earlier price-series examples. `DATA_MODE` rejects real-history access before
the legacy adapters run. Both notebooks executed successfully in synthetic mode.

```bash
npm run cycle:workbench -- compare --as-of 2026-08-31T20:00:00+00:00 --output reports/cycle-workbench/demo
```

This command is available now. Manifest ingestion is also implemented; see
[example input contract](../examples/cycle-workbench/README.md) and
[notebook instructions](../notebooks/README.md). The sample contains synthetic
measurements, not current market observations. Seven named metrics are transformed
into illustrative scores with source evidence preserved; a supplied score is not
accepted as a measurement. The next application increment is a qualified current
source snapshot and broader component calculations, with explicit missingness.

Build tools that answer two practical questions at an explicit information cutoff:

1. What does the economic, earnings, valuation, technical, credit, and investor
   behavior evidence say about the market environment and an appropriate research
   posture?
2. Is a specified instrument worth considering in that environment, what supports
   or contradicts the thesis, and what would change that assessment?

The main project goal remains reproducible, calibrated forecasts with demonstrated
incremental predictive and executable economic value on unseen evidence. This
secondary product can deliver useful descriptive analysis even if Cycle 1 rejects
its predictive claims. It must earn any predictive or allocation claim through its
own validation. A useful dashboard does not qualify the suspended Cycle 1 dataset
or authorize selection, confirmation, or trading.

Use the product name **Cycle Analysis Workbench**. Identify the conceptual
inspiration as Maru Cape / Mariela Capezzuoli, but label every numerical rule by
its actual origin. “CAPE” as a valuation statistic must be named **Shiller CAPE**;
it is not an abbreviation for this whole method.

## What the public method supports

The public syllabus attributed to Mariela Capezzuoli covers economic phases,
employment and inflation, the Fed, the yield curve, and credit; company earnings
and sector sensitivity; historical P/E, P/B, and P/S comparisons; investor
psychology; structural trend, volume, volatility, and moving averages; and
defensive/aggressive positioning. It connects fundamental analysis with trend
analysis and emphasizes preparing for conditions rather than knowing the future.
This supports a multi-component workbench rather than assuming one master
indicator. [Instructor's public Ciclos Psico-Económicos syllabus](https://clavebursatil.com/ciclos-psico-economicos/).

The current US-cycle course listing names the same instructor but does not expose
its detailed curriculum. It therefore adds no executable formula specification.
[US-cycle course listing](https://clavebursatil.com/curso/ciclos-de-la-bolsa-de-estados-unidos/).

Neither inspected page specifies a complete indicator formula, exact weights,
thresholds, estimation windows, or trading algorithm. The mappings below are
**our proposed operationalizations**, not a reproduction of an undisclosed model.
Record source URLs, publication dates when available, access dates, and precise
attribution for each future method claim. Only call a rule an exact reproduction
after verifying the actual rule and its inputs from an authoritative source or
user-provided material. Inaccessible videos and third-party summaries do not
establish an exact implementation.

## Components and useful outputs

All formulas and thresholds in this table are proposals to version before use.
Keep the dimensions visible rather than hiding disagreements in a single score.

| Component | Initial measurable implementation | Practical output and limitation |
|---|---|---|
| Economic environment | Vintage-safe inflation and industrial-production changes; later employment, GDP, policy rate and term-curve slope | Growth/inflation/monetary context with direction, freshness, and conflicts; no assertion that one proxy identifies a recession |
| Credit conditions | Existing `MPRIME - GS3M` level and exact three-month change, clearly named lending-rate proxy; later separately qualified lending-standards and financial-conditions inputs | Tightening/easing and current stress separated from boom-created fragility; the rate difference is not corporate default spread |
| Fundamental quality | For companies: reported revenue/earnings growth, margins, cash generation, leverage and interest coverage, with sector-specific applicability | Quality/stability assessment, balance-sheet concerns, and cyclical sensitivity; losses and unsuitable denominators yield unavailable ratios |
| Fundamental valuation | Company P/E, P/B, P/S and cash-flow metrics against cutoff-safe own history and a declared peer set; ETFs require dated aggregate/holdings evidence | Attractive/ordinary/expensive relative to the chosen reference; price falling is insufficient evidence of cheapness |
| Structural position | Existing trailing robust log-price trend and causal deviation normalization; disclose price/total-return and real/nominal convention | Stretched/below-trend position; a price trend is not intrinsic value |
| Technical timing | Explicit trailing moving averages, slopes, drawdown, realized volatility, relative strength against a chosen benchmark; later volume and breadth where coverage exists | Improving/deteriorating timing and trend/countertrend distinction; no exact top/bottom claim |
| Investor behavior | Initially unavailable unless a distinct qualified proxy is supplied; later volatility expectations, positioning or survey inputs with clear identities | Fear/risk appetite evidence and conflicting readings; realized volatility is not a sentiment survey and a valuation residual is not identified psychology |
| Expectations | Caller-supplied fundamental scenario or timestamped consensus, with assumptions retained | Implied hurdle, upside/downside scenario sensitivity, and actual-vs-expected surprises; no invented consensus estimates |
| Joint assessment | Rule table combining market context, instrument quality/valuation/timing, and evidence quality | Candidate, wait, defensive review, neutral, or insufficient evidence; explicit reasons, invalidation conditions, and next review |

Use descriptive structural zones such as `BELOW_TREND`, `NEAR_TREND`, and
`ABOVE_TREND` in the product. Existing low-level nested-cycle names that say
“undervalued” must not be rendered as a fundamental valuation conclusion.

## Existing assets to reuse

- [cycle_analysis_tools.py](../python/src/spy_predictor_quant/cycle_analysis_tools.py)
  already implements causal structural trends, robust scores, component dimensions,
  expectations decomposition/surprise, credit amplification, rule states, nested
  cycles, fixed-parameter forward state filtering, and bounded research exposure
  mapping. [CYCLE_ANALYSIS_TOOLS.md](CYCLE_ANALYSIS_TOOLS.md) documents their contracts.
  The caller currently bears responsibility for vintage safety and meaningful
  normalized inputs; the new orchestration layer must enforce those requirements.
- Existing tests in `python/tests/test_cycle_analysis_tools.py` cover these
  primitives. Add end-to-end input provenance and decision tests rather than
  replacing their mathematical implementations.
- The two existing cycle notebooks are the initial user-facing interface for
  this secondary goal, to be expanded rather than replaced by a CLI-only product.
  Keep explicit synthetic mode during development: their automatic mode can use
  validation history.
- `cycle1_fred.py`, `historical_http.py`, `market_archive.py`, calendar helpers,
  and IBKR normalization provide patterns for source adapters, immutable raw
  snapshots, cutoff handling, and market conventions. Reuse helpers without
  changing Cycle 1 authorities or importing its evaluation runner.
- Archived SPY/QQQ prices, sponsor distributions, and CPIAUCSL/INDPRO/MPRIME/GS3M
  vintages exist. They are neither current-market evidence nor automatically
  approved secondary-track inputs. First audit intended access, timestamps,
  coverage, source permission, and research-only reconstruction limitations.

The missing product pieces are a separate input manifest and configuration,
source orchestration, company/ETF fundamental adapters, rule-based explanations,
CLI/reporting, and a dedicated evaluation ledger.

## Source and timing contract

Every input needs instrument/series identity, units, frequency, observation or
accounting period, publication time, first-seen time, retrieval time, source URL,
snapshot hash, vintage/accession, adjustment convention, and admissible use.
Reject observations published after the report cutoff. Date-only publications
become available conservatively at the documented end of that day. Preserve
revisions as separate records and never backfill a historical decision with a
later filing or a present-day constituent list.

ALFRED archives vintage versions of economic data, making it a candidate for
historical release-aware joins; series-specific coverage still needs checking.
[ALFRED help](https://alfred.stlouisfed.org/help).

SEC submissions and company-facts APIs expose filing histories and XBRL facts
without API keys. Company-facts coverage is limited by taxonomy and entity scope;
custom tags need separate handling. The frames API selects last-filed facts and
must not be treated as a historical point-in-time panel. Use accession-specific
facts joined to filing availability, correct units and fiscal periods, and an
explicit amendment policy. [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

The Chicago Fed publishes weekly NFCI conditions and risk/credit/leverage
components. Their sample-based construction is a reason to preserve dated
releases rather than treating today's historical download as unrevised historical
evidence. [NFCI methodology](https://www.chicagofed.org/research/data/nfci/about).
The Fed's generally quarterly SLOOS distinguishes lending standards/terms from
loan demand, making it a useful separate candidate for the credit panel.
[SLOOS source](https://www.federalreserve.gov/data/sloos.htm).
Cboe offers VIX historical data as a candidate volatility-expectations diagnostic;
check access and permitted reuse before adding ingestion.
[Cboe historical data](https://www.cboe.com/tradable-products/vix/vix-historical-data).

These are proposed source choices, not newly authorized Cycle 1 sources or claims
that the adapters already exist. Preserve the existing Moody's/ICE and Tiingo
exclusions. No new paid data purchase belongs to this plan. Public web access
alone does not establish redistribution rights.

Reports must distinguish `SYNTHETIC`, `RECONSTRUCTED_RESEARCH`, and
`OBSERVED_AS_OF` evidence. A latest snapshot can support a dated current
description, but cannot establish what a user could have seen years ago.
Track `FRESH`, `STALE`, `MISSING`, and `NOT_APPLICABLE` per component. Define
freshness against the source's expected publication schedule and market calendar,
with an explicit grace period in configuration; do not treat quarterly filings
as stale merely because a daily price changed. Mixed-frequency panels show each
effective date and never imply that the report has six equally current readings.

US broad-market context plus SPY/QQQ is the first scope. It must be labelled
**US-equity coverage**, not “the entire global market.” Extend to a small declared
US-company watchlist once fundamentals work. Argentina, CEDEARs, other countries,
bonds, commodities, and crypto require their own currencies, accounting,
liquidity, calendars, and source contracts. For example, CEDEAR ratios and FX
translation cannot be inferred from US-share prices alone.

## Decision outputs

Produce JSON plus a readable HTML or Markdown report. A market report includes
the cutoff, coverage matrix, component values and changes, evidence links,
conflicting signals, research posture, scenario triggers, and next review date.
An instrument report adds its market/sector benchmark, quality and valuation
evidence, structural/timing position, thesis/counter-thesis, and conditions that
would improve or invalidate the case. A watchlist compares only instruments with
compatible evidence and does not place missing fundamentals at the top of a rank.

Proposed ordered action categories, to be encoded and fixture-tested in M1:

| Category | Rule intent | Useful suggested next step |
|---|---|---|
| `INSUFFICIENT_EVIDENCE` | Required provenance, freshness, quality, valuation, or risk evidence absent | Show exactly what is missing; abstain from an overall investment judgment |
| `DEFENSIVE_REVIEW` | Explicit severe risk/fragility rule or instrument thesis failure | Review exposure, concentration and capital-preservation alternatives; show the trigger |
| `WAIT_FOR_CONFIRMATION` | Interesting fundamental case with adverse timing or contradictory context | Watch specific improving conditions and thesis invalidation levels |
| `CANDIDATE_FOR_RESEARCH` | Required evidence complete and configured quality/value/timing/risk conditions align | Investigate a staged-entry scenario with explicit risk assumptions |
| `NEUTRAL` | Complete evidence with no qualifying edge under the rules | Maintain review cadence; list what would move the assessment |

Market-only reports use `SUPPORTIVE`, `MIXED`, `DEFENSIVE`, or
`INSUFFICIENT_EVIDENCE`, separately from instrument attractiveness. A favorable
market does not make every instrument attractive. Missing instrument valuation
still permits a technical panel, but prevents a complete investment assessment.

Initial confidence measures completeness, freshness, and agreement, with its
formula shown. It is not a probability of profit. Optional scenario budgets
require user-entered horizon, base currency, existing exposures, liquidity needs,
loss tolerance, concentration limits, and costs; otherwise omit personalized
position size. The existing exposure mapper is a research utility, not an
allocation policy with established economic value. Every proposed action includes
the evidence that would reverse it. No order submission or scheduled execution
is part of this workstream.

## Phased executable plan

Commands below describe the intended CLI contract; the synthetic fixture commands
now exist with timezone-aware cutoffs (see the current command above), while
manifest/universe adapters remain unimplemented. Use a
separate `spy_predictor_quant.cycle_workbench` module and `config/cycle-workbench-*`
identities. Write only under `reports/cycle-workbench/` and a dedicated secondary
source archive, never the frozen Cycle 1 output directories.

### M0 — method/source inventory and frozen initial design

Deliver the component-to-source registry, availability matrix, independent-rule
labels, input/report schemas, and `cycle-workbench-v1` draft configuration.
Specify windows, signs, threshold ordering, required/optional components,
freshness policy, instrument scope and benchmark conventions before reading
outcomes. Avoid tuning a “cycle top” composite just to match familiar episodes.
This document establishes the initial plan; executable configuration is still due.

### M1 — synthetic workbench MVP (immediate implementation)

Implement an offline input adapter, explicit-cutoff joins, and market/instrument
report composition around existing `cycle_analysis_tools`. Add independent
fundamental fixtures, technical timing, ordered actions, and reason codes.
Provide synthetic examples of recovery, expensive rally, stressed selloff,
cheap-but-deteriorating instrument, conflicting dimensions, and missing data.

Extend the existing notebooks as part of this milestone:

- [01_structural_trend_and_expectations.ipynb](../notebooks/01_structural_trend_and_expectations.ipynb):
  instrument selection, explicit cutoff, structural-position charts, separate
  fundamental valuation inputs, expectation scenarios and thesis/counter-thesis.
- [02_cycle_architecture_credit_and_risk.ipynb](../notebooks/02_cycle_architecture_credit_and_risk.ipynb):
  market component dashboard, credit/stress/fragility evidence, source freshness,
  conflicting signals, and conditional market/instrument assessment panels.

Preserve their Spanish/English explanations. Move shared input handling and
report decisions into the workbench module so notebooks and CLI produce the same
assessment. Add cutoff, evidence-mode and instrument controls; export the same
JSON/HTML or Markdown report without requiring a new interface. Replace automatic
Cycle 1 history access with an explicit secondary manifest adapter before real
use. Keep future-realized surprise/normalization studies in clearly separate
retrospective cells, inaccessible to an as-of assessment. Label illustrative
fundamental and psychology proxies in both plots and conclusions.

```bash
python/.venv/bin/python -m spy_predictor_quant.cycle_workbench market --fixture recovery --as-of 2026-08-31T20:00:00+00:00 --output reports/cycle-workbench/demo-market
python/.venv/bin/python -m spy_predictor_quant.cycle_workbench instrument --fixture cheap-deteriorating --symbol DEMO --as-of 2026-08-31T20:00:00+00:00 --output reports/cycle-workbench/demo-instrument
python/.venv/bin/python -m spy_predictor_quant.cycle_workbench compare --as-of 2026-08-31T20:00:00+00:00 --output reports/cycle-workbench/demo-watchlist
```

Acceptance: each command produces a reproducible hashed JSON/report pair; changing
future observations or later revisions cannot alter an earlier result; adverse
timing cannot disappear inside a good valuation score; missing required evidence
causes abstention; instrument and market conclusions remain distinct. These are
functional tests, not tests that the method predicts markets.
Both notebooks must also execute end-to-end on synthetic fixtures and agree with
the CLI on component values, reason codes and final assessment.

### M2 — qualified current US-market snapshot

Add a manifest validation command and read-only approved-source snapshot capture.
Establish source terms, release calendars and immutable storage before new
ingestion. Use a prospective/latest cutoff outside the main experiment's
historical confirmation interval; show all stale/missing dimensions honestly.

```bash
python/.venv/bin/python -m spy_predictor_quant.cycle_workbench validate-inputs --manifest snapshots/cycle-workbench/us-latest/manifest.json
python/.venv/bin/python -m spy_predictor_quant.cycle_workbench market --manifest snapshots/cycle-workbench/us-latest/manifest.json --as-of 2026-09-08 --output reports/cycle-workbench/us-market
```

Acceptance: produce a real, explicitly dated US-market report and SPY/QQQ
descriptive panels with source links and publication timestamps. Where ETF
fundamentals or psychology evidence remain absent, issue partial panels and an
incomplete overall assessment; do not fill them with price proxies.

### M3 — instrument research and comparison

Implement SEC/issuer fundamentals and security-identity mapping for a small
predeclared company universe; implement dated ETF aggregates separately. Add
sector-appropriate ratios, benchmark-relative technicals, corporate-action checks,
and scenario assumptions. Make `instrument --symbol ... --manifest ...` and
`compare --universe ... --manifest ...` produce explanations and conditional
investment suggestions under the explicit rules above.

Acceptance: a reader can trace every attractiveness conclusion to dated facts,
see counter-evidence and scenario sensitivity, and distinguish a quality/value
candidate from a mere large drawdown. No personalized size without portfolio
inputs. No cross-universe comparisons with silently incompatible conventions.

### M4 — independent validation and prospective journal

Start an append-only prospective assessment log before changing rules in response
to outcomes. Freeze each version and record every tested variation. Any historical
test needs a new secondary protocol, admissible partitions and datasets, and
available-at-the-time constituents/fundamentals. Keep Cycle 1's selection and
confirmation outputs inaccessible to this workstream.

Measure data quality and decision stability first. For economic claims, specify
forecast horizons, mature labels and primary metrics in advance; compare against
unconditional/benchmark and simple trend or valuation baselines. Evaluate
drawdown, turnover, costs and opportunity cost for an explicitly defined policy.
Handle overlapping horizons and shared market shocks as dependent observations;
report uncertainty, all trials and negative results. State-probability calibration
and probability-of-profit calibration are separate tasks. Descriptive historical
agreement with an analyst's narrative establishes neither.

Acceptance: retain `UNVALIDATED` unless independent evidence supports the precise
claim being made. A failed prediction test may leave the descriptive workbench
useful; it cannot justify advertising calibrated returns or profitable allocation.

## Parallel execution and next handoff

The primary Cycle 1 track and this application track remain isolated. The current
source snapshot, five-symbol SEC-enabled META packet, immutable first forecast,
outcome/scoring loop and guarded post-close runner are complete. Optional future
packets can add type-3 delayed IBKR context, an explicit ten-day ES/NQ rollover,
VIX/VIX3M structure and the transparent risk-appetite proxy. These additions do
not change Cycle 1 numerical rules or authorize its historical holdout.

The dated operational sequence is now:

1. After a new XNYS close plus 20 minutes, issue another observation with
   `npm run meta:postclose`; the next normal window begins September 11, 2026 at
   20:20 UTC / 17:20 Buenos Aires.
2. Run `npm run meta:outcomes -- update` on or after September 17 at 20:20 UTC to
   capture and score the first five-session outcomes. It is a no-write no-op before
   maturity.
3. Refresh QQQ holdings only through a permitted browser-saved sponsor table;
   continue primary event/calendar and issuer evidence adapters.
4. Keep production agents and any probability combiner conditional on prospective
   comparison against the quant-only records.

Exact commands and state semantics are in
[META_OBSERVATION_OPERATIONS.md](META_OBSERVATION_OPERATIONS.md).

Open research gaps: exact Maru Cape indicator formulas and parameters; any
authoritative numerical strategy rules; free, permitted, dated ETF aggregate
fundamentals; a suitable independent psychology proxy; historical issuer/peer
coverage and revisions; and empirical value of the proposed combined decisions.
Keep these explicit rather than silently inventing missing pieces. No present-day
investment recommendation has been computed by this planning review.
