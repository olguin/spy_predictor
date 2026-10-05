# Current-prompt baseline: rejected

September 21, 2026. Fixed saved development evidence, prompts v2.7, existing
`openai-codex/gpt-5.6-terra` / medium runtime. Company then Director; no other
specialist, fresh acquisition, publication or frozen release evaluation.

The runner and scorecard are implemented. The live baseline did **not** produce
an accepted Director report. Accepted Company work and the rejected Director
candidate are preserved separately. This failed experiment is the baseline;
it is not counted as successful research because its infrastructure worked.

| Measurement | Result |
|---|---|
| Company | Completed in three calls: two scenario grids, then findings |
| Director | One submission rejected; no accepted synthesis |
| Model calls | 4 of the registered maximum 8 |
| Reported tokens | 162,827 input / 6,417 output |
| Catalog cost | $0.402658, all usage known |
| Source requests / downloaded bytes | 0 / 0 |
| Engineering outcome | FAIL / EVALUATION_INCOMPLETE |
| Assistant usefulness review | REJECTED, 5/12, three critical defects |
| Actual user acceptance | Not collected |

## What improved in this particular probe

Company produced the numerical deliverable and preserved separate annual/interim
earnings. It distinguished conditional scenarios from observed multiples or
consensus and retained business/market observations despite policy gaps. Dated QQQ
holdings were available and used. These observations establish behavior in this
probe only; they are not an equal-budget improvement estimate against the old run.

## What still failed

1. **Director claim references are inconsistent.** There are six invalid
   claim/conclusion links. Examples include valuation-only claims cited as relative
   preference claims, a QQQ claim absent from NVDA's instrument claim list, and an
   NVDA/QQQ market claim cited for MU without MU scope. Production validation
   correctly rejected the submission. See
   [expanded rejected candidate](baseline-v27/rejected-director-candidate.json).
   Typed evidence aliases were expanded for inspection; no semantic repair or
   acceptance was performed.
2. **The correction did not fit admission.** The Director's dispatched request
   was 184,823 bytes. After its response, 162,827 input tokens had been consumed
   against a 350,000 ceiling. The rejection added a 17,365-byte history entry.
   The controller's conservative request-bytes-plus-consumed-tokens check refused
   the next request, despite four calls remaining. This is an admission/context
   limitation, not observed consumption of 350,000 actual tokens. The rejected
   next request was not persisted or dispatched, so its exact size is unknown.
3. **Company's scenarios lack a defensible earnings bridge.** MU's hypothetical
   FY2026 annual EPS values of 35/45/55 are not reconciled with reported nine-month
   EPS of 41.40 and archived Q4 GAAP EPS guidance of 30.73 ±1.00. The lower annual
   figure is not inherently impossible, but needs an explicit remaining-period,
   share-count or basis explanation. One cannot silently add per-share periods.
   Generic phrases about moderation do not establish that explanation. Multiples
   for both companies are described as compression/premium assumptions without a
   defensible reference or expectations argument. The grids pass arithmetic but
   fail the registered valuation-rationale criterion.
4. **Relevant guidance is accessible but absent from the default view.** MU's
   guidance EPS is at character 3203 of the archived normalized release excerpt;
   the default model excerpt is 1,600 characters. Company used neither of its two
   remaining inspection turns. Meanwhile, 24 filing-section records occupy
   51,744 bytes of the Director evidence projection. This identifies both an
   evidence-selection problem and a prompt/task behavior to test, not proof that
   all filing excerpts are unnecessary.
5. **Director repeated a numerically wrong comparison.** MU's relative-preference
   text describes stronger conditional scenario upside. The actual stored bull
   sensitivities are MU approximately +40.78% and NVDA +65.34%. The comparative
   wording is contradicted by the grids and was never published. Director also
   carried forward the Company assumptions without reconciling their rationale.

All securities, values and dates above describe the archived evaluation output,
not current investment guidance. Detailed calculations and provenance are in
[baseline diagnostics](baseline-v27/baseline-diagnostics.json).

## Predeclared scorecard

| Dimension | Score / 2 |
|---|---:|
| Source support | 1 |
| Valuation rationale | 0 |
| Comparison | 0 |
| Downside | 1 |
| Change conditions | 1 |
| Uncertainty scope | 2 |

The threshold was at least 1 in every dimension and 10/12 overall, with no
unresolved critical defect. The result fails on both missing required quality
and critical defects. These are assistant judgments supported by referenced
artifacts, not user acceptance or independent professional financial certification.
See the [scored result](baseline-v27/scorecard.json) and
[full review with artifact references](baseline-review.json).

## Negative control and next intervention

The separately registered source-omission case removed `sec-facts-NVDA`. It
returned [EXPECTED_EARLY_STOP](missing-annual/scorecard.json) with **zero model
calls**, preserving the original capture. That verifies inexpensive refusal of
missing mandatory inputs; it is not a successful research report.

Do not run the entire system yet. The next candidate should be evaluated on the
same saved packet with changes explicitly separated and versioned:

- Improve evidence presentation/admission diagnostics: expose relevant earnings
  outlook alongside historical anchors, measure role-specific context, and retain
  inspectable provenance. Do not drop evidence silently or merely raise ceilings.
- Test Company instructions that require an earnings/guidance bridge, period and
  share-basis reconciliation, and a defensible multiple reference or explicitly
  reverse-solved sensitivity. The method must fit the five-turn contract.
- Test Director synthesis instructions/transport that produce correctly scoped
  comparative inference claims, valid claim references, and comparisons checked
  against computed results. Do not weaken validation to accept this candidate.
- Add explicitly defective candidates to Challenger evaluation before testing
  whether challenge catches these semantic errors. Challenger was not run here.

Record each intervention and compare it with v2.7 under matched conditions; do
not attribute combined prompt/context changes to a single cause. Repeat selected
cases before claiming reliability. Then proceed to a full development run and
the unchanged M4 comparisons. No prompt tuning or second paid candidate was
performed during this baseline experiment.
