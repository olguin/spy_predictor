# CYCLE-ASYMMETRY-001 preregistration

## Status and boundary

**2026-09-07 repair notice:** v4 is suspended for candidate evaluation.
The corrected implementation rejects unqualified DGS3MO publication history;
QQQ has no selection forecasts with 120 mature training labels. The spread lag
has been repaired. [CYCLE1_REPAIR.md](CYCLE1_REPAIR.md) is the current repair
authority. Specification and dataset identities below are preserved historical
authorities, not permission to run candidates. A new amendment and source
qualification are required before proceeding.

This is the frozen Phase 1B specification. Versions 1–3 were written before
their corresponding acquisition or feature gates; version 4 was frozen after
NFCI coverage failed but before any candidate-output inspection. The
machine-readable authority is `config/cycle1.json` (preregistration v4), validated by
`schemas/cycle1-config.schema.json` and the semantic checks in
`cycle1_config.py`.

Increments 1–4 are complete. The final dataset is
`cycle1-monthly-19ccd95384e690de`, with identity
`19ccd95384e690dee2fd529c3889a5b1ce17d956f8b9a1efffe551ec73e87753`.
Its online build and offline reproduction match exactly. No candidate model or
confirmation result has been computed.

`TARGET-TOURNAMENT-001` remains complete with `NO_TARGET_ADEQUATE`. Phase 1B is
a separate monthly hypothesis family and cannot revise that result.

The cycle-asymmetry model is this project's independent quantitative
formalization inspired by public cycle-investing concepts. It is not presented
as Mariela Capezzuoli's proprietary or exact model, and no implemented weight,
threshold, or rule is attributed to her.

## Question and instruments

At the final scheduled US equity close of each calendar month, do frozen
valuation, stress, and direction variables materially improve the out-of-sample
distribution forecast of SPY or QQQ twelve-month real excess total return?

SPY and QQQ are evaluated separately. Neither can qualify the other. A common
US macro or broad-market input is labeled as such; Shiller CAPE is never called
QQQ valuation.

## Frozen targets

The primary label begins at the snapshot session's total-return close and ends
at the final scheduled session close of the calendar month twelve months later.
ETF total return uses split-adjusted prices with cash distributions reinvested
on the ex-date. The cash comparator is a monthly rolled research proxy accrued
from the latest published three-month constant-maturity Treasury rate at each
holding-period start using actual/365 simple accrual. Equity and cash are
deflated by the same pinned CPI path, so their log real-return difference equals
their log nominal-return difference.

The secondary label is the minimum daily total-return-index drawdown over the
same inclusive path, with the starting value included in the running peak. Its
event is drawdown less than or equal to -20%. The analogous 24-month real excess
return is diagnostic only and cannot rescue primary-target failure.

The forecast cutoff is the scheduled month-end close. A research policy may
execute no earlier than the next scheduled session open. A labeled row becomes
training-eligible only after its complete target path and endpoint precede the
new forecast cutoff.

## Frozen representation

Every scale, percentile, trend, and fitted transformation uses information
available by the cutoff and is fitted within its training fold. Missing core
features make the candidate row unavailable; no silent imputation is allowed.

The valuation dimension uses a 60-month trailing robust log-real-price trend.
The exact Theil-Sen line is scaled by the trailing residual median absolute
deviation. A positive valuation score means cheaper. Shiller CAPE is a
non-promotable discovery diagnostic unless a future preregistration explicitly
changes that status before a new confirmation sample.

Stress combines the point-in-time bank-prime-minus-three-month-Treasury credit
spread, three-month realized volatility, and twelve-month drawdown magnitude.
The spread is `MPRIME_t - GS3M_t` using the latest common observation month for
which both ALFRED vintages were published by cutoff. Higher stress receives the
contrarian positive sign. Direction combines six- and twelve-month momentum,
price versus its ten-month real moving average, the negative of the spread's
three-month change, and six-month point-in-time industrial-production growth. Higher
direction means improvement. Features are converted to expanding midrank
percentiles in [-1, 1], then equally weighted within dimensions; the three
dimensions are equally weighted.

NFCI is diagnostic-only. It cannot enter a promotion-eligible feature, score,
state, candidate, gate, or policy in the first Cycle 1 run.

The deterministic states and their precedence are frozen in the config:
`EUPHORIA`, `EARLY_RECOVERY`, `CRISIS`, `CORRECTION`, `GREED`, and `NORMAL`.
They describe observable inputs and are never hand-labeled historical episodes.

## Models and hypothesis budget

Each instrument has exactly five models: unconditional history,
valuation-only, direction-only, a fixed cycle-score tertile model, and one
fixed-penalty regularized cycle model. There is no hyperparameter search and
one seed, 42, is used. No HMM or transfer-model variation is included.

The primary ledger therefore contains exactly ten instrument/model
evaluations. Any added window, feature variant, model, seed, transfer fit, or
state count requires a new preregistration and cannot be introduced after
confirmation output is opened.

## Evaluation and gates

Expanding and 180-month rolling forecasts begin after 120 training months.
Training labels, selection, and confirmation are separated by target-aware
purging and a twelve-month embargo. The mechanically selected confirmation
block contains at least 96 complete monthly labels, eight calendar years, and
eight non-overlapping annual blocks, with at least 48 labels in each half.

The primary distribution metric is CRPS. Material improvement requires the
absolute, relative, cross-mode, cross-half, block-bootstrap, coverage,
monotonicity, stability, concentration, and Holm-Bonferroni gates encoded in
the config. The secondary drawdown output must meet the encoded Brier, log-loss,
calibration, and ordering gates when used in a claim.

Policy evaluation is downstream of predictive qualification. It uses only the
three frozen long/cash exposure levels, begins with a one-session lag, includes
turnover-based costs and stressed costs, and compares with a selection-period
volatility-matched static allocation. A policy curve cannot rescue a failed
forecast.

The only experiment decisions are `FREEZE_CYCLE_TARGET` and
`NO_CYCLE_TARGET_ADEQUATE`. An instrument is independently `QUALIFIED` or
`REJECTED`. Evidence is explicitly `POINT_IN_TIME_ADMISSIBLE` or
`RECONSTRUCTED_RESEARCH_ONLY`.

## Source-audit amendment boundary

The source audit may resolve exact endpoints, accepted series, licensing
restrictions, coverage dates, and the mechanical confirmation dates implied by
the frozen boundary rule. It may not change targets, features, transforms,
signs, windows, state rules, models, seeds, numeric gates, or hypothesis count.
Changing any protected scientific field requires a new preregistration version
before feature or candidate output is computed.

Preregistration v2 replaced the originally proposed Moody's Baa-minus-Treasury
input before acquisition or feature computation. The source audit found that
the series notes prohibit storage for subsequent use without prior written
consent, which is incompatible with this project's immutable archive. No
candidate result was inspected before the amendment. The replacement NFCI is
accepted only for local research with citation, no redistribution, and exact
ALFRED vintage reconstruction because its published history is revised.

Preregistration v3 corrected a coverage infeasibility found before feature
computation. A 120-month trend followed by a separate 120-month percentile
warm-up would have left actual QQQ history unable to supply the frozen 120
training months, 12-month embargo, and 96 confirmation labels. Version 3 uses a
60-month robust trend and a 24-month expanding-percentile warm-up. This is the
only v3 scientific change; models, targets, gates, states, seeds, and hypothesis
count remain unchanged, and no candidate output existed when it was made.

Preregistration v4 corrected a second coverage infeasibility found by the first
complete point-in-time feature build. Although NFCI's reconstructed observation
history begins in 1971, its first ALFRED vintage is 2011-05-25. With the frozen
24-month normalization warm-up it yielded only 147 complete feature/target rows
versus the unchanged 228-row minimum. Version 4 replaces only the core NFCI
level and three-month-change features with `MPRIME - GS3M` and its three-month
change. Both Federal Reserve H.15 inputs have ALFRED vintages beginning
1996-12-03. Moody's BAA remains excluded because its storage restriction is
incompatible with the immutable archive. No candidate output existed before
this amendment.

Source audit v2 replaced only the coverage-inadequate ETF sources. Read-only
IBKR `TRADES` bars provide inception-length split-adjusted daily prices. The
exact SPY cash source is State Street's official historical-distributions
workbook. The exact QQQ cash source is Invesco's sponsor distribution table.
Invesco currently rejects automated archive requests with HTTP 406 and its
terms prohibit repeated automated extraction, so the runner requires one
browser-saved CSV or HTML table at
`datasets/cycle1/manual-sources/invesco-qqq-distributions.csv`. The importer
pins those bytes and then verifies them offline; it does not contact Invesco.

Tiingo Starter passed a transient inception-coverage probe, but its August 5,
2026 terms prohibit Starter/Trial users from persistently writing, saving,
archiving, backing up, or retaining Tiingo data. It is therefore explicitly
excluded from source audit v2. No Tiingo response rows were archived.

The v2/v3 preflight runs before any network acquisition. The supplied Invesco
snapshot contains exactly 88 unique QQQ ex-dates from 2003-12-24 through
2026-06-22 and hashes to
`dbe9351a005efbc97387a767b3cfd31a93f22cc703974b7172097e2ed2d4c938`.
The importer accepts Invesco's literal `--` missing components, while required
cash amounts and dates remain mandatory. IBKR's adjusted series is retained
only for diagnostics: it omits the official 2004-12-17 and 2005-06-17 QQQ
events and its rounded prices cannot substitute for exact sponsor cash amounts.

Source audit v3 is the current authority. It hash-links v2, demotes NFCI to
diagnostic-only, accepts point-in-time MPRIME and GS3M, and preserves every
other qualified/excluded decision. Its hash is
`80a80d252c65abe9b13a8533e6d5ad23d65e68e3df993ab2734594c5ab8f3a90`.

The completed reproducibility commands are:

```bash
npm run cycle1 -- --dataset-only
npm run cycle1 -- --dataset-only --offline
```

Both commands reproduce dataset identity
`19ccd95384e690dee2fd529c3889a5b1ce17d956f8b9a1efffe551ec73e87753`.
SPY has 308 model-eligible rows and QQQ has 234; both have 100% core-feature
coverage. The final 96-month confirmation interval is 2017-07-31 through
2025-07-31, preceded by the frozen 12-month embargo. These exact boundaries
are stored in each validation-track manifest and are part of dataset identity.

The next implementation increment is the five frozen models per instrument,
an immutable ten-entry hypothesis ledger, selection-only walk-forward tooling,
and an explicit one-time confirmation-opening guard. Confirmation output must
remain unopened until that machinery is complete and tested.

No paid data, LLM, agent, account query, order, leverage recommendation, or
post-confirmation specification change is permitted in this phase.
