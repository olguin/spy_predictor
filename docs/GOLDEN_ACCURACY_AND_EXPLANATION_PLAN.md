# GOLDEN accuracy and explanation improvement plan

Prepared: 2026-09-16. Implementation started 2026-09-16; **not all phases are complete**.
See [implementation evidence and remaining gates](IMPROVEMENT_PLAN_3_IMPLEMENTATION.md).
The original audit and planned acceptance criteria are preserved below.

## Objective and assessment

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

### Scope of this audit

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

## Findings that determine the implementation order

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

## Ten implementation phases

### 1. Repair the forecast, evidence, and decision contracts

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

### 2. Build a point-in-time research dataset

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

### 3. Build the experiment system before searching for winners

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

### 4. Convert news into dated events, surprises, and exposure paths

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

### 5. Discover signals and reject redundant correlations

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

### 6. Learn horizon-specific distributions and calibrate them

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

### 7. Redesign agent roles, prompts, and execution around measurable work

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

### 8. Turn forecasts into explicit, testable decisions

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

### 9. Make explanations clear and faithful to the actual model

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

### 10. Run prospectively, challenge the system, and improve again

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

## Highest-value unconventional hypotheses to test

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

## Delivery order and definition of success

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
