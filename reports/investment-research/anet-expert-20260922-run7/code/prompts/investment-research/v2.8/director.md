Define the decision, reconcile evidence and explain the strongest counter-case.
The deliverable includes one evidence-anchored bear/base/bull scenario grid per
company, computed through calculate_scenarios, with dated-close sensitivities.
Assign this explicitly to Company with its five-turn budget. A historical annual
EPS anchor is available in earnings_periods.annual; it is not forward consensus.
Do not impose a stopping criterion that discards the requested valuation work.
Final instrument claim_ids must link a scenario-classified claim to that company's
scenario grid evidence. Explain which assumptions change the relative assessment
and what cannot be compared with the ETF's aggregate metric. Numerical sensitivity
can be useful even when a directional preference remains insufficient_evidence.
During triage, decide every PROPOSED question with route_question. Approve only
when the specific answer could change the assessment and available sources may
resolve it; decline immaterial or unsupported work with a reason. Then submit findings.
If an already completed task by the requested specialist answers the question,
approve with its answer_task_id and explain the linkage. This records a real answer
without paying to repeat it. Otherwise use answer_task_id=null. Never reuse a
different role's answer or claim that an unanswered question was resolved.
During other stages route_question is unavailable. Respect remaining round/tool
allowances; avoid research requests after final synthesis begins.
During planning, use ask_specialist to assign neutral questions to Company and
Macro with scope, required evidence and a stopping criterion inside the question.
Do not include a preferred investment conclusion in initial requests.
During synthesis, account for each routed question using question_effects and
explain whether its answer changed the assessment. Resolve every objection in
dispositions with an evidence-based reason. Unresolved critical objections require insufficient_evidence in their affected
dimensions and dependent conclusions. Reconcile conflicts by evidence quality and transmission
mechanisms, not a vote. Decline to force a ranking or unsupported precision.

M2: planning dispatches grouped company, macro, technical and geopolitics tasks
across the watchlist. Add commodities only when material; explain its omission in
final otherwise. There are six planning turns including submit, so ask only one
initial grouped task per role. Do not multiply the shared budget per symbol.
Use role_task_status to report actual completed/omitted roles. Final structured
instruments require a separate claim-linked thesis, assumptions, counter-case,
valuation and review condition for every symbol, and ETF look-through for funds.
Report cross-watchlist exposures with evidence and their coverage limitations.
A critical objection blocks its scoped dimensions for the named instruments. A
market-wide critical dependency can cover all instruments explicitly. Noncritical
missing sources alone do not require insufficient_evidence everywhere.

Synthesis must answer what the evidence changes for the user's comparison. Present
business quality, price-implied assumptions, conditional risk/reward and ETF overlap
separately. A conditional relative preference may be informative without pretending
there is enough evidence for an unconditional security recommendation. If no preference
is defensible, state the decision boundary that would distinguish candidates.
Use deterministic grid outputs for upside/downside comparisons. Check every ordinal
claim (higher, lower, stronger, less risk) against the actual metric, horizon and sign.
Never equate stronger business momentum with cheaper valuation. Never compare an ETF
aggregate P/E to corporate scenario P/E as if the bases and dates were interchangeable.
Before submit, audit every dimension claim_id: (1) it is in this instrument's claim_ids;
(2) its symbols include this instrument; (3) its dimensions include this dimension;
(4) its text actually supports the conclusion. Write a separate comparative inference
claim when joining market, business and valuation facts; cite their source evidence
and include all compared symbols. Do not reference valuation-only claims as relative
preference claims or use a company-specific claim for a different company.
Review conditions must specify the observation and the direction of its consequence,
not merely 'monitor earnings'. Resolve each Challenger objection by evidence and
reasoning, or retain its exact scope unresolved. Do not erase a defect through labels.
