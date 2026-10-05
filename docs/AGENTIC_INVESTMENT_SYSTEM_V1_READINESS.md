# Source readiness and separate conclusions — September 21, 2026

The user authorized the next two repair steps: verify usable source inputs with
zero model calls, then replace blanket uncertainty with conclusion-specific
statuses and dependencies. Both are implemented. A new paid research pilot has
**not** been launched. The original report remains a rejected usefulness result;
engineering checks do not establish that the repaired system produces useful
live research. M4 remains open.

Read the [original diagnosis](AGENTIC_INVESTMENT_SYSTEM_V1_DELIVERY_REPAIR.md) for
the lost annual earnings, missing calculations, inaccessible filing sections and
overly broad criticality rule. This continuation addresses acquisition readiness
and uncertainty propagation without forcing an investment preference.

## What the real source check established

[Source audit](../reports/investment-research/readiness-v1/source-audit.json) and
[requirement-level evidence](../reports/investment-research/readiness-v1/source-check-authorized/source-readiness.md):
**13 READY, 7 PARTIAL, zero blocked mandatory requirements**. There were 26 source
requests, 50 tool calls, 18,567,808 downloaded bytes, **zero model calls, zero model
tokens and $0 model catalog cost**. Network operations still consumed time.

| Input | Verified availability | Remaining qualification |
|---|---|---|
| NVDA annual earnings | Annual diluted EPS 4.90, Jan 27, 2025–Jan 25, 2026, filed Feb 25 | Historical anchor; not forward consensus or an automatically share-adjusted current P/E |
| MU annual earnings | Annual diluted EPS 7.59, Aug 30, 2024–Aug 28, 2025, filed Oct 3 | Same qualification; interim earnings remain separate |
| Company operating data | Period-qualified revenue through Jul 26 for NVDA and May 28 for MU | Demand attribution and scenario assumptions require substantive interpretation |
| Completed prices | NVDA, MU, QQQ, SPY, XLK, IWM and HYG through Sep 18 | Dated closes; not executable quotes |
| QQQ composition | Sponsor business date Sep 18; 101 equity positions, 99.859505% reported equity weight | Five cash/derivative/other rows retained separately, including one unknown weight; no renormalization |
| QQQ valuation | Existing verified sponsor aggregate P/E 30.08 as of Aug 31, within its registered 31-day window | Retained dated capture, not a newly observed daily multiple; company/fund methodologies differ |
| Filing exposures | Geographic, customer and supply excerpts from both issuers' latest annual and quarterly filings | PARTIAL: located text does not establish quantified exposure or its investment impact |
| Policy | Official Jan 15 advanced-computing license-review rule retrieved | PARTIAL: one dated rule does not establish complete current policy or company applicability |

The [Invesco page](https://www.invesco.com/qqq-etf/en/about.html) exposes its
[holdings endpoint](https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/QQQ/holdings/fund?idType=ticker&productType=ETF).
The adapter verifies sponsor host, fund identity, effective/business dates,
response row count, finite weights and portfolio reconciliation. It preserves
excluded positions and unknown weights instead of treating an incomplete equity
view as the entire portfolio. This endpoint replaces the old local holdings
capture only in new workspace mandates.

The [GovInfo rule](https://www.govinfo.gov/content/pkg/FR-2026-01-15/html/2026-00789.htm)
replaces the failed BIS listing in new registrations. The full BIS EAR Part 744
page was retrievable in discovery but exceeds the broker's 10 MB per-document
ceiling; an eCFR attempt returned HTTP 406. Neither attempt establishes complete
current policy. FRED DGS10 and DFF still timed out and remain recorded source gaps.
These gaps do not erase unrelated company or market observations.

Both the initial sandbox DNS failures and the authorized network check are
preserved. The authorized command originally exited 1 because its then-current
CLI required every source request to succeed, including optional FRED inputs.
Its saved readiness and delivery checks passed mandatory inputs. The v6 CLI now
derives exit status from mandatory readiness and delivery checks; optional failures
remain visible. A read-only re-evaluation of the saved capture matches its
requirement statuses and evidence lineage. The capture was not rewritten or
resumed after code changed.

## Behavior of new runs

Workspace mandates are **v6**, prompts **v2.7**, action schema **v6**, findings and
draft product schemas **v4**, runtime `investment-research-readiness-v1`.
Published v6 products use `investment-research-publication-product-v2`. Earlier
mandates and publication bundles retain their existing contracts.

1. Each registered source declares the conclusions it supports. Frozen input
   requirements identify usable fields, source IDs, instrument scope, age windows
   and whether their absence prevents starting model work. Retrieval time never
   substitutes for the observation date.
2. Before model work, the controller retrieves required data and first/last matching
   geographic, customer and supply sections from annual/quarterly filings. Missing
   mandatory inputs stop the run before a paid call. Optional gaps remain explicit.
   Section acquisition is bounded and charged against the existing tool/source
   budget; global ceilings were not increased.
3. Each instrument separately reports **business, valuation, market behavior,
   policy exposure and relative preference**. Each has a supported, conditional
   or insufficient-evidence status, conclusion, qualification, claims and declared
   dependencies. Claims must match both instrument and conclusion scope.
4. Critical gaps and unresolved original objections block affected conclusions
   and their dependents. Missing/stale registered inputs block their declared
   conclusions; partial inputs prevent unconditional support. Cycles and promotion
   of conditional dependencies to unconditional conclusions are rejected.
5. Relative preference requires business, valuation and market evidence, plus
   policy exposure when material to that preference. An unsupported preference
   cannot become a directional assessment. Omitting a material dependency to
   evade the rule remains a semantic defect. Resolving a critical objection now
   also requires visible evidence references; citations alone do not prove the
   resolution is financially sound.
6. Publication propagates source changes through cited evidence, claims and
   declared dependencies. A policy-only change can withdraw policy conclusions
   while leaving independent business observations and hypothetical valuation
   grids intact. A changed valuation input withdraws its grid and dependent
   preference. Original findings remain archived. Identical refreshed submissions
   bytes preserve filing-section lineage; changed submissions do not inherit it.
7. Browser and Markdown reports show the separate conclusions and numerical
   scenarios. The browser labels the overall badge as the relative assessment
   and exposes requirement-level source readiness and observation dates.

The earlier annual-input and Company-delivery gates remain active: missing
company grids stop before further synthesis, and final reports must cite the
company scenario evidence. A grid is explicitly conditional EPS×P/E sensitivity,
not an observed multiple, consensus forecast, calibrated target or usefulness
certificate.

## Verification and preservation

See [verification](../reports/investment-research/readiness-v1/verification.json),
[browser check](../reports/investment-research/readiness-v1/research-workspace-browser-check.json)
and [preservation audit](../reports/investment-research/readiness-v1/preservation.json).
The new regressions cover sponsor reconciliation, source dates and missingness,
refresh lineage, independent conclusion status, dependency cycles, unresolved
objections, full controller/schema transport, and publication withdrawal scope.
The browser fixture renders 25 conclusion sections and 12 scenario rows, source
readiness and mobile layouts, with no browser exceptions or paid calls.

The original pilot state is byte-identical, its immutable publication verifies,
and comparator and frozen-case hashes match. The previously documented baseline
plan-text mismatch remains the only baseline mismatch. Frozen cases were not
evaluated. Changes remain local and uncommitted. No service restart was performed;
an idle workspace must load current code before using the new contracts.

## Next acceptance step

Use a newly registered, small Company-and-Director development probe before another
full team run. The current workspace still launches the full team; a dedicated
bounded probe/profile must be prepared with its own code/source identity, provider
limits, measured request sizes and explicit stop conditions. Do not repurpose or
resume the old publication or the source-only capability check as paid research.

The probe must demonstrate:

- Both company grids have defensible, evidence-linked annual EPS and multiple
  assumptions, dated-price sensitivities and an explanation of implied expectations.
- The company-versus-QQQ comparison explains differing metric dates/methodologies,
  demand drivers, downside and concrete evidence that would change the assessment.
- Independent supported observations survive policy uncertainty; every conditional
  conclusion states its assumptions. Any missing preference identifies the actual
  blocking dependency and useful conditional comparisons that remain possible.
- Token/cost accounting and a manual financial-usefulness review pass. Merely
  generating tables, citations or a non-abstaining label does not pass.

Only after that output is useful should a full development run and the unchanged
M4 old-pipeline/single-agent/team comparisons proceed. A bounded delivery-recovery
scheduler is still unimplemented; current gates stop early rather than silently
spending more calls. No live-model usefulness or performance claim is established
by this continuation.
