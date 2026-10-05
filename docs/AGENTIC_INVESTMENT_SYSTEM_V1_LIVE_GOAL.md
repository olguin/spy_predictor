# Live global assessment goal and remediation — October 3, 2026

## Authorized product goal

The user requests this experience for one stock or a few selected stocks:

> As of this exact time, here is the stock's overall assessment, the global forces
> that matter to it, the most plausible conditional outcomes, what I recommend
> considering, and what would change that view. In the monitor and summary pages,
> provide a crystal clear report for each agent explaining what it has done, its
> main conclusions, and a final short summary.

The user authorized immediate implementation and evaluation on October 3,
superseding earlier session-stop instructions for this work. This includes bounded
real source/model checks needed to assess the completed product. Preserve original
runs, publications and scorecards. Do not redefine investment returns as research
quality or claim calibrated probabilities from a qualitative scenario.

## Immediate remediation sequence

The user's third task adds a full usability and report-quality requirement:
substantially improve every agent's report, make stock input and report navigation
clear, and use polished graphs, charts and tables only when they explain a material
finding. Keep the initial screen concise and reveal detailed evidence on demand.
Use the saved deterministic data for visuals; avoid extra model calls for decoration.

1. Replace the fixed pilot entry with explicit one-to-five-stock selection and
   configurable research horizons. Register sources for exactly that selection;
   resolve new US-listed issuer identities through primary SEC records.
2. Acquire a timestamped market snapshot alongside completed-session history.
   Record requested cutoff, observed market times, source dates, feed coverage,
   market state and completion time. Include current company disclosures and
   relevant macro/policy sources. Refresh price-sensitive inputs before reporting.
3. Extend the report contract with overall assessment, relevant global forces,
   conditional outcomes and consequences, practical recommendation and change
   conditions. Preserve scoped uncertainty while requiring available analytical work.
4. Provide readable reports for every role in both monitor and summary views:
   work actually performed, evidence inspected, main conclusions, limitations and
   final short summary. Show unfinished/omitted/failed agents honestly. Keep raw
   structured records available as supporting detail.
5. Verify single/multiple-stock scope, temporal integrity, price/news freshness,
   report completeness, actual model routing, missing-data behavior and browser
   presentation. Evaluate the complete live product against a frozen rubric.
6. Repair diagnosed failures with focused replays where possible, retain every
   attempt and record actual calls, tokens, cost and latency. Require zero unresolved
   material output errors and useful complete reporting before calling the new
   product goal met.

## Acceptance criteria

- Every selected stock has all five requested report sections, explicit source
  support, an opposing case and concrete evidence that changes the assessment.
- Relevant global mechanisms explain effects on revenue, costs, financing,
  valuation or market behavior; unrelated generic world commentary does not pass.
- Consequences distinguish observations, analyst assumptions and conditional
  inferences. Ranking scenarios requires a stated basis; numeric likelihoods
  require qualified evidence and retain their actual limitations.
- Live, delayed, last trade, completed close and market-closed states remain distinct.
  Missing live entitlement cannot be presented as a fresh executable quote.
- Each implemented role has a clear activity report and concise conclusion summary
  in both the monitor and saved report, including partial and omitted states.
- Input controls expose stocks and horizon. Report navigation separates overview,
  individual agents and evidence, with accessible keyboard controls, mobile
  layouts and a small number of relevant visuals. Charts identify units, dates,
  benchmark and data source, and remain optional when evidence is missing.
- Development review requires at least VERY GOOD (16/20, every axis at least 3,
  no unresolved critical defect) across accuracy, depth, usefulness, uncertainty
  and coherence, plus engineering and browser checks.
- Report actual latency and resource usage within the registered run budget.
  Improvements are judged against the delivered experience and saved baseline;
  investment performance and user usefulness acceptance retain separate records.

Status: product contracts implemented; revised-system acceptance remains open.
The user has asked whether to stop after repeated failures. No further paid run
will start while the choice to stop current run7 or let it finish is pending.
See the [failure audit](AGENTIC_INVESTMENT_SYSTEM_V1_FAILURE_AUDIT.md). The criteria
above remain unchanged; historical evidence below is not a completion claim.

## Implementation and evidence — October 4, 2026

Implemented the versioned v7 live mandate and v2.21 derived live/report profile. The
reviewed v2.17 prompts remain intact and remain the default for existing v6 mandates.
New explicit workspace stock submissions use v7/v2.21; legacy API payloads retain
their recorded pilot behavior. New issuer registrations resolve through SEC ticker
records and are subsequently checked against issuer submissions. Unclassified sector
comparators are explicitly broad SPY comparisons.

All five specialists are assigned once by the controller, alongside Director and
independent Challenger stages. Every submission carries a readable agent narrative;
Director synthesis requires the five requested global-analysis sections per stock,
distinct bear/base/bull outcomes with evidence and plausibility basis, and concrete
view-change conditions. Unknown or unread evidence IDs and missing role coverage
fail validation. Recorded tool actions remain distinct from agent-written activity.

Market snapshots use configured IEX coverage with explicit quote/trade times and
market state. Snapshots are acquired before final synthesis and at report delivery. Registered
SEC event catalogs and monetary feeds are also refreshed before final, with changed
or failed event refreshes made explicit for the affected assessment. Completed daily
closes are preserved separately. Current SEC event exhibits and the newest available
Federal Reserve monetary release supplement issuer filings and FRED rates. Dated
international, dollar, gold and oil ETF proxies add relevant global market context;
they are explicitly not direct economic indexes or causal proof.

The report has three concise reading views: overall assessment, individual agents,
and evidence/limitations. Both report and monitor offer all seven agent reports with
actual activity, main conclusions, short summary, gaps and evidence dates. Execution
details remain expandable. Charts use admitted, matched completed-session data,
show one selected graph at a time, and expose exact tables and source links. Charts
also appear on the relevant Technical agent report. No decoration model calls.

Evidence:

- 101 focused regression tests passed (79.21 seconds); all worker findings synthetic.
- Chrome checks passed for desktop/mobile input, explicit ticker/horizon controls,
  all seven agent reports, global report sections, progressive disclosure, form launch,
  saved monitor states and no JavaScript exceptions.
- Source check 2: all 17 registered ANET sources acquired; required readiness passed.
  SEC keyword excerpts and dated policy applicability remain qualified partial inputs.
- Actual FRED MIME type `application/csv` was rejected by the broker; fixed and verified
  against live DGS10 and DFF retrieval.
- Real full-system ANET run and predeclared role/product/resource review are saved in
  `reports/investment-research/live-goal-v1/`. ANET completed in 11.5 minutes /34 calls/$2.95 catalog estimate, with
  provisional per-role scores16–18/20 and no unresolved material final defect.
  Explicit per-axis review is `anet-development-review2.json`.

This evidence proves the implemented contracts and browser behavior. It does not yet
record complete live quality acceptance or investment performance. Continue the live
review and repair any diagnosed material defects before marking the goal complete.

## Diagnosed multi-stock repairs — October 4

- Run1 stopped during Director synthesis when the host slept. The failed provider
  attempt has unknown usage; original state remains terminal. Live macOS runs now
  hold a temporary idle-sleep assertion, released on exit; deadlines still count
  wall time and manual sleep is not overridden.
- Run2 completed all seven roles in14.1 minutes /32 calls/$3.88. Numerical archive
  checks passed; agent-level quality failed because Company did not adequately
  reconcile non-operating GAAP EPS, and Challenger treated truncated citation text
  as a contradiction despite supporting text later in the full excerpt. Director
  corrected the final. The v2.21 prompts require targeted earnings-component and
  full-citation inspections; original results and failed grades remain preserved.
- Run3 delivered the earnings-composition repair in Company findings, then stopped
  when Director repeated an already-approved question. Routing now offers only
  PROPOSED question IDs and identical direct repeats are idempotent. Conflicting
  repeats remain rejected. Known receipts and the original failure are preserved.
- Individual agent pages show Director final-review decisions and keep the full
  primary memo alongside narrower follow-up findings. Charts stay optional and
  use no additional model calls.
-64 focused routing/live/workspace/M3 regressions passed;14 live tests passed after
  follow-up preservation. Updated desktop/mobile Chrome checks passed with no
  exceptions. Run4 was registered before execution; its subsequent failure is
  recorded below. No universal forecast, human acceptance or return claim follows.

Run4 stopped at the delivery gate with a missing NVDA grid. The old seven-turn
pilot allowance could not accommodate a multi-company primary-source audit and
both required grids. v2.21 allocates Company7+3 additional turns per extra company,
protects one calculation per missing company plus submission, and scales the shared
call cap by stock count (40/48/56/64/72) within unchanged25-dollar/one-hour bounds.
Total-GAAP sensitivity remains permissible with explicit non-operating-component
uncertainty; it must not be confused with a recurring-operating forecast.
Run5 is registered with48 calls. A new reserve-path regression caught a lookup
after restricting offered tools; the restricted path now returns directly and
15 live-contract tests pass. The frozen in-flight archive is explicitly qualified
as a development case; its source hashes are retained and publication is unavailable
under changed code. No failed run was silently resumed or assigned fabricated work.

Run5 subsequently stopped with the reserved-tool lookup KeyError. Run6 then stopped
in worker initialization: the Python scheduler offered calculation-only tools, but
the TypeScript contract required submission to remain offered. The worker now
admits that exact reserved alternative. Original run6 unknown-usage accounting is
preserved. This is a cross-language integration failure, not an agent-quality score.

Latest engineering verification: 108 Python regressions, eight TypeScript worker/
contract tests and updated desktop/mobile Chrome checks passed. An additional
offline integration test passes actual Python-generated tool envelopes through the
TypeScript boundary for one through five companies, ETF-only and mixed scopes,
every role/stage, final submission, pending/completed routing and each reserved
calculation turn. This check makes no provider or source calls. It does not test
the investment judgment of a live model.

Run7 was registered and started before the user's stop question. At 22:37 UTC,
it remained RUNNING, with Company and Macro completed. Its complete numerical,
per-role, temporal and delivered-report review is pending; no current v2.21
all-role live acceptance has been recorded. Do not start a further paid attempt
while the user's requested stop/continue clarification remains unanswered.

## Run7 terminal review — October 4, 22:44 UTC

Run7 completed normally in14.74 minutes,34 model calls/$4.0665086, all usage known. All seven roles completed;14 numerical/archive groups and actual desktop/mobile saved-report/chart checks pass. The original final product nevertheless fails quality: Director added an NVDA raw-material-inventory proposition citing a land/power/shell lease-guarantee passage after Challenger draft review. Director is15/20 FAIL; other six roles16–19/20 in provisional assistant review. See `nvda-mu-development-review7.json`. No all-role acceptance, publication or goal completion. No further research worker is active and no additional paid attempt was launched. The pending user choice is now pausing all work versus continuing offline fixes.
