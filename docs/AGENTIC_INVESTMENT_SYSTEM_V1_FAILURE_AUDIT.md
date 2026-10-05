# Revised live system: failure audit — October 4, 2026

## Decision and current status

The user asked why failures were repeated and whether to stop. The recommendation
is to pause paid evaluations and complete an offline audit. A choice to stop the
existing run7 immediately or let only that run finish is pending. No further paid
run will be launched while it is pending. The goal is still active and unmet;
there is no inferred permission to pause or declare it complete.

The repeated failures have distinct causes. Some agent analyses needed substantive
correction. Several other attempts stopped because our controller/worker code or
resource allocation was defective. Whole paid reruns were started before all
affected paths were checked together. That process was an assistant execution
mistake, and passing isolated tests was insufficient evidence for rerunning.

## Preserved terminal attempts

Artifacts are under `reports/investment-research/live-goal-v1/`. These amounts are
recorded research-model catalog estimates, not invoices or coding-assistant cost.
Unknown receipts remain unknown; incomplete runs are never counted as quality
passes. Terminal runs total **$16.3789204 known catalog cost**, plus unknown usage
in NVDA/MU run1 and run6. Active run7 is additional and excluded from this total.

| Case | Execution | Principal defect | Recorded cost | Evidence and repair |
| --- | --- | --- | ---: | --- |
| ANET run1 | Draft complete | Policy applicability remains a scoped missing input | $2.9477610 | `anet-development-review2.json`; provisional 16–18/20 role reviews; not current v2.21 acceptance |
| NVDA/MU run1 | Incomplete | Host sleep exceeded worker deadline during synthesis | $3.4234426 + unknown | Original state; temporary idle-sleep assertion and wall-clock deadline |
| NVDA/MU run2 | Draft complete, quality failed | Company conflated GAAP residual with operating continuation; Challenger contradicted truncated citation without reading full text | $3.8752650 | `nvda-mu-development-review2.json`; targeted earnings and full-text inspection requirements |
| NVDA/MU run3 | Incomplete | Director repeated an already handled question; controller rejected it | $2.9447954 | `nvda-mu-development-review3.json`; pending-only routing and idempotent same-decision handling |
| NVDA/MU run4 | Incomplete | Company lacked required NVDA scenario grid after seven-turn allowance | $1.1008184 | `nvda-mu-development-review4.json`; stock-scaled capacity and reserved calculation turns |
| NVDA/MU run5 | Incomplete | Python tool generator looked up submission after narrowing tools to calculation | $1.0345436 | `nvda-mu-development-review5.json`; return restricted schema immediately; runtime drift explicitly qualified |
| NVDA/MU run6 | Incomplete | TypeScript rejected Python's calculation-only envelope | $1.0522944 + unknown | `nvda-mu-development-review6.json`; exact reserved exception in worker allowlist |

The delivery gate correctly exposed missing work in run4. That protection does
not excuse the insufficient scheduling that caused the missing work. Numerical
verification of run2 also did not prove its prose or individual agents were sound.

## Engineering evidence and its limits

- 108 Python regressions passed, including live contract, routing, legacy
  compatibility, delivery and local workspace HTTP behavior.
- Eight TypeScript contract/worker tests passed, including one-call execution,
  reserved calculation, measured failure receipts and blocked continuation.
- Updated compact-layout Chrome checks passed: explicit stock/horizon entry,
  seven agent reports, global sections, optional charts, responsive views and
  no JavaScript exceptions. Browser checking used zero provider calls.
- New `pi-research-python-boundary.test.ts` passed actual Python-generated
  schemas through the TypeScript validator across one through five companies,
  ETF-only/mixed scope, all roles/stages, last-turn submission, pending/completed
  routing and every reserved calculation. Source acquisition and models are
  never invoked. Existing runtime files were not changed during run7.

The new test closes a specific gap between the two languages. It proves envelope
compatibility, not SDK schema acceptance, useful model decisions or live complete
delivery. The mocked worker tests cover execution/receipt behavior separately.
Live v2.21 quality is still unproven. An accepted Company task alone cannot prove
the whole system, and engineering counts cannot substitute for role reviews.

## Gate before any further paid attempt

1. Revalidate the current run handle and terminal state. Never start replacement
   work because an observation timed out. Respect the pending stop decision.
2. Keep runtime code frozen during a live evaluation. For a diagnosed defect,
   preserve the failed run and isolate its reproducer offline first. Require
   real Python/TypeScript contract checks whenever offered tools change.
3. Require the relevant controller, worker, budget, receipt and browser checks
   to finish before launch; correct any admission claim whose check was pending.
4. Register one bounded experiment with a precise hypothesis and frozen rubric.
   Use a focused replay when the defect is local. A whole run requires evidence
   that the defect affects the complete flow and cannot be validated locally.
5. Review every role's facts and reasoning against the complete cited source,
   numerical outputs, actual fiscal/share basis and scoped missing inputs.
   Maintain the original floor: 16/20, each axis at least 3, no unresolved
   material output error. Do not lower it to declare success.
6. Review the delivered report: selected stocks and horizons, source/quote
   clocks, material global mechanisms, conditional consequences, practical
   advice, view-change conditions, all seven readable agent reports and
   scoped optional charts. Record known/unknown usage and elapsed time.

The complete revised goal remains unchanged. One-to-five-stock behavior and
quality/performance must be demonstrated at the relevant scope before completion;
a synthetic scope check or a single successful development case is insufficient
to claim universal quality. Human usefulness, release acceptance and investment
returns retain their separate evidence requirements.

## Run7 terminal addendum

Run7 finished normally at2026-10-04T22:44:27.934441+00:00 (14.74 minutes,34 calls,$4.0665086, known receipts). Numerical/archive and actual browser checks pass, but final quality fails a post-review source/proposition mismatch in NVDA global forces. Director15/20 FAIL; six other roles16–19/20 provisional. See `nvda-mu-development-review7.json`. All live attempts are now terminal, with $20.4454290 known catalog cost plus unknown run1/run6 receipts. The earlier active-run budget snapshot remains historical. User preference to pause all work or continue offline fixes is pending; no new paid run.
