# Specialist prompt improvement loop

October 3, 2026: the user requested [default promotion](AGENTIC_INVESTMENT_SYSTEM_V1_PROMOTION.md).
The exact reviewed role prompts are frozen as v2.17 and active for new v6 runs.
This supersedes the earlier decision to withhold default promotion; it does not
mark the original broader campaign or V1 release gates as passed.

Status: per-role development target reached with a focused repair, September 21,
2026 (completion September 22 UTC). The broader multi-case campaign is deferred.
See the [final outcome](../reports/investment-research/evaluation-v1/role-target-outcome.md).
User authorized iterative specialist improvement and paid evaluations. No release-case
tuning, publication, or market-performance claim is authorized by a development rating.

## Frozen quality target

Every scheduled task receives five independently reasoned 0–4 scores: evidence
accuracy, analytical depth, decision usefulness, uncertainty handling and coherence.
VERY GOOD requires at least 16/20, every dimension at least 3, accepted task output,
known usage and no unresolved critical defect. EXCELLENT requires at least 19/20
with the same gates. These thresholds are frozen in each experiment registration;
failures cannot be averaged away. Assistant review remains provisional and cannot
supply actual human usefulness acceptance.

Assess all seven roles: Company, Macro, Technical, Geopolitics, Commodities,
Challenger and Director. Score both Director draft and final. Missing inputs do
not excuse shallow reasoning; they also do not authorize invented rates, policy,
commodities prices or exposure coefficients. A role can deliver strong bounded
conditional analysis without an unconditional security recommendation.

## Iteration procedure

1. Preserve the failed v2.7 baseline and original rejected publication.
2. Register source-only archived evidence, exact runtime and prompt hashes,
   schedule, omissions, quality rubric and resource limits before dispatch.
3. Execute the production model worker, tool contracts and usage accounting.
4. Review every task using specific output and source artifact references.
   Seek an independent critical review; retain disagreements and failed attempts.
5. Change prompts only for diagnosed failures. Runtime/context interventions are
   recorded separately; a combined intervention cannot establish prompt-only gains.
6. Register a fresh experiment. Do not resume a failed run under changed code.
7. Validate the successful candidate on a missing-evidence development case and
   challenge the reviewer with planted material errors plus a sound control.
8. Report the lowest rating across required cases and cumulative actual usage.
   Promote only after quality and regression checks; release acceptance stays open.

## First candidate: v2.8

The all-role profile schedules Company research (5 turns), four other specialist
research tasks (3 each), Director draft (3), Challenger review (3), Director final
(3). It exercises research/review/synthesis, not Director planning/triage or the
independent initial Challenger pass. Those workflow variants require separate
coverage before claiming the entire production orchestration is improved.

Changes include role-specific causal reasoning and review conditions, fiscal and
share-basis reconciliation, reverse valuation expectations, comparative arithmetic
checks and claim-to-dimension linking. The deterministic context profile exposes
outlook sections and selected latest filing keyword windows; all archived content
remains inspectable. Selection is mechanical and does not certify relevance.
Scenario outputs add break-even EPS/P/E and a clearly qualified constant-share
residual when annual/interim periods align. No mathematical result is generated
by a model.

The successful preparation is `all-roles-v28-round1b`. Two earlier preparations
stopped with zero model calls because proposed resource limits exceeded schema
maxima; those directories remain as failed setup artifacts. Registered ceiling:
28 model calls, 900,000 input tokens, 100,000 output tokens, $10 estimated catalog
cost, 1,200 seconds; no source requests or downloads. Cost/output ceilings can be
observed only after a provider response and are not a guaranteed prepaid cap.

## Commands

```sh
python/.venv/bin/python -m spy_predictor_quant.investment_research.evaluation prepare \
  --source reports/investment-research/readiness-v1/source-check-authorized \
  --output reports/investment-research/evaluation-v1/NEW-EMPTY-DIRECTORY \
  --profile all_roles --prompts v2.8
python/.venv/bin/python -m spy_predictor_quant.investment_research.evaluation run \
  --output reports/investment-research/evaluation-v1/NEW-EMPTY-DIRECTORY --execute
python/.venv/bin/python -m spy_predictor_quant.investment_research.evaluation score-roles \
  --output reports/investment-research/evaluation-v1/NEW-EMPTY-DIRECTORY \
  --review PATH-TO-EVIDENCE-LINKED-REVIEW.json
```

Jev investigation is separate: see the [implementation plan](AGENTIC_INVESTMENT_SYSTEM_V1_JEV_PLAN.md).
No Jev production integration or measured savings has been claimed.

## Measured iteration 1 and response

`all-roles-v28-round1b` ended incomplete: 15 calls, 545,907 input / 16,083
output tokens, $1.284810 estimated cost, no acquisition. Independent development
scores: Company 12, Macro 11, Technical 13, Geopolitics 14, Commodities 10 /20.
Director draft exhausted its turns after two rejected submissions; draft/final
Director and Challenger have no accepted output and receive zero delivery scores,
explicitly not an analysis-quality assessment. No role passed.

The independent review and deterministic role scorecard are retained inside that
run. Shared weaknesses were overbroad critical gaps, uninspected-versus-missing
confusion, weak interpretation of calculated valuation thresholds, and vague
change conditions. The evaluator's initial questions also repeated the entire
mandate for every specialist, encouraging role overlap.

The separately registered `all-roles-v29-round2` rewrites specialist instructions,
limits task questions to each role, and requires instrument identities in draft
transport as well as final transport. This is a combined prompt/task/transport
intervention, not evidence of prompt-only causation. Company is required to
interpret residual EPS and reverse-expectation thresholds; other roles contribute
specific mechanisms and observable analytical changes. The original model and
archived inputs remain unchanged.

A registered `--challenge` option now adds an explicitly unverified alternative
candidate after an accepted Director draft. It reverses the actual bull-sensitivity
ordering, overclaims current policy clearance, and adds one true dated-close
control. The original draft is preserved. Synthetic claims are never presented as
model output or published. Challenger's passing rating also requires identifying
both material errors without critically flagging the sound control; independent
review still assesses the objection reasoning and Director dispositions.

## Measured iteration 2 and third candidate

`all-roles-v29-round2` ended incomplete: 15 calls, 566,711 input / 21,068
output tokens, $1.364350 estimated cost. Independent scores: Company12 (critical
upside/downside and fiscal-timing contradictions), Macro14, Technical16 VERY_GOOD,
Geopolitics15, Commodities16 VERY_GOOD. Director again exhausted draft turns; no
accepted Challenger or final output. The first two iterations total30 calls and
$2.649160, all usage known. Scores are not averaged across roles to declare success.

`all-roles-v210-round3-high` is a new combined intervention: explicit blocking-gap
semantics in prompt AND tool-schema descriptions, deterministic absolute-loss versus
bull-gain asymmetry, and all dimensional validation conflicts returned together.
The same model is registered at high reasoning effort with a10,000-token response
ceiling instead of medium/6,000. Any gain cannot be attributed to prompts alone.
The global registered limits remain unchanged. No production prompt promotion yet.

The campaign aggregator records every supplied iteration's usage and accepts only
a complete candidate cohort with identical prompts, runtime, rubric and source
capture, containing both an ordinary case and a missing-evidence/planted-error
stress case. Each role's cohort score is its minimum across tasks/cases. Use:

```sh
python/.venv/bin/python -m spy_predictor_quant.investment_research.evaluation_campaign \
  --run PATH-TO-EACH-ITERATION --candidate PATH-TO-SELECTED-PRIMARY \
  --candidate PATH-TO-SELECTED-STRESS --output PATH-TO-CAMPAIGN-JSON
```

Repeat `--run` for every measured iteration, including both selected candidates;
never omit failed attempts from the spending ledger.

## Iterations 3–5: calendar correctness and runtime interruption

`all-roles-v210-round3-high` consumed 18 calls, 713,898 input / 24,838
output tokens and $1.7124888 estimated cost. Macro, Technical, Geopolitics and
Commodities reached VERY_GOOD. Company still misstated fiscal dates and treated
out-of-guidance stresses as guidance endpoints; Director repeated errors and
omitted useful thresholds. Challenger did not complete, and final synthesis was
not reached. This is a failed iteration, not a passing ensemble assembled from
individually successful roles.

v2.11 exposes deterministic fiscal calendars derived from archived company filings:
NVDA FY2027 ends January 31, 2027; MU FY2026 ends September 3, 2026. Both are
disclosed 53-week years. Ambiguous or unsupported calendars remain unknown.
Scenario calculation rejects contradictory dates and retains calendar provenance.
The prompts distinguish management guidance bounds from additional stress cases,
retain fixed-input break-even conditions, and prohibit unmeasured fund comparisons.

`all-roles-v211-round4-high` stopped after a Technical worker abort with unknown
provider usage. Its measured lower bound is 7 calls, 214,904 input / 6,208 output
tokens and $0.504304; one attempted response cannot be priced. Accepted Company
and Macro outputs scored 16/20 analytically, but unknown run usage prevents a
passing registered score. Earlier accepted outputs do not repair the failed run.

The aborted response arrived beyond its 180-second deadline. The worker previously
checked a monotonic clock, which can exclude host sleep; this is a possible cause,
not a proven diagnosis. The runtime now also checks wall time, rejects late output,
and preserves any measured provider usage before rejecting its action. Tests cover
clock advancement and late known-usage responses. `all-roles-v211-round5-high` is
a fresh registration with the same v2.11 prompts and high/10,000 model settings;
the retry is a runtime intervention. Its outcome remains pending until independent
review, deterministic scoring and the separate stress case complete.

Before iteration 5, the loop totals 55 attempted calls and at least $4.8659528 in
catalog research-model cost. The unpriced abort makes this a lower bound. This
excludes the earlier v2.7 baseline, original pilot and coding/review assistant usage.

## Iterations 5–7: preserve analysis during review

Round5 completed in16 calls, 650,585 input /25,187 output tokens and $1.5937372.
All five specialists and Challenger reached VERY_GOOD. Director draft and final
scored15/20 and failed: the draft gave selected grid asymmetry too much comparative
weight; final removed that implication but also dropped explicit residual earnings
interpretation and descriptive gain/loss comparison. Completion is not quality
acceptance. The reviews and deterministic scorecard remain in that run directory.

v2.12 changes only the Director prompt. Each company valuation field must contain
its actual numeric residual bridge, guidance-versus-stress interpretation,
fixed-input reverse thresholds and descriptive scenario sensitivities. Review
corrections remove the faulty inference while retaining supported analysis;
selected stress-band asymmetry still cannot establish attractiveness or preference.

Round6 used7 attempted calls, 215,097 known input /6,134 known output tokens and
at least $0.503802. Company and Macro completed; Technical timed out with unknown
usage. The Mac power log confirms idle sleep at01:33:55UTC and wake at01:41:41UTC,
during the Technical request beginning01:33:27UTC. The new wall deadline correctly
stopped the run on wake. This is an infrastructure interruption, not a measured
quality failure for the unexecuted roles.

`all-roles-v212-round7-high` repeats the unchanged registered candidate with
`caffeinate -i` limited to the evaluation process. It prevents idle sleep while
that process runs; it does not change model settings or acceptance standards.
Through round6, the loop records78 attempted calls and at least $6.963492 in
catalog research-model cost, with two unknown attempts. The active retry and
eventual stress case must be added before a final accounting or quality claim.

## User-directed efficiency correction

The user challenged the repeated whole-team reruns and elapsed time. The active
round8 will finish and deliver its report and scorecard. Any remaining role failure
will be addressed through a separately registered specialist replay, rather than
another automatic whole-team run. The extra missing-evidence/planted-error campaign
is deferred. Its original two-case acceptance criteria are retained and must not be
reported as passed without those cases. The per-task rubric and critical-error gate
are unchanged; targeted role passes must be identified separately from end-to-end
cohort success. No new live source acquisition or production release is implied.

Round7 completed18 calls, 776,144 input /32,870 output tokens and $1.9315216,
with all usage known. Seven tasks reached VERY_GOOD, including both Director
stages; Commodities scored15/20 because it required management attribution and
quantification before revisiting qualitative risk. v2.13 changes only that prompt:
credible applicable independent evidence can justify conditional review before
the effect can be sized. The active run is `all-roles-v213-round8-high`.

## Completed round8 and focused Technical repair

Round8 completed all tasks in 17 model calls, 758,397 input / 37,382 output tokens
and $1.941186, all usage known. Seven tasks reached VERY GOOD, including both
Director stages and the repaired Commodities contribution. Technical scored 10/20
with a critical direction error: it described QQQ as lagging SPY at all windows,
while the archived panel shows positive 5/21-session and negative 63-session excess
returns. The Director report uses the correct 63-session comparison and does not
repeat this error. The full-run score remains failed.

v2.14 changes only Technical: report signed values independently for each horizon
and audit every summary/claim/counter-case direction against them. The new
`specialist` profile dispatches only the selected research role, under the same
source packet, context projection, worker, tools, accounting and quality rubric.
It cannot schedule synthesis, delegation or the other specialists. Its Technical
task permits at most three turns; the actual repair took **one call**, 24,207 input /
2,835 output tokens and $0.082434. Independent review checked all 18 signed
comparisons and graded it 16/20 VERY GOOD.

```sh
python/.venv/bin/python -m spy_predictor_quant.investment_research.evaluation prepare \
  --source reports/investment-research/readiness-v1/source-check-authorized \
  --output reports/investment-research/evaluation-v1/NEW-EMPTY-DIRECTORY \
  --profile specialist --role technical --prompts v2.14 \
  --reasoning high --max-output-tokens 10000
```

Do not interpret this repair as a successful full-team rerun. The per-role result
explicitly selects Technical's focused review and the other roles' round8 reviews;
the v2.14 prompt hashes match those reviewed role prompts. Planning, triage, initial
independent risk assessment, fresh acquisition and the additional stress campaign
remain unvalidated by these role scores. Production prompt defaults are unchanged.

The original Challenger review was reconsidered against its actual assignment:
a missing multiple-range selection rule can be a legitimate material analytical
improvement even when a grid is labeled hypothetical. It preserved valid arithmetic,
kept the gap noncritical, and required empirical history only if empirical relevance
was claimed. The independent review records this reasoning; no scoring threshold
changed to obtain a pass.

All nine measured runs (eight full-team iterations plus one specialist replay) are
retained. The ledger totals 114 attempted calls, 4,465,850 known input / 172,605 known
output tokens and at least $10.9186336. Two interrupted attempts have unknown usage.
The monitor's backend and browser now treat evaluation completion/failure as terminal;
the old display could incorrectly show finished evaluations as running or stale.
Original source capture, pilot, publication and frozen cases still pass preservation
checks. No further paid run is active or automatically scheduled.
