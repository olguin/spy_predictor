# Cycle 1 v5 amendment implementation

The [successor design review](CYCLE1_SUCCESSOR_DESIGN.md) records the subsequent
pre-output v2 proposal and deterministic daily-path helper. It does not switch
the v5 authority to a new simulation or reopen the stopped v1 design.

2026-09-08. Status: **proposal validated; synthetic v1 stopped with insufficient evidence**.
The v4 authorities are unchanged and suspended. No real candidate metrics have been computed. Synthetic development profiles
now exist; the terminal prerequisite review closed this design before locked
power validation. Increment B reached its stop outcome, without qualification.
This file records implementation,
not approval of an experimental design or permission to open confirmation.

Run `npm run cycle1 -- --contract-only` to validate the linked proposal and
produce a deterministic report without reading market data. The CLI selects the
v5 config and proposed v4 source audit together. Ordinary invocations still
select the suspended v4 authorities. Both the runner and direct dataset builder
block v5 acquisition/builds, including `--dataset-only`.

## Implemented contract transition

- Seven SPY models, two conditional QQQ cycle transfers, and one QQQ empirical
  reference form ten explicit ledger records. The position-plus-direction ridge
  baseline supplements history, volatility, position, and direction comparators.
- Two composite cycle claims each require all five comparator tests in both
  modes. Composite p-values use the maximum component p-value; Holm retains the
  two-claim family, including skipped claims at p=1. Shared calendar-block indices,
  paired coverage, materiality scope, confirmation-half positivity, concentration,
  and era arithmetic are explicit. A 0.67 positive-era threshold with three eras
  requires three positives; it is not silently rounded down to two.
- Literal selection, embargo, confirmation, and half boundaries replace the
  moving last-96 rule. Calendar annual blocks are not declared independent.
  Embargo-origin training labels remain excluded; maturity supplies the purge.
- Ridge standardization, empirical residual distributions, tertile ties,
  unavailable folds, and distinct downside-episode support are specified as
  proposed rules. Return, downside, policy, transfer, and deployment outcomes are
  separate. Numeric downside support is a proposed design choice requiring the
  synthetic review; it is not evidence of adequate historical support.
- Policy returns use monthly execution intervals. The static risk-matched
  benchmark receives the qualification gates; cash receives a positive mean
  excess-return check, and buy-and-hold remains an explicit contextual comparison.
  A cash Sharpe-like ratio with zero excess volatility is undefined.
- GS3M supplies the proposed cash proxy under strict holding-start publication
  rules. Feature vintage admission remains inclusive at the forecast cutoff.
  These are different uses, stated explicitly. Reconstructed ETF inputs can
  support only conditional historical research; CAPE and NFCI stay diagnostics.
- The proposed source audit hash-links to v3, inherits its exclusions, and pins
  reuse of its raw root and manual QQQ source. It does not migrate or acquire data.

The v5 JSON Schema closes every field and pins scientific values with `const`.
A scientific change therefore requires updating the proposal, its schema, the
source-audit preregistration hash/schema, and the review report together. This
strict proposal schema is deliberate; it is not a generic configuration schema.
The loader also checks ledger/model/claim consistency independently. The archived
v4 schema is selected explicitly, preserving its original validation behavior.

## Simulation design and current next step

The simulation design is frozen in
[config/cycle1-simulation-v1.json](../config/cycle1-simulation-v1.json). The
synthetic primary return evaluator and bounded development profile are implemented.
See [CYCLE1_SYNTHETIC_DESIGN.md](CYCLE1_SYNTHETIC_DESIGN.md) for pre-output calendar
and CPI corrections, scope, exact identities, performance, and remaining work.
The actual fixed confirmation calendar has 97 months (48/49 halves); 96 was the
archived target count, with October 2024 missing. Score ordering is diagnostic,
not an additional primary location gate.

The existing implementation now includes conditional QQQ transfer, score-ordering
diagnostics, and downside and policy calculations with controlled fixtures.
The latest available-branch profile projects 1,801.30 seconds against the frozen
3,600-second budget, with exact equivalence to the saved primary results. This
supersedes the earlier 71-minute estimate. However, conditional feature surrogates
do not validate the full market feature pipeline; the frozen generator supplies
neither daily-close downside paths nor next-session-open execution tapes.
Downside and policy therefore remain unavailable in simulation, and a full
procedure runtime or power result has not been established.

The immutable [terminal decision](../experiments/cycle1-power-v1/decision.json)
and [stop report](../reports/cycle1-power-stop-7d7b93257f67e058/report.json) record
`INSUFFICIENT_EVIDENCE` / `STOPPED_BEFORE_LOCKED_VALIDATION`. This is an evidence
scope stop, not demonstrated statistical power failure. Zero locked validation
replications were drawn; no power or false-qualification bounds were estimated.
The v5 contract-only command exposes `STOPPED_INSUFFICIENT_EVIDENCE`, and real
progression remains blocked. No numeric gates or design effects changed.

The current design cannot be reopened. One separate versioned redesign remains
available, but is not automatic: it needs a rationale linked to this stop,
complete missing evidence scope, new locked streams and identity, and explicit
use of the single redesign slot. No successor was created during this work.

Before source migration, independently back up and restore the raw archive.
The local restore below verifies preservation but does not complete that
requirement. No dataset is newly qualified by this amendment work.

## Verification

Latest synthetic verification and profile evidence are recorded in
[CYCLE1_SYNTHETIC_DESIGN.md](CYCLE1_SYNTHETIC_DESIGN.md). The following checks
describe the earlier proposal-only increment.

`npm run check` passed TypeScript compilation, 15 TypeScript tests, and 115
Python tests. Seventeen new tests cover proposal accounting, scientific mutations,
missing contracts, mismatched authorities, reproducible contract reporting,
and runner/direct-builder denial before any acquisition. The proposal tests
were rerun after the final contract wording changes.

The original metadata preflight returned expected exit 2 and hash
`352a046a5c12b63e712b7335ee0c9102d31af45a3978ac6ccf7228ea361772bf`.
A private local backup restored 1,976 files (285,642,437 bytes) into a separate
directory, verified every SHA-256, and reproduced that same blocked preflight.
The inventory and result are in
`backups/cycle1-amendment-20260908T033825Z/verification.json`; the backup directory
is mode 0700 and Git-ignored. The archive captures the intermediate proposal
revision at backup time; it is not a snapshot of subsequent code/doc changes.
It is on the same volume and is not an independent encrypted disaster-recovery
backup. PostgreSQL was not started or backed up. No source was migrated.
