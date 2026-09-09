# Cycle 1 synthetic design and evaluator development

2026-09-08. The frozen simulation v1 is **STOPPED_BEFORE_LOCKED_VALIDATION**.
No real candidate fitting or confirmation scoring is authorized. The current
result is **INSUFFICIENT_EVIDENCE**, not a passing or failed statistical power audit.
Increment B reached its explicit stop outcome; it did not qualify progression.
The immutable [decision record](../experiments/cycle1-power-v1/decision.json)
and [stop report](../reports/cycle1-power-stop-7d7b93257f67e058/report.json)
supersede earlier in-progress documentation. This state was reproduced on
2026-09-08 without new synthetic draws or real candidate evaluation.

Subsequent main-goal work produced a
[validated successor proposal and deterministic path helper](CYCLE1_SUCCESSOR_DESIGN.md).
That proposal is not frozen, consumes no redesign slot and releases no streams.
The v1 state and all evidence below remain unchanged.

## Authorities and pre-output corrections

[Simulation v1](../config/cycle1-simulation-v1.json) pins the linked v5 proposal,
generator equations, numerical effects, ten scenarios, random streams, and
computational budget. Its closed schema and hash are validated before generation.
The design hash is
`4cd8f85baa83178d53fcdbf4fae2a86732bf41e6f30b6841aeff82cab67dba20`.
No synthetic performance output existed when this design was written.

The [calendar metadata audit](audits/cycle1-confirmation-calendar-v1.json)
identified a discrepancy before simulation: July 2017 through July 2025 contains
97 calendar months. Both archived ETF target tracks contain 96, omitting October
2024. The pinned October 2025 CPI observation has one missing-value record and
no nonmissing record. The v4 builder skips a primary label when either endpoint
CPI level is unavailable, even though CPI cancels from the excess-return formula.
The audit verifies artifact hashes and reports dates/missingness only.

The proposal now uses 97 confirmation dates, with halves of 48 and 49, preserving
all original endpoints. Its primary excess-label eligibility and availability
exclude CPI diagnostics. This is an explicit scientific amendment, not a change
to the archived dataset. The v5 target-builder implementation and every holding
period still require qualification in increment C; October 2024 has not yet been
rebuilt or declared admissible. The 96-label minimum remains a support floor,
not a calendar construction rule.

Score ordering also became explicitly diagnostic before simulation. A claim
about distribution quality may be supported by scale forecasting without ordered
mean returns. Requiring mean ordering would add a different primary location
claim and make the scale-only power requirement internally inconsistent. CRPS,
materiality, RMSE, coverage, era stability, concentration, both modes, and both
confirmation halves remain in the primary procedure. No substantive numeric
gate was relaxed after observing simulation output.

## Frozen simulation scope

Monthly paths run from January 1990 through July 2026. Three independent Gaussian
AR(1) states become bounded dimension surrogates via `tanh`; the cycle signal is
their equal-weight mean. These are explicitly conditional feature surrogates,
not the complete daily-price/macro-vintage feature pipeline. Annual labels sum
the following twelve monthly returns. Volatility uses a separate persistent
log-volatility process and standardized Student-t innovations. A three-month
trailing monthly-volatility surrogate supplies the volatility comparator.

The design includes no-skill, persistent heavy-tail, strong-baseline partial-null,
location, scale, break, rare-crash, and missingness scenarios. In the partial null,
the signal is the position/direction mean and stress adds no population
information. SPY and QQQ share shocks, state and volatility; QQQ also has an
idiosyncratic shock. They are not independent replications.

Annualized one-step location amplitudes are 0.02 and 0.08. Log-scale loadings are
0.15 and 0.60. The larger design effects deliberately ask whether the short
calendar can detect even substantial skill. They do not assert that such market
effects exist or imply policy profitability. The usefulness effects receive
report-only power estimates; both larger location and scale scenarios must clear
the eventual power gate. Effects cannot be increased merely to make it pass.

Development uses the fixed set of three replication indices per scenario.
Validation has a separate entropy and 2,000 replications per scenario, totaling
20,000. The validation generator currently rejects every request. Component
tests use 10,000 shared 12-month moving-block resamples. Required validation
criteria remain one-sided exact 95% Monte Carlo bounds: false qualification upper
bound at most 0.10 and design-effect power lower bound at least 0.80. Neither
bound has been calculated from a qualifying validation run.

The profile budget is 120 seconds; the validation budget is 3,600 seconds.
Insufficient or indeterminate evidence cannot authorize real evaluation.
Implementation optimization can preserve the same experiment; changing scientific
rules after locked validation would require a versioned record and new locked
streams, subject to the one-redesign limit.

## Implemented and verified

The reusable return-distribution code implements all seven SPY models: empirical
history, volatility tertiles, three simple ridge variants, cycle-score tertiles,
and the three-dimension ridge challenger. Ridge uses training-only population
standardization, an unpenalized intercept, fixed alpha 10, and centered empirical
training residuals. Ties, collapsed bins and minimum support fail explicitly.

The primary evaluator uses 120 strictly mature labels and a 180-calendar-month
rolling window, excludes embargo-origin labels, and permits mature earlier
confirmation labels in later automatic refits. Selection has 68 origins;
confirmation has 97. Unavailable folds remain in coverage denominators. Interior
paired-calendar gaps produce an invalid-evaluation status instead of compressed
bootstrap time. Every challenger is compared with all five baselines in both
modes, with maximum component p-values and the fixed two-claim Holm family.
Only selection survivors enter the simulated confirmation decision.

Tests cover hand-checkable CRPS, ridge normal equations and intercept shifts,
tertile ties, overlapping path sums, strict maturity, calendar counts, embargo
exclusion, future-label noninterference, shared resampling arithmetic, Holm,
strong-baseline failures, favorable gate fixtures, missing-calendar rejection,
synthetic-only entry guards, locked-stream rejection, and metadata hash checks.

The supplemental procedure now implements score-ordering diagnostics, conditional
QQQ transfer using retained SPY fits and unchanged numeric gates, and separate
downside and allocation-policy calculations. Downside includes daily-close event
labeling, overlapping-event episode support, smoothed probabilities, logistic
fits, Brier comparisons and calibration diagnostics. Policy calculations use
monthly execution tapes, weight drift, transaction costs, terminal liquidation,
a selection-only static risk-matched benchmark, and normal/stressed cost cases.
Fixtures verify these calculations; they do not supply admissible simulation
evidence. The frozen generator supplies neither daily closes nor execution opens,
so development reports correctly leave downside at `INSUFFICIENT_SUPPORT` and
policy at `NOT_EVALUATED`. Monthly labels cannot stand in for either tape.

This is not a full-procedure qualification implementation. Complete daily-price
and macro-vintage feature-path simulations remain absent from the frozen design.
There is no real selection loader, immutable real
forecast ledger, or one-time historical opening mechanism.

## Profile evidence and next action

The original `npm run cycle1:synthetic-profile` runner writes an opening record before draws,
uses only the fixed development seed set, and reuses a completed report for the
same identity. An interrupted opening cannot silently start again. The runner
also exercises synthetic confirmation independently for branch coverage and a
conservative runtime estimate; those exercises never alter procedure decisions.

The [initial profile](../reports/cycle1-synthetic-profile-2c3171a0e54ca6de/report.json)
completed 30 runs in 6.9 seconds, with a conservative 5,636-second validation
projection. The full test suite was running concurrently during this initial
measurement. Caching outcome-independent resampling counts produced the
[earlier optimized primary profile](../reports/cycle1-synthetic-profile-1be294cf8dc77391/report.json):
30 runs in 4.0 seconds, with a 4,252-second projection (about 71 minutes).
All 30 procedure results and confirmation branch exercises matched the first
implementation exactly. No new random replication indices or scientific rules
were introduced by the optimization. Both profile records are preserved.

The [latest available-branch profile](../reports/cycle1-optimization-572f14bfdfd34dad/report.json)
supersedes those runtime estimates. It includes the implemented QQQ branch and
projects **1,801.30 seconds** against 3,600 seconds, from 30 development runs in
2.36 seconds. Its equivalence audit preserves 60 partition reports, 360 score
arrays and 120 path arrays exactly, with no new replication indices or scientific
configuration changes. The estimate multiplies the maximum observed branch
duration by 20,000; cache setup is recorded separately. It is machine-dependent
and covers available branches only, not the missing whole procedure.

The available-branch compute gate passes. The scope gate does not: the frozen
design explicitly cannot authorize real evaluation, and supplies conditional
feature surrogates with no daily-close or execution-open generator. The terminal
review therefore recorded `FROZEN_SIMULATION_SCOPE_CANNOT_SUPPORT_REAL_APPROVAL`
and `REQUIRED_EVIDENCE_PATHS_NOT_SPECIFIED`. Its report hash is
`7d7b93257f67e058d725a526f5625b4a68048346a36c3667e12c2e7b6a2e3ef1`.
All 20,000 locked replications remain unopened. Power, family-wise error and
Monte Carlo bounds remain unestimated; statistical design failure is unproven.

The current design cannot be reopened. One redesign slot remains, with no
automatic redesign. Any proposed successor needs a separate versioned design
and rationale linked to this stop, the missing feature/daily-close/execution
scope, a new identity and new locked streams, and the recorded single-redesign
accounting before validation. Effects and usefulness gates may not be changed
to force a pass. No successor design was created during this verification.
Real dataset rebuild, source migration, candidate evaluation, historical
confirmation and deployment remain closed. Independent archive backup/restore
also remains required before migration.

## Reproduced verification

On 2026-09-08, `npm run check` passed compilation, 15 TypeScript tests and 152
Python tests. The suite includes immutable-stop publication, tampered evidence,
implementation identity checks, no-new-draw guards, and denied real progression.
`npm run cycle1:optimize-profile` returned the cached report above; it did not
rerun timing. `npm run cycle1:power-audit` reproduced the terminal report with
expected exit 2. `npm run cycle1 -- --contract-only` returned
`STOPPED_INSUFFICIENT_EVIDENCE` with exit 0 for successful contract inspection.
`npm run cycle1:preflight` remained a metadata-only blocked check, with expected
exit 2 and unchanged hash
`352a046a5c12b63e712b7335ee0c9102d31af45a3978ac6ccf7228ea361772bf`.
The verification changed no scientific config, profiled implementation or seed.
