# Jev integration: a plan to measure decision overhead reductions

Status: investigation and implementation plan, September 21, 2026. No Jev calls,
SDK installation, credentials changes or production integration were performed.
The specialist prompt experiments are a separate intervention. Freeze their
accepted baseline before measuring the changes proposed here.

Expanded after reading all five requested classification pages, plus the Python
SDK, primitive-specific, confidence, model and API references. The examples
below are documentation-only and have not been executed against TypeSafe.

## Recommendation

Use Jev first for **shadow scoring and evidence relevance**, then test replacing
**follow-up triage decisions**. Retain generative specialists, independent
challenge, financial reasoning and report synthesis. Keep calculations,
identity checks, timestamps, coverage and dependency propagation in ordinary
code. These are proposed uses, not demonstrated savings or accuracy improvements.

Jev evaluates a supplied state using typed Choice, Score and Noul questions.
Independent questions sharing that state can be batched. This makes bounded
classification and rubric checks plausible candidates; broad research needs
decomposition. [TypeSafe introduction](https://docs.typesafe.ai/introduction)

The requested coding-agent documentation explicitly distinguishes Jev from a
generative coding model: it does not write reports, generate arbitrary tool
arguments or replace a conversational worker. Replacing the `model` field in
our Pi worker would therefore be the wrong integration. Keep the controller;
add a separate decision-provider adapter.
[Jev with coding agents](https://docs.typesafe.ai/introduction/coding-agents)

## Actual model and state contract

This is a classification/decision model with a constrained answer space. We
still author natural-language instructions and criteria, but receive a typed
decision rather than asking a text generator to emit JSON. It cannot create the
specialist's explanation, discover a new investment thesis, or generate missing
evidence. Calibration is a property measured across predictions, not a guarantee
that a particular classification is correct.
[System One](https://docs.typesafe.ai/concepts/system-one)

`state` means the supplied input to one evaluation: a string, object or array.
It is not our `state.json`, a mutable server-side research session, or a substitute
for `Store`. We should build a compact object containing only the candidate
answer, relevant excerpt, task and precomputed scope facts. All questions in
that request see the same object. Code must carry any result needed by a later
request into its next input; the documented interface supplies no implicit
conversation memory. Text/structured text is supported; raw PDFs, images and
audio require preprocessing. [State](https://docs.typesafe.ai/concepts/state)

| Primitive | Input we define | Returned result | Intended use here |
|---|---|---|---|
| `Choice` | An instructions field and option-description map | Selected option, every option's probability, confidence | Select a listed completed answer, passage category or optional specialist; include `none`/`unclear` |
| `Score` | Instructions and an ordered array of descriptive levels | Probability-weighted level index, distribution, legend, confidence | Rank passage relevance or screen one narrowly defined response property |
| `Noul` | A yes/no proposition, optionally with `true`/`false` boundary descriptions | `noul`, the probability of yes; no separate confidence | Test whether a passage explicitly contains guidance, or a response states a change condition |

Choice supports at most 255 options. A mutually exclusive Choice cannot express
that several passages are relevant; use one Noul/Score per passage for that case.
[Choice](https://docs.typesafe.ai/primitives/choice)

Score supports 2–10 levels, indexed from zero. Each level description must stand
alone: the model does not see its ordinal number or neighboring descriptions.
`score=3.2` is a weighted position on the rubric, not a precise quality
measurement or a probability of correctness. HTTP distribution keys are strings;
the Python SDK exposes Score level keys as integers. Do not silently round a
fractional Score into this repository's independent integer review grades.
[Score](https://docs.typesafe.ai/primitives/score)

Use Noul for a defined proposition, not as a vague quality scale: 0.5 represents
uncertainty between yes and no, not a medium-quality report. A relative Choice
winner can still be a poor absolute match; separate suitability checks can
prevent forced selection. [Noul](https://docs.typesafe.ai/primitives/noul)

Question IDs only correlate requests and answers; they are not shown to the
model. Write the full question, with explicit paths such as
`candidate_answer.text`, inside instructions. Batch independent questions that
use the same state. A second call is justified when the first result is needed
to retrieve a different passage or build a new candidate set, not merely because
application code branches later. Batch independence does not remove the risk of
irrelevant material in a large state. [Primitives](https://docs.typesafe.ai/primitives)

Instructions and criterion descriptions may themselves be JSON objects or
arrays. Keys such as `question`, `covers`, `excludes` and `examples` are our
semantic labels, not special API operators. Use them to distinguish reported
results from guidance and conditional stress assumptions. The advanced taxonomy
pattern walks candidate subtrees in code; it is optional for a large topic
catalog, unnecessary for our five specialist roles.
[Advanced structure](https://docs.typesafe.ai/primitives/advanced)

## Concrete API examples

The wire endpoint is `POST https://api.typesafe.ai/v1/systemone`, authenticated
with a Bearer key. Send `{model, state, questions}` and receive
`{model, answers, usage}`. Persist the returned version and usage, and reject a
missing/mismatched question result. A successful HTTP response is not permission
to execute a research action. [HTTP API](https://docs.typesafe.ai/api)

The following is a runnable-shaped Python example using documented SDK names.
Prerequisites, **not performed for this investigation**: install a pinned
`typesafe-sdk` release and configure `TYPESAFE_API_KEY`. The input is a small
illustrative packet; production would build it from archived artifacts and
hash it. This is an API-shape demonstration, not tested classification behavior.
[Python SDK](https://docs.typesafe.ai/sdk/python)

```python
import json
from typesafe_sdk import Choice, Noul, RetryPolicy, Score, TypeSafeClient

packet = {
    "followup": {"text": "Does the cited Q3 outlook include China compute?"},
    "candidate_answer": {
        "task_id": "task-company-1",
        "text": "The cited Q3 outlook excludes China Data Center compute revenue.",
    },
    "passage": {
        "text": "The Q3 outlook assumes no China Data Center compute revenue.",
        "source_id": "illustrative-source",
    },
    "code_checks": {"completed": True, "recipient_matches": True,
                    "symbol_scope_covers_request": True},
}
questions = {
    "answer_fit": Choice(
        instructions={
            "question": "Does `candidate_answer.text` answer `followup.text`?",
            "scope": "Compare the requested subject and qualification; do not invent facts.",
        },
        criteria={
            "answered": {"covers": "Explicit answer to the exact requested issue",
                         "excludes": "Related subject without the requested conclusion"},
            "partial": "Answers only part of the requested issue",
            "unanswered": "Does not answer the requested issue",
            "unclear": "Cannot determine from the supplied text",
        },
    ),
    "passage_relevance": Score(
        instructions="How directly does `passage.text` address `followup.text`?",
        criteria=["Unrelated to the requested issue",
                  "Background about the issue, without an answer",
                  "Explicitly addresses the requested issue"],
    ),
    "guidance_present": Noul(
        instructions="Does `passage.text` explicitly describe management outlook or guidance?",
        criteria={"true": "An explicitly stated outlook or guidance assumption",
                  "false": "Reported historical results or no outlook statement"},
    ),
}
with TypeSafeClient(
    model="jev-1.13.0",
    retry=RetryPolicy(max_retries=0, timeout=10.0),
) as client:
    result = client.system_one(state=packet, questions=questions)
    raw = result.raw_http_response.json()

assert raw["model"] == "jev-1.13.0"
assert set(raw["answers"]) == set(questions)
assert all(raw["answers"][key]["type"] == kind for key, kind in {
    "answer_fit": "choice", "passage_relevance": "score",
    "guidance_present": "noul",
}.items())
print(json.dumps(raw, indent=2))  # Prototype only; production writes a metered receipt.
```

The client supports `result.choices[id]`, `result.scores[id]`,
`result.nouls[id]` and the complete raw HTTP response. The raw check above matters
because SDK forward compatibility can skip an unknown answer kind. Production
must also validate finite values, distributions, exact option sets and usage;
the assertions are not a complete adapter. Avoid debug logging of source packets:
SDK debug bodies are not redacted. [SDK usage](https://docs.typesafe.ai/sdk/python/usage)

`RetryPolicy(max_retries=0)` disables retries. Its `timeout` is a retry-budget
setting; retain the controller's independent wall-clock deadline and test actual
network-timeout/cancellation behavior before deployment. Failed/late calls must
retain known receipts; unknown usage remains a lower bound.
[Retry configuration](https://docs.typesafe.ai/sdk/python/api/retries)

For excerpt selection, build one independent question per candidate, rather than
one request per excerpt. This snippet replaces the preceding `packet/questions`
construction; code retains source IDs and offsets in its candidate manifest:

```python
packet = {
    "task": "Find disclosures about customer data-center power constraints.",
    "passages": [
        {"text": "We guarantee certain AI cloud partners' land and power leases."},
        {"text": "Cash and cash equivalents increased during the quarter."},
    ],
}
questions = {
    f"relevant_{index}": Noul(
        instructions=f"Does `passages[{index}].text` address the issue in `task`?",
        criteria={"true": "Contains a directly relevant disclosure or qualification",
                  "false": "Unrelated text or only generic background"},
    )
    for index in range(len(packet["passages"]))
}
```

For this repository, selection combines calibrated scores with mandatory
inclusion rules. No low score may delete a required fiscal-calendar, guidance,
share-basis or counterevidence passage. Numerical input extraction, date assembly
and broker arguments stay in code. The classifier only chooses among supplied
options; it does not return a new excerpt, explanation or arbitrary query.

For answer reuse, code first rejects invalid identity/role/symbol scope. It then
considers the semantic `answer_fit` distribution under a held-out, calibrated
threshold. If accepted, code supplies the existing answer task ID to the shared
controller policy and records a template reason plus the decision receipt.
`partial`, `unanswered`, `unclear`, malformed output, timeout or an uncalibrated
confidence range retains Director triage. No threshold in this document is
claimed to be validated, and the example does not execute a route.

## Evidence from this repository

The current worker returns exactly one action per authorized invocation. Python
executes it, then supplies the result on another paid turn. This is intentional
budget control, but it makes repetitive routing and evidence selection costly.
See [worker](../packages/agent-runtime/src/pi-research-worker.ts) and
[controller](../python/src/spy_predictor_quant/investment_research/controller.py).

The rejected historical full run used 28 calls and $1.3393828 estimated catalog
cost. Reading its stored receipts gives these relevant subsets:

| Stage | Calls | Catalog cost | Observed actions |
|---|---:|---:|---|
| Director planning | 5 | $0.0843552 | Four specialist assignments, then findings |
| Director triage | 2 | $0.1245200 | Reused a specialist answer through `route_question`, then findings |
| Company research | 3 | $0.1615120 | Two evidence inspections, then findings |
| Challenger review | 2 | $0.1517800 | Evidence inspection, then objections |

These are historical observations from the
[original run](../reports/investment-research/workspace-v1/cc7276bf-94d6-4137-a6e9-8ce2abc7ee7d/run/state.json),
not forecasts for the newer prompts. Triage accounted for about 9.3% of that
run's catalog cost; eliminating it cannot by itself solve total cost. Its final
findings may carry useful reasoning, so removing both calls requires proving
that the replacement preserves required information.

The separate Company/Director v2.7 baseline failed with four calls and $0.402658
catalog cost. It had no planning or triage stage. Consequently, a triage adapter
would remove **zero** calls from that experiment. Its problems were weak valuation
rationale, missing guidance in the default excerpt, invalid claim scope and a
reversed numerical comparison. Jev cannot replace an earnings bridge or fix the
arithmetic. See the [baseline review](../reports/investment-research/evaluation-v1/baseline-review.md).

The more recent [round5 receipts](../reports/investment-research/evaluation-v1/all-roles-v211-round5-high/state.json)
show 16 calls and $1.5937372 estimated catalog cost. Six calls selected
`inspect_evidence` actions: two each for Macro, Geopolitics and Commodities,
costing $0.4375816 together. Company used two `calculate_scenarios` actions plus
findings; Technical, draft Director, Challenger and final Director each submitted
findings in one call. This fixture has **no planning or follow-up triage calls**.
Replacing triage therefore saves zero here; reducing evidence-selection turns
is its concrete experimental opportunity. The six calls are a historical target
set, not a savings forecast: preloading the same evidence may be sufficient in
plain code, some calls may remain useful, and extra context/classifier/fallback
costs must be counted. Round5 also failed the Director quality target, so its
operational completion does not make it an accepted quality baseline.

## Candidate changes, ranked

| Priority and location | Proposed decision | What it can save | Boundary |
|---|---|---|---|
| 1. `evaluation.py` | Atomic response-quality checks against supplied evidence and a frozen rubric | Can later substitute for repetitive model-grader calls; today adds cost because grading is assistant/human review | Diagnostic only; cannot supply human acceptance or independently certify financial correctness |
| 1. `context.py`, `Broker.inspect_evidence`, readiness sections | Rank candidate passages for guidance, financial basis, geographic exposure or a specific task | May remove LLM inspection-selection turns and reduce repeated context tokens | Mandatory inputs always included; low relevance confidence never silently drops evidence |
| 2. `Controller.run` triage and `prioritize` | Decide whether a proposed question is already answered, resolvable and material | Candidate replacement for bounded Director routing calls; actual net savings require calibrated replay | All task reserves, exact identity/scope checks and final question accounting remain code |
| 3. Director planning | Rank optional role assignments from a code-defined task catalog | May reduce repeated `ask_specialist` selection turns | Mandatory roles scheduled in code; open-ended decision framing remains generative |
| 3. Challenger assistance | Flag claim/excerpt mismatch, omitted qualification or apparent unsupported language | May focus reviewer context; no direct saving until review-call reduction is demonstrated | Keep independent risk view and semantic financial challenge |
| Later. Publication refresh | Categorize already-extracted textual changes for reviewer prioritization | Review triage, not current LLM-call savings | Refresh is already deterministic; never let Jev override required withdrawal |

### Precise insertion points and removable invocations

| Existing callsite | Jev primitive and supplied state | LLM invocation that could disappear | Work that remains |
|---|---|---|---|
| `Controller.run`, proposed-question branch, and `Controller.prioritize` in [controller.py](../python/src/spy_predictor_quant/investment_research/controller.py) | Choice among completed, code-filtered answers plus `none`/`unclear`; separate Noul for explicit coverage of the requested issue. For new work, narrowly defined materiality and availability questions | Director turn emitting `route_question`; a triage `submit_findings` turn only if it contains no indispensable new analysis and equivalent bookkeeping is provided | Existing completion/role/symbol checks, budget reserve, question status, final question-effects accounting; generative triage for unresolved cases |
| `compact` in [context.py](../python/src/spy_predictor_quant/investment_research/context.py), `acquire_sections` in [readiness.py](../python/src/spy_predictor_quant/investment_research/readiness.py), `Broker.call('inspect_evidence')` / `document_section` in [broker.py](../python/src/spy_predictor_quant/investment_research/broker.py) | Noul per candidate passage for task relevance; optional Score for rank and Choice for a known section category. State includes actual candidate text, not metadata alone | Worker turn selecting an evidence inspection, if controller preselection exposes the needed passage before that turn | Actual inspection and source recording, full-source access, provenance, deterministic required windows; specialist must still analyze the result |
| `Controller.route` during Director planning | Choice among a fixed optional task catalog; independent Noul per optional role when several may apply | Repeated `ask_specialist` selection turns for predefined tasks | Research question generation and Director's decision framing. Scheduling mandatory roles needs code, not Jev |
| `evaluation.scorecard` / `validate_review` and [evaluation_campaign.py](../python/src/spy_predictor_quant/investment_research/evaluation_campaign.py) | Atomic Noul checks for an explicit residual interpretation/change condition; Score for one causal-analysis property using supplied response/excerpts | None in today's runtime: review is supplied by an independent assistant/human, and scoring is code | Named reviewer reasons, artifact references and critical-defect adjudication. Store classifier diagnostics separately; Jev cannot author required reasons or human acceptance |
| Challenger `review` task created in `Controller.run` | Noul per claim/excerpt pair for a specific omitted qualification, or Choice selecting among enumerated discrepancy types | None initially. A screen may focus the retained Challenger, but cannot replace its generative objections or explanation | Causal financial analysis, alternative explanations, objection identity/scope and Director dispositions |

Do not label a JSON-shaped financial analysis as classification merely because
the output has fields. Company scenario assumptions and Director conclusions
require open-ended reasoning. Likewise, the round5 `calculate_scenarios` calls
contain model-chosen EPS/P-E inputs; Jev cannot recover arbitrary numerical
assumptions by emitting Score values. Batching those two calls is a separate
tool/orchestration design, not demonstrated Jev replacement.

Do not migrate `calculate_scenarios`, comparison panels, annual EPS parsing,
holdings reconciliation, source freshness, claim/evidence identity validation,
eligibility dependencies, publication integrity or budget accounting to Jev.
They already run without LLM calls. The deterministic comparison check that
would catch reversed scenario upside belongs beside the stored numerical
results, not in a probabilistic grader.

Relevant boundaries are implemented in
[scenarios](../python/src/spy_predictor_quant/investment_research/scenarios.py),
[panels](../python/src/spy_predictor_quant/investment_research/panels.py),
[dimensions](../python/src/spy_predictor_quant/investment_research/dimensions.py),
[readiness](../python/src/spy_predictor_quant/investment_research/readiness.py),
[result transport](../python/src/spy_predictor_quant/investment_research/result_transport.py)
and [publication](../python/src/spy_predictor_quant/investment_research/publication.py).

## Proposed architecture

Add `decision_provider.py` behind an `off | shadow | assist | route` setting in
a new frozen policy version. Use the Python controller's state/store/ledger;
do not route Jev through the Pi worker or give it broker execution privileges.
The adapter takes a bounded packet plus versioned questions and returns a
validated decision record. The controller alone decides whether to act.

Suggested new files:

- `investment_research/decision_provider.py`: HTTP/SDK transport, response
  validation, timeouts, exact model identity and receipts.
- `investment_research/decision_policy.py`: deterministic decisions and fallback
  rules; no research findings generated from template text.
- `config/investment-research-jev-v1.json`: versioned provider/policy/budget settings.
- `prompts/investment-research-decisions/v1/*.json`: atomic question definitions
  for grading, excerpt relevance and routing, separate from specialist prompts.
- `schemas/investment-research-decision-v1.json`: request/answer/receipt contract.
- A dedicated development replay command and tests; extend the evaluator through
  an optional hook rather than altering its registered acceptance threshold.

Each record should contain state-content hash, evidence/claim/question IDs,
question-definition hash, requested and returned model, policy version, raw
answer reference, probabilities, usage, catalog price/version, latency, attempts,
decision and fallback reason. Store these as **judgments**, not primary evidence.
Changing model, criteria, packet construction or threshold invalidates the
associated calibration and cache identity.

Use a separate `decision_calls` ledger while counting both providers toward a
combined AI spend and wall-time ceiling. Record LLM calls avoided separately;
never report a Jev call as zero model usage. Cache only exact matching requests
under the pinned model and policy, and account for cache hits explicitly.

## Question design

Jev's question IDs are not supplied as semantic instructions; every question
must identify the relevant state fields in its own instructions. Questions in
one request are independent. If later questions require newly selected documents,
retrieve those documents and make a second request; do not imply hidden
communication between questions. [Primitives](https://docs.typesafe.ai/primitives)

Examples below describe proposed application behavior, not verified accuracy:

| Input packet | Atomic questions | Action in code |
|---|---|---|
| A claim, its cited excerpt, explicit fiscal/accounting labels | Does the excerpt state this observation? Is the claim marked as an assumption where appropriate? Does it omit a stated qualification? | Flag disagreement for review; retain original evidence and generative explanation |
| Candidate passages and a Company task | Which passages contain management guidance? Which discuss annual versus interim results? Which address diluted-share basis? | Include required sections and the relevant ranked passages; preserve a catalog and inspectability for the rest |
| Proposed follow-up plus candidate completed findings | Which listed answer, if any, addresses this question? Is additional registered evidence available? Is this question material to the named conclusion? | Check scope/role/reserves; reuse, schedule or send ambiguous items to Director |
| A completed specialist response and cited excerpts | Does it explain the causal mechanism? State what would change the conclusion? Separate observations from assumptions? | Store dimension scores and flagged items; aggregate in code under the existing rubric |

Use `none`, `unclear` or `requires_reasoning` where a closed choice could otherwise
force a false answer. Provide canonical scope, precomputed periods and numerical
comparisons rather than asking Jev to reconstruct them. Do not ask one broad
question such as “Is this report excellent?” and treat the answer as a verdict.
Atomic scores can be combined in code, with independently binding critical
defects. [Composite scoring](https://docs.typesafe.ai/patterns/composite-scoring)

## Implementation phases

### Phase 0 — Freeze comparison and labeled development data

1. Finish the specialist-quality work and freeze the chosen generative baseline.
   Retain every rejected candidate and its observed cost.
2. Label saved development artifacts for passage relevance, question reuse,
   routing and response-quality dimensions. Include missing policy evidence,
   wrong numeric direction, unsupported multiples, accounting mismatch, stale
   dates and superficially polished but incomplete analysis.
3. Split by source document/report family, not individual snippets. Reserve a
   holdout before tuning question wording or thresholds. Do not use the frozen
   M4 release cases for iterative development.
4. Register plain-code baselines: required-section extraction, lexical passage
   retrieval, exact duplicate detection, fixed scheduling and batch task
   assignment. Jev must beat these where they solve the same problem.

Deliverable: frozen experiment registration, labels with reviewer provenance,
error-cost definitions and matched LLM/code comparators. No production behavior
changes or API calls are needed to prepare this phase.

### Phase 1 — Provider adapter and shadow evaluation

1. Verify account availability, credential presence without displaying its value,
   current pricing/limits and the data-processing terms for the intended packets.
2. Implement the adapter and tests with recorded synthetic responses. Pin the
   model; register its identity and the question definitions with each experiment.
3. Run bounded shadow scoring on saved development responses. Assess one
   semantic property at a time. Code still checks numbers, dates and references.
4. Compare Jev against reviewer labels and a generative-grader baseline if one
   is introduced. Neither model grades its own output as independent acceptance.
5. Inspect every false acceptance and every unnecessary failure. Report both
   coverage at the selected threshold and quality of the automated subset.

The initial adapter should use no automatic retries. The SDK defaults to retries,
so disable them or explicitly meter each attempt if using it. Treat unknown
usage as unknown cost, not free. Handle HTTP 401/422 as configuration failures
and 429/529 through a separately budgeted retry/fallback policy.
[API reference](https://docs.typesafe.ai/api)

Before shadow calls, add synthetic contract tests for missing/extra question IDs,
wrong primitive type, unexpected model version, malformed/nonfinite probability,
Score distributions with incorrect level keys, and unknown SDK answer kinds.
Test timeout after dispatch, late receipt, retry count zero, cancellation, and
repeated controller resume: a saved decision must not trigger a second provider
call. Keep a decision-specific reservation so fallback cannot consume the final
Director/Challenger reserve.

| Condition | Controller behavior |
|---|---|
| `off` or no calibrated policy | Preserve the existing code/LLM path; no Jev call |
| Shadow result disagrees | Record diagnostic only; never alter the live task |
| Valid confident match, all hard checks pass | Apply only the promoted decision type and record its exact candidate/receipt |
| Ambiguous, unsuitable or contradictory answers | Preserve required passages; use original Director/inspection path if its reserved budget remains |
| Invalid credentials/schema/model version | Disable this decision adapter for the run, record configuration failure, preserve baseline path |
| Rate limit, overload, timeout or missing response | Record attempt and known/unknown usage; no implicit retry; use separately budgeted fallback |
| Global budget/deadline exhausted | Preserve incomplete status; do not bypass the limit or pretend a classifier supplied missing research |

Evaluate adverse packets explicitly: a source passage commanding the classifier
to choose `answered`, a correct answer for the wrong symbol, guidance confused
with an actual result, a fiscal label mismatch, and two plausible partial answers.
Use named, code-computed scope flags; Jev cannot authorize its own input or
reconstruct scope through several identity hops. Thresholds are specific to the
primitive and question version. Do not assume separate Noul propositions and
their negations sum to one, or that a Noul threshold transfers to Choice.
[Model failure modes](https://docs.typesafe.ai/model-jaggedness/jev-1.13)

### Phase 2 — Evidence presentation experiment

1. Create candidate passages deterministically from archived documents, keeping
   source hash, parent ID and offsets. Include known earnings/outlook sections
   by rule before any semantic ranking.
2. Batch relevance questions against compact packets. Fit request size to the
   pinned model; do not send the entire controller history.
3. Produce an auditable context selection manifest with included and omitted
   evidence IDs and reasons. Missing or low-confidence answers fall back to the
   established projection/inspection path. They do not mark a source missing.
4. Replay Company and Director under matched prompt/model/turn limits with:
   existing projection, improved deterministic projection, and deterministic
   projection plus Jev. Measure the marginal contribution of Jev.

This phase targets the observed hidden-guidance/context problem. It must not
claim that an earnings bridge is correct merely because guidance is visible.

### Phase 3 — Replace bounded follow-up triage

1. Extract triage policy from `Controller.prioritize` so both providers invoke
   the same scope, completed-answer and task-reserve checks.
2. Evaluate all proposed questions in a bounded batch. Keep routing questions
   distinct from evidence-sufficiency and materiality questions.
3. First automate only high-precision reuse of an already completed, in-scope
   answer. Preserve the original answer task ID and explicit machine decision
   receipt. Never imply that Director reviewed a machine-routed question.
4. Add approval/decline routing only after its own holdout evaluation. Ambiguous
   cases go to Director within its original budget. Hard limits remain hard.
5. Remove the triage submission call only after its required bookkeeping is
   produced deterministically and any substantive reasoning is retained in the
   final Director input. Final question effects remain mandatory.

A future batch `ask_specialists` tool or code-defined mandatory plan can also
eliminate repetitive assignment calls. That is ordinary orchestration work and
should be credited separately from Jev. Optional topic routing is its plausible
Jev extension; new research-question generation remains an LLM task.

### Phase 4 — Full-system comparison and rollout

Run matched full development cases for the accepted baseline, code-only
optimizations, and code plus Jev. Include failures, fallback calls, unknown-usage
events and repetitions in the denominator. Review final research quality, then
apply the unchanged M4 comparisons. Enable each decision type separately with
an immediate off switch and replayable decision records.

Publication-change categorization remains shadow-only in this plan. Existing
refresh withdrawal cannot be relaxed on a semantic classifier's assurance.

## Proposed acceptance criteria

These are engineering targets to register before the live experiment, not
observed performance or statistically established guarantees.

| Area | Promotion requirement |
|---|---|
| Transport and provenance | All responses validated and receipted; exact requested question set; malformed/missing/nonfinite values rejected; secrets absent from artifacts |
| Deterministic boundaries | Zero bypasses of arithmetic, date, identity, source, scope, budget, dependency or publication checks in regression tests |
| Excerpt selection | No mandatory passage omitted; at least 98% recall on labeled decision-critical passages; no recurrence of the hidden-guidance failure |
| Automated answer reuse | At least 99% precision on the automated holdout subset; zero false reuse of seeded critical mismatches; report coverage and confidence interval |
| Quality screening | Detect every seeded critical defect; at least 95% recall on independently labeled critical defects; report false-positive rate and uncertainty; no autonomous publication acceptance |
| Whole-report quality | Every required specialist stays at the registered VERY GOOD-or-better threshold; no new critical defect or material loss of supported analysis |
| Efficiency | At least 20% lower median cost for the targeted stage, including Jev and fallbacks; report whole-run cost separately; no more than 10% p95 whole-run latency regression |
| Reproducibility | Registered inputs/model/policy/criteria; held-out family split; repeated selected cases; separate tuned and unseen results |

Do not treat a small sample with zero failures as proof of 99% precision. Report
sample size and intervals; keep shadow/assist mode if the holdout is too small.
Choose thresholds per decision consequence using measured performance.
TypeSafe's Choice/Score confidence summarizes the answer distribution; it is
not our independently measured probability of correctness. Noul has no separate
confidence. [Confidence](https://docs.typesafe.ai/confidence)

## Costs, constraints and risks

At investigation time, the official model page lists `jev-1.13.0` at **$0.042 per
million input tokens**, with free output, a 64k total request limit and a 32k
limit for state plus longest question. It lists 250,000 tokens/second and 1,200
requests/minute, with limits subject to change. Pin a version instead of relying
on the moving `jev-latest` alias. [Models](https://docs.typesafe.ai/models)

A 10,000-input-token request would therefore cost about $0.00042 at that listed
rate; 100 such requests about $0.042. This is arithmetic on advertised prices,
not measured usage. It excludes retained LLM work, fallbacks, retries and
integration effort. Subscription/catalog estimates and provider bills should
be reported distinctly. The small unit price is promising, but extra screening
that removes no work increases total cost. No numerical latency promise was
verified in this investigation; measure p50/p95 under our actual packet sizes.

Known vendor limitations particularly matter here: numerical precision and date
ordering are weak; long irrelevant state, multi-hop reasoning and adversarial
text can degrade decisions. Jev is not trained for free-form generation. Keep
precise computation and identities in code, use compact evidence packets and
test malicious source passages. Never treat relevance or a high score as source
truth. [Jev 1.13 limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13)

Reviewer disagreement, scoring to the test and confidence miscalibration remain
application risks. A polished unsupported report must fail. Keep critical
defects independent of averages, blinded held-out reviews separate from prompt
tuning, and human usefulness acceptance distinct from all model grades.

The docs link their DPA and privacy policy and describe enterprise zero-data-
retention availability. Those pages do not establish this project's account
terms. Confirm them before sending non-public research, private positions or
credentials; initial trials can use the saved public-evidence packets.
[Legal documentation](https://docs.typesafe.ai/legal)

## Next implementation slice

Build the disabled-by-default adapter, receipt schema, synthetic transport tests
and shadow replay registration. Then run the small labeled relevance/quality
probe. Promote answer-reuse routing only if its measured precision and savings
justify it. This preserves the useful specialist reasoning while targeting
actual decision overhead.

## September 21 addendum: a concrete code-only baseline

The specialist development iterations exposed an evidence-selection failure:
both issuers' archived filings stated their 53-week fiscal calendars, but the
Company output used incorrect fiscal endpoints. NVIDIA's disclosure appeared
near normalized character 15,486; Micron's appeared near 19,515, beyond the
standard 16,000-character excerpt. Both also disclosed 14-week fourth quarters.
See the [round3 independent diagnostics](../reports/investment-research/evaluation-v1/all-roles-v210-round3-high/independent-review.md).

Round4 adds deterministic archived keyword windows, source-linked calendar
derivation, and rejection of contradictory named fiscal periods. The derived
dates are January 31, 2027 for NVIDIA FY27 and September 3, 2026 for Micron FY26.
This requires no decision-provider call. Its candidate outcomes are evaluated
separately; implementation alone does not establish research-quality success.

This is the baseline a Jev relevance selector must improve upon: ordinary
retrieval exposes an identifiable required passage, and code derives/validates
dates. Jev might help classify less predictable passages, but replacing this
working retrieval/arithmetic path with another model would add cost and a new
failure surface unless an experiment demonstrates a net benefit. No Jev savings
or accuracy measurements are claimed by this addendum.
