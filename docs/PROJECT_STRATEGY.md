# Project strategy: establish useful evidence before expanding the platform

Strategy revision: 2026-09-09. Current executable status lives in
[PROJECT_PLAN_AND_STATUS.md](PROJECT_PLAN_AND_STATUS.md).

The user explicitly authorized a separate historical development track on
2026-09-09. Follow [HISTORICAL_DEVELOPMENT.md](HISTORICAL_DEVELOPMENT.md) to qualify
bounded SPY inputs and run the seven fixed models in expanding and rolling
walk-forward development. Preserve both stopped experiments and exclude the
literal July 2017–July 2025 final evaluation calendar. This new track may produce
descriptive development metrics without passing the closed power protocols;
it cannot make their research qualification claims or open confirmation.

The revised development plan includes a pre-output missingness amendment:
two missing archived SPY sessions invalidate 26 daily-feature origins. Preserve
all 200 origins and all 68 scheduled forecast months, exclude incomplete training
rows, and retain the 120-label minimum. Qualification establishes 42 trainable
forecasts per mode. Missing periods are reported, not imputed. Details, source
identities, runnable commands and limitations are in the development note.

The user closed the missing-session investigation on 2026-09-09. Post-output
diagnostics showed unstable rankings across years and leave-one-year-out slices.
The project therefore stops model search on this small development sample and
collects new observations through the frozen, static-reference
[prospective cohort](PROSPECTIVE_OBSERVATION.md). The current SPY/QQQ workbench
snapshot is also complete. No final historical evaluation was opened.

The A–E sequence below remains the historical **Cycle 1 research qualification
plan**, not the dependency chain for the separately authorized development track.
Cycle 1 simulation v1 stopped for insufficient evidence scope. Its sole registered
successor stopped for computational insufficiency after one development draw,
with zero locked replications and no remaining redesign slot. Neither experiment
may be reopened, and their code/configuration/decision artifacts remain immutable.
The v4 dataset is an unqualified archive and the v5 contract remains a proposal.

## 1. Goal and assessment

Build a reproducible system that uses information available at a forecast cutoff
to produce calibrated market forecasts with useful incremental value on unseen
observations. Establish whether those forecasts improve an executable policy
after costs. Specialized LLM agents and eventual evolution remain research
hypotheses for improving that system, conditional on evidence.

The strongest part of the existing plan is its scientific infrastructure:
immutable inputs, code-aware identities, chronological evaluation, explicit
negative decisions, and separation of forecasts from execution. Preserve it.
The weakest part is the assumption that completing a long sequence of platform
phases will produce predictive value. The scarce resource is independent market
evidence. More code, overlapping labels, or correlated instruments do not create
it. A useful quantitative-only forecaster, or an auditable decision to stop an
unsupported hypothesis, is a valid project outcome.

The immediate deliverable should be one decision-quality Cycle 1 experiment.
It should answer whether the frozen cycle representation adds return-distribution
information beyond simple position, direction, and volatility baselines. It
should separately report downside forecasting and economic-policy evidence.

| Existing weakness | Strategic correction |
|---|---|
| Status says both suspended and qualified | One compact handoff, one current strategy, versioned scientific authorities |
| Coverage counts treated as sufficient evidence | Full-path admissibility, mature-label feasibility, then whole-procedure power |
| QQQ promoted independently despite no selection forecasts | SPY development; QQQ transfer evidence only |
| Many gates without a complete test definition | Explicit claims, paired comparisons, multiplicity, missingness, and decision rules |
| Anti-overfitting scheduled after evolution | Implement it before the first Cycle 1 candidate result |
| Broad Reality Store and agents on the mandatory path | Extend existing storage only for an identified experiment or operational need |
| Historical reconstruction can appear to imply deployment readiness | Separate historical research qualification, prospective validation, and execution |
| Monthly research inherits a daily intraday workflow | Use a monthly forecast schedule with explicit acquisition and execution timing |

## 2. What the evidence currently permits

Phase 1 closed with `NO_TARGET_ADEQUATE`: none of 24 tested instrument/horizon
candidates passed its final gates. Preserve that result and its documented gate
correction. It rejects those candidates on that dataset; it does not prove that
all market forecasting is impossible.

Cycle 1 has no candidate results. The current v4 runner refuses evaluation;
the repaired dataset build fails on cash publication coverage. The pinned
[repair audit](audits/cycle1-repair-352a046a5c12b63e.json) verifies:

- SPY has 200 archived selection rows but only 68 forecasts after requiring
  120 mature training labels. Filtering for DGS3MO publication leaves one.
- GS3M covers all archived selection starts and preserves SPY's 68 forecasts.
  This is a start-date audit, not qualification of every monthly cash accrual
  in every target path.
- QQQ has 126 selection rows and zero selection forecasts. At the first
  confirmation cutoff it has 126 mature selection labels, enough for an
  unconditional reference distribution, not independent development evidence.
- Both ETF tracks are `RECONSTRUCTED_RESEARCH_ONLY`. Macro vintages do not
  establish original first-seen provenance for the ETF prices or distributions.

The 96 monthly confirmation labels span eight years; that does not mean 96
independent annual returns. Eight non-overlapping annual intervals are a
calendar description, not an estimated effective sample size or eight independent
economic regimes. These historical market episodes are already familiar to the
researchers; sealing model outputs does not make the history human-unknown.
Persistent predictors and overlapping returns can produce
misleading apparent long-horizon strength. This motivates the simulation gate;
it does not establish in advance that Cycle 1 will fail.
[Boudoukh, Richardson, and Whitelaw](https://www.nber.org/papers/w11841).

Keep the cycle idea as an independent quantitative formalization inspired by
public cycle-investing concepts, including Howard Marks and Mariela Capezzuoli.
No invented rule is their proprietary model. The active feature called
“valuation” measures trailing real-price position, not fundamental valuation;
`MPRIME - GS3M` is a lending/monetary-rate proxy, not corporate default spread.
Stress can raise both expected returns and future downside risk. Descriptive
states do not establish causal mechanisms or predict exact tops and bottoms.

## 3. Recommended Cycle 1 amendment

### Preserve the question; repair its executable definition

Keep monthly XNYS cutoffs, the 12-month excess log total-return target, the
secondary -20% daily-close drawdown event, the diagnostic-only 24-month horizon,
existing feature windows/signs, and deterministic states. No HMM, indicator
search, or new paid source belongs in this amendment.

Replace DGS3MO with the archived GS3M series for the research cash proxy.
GS3M is a monthly average of business-day three-month constant-maturity yields
quoted on an investment basis; it is not a realized investable cash total-return
index. Preserve that distinction in every target and policy report.
[Federal Reserve/FRED GS3M definition](https://fred.stlouisfed.org/series/GS3M).

At each holding-period start, use only an observation and vintage already
published by that instant. Freeze strict versus inclusive timestamp comparisons
consistently across config and code; date-only releases retain conservative
end-of-day availability. Preserve actual/365 accrual. The common CPI deflator
cancels from the excess log-return label; do not market that label as an
additional independent inflation prediction.

Keep the archived confirmation dates fixed at 2017-07-31 through 2025-07-31,
with the existing two halves and preceding 12-month embargo. Encode those dates
explicitly. A later ingestion date must not silently shift a “last 96 labels”
boundary. New dates belong to a separately identified future-evidence pool.

Retain 120 mature training labels, a 180-calendar-month rolling window, and both
expanding and rolling evaluation. Maturity implements the overlap purge; do
not subtract it twice. Freeze whether embargo-origin labels remain excluded
from confirmation training; recommended default: exclude them throughout this
experiment. Automatic refits may use earlier confirmation-origin labels only
after maturity, under the unchanged algorithm, without intermediate inspection.

### Keep two cycle challengers and meaningful comparators

The v5 draft's five primary tests against unconditional history do not fully
encode the stronger claim that a cycle model beats every simple alternative.
Its eleven-entry ledger also leaves the QQQ reference ambiguous. Replace the
implicit instrument-times-model accounting with explicit evaluation records.

Recommended model roster, all fixed before real output:

| SPY model | Role and purpose |
|---|---|
| Unconditional empirical history | Reference distribution |
| Volatility-conditioned empirical history | Detect gains explained by volatility conditioning alone |
| Position-only ridge distribution | Existing “valuation-only” baseline, described accurately |
| Direction-only ridge distribution | Existing direction baseline; includes macro/credit inputs, not pure momentum |
| Position-plus-direction ridge distribution | Joint simple baseline; test whether the full cycle adds beyond their combination |
| Fixed cycle-score tertiles | Transparent cycle challenger |
| Regularized three-dimension cycle distribution | Second and final cycle challenger |

Use the existing ridge penalty and a common, completely specified residual
distribution construction across regression models. Retain the draft's empirical
training-residual approach as the starting specification; test its calibration
and shrinkage effects synthetically before freezing it. A ridge mean alone
is not a probability distribution. Freeze standardization, intercept, residual
centering, quantiles, tertile ties, minimum bin support, and unavailable-fold
behavior. No outcome-driven choice among distribution constructions.

This adds one small joint baseline to the draft, not another cycle challenger.
Register seven SPY evaluation entries, two conditional QQQ cycle-transfer entries,
and one QQQ unconditional reference: ten planned entries, with explicit skipped
statuses for transfer checks whose SPY candidate never qualifies. Modes, metrics,
comparisons, refits, and seeds must also be enumerated; ten entries are not ten
independent statistical tests. Drawdown and policy records link to these entries
and cannot become unrecorded alternatives.

For QQQ, transfer each qualifying SPY model's fitted parameters, standardizer,
residual distribution, and bin boundaries at the corresponding cutoff. Compute
QQQ's own causal instrument features, but do not refit the transferred model or
choose a rescaling from QQQ outcomes. Fit only its explicitly registered
unconditional reference on mature QQQ labels. Transfer failure limits the
generality claim; it cannot select or rescue an SPY candidate. SPY and QQQ
experience common market shocks and are not independent replications.

### Define claims and tests separately

The primary claim is incremental SPY return-distribution skill for either of
the two cycle challengers. Require material CRPS improvement against every one
of the five comparators, on common eligible dates, in both modes. CRPS is a
proper distributional score; its improvement alone does not establish better
mean-return timing or a profitable policy. Report interval coverage, location
error, and dispersion diagnostics alongside it.
[Gneiting and Raftery](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf).

For each challenger/comparator/mode, define paired loss improvement as comparator
CRPS minus challenger CRPS. Use the same time-block resampling indices across
all models and modes. Freeze a null-centered one-sided dependent-bootstrap test
and interval construction. Recommended family: one composite claim per cycle
challenger, with its p-value the maximum over required comparator/mode tests,
then Holm correction across the two challenger claims. Skipped claims retain
p=1; do not shrink the family after selection. This construction requires valid
component tests; dependence-aware simulation must check the complete procedure,
including partial nulls where a challenger beats history but not a strong baseline.

Retain the draft's full-partition starting materiality gates (at least 0.001
absolute and 2% relative CRPS improvement) for the pre-output design review.
They are project choices, not literature-certified useful effect sizes. Encode
their units and exact comparator scope. Define positive improvement in both
confirmation halves as a robustness requirement; do not silently require each
four-year half to pass a second full significance test. Freeze era boundaries,
minimum support, maximum degradation, and concentration arithmetic. Resampling
block length 12 is a starting design, not a proof that dependence ends at month
12; include more persistent processes in the power audit.

Coverage is measured against the fixed eligible calendar, not just surviving
forecasts. Failed folds count as missing. Paired comparisons use a documented
common-date intersection and must themselves retain required coverage. A
candidate may not improve its score by failing on difficult dates.

Drawdown calibration is a separate secondary claim with its own support gates.
Count distinct event episodes as well as overlapping positive labels. Too few
episodes means insufficient downside evidence, even if hundreds of monthly
labels exist. A return-qualified model cannot expose an unqualified downside
probability to a policy. Score-ordering diagnostics apply to the claims they
actually support; return ordering does not imply inverse drawdown ordering.
Secondary and 24-month outcomes cannot rescue the primary claim.

Policy qualification is downstream and separate from forecast qualification.
Freeze its mapping before confirmation, including forecast-tertile construction,
weight drift, the 0.5/0.75/1.0 exposure levels, next-session execution, dividends,
turnover, 5 bps one-way costs, and doubled-cost stress. Use actual non-overlapping
monthly holding returns; never compound the annual target labels as monthly P&L.
Verify price and cash-distribution units at open-to-open boundaries. Cash remains
a modeled proxy, so later paper qualification must check achievable cash yield.

Compare against buy-and-hold, cash, and the selection-calibrated static risk-matched
allocation. Give all comparisons identical cost/dividend treatment. Specify
whether the risk statistic uses arithmetic excess returns and its annualization;
the draft's 0.1 threshold is meaningless without that definition. Freeze the
benchmark-weight tie rule. A policy failure can leave a useful historical
forecasting result, but cannot qualify an allocation overlay.

## 4. Implementation sequence and acceptance gates

These are bounded increments, in order. Do not start the next dependent increment
on a verbal claim that the preceding one is “basically complete.”

### A — Make the amendment coherent and preserve the archive

Deliver a reviewed proposed v5 contract, explicit ledger template, matching JSON
Schema and semantic loader, amended source audit, and synthetic-only execution
mode. Keep the real-data evaluation gate closed. Correct the draft's misleading
`status: frozen-before-candidate-output` when implementing the amendment; the
file is currently a draft despite that field.

Update version handling in `cycle1_config.py`, source-audit inheritance, track
roles, and the CLI together. The CLI currently pins source audit v3; changing
only `config/cycle1.json` will not switch the workflow coherently. Preserve the
v4 validator/schema and hash-linked audit chain for historical verification.
Resolve diagnostics versus promotable reconstructed-market evidence explicitly.

Deliver a private archive inventory and a backup/restore verification record
using [DATA_DURABILITY.md](DATA_DURABILITY.md) before any source migration.
No verified independent backup is currently documented. Reuse pinned raw bytes
by verified reference: raw directories are keyed by source-audit hash, so a new
audit must not accidentally force reacquisition or lose the manual Invesco input.

Acceptance: conflicting versions, roles, budgets, missing contracts, absent power
approval, or a wrong dataset hash cannot authorize real evaluation. All proposed
scientific changes are listed together before candidate output.

### B — Build the evaluator on synthetic evidence and measure feasibility

Implement the small model roster, fold engine, scoring, claim tests, and report
decision function against synthetic fixtures first. The original instruction
“power audit before model code” has a circular dependency: whole-procedure power
needs the actual evaluation algorithm. Synthetic model implementation is allowed;
real candidate fitting remains blocked.

Before simulation, freeze generators, effect sizes, pass criteria, random streams,
and computational budget. Generate return paths and derive overlapping annual
labels, rather than drawing independent annual outcomes. Include persistent
predictors, clustered volatility, heavy tails, structural breaks, rare downside
episodes, missingness, no-skill and partial-null cases, and useful location/scale
effects. Respect the actual dates, sample lengths, maturity, refits, selection
screen, confirmation halves, and all required comparisons. Where claims concern
features derived from prices, construct those features consistently from the
synthetic path or document the simulation's narrower scope.

Use at least the draft's 2,000 outer replications per required scenario, with
Monte Carlo uncertainty. Profile a small synthetic run first; cache shared fits
and batch paired resampling so the nested simulation is computationally feasible.
Keep a bounded development seed set and a separate locked validation seed set.
Run the exact final algorithm on that validation set; retries after scientific
changes require versioned audit records and a new locked seed set.

Recommended design target: the one-sided 95% Monte Carlo upper bound on false
qualification is at most the chosen 10% research family-wise rate, and the
corresponding lower bound on power is at least 80% at a predeclared, economically
justified design effect. Distinguish that effect from the observed materiality
cutoff: when the true effect sits exactly at a hard improvement cutoff, an
80% probability of clearing every gate is generally unrealistic. Report power
at the usefulness boundary too, and state which smaller effects remain unresolved.
Calibrate component testing conservatively if necessary. Publish the power curve
and detectable effect scale; do not raise the assumed design effect until the
audit passes. A scale-only scenario is not expected to pass a separate
return-timing claim. State which scenarios must pass which claim.

These are proposed design criteria to freeze in A, not achieved results. A failed
or indeterminate audit closes this design as `INSUFFICIENT_EVIDENCE` without
opening historical confirmation. At most one documented pre-output redesign
may reduce the number of claims or change the evidence-acquisition plan. Do not
iterate indefinitely on gates or soften substantive usefulness requirements.

Acceptance: a deterministic, code/config-hashed power report validates the full
historical qualification procedure, or an explicit stop report identifies what
evidence is missing. Synthetic power supports study design; it proves no market
edge and does not make the historical data prospectively unseen.

### C — Rebuild and qualify the amended monthly dataset

Freeze the final amended authorities after B. Build a new immutable dataset
from the existing archives and prove identical offline reconstruction.

There is a concrete implementation trap: `build_cycle_targets` currently tries
every SPY month from January 1993, while the first pinned GS3M vintage is December
1996. Preserve all price history for feature warm-up, but generate evaluation
targets only for the predeclared feature/source-admissible calendar. Record
excluded warm-up dates and reasons. Never fabricate early rates or silently
drop a missing internal holding period. Check every monthly accrual through
each complete target, not only the target's initial start.

Make dataset feasibility role-aware: QQQ's zero development forecasts cannot
block an otherwise valid external-transfer dataset. Verify its reference-label
maturity instead. Count joined feature/target rows with actual availability;
228 raw rows alone are not an acceptance criterion. Recompute all features
after the exact three-observation-month spread-lag repair.

Audit corporate-action adjustment units, missing-value vintage revisions,
internal session/month gaps, macro cutoff handling, and label availability.
Tests should mutate future observations/releases and prove earlier features,
eligible training sets, and forecasts unchanged. The 24-month diagnostic must
not reduce primary coverage or expose its future label to training.

Acceptance: full-path source/target checks, expected literal partitions,
role-specific mature-label counts, component provenance, artifact hashes, and
offline identity all pass. If counts differ from the audit assumptions, stop
before fitting real candidates and revisit the documented feasibility decision.

### D — Selection only, with the confirmation boundary enforced

Persist the complete ledger before fitting real data. Evaluate only SPY selection
using the frozen algorithm, then mechanically retain eligible cycle challengers.
Do not tune features, penalties, distributions, state rules, or policy on this
short selection window. If none survives, emit the appropriate negative or
insufficient-evidence decision and leave confirmation unopened.

Separate selection-accessible artifacts from confirmation target values and
metrics. Preflight may read date metadata and verify hashes; notebooks and
development code must not default to a full-history validation track. The current
notebook `auto` mode is exploratory, not a confirmation-access control. Use
synthetic mode during implementation and add explicit dataset/partition access
checks before allowing real-data diagnostic use.

Test leakage, fit counts, ties, one-class folds, empty bins, partial coverage,
resampling arithmetic, refits, and resumability with small hand-checkable cases.
Use shared evaluation code for synthetic, selection, and final report paths.

Acceptance: immutable selection report and survivor list, complete test suite,
report schema, and one-time opening mechanism ready before any confirmation
metric can be returned. A configuration flag alone is not a sealed-test service.

### E — One confirmation decision

Bind the opening record atomically to the exact code, data, config, ledger,
selection, and power-audit hashes. Persist the opening before computation;
resumes use the same identity. Do not stream intermediate candidate or QQQ
metrics. An identical rerun may reproduce the report; changed scientific
identities cannot reopen the same confirmation block for another positive claim.

Run SPY confirmation, the conditional QQQ transfer checks, and eligible secondary
and policy analyses. Persist forecasts, paired losses, intervals, all gate
outcomes, skipped analyses, source limitations, hypothesis counts, and a compact
decision summary. A valid empirical failure is distinct from insufficient power
or an invalid computation. If a post-opening defect changes scientific results,
record invalidation and require new unseen/forward evidence for promotion.

Recommended report dimensions, to encode in A:

| Dimension | Possible conclusion |
|---|---|
| Evaluation validity | Valid / invalid, with reason |
| SPY historical forecast | Research-qualified / no candidate adequate / insufficient evidence |
| Drawdown forecast | Qualified secondary claim / failed / insufficient support / not evaluated |
| Allocation policy | Qualified for further testing / failed / not evaluated |
| QQQ | Transfer supports / does not support / insufficient / not run |
| Deployment | Not qualified by this historical experiment |

If legacy `FREEZE_SPY_CYCLE_TARGET` is retained, define it as freezing an exact
historical research specification only. It must never imply live readiness.

## 5. Turn a surviving result into a useful system

The original phases become conditional work packages; their numbers no longer
set the dependency order.

| Stage | Minimum deliverable | Exit condition |
|---|---|---|
| Historical evidence — Phase 1B plus essential Phase 7 controls | Increments A–E above | Valid, immutable decision; no automatic promotion after inconclusive evidence |
| Operational quant forecast — narrow Phases 2–3 | Target-specific point-in-time store, reusable approved model, monthly scheduler, forecast/outcome registry | Deterministic replay, input freshness, failure handling, and offline/operational parity |
| Prospective observation | Timestamped inputs and forecasts before outcomes exist; delayed label attachment | Predeclared calendar, effective-sample, calibration, and incremental-value requirements |
| Allocation validation — relevant Phases 10–11 | Frozen quant policy, paper-only workflow, champion/challenger registry | Operational reliability plus separate cost/risk and evidence gates |
| Fixed contextual agent experiment — Phases 4–5 | One agent, one named information gap, schema/evidence validation and exact cache | Incremental prospective value over quant-only after cost, latency, and failures |
| Evolution — Phase 6 and expanded Phase 7 | Small budgeted search, lineage, inaccessible final test, promotion controls | Beats the fixed-agent baseline on fresh evidence; search cost justified |
| Options/instrument expression — Phases 8–9 | Hypothesis-specific data and executable payoff/cost comparison | Incremental value over the simplest permitted expression |
| Controlled live — Phase 12 | Isolated executor, hard risk limits, kill switch, reconciliation and manual disable | Separate explicit deployment authorization after paper/evidence gates |

Start monthly prospective forecast capture as soon as a specification is stable
and historically research-qualified. Do not wait for a generalized Reality Store,
five agents, evolution, or a dashboard. Forecast generation and raw acquisition
must record actual availability time; delayed data cannot be represented as a
forecast issued at an earlier scheduled close. Operational execution must occur
after the real issue time. Archive unavailable forecasts too.

If historical power is inadequate, a frozen, clearly unqualified benchmark or
candidate may be placed in a separately registered observation-only cohort to
collect new evidence. No policy promotion follows from that choice. Begin only
after a stable algorithm and data timing contract exist; this strategy review
does not start a scheduler or any external workflow.

Twelve-month labels take at least twelve months to mature, and nearby monthly
forecasts overlap. A few months of paper trading can test operations but cannot
validate the annual hypothesis. Set review dates and evidence minima before
capture; show progress without repeatedly testing for significance or resetting
the cohort when results disappoint. New model versions receive new cohorts.

For agents, use the existing runtime interface and first choose a concrete
information gap the quant model cannot already represent. Require distinct
input evidence, an abstention path, quant-only ablations, token/latency/failure
accounting, and versioned prompts/models. Retrieval cutoffs cannot remove future
market knowledge embedded in model weights. Historical LLM replay is development
evidence with explicit contamination limitations; promotion requires prospective
evidence. Runtime choice and an initial population of 12 by 10 generations are
not current commitments.

Keep TypeScript orchestration, Python statistics, immutable Parquet/JSON inputs,
DuckDB analysis, and existing persistence contracts. Add PostgreSQL operational
metadata where needed; a broad data-platform rewrite is unnecessary. News, SEC,
options, and additional instruments enter only through a separately specified
experiment with a data and evaluation budget.

## Parallel application track — Maru Cape cycle analysis

User direction, 2026-09-08: pursue a secondary practical application alongside
the forecasting research. The [application plan](MARU_CAPE_APPLICATION_PLAN.md)
defines tools for a cutoff-specific market assessment and an instrument report
covering cycle location, business quality and valuation, technical timing,
psychology, credit and risk. Each assessment should explain what supports an
investment idea, what contradicts it, what is missing, and what would change it.

Ground the component map in Mariela Capezzuoli's public teaching and identify
our own formulas and decision rules explicitly. Existing exploratory tools can
support this track; they do not reproduce an undisclosed proprietary indicator.
Deliver runnable reports incrementally, beginning with archived SPY/QQQ inputs
and transparent missing-data handling. Do not present price position as business
valuation or retrospective reconstructions as live point-in-time evidence.

This track may progress while the Cycle 1 design remains stopped. Its descriptive
assessments do not qualify a forecasting model, modify the Cycle 1 experiment,
or authorize orders. Any later predictive or policy claim needs its own frozen
evaluation and unseen evidence. Keep the no-new-paid-data constraint and use
separate report identities, configurations and output directories.

Implementation progress: both notebooks run shared synthetic market and instrument
assessments with explicit cutoffs, component/source panels, scenario comparisons
and export. The separate META track has also archived a current five-symbol
SEC-enabled packet, registered its first quant-only forecast, and implemented
immutable outcome acquisition/scoring plus guarded post-close operation. Future
packets support VIX/VIX3M, transparent risk-appetite and delayed IBKR context.
This is operational research evidence, not a current investment recommendation,
calibrated probability model or Cycle 1 qualification. See the handoff and
[META runbook](META_OBSERVATION_OPERATIONS.md) for the next dated operations.

## 6. Resource discipline, stopping rules, and maintenance

Zero new paid data remains the active Cycle 1 constraint. Preserve the source
audit's exclusions and manual-source handling. Current provider pricing and
live entitlements are not prerequisites for the archived monthly experiment.
Do not repeatedly reacquire history to make an old experiment look current.

For each increment, record its artifacts, acceptance checks, computational cost,
decision, and next action. Keep only one active scientific amendment. If Cycle 1
fails, stop that family. Any new horizon, feature family, data purchase, or search
budget needs its own rationale and preregistration. More attempts on the same
historical eras are not fresh confirmation, even with a new experiment name.

Prefer the simpler model when incremental cycle value is absent. A simple-model
result may motivate a separately qualified forecasting service; it cannot be
renamed as confirmation of the cycle theory. Options, agents, and evolution are
not remedies for missing independent observations or unqualified inputs.

The working handoff should contain only current status, exact authority links,
known blockers, verified commands, and the next bounded increment. Replace
obsolete instructions instead of adding another superseding paragraph. Keep
scientific history in versioned configs, reports, repair notes, and Git. Update
this strategy only when a decision changes its dependencies or evidence policy.
