# Cycle 1 pre-evaluation repair

Status: 2026-09-07. Correctness repairs implemented; v4 candidate evaluation
is suspended. This document supersedes the earlier instruction to implement
increment 5 using dataset `cycle1-monthly-19ccd95384e690de`.

## Implemented repairs

1. Cash accrual selects DGS3MO by observation date and vintage publication at
   each holding-period start. Later revisions cannot change an already fixed
   accrual. Same-day releases after the close are excluded. Missing revisions
   do not resurrect older values.
2. The spread change uses the latest common published observation month and
   the exact observation three months earlier from both series. Missing months
   are not silently replaced by older ones.
3. Dataset construction requires consecutive calendar months and checks
   selection forecasts against mature training labels in expanding and rolling
   modes. Zero feasible selection forecasts is a hard failure. Nonzero counts
   are necessary, but do not establish statistical power.
4. The v4 evaluation boundary is explicitly suspended. Its ten-entry budget
   check cannot be mistaken for scientific approval.
5. `npm run cycle1:preflight` verifies the archived manifests and relevant
   artifact hashes, projects selection targets to date metadata, and produces
   a deterministic audit with implementation hashes. It neither fits models
   nor computes candidate or confirmation metrics. Exit code 2 means blocked;
   code 1 means invalid audit input.

The v4 config, source-audit hashes, raw bytes, and dataset directories are
preserved. A corrected dataset must receive a new identity. Earlier offline
reproduction demonstrates reproducibility, not correctness.

Verification: `npm run check` passed (15 TypeScript tests, 97 Python tests).
The [pinned metadata audit](audits/cycle1-repair-352a046a5c12b63e.json)
records the original dataset and the repair implementation hashes. The corrected
offline build was also exercised and produced the expected cash-source failure.

## Verified feasibility and source limitation

| Track | Archived selection rows | Mature-label selection forecasts | GS3M coverage | Mature selection labels at confirmation start |
|---|---:|---:|---:|---:|
| SPY | 200 | 68 | All 200 starts | 200 |
| QQQ | 126 | 0 | All 126 starts | 126 |

Counts hold in both walk-forward modes. Existing conservative label availability
and the 120-training-label requirement are unchanged. The cash filter examines
holding-period starts only; it is not full-path target qualification.

The first pinned DGS3MO publication is `2005-06-28T23:59:59.999999+00:00`, so
sixty-seven SPY selection starts lack admissible coverage. The already archived
GS3M vintages begin `1996-12-03T23:59:59.999999+00:00` and cover every SPY and
QQQ model-eligible start. GS3M is the monthly average of the three-month
constant-maturity Treasury yield. At a month-end cutoff the implementation uses
the latest earlier observation whose vintage was already published.

The repaired `npm run cycle1 -- --dataset-only --offline` stops at the first
January 1993 SPY target with `No publication-admissible cash rate`. This is
the intended failure. No replacement dataset is claimed ready.

## Chosen unblock

The recommended amendment replaces DGS3MO with the already accepted GS3M
monthly series for the cash comparator, while retaining strict publication
rules. This avoids new acquisition and restores the full eligible calendar.
It changes the target definition and therefore requires a new preregistration,
source audit, dataset identity, and hypothesis ledger before model output.

SPY becomes the development and independently promotable instrument. QQQ is an
external transfer/robustness track: an SPY-frozen specification can be evaluated
there, but QQQ cannot independently qualify. QQQ has 126 mature selection labels
at the confirmation boundary, so this transfer check is mechanically feasible
without using its confirmation outcomes for development.

Verified source leads include the Federal Reserve's dated
[September 3, 1996 H.15 release](https://www.federalreserve.gov/releases/h15/19960903/)
and FRASER's [historical H.15 collection](https://fraser.stlouisfed.org/title/h15-selected-interest-rates-86).
These are not qualified inputs. Audit coverage, extraction accuracy,
publication conventions, revisions, and storage of mixed-content releases
before ingestion. The releases also contain third-party series that remain
excluded; government hosting does not remove those restrictions.

The three-month constant-maturity investment-basis yield must not be confused
with the separate three-month Treasury bill discount-basis series.

## Scientific amendment work order

These are proposals, not an already frozen v5 protocol.

1. Freeze the v5 amendment using GS3M, SPY development, and QQQ external
   transfer. Preserve v4 and its dataset as superseded artifacts.
2. Finalize the evaluation contract below. Record every added benchmark or
   transfer model in the amended ledger instead of hiding it to preserve ten.
3. Simulate the complete protocol under synthetic null and useful-effect
   scenarios with overlapping labels, persistent predictors, and clustered
   volatility. Freeze scenario generation and useful effect sizes first.
   Measure false positives and power for the entire promotion procedure.
   No power result is claimed while the protocol is incomplete.
4. Publish the amendment and source audit; rebuild into a new immutable dataset.
   Finish selection-only implementation and tests before the one confirmation
   opening. Identical report reproduction is allowed; scientific retuning
   after opening requires new unseen or forward evidence.

## Evaluation contract to finalize

| Area | Required decision before candidate implementation |
|---|---|
| Distribution | Specify the complete return distribution for ridge models, residual estimation/scaling, input columns, intercept, penalty, and quantiles. Ridge means alone do not define probabilistic forecasts. |
| Inputs | Choose individual features versus dimension scores and enumerate interactions. Use the same distribution construction across comparable regression baselines. |
| Volatility benchmark | Add one simple volatility-conditioned distribution comparator. Separate location, dispersion, and downside skill. Update the comparison family and ledger. |
| Tertiles | Define training-only quantile algorithm, ties, boundary inclusion, and behavior below minimum bin counts. No outcome-based tie breaking. |
| Degenerate folds | Define probability smoothing, one-class handling, and minimum event support for calibration. Failed folds remain in coverage accounting. |
| Training | Require complete endpoints and label publication before cutoff. Define rolling windows in calendar months. Do not count the same maturity purge twice. |
| Transforms | Distinguish causal percentile state available through each cutoff from standardizers fitted on training data. Rolling fitting must not silently reset historical percentile state. |
| Confirmation refits | Preferred: automatic refitting may use earlier labels after maturity under the unchanged algorithm, without human inspection or retuning. Encode this rule explicitly. |
| Tests | Enumerate candidate/comparator/null, paired loss differences, null-centered dependent resampling, one-sided p-values, Holm family, and cross-mode/half combination. Ledger records are not themselves statistical tests. |
| Eras | Encode calendar boundaries, block alignment, insufficient-era handling, and the denominator for single-block benefit concentration. |
| Interpretation | Price position is not fundamental valuation; prime-minus-Treasury is a monetary/lending-rate proxy. Higher expected return need not imply lower drawdown risk. Separate claims and ordering gates. |
| Policy | Define the statistic behind the 0.1 risk-adjusted threshold, monthly rebalancing/drift, next-session open, distributions, turnover, cash, and selection-only benchmark calibration. Never compound overlapping annual labels as monthly returns. |
| Provenance | Resolve what reconstructed ETF evidence can qualify. Point-in-time macro inputs do not make the whole track replay-safe. Reconcile diagnostic-only versus promotable-tier rules. |
| Decisions | Distinguish inadequate predictive evidence, insufficient data/power, and invalid evaluation. None automatically permits promotion. Keep Phase 1's result and its scoped interpretation. |

## Roadmap corrections

- Make anti-overfitting controls prerequisites to selection and evolution.
- Begin immutable monthly forecast capture once a stable model qualifies
  historically. Annual labels take time to mature; capture is separate from
  orders or paper execution.
- Expand the Reality Store only for a named experiment's required inputs.
- Treat agents, evolution, options, and execution as conditional branches.
  A useful quantitative-only system is an acceptable endpoint.
- For future LLM evaluation, record model versions and training-period limits.
  Restricted retrieval cannot remove knowledge inside model weights; require
  prospective evidence for promotion.
- Replace the legacy daily 09:29 schedule if a monthly target is frozen.
