# Research delivery failure and repair — September 21, 2026

The [subsequent readiness and conclusion-scoping repair](AGENTIC_INVESTMENT_SYSTEM_V1_READINESS.md)
implements the next two authorized steps with zero model calls. New workspace
contracts are now v6/v2.7; the v5/v2.6 implementation below is the first checkpoint.

The user rejected the NVDA/MU/QQQ pilot as useless relative to its effort and
resource use. **This is a product usefulness failure.** The earlier structural
and final-claim checks remain historical engineering evidence; they do not
supersede this feedback. A report that lists unanswered requirements is not a
completed answer merely because every field is populated and its caveats are
accurate. V1 remains unreleased; M4 remains open.

The original publication, state, source bytes and acceptance records remain
unchanged. Actual user feedback is appended to the publication's feedback store;
its receipt and the reproducible diagnosis are in
`reports/investment-research/delivery-repair-v1/`.

## What failed and what the evidence establishes

The pilot spent 28 calls, 565,541 input and 18,568 output tokens, 822.46 seconds of
research and $1.3393828 estimated catalog cost. It completed with **12 model calls
unused**. Increasing the global ceiling is not the first remedy.

| Defect | Evidence from the saved run | Consequence |
|---|---|---|
| Annual earnings discarded by normalization | Original SEC payloads include NVDA annual diluted EPS 4.90 for Jan 27, 2025–Jan 25, 2026 and MU 7.59 for Aug 30, 2024–Aug 28, 2025. The legacy selector exposes one latest EPS, respectively a six-month 4.85 and nine-month 41.40. | Agents repeatedly mistake an incomplete projection for absent source data. These historical annual observations are anchors, not forward estimates or automatically comparable current P/Es. |
| Required calculations were optional in practice | Company used two `inspect_evidence` calls then submitted on turn 3 of 5. The entire pilot made zero `calculate` calls. | No scenario analysis despite the explicit valuation question and available arithmetic tool. |
| Tool granularity did not fit the task budget | Two companies × three scenarios require six single-price calculations; percentage comparisons need more calls. Company has five turns including submission. | The requested complete numerical deliverable cannot fit the original grouped task even if the agent tries. |
| Director stopping and follow-up rules missed the deliverable | Company assignment says stop after latest results plus one filing/companyfacts source per company. The sole later question is Technical→Macro and reuses an answer. No valuation recovery task was requested. | Coordination records activity and dispositions without ensuring the main question gets answered. |
| Filing access stops at the opening | Broker stores full documents but exposes first 16,000 normalized characters; normal context shows only 1,600. `inspect_evidence` originally returns the same bounded record. | Substantive geographic/customer/risk sections may be downloaded but inaccessible to the worker. |
| Acquisition checks measure availability, not answerability | SEC requests succeed despite the missing annual projection; FRED times out, BIS fails, and current sponsor page lacks holdings. | An HTTP/source pass authorizes expensive research without verifying required usable fields. |
| Uncertainty collapses too broadly | Geopolitics marks unavailable BIS status critical for NVDA, MU and QQQ. Validation blocks a whole instrument when any declared critical gap affects it. | Missing a policy fact can veto an entire assessment instead of only the dependent claim. The model's criticality judgment needs review; removing all critical checks would be wrong. |
| Publication has no analytical-completion gate | Final checks enforce identity, citations and objection dispositions, allowing every requested valuation field to say unavailable. | A syntactically correct non-answer can be published as the finished product. |
| The conclusions page hides existing detail | Instrument cards previously omitted `assumptions`, `etf_lookthrough`, and numerical evidence tables. | Users see a shorter and less useful report than the saved evidence permits. This does not explain away the missing calculations: none existed. |

The generic limitations quoted by the user are mostly system qualifications,
not evidence that the research question was answered. Keep necessary provenance
and uncertainty, but do not use a limitations list as a substitute for analysis.
The publication refresh validates changes within registered sources; it never
repairs incomplete analytical work.

Reproduce the read-only diagnosis (no acquisition or paid calls):

```sh
python/.venv/bin/python scripts/diagnose-investment-research-delivery.py \
  reports/investment-research/workspace-v1/cc7276bf-94d6-4137-a6e9-8ce2abc7ee7d/run
```

## Implemented first repair

New workspace mandates use **v5**, prompts **v2.6**, action schema **v5**, runtime
`investment-research-delivery-v1`. Model, global ceilings and old publication
identities are unchanged. Older mandates retain their contracts. No paid research
run was launched during this repair.

1. The research adapter now retains annual and interim diluted EPS observations
   separately, including period dates, duration, accounting basis, units, accession
   and reported share-basis qualifications. It filters inadmissible accessions and
   future filings. It does not modify the legacy parser, silently annualize a
   quarter, derive TTM EPS by adding per-share values, or claim consensus.
2. `inspect_evidence` supports a literal query and match occurrence over the full
   archived document. Returned evidence has a parent identity, unchanged raw hash,
   retrieval date and exact normalized character locator. The operation spends
   one tool call and no new source request. Missing matches remain typed gaps.
3. `calculate_scenarios` computes three company EPS×P/E prices and percentage
   sensitivities to a matching dated close in one call. All EPS/multiple inputs
   are explicitly assumed, with a full annual period, basis and per-case rationale.
   It checks registered company identity, annual anchor presence, price identity,
   freshness flag, finite positive inputs and bear/base/bull ordering. ETF earnings
   fabrication and partial-period inputs are rejected. Financial suitability of
   assumptions and corporate-action compatibility still require semantic review.
4. New v5 runs check annual company anchors and fresh completed closes before any
   model call. After Company completion, absent grids stop the run before further
   scheduled work. Another check runs before synthesis; final findings must cite
   each company's grid through a scenario-classified instrument claim. Publication
   rechecks this before spending refresh requests. Failures preserve partial work
   as `INCOMPLETE` with the specific missing items; no automatic paid rerun occurs.
5. Updated prompts explicitly assign the deliverable, reserve its turns, distinguish
   assumptions from consensus and scope uncertainty to the conclusion it blocks.
   Genuine critical dependencies still block directional eligibility. The gate
   deliberately does **not** require a positive recommendation or forced ranking.
6. Markdown and browser conclusions show recorded scenario tables and rationale;
   the browser also shows existing assumptions and ETF exposure. Withdrawn scenario
   guidance is excluded after refresh invalidation. Stopped runs show the coverage
   failure and stop reason directly in the conclusions page.

This first gate deliberately covers the positive-EPS company valuation workflow
used by this workspace. Loss-making companies, missing SEC annual anchors and
other valuation methods need a separately specified delivery contract; they must
not receive fabricated positive EPS merely to pass. A full scenario grid may
still be analytically poor: presence and arithmetic checks are necessary, not a
usefulness score. Likewise, missing policy/holdings acquisition is still a real
unresolved defect, not repaired by having an additional tool.

## Keep / change / remove and next acceptance

- **Keep:** immutable evidence, dated inputs, deterministic calculations, source
  integrity, known usage, genuinely independent challenge, bounded execution and
  honest refusal of unsupported factual or directional claims.
- **Change now:** field-level input visibility, batch arithmetic, substantive
  document access, explicit valuation assignment, early analytical-completion
  checks and presentation of the numerical deliverable.
- **Remove as success criteria:** differentiated prose, completed roles, question
  counts, objection dispositions and publication status standing in for an answer.
  Remove the assumption that more calls or another specialist fixes missing data.

Before another full pilot:

1. Verify fresh working policy sources and dated QQQ sponsor holdings, and inspect
   relevant issuer geographic/customer/supply disclosures through the repaired
   path. Freeze new source windows and source replacements after verification.
2. On development evidence, review **financial usefulness**, not just the grid:
   explain why each annual EPS and multiple range is defensible, identify implied
   expectations versus the dated price, distinguish corporate versus fund metric
   conventions, quantify conditional downside and identify decision-changing
   evidence for each instrument. If no relative preference survives, explain the
   explicit assumptions under which it would change. Arbitrary bear/base/bull
   numbers fail this review even when the schema passes.
3. Replace the single instrument-wide criticality switch with a versioned
   claim/dimension dependency contract: business evidence, valuation, market
   behavior, policy exposure and directional preference can have distinct status.
   Do not merely relabel critical gaps noncritical. Test both genuinely fatal
   dependencies and missing optional evidence, including ETF-specific cases.
4. Route any material recoverable delivery gap to a specifically budgeted repair
   task; otherwise stop early. The first implementation stops after an incomplete
   Company task; it does not yet implement a recovery scheduler. Reduce repeated
   irrelevant context only after measuring which evidence each role needs.
5. Then register a bounded real development run with an explicit review rubric.
   A useful output must actually answer valuation/demand/downside/change-of-view,
   with source-backed facts and defensible conditional conclusions. No claim that
   this repair guarantees useful live-model behavior is justified before that run.
6. Continue unchanged M4 comparisons: old pipeline, single capable agent and team,
   with separate fixed-evidence and comparable-budget end-to-end evaluations.
   Frozen release cases remain untouched. User usefulness acceptance and zero
   unresolved critical release errors remain required.

This is a development repair, not M4 completion, investment performance evidence,
or authorization to relaunch a frozen run under different code.

## Verification and preservation

[Verification record](../reports/investment-research/delivery-repair-v1/verification.json):
564 tests passed in the complete Python suite; TypeScript compilation and all 34
JavaScript tests passed. After adding a refresh-withdrawal regression and final
scenario table styling, all seven focused delivery tests and the headless browser
check passed. The browser renders 12 scenario rows from synthetic evidence,
existing assumptions and ETF exposure, fits mobile width and reports zero browser
exceptions. No provider calls were made by these checks. The browser screenshot
is explicitly synthetic; it is not a repaired investment recommendation.

The original pilot state is byte-identical to the diagnosed snapshot and the
publication bundle still verifies. Comparator and frozen development/release
hashes match. The only baseline registration mismatch is the already documented
plan text; baseline runtime/configuration files are unchanged. No frozen release
case was evaluated. Files are local changes; no commit, push or service restart
was performed as part of this repair.
