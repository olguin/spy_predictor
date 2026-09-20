# Project plan, status, and next-session handoff

Planning update: 2026-09-20. Engineering baseline updated: 2026-09-17.
Repository: `spy_predictor`.

**Next product plan: [Agentic Investment System V1](AGENTIC_INVESTMENT_SYSTEM_V1_PLAN.md).**
The user clarified the goal as cooperating research agents and confirmed a
primary horizon of several weeks to three months. The plan covers tool-based
research, targeted inter-agent questions, independent challenge, publication-time
freshness and a measured feedback cycle. It is a planning deliverable; no V1
runtime implementation or new empirical result is claimed. It supersedes the
fixed-packet workflow below as the proposed product direction, while retaining
existing experiment protections and qualification gates.

For the delivered baseline, read [the engineering handoff](IMPROVEMENT_PLAN_3_HANDOFF.md).
Synthesis diagnosis found and repaired exact-decimal transport loss. Full
archived Astra synthesis and all 15 rendered frozen rows now pass. A newly
captured chain also passed through registered synthesis recovery; its original
single-pass attempt remains partial and publication freshness remains gated. See the
[diagnosis record](IMPROVEMENT_PLAN_3_SYNTHESIS_DIAGNOSIS.md).
The existing worktree contains uncommitted/untracked work.
Historical qualification gates remain binding for performance claims, while
independent engineering can continue. IBKR Gateway is not required.

Current evidence: 1,704 diagnostic panel rows; 111 SEC/ALFRED reconstruction
records; 120 prospective research observations; four bounded prompt fixtures;
15 verified fallback-report rows, plus a verified full archived synthesis report.
Last full check passed 27 JS and 483 Python tests; final logging changes passed
build and 28 JS tests with Python unchanged. Both archived and newly captured
seven-role results are verified, with recovery lineage kept explicit.
See the [step-5 runbook](IMPROVEMENT_PLAN_3_STEP5_RUNBOOK.md) for receipts.
These counts do not establish a qualified training panel or predictive accuracy.

Existing implementation workstream: [IMPROVEMENT PLAN 3](#improvement-plan-3).
Implementation began 2026-09-16. The first engineering release repairs forecast,
evidence, decision, freshness and pairing contracts and adds a point-in-time
research store, experiment harness and dated-event controls. The full ten-phase
plan remains incomplete. Historical-data qualification and mature prospective
outcomes gate model selection and promotion. See the detailed
[implementation record](IMPROVEMENT_PLAN_3_IMPLEMENTATION.md) for delivered work,
validation and the remaining gate for every phase.

The GOLDEN GOAL clarity/probability/action redesign was implemented on 2026-09-15
as the v2 forecast/action contract and v3 agent-output contract. The user deferred
further VIX/VIX3M availability troubleshooting. Do not buy subscriptions or
register forecasts merely by reading this handoff.

## GOLDEN GOAL

Build an on-demand agentic META analyst that accepts a user-selected set of five
US-listed stocks and/or ETFs and analyzes them using all information genuinely
available at a declared cutoff. Combine bounded global and US market context,
Maru Cape-inspired cycle indicators, macro and central-bank evidence, yield
curves, credit, volatility and fear/risk-appetite measures, instrument technicals,
fundamentals, valuation, ETF look-through, news, events and geopolitical
transmission mechanisms.

Five independent specialists analyze one immutable evidence packet. A critic
audits claims, omissions, contradictions and duplicated evidence. A final META
synthesis produces a short-, medium- and long-horizon assessment for every
symbol: probabilities, recommendation, thesis, counter-thesis, catalysts, risks,
invalidation conditions, evidence-family coverage and missing inputs.

The finished system must run at any requested moment on a trading day. Every
input must say whether it is real-time, delayed, latest-completed-close, stale or
missing. An unfinished daily bar or delayed quote must never be represented as a
completed or real-time observation.

The product has two distinct operating lanes:

1. **On-demand analysis:** run whenever requested and produce the best supported
   analysis at that actual cutoff. This is the primary product goal.
2. **Prospective evaluation:** issue immutable forecasts only inside registered
   windows, attach outcomes later, and measure calibration and incremental value.
   This is the evidence path, not a restriction on ordinary analysis.

Agents must not improvise probabilities. They produce structured, cited facts and
bounded inferences. A separate numerical layer converts validated inputs into
probabilities, and a versioned policy converts them into research recommendations.
Until trained and prospectively tested, outputs must be labeled experimental or
uncalibrated. No order submission or personalized position sizing is implied.

## Current readiness

Implemented:

- Capture accepts 1–10 unique symbols; five is the intended normal universe.
  ETFs are declared as a subset of those symbols.
- Capture and offline build produce an immutable cutoff-bound packet with raw
  source hashes, calculated panels, acquisition failures and missingness.
- The versioned `meta-product-config-v1` contract freezes the dual operating lanes,
  symbol bounds, 5/21/63-session horizons, evidence states and probability states;
  current rendered output validates against `meta-product-view-v3`.
- Five specialist roles exist: macro/cycle, technical, fundamental, news and
  geopolitical. Sol performs criticism and Astra final synthesis.
- The pinned Pi/OpenAI Codex adapter supports trusted manual runs with
  Terra/Sol/Astra routing, schema checks, usage receipts, process-group
  cancellation, timeout escalation and fail-closed dependent stages.
- A clean legacy seven-stage run completed over the September 11 packet. Model
  identities and all 50 final citation occurrences passed manual review. That
  legacy evidence does not qualify the latest v4 chain: its six specialist/critic
  stages completed, but synthesis timed out. Neither run proves forecast accuracy.
- Agent output v4 retains claim-level `FACT`/`INFERENCE` records with evidence IDs,
  stance, evidence family, horizons, invalidation and exact JSON Pointer references
  for calculated values, plus distinct 5/21/63-session decisions. V4 uses explicit
  horizon support/opposition edges; the legacy stance field does not control v4
  scoring. Validation
  quarantines wrong numeric values and symbol-irrelevant claims for mandatory
  critic rejection and fail-closes malformed horizon support.
- Agent runs write a hash-bound manifest and support strict `agents --resume`.
  Verified roles are reused in a new linked run directory; incomplete roles are
  rerun and identity/dependency changes fail closed.
- `npm run meta:analyze` implements the non-registering on-demand lane from fresh
  capture through final Markdown report and receipt. It is fixture-tested for
  explicit cutoff/market-period/price-basis reporting and cannot enter the
  prospective ledger.
- Deterministic panels include completed-session SMA20/50/200, RSI14, ATR14,
  drawdown, returns and realized volatility; CPI, industrial production, DFF,
  T10Y2Y, MPRIME/GS3M, NFCI, STLFSI4, VIX and VIX/VIX3M; a transparent
  risk-appetite proxy; SEC company facts; bounded timestamped news; selected primary Fed,
  Federal Register and issuer sources; optional ETF files; and optional delayed
  IBKR context.
- G4 supplies Alpaca one-minute bars and latest quotes/trades in on-demand
  `intraday` mode. Free IEX evidence is labeled `REAL_TIME` plus `IEX_ONLY`, never
  consolidated. The packet includes rolling 1/5/15/60-minute OHLCV/VWAP,
  regular/extended-hours summaries, quote age, daily/weekly views, SPY-relative
  returns and descriptive support/resistance candidates. Halt status is explicitly
  unknown because no qualified halt feed is installed.
- The on-demand capture now requests licensed Massive index snapshots for
  `I:VIX` and `I:VIX3M`, validates exact index identity, provider `REAL-TIME` or
  `DELAYED` labeling, timestamps and age, and computes a same-session ratio only
  when both legs qualify. If either leg is unavailable, current VIX is
  `MISSING_INTRADAY`; the completed FRED observations remain visibly separate
  and are not silently substituted in the risk-appetite calculation.
- G5 adds public FRED 2Y/5Y/10Y/30Y yields, 10Y–3M, SOFR, 10Y real yield,
  breakeven inflation, NFCI credit contribution, broad dollar and WTI; same-date
  curve/real-rate panels; and daily market proxies for US size/style/sectors,
  developed ex-US, emerging markets, Japan, eurozone, credit, Treasuries, dollar,
  gold, copper and oil. Proxy limitations and missing central-bank/surprise/
  positioning families are machine-readable.
- G6 adds per-instrument evidence profiles, conservative SEC market-cap and
  price/book proxies when facts permit, ETF evidence-family gaps, event-state
  taxonomy and validated symbol/horizon transmission links for supplied
  geopolitical evidence.
- Quant-only observations exist for September 10 and 11, with 30 symbol/horizon
  records currently `NOT_DUE`.
- The separate 12-origin static-reference cohort is registered; its first origin
  is September 30, 2026.

Not implemented or incomplete:

- IBKR currently supplies optional type-3 delayed context, not entitled real-time
  API data, and never replaces the official close. Alpaca IEX now supplies the
  default live intraday lane without IBKR Gateway.
- Foreign central-bank adapters, release-surprise data, official global index
  levels, corporate option-adjusted spreads, broad market internals and qualified
  positioning/survey inputs remain incomplete. ETF price series are explicitly
  proxies, not index levels, commodity spot prices or credit spreads.
- The geopolitical reasoning contract exists, but broad primary and
  exposure-linked source coverage is insufficient.
- Generic SEC evidence and bounded valuation proxies exist, but issuer releases,
  earnings calendars, guidance, peer sets and geographic/supply-chain exposure
  remain incomplete for arbitrary symbols.
- QQQ browser-saved holdings and sponsor-profile inputs are configured and
  validate successfully. They remain manual and must be refreshed according to
  their embedded sponsor dates; filesystem creation time is not evidence age.
- The configured Massive key authenticates for Futures, but index snapshots and
  same-day minute aggregates for `I:VIX` and `I:VIX3M` returned HTTP 403. The
  September 15 read-only IBKR diagnostic qualified both indices and returned
  delayed values; live requests returned entitlement error 354. IBKR index capture
  is not yet wired into the META pipeline. Current volatility therefore remains a
  report gap, not proof that the indicators are unavailable. See the deferred
  data-access handoff below. Do not scrape Cboe's delayed-quote page; its terms
  prohibit automated extraction. Do not purchase data without user approval.
- Fear/risk appetite uses transparent proxies. There is no qualified comprehensive
  fear/greed, options-skew, flow, positioning or survey panel.
- Agent claims remain categorical/cited inputs rather than free-form numeric
  confidence. The G7 engine now converts horizon-applicable validated claims and
  bounded quantitative features into an experimental distribution. Pi OAuth is
  renewed, required models are visible, and the post-renewal five-symbol Terra
  stage passed the complete structured-output and claim-validation gate. The
  failed pre-renewal and schema-dialect attempts remain preserved, not reused.
- The zero-log-drift reference remains the unchanged comparator. The new META
  distribution and G8 research actions are deterministic but uncalibrated. They
  must not be represented as predictive skill until G9's prospective gate passes.
- There is no paper allocation workflow or live order path. G10 now supplies a
  local read-only dashboard/API and guarded scheduler, but no unattended system
  schedule has been installed.

## GOLDEN GOAL implementation plan

These are the active global phases. Each phase must produce versioned contracts,
immutable artifacts, tests and explicit failure behavior.

### G0 — Product contract and dual-lane architecture — COMPLETE

Define on-demand versus prospective modes, instrument identity, cutoff semantics,
5/21/63-session horizons, output vocabulary, freshness states and abstention.
Define “global context” as a bounded coverage set. Clarify that *tasa Fed* means
the Fed policy rate; fiscal tax data is separate. Share acquisition and analysis
between lanes while restricting only prospective registration to issue windows.

### G1 — Reliable and resumable agent orchestration — COMPLETE

Implement hash-verified `agents --resume <run-directory>`. Reuse a role only when
packet, runtime configuration, harness, request/input, validated result and receipt
identities match. Resume the earliest missing stage without editing old artifacts.
Add safe content-addressed caching and tests for interrupted specialist, critic
and synthesis stages.

### G2 — Claim-level evidence and deterministic auditing — COMPLETE

Make every material claim a structured `FACT` or `INFERENCE` with evidence IDs,
symbol, horizon and invalidation. Check source membership, cutoff, symbol
relevance and calculated values. Have the critic expose unsupported claims,
correlated signals, duplicate stories, contradictions and omissions.

### G3 — On-demand `meta:analyze` pipeline — COMPLETE

Add one command accepting symbols, ETF subset, actual analysis time and market
mode. It runs capture, build, specialists, critic, synthesis and report generation
during premarket, regular hours, post-close or closed markets. It must show partial
coverage and never register prospectively unless separately requested.

### G4 — Intraday and multi-timeframe market data — COMPLETE, BOUNDED V1

Add qualified timestamped quotes and intraday OHLCV: suitable 1/5/15/60-minute,
daily and weekly views; current open/high/low/volume/VWAP; relative strength;
support/resistance; market-hours state; pre/post-market labels; halts and quote
age. Verify provider entitlements. IBKR Gateway is needed only when IBKR is the
selected provider; real-time claims require real-time subscriptions.

Implemented with Alpaca IEX as the free default. IEX is real-time limited-venue
evidence, not SIP. `sip-delayed` is an explicit alternative. Daily close and
intraday observations remain separate. Weekly, relative-strength,
support/resistance and extended-hours fields are deterministic; halt status
abstains until a qualified feed exists.

### G5 — Broader global, cycle, fear and market evidence — COMPLETE, BOUNDED V1

Add major indices/sectors; 2Y/5Y/10Y/30Y Treasury yields and slopes; Fed target,
effective funds, SOFR, expectations, real yields and inflation expectations;
qualified investment-grade/high-yield credit; dollar/FX, oil, gold and copper;
major European/Asian context; material central-bank events; release surprises;
breadth, volume and market internals; and permitted sentiment/positioning inputs.
Keep public Maru Cape concepts distinct from this project's proxy formulas.

Implemented as public FRED panels plus a declared ETF proxy basket. Coverage is
substantially broader but deliberately not called exhaustive: unavailable
foreign-central-bank, economic-surprise, official market-internals and
positioning families remain `MISSING`.

### G6 — Company, ETF, event and geopolitical evidence contract — COMPLETE, BOUNDED V1

For companies, add issuer releases, earnings/events, guidance, suitable valuation,
peers, sector-specific fundamentals and country/currency/supply-chain exposure.
For ETFs, add dated holdings, allocations, concentration, fees, tracking and
sponsor valuation/quality using permitted sources or fresh manual files. Expand
policy, sanctions, tariff, regulation and geopolitical sources, mapping each event
through a documented transmission mechanism to affected symbols and horizons.

The validation, missingness and transmission contracts are implemented. Actual
coverage still varies by symbol: SEC is generic for US issuers, configured issuer
feeds are limited, ETF sponsor files remain manual, and geographic/supply-chain/
peer data is not inferred when absent. Those are visible evidence gaps, not hidden
phase completion claims.

### G7 — Structured META forecast and probability engine — V2 CLARITY REDESIGN COMPLETE

Have agents emit bounded horizon signals, evidence quality, disagreement and
abstention features—not free-form probabilities. Build a deterministic statistical
layer combining quantitative and structured contextual features. Model 5/21/63
session event probabilities, probability of positive return, return/price
quantiles and uncertainty. Keep LLM confidence separate from probability and
retain quant-only comparators and evidence-family ablations.

V2 uses critic-accepted, horizon-specific specialist claims under
`meta-forecast-policy-v2`. Rejected claims are excluded mechanically; material
unresolved claims, mixed views, critical gaps and excessive disagreement gate the
action to WAIT. Exact duplicate evidence signatures receive one role weight.
Every row binds a completed-close reference, observation date, forecast origin,
exact target session and terminal-event definitions. Expected and median returns
are distinct, and intraday-entry profitability/path probabilities are excluded.

### G8 — Recommendation and risk policy — COMPLETE, EXPERIMENTAL V2

Freeze how probabilities, expected outcomes, uncertainty, evidence quality and
invalidation map to horizon-specific research actions such as
`BULLISH_RESEARCH`, `ACCUMULATE_CONDITIONALLY`, `WATCH`, `NEUTRAL`,
`REDUCE_RISK`, `BEARISH_RESEARCH` or `INSUFFICIENT_EVIDENCE`. Every action must
show catalysts, counter-case, risk/reward, evidence quality and review trigger.
Portfolio sizing remains separate and requires explicit user constraints.

The policy is frozen in `config/meta-forecast-policy-v2.json`. It reports evidence
family coverage rather than claim-count confidence. Conditional entry requires a
cited numeric field/level, comparison, units, confirmation interval and expiry;
otherwise the action is WAIT. Outputs separate new-position and existing-holding
implications, blockers and next review. Position sizing and order execution remain
out of scope.

### G9 — Prospective evaluation and model governance — INFRASTRUCTURE COMPLETE; EVIDENCE ACCUMULATING

Keep the post-close ledger as the controlled evidence lane. Issue immutable
quant-only and META forecasts on common dates, acquire outcomes independently,
and evaluate calibration, proper scores, interval coverage, failures and
recommendation outcomes. Account for overlapping horizons and shared shocks.
Every material model, prompt, policy or data change receives a new cohort.

Registration can now attach the exact structured forecast and agent report to the
same immutable symbol/origin/horizon records as the zero-drift comparator. Outcome
scoring covers both variants, every role ablation, paired score deltas, interval
coverage, recommendation outcomes and governance cohorts. Cohort identity binds
policy, engine, packet implementation, product contract, agent runtime and
harness. Qualification requires at least 180 scored records, 60 distinct origins
and 40 records per horizon, followed by time-block/origin-cluster statistical
review. Current status is 30 legacy quant-only records, all `NOT_DUE`; no META
cohort is calibrated.

### G10 — Product interface and operational automation — IMPLEMENTED; UNATTENDED INSTALL DISABLED

- **G10.0 — contracts and operating policy:** versioned product, operations,
  attempt, state, alert and cache schemas plus a validated policy.
- **G10.1 — product projection:** one hash-verified view joins packet, agent,
  structured-forecast and G9 evaluation artifacts without changing the evidence.
- **G10.2 — human/API interface:** immutable JSON, readable Markdown,
  responsive self-contained HTML and a local-only read-only HTTP/API surface.
- **G10.3 — rate-aware acquisition:** thread-safe release-identity/TTL caches,
  pacing, content hashes and explicit manual-ETF rules in the normal capture path.
- **G10.4 — bounded operation:** source, byte, wall-time, parallelism, model-call,
  token and catalog-cost-estimate ceilings with fail-closed budget accounting.
- **G10.5 — guarded scheduling:** XNYS/DST/holiday/early-close decisions,
  dry-run by default, immutable attempts and duplicate/nonterminal protection.
- **G10.6 — monitoring and runbook:** append-only deduplicated alerts, visible
  partial failures, operational doctor, daily commands and interpretation guide.

The `meta-product-view-v1` projection generates an immutable hashed JSON summary,
readable Markdown, self-contained responsive HTML and a local-only, read-only
dashboard/API. It opens with a prominent Astra-authored **GOLDEN
RECOMMENDATIONS / GOLDEN CONCLUSIONS** executive synthesis containing the market
regime, critical cross-cutting conclusions, a ranked view of every requested
symbol, immediate review triggers and decisive evidence limitations. It also
displays the five-symbol × 5/21/63-session board, freshness,
coverage, a whole-market strip for volatility, policy, curve, financial
conditions and inflation, evidence quality, disagreement, probabilities, recommendations,
catalysts, counter-case, review triggers, partial failures, provenance and
prospective status. Missing/stale/failed evidence is never rendered as neutral.

The versioned operations policy adds release/TTL/manual cache rules, request
pacing, acquisition and agent budgets, immutable operation attempts and stage
receipts, deduplicated append-only alerts, calendar-aware dry runs, and guarded
prospective/outcome scheduler commands. The cache is integrated into normal
on-demand and post-close acquisition. Scheduler identities prevent replacement
forecasts and retain blocked/degraded attempts. Holiday, weekend, early-close,
DST, tamper, stale-cache, partial-agent, budget, duplicate and restart behavior is
covered by tests. No launchd/cron job is installed automatically.

The complete operator and interpretation guide is
[`GOLDEN_GOAL_DAILY_OPERATIONS.md`](GOLDEN_GOAL_DAILY_OPERATIONS.md).

### G11 — Paper policy and controlled deployment

Only after adequate evidence, separately qualify allocation, costs, turnover,
risk limits, kill switch, reconciliation and paper execution. Live orders require
new explicit user authorization and independent operational/evidence gates.

## IMPROVEMENT PLAN 3

Whole-process accuracy, agent architecture, and explanation improvement plan.
**Implementation started 2026-09-16. The original plan below is preserved;
current delivery evidence and remaining gates are recorded in
[IMPROVEMENT_PLAN_3_IMPLEMENTATION.md](IMPROVEMENT_PLAN_3_IMPLEMENTATION.md).
The full plan and empirical accuracy qualification remain incomplete.**

This is the active next-session improvement sequence. Earlier completed-plan
entries below remain historical records; the audit findings here qualify their
completion claims. Preserve the closed research tracks and frozen cohorts.
The complete plan is embedded below; the original standalone copy remains in
[GOLDEN_ACCURACY_AND_EXPLANATION_PLAN.md](GOLDEN_ACCURACY_AND_EXPLANATION_PLAN.md).

Prepared: 2026-09-16. Original saved status was proposed/not implemented.
Current implementation evidence is in [the implementation record](IMPROVEMENT_PLAN_3_IMPLEMENTATION.md).

### Objective and assessment

Analyze five user-selected stocks/ETFs at a declared live-market cutoff, with
separate 5-, 21-, and 63-session forecasts, evidence, uncertainty, and useful
decision conditions. Improve predictive performance on unseen observations and
make it possible to understand exactly why a recommendation exists. Sixty-three
sessions is approximately a quarter; a genuine one-year investment outlook
requires a separate target, model, and evaluation cohort.

The repository has a useful foundation: immutable evidence packets, source
hashes, explicit evidence states, numerical citations, specialist outputs,
criticism, deterministic forecast generation, and prospective outcome machinery.
However, **the current probability engine is a hand-designed scoring model,
and the predictive contribution of the agentic layer is unproven**. Completing
an agent run, accepting its citations, and producing a schema-valid report do
not establish that its conclusions improve forecasts.

The central research question should be:

> What changed relative to information already available, how does that change
> reach this instrument, how much has price already reacted, and does the
> remaining information predict its future return or risk on unseen data?

#### Scope of this audit

Reviewed the status/handoff, capture and packet construction, evidence panels,
agent prompts and validation, forecast/action policy, product rendering, and
outcome aggregation. Inspected September 15 run artifacts, including the completed
resumed run `agents-20260915T190053443022Z-7ac8a380`. Ran read-only Python checks
against its outputs and the current forecast functions. No new live capture,
model training, paid data purchase, or forecast registration was performed.

The completed run reused specialists and the critic from an earlier run. It is
evidence of a completed resumed chain, not proof that the latest code completes
a fresh live run reliably. Its forecast artifact also predates some current
validation edits. Findings below distinguish artifact observations from current
source-code behavior. These files are development artifacts, not a representative
sample from which to estimate production reliability.

### Findings that determine the implementation order

| Finding | Evidence and consequence |
| --- | --- |
| Probabilities are not learned | `meta_forecast._quant_signals` averages fixed transformations of trend, momentum, relative strength, and risk appetite. Context uses fixed role/direction weights. No fitted predictive relationship selects these weights. |
| Directional probability has an artificial ceiling | `_distribution` sets log-return mean to `score × 0.35 × sigma`. Therefore `P(up) = Φ(0.35 × score)`, bounded at approximately **36.3%–63.7%**. Conditional on score, horizon and volatility cancel from this probability; they still affect the price range. Changing this ceiling alone would not improve accuracy. |
| Agent evidence did not change the completed run's numbers | All 15 symbol/horizon rows had insufficient accepted context roles. Their combined scores equal the quantitative scores, allowing floating-point rounding. Macro, fundamental, and geopolitical specialists each returned `UNKNOWN` on all 15 horizons. All 15 actions were `WAIT`. |
| Valid facts and predictive signals are conflated | The critic can establish support for a statement, but the forecast then maps an accepted directional assessment to a fixed number. Neither the citation nor role agreement measures incremental predictive value. |
| Some quarantines do not reach scoring | Current `_context_signals` does not consume `deterministic_claim_rejections`. Adding a horizon-level incompatible-opposition finding to the accepted ANET/5-session row leaves its context result unchanged. Existing support filtering catches some defects, but is not an exhaustive quarantine gate. |
| Claim identity and stance need stronger contracts | Critic references use `role:claim_id`, while uniqueness validation is local to a symbol assessment. A claim ID repeated across symbols can collide. A fact's global stance also cannot cleanly express opposite implications at different horizons. |
| Recommendations lose important specialist output | `_recommendation` hardcodes `invalidation_trigger: None` and a generic next review. All 15 inspected forecast rows have null invalidations. `_trigger_for` selects a numeric trigger without establishing all trigger validity, critic acceptance, or whether it has already occurred. |
| Intraday analysis and forecast origin differ | Information can be captured intraday while the forecast reference and target derive from the preceding completed daily close. Part of the reported return is then already observed. This can be a legitimate explicitly defined close-based forecast, but does not answer return from a new entry now. |
| Freshness is separated from displayed values | Product freshness can be degraded while the instrument's original acquisition state still says `REAL_TIME`. Display age and publication eligibility with each value; keep the immutable cutoff forecast separate from current action eligibility. |
| The comparative scoreboard misses v2 | `meta_outcomes._aggregate` pairs against the hardcoded `experimental_meta_v1` key. Current v2 needs version-aware pairing. Cohort counts exist, but pooled summaries and volume thresholds do not constitute dependence-aware statistical evidence. |
| Evidence breadth exceeds usable specificity | The inspected packet has 211 evidence items and 70 news items, yet all five geopolitical panels have zero explicit transmission links. Latest SEC snapshots do not provide a fully comparable multiyear, point-in-time fundamental panel. More documents alone will not resolve this. |

Key source files:
[forecast](../python/src/spy_predictor_quant/meta_forecast.py),
[agents](../python/src/spy_predictor_quant/meta_agents.py),
[evidence](../python/src/spy_predictor_quant/meta_evidence.py),
[product](../python/src/spy_predictor_quant/meta_product.py), and
[outcomes](../python/src/spy_predictor_quant/meta_outcomes.py).
Artifact:
[completed forecast](../reports/meta-analysis/agents-20260915T190053443022Z-7ac8a380/structured-forecast-v2-verified.json).

### Ten implementation phases

#### 1. Repair the forecast, evidence, and decision contracts

**Deliverables**

- Define separate immutable targets for prior-close analysis and prediction from
  a qualified current observation. Record information cutoff, source availability,
  reference timestamp/price/feed, target timestamp, session calendar, and price
  versus total-return basis. Do not relabel old forecasts or mix these targets in
  evaluation. A quote midpoint is not automatically an executable entry price.
- Make claim IDs globally unambiguous within a run. Separate atomic observations
  from horizon-specific directional hypotheses and their supporting/opposing edges.
- Apply every deterministic rejection before scoring, including row-level
  rejections without claim IDs. Audit trigger value, units, provenance, comparison,
  interval, expiry, and already-satisfied state. Preserve supported invalidations
  and exact review events; represent unavailable ones explicitly.
- Add version-aware outcome pairing and cohort-specific summaries. Distinguish
  full-quantitative fallback from a model that actually used agent features.
- Bind displayed price age and publication eligibility to the value. Preserve the
  original cutoff forecast and record a separate freshness-based action overlay.

**Acceptance gate:** adversarial fixtures cannot score rejected evidence, reuse
ambiguous identities, show stale prices as currently live, or pair incompatible
origins/variants. Every forecast and report agree on reference, numbers, action,
invalidation availability, and review condition. Existing ledgers remain immutable.

**Primary surfaces:** `meta_agents.py`, `meta_forecast.py`, `meta_product.py`,
`meta_outcomes.py`, versioned schemas and policies.

#### 2. Build a point-in-time research dataset

**Deliverables**

- Create versioned observation and feature tables with `effective_at`,
  `published_at`, `first_seen_at`, `available_at`, `captured_at`, source version,
  units, revision identity, and quality flags. Unknown availability timestamps
  must not be treated as evidence that historical data were usable.
- Reconstruct SEC periods consistently: quarterly versus year-to-date flows,
  trailing twelve months, comparable growth, margins, cash conversion, accruals,
  inventory, capital expenditure, dilution, leverage, and share/split consistency.
  Include filing changes and management guidance with availability timestamps.
- Store macro release vintages and release calendars; separate actual releases,
  contemporaneous expectations, revisions, and derived surprises. Expectations
  without a qualified source remain missing. Do the same for earnings estimates.
- Version ETF holdings and exposures. Treat QQQ and its constituent stocks as
  overlapping exposures. Add breadth, sector/market returns, credit, rates,
  liquidity, volatility, and options features only with qualified history/feeds.
- Train on a broader, historically defined stock/ETF panel while continuing to
  produce five-symbol reports. Control survivorship, delistings, corporate actions,
  and liquidity selection; do not claim broad applicability from five AI-heavy names.

**Acceptance gate:** an as-of query reconstructs what was available at the cutoff;
later revisions/filings cannot change a frozen historical feature vector. Tests
cover after-close releases, holidays, splits, amended filings, and missing feeds.
Document coverage, acquisition cost, licenses, and blocked histories before choosing
models that depend on them. Do not purchase subscriptions automatically.

**Primary surfaces:** capture adapters, `meta_evidence.py`, proposed point-in-time
store and feature registry, dataset manifests.

#### 3. Build the experiment system before searching for winners

**Deliverables**

- Use chronological walk-forward evaluation. Fit imputation, scaling, feature
  selection, hyperparameters, and calibration only within each training window.
  Keep all symbols from the same date together. Purge overlapping label intervals;
  determine gaps from actual feature/label information windows.
- Pre-register a small candidate set and keep a trial ledger, including failures.
  Reserve an untouched final period. Evaluate 5/21/63-session targets separately.
- Baselines: unconditional historical frequency, market/sector-conditioned model,
  simple momentum, regularized linear model, current heuristic, and quant-only
  versus quant-plus-agent features on exactly the same observations.
- Score probability quality with Brier/log loss, return distributions with proper
  distribution/quantile scores, interval coverage and width, and direction accuracy
  relative to its base rate. Report abstention coverage and performance together.
- Estimate paired improvement with time-block inference, accounting for overlapping
  horizons and cross-symbol dependence. Report origin counts, uncertainty, and
  an explicit effective-sample methodology. Fifteen rows per run are not fifteen
  independent market experiments.
- Treat historical LLM extraction as potentially contaminated by model training
  knowledge. Use source-only extraction, ticker-blind perturbations, human audits,
  and prospective frozen-model evaluation; masking names does not prove no hindsight.

**Acceptance gate:** synthetic leakage and shuffled-label controls fail as expected;
each promoted variant beats a preregistered strong baseline with dependence-aware
uncertainty on the primary metric, without unacceptable secondary regressions.
Choose material improvement and sample-power requirements before inspecting results.
An inconclusive result remains inconclusive, even after an arbitrary row threshold.

The need to assess LLM temporal contamination is supported by
[Glasserman and Lin's study](https://arxiv.org/abs/2309.17322).

#### 4. Convert news into dated events, surprises, and exposure paths

**Deliverables**

- Cluster syndicated/updated stories into events using entity/event keys, text
  similarity, and publication time. Preserve first publication, first system
  availability, corrections, contradictions, and independent-source count.
- Extract event type, affected entity, actual change, prior known state,
  expectation source, surprise if measurable, and expected transmission delay.
  A positive headline is not inherently a bullish return signal.
- Build a dated exposure graph: customer/supplier, competitor, geographic revenue,
  export restrictions, input costs, rates sensitivity, and ETF holdings. Every
  edge needs evidence, validity dates, and confidence; model-inferred links remain
  hypotheses until verified. Unknown exposure is not zero exposure.
- Measure pre-event positioning proxies and post-event market/sector-adjusted
  price/volume reaction. Define the prediction origin after the measured reaction
  window; never use a later reaction to predict an earlier entry.
- Extract changes in filings and guidance, including changed risk language,
  customer concentration, inventory, capital expenditure, and cash conversion.

**Acceptance gate:** manually reviewed event sets meet predeclared entity, novelty,
timestamp, and factual extraction criteria. Duplicate headlines cannot create
extra votes. Every geopolitical conclusion has an exposure path or explicit
missingness. Predictive usefulness is assessed later, separately from extraction.

Event classification is motivated by
[Which News Moves Stock Prices?](https://www.nber.org/papers/w18725);
filing-change features by [Lazy Prices](https://www.nber.org/papers/w25084).
These are hypotheses to reproduce in our setting, not inherited performance claims.

#### 5. Discover signals and reject redundant correlations

Build a bounded signal laboratory, not an unlimited search over indicators.

| Question | Candidate methods | Required checks |
| --- | --- | --- |
| Is there a basic relationship? | Rank correlation, rolling lead/lag association, market/sector residualization | Out-of-sample direction and magnitude; confidence intervals; no future residualization inputs |
| Which correlated indicators add information? | Elastic net/group regularization, clustered feature groups, blocked stability selection | Stable selection across windows; grouped ablations; incremental value over existing factors |
| Is the relationship nonlinear? | Mutual information screening, shallow boosted trees, generalized additive models | Training-only screening, permutation controls, bounded hyperparameter search |
| Do effects arrive with delays? | Sparse VAR/Granger tests; PCMCI as an optional research candidate | Autocorrelation, stationarity changes, hidden confounding, multiple testing; predictive timing is not proof of causality |
| Which events affect which exposures? | Event studies, matched comparisons, local projections, event × surprise × exposure interactions | Pre-trends, simultaneous announcements, overlapping events, matching based only on known information |
| Does usefulness change with conditions? | Regime interactions, rolling coefficients, change-point monitoring | Online regime assignment only; no retrospectively smoothed regime labels in live simulations |

Each signal card records hypothesis, formula, input timing, expected horizon,
supporting mechanism, sample/effective-sample counts, effect uncertainty, baseline
comparison, cost sensitivity, regime behavior, decay, redundancy cluster, and
number of trials. Use a train-only redundancy graph so RSI, moving averages,
momentum, and five agents repeating the same chart do not masquerade as independent
evidence. Disagreement can be tested as a risk feature instead of an automatic veto.

Operationalize Maru Cape-inspired cycle ideas as explicit, reproducible hypotheses
about growth, inflation, liquidity, credit, real rates, and risk appetite. Document
the intended source/formula before claiming to implement a named indicator.
Test each component and interaction against simpler baselines.

**Acceptance gate:** no signal advances on in-sample correlation alone. Promote
only preregistered out-of-sample improvements stable enough for the proposed use;
archive failed signals and retain their trial count.

Method references: [Stability Selection](https://stat.ethz.ch/Manuscripts/buhlmann/stabilityselection.pdf)
and [PCMCI](https://pmc.ncbi.nlm.nih.gov/articles/PMC6881151/).
Their theoretical guarantees depend on assumptions; changing to financial block
sampling does not automatically preserve those guarantees.

#### 6. Learn horizon-specific distributions and calibrate them

**Deliverables**

- Replace fixed score-to-probability conversion with competing fitted models:
  regularized logistic/linear or additive models first, then shallow gradient
  boosting if justified. Model market/sector and instrument-specific behavior
  explicitly, using pooled/hierarchical estimates where individual histories are thin.
- Predict both direction and return/risk distributions. News can affect dispersion
  and downside tails without changing the mean. Separate absolute return from
  excess return; outperforming QQQ can still mean losing money.
- Use training-only out-of-fold probability calibration. Assess reliability by
  horizon, market condition, and data-availability pattern when sample sizes permit.
  Do not force impressive-looking probabilities or prescribe a target hit rate.
- Compare simple residual/quantile intervals with adaptive conformal methods.
  Respect delayed 21/63-session labels; long-run coverage is not a guarantee for
  every stock, event, or market regime. Allow explicit out-of-distribution status.
- Compare feature-group ablations, including removing all LLM features. Retain
  agent-derived features only when their measured contribution justifies them.

**Acceptance gate:** the model passes Phase 3 gates, improves probability quality
over the strongest baseline, and has documented interval coverage/width and tail
behavior. Without enough evidence, retain the better baseline and mark the
challenger experimental.

The comparative-model approach is informed by
[Gu, Kelly, and Xiu](https://www.aqr.com/insights/research/journal-article/empirical-asset-pricing-via-machine-learning).
Adaptive intervals are a candidate based on
[Gibbs and Candès](https://arxiv.org/abs/2106.00170), subject to the limitations above.

#### 7. Redesign agent roles, prompts, and execution around measurable work

Replace repetitive directional essays with distinct contracts. Keep deterministic
arithmetic and fitted forecasts in code; use agents where interpretation helps.

| Stage | Required prompt/output change | Evaluation |
| --- | --- | --- |
| Evidence preparation | Identify exact entity, units, period, publication/availability time, source span, and change from prior known state. Return missingness explicitly. | Entity/time/unit accuracy; unsupported extraction rate |
| Technical | Read calculated features; describe trend, liquidity, relative strength, event reaction, and measurable conditions by horizon. Do not recalculate indicators or invent predictive strength. | Numeric grounding; redundancy; incremental feature value |
| Fundamental/ETF | Separate business quality, change in economics, valuation, expectations, and holdings exposure. Mark incomparable periods and unknown consensus. | Period consistency; exposure accuracy; surprise extraction |
| Macro/cycle | Separate level, change, and surprise. Explain a sourced exposure path and timescale. Keep stress scenarios separate from estimated event probabilities. | Correct timing; exposure support; risk/return contribution |
| News/geopolitics | Identify novel events and dated exposure paths; distinguish observed facts from hypothetical escalation. Report reaction already observed at cutoff. | Event deduplication; verified links; temporal integrity |
| Evidence critic | Decide factual validity, timing, numeric agreement, contradictions, and source independence. Cannot promote a true fact to a predictive signal. | Seeded-error detection; false-rejection rate |
| Independent challenger | Examine the same facts without seeing the first agent's conclusion; identify the strongest countercase and falsifiable discriminator. | Counterevidence recall; resistance to anchored conclusions |
| Research planner | Request a bounded missing observation only when it may change a decision or materially reduce uncertainty, considering latency/cost. | Decision-relevant retrieval yield; budget and latency |
| Report editor | Explain frozen model/action outputs, measured drivers, countercase, and review conditions. Never add numbers or change the decision. | Numerical consistency; unsupported claims; reader comprehension |

Common hypothesis template:

> State the observed fact and source. State what changed and when it became
> available. State the proposed mechanism and horizon. Separate measured
> predictive evidence from an untested hypothesis. Identify the strongest opposing
> evidence and an observable condition that would change this assessment. If the
> expectation, exposure, or timing is unknown, name that missing field.

Schema changes: separate `observation`, `event`, `exposure_edge`, `hypothesis`,
`validated_feature`, `model_output`, and `decision` records, each with stable IDs,
provenance and versions. Do not make critic/editor roles regenerate unnecessary
symbol/horizon forecast rows. Generate repetitive structures deterministically.

Execution changes: cache slow fundamental/exposure work by content identity;
refresh fast prices/events independently. Invalidate dependencies precisely.
Retry only failed compatible stages, using role-specific prompt/schema/model/input
identities. Bound retrieval, tokens, time, and repair attempts. Different role
names or models do not establish independent evidence.

**Acceptance gate:** frozen prompt evaluations include duplicate stories, removed
sources, wrong units, incompatible horizons, stale observations, adversarial source
instructions, reordered documents, and ticker masking. Grade factual extraction
and predictive contribution separately. Additional agents must justify their
cost/latency on this evaluation; disagreement alone is not useful diversity.

#### 8. Turn forecasts into explicit, testable decisions

**Deliverables**

- Replace undifferentiated WAIT with reasons such as `WAIT_DATA`, `WAIT_EVENT`,
  `WAIT_PRICE_CONFIRMATION`, `NO_MEASURED_EDGE`, and `OUT_OF_DISTRIBUTION`.
  Keep reason codes separate from the public action if compatibility requires it.
- Define critical inputs from the selected model and decision's dependencies,
  rather than requiring three agreeing specialists for every situation. A missing
  geopolitical forecast need not veto a qualified technical model; a missing
  current quote can still prevent an entry assessment.
- Evaluate expected payoff, downside, uncertainty, spreads, fees, liquidity, and
  event risk. `P(up)>50%` alone does not establish positive expected net payoff.
  Treat uncertainty as a reason to reduce decision strength, not invent precision.
- Emit confirmation, expiry, invalidation, and next-review fields with observable
  definitions. Distinguish thesis invalidation from an executable stop. A trigger
  already met before publication is not a future setup.
- Avoid personalized hold/reduce instructions without position context. Keep
  hypothetical existing-position research separate from new-entry research.
- Create a separate conditional-entry evaluation lane: trigger observation,
  realistically available execution price, subsequent path, transaction costs,
  and expiry. Never score an untriggered setup as a completed trade.

**Acceptance gate:** every action has a traceable policy reason and next observable
condition. Evaluate utility and abstention together; an always-WAIT policy cannot
win by excluding every difficult observation. No forced buy/sell quota.

#### 9. Make explanations clear and faithful to the actual model

**Deliverables**

- First screen: five symbols × three horizons. Each cell shows action and reason,
  calibrated/experimental status, probability target, return range, and data age.
  Mark unsupported cells explicitly; make common sector/ETF overlap visible.
- One concise card per symbol: **what changed; three main measured drivers;
  strongest countercase; what is already reflected in the observed reaction;
  next decision condition; expiry/review time**. Claiming something is fully
  priced in requires evidence; otherwise say the degree is unknown.
- Show comparison to the baseline and prior report. Explain whether a change
  came from price, a new event, model/version changes, or corrected information.
- Derive numeric driver contributions from the fitted model using documented
  grouped attribution/ablation methods. Distinguish local explanation from
  retrained out-of-sample ablation. Correlated-feature attribution is not causal
  effect; never ask an LLM to invent contribution percentages.
- Expandable detail: source passage, timestamp, calculation, exposure path,
  uncertainty, signal validation record, and missing fields. Label factual
  observation, statistical association, and scenario assumption separately.
- Remove repetitive generic market prose and forced cross-symbol rankings when
  differences are smaller than uncertainty or all setups are unavailable.

**Acceptance gate:** deterministic checks find zero changed forecast numbers or
action contradictions. In reader tests, users can identify the target, main
drivers, missing evidence, downside, and next review without opening a raw packet.
Evaluate clarity separately from persuasive tone and trading performance.

#### 10. Run prospectively, challenge the system, and improve again

**Deliverables**

- Freeze champion/challenger versions and publish append-only predictions before
  outcomes. Keep on-demand analysis separate from registered evaluation windows.
  Never rewrite predictions after observing returns.
- Run five-symbol market-session exercises covering normal trading, earnings,
  macro announcements, stale/missing feeds, and interrupted agent stages. Set
  per-stage latency/freshness budgets; revalidate current price and action
  eligibility before publishing. A long research run must not masquerade as live.
- Monitor Brier/log loss, interval coverage, baseline deltas, costs, coverage,
  stale-publication rate, event extraction quality, source failures, and latency.
  Monitor concentration and common market drivers across the five names.
- Classify misses: data defect, timing defect, exposure error, feature failure,
  regime shift, calibration error, execution assumption, or explanation defect.
  Review successes too; a correct direction can have an unsupported explanation.
- Run a second full-system improvement cycle using paired ablations: no agents,
  no news, no macro, no fundamentals, and simpler prompts/models. Use new holdout
  periods or prospective evidence after tuning; do not repeatedly consume the
  same holdout. Remove components that fail to earn their complexity.
- Promote or roll back against preregistered statistical and operational gates.
  A 63-session label requires 63 sessions to mature; engineering completion must
  be reported separately from demonstrated prospective predictive improvement.

**Acceptance gate:** reproducible reports and decisions, reliable live operation,
and documented prospective evidence for any accuracy claim. If a challenger fails,
retain the stronger baseline and publish the negative result.

### Highest-value unconventional hypotheses to test

These are bounded experiments, not claims of existing edge:

1. **News/reaction mismatch:** positive news with negative sector-adjusted price
   reaction, or negative news absorbed without a decline. Test surprise, prior
   run-up, liquidity, and subsequent drift jointly at an eligible later origin.
2. **Economic propagation delays:** customer capital-expenditure changes reaching
   suppliers at different lags. Require dated, verified business relationships;
   compare with ordinary sector momentum to detect relabeled beta.
3. **Disclosure change over disclosure sentiment:** newly altered guidance/risk
   passages and cash-conversion changes versus another generic earnings summary.
4. **Evidence conflict as information:** strong trend with deteriorating cash flow
   may affect downside or regime-transition risk even if direction remains unclear.
5. **Separate clocks:** fast event/liquidity features and slow business/cycle
   features should expire and influence horizons differently, instead of receiving
   one permanent bullish/bearish vote.
6. **Decision-sensitive research:** estimate whether resolving a missing fact could
   cross an action threshold before spending time retrieving it. Begin with a
   deterministic sensitivity/budget rule; learn retrieval value only with evidence.

### Delivery order and definition of success

Phase 1 is immediate correctness work. Phase 2 supplies the historical foundation;
Phase 3 must exist before signal selection. Phases 4 and 5 feed Phase 6. Prompt
evaluation in Phase 7 can begin earlier, but cannot claim predictive improvement
without Phases 3 and 6. Phase 8 defines decision contracts before Phase 9 presents
them. Start append-only research observations early; Phase 10 promotion waits for
mature outcomes and all necessary gates.

The first useful release should be a correct, readable baseline with honest
missingness and a working comparison harness. The next release should add only
validated event/features/models. The final release should demonstrate reliable
five-symbol live operation and perform the second improvement cycle.

Success is **better out-of-sample probability/risk estimates, useful decisions at
measured coverage, and explanations that faithfully expose evidence and uncertainty**.
No particular algorithm, number of agents, or headline hit rate is a success
criterion by itself. No predictive improvement is asserted by this plan.

## Immediate next-session work order

1. Read [IMPROVEMENT_PLAN_3_HANDOFF.md](IMPROVEMENT_PLAN_3_HANDOFF.md), inspect
   `git status --short`, and preserve all modified/untracked files and immutable
   runs. Phase 1 contract repairs and the subsequent five-step engineering work
   already exist; do not restart them.
2. Read the synthesis diagnosis record before more model calls. Exact decimal
   transport is repaired; archived and newly captured full chains pass through
   registered recovery. The ordinary full-payload fresh stream still failed once.
   Improve that path's reliability or integrate the verified compact path with
   explicit budgets; do not repeat completed specialists or blind long retries.
3. Preserve the verified 15-row numerical/product receipts. A new current-entry
   demonstration needs new capture and timely publication. Keep old packet cutoff
   and publication freshness honest. No retrospective forecast issuance.
4. Continue existing ETF diagnostics and separate prospective collection without
   requiring broad stock-universe history. Preserve the current NOT_QUALIFIED
   manifest and all statistical thresholds. Qualify each required source family
   separately; a historical universe is relevant to broad stock selection, not
   a universal prerequisite for the fixed ETF price study or engineering work.
5. Run focused checks after relevant code changes, then `npm run check`. Existing
   validation: TypeScript build, 28 JS, 483 Python (the final logging-only change
   reran build/JS; Python hashes match the full check). No data purchase is needed
   for this engineering work; IBKR Gateway can remain closed.
6. Keep prospective issue and outcome evaluation separately governed. Recheck
   current dates/status before any authorized issue; collection alone does not
   register forecasts. No G11 allocation, trading or unattended installation is
   authorized by this handoff. VIX/VIX3M access work remains deferred unless the
   user requests it.

### GOLDEN GOAL improvement plan — implemented September 15, 2026

User request: make probabilities, exact conditional actions and the overall META
conclusion crystal clear. Saved September 15 after the September 14 report audit.
The following six work packages record the implemented increment across
G2/G4/G7/G8/G10 and its original acceptance criteria.

Implementation result: all six packages below are implemented in the v3 dynamic
agent schemas, v2 policy/structured-forecast/product schemas, reordered runner,
publication freshness projection, decision-first Markdown/HTML/JSON views and
regression tests. Frozen v1 artifacts remain readable and are never rewritten.
The second-pass audit also bound intraday bar/trade/quote values to separate
timestamps, enforced claim stance in horizon support/opposition, checked symbol
summaries against their horizon rows and de-duplicated exact cross-role evidence
signatures. These changes create a new governance cohort and do not establish
calibration or predictive skill.

**Audited defects and regression evidence**

- Astra synthesis currently precedes `create_structured_forecast`, so it never
  sees the final probabilities or threshold-generated recommendations.
- Specialists emit one symbol-wide direction despite claims spanning 5/21/63
  sessions. Opposite horizon views collapse into `MIXED`.
- `MIXED` and `NEUTRAL` both score zero. Conflict is not genuine neutrality.
- Evidence-quality percentages reward claim/citation counts; approximately 92%
  is neither calibrated confidence nor measured predictive reliability.
- Probability thresholds can produce `ACCUMULATE_CONDITIONALLY` without a
  measurable entry condition or decisive missing-data restriction.
- Critic objections do not mechanically exclude rejected claims from scoring.
- The first horizon-applicable synthesis claims become supporting conditions
  without a structured distinction between support, opposition and triggers.
- In the audited META five-session forecast, P(up) = 57.3% means terminal price
  above the September 11 close of $648.03, not profitability buying intraday.
  Bear/neutral/bull probabilities are 31.2% below -2%, 23.5% within +/-2%, and
  45.3% above +2%, relative to that same reference. These are compatible events
  with different definitions, not inconsistent estimates.
- The distribution is experimental/uncalibrated. Its volatility-scaled mean can
  make five- and 21-session directional probabilities identical by construction.
  Mean simple return is not the median outcome or a price target. Prompt edits
  cannot establish predictive skill or repair statistical assumptions by themselves.

**1. Probability and freshness contract**

- Each symbol/horizon must carry reference price, observation timestamp, forecast
  origin, target trading-session date, event definitions, and daily-close versus
  intraday-entry basis. A daily-close forecast must not imply profit from buying
  at the displayed intraday price. Intraday-origin forecasts need a separately
  specified and versioned methodology, not merely relabeling the current output.
- Display calibration status, source coverage, data age and material missingness.
  Distinguish probability of any terminal gain from bull/bear threshold events;
  neither is a probability of touching a target or avoiding a stop along the path.
- Validate freshness at publication as well as capture. The audited run froze
  evidence at 17:21:43 UTC and finished synthesis about 28 minutes later.
  Quote receipt time is not observation time; bind each displayed value to its
  own timestamp. A new quote must not make an older last trade appear fresh.
- September 11 was a legitimate previous completed session on September 14,
  not a current intraday observation. Distinguish live, delayed, completed-session,
  stale and missing states, and do not call a merely age-eligible release the
  latest official release without verifying release identity.
- Define explicit critical versus advisory evidence gaps and their action gates.
  Keep old FRED closes separate from current volatility; no silent substitution.

**2. Reorder analysis and make criticism enforceable**

Target order: frozen evidence -> horizon-specific specialists -> critic claim
decisions -> numerical forecast and action gates -> Astra final conclusions ->
consistency validation -> immutable report.

- Retain five specialists, critic and final synthesis; final Astra receives the
  actual immutable numerical output, policy actions and accepted claim IDs.
- Critic returns structured `ACCEPT`, `REJECT` or `NEEDS_VERIFICATION` for material
  claim IDs, with reasons/corrections. Rejected claims cannot influence scoring;
  unresolved material claims trigger explicit restrictions.
- Separate accepted contextual features from synthesis prose to remove the
  current downstream dependency on a synthesis that has not seen the numbers.
  If final synthesis discovers a new material contradiction, fail closed to
  review/WAIT; do not silently recompute probabilities after writing conclusions.
- Version the agent schemas, prompt/dependency identities and resume contracts.
  Old cached role outputs cannot bypass a changed contract or dependency.

**3. Decision-oriented specialist prompts and schemas**

- For every symbol and each 5/21/63-session horizon, require direction, strongest
  support, strongest opposition, action implication, confirmation, invalidation,
  missing evidence and review time/event. Distinguish mixed, neutral and unknown.
- Represent measurable triggers with a cited field/level, comparison, units,
  confirmation interval and expiry. Unsupported levels remain unavailable; do not
  invent precise numbers to satisfy the schema.
- Technical: sourced support/resistance and exact confirmation rules instead of
  vague "trend repair". Fundamental: separate company quality, valuation and
  attractiveness of entering now. News: deduplicated new information and verified
  publication/event dates. Macro/geopolitical: asset-specific transmission and
  enacted policy versus proposed/hypothetical scenarios.
- Preserve packet-only reasoning, role projections, FACT/INFERENCE labels and
  exact numeric pointers. Keep orchestration documentation and runtime prompts
  synchronized; agents cannot retrieve omitted data with their current empty tools.
- Replace claim-count-based apparent confidence with transparent evidence-family
  coverage and limitations. Repetition and correlated inputs must not add confidence.

**4. Astra final decision mandate**

Proposed central instruction:

> Using the supplied final numerical forecast and accepted claims, explain what
> to do now, what would change that action, and what could go wrong. Do not invent
> or modify probabilities. Resolve contradictions explicitly. If a material
> contradiction or evidence gap remains, recommend waiting and identify the
> precise requirement for reassessment.

- Let Astra explain supplied numbers through exact references; retain the ban on
  inventing probabilities rather than the current blanket ban on discussing them.
- Give one unambiguous current action per symbol/horizon, aligned with the policy
  and evidence gates. Separate considering a new position from already holding.
- WAIT must specify what is awaited and when to reassess. Conditional actions
  need observable triggers and invalidation, not just probability thresholds.
- Personalized sizing, account allocation and order submission remain out of scope.

**5. GOLDEN RECOMMENDATIONS / GOLDEN CONCLUSIONS first screen**

- One short overall conclusion and at most five critical cross-market findings.
- One concise decision row per symbol/horizon: action now, conditional trigger,
  invalidation, clearly defined probability, evidence blocker and next review.
- Explain the action in plain language, including why a seemingly bullish number
  may still mean WAIT. Keep support, counter-case and conditions distinct.
- Label research priority separately from buy attractiveness. Permit ties and
  "no attractive setup" rather than forcing a misleading buy-like ranking.
- Replace misleading confidence percentages with transparent coverage/limitations.
  Keep detailed agent prose, source dates and audit trails expandable in HTML;
  Markdown and JSON must express the same decisions and freshness semantics.

**6. Acceptance tests, rollout and governance**

- Start with the preserved five-symbol x three-horizon report as a regression
  fixture; no new paid model run is required to define or test the contract.
- Test action/prose consistency; exact reference prices and target sessions;
  event probabilities and sums; horizon-specific mixed/unknown views; rejection
  exclusion; duplicated-claim invariance; and measurable conditional triggers.
- Test capture-to-publication aging, value/timestamp binding, closed-market
  labeling, delayed/frozen data, stale-not-live rendering and critical-gap gates.
- Test schema, dependency/resume identity and HTML/Markdown/JSON parity. Explicitly
  preserve historical packets, forecasts, failed attempts and quant-only comparators.
- After offline/focused tests and full checks pass, run one bounded fresh
  on-demand smoke with the requested universe. Do not register it retroactively.
- Changed probability methodology/policy or material prompt/data dependencies
  require new version/cohort identities. Never alter frozen historical forecasts
  or describe these clarity changes as evidence of calibrated predictive skill.

Implementation touchpoints: `python/src/spy_predictor_quant/meta_agents.py`
(runtime roles, schemas, projections, dependencies), `meta_analysis.py` (ordering,
capture/freshness), `meta_forecast.py` (features/distribution/action gates),
`meta_product.py` (report projection/rendering), their tests, relevant `schemas/`
and `config/meta-forecast-policy-v1.json` successors, and
`docs/META_ANALYSIS_PROMPT.md` / `docs/META_ANALYSIS_PLAN.md`.

### Deferred VIX/VIX3M data-access handoff — verified September 15

The user will resume troubleshooting in a later session. Do not purchase anything
or assume this is blocked on Massive. The earlier connection-refused result is
superseded by a successful Gateway test and index diagnostic:

| Check | Verified result |
| --- | --- |
| Gateway | `127.0.0.1:4002`, configured paper/read-only client; server-time probe passed |
| VIX | `IND`, `CBOE`, USD, conId `13455763`, CBOE Volatility Index |
| VIX3M | `IND`, `CBOE`, USD, conId `47511905`, CBOE S&P 500 3-Month Volatility Index |
| VXV alias query | Error 200; use the verified VIX3M contract, not guessed aliases/futures |
| Live requests | Both returned 354: requested market data is not subscribed |
| Delayed requests | Both returned data type 3 and 10167: displaying delayed data |
| Returned VIX last | 17.10, timestamp September 14 20:12:16 UTC / 16:12:16 New York |
| Returned VIX3M last | 19.29, timestamp September 14 20:10:46 UTC / 16:10:46 New York |

The check received data around September 15 03:51 UTC, outside both contracts'
returned trading hours. These values are delayed last observations, not live or
verified official closes, and their timestamps differ. Daytime refresh cadence
and a time-aligned ratio have not been qualified. Raw diagnostic output is in the
conversation; no persistent diagnostic script/artifact was created.

Closed markets explain lack of new ticks, but IBKR documents error 354 as missing
live entitlement for the requested instruments. This proves missing access for
the tested paper login, not that the live account has no subscription. Frozen
type 2 requires live entitlement; delayed-frozen type 4 is a separate fallback.

Next requested diagnostic: keep paper/read-only settings, check existing live-user
subscriptions and sharing with the Gateway paper username, then retest both live
and delayed types during overlapping hours. September 15 at 10:00 New York /
11:00 Buenos Aires was the suggested test time; if resuming later, select a new
valid session and verify schedules rather than reusing that date. Success is
actual type 1 plus advancing source timestamps; do not infer live access solely
from nonempty prices. No port change or disabling read-only is needed.

Portal paths documented at review: Settings -> Trading Platform -> Market Data
Subscriptions; Settings -> Account Configuration -> Paper Trading Account ->
share real-time market data. Cboe Streaming Market Indexes was listed at $3.50/month;
verify current coverage/price before any user-approved purchase. Massive indices
snapshots and current minute aggregates both returned 403 with the current key.
IBKR index capture still needs a separate adapter: the existing contract loader
only permits STK/FUT and the SPY/QQQ/ES/NQ universe. Do not destabilize that frozen
workflow just to add the two IND contracts. Proposed report capture cadence is
30–60 seconds for entitled live data, with source-age and inter-leg skew checks;
polling delayed data faster does not remove its delay.

Primary references:

- [IBKR error codes](https://www.interactivebrokers.com/docs/tws-api/doc/error-handling/error-codes)
- [IBKR live/frozen/delayed data types](https://www.interactivebrokers.com/docs/tws-api/doc/market-data-delayed/introduction)
- [IBKR market-data pricing](https://www.interactivebrokers.com/en/pricing/market-data-pricing.php)
- [IBKR paper-account data sharing](https://www.ibkrguides.com/orgportal/papertradingaccount.htm)
- [Massive indices plans](https://massive.com/indices)

### Recorded verification and latest completed report

Latest verification passed on September 15, 2026: TypeScript compilation, 19
TypeScript tests, and 424 Python tests. The focused analysis/forecast/product/
observation/outcome suite passed all 76 tests, final v2 forecast and product
schemas validated their persisted artifacts, and `git diff --check` passed. The
G9 ledger remains unchanged: 30 `NOT_DUE`, zero `READY`, zero `SCORED` and zero
`WAITING_FOR_DATA` records. The separate static prospective cohort is also
`NOT_DUE`, with zero issued origins and next origin September 30. No September 15
on-demand artifact was registered prospectively.

The completed v3 seven-role run is
`reports/meta-analysis/agents-20260915T190053443022Z-7ac8a380`, resumed from the
fresh regular-session packet run at
`reports/meta-analysis/analysis-20260915T162815830204Z-d9e1a580/packet.json`.
The resume reused five specialists plus Sol's 47-claim critic audit and retried
only Astra after a provider WebSocket close. Final status is
`COMPLETED_UNCALIBRATED_RESEARCH`, with no failures, 15 immutable decision rows
and five bounded critical findings. The critic accepted 43 claims, rejected one
and marked three for verification. Every policy action is `WAIT` because fewer
than three independent directional evidence families survived the horizon gates;
this is an explicit evidence restriction, not a negative return forecast.

The final persisted forecast is
`structured-forecast-v2-verified.json` under that run (artifact hash
`7a7f51a1dcd9993534ab31c024f6fcdfb54cfaa2650ffb8a5b099ef62106f4b9`,
cohort `2128a53ad9e247d1837b1bed4bbe4f5a4701746cd6870accf4eaff703239b680`).
The readable JSON/Markdown/HTML bundle is `product-verified/` (view hash
`d1df509bba29d39f76ff04073cb8b798deb300ed940703987743e65daee37a7c`).
Its publication state is deliberately `DEGRADED` because the transport/recovery
delay exceeded 15 minutes; individual intraday rows are visibly
`STALE_AT_PUBLICATION` rather than being mislabeled live.

The second effectiveness pass fixed defects found only under real model output:
provider-strict critic audit fields, critic-only versus specialist-only semantic
validation, deterministic quarantine of bad numeric paths and malformed horizon
support, exact duplicate specialist-row normalization with raw stdout retained,
final persisted-forecast schema validation, and failing CLI status for partial
agent chains. A later clean run demonstrated the failing exit status and produced
one exact duplicate fundamental row; the new narrow normalizer collapses only
identical copies and still rejects conflicting duplicates. The final prompt also
spells out stance, summary and JSON-Pointer self-checks. These robustness changes
are covered by the September 15 full test result above.

G10 production-shape smokes also passed: the preserved September 11 packet
rendered five symbols × three horizons plus a six-indicator whole-market strip
and G9 status into hashed JSON, Markdown and self-contained HTML; the operations
doctor returned `OK`; and a September 14 calendar dry run returned `READY` with
`writes: false`.

The September 14 intraday run froze evidence at `2026-09-14T17:21:43Z` for
ANET/QQQ/MU/META/NVDA. It captured live IEX context for all five symbols (ANET
and QQQ explicitly `PARTIAL_GAPS`), evaluated 70 eligible news items including
48 published on the cutoff UTC date, and completed all specialists, Sol critic
and Astra synthesis after fail-closed retries. The successful agent run is
`reports/meta-analysis/agents-20260914T174248057730Z-a4179c4e`; its product is
`DEGRADED`, with current-volatility HTTP 403 failures and additional coverage
limitations. Do not claim volatility is the only limitation. Its source packet is
`reports/meta-analysis/analysis-20260914T172144052875Z-a5bb0b64/packet.json`.
Preserve `meta-report.json`, `structured-forecast.json`, and `product/` beneath
the successful agent run as regression evidence for the saved clarity plan.
That September 14 bundle remains preserved as the pre-v2 regression artifact; it
is readable but does not satisfy the v3/v2 contract by itself.

## Operational calendar

- Recompute the eligible META prospective origin using the scheduler dry run at
  resume time. The previously recorded September 14 window is historical guidance,
  not an instruction to backfill or issue without checking current state.
- September 10 five-session outcomes mature September 17 at 20:20 UTC.
- September 11 five-session outcomes mature September 18 at 20:20 UTC.
- Dry-run `npm run meta:schedule -- outcomes`, then append `--execute` when due;
  before maturity the underlying update is a no-op.
- The static monthly cohort first becomes due after the September 30 close.
  `npm run prospective:status` remains authoritative.
- IBKR Gateway need not stay open. Open it for optional IBKR capture or a future
  IBKR-backed intraday run. Current access is delayed type-3, not real-time.
- QQQ prices are available. Complete QQQ look-through requires browser-saved
  holdings no more than seven calendar days old and a sponsor profile no more
  than 31 calendar days old. Do not automate the Invesco browser endpoint without
  permission.

## Scripted operation recipe — recorded September 14, 2026

Historical runbook: check the current date, scheduler state and the next-session
work order above before execution. Saving the clarity plan does not authorize a run.

The daily workflow is centralized in `scripts/golden-goal-daily.mjs`; its
non-secret watchlist and input paths are in `config/golden-goal-daily-v1.json`.
Do not create or maintain numbered `daily_operation_first.py` files: the single
driver keeps symbol, ETF, model, policy and manual-evidence arguments consistent
across phases. Every write/model phase remains dry-run by default and requires
an explicit `--execute`.

From the repository root, the ordered recipe is:

```bash
cd /Users/juanpablo/jp/projects/spy_predictor

# 1. Readiness. This reads credentials but never prints them.
npm run golden:check

# 2. Optional during-session GOLDEN GOAL analysis; first line writes nothing.
npm run golden:intraday
npm run golden:intraday -- --execute

# 3. Daily prospective forecast: run after 17:25 Buenos Aires time.
npm run golden:close
npm run golden:close -- --execute

# 4. Acquire/score any matured 5/21/63-session outcomes.
npm run golden:outcomes
npm run golden:outcomes -- --execute
```

For the normal after-close workflow, steps 1, 3 and 4 are sufficient; intraday
analysis is optional and is never registered prospectively. Never execute the
second `golden:close` command unless the first reports `would_execute: true`.
The current Sunday dry run correctly reports the September 11 origin as a
duplicate; after the September 14 close plus 25 minutes it should identify the
September 14 origin as `READY`.

The combined driver is also available:

```bash
# Runs readiness plus prospective/outcome dry runs; no research writes.
npm run golden

# Repeats the guards, then executes eligible prospective and outcome work.
npm run golden -- --execute
```

The staged commands are preferred for the first live day because each decision
is visible before the next step. The combined readiness invocation begun during
the September 13 implementation session was operator-interrupted before it
returned; do not describe that particular invocation as a completed check.
Independent evidence established Pi OAuth, a complete resumed seven-role
five-symbol run, Alpaca connectivity, `SEC_USER_AGENT`, the operations doctor,
19 TypeScript tests and 424 Python tests.

Current manual configuration points to the validated QQQ holdings and
sponsor-profile files under `datasets/workbench/manual-sources`. Their embedded
source dates remain authoritative. If they are replaced, update their exact paths
under `holdings_files` and `profile_files` in
`config/golden-goal-daily-v1.json`; never put credentials in that file.

The execute command prints a receipt containing `product_bundle`. Open that
directory's `index.html`, or serve it with:

```bash
npm run meta:product -- serve --bundle /exact/product_bundle/path/from/receipt
```

Read the result in this order: the GOLDEN RECOMMENDATIONS / GOLDEN CONCLUSIONS,
current-vs-completed-close volatility cards, run/probability status, partial
failures and freshness, each symbol's 5/21/63-session probabilities and action,
then evidence-family coverage, disagreement, counter-case and review triggers.
All probabilities remain `EXPERIMENTAL_UNCALIBRATED`; no order is submitted.
IBKR Gateway and a new paid subscription are not required.

## Manual QQQ holdings and sponsor-profile refresh runbook

No account, paid subscription, API key or IBKR Gateway is required for this
manual step. Perform it before a live run when QQQ look-through matters. For the
best live evidence, refresh holdings on the day of the run using the latest date
Invesco displays. Seven days is the hard `CURRENT` limit, not the recommended
refresh interval. Refresh the sponsor profile when its displayed values change;
31 days is its hard `CURRENT` limit.

### 1. Refresh QQQ holdings

1. In a normal interactive browser, open the official Invesco page:
   `https://www.invesco.com/qqq-etf/en/about.html`.
2. Open **Holdings**, select **See all holdings**, and wait for **All QQQ
   holdings** to load. Record the page's displayed **as of** date. Never replace
   that source date with today's date merely to pass the freshness check.
3. Copy the complete displayed table into a spreadsheet. Complete holdings are
   preferred. A top-holdings subset is accepted, but the packet will disclose its
   limited total weight and overlap coverage.
4. Create
   `datasets/workbench/manual-sources/qqq-holdings-YYYYMMDD.csv`, where the
   filename date is the displayed holdings date. Use exactly these columns:

   ```csv
   as_of,source_url,ticker,name,weight_pct,sector
   2026-09-11,https://www.invesco.com/qqq-etf/en/about.html,NVDA,NVIDIA Corp,8.22,Information Technology
   ```

5. Repeat the same `as_of` and official `source_url` on every row. Use one unique
   uppercase ticker per row. Enter `8.22` for a displayed `8.22%`, not `0.0822`.
   Weights must be positive and their sum must not exceed `100.5`. `sector` may
   be blank when the official page does not provide a holding-level sector; do
   not infer it from memory or another undated source.
6. Save as UTF-8 comma-separated CSV. Do not commit or redistribute the sponsor
   table; `datasets/workbench/` is ignored local evidence.

The checked format example is
`examples/meta-analysis/etf-holdings-template.csv`.

### 2. Refresh the QQQ sponsor profile

1. On the same official page, record only currently displayed fund facts, such
   as **Total Expense Ratio** and **Number of Holdings**. Optional supported
   fields are `pe_ratio`, `price_to_book_ratio`, `roe_pct`,
   `earnings_growth_pct`, `distribution_yield_pct` and
   `tracking_difference_pct`; omit any value the sponsor does not display.
2. Copy `examples/meta-analysis/etf-profile-template.json` to
   `datasets/workbench/manual-sources/qqq-profile-YYYYMMDD.json` and replace all
   template values. Example:

   ```json
   {
     "symbol": "QQQ",
     "as_of": "2026-09-13",
     "source_url": "https://www.invesco.com/qqq-etf/en/about.html",
     "metrics": {
       "expense_ratio_pct": 0.2,
       "holdings_count": 100
     },
     "methodology_note": "Official QQQ page accessed 2026-09-13; no separate metric-specific as-of date was displayed."
   }
   ```

3. When a metric has its own displayed as-of date, use that date. When the page
   gives no metric-specific date, `as_of` may be the browser access date only if
   `methodology_note` says so. Percent fields use percentage units: `0.2` means
   `0.20%`. Never use zero as a missing-value placeholder; omit the field.

### 3. Validate the two files before spending on agents

Run an evidence-only capture first:

```bash
node --env-file=.env scripts/meta-analysis.mjs capture \
  --symbols QQQ --etfs QQQ --macro-only \
  --etf-holdings QQQ=datasets/workbench/manual-sources/qqq-holdings-YYYYMMDD.csv \
  --etf-profile QQQ=datasets/workbench/manual-sources/qqq-profile-YYYYMMDD.json
```

Open the printed `snapshot.json`. Do not start the agent run unless:

- `sources` contains both `holdings-QQQ` and `etf-profile-QQQ`;
- `acquisition_errors` contains neither key; and
- the displayed source dates were transcribed exactly.

Then pass the same paths to the real command:

```bash
npm run meta:analyze -- \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ \
  --runner-config config/meta-agent-pi-codex.example.json \
  --market-data-mode intraday --intraday-feed iex \
  --etf-holdings QQQ=datasets/workbench/manual-sources/qqq-holdings-YYYYMMDD.csv \
  --etf-profile QQQ=datasets/workbench/manual-sources/qqq-profile-YYYYMMDD.json
```

After `build`, confirm `packet.json` reports `etf_holdings.QQQ.status` as
`CURRENT`, `etf_sponsor_profiles.QQQ.status` as `CURRENT`, and
`instrument_evidence_profiles.QQQ` lists no unexpected missing family. The
current contract will still show `country_allocation` as missing unless a future
validated sponsor-country input is added; do not interpret that expected gap as
a file failure. Replace every `YYYYMMDD` placeholder in commands with the actual
source date. If the files are absent or stale, the live run is still safe to
execute, but QQQ fundamental/look-through conclusions must remain partial or
abstain.

Recurring live-operation rule: before each important QQQ run, compare the
official holdings `as of` date with the local filename/content. Regenerate the
CSV whenever the sponsor date changes or the file exceeds seven calendar days;
otherwise reuse it. Compare the sponsor facts with the JSON and regenerate it
whenever a value changes or it exceeds 31 calendar days. Price, macro, news and
intraday evidence are captured afresh by the command and need no manual refresh.

The guarded quant-only prospective command is:

```bash
npm run meta:schedule -- prospective \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ \
  --etf-holdings SPY=datasets/workbench/manual-sources/spy-top-holdings-20260909.csv \
  --execute
```

Those symbols are examples, not a fixed universe. ETF files and delayed IBKR
context are optional but must be reported missing when omitted.

After Pi OAuth and the bounded schema smoke pass, start the first structured META
cohort by adding the runner configuration inside the same guarded post-close
window:

```bash
npm run meta:schedule -- prospective \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ \
  --runner-config config/meta-agent-pi-codex.example.json \
  --etf-holdings SPY=datasets/workbench/manual-sources/spy-top-holdings-20260909.csv \
  --etf-holdings QQQ=datasets/workbench/manual-sources/qqq-holdings-YYYYMMDD.csv \
  --etf-profile QQQ=datasets/workbench/manual-sources/qqq-profile-YYYYMMDD.json \
  --execute
```

This runs specialists, critic, synthesis, G7/G8, then registers the quant
comparator and structured experimental META forecast together. Preflight,
capture, packet validation or structured-contract failures prevent registration.
Individual role failures remain recorded and force missing/insufficient context;
they do not silently select that origin out of the prospective cohort.
Run each prospective command once without `--execute` first and proceed only
when the dry run reports `would_execute: true`.

The on-demand completed-close command is:

```bash
npm run meta:analyze -- \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ \
  --runner-config config/meta-agent-pi-codex.example.json \
  --etf-holdings SPY=datasets/workbench/manual-sources/spy-top-holdings-20260909.csv
```

For live IEX intraday context, add:

```bash
  --market-data-mode intraday --intraday-feed iex
```

This uses existing Alpaca credentials. It never silently upgrades IEX to
consolidated coverage. `--intraday-feed sip-delayed` requests explicitly delayed
consolidated evidence subject to the account entitlement.
Resume an eligible interrupted run with:

```bash
python/.venv/bin/python -m spy_predictor_quant.meta_analysis agents \
  --resume /exact/path/to/agents-run-directory
```

## Immutable evidence to preserve

- Successful run: `reports/meta-analysis/agents-20260913T070543331922Z-888dea7c`
- Renewed-OAuth constrained-output stage gate:
  `reports/meta-analysis/agents-auth-smoke-20260913/agents-20260914T003609860649Z-f15d21c2`
- [Full Terra/Sol/Astra audit](../reports/meta-analysis/audits/20260913-full-terra-sol-astra-run.md)
- Packet hash: `59d8445181abcf42785c1bc4022920ec1a89dae6b49dc9d3bb948891e9a4ec31`
- Meta-report SHA-256: `721278b46cf75bc9849680d60eda1b5684d9d822b10f52ce38d9222993a52d7b`
- Synthesis SHA-256: `52f72ce2186fff44cd869778688c791460fc7940e28150d276bed2c4a032b051`
- Aborted run: `reports/meta-analysis/agents-20260913T033409060631Z-5a6bd550`
- September 10 packet/forecast hashes:
  `6a5d97828bc216d5ba05028e7f5d6db55c8a40a013e4d8c1bcea07e5884b0ba3` /
  `f5c0610172460dd47e46c2ebfae96bb3283d266fe6db3840ce57310e6f9ef5a5`
- September 11 packet/forecast hashes:
  `35d07e5f0045f9591bf92c6bd80d1ae8f8e099d0347f77317df11f20914b1b18` /
  `99a6064495d5a034b6eb945ee44382633cae64b79882f1b9dfdbc5eaba085b20`
- Static cohort identity:
  `415e6dcbc1f4964095147591850400e26d81eecb7840e46ab3b8b94483dc1592`

Do not rerun, merge or register the September 13 analysis as a retrospective
September 11 forecast. It qualifies the harness only.

## Closed and separate tracks

Cycle 1 and both power experiments remain stopped. The registered successor
consumed its redesign slot and stopped for computational insufficiency after one
development replication; no locked replications ran. Do not reopen or modify it.

Historical development is complete. Only 42 common dates scored, rankings were
unstable, and neither cycle challenger beat every baseline in both modes. The
missing-session investigation closed as `DATA_REPAIR_NOT_QUALIFIED`. Do not search
or retune those outcomes or open the excluded July 2017–July 2025 evaluation.

The static monthly cohort is a separate frozen unconditional benchmark, not the
GOLDEN GOAL model.

## Governing documents

- [IMPROVEMENT_PLAN_3_HANDOFF.md](IMPROVEMENT_PLAN_3_HANDOFF.md): current continuation
  state, exact artifacts, failed attempts, commands and next implementation task.
- [META_ANALYSIS_PLAN.md](META_ANALYSIS_PLAN.md): current inputs, formulas,
  orchestration and source policy. This handoff's dual-lane product priority
  supersedes its post-close-centered ordering.
- [META_OBSERVATION_OPERATIONS.md](META_OBSERVATION_OPERATIONS.md): prospective
  issue, delayed context and outcome commands.
- [META_ANALYSIS_PROMPT.md](META_ANALYSIS_PROMPT.md): current agent orchestration.
- [MARU_CAPE_APPLICATION_PLAN.md](MARU_CAPE_APPLICATION_PLAN.md): method/source
  attribution and workbench foundations.
- [PROSPECTIVE_OBSERVATION.md](PROSPECTIVE_OBSERVATION.md): static monthly cohort.
- [HISTORICAL_DEVELOPMENT.md](HISTORICAL_DEVELOPMENT.md): closed development track.
- [PROJECT_STRATEGY.md](PROJECT_STRATEGY.md): historical Cycle 1 strategy and
  evidence principles, not the active product sequence.

## Non-negotiable controls

- Freeze inputs before reasoning; new evidence creates a new packet.
- Preserve timestamps, hashes, licenses and missingness.
- Do not count correlated inputs or repeated agent discussion as confirmations.
- Do not equate schema/citation success with truth, calibration or profit.
- Preserve quant-only comparators, failures and negative outcomes.
- Keep credentials, private account data and order tools outside agent requests.
- No live trading or personalized allocation without separate authorization.
- Preserve unrelated work, ignored archives, snapshots and historical reports.

## Maintaining this handoff

Keep this file centered on the GOLDEN GOAL, one active increment, operational
dates and immutable evidence. Replace stale instructions rather than appending
contradictory history. Keep detailed formulas/source rationale in the META and
Maru plans and completed-run detail in immutable reports and audits.
