# Improvement Plan 3 implementation record

Updated 2026-09-17; next-session handoff saved. Implementation is underway. **The ten-phase plan is not
complete, and no predictive improvement is claimed.** The first engineering
release repairs the forecast contracts and supplies a separate research store
and comparison harness. Qualification gates remain binding.

The subsequent five-step work package now includes actual SEC/ALFRED historical
reconstruction, a separate quantitative-only protocol, a frozen 1,704-row real-data
diagnostic panel/scorecard, pre-outcome feasibility, four live semantic fixtures,
and prospective collection. See the [step-5 runbook](IMPROVEMENT_PLAN_3_STEP5_RUNBOOK.md)
for current commands, receipts and remaining gates. The price panel is explicitly
`NOT_QUALIFIED`; no audit flags were relaxed to obtain the diagnostic scorecard.
The first live v4 chain completed specialists and critic; synthesis recovery is
recorded separately with all timeout/transport failures retained. The adapter
now requests SSE, FRED collection transport is repaired, and the full check passes
20 JavaScript plus 477 Python tests. The separate prospective store contains
120 observations. The final bounded Astra SSE attempt also timed out after
900 seconds. A verified 15-row fallback report works, but full live synthesis
and qualified historical price data remain open acceptance gates.

The sections below describe the initial engineering release and its acceptance
gates; the runbook records the subsequent work and supersedes initial statements
that no real panel, live calls or prompt evaluations had yet been performed.

## Next-session decision

September 17 continuation: [synthesis diagnosis](IMPROVEMENT_PLAN_3_SYNTHESIS_DIAGNOSIS.md)
identified last-digit loss in two returned probabilities. Exact decimal string
transport now preserves the original frozen numbers under unchanged Python v4
validation. Full archived Astra synthesis passed and its product passed all 15
frozen-row checks. The newly captured chain also passed through registered compact
recovery after its initial synthesis stream failed; the original run remains
partial and the recovered publication remains freshness-gated. Latest full
check passed 27 JavaScript and 483 Python tests; final logging changes passed
build and 28 JavaScript tests with Python unchanged. Earlier failures above are
retained historical evidence, not the current archived-synthesis status.

Read [the saved handoff](IMPROVEMENT_PLAN_3_HANDOFF.md) first. The original next
step was bounded synthesis diagnosis with progress instrumentation and a small
contract-valid probe; that work is now completed, with fresh-operation verification
tracked separately. It was not blocked by purchasing historical data.
The earlier blocked-goal record describes incomplete full acceptance; it must not
be interpreted as an instruction to stop all independent implementation.

Historical universe membership is required for broad stock-selection claims,
not for the fixed SPY/QQQ/XLK price diagnostic. Existing revised bars remain useful
under their explicit limitations. No failed audit was changed, frozen protocol
relaxed, or claim of qualified historical replay added by this clarification.
The original ten-phase goal and empirical qualification requirements remain.

## Delivered behavior

New forecasts use `meta-structured-forecast-v3`; new product bundles use
`meta-product-view-v3`; new agent requests use `meta-agent-output-v4`.
Readers retain support for frozen older artifacts. The existing v2 probability
policy and its hand-designed weights remain experimental. A new engine/cohort
identity records implementation hashes; old issued forecasts are not migrated.

- A forecast records its information cutoff, actual reference timestamp and
  price, feed, source availability or explicit unknown availability, calendar,
  target close, and price/corporate-action basis. Completed-close and qualified
  current-trade origins are distinct. Current-trade forecasts require timestamped
  regular-session trades with source provenance and availability; quote midpoints
  are not substituted for trades. The prospective close lane rejects current-trade
  targets rather than pairing them with a different origin.
- Claim IDs must be unique across symbols within each role, making `role:claim_id`
  unambiguous in the run. V4 support/opposition arrays define hypothesis edges for
  each horizon. The legacy `stance` field remains on the wire for strict-schema
  compatibility, but does not control v4 scoring. One fact can support different
  directions at different horizons. V3 retains its legacy stance interpretation.
- Claim and row-level deterministic quarantines reach scoring, ablations, and the
  numerical input supplied to synthesis. Old flattened findings without roles are
  treated conservatively. Incompatible horizons and contradictory edges are
  rejected. Duplicate critic decisions and ambiguous identities fail closed.
- Conditions are audited for availability, finite level, units, provenance,
  supported field/comparison/interval, ISO timestamp expiry, and already-satisfied
  state. The initial supported condition is a USD completed close over one completed
  session. Other condition types remain explicitly unavailable pending a qualified
  evaluator. Accepted invalidations and exact specialist review events survive into
  forecasts and Markdown/HTML. An invalidation is a research condition, not an order.
- Each row says `QUANT_ONLY_FALLBACK` or `QUANT_PLUS_AGENT_HEURISTIC`. Decision
  reasons distinguish data, events, price confirmation and unmeasured edge. Existing
  holdings require position context instead of silently issuing a personalized
  hold/reduce instruction. The policy still uses the existing role-count heuristic;
  model-specific decision dependencies have not been qualified.
- Price states travel with their values, including age and publication eligibility.
  Publication can mark a formerly live value stale. A separate current-entry overlay
  handles price freshness, expired conditions and regular-session eligibility while
  retaining the cutoff forecast. The report verifies synthesis actions/probabilities
  against the frozen numerical artifact and labels cutoff decisions explicitly.
- Outcome pairing recognizes v1/v2/v3 variants and separates cohort, horizon,
  target contract, origin, return basis and actual agent usage. Incompatible groups
  have no pooled paired delta. Legacy aggregate summaries remain descriptive.
  Conditional entries are not counted as executed trades.

## Research infrastructure

`meta_research_data.py` provides append-only, hashed observations, as-of revision
selection, immutable feature snapshots, declared units/formulas and coverage
audits. Unknown availability and quality restrictions exclude records from
as-of features. Quarterly/YTD reconstruction and contiguous trailing-four-quarter
helpers preserve fiscal periods and share bases; incomparable periods and share
bases are rejected. Release surprises require a comparable expectation captured
before the release.

Packet ingestion starts a **new** research observation at conservative ingestion
time. It retains the original cutoff separately and does not turn historical bars
inside a recent download into point-in-time history. Re-ingestion is idempotent.
The initial import contains 40 numerical observations for ANET, META, MU, NVDA
and QQQ from one archived packet. This is not a training panel.

`meta_experiments.py` supplies:

- A bounded candidate set: historical frequency, market/sector, momentum,
  regularized quantitative, current quantitative heuristic, and quant-plus-agent.
- Separate 5/21/63-session chronological folds, grouped by market date across
  symbols, with label-availability purging and an untouched final period.
- Training-only imputation/scaling and a purged trailing training partition for
  calibration and residual intervals. Fitted candidates use regularized logistic
  and ridge models. All remain research candidates, outside production routing.
- Brier/log loss, direction/base-rate comparisons, quantile loss, interval
  coverage/width and abstention coverage/performance.
- Exact paired observations, cross-symbol aggregation by market date, moving-block
  uncertainty, preregistered multiplicity correction and a documented effective
  block-count diagnostic. Row counts alone cannot qualify a result.
- Immutable protocol/dataset/code registration and started/result/failure records.
  Real panels must bind frozen feature snapshots and pass availability, universe,
  corporate-action and licensing audits. Closed research tracks cannot be supplied
  as the new cohort. No command promotes a model or issues a production forecast.
- Exact additive ridge contributions in return units, distinct from causal effects
  or out-of-sample feature-group ablations.

The default protocol is a **proposal requiring a qualified dataset**, not an
already registered real-data experiment. No final holdout has been opened.

`meta_events.py` supplies dated news clustering, explicit unknown independence,
verified exposure-path checks and an origin-safe market-adjusted reaction helper.
Packet construction exposes clusters to specialists; forecast scoring prevents
shared events/evidence from creating extra independent role votes. Clustering
does not certify facts, novelty, expectations, exposure or predictive strength.
Exposure/reaction helpers need qualified dated inputs; they do not invent them.

## Phase gates

| Phase | Engineering delivered | Remaining acceptance work |
|---|---|---|
| 1: correctness | Target/claim/condition contracts, quarantine propagation, pairing, freshness overlays, faithful rendering; adversarial tests and offline five-symbol replay | Fresh live v4 chain qualification is separate from this offline evidence |
| 2: point-in-time data | Observation/feature store, period and surprise helpers, conservative initial import, coverage receipt | Audited broad universe, delistings/actions, historical SEC reconstruction, macro/expectation vintages, ETF/exposure histories, licensing and coverage qualification |
| 3: experiment system | Purged date-grouped folds, frozen protocol/trial ledger, baseline comparisons, block inference, leakage/holdout/null fixtures | Real eligible panel, pre-inspection power review and real preregistration; no empirical winner yet |
| 4: events/exposures | Dated clusters and source dependence in packets/scoring; verified path and reaction helpers | Reviewed event corpus, factual/novelty extraction criteria, actual dated exposure graph, filing/guidance changes |
| 5: signal discovery | Candidate budget is bounded by the experiment protocol | No signal search performed; eligible data and Phase 3 gates are prerequisites |
| 6: fitted distributions | Experimental logistic/ridge candidates, temporal calibration, residual intervals and model contributions in the harness | Real horizon-specific fitting, stability/coverage/ablation evidence and promotion gates; production remains the heuristic baseline |
| 7: agents | V4 horizon edges, unique IDs, dated-event context, prompt distinctions and deterministic numeric/claim gates | Frozen semantic prompt evaluations; independent challenger/planner cost/value evaluation; no new paid agent run |
| 8: decisions | Reason categories, auditable conditions, explicit position-context requirement and publication overlays | Qualified model dependencies, net-payoff/cost/liquidity policies and separate conditional-entry execution evaluation |
| 9: explanations | Frozen cutoff vs current-entry distinction, reference details, invalidation/review, fallback labels and actual heuristic inputs | Reader tests, prior-report change decomposition and fitted-model explanations in the product |
| 10: prospective cycle | Existing immutable lanes preserved; read-only maturity status checked | New cohort registration, live exercises, mature outcomes, miss attribution, paired ablations and second improvement cycle |

The current gate is the audited historical panel. Existing closed cohorts are
not reopened to manufacture a training sample. Model selection and promotion
must wait for eligible observations and the specified uncertainty tests. At the
read-only status check on September 16, the META ledger had 30 `NOT_DUE` records,
zero ready/scored outcomes, and the other prospective lane's next origin was
September 30. A 63-session result still needs its actual future outcome.

## Commands and review artifacts

```sh
npm run meta:research:data -- audit --root datasets/meta-research/improvement-plan-3
npm run meta:research:data -- ingest-packet --root datasets/meta-research/improvement-plan-3 --input PATH_TO_PACKET
npm run meta:research:data -- ingest --root NEW_RESEARCH_ROOT --input OBSERVATIONS_JSON
npm run meta:research:data -- freeze --root NEW_RESEARCH_ROOT --input REGISTRY_JSON --cutoff ISO_TIMESTAMP
npm run meta:research:experiment -- preregister --root NEW_EXPERIMENT_ROOT --protocol config/meta-experiment-protocol-v1.json --manifest QUALIFIED_PANEL_MANIFEST
npm run meta:research:experiment -- run --root NEW_EXPERIMENT_ROOT --panel PANEL_JSON
npm run meta:forecast -- --packet PATH_TO_PACKET --meta-report PATH_TO_REPORT --output NEW_FORECAST_PATH --origin-kind QUALIFIED_CURRENT_TRADE
```

Input/output schemas include `meta-pit-observation-v1`,
`meta-feature-registry-v1`, `meta-structured-forecast-v3` and
`meta-product-view-v3`. The experiment registration pins the protocol,
dataset manifest and implementation hash. Generated records use exclusive writes.

Initial coverage receipt:
[coverage-20260916.json](../datasets/meta-research/improvement-plan-3/coverage-20260916.json).
Verified offline artifacts: [HTML report](../reports/improvement-plan-3/verified-20260916/product/index.html),
[structured forecast](../reports/improvement-plan-3/verified-20260916/structured-forecast.json),
and [15-row parity receipt](../reports/improvement-plan-3/verified-20260916/verification.json).
This replays archived evidence and is explicitly stale, not a fresh live-market assessment.
Original reports and forecast ledgers remain intact. No subscription purchase,
order submission, G11 allocation or forecast registration was performed.

Validation: adversarial fixtures cover quarantine formats, collisions, horizon
edges, numeric/trigger defects, current-trade origin qualification, stale/future
timestamps, revisions, after-close availability, splits, missing expectations,
deduplication, exposure expiry, reaction leakage, training-only transforms,
holdout perturbation, shuffled labels, exact pairing and failure-ledger integrity.
The cancellation fixture now waits for the child to consume its request before
testing an active-role cancellation, removing a request-file/Popen race.

Validation completed: `npm run check` passed TypeScript compilation, 19 JavaScript
tests and 461 Python tests. A final focused run passed 38 tests, including two
additional no-feature/material-verification edge cases added after full-suite
collection. The verified offline replay checked reference, probability, action,
invalidation and review parity for all 15 rows. Four new JSON schemas validate,
and `git diff --check` is clean.
