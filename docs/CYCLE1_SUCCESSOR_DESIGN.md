# Cycle 1 successor design review

Current implementation update: [mathematical repairs](CYCLE1_SUCCESSOR_REPAIRS.md)
now fix price support and establish annual nulls for the explicitly amended
candidate. `cycle1:repair-check` returns `SPECIFIC_BLOCKERS_REPAIRED_NOT_REGISTERED`.
Final authority links, registration, full-procedure integration/profiling and
locked validation remain pending. No scenario role or numeric gate is weakened.

Earlier implementation history: the
[candidate simulator equations](CYCLE1_SUCCESSOR_EQUATIONS.md) are now executable
on supplied innovations, including actual nine-feature feedback, macro releases,
daily prices, corporate actions, cash/excess targets and shareholder execution.
`npm run cycle1:equation-check` publishes a reproducible deterministic fixture.
The annual null for the actual process remains unproven; final authority freezing,
registration, full-procedure profiling and random validation have not occurred.
The subsequent [readiness review](../reports/cycle1-successor-readiness-3b7d5d92f7457de2/report.json)
returns `NOT_READY_TO_FREEZE`: the candidate dividend equation also fails positive
price support on a supplied shock. Repair that joint law and resolve the annual
null before registration; the single redesign slot is still unused.
The original v2 proposal/report below remain unchanged historical review records.

2026-09-08. The next main-goal increment delivers a **validated pre-output
proposal**, not a frozen simulation or a passing power result. It follows the
user's instruction to proceed after the v1 stop. No successor random draws,
market-data reads, dataset migration or real candidate evaluation occurred.

## Delivered contract

[Simulation v2 proposal](../config/cycle1-simulation-v2-proposal.json) links the
immutable v1 decision, stop report, design, v5 preregistration and source audit.
Its closed [schema](../schemas/cycle1-simulation-v2-proposal.schema.json) pins
the proposal's complete contents. The loader independently verifies the linked
authorities, unchanged scientific constraints, and distinct new stream IDs.

The proposal preserves the literal origin/selection/confirmation calendar,
all ten scenario parameter sets and their acceptance roles, the design/usefulness
effects, both primary cycle claims, Monte Carlo gates, resampling and compute
budgets. It cannot release development or validation. The proposed stream
entropies are 2026090803 and 2026090804; no draws have used them.

Proposal hash:
`d498c5d55ab206fd870e70e6cdcf0eafdd7c03bb051124ab25e876a21f7e6708`.

Run:

```bash
npm run cycle1:redesign-review
```

Exit 0 means the **proposal inspection** succeeded. The result is
`VALID_PROPOSAL_NOT_FROZEN`, with every execution permission false. Exit 1 means
invalid or inconsistent input. The deterministic
[review report](../reports/cycle1-redesign-proposal-0fe0d5f9b35ebef3/report.json)
binds the proposal, predecessor, schema and review implementation. Repeating the
command preserves existing report bytes and modification time.

## Required successor path

The path contract specifies the generation order and required evidence:

1. Generate macro observations and separately timestamped first releases,
   revisions and missing-value records.
2. At each actual XNYS month-end close, admit only the available information and
   derive all nine features and their expanding normalization from each
   instrument's own daily history. Latent dimension surrogates cannot stand in.
3. Use that completed feature state for the following month's return parameters.
   Generate chronological scheduled opens/closes, including early closes and
   corporate-action conventions, without future information entering the state.
4. Derive annual excess labels, daily-close drawdown events and next-session-open
   policy tapes from that shared path. Cash uses strict holding-start publication
   and actual/365 accrual. CPI cannot gate the cancelled excess-return label.
5. Preserve the full eligible calendar and explicit missingness. Exercise every
   downstream branch on deterministic fixtures even when random selection would
   skip it; branch exercises never enter qualification counts.

These are executable-contract requirements, not an implemented path generator.
Existing downstream code and the v1 timing report cannot establish this scope.

The first deterministic implementation is
[cycle1_path_evidence.py](../python/src/spy_predictor_quant/cycle1_path_evidence.py).
It verifies complete scheduled XNYS session inventories and derives the annual
equity leg, daily-close drawdown event, and a distinct monthly next-open equity
return from supplied synthetic total-return levels. It rejects internal gaps,
shifted month ends, missing endpoints, raw-price units and real-data evidence
tags. It deliberately returns `completePrimaryTarget: false`: cash, corporate
action construction, release timing and full features remain unverified. It has
no random generator, archive loader or connection to the stopped v1 runner.

## Scientific work required before freezing

### Current deterministic implementation progress

The subsequent increment added two testable building blocks, without changing
the proposal, frozen v1 code, gates, or random streams:

- [cycle1_null_law.py](../python/src/spy_predictor_quant/cycle1_null_law.py)
  checks exact finite-state conditional return distributions using rational
  arithmetic. It includes a predictable, persistent baseline with no incremental
  information from the extra state, plus a counterexample whose one-month laws
  agree but twelve-month outcomes differ. It also detects equal-mean but
  different-scale laws. Run `npm run cycle1:null-law-check` for these algebraic
  fixtures. They are not simulation performance output.
- [cycle1_successor_inputs.py](../python/src/spy_predictor_quant/cycle1_successor_inputs.py)
  implements explicit-timezone synthetic vintage selection, missing-revision
  tombstones, inclusive feature admission versus strict cash admission, and
  actual/365 cash accrual with every scheduled monthly boundary required. It
  records which observation/revision supplied each interval. Future revisions
  cannot rewrite earlier accruals. Tests expose legacy boundary and missingness
  differences without mutating the stopped implementation.

The precise information-null condition is equality of the **full twelve-month
excess-return law** across extra-feature states sharing the same baseline
information. Matching means or one-month laws is insufficient. A sufficient
condition for a finite-state Markov generator is equality of the joint
distribution `(next baseline state, next excess return)` within every baseline
group. Conditioning on that pair and iterating proves equality of accumulated
return laws at every horizon. The checker verifies that stronger condition as
well as directly computing the twelve-month laws.

This does not yet prove that the continuous market/feature generator has that
property. Its actual rolling features, volatility and macro release history must
be represented in the state and checked; arbitrary finite-state examples cannot
substitute. An information null also does not guarantee identical finite-sample
CRPS between differently estimated or misspecified comparators. The eventual
whole-procedure simulation must still measure actual false qualification.

Raw split/dividend equations and separate shareholder execution accounting are
now implemented and tested in the successor equation engine. It distinguishes
entry- and exit-day dividend entitlement. The older daily helper alone still
does not prove raw-action units; use the new engine and its validated target path.

The proposal intentionally records four unresolved items rather than asserting
that a linked schema proves a complete scientific design:

- **Annual null validity.** Specify the conditional law of the full 12-month
  target in the no-skill and strong-baseline partial-null scenarios. With
  path-derived stress, volatility persistence and feedback, a zero coefficient
  in a one-step equation does not imply no additional annual information. For
  example, current drawdown or daily volatility can reveal a persistent variance
  state not retained by a coarser comparator. A false-qualification rate is
  uninterpretable if its nominal null actually contains incremental information.
  This is a design concern, not an observed simulation failure. Keep every
  original required null scenario; do not change its role to report-only.
- **Daily/macro equations.** Fix overnight/intraday allocation, actual-session
  scaling, joint shocks, crash timing, positive macro transforms, release lags,
  revisions, missing-value semantics, cash and corporate actions numerically.
  Set these before any random performance output; do not pick them by searching
  for a passing development result.
- **Implementation parity.** Establish one verified feature/target path for
  synthetic and eventual research use. The current feature vintage index skips
  missing records, while cash selection processes missing revisions; this needs
  an explicit contract and hand-checkable tests before a successor implementation.
  Preserve stopped v1 code identities while developing its successor.
- **Authority transition.** Link the final schema, simulation, preregistration,
  source audit and redesign registration together. The current v5 proposal still
  points at v1. Merely adding a new simulation file must not switch the runner.

## One-redesign accounting and next increment

The immutable v1 record retains its historical count of zero redesigns. A draft
review does not consume the slot and creates no experiment registration. Before
the first successor development draw, atomically record the **one final frozen
successor** in `experiments/cycle1-power-redesign/registration.json`, linked to
the v1 stop and new design identity. The current review refuses to replace or
reset an existing registration. No freeze or release command exists yet.

The next bounded increment is to resolve the four pre-freeze items above, starting
with annual-null validity and causal generator equations, and test their algebra
and timing with hand-constructed paths. Then freeze/register the single successor
and implement its full path without changing the stopped v1. Only a complete
fixture suite and whole-procedure runtime profile can precede locked validation.
If the design cannot satisfy those constraints, retain an explicit stop instead
of using nominal nulls or reducing scientific requirements.

## Verification

Nineteen new tests cover immutable reproducible publication without any archive
or random draws, corrupt/missing predecessor evidence, existing-registration
denial, new/distinct streams, and rejection of rehashed changes to effects,
calendar, scenario roles, gates and budgets. Independent semantic checks also
reject several accidental matching schema/config edits. These tests establish
the proposal boundary only; they do not verify a full-path generator or power.
Seven further hand-constructed path tests verify an intramonth loss that is absent
from month-end returns, an open-price gap distinct from annual label returns,
internal-session and endpoint rejection, and invariance to levels after the
target end. No random replication indices are used by these tests.

Final `npm run check` passed compilation, 15 TypeScript tests and 178 Python
tests. The successor review published the linked report successfully. The old
`cycle1:power-audit` still reproduced stop hash `7d7b93257f67e058` with expected
exit 2. Documentation links and `git diff --check` passed.

Subsequent combined-track verification passed compilation, 15 TypeScript tests
and 206 Python tests. Nine annual-law and seven synthetic vintage/cash tests
were added to the main track; twelve workbench tests cover the secondary track.
Both expanded notebooks executed on synthetic inputs with zero errors. No
successor random streams, real candidate outputs or confirmation were opened.
