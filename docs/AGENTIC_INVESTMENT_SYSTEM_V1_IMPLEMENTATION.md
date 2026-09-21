# Investment research V1 implementation

Updated September 20, 2026. **V1 is not released.** M1 engineering acceptance is
retained in `m1-live-v4`. M2 now implements the full roster, five-instrument grouped
research, scoped findings, ETF look-through, scenario valuation, fixed benchmark
context and canonical review conditions. M2 engineering acceptance passed with
`m2-live-v7`; the source/claim review and remaining limitations are recorded below;
M3 publication/monitoring is now implemented with synthetic engineering evidence;
see the [M3 continuation record](AGENTIC_INVESTMENT_SYSTEM_V1_M3.md). M4 release
comparison and actual user usefulness acceptance remain open.

Read the [full conformance audit](AGENTIC_INVESTMENT_SYSTEM_V1_AUDIT.md). The original
plan remains the acceptance authority. The existing META runner, forecasts,
observation ledgers, historical cohorts and holdouts remain separate.

## Current implementation

- Python controls tasks, evidence, tool authorization, budgets and draft acceptance.
  A separate Pi worker selects one action per authorized invocation. Its next
  invocation receives the task history and tool results; each turn has a receipt.
  The legacy Pi adapter's one-call contract remains unchanged.
- Mandate v3 supports up to five companies/ETFs. Director, Company, Macro, Market
  Behavior/Technical, Geopolitics and Challenger form the core team; Commodities
  is optional with an explicit omission reason. Tasks can share multiple symbols.
  Mandates v1/v2 retain the single-company workflow. Initial
  specialists and the independent Challenger do not see the Director's preferred
  conclusion. Task-specific manifests describe their actual visible evidence.
- Initial Director assignments are neutral. Specialist and challenge requests go
  through Director triage. The Director can approve new research, explicitly reuse
  a completed answer from the requested specialist, or decline with reasons.
  Requests retain their dependency, instrument, horizon, impact, deadline and
  model-turn allowance. Two shared follow-up rounds remain the maximum.
- The broker reuses existing primary-feed and SEC parsers. Discovery indexes dated
  documents from configured publisher feeds and SEC submissions. It admits linked
  documents only within the publisher boundary; it does not expose arbitrary URLs.
  Reading an index does not mark its linked articles as read.
- SEC submissions and company facts retain filing/accession, fiscal period, units
  and revision context. Credentials remain in the broker environment. A capability
  check verified actual issuer/Fed/SEC access, distinct from credential presence.
- Decimal calculations can resolve `evidence_id#/json/pointer` inputs directly from
  stored numeric fields. Literal decimal inputs remain labeled scenario assumptions.
  Formula suitability and semantic source support still require review.
- Original objections and question IDs are required keys in final response objects.
  A versioned transport deterministically restores those objects to stored lists.
  It does not repair the model's judgments or rename objections. Only Challenger
  creates formal objections; other roles record gaps and counter-theses.
- Atomic checkpoints, immutable request/response/evidence/product files, parent
  manifests and copied runtime source files make runs auditable even with a dirty
  worktree. No interrupted or failed paid attempt is silently retried. Completed
  acquisition and accepted turns can be reused on a valid restart.
- Successful runs produce Markdown and structured JSON **drafts**. Publication
  timestamps and observation contracts remain null. `review` and `evaluate` are
  deliberately not exposed before their implementations exist.

## M2 additions

- New mandates freeze a benchmark context list independently of the watchlist and
  declare source scopes. Seed acquisition shares normalized evidence across all
  roles within one global source/token/time budget. Initial specialists retain
  independent findings contexts; only shared factual evidence is seeded.
- Existing Alpaca daily metrics, SEC company facts, FRED CSV and sponsor ETF parsers
  are wrapped by the bounded broker. Alpaca authentication stays in the environment;
  endpoint/feed/adjustment and payload symbol are checked. Saved dataset imports
  require a frozen hash and original capture time. Capture/end times prevent a
  partially captured session becoming a completed close later.
- Relative-strength comparisons require matching date/feed/share/return basis.
  The comparison panel records exact decimal differences of the stored metrics.
  Fixed SPY/IWM/HYG context does not use watchlist RSI/breadth. Missing context is
  explicit. Price returns exclude cash dividends and are descriptive only.
- QQQ look-through retains holdings dates, stale/partial coverage, concentration,
  sponsor costs and selected-company overlap. It never implies known portfolio
  weights. Each ETF thesis has a required look-through explanation or missingness.
- `scenario_price` calculates assumed earnings/share × assumed P/E with Decimal;
  recorded scenario outputs can feed percentage comparisons without copying numbers.
  Bear/base/bull assumptions remain scenarios; source-linked extraction stays distinct.
- Claims, gaps, objections and requests carry symbol scopes. A critical missing
  source or unresolved objection blocks only its affected assessment. Final instrument,
  question and objection identities are required keys on the model response and
  restored deterministically. All specialist completions/omissions are reconciled
  with actual tasks; nonessential missing sources do not force all results to WAIT.
- Machine review conditions use `completed_close`, symbol, comparator, decimal
  threshold, share basis, expiration and evidence. `human_review` has no fabricated
  price trigger. Legacy arbitrary aliases are rejected, not silently translated.
  Evaluating conditions and checking expiration before publication remain M3 work.
- SEC hidden inline XBRL is excluded from readable excerpts. Task creation/start/end
  and turn-limit telemetry support the next stage's monitor.

## Versions and cases

The initial `prompts/investment-research/v1/` and its synthetic report are retained.
The audit revision used `v1.1`; live findings then motivated `v1.2` and runtime
policy `investment-research-m1-v4`. The worker bridge is `pi-research-worker-v2`,
with action v3, findings v2 and draft-product v2 contracts. Earlier artifacts retain
their original versions and status. M2 uses prompts `v2.5`, mandate/findings/product
`v3`, action `v4`, and runtime policy `investment-research-m2-v7`; the Pi bridge
protocol stays `pi-research-worker-v2`. New versions do not rewrite old artifacts.

`examples/investment-research/development-cases-v2.json` and `release-cases-v2.json`
contain six distinct synthetic source-input mandates each, covering valuation,
macro conflict, policy exposure, ETFs, missing data and fast events. Expected
behavior is recorded before candidate evaluation and hashes freeze both sets.
These are runnable input mandates, **not passed release evaluations**. No candidate
has been evaluated on the release set. The original v1 case descriptions remain
specifications and are not retroactively promoted to acceptance evidence.

`examples/investment-research/comparator-v2.json` registers the already-completed
September 17 current-research packet, recovered report and verification record by
hash. Its original incomplete single-pass run, degraded product, publication lag
and unknown interrupted usage remain visible. It captures observed pre-change
behavior; a fresh budget-matched old/single/cooperative comparison still belongs
to M4. This does not open a historical evaluation cohort.

Evidence requirements by task:

| Task | Critical for a supported conclusion | Optional/contextual evidence |
|---|---|---|
| Company | Dated issuer/filing support for material operating, exposure or valuation claims; matching units/periods for arithmetic | Consensus, additional press coverage, peers when unavailable |
| Macro | Dated policy/source support for stated current policy facts; issuer exposure before a quantified company impact | Broader macro series and additional commentary |
| Challenger | Source/claim references for material objections; explicit unresolved dependencies | Independent corroboration when available |
| Director | Valid specialist findings, question effects and every original objection disposition | Additional research only when material and within the shared budget |

Missing optional evidence is reported. Missing critical evidence blocks the
corresponding conclusion; it does not supply invented numbers or probabilities.
Source-support quality remains a separate semantic review, not just schema validity.

## Run locally

From the repository root, with the existing environments:

```sh
source ~/.nvm/nvm.sh && nvm use 22
packages/agent-runtime/bin/pi-research-worker --preflight
node --env-file=.env scripts/investment-research.mjs check-sources \
  --mandate config/investment-research-m2-live-v7.json \
  --output reports/investment-research/my-source-check
node --env-file=.env scripts/investment-research.mjs run \
  --mandate config/investment-research-m2-live-v7.json \
  --output reports/investment-research/my-run
node --env-file=.env scripts/investment-research.mjs inspect \
  --output reports/investment-research/my-run
node --env-file=.env scripts/investment-research.mjs resume \
  --output reports/investment-research/my-run
python/.venv/bin/python scripts/audit-investment-research-m2.py \
  reports/investment-research/my-run
```

Use a new directory for each run or source check. `run` makes real model calls;
`check-sources` makes source requests only; `--preflight` makes neither paid model
calls nor research acquisitions. A fixture mandate replaces source data but the
CLI still uses the real model. The test double exists only in tests. `inspect`
is read-only. A frozen runtime/configuration mismatch prevents resume.

Read `draft.md`, `state.json`, the immutable artifact directories and `code/`.
The structural audit checks receipts, retrieval, cooperation, question effects and
manifest identities; it explicitly requires a separate semantic review.

## Bounds and current coverage

The live profile retains 16 tasks, 40 model calls, 250 source requests, 100 tool
calls, 1,000,000 aggregate input tokens, 100,000 output tokens, a $25 catalog-estimate
ceiling, two follow-up rounds and 1,200 elapsed seconds. Workers run sequentially,
below the two-worker ceiling. Source limits are 10 MB per document and 50 MB per
run, explicitly recorded before the live check. The larger per-document limit is
needed for SEC company facts; it does not authorize larger model context.

For M1, per-task ceilings are explicit: independent Challenger 4 turns, Director
planning 4, initial specialist 6, follow-up specialist 4, triage 5, draft 2,
Challenger review 3 and final Director 3. The last admitted task turn permits only
submission of findings. Final capacity is reserved before optional research.
Observed overages are retained. Provider token limits and catalog dollar estimates
may only be enforceable after a response; they are not exact spending guarantees.
Unknown usage/prices stop further work and are never represented as known zero.
Rejected submissions receive explicit contract feedback only while task turns
remain. Their raw responses and usage are retained as `REJECTED_VALIDATION`;
correction consumes a separately authorized model turn. No result is rewritten,
no turn ceiling is raised and provider/transport failures are not retried.

Coverage is limited to configured indexes and admitted linked documents. Unknown
source availability remains unknown; it is not inferred from article dates.
Long documents expose bounded excerpts and normalized SEC fields; unread or
unavailable sections remain gaps. General web search, comprehensive financial
exposure extraction, fresh executable quotes, broad news and consensus coverage
are not claimed. M2 adds registered Alpaca daily bars and FRED CSV adapters; access failure remains a
source gap. No broad-news subscription or consensus service is implicitly added.

For M2, the independent pass has 3 turns, planning 6, grouped research 5, follow-up
4, triage 5, draft 2, review 3 and final 3. Limits are ceilings, not extra reserved
budgets for each symbol. All five candidates share the same aggregate 40-call and
20-minute limits. Network source checks consume no model calls.

## M1 live validation record

- `m1-source-check-v2-sandbox`: four successful primary-source checks, zero model
  calls; actual source coverage and downloaded bytes retained.
- `m1-live-v2`: sandbox worker initialization failed. The attempt remains incomplete
  with usage uncertainty and was not resumed or overwritten.
- `m1-live-v2-authorized`: real retrieval and bidirectional Company/Macro questions;
  37 model calls. Validation rejected the final response because it replaced
  original objections instead of disposing of them. The original run remains
  incomplete, including its budget-omitted triage task and all measured usage.
- `m1-live-v3-registration.json`: freezes the corrective profile before another run.
  The new profile keeps the same model and aggregate ceilings while adding task
  limits, exact objection/question maps and explicit answer reuse.
- `m1-live-v3`: stopped after 13 calls because Company returned `watch` alongside
  a critical gap. This rejection remains intact. The next version added explicit,
  bounded validation feedback, rather than weakening the eligibility rule.
- `m1-live-v4`: **accepted unpublished draft**. Ten tasks completed in 350.79
  seconds, with 30 model calls, 7 source requests, 408,074 input tokens, 13,438
  output tokens and a $0.9469912 catalog cost estimate. Macro requested Company
  evidence, Director explicitly reused its relevant answer, and a later challenge
  caused a new Company investigation. Final synthesis accounts for four questions
  and all seven original objections. All usage is known; no correction turn was
  needed in this successful run (bounded correction is covered by tests).

Read the [accepted draft](../reports/investment-research/m1-live-v4/draft.md),
[structural audit](../reports/investment-research/m1-live-v4/acceptance-structural.json)
and [semantic review](../reports/investment-research/m1-live-v4/acceptance-semantic.json).
The draft correctly retains `insufficient_evidence` for a directional/relative-return
judgment: price/valuation and measured financing sensitivity are missing. Source
support for its final factual claims was checked against retained issuer/Fed
excerpts. Three noncritical defects remain recorded: absence-of-evidence wording,
inline-XBRL readability and underuse of the available normalized companyfacts tool.
This is an engineering review, not user usefulness acceptance or a release score.

Across the three receipted live runs, the known catalog estimates total $3.0334772
for 80 model calls. The separate failed sandbox attempt retains unknown usage.
These are measured iteration resources, not a claim of equal-cost quality versus
the legacy or single-agent comparators.

M1 checks at its acceptance: TypeScript and all 33 JavaScript tests passed; its complete
Python run passed 511 tests, including 28 focused research tests. Baseline hashes
confirm the previous META runtime/configuration files were preserved. The v2
development/release case hashes still match, and no release candidate evaluation
has been run on those cases.

## Remaining release gates

The completed M1 evidence meets the first cooperative-slice gate; neither the
scripted fixture nor the earlier rejected syntheses were counted as that success.
M2 now adds
Market Behavior, Geopolitics, conditional Commodities, five-symbol scheduling,
ETFs, valuation sensitivity, canonical machine conditions, fixed benchmark context
and shared-exposure reporting. M3 adds final refresh/invalidation, publication,
journal/review/feedback, corporate-action-safe publication-origin outcomes and the
[requested graphical run monitor](AGENTIC_INVESTMENT_RUN_MONITOR.md).
M4 compares the old pipeline, single agent and cooperating system under declared
budgets and requires reviewed usefulness evidence. V1 is M0–M4 complete, not simply
a working multi-agent loop.


## M2 acceptance work and retained iterations

The fifteen M2 regression cases cover a complete five-symbol cooperative fixture,
scoped missingness/objections, ETF fields, exact scenario calculations, canonical
conditions, fixed benchmark inputs, matching SEC issuer contexts, original capture
end times, immutable local imports, final instrument identities and value-preserving
context projections. The fixture has no paid model and proves infrastructure only.

`m2-source-check-v1` records the sandbox DNS failures and successful local ETF
imports. `m2-source-check-v1-authorized` records 22 successful sources out of 25:
SEC submissions/facts for ANET/MU/META/NVDA, ten candidate/benchmark price series,
QQQ sponsor imports and issuer/Fed feeds. FRED requests timed out and BIS returned
an HTTP error; those optional failures were not concealed. Both checks used zero
model calls. The authorized check downloaded 15,427,035 bytes.

The separately registered `m2-live-v1` candidate stopped incomplete on invocation
nine when a worker returned unknown usage. Eight known receipts total 475,804 input
and 4,760 output tokens, with $1.0004336 known catalog cost. The ninth invocation
remains unknown. Its old receipt's `model_calls=2` counted the guard's rejected
continuation attempt, not two admitted provider dispatches. The revised boundary
counts admitted and blocked calls separately and preserves a paid receipt when a
later synthetic SDK error reports zero usage. A regression test verifies that the
second provider dispatch does not happen. No old receipt was rewritten.

That iteration also exposed repeated normalized text/data in every task context.
Runtime v2 / prompts v2.1 replace duplicated excerpts with explicitly labeled
normalized projections, retain original numeric values/pointers, keep full evidence
available through inspection, and give planning only the source catalog. The
independent pass submits risks directly; research/review stages can request work.
The registered `m2-live-v2` candidate retains the same model, source inputs and
aggregate budget ceilings. Its result and review are recorded separately, without
promoting the earlier incomplete candidate or changing historical artifacts.


The `m2-live-v2` candidate also stopped at the Company worker boundary (10 admitted
calls), now with all usage retained: 188,333 input and 5,042 output tokens,
$0.4288756 catalog estimate. It did not reach synthesis and is not accepted.
Inspection of installed Pi 0.85.1 showed that its provider request enables parallel
tool calls by default. Runtime v3 adds a payload hook that requires one tool choice
and disables parallel calls, while retaining the independent admission guard.
This matches the [official OpenAI function-calling controls](https://developers.openai.com/api/docs/guides/function-calling).
The provider settings are tested in the worker wiring fixture; `m2-live-v3` is
separately registered with the same model, source mandate and aggregate limits.

Checks at runtime v3: TypeScript compilation, 34 JavaScript tests and 521 Python tests
passed. The complete Python suite includes 38 focused research tests. The saved
`m2-engineering-fixture-v3` draft completes all five instruments in 10 synthetic
tasks/17 synthetic invocations; its `FIXTURE-NOT-LIVE.txt` explicitly disclaims
real-model acceptance and investment performance. Baseline runtime/configuration
hashes remain unchanged apart from the deliberately updated plan document.
Development/release case hashes still match and release cases remain unevaluated.


`m2-live-v3` successfully completed the independent Challenger, planning, all four
core specialists, Director triage and a Company follow-up. It retained 31 known
model invocations, 871,922 input and 17,243 output tokens, $1.9148176 estimated
catalog cost, and 29 source requests. Conservative input admission then rejected
the draft request. This remains **incomplete**, not an accepted M2 report.

Runtime v4 reserves up to 300,000 of the **existing** aggregate input-token limit
against optional follow-ups (one third for smaller budgets), exposes remaining
resource ceilings and reservations to the Director, and removes repeated source
hash/document IDs and URLs from compact model context. All full artifacts remain
available through inspection. Budget-omitted answer tasks mark questions unanswered.
A regression test ensures optional work cannot cross that final capacity reserve.
The model and original total run ceilings are unchanged in registered `m2-live-v4`.


`m2-live-v4` retained 13 calls, 230,189 input and 7,242 output tokens and a
$0.5382964 catalog estimate. Company used a real deterministic scenario-price
calculation, but its last-turn submission combined critical gaps with eligible
instrument assessments. Validation rejected it and the task exhausted its fixed
turn allowance. The candidate remains incomplete; eligibility was not relaxed.

Runtime v5 / prompts v2.3 give preliminary specialists/planning/triage/review a
narrower wire result: scoped findings, gaps, assumptions, questions and objections.
Only Director draft/final stages emit the complete per-instrument assessments and
role coverage. Inapplicable preliminary fields are stored as empty lists; no
submitted judgment is changed or repaired. The Director's critical-gap eligibility
rule still applies to every affected instrument. A transport regression covers
this stage separation. `m2-live-v5` is independently registered before execution.

Frozen live profiles reproduce their stated acquisition windows. Create a new,
dated mandate for later research; reusing an old price end-time must not be
interpreted as a fresh market capture. M3 owns final publication refresh.


`m2-live-v5` stopped during initial Director planning because it cited a registered
source ID as retrieved evidence. Its three known invocations retained 53,142 input
and 2,872 output tokens and $0.140748 estimated catalog cost. Unknown references
were rejected rather than relabeled after the fact.

Runtime v6 / prompts v2.4 use manifest-bound `eN` aliases on the model wire, with
allowed evidence references enumerated in each tool schema. A request stores its
alias-to-immutable-ID map outside the context sent to the model. The controller
expands only typed evidence references and numeric JSON-pointer prefixes; it does
not rewrite prose, numbers or judgments. Artifacts and accepted findings continue
to use immutable IDs. The structural audit resolves the map before verifying
visible manifests. This also reduces repeated hash-token overhead. Registered
`m2-live-v6` preserves the model and original aggregate ceilings.


`m2-live-v6` completed initial research and follow-up but stopped at draft validation
when the Director copied Challenger objections into its own zero-length objection
field. Its 33 known invocations used 737,837 input and 17,240 output tokens,
$1.63417 catalog estimate and 27 source requests. It is incomplete and retained.

Runtime v7 / prompts v2.5 omit the inapplicable objection field entirely from
non-Challenger wire responses, restoring only the defined empty stored list.
Challenger objection IDs and Director disposition requirements remain unchanged.
Task creation now checkpoints with the complete enclosing transition, preventing
a persisted child task without its linked question or final symbol scope. Tests
cover both defects. The separately registered `m2-live-v7` uses the same model,
source mandate and aggregate ceilings; its outcome is not presumed accepted.


Current implementation checks: **526 Python tests**, including 43 focused research
cases, pass. TypeScript compilation and all **34 JavaScript tests** pass. The
current `m2-engineering-fixture-v7` reproduces the five-symbol cooperative flow
with synthetic source data and a scripted worker; its marker and acceptance file
explicitly exclude live-model or performance claims. The preserved META runtime
and configuration hashes match the registered baseline. The plan document is
the intentional exception, reflecting progress and the requested M3 monitor.
Development/release case hashes still match; release cases remain unevaluated.


## M2 engineering acceptance result

The independently registered `m2-live-v7` completed an **unpublished five-symbol
draft** in 920.36 seconds (15 minutes 20 seconds). Eleven tasks completed with
34 real model calls, 30 source requests, 59 tool calls, 842,864 input tokens,
20,456 output tokens and a **$1.9118464 catalog cost estimate**. Usage is known
and reconciles with receipts. No rejected submission or extra retry was needed
in this candidate. Terminal resume makes no worker call and preserves the state
byte for byte. Archived code matches the pre-run registration.

Market Behavior requested Macro context; the Director reused its completed answer.
Geopolitics requested issuer exposure evidence; the Director scheduled a separate
Company follow-up. Final synthesis explains all six questions and disposes of
all six original Challenger objections. Four core specialists completed;
Commodities has an explicit materiality-based omission.

Read the [five-symbol draft](../reports/investment-research/m2-live-v7/draft.md),
[structural acceptance](../reports/investment-research/m2-live-v7/acceptance-structural.json)
and [final-claim review](../reports/investment-research/m2-live-v7/acceptance-semantic.json).
The source review covers all six final factual claims plus the inference and
scenario qualifications. Deterministic tables retain stored values; review levels
match their stated moving-average references within binary-float representation
noise and carry future expiration, share basis and source IDs in structured JSON.

All five assessments remain `insufficient_evidence`, for stated issuer/ETF gaps,
with different theses, counter-cases and review conditions. This is engineering
acceptance, **not user usefulness acceptance**. The live report alone does not
prove the counterfactual behavior when only a nonessential source is missing;
the cooperative fixture explicitly verifies that scoped behavior. Bear/base/bull
sensitivity and calculation chaining pass deterministic tests; the accepted live
run did not create company valuation scenarios. A real scenario-price invocation
is retained in the incomplete v4 candidate. No scenario was invented to improve
the final report's appearance.

Recorded follow-up defects include underused valuation tools, bounded filing
coverage, broad abstention, repeated shared prose and incomplete Markdown display
of the condition fields already available in JSON. M3 should surface those fields
together; M4 must assess decision usefulness, latency and repeated-run reliability.
None of these limitations is hidden by the structural pass.

Across seven M2 live development candidates, 133 model invocations were admitted.
Known usage totals 3,400,091 input and 74,855 output tokens, with **$7.5691876 known
catalog cost**. The first candidate retains one invocation with unknown usage,
so these token/cost totals are lower bounds. Source-only checks used no model
calls. These are cumulative development resources, not the cost of one successful
run or an equal-budget M4 comparison. All six incomplete candidates remain intact.

M2's engineering gate is met. The next phase is M3, including the requested
[graphical run monitor](AGENTIC_INVESTMENT_RUN_MONITOR.md), final refresh/publication,
review/feedback and the separate safe publication-origin observation contract.
M4 comparisons and user usefulness review remain required before V1 release.
