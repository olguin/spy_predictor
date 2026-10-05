# Development evaluation — Company and Director baseline

The immediate objective is to measure the current prompts before tuning them.
Engineering tests establish execution and contract behavior; the separately
registered scorecard evaluates research usefulness. This is a development
experiment, not a release-case evaluation, publication or performance backtest.

The first live baseline and negative control are complete. Read the
[measured outcome and defects](../reports/investment-research/evaluation-v1/baseline-review.md):
four model calls, $0.402658 catalog cost, baseline **REJECTED**. The negative
control stopped with zero calls. The current v2.7 prompts remain unchanged.
The [verification record](../reports/investment-research/evaluation-v1/verification.json)
distinguishes passing engineering checks from the rejected live research result.

## Current runner

`python -m spy_predictor_quant.investment_research.evaluation` provides three
commands: `prepare`, `run --execute`, and `score`. Preparation performs no model
work. It imports a source-only v6 capture into a separate content-addressed store,
preserving raw documents, dates, hashes and evidence identities. Prior model
findings or calculations are refused as baseline inputs. The controller computes
the same deterministic comparison panel from the imported data.

The new registration freezes evidence, cutoff, prompt texts/version, runtime
source identity, task instructions, tools, limits, omissions, expected behavior
and rubric. No original state or publication is resumed or rewritten. Effective
input age is evaluated at the archived cutoff, explicitly not at the experiment's
execution time. The output is therefore never presented as freshly acquired
investment research.

The initial profile schedules Company (at most five calls) followed by Director
final synthesis (at most three). It retains the current model and reasoning setting,
with 350,000 input tokens, 48,000 output tokens, 900 seconds and a $3 catalog-cost
ceiling. There are no new source requests or downloads. Worker usage and cost are
checked after responses, so an individual response can exceed the remaining cap;
all observed usage is retained and further work stops. Missing usage stops work.

Only inspection of copied evidence and documents, deterministic calculations,
scenario calculations and submission are exposed. Other specialists, planning,
follow-ups, source acquisition and publication are outside this profile. Omitted
roles must be reported honestly. Full-team scheduling is refused for evaluation
state, and terminal/interrupted evaluations do not automatically replay paid work.
This isolates Company delivery and Director synthesis, not cooperation quality.

Every dispatch stores the complete request and response plus measurements of
request bytes, evidence bytes, tool-schema bytes and prior-findings bytes. These
are byte counts, not token estimates. Scorecards include provider-reported tokens,
catalog cost, attempts, rejected submissions, tools, per-role status and elapsed
time. Failures remain in the denominator. Unknown usage is explicitly a lower
bound, never silently treated as a free failed run.

## Predeclared usefulness rubric

Each dimension receives 0 (missing/misleading/unusable), 1 (useful but materially
incomplete), or 2 (specific, supported and decision-relevant):

| Dimension | What a reviewer must establish |
|---|---|
| Source support | Material claims agree with primary evidence, observation dates, fiscal periods, accounting and share basis |
| Valuation rationale | EPS and multiple ranges have defensible anchors and mechanisms; an arbitrary grid does not pass |
| Comparison | Company versus ETF differences and implied expectations are explained; incompatible methods/dates are qualified |
| Downside | Specific counter-case and financial transmission, with conditional downside and no invented probabilities |
| Change conditions | Observable, instrument-specific evidence explains how conclusions would change |
| Uncertainty scope | Supported observations survive unrelated gaps; material dependencies remain binding |

The initial development threshold is **at least 1 in every dimension and 10/12
overall**, with **zero unresolved critical defects**. A critical factual,
numerical, timing, attribution or required-analysis defect independently fails.
These are deliberately declared development criteria, not empirically calibrated
probabilities or immutable future product requirements. Any future revision must
be versioned before scoring the candidate it will judge.

There is no reward for merely producing a recommendation. A justified conditional
comparison can pass; blanket abstention that avoids available analysis fails.
Every manual score and defect requires a reason and references to artifacts in
the evaluation directory. Exact claim IDs/source paths should be included in the
reason. Assistant review can yield only a provisional pass; it cannot supply
human usefulness acceptance. Actual user review and unchanged M4 gates remain
necessary. A model grader, if added later, will be a diagnostic aid.

Scorecards distinguish `engineering_status` from `review_status`. A valid report
awaiting semantic review is `PENDING`, not accepted. A registered missing-input
case can pass its expected early-stop behavior with zero calls without counting
as a useful research report. Reviews and scorecards are content-addressed; the
top-level `scorecard.json` points to the latest derived score, retaining earlier
records for audit.

## Commands and artifacts

```sh
python/.venv/bin/python -m spy_predictor_quant.investment_research.evaluation prepare \
  --source reports/investment-research/readiness-v1/source-check-authorized \
  --output reports/investment-research/evaluation-v1/baseline-v27

python/.venv/bin/python -m spy_predictor_quant.investment_research.evaluation run \
  --output reports/investment-research/evaluation-v1/baseline-v27 --execute

python/.venv/bin/python -m spy_predictor_quant.investment_research.evaluation score \
  --output reports/investment-research/evaluation-v1/baseline-v27 \
  --review reports/investment-research/evaluation-v1/baseline-review.json
```

`prepare` refuses to overwrite a nonempty directory. The example baseline path
is an existing experiment after preparation; use a new path for another candidate.
For future prompt candidates, `--prompts v2.8` can select a new compatible prompt
directory after it is created and reviewed. Freeze it before execution; changing
runtime code or prompts invalidates an unexecuted registration. Do not rewrite
v2.7 as a candidate update or modify old registrations to bypass integrity checks.

`--omit-source SOURCE_ID` explicitly registers source removal and removes its
dependent sections from the copied packet. `--expect early_stop` registers the
expected zero-call stop when mandatory inputs are absent. Original captures are
unchanged. These interventions are development cases; they do not alter frozen
release cases or establish performance on an unseen cohort.

Read `registration.json`, `evaluation-report.md`, `scorecard.json`, task histories,
`requests/`, `responses/`, `request_profiles/` and the cited `evidence/` records.
The empty `review-template.json` does not represent a completed review.

## Sequence after the baseline

1. Diagnose the first failing stage using actual requests, accepted/rejected
   submissions and semantic review. Separate input visibility, context, turn
   limits, prompt instructions and judgment errors.
2. Make one focused prompt or context intervention and register a new candidate.
   Keep source packet, model, task profile and resource caps matched when isolating
   prompt effects. Report all attempted candidates and their cumulative cost.
3. Extend development tests to optional-policy missingness, conflicts, stale data
   and claim preservation in synthesis. Test Challenger's false-positive and
   missed-error behavior using explicitly seeded defects. Cover other roles before
   treating the full team as accepted. These live experiments are not yet run.
4. Run selected repetitions and then a bounded full-system development experiment.
   Check acquisition, scheduling, handoffs, follow-up value, synthesis and refresh
   together. Keep the original rejected run as the historical failure record.
5. Perform unchanged M4 comparisons of old pipeline, single capable agent and
   cooperating team: fixed-evidence synthesis separately from comparable-budget
   end-to-end research. Equal budgets do not imply equal actual cost or information.
   Keep release cases separate from iterative tuning, review output usefulness,
   and simplify/remove roles that do not justify their measured cost.

Delayed market observations belong to the existing observation contract. This
small research-quality experiment does not establish market outperformance.
