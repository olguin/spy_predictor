# Improvement Plan 3 — next-session handoff

September 20 planning continuation: the next proposed product implementation is
[Agentic Investment System V1](AGENTIC_INVESTMENT_SYSTEM_V1_PLAN.md), following the
user's clarification of cooperating research agents and a weeks-to-three-months
investment horizon. Read that plan for the new work sequence. Implementation under
it has not started; the September 17 engineering evidence and unfinished work
below remain unchanged.

Saved 2026-09-17. Workspace: `/Users/juanpablo/jp/projects/spy_predictor`.
Read this first, then [project status](PROJECT_PLAN_AND_STATUS.md),
[implementation record](IMPROVEMENT_PLAN_3_IMPLEMENTATION.md), and
[step-5 runbook](IMPROVEMENT_PLAN_3_STEP5_RUNBOOK.md).

## September 17 continuation — synthesis repair

The diagnosis work order below has now produced a repair and successful full
archived synthesis. Read [the diagnosis record](IMPROVEMENT_PLAN_3_SYNTHESIS_DIAGNOSIS.md)
for the current evidence, all preserved attempts and exact artifact paths.

- Added bounded credential-free runtime, dispatch, response, tool and terminal
  markers. Disabled Pi's separate provider retries and enforced one model call.
- A retained full output exposed two last-digit probability-enum mismatches.
  Decimal enum choices now travel as exact strings and map only to their original
  frozen numbers. Python v4 validation remains strict, with no tolerance added.
- Initial ANET and repaired NVDA small probes passed. Full five-symbol archived
  synthesis passed using Astra/medium in 223 seconds; its rendered product passed
  all 15 frozen-row parity checks. Prior failed candidates remain failed.
- Latest full check: TypeScript, 27 JavaScript tests and 483 Python tests passed;
  after final logging changes, build and all 28 JavaScript tests passed, with
  Python sources unchanged.
- The separately registered fresh run completed six roles, then its full-payload
  synthesis stream failed. One compact recovery completed Astra and passed all
  15 product rows on that same fresh capture. The original run remains `PARTIAL`.
  See `fresh-chain-verification.json` under the diagnosis root. The recovered
  product is `DEGRADED` with its 13:51:46 UTC cutoff and 1,436.55-second
  publication lag retained; this is not an actionable current quote.
- All attempts are terminal. Next engineering work concerns ordinary-path
  streaming reliability or explicitly integrating the verified compact path;
  do not rerun completed specialists merely to retry synthesis.

This continuation preserves the original work order and historical failure
record below. No historical qualification flag, forecast issuance, frozen cohort,
or empirical-accuracy claim is changed by the synthesis repair.

## User intent and current decision

The user asked to finish the five-step implementation work package, subsequently
asked why historical data was blocking progress, and requested this saved handoff
to continue in a separate session. The five work steps are distinct from the
original ten research phases. Preserve the full objective:

> Complete and validate the five-step implementation work package: remove
> unnecessary historical-data and agent-feature dependencies; build a qualified
> baseline research dataset; add/audit macro, SEC and optional evidence histories;
> establish preregistered statistical feasibility; finish independent live v4
> agent, prompt evaluation, report and prospective-collection readiness work.
> Preserve frozen/closed cohorts, avoid unapproved data purchases and trading,
> and distinguish engineering readiness from empirical accuracy.

The previous goal was marked blocked after three checks of the missing historical
qualification and failed synthesis. The subsequent discussion corrected the next
work order: **continue engineering by diagnosing synthesis; do not wait for a
data purchase or historical universe before doing independent work.** Do not
shrink the full goal or mark it complete merely because local tests pass.

Track separately:

- Working system: capture → independent specialists → critic → synthesis →
  report, with an independently governed prospective issue/evaluation lane.
- Validated predictive performance: qualified inputs, appropriate historical
  experiment, enough independent dates, and matured prospective outcomes.

No archive/provider path was supplied by the user. No new data purchase was
authorized. IBKR Gateway is unnecessary for the current Alpaca-backed path.

## Original handoff baseline (superseded by the continuation above)

| Requirement | Current evidence/status |
|---|---|
| Forecast/evidence/decision contracts | Implemented: agent v4, structured forecast v3, product v3; legacy readers retained. Do not restart Phase 1. |
| Remove agent-history dependency from quant baseline | V2 protocol supports a separately registered quantitative-only candidate set. |
| Historical reconstruction | 111 SEC/ALFRED v2 observations; explicit reconstruction lane, actual download dates retained; source/schema/as-of checks passed. |
| Baseline panel | 1,704 rows, 282 sessions, SPY/QQQ/XLK; revised-price diagnostic only, **NOT_QUALIFIED**. |
| Statistical feasibility | Frozen before outcome calculation; 5/21/63-session horizons have 6/1/0 effective blocks, below the fixed minimum 30. No promoted model. |
| Live v4 agents | Five specialists plus critic completed with verified receipts. Synthesis has not completed. |
| Prompt evaluation | Four bounded semantic fixtures passed after one provider-schema repair; Codex review, not a human study or population error estimate. |
| Report | Fallback HTML/Markdown/JSON works; all 15 rows passed frozen numerical/reference/action parity checks. Synthesis missing and publication stale are visible. |
| Prospective research collection | 120 observations across three packets; re-import is idempotent. Last packet has one missing FRED series, DGS5. |
| Forecast issue/outcomes | Separate governed lane. These 120 observations are **not 120 issued forecasts** and do not establish predictive accuracy. No scheduler was installed by this work. |
| Tests | Last full `npm run check`: TypeScript build, 20 JS tests, 477 Python tests passed. This handoff edit does not rerun the full suite. |

The current pilot covers 2025-08-01 through 2026-09-15. The final holdout beginning
2026-09-16 remains unopened by that experiment. Its small sample cannot support
the required statistical claims, independently of the provenance issue.

## Original implementation work order: diagnose synthesis

1. Inspect the preserved request, terminal failure and Pi adapter. Add bounded,
   credential-free progress evidence for runtime/auth readiness, request dispatch,
   first response event, result-tool invocation and termination where supported
   by the installed Pi runtime. Do not log tokens, headers or complete payloads.
   **Implemented by the September 17 continuation above.**
2. Verify the installed runtime's event/transport API. Preserve the configured
   model rather than silently switching models. Use the OpenAI Docs skill when
   required for OpenAI-specific implementation/troubleshooting.
3. Prepare one immutable, small synthesis diagnostic using the same v4 contract
   and configured Astra model. Declare input, runtime, timeout and call budget
   before execution; validate its output with the actual Python contract.
   A small passing probe does not qualify the complete five-symbol chain.
4. Let the observed failure stage determine the next change. Increase workload
   only after the bounded probe works. Avoid another identical uninstrumented
   900-second retry. No cause has been proven: a timeout alone does not establish
   a provider outage, quota problem, oversized context or defective schema.
5. Once repaired, verify the full five-symbol v4 chain, model/usage receipts,
   frozen numerical parity and rendered product. An old packet may establish
   contract behavior, but fresh capture is required to demonstrate current
   operation; never relabel old evidence as current or issue forecasts backward.

Relevant files:

- `packages/agent-runtime/src/pi-codex-adapter.ts`: Pi session and single
  `submit_result` tool; SSE requested by default, retries/compaction disabled.
- `packages/agent-runtime/src/pi-codex-contract.ts`: input validation, provider
  schema projection, transport validation, usage receipt.
- `python/src/spy_predictor_quant/meta_agents.py`: orchestration, strict output
  checks, completed-role reuse and run identity.
- `python/src/spy_predictor_quant/meta_synthesis_recovery.py`: separately
  registered compact synthesis request, verified six-role dependencies, one
  bounded call, immutable success/failure artifacts.
- `config/meta-agent-pi-codex.example.json`: Terra specialists, Sol critic,
  Astra synthesis, medium reasoning, normal timeout 600 seconds, parallelism 2.

Last recovery requested Astra/medium/SSE, max output 20,000 tokens, timeout 900
seconds. The compact request is about 280 KB versus 681 KB before projection.
Both stdout and stderr were empty at timeout. Projection retains every specialist
claim and critic decision, cited evidence/numeric pointer positions, and exact
frozen distributions, references and recommendations. It omits redundant context
and numerical ablations. This did **not** establish a successful workaround.

## Exact live artifacts — preserve all attempts

All paths below are relative to `reports/improvement-plan-3/step5-live/`:

| Artifact/run | Result |
|---|---|
| `analysis-20260916T141234519041Z-6c4fb050/packet.json` | Five-symbol packet, cutoff 2026-09-16T14:10:10.463607Z. |
| `agents-20260916T164704425042Z-3491a786/` | Six stages completed; Astra synthesis timed out at 600 seconds. |
| `agents-20260916T175546368669Z-10c87b65/` | Verified six-role reuse; synthesis timed out at 600 seconds. Use this as the recovery parent. |
| `synthesis-recovery-20260916T181057780677Z-fd907455/` | Compact Astra request; 900-second timeout. |
| `synthesis-recovery-20260917T005607354136Z-a2dfef56/` | Explicitly registered Sol attempt; WebSocket close 1006. |
| `synthesis-recovery-20260917T023626062513Z-005dea0d/` | Original Astra over SSE; 900-second timeout. `registration.json`, `request.json`, `started.json`, `failed.json` retained. |
| `fallback-forecast.json` | Frozen numerical forecast tied to the partial agent report. |
| `fallback-product/index.html` | Readable degraded report; `summary.json`, `report.md` and `product-parity-verification.json` beside it. |

All recorded attempts are terminal. The last model process/session was 9690 and
subsequently returned unknown process ID; there is nothing to resume by polling
that handle. Do not assume a job is running from `started.json` alone.

Recovery registrations pin Python implementation and, for the latest attempt,
the adapter/contract sources. **Do not rerun an old registration after editing
those files.** Preserve prior code/evidence and prepare a new diagnostic/run with
its own hashes. Prior timeout usage is unknown; do not report it as zero.

## Historical-data clarification — avoid repeating the stall

We have usable historical prices. A date on a historical bar does not prove the
exact version available at an earlier prediction cutoff. Strict replay needs
availability/revision evidence; an ordinary revised-data diagnostic has weaker
claims. Keep that limitation explicit without blocking unrelated engineering.

Historical stock membership/delistings are relevant to broad stock selection.
They are **not a prerequisite for the fixed SPY/QQQ/XLK price case study**.
Historical ETF holdings are needed only for models using historical exposures.
ALFRED revisions and SEC filing availability are separate source families, and
the existing bounded reconstruction adapters already handle those families.

Do not set the current manifest's failed audits to true based on this clarification.
Any scope-specific qualification policy change needs its own explicit design,
evidence and tests; preserve prior registrations and results. Timestamp archives
also do not solve insufficient independent dates. Do not buy a generic dataset
before identifying the precise missing fields and confirming provider coverage.

## Source map and evidence locations

| Purpose | Location |
|---|---|
| Append-only observations/as-of reconstruction | `python/src/spy_predictor_quant/meta_research_data.py` |
| Alpaca/ALFRED/SEC capture | `python/src/spy_predictor_quant/meta_research_sources.py` |
| Frozen diagnostic panel | `python/src/spy_predictor_quant/meta_research_panel.py` |
| Registration/feasibility/paired evaluation | `python/src/spy_predictor_quant/meta_experiments.py` |
| Semantic fixture runner | `python/src/spy_predictor_quant/meta_prompt_eval.py` |
| Separate prospective collection | `python/src/spy_predictor_quant/meta_research_collection.py` |
| Public FRED HTTP repair | `meta_analysis.py`: bounded HTTPS curl for public graph endpoint only; authenticated requests retain original handling. |
| Provider boolean-schema repair | `pi-codex-contract.ts`: provider projection supports boolean subschemas; Python still enforces original schema. |
| Pilot source data and panel | `datasets/meta-research/quant-pilot-20260916/` and its `panel-v1/` subdirectory |
| Pilot registration/result/scorecard | `reports/improvement-plan-3/quant-pilot-20260916/` |
| Exact registered experiment code | `reports/improvement-plan-3/quant-pilot-20260916/registered-code/`; archived before later FRED source change. Current code cannot silently rerun that registration. |
| Prompt review and initial failure | `reports/improvement-plan-3/prompt-eval-20260916/semantic-review.md` |
| Identical empty-news retest | `reports/improvement-plan-3/prompt-eval-empty-schema-fix-20260916/` |
| Prospective capture/store/receipts | `datasets/meta-research/prospective-v1/` |
| Latest prospective packet | `reports/improvement-plan-3/prospective-v1/analysis-20260917T024416779722Z-4fd55e63/packet.json` |
| Latest verified import | `datasets/meta-research/prospective-v1/receipts/collection-20260917T025216020611Z-00f40b96/completed.json`; 120 total, partial-source status, unchanged hashes on re-import. |
| Recorded acceptance check | `reports/improvement-plan-3/step5-acceptance-20260917.json`; intentionally `full_plan_complete: false`. |

`prompt-eval-20260916-fixed/` contains prepared fixtures but was not executed;
do not mistake preparation for successful model calls. The readiness receipt
`collection-readiness-env-20260916.json` loaded `.env`; the earlier receipt without
`-env-` was generated without the environment and is not the credential baseline.

## Environment and commands

Use the existing dependencies: last verified Node 22.22, Pi 0.85.1, and
`python/.venv/bin/python`. Do not reinstall or change model libraries by default.
The Node wrapper loads `.env`; direct Python commands do not automatically do so.
Credentials remain in `.env` / Pi's private OAuth store, not in this handoff.

```sh
cd /Users/juanpablo/jp/projects/spy_predictor
git status --short
source /Users/juanpablo/.nvm/nvm.sh
nvm use 22

# Runtime/auth/model readiness; does not establish a successful model response.
npm run pi:preflight --workspace @spy-predictor/agent-runtime

# No model call; reports collection readiness and next exchange-close time.
npm run meta:research -- collection prepare

# Focused checks after synthesis-related edits.
python/.venv/bin/python -m pytest python/tests/test_meta_synthesis_recovery.py python/tests/test_meta_product.py python/tests/test_meta_analysis.py

# Full check when implementation changes warrant it.
npm run check
```

When continuing actual collection, `npm run meta:research -- collection collect`
uses network sources and appends research observations. It neither issues a
forecast nor installs a schedule. Do not launch the full `meta:analyze` pipeline
as the initial synthesis probe: it can repeat costly successful stages.

The exact original product parity helper is saved at
`reports/improvement-plan-3/handoff-20260917/verify_product_parity.py`; it takes
receipt output directory, forecast file, product directory and original synthesis
request as four positional arguments. It verifies 15 rows and writes exclusively;
use a new output directory for a new receipt. It intentionally compares against
the frozen parent, not a newly recalculated forecast.

Network/credential-store sandbox failures need the tool's normal escalation path;
do not bypass restrictions or mistake a sandbox denial for bad credentials.
No new approval for buying data, trading, orders, retrospective issuance or
unattended installation is implied by resuming implementation.

## Preservation and handoff verification

The workspace contains substantial pre-existing modified and **untracked** source,
schemas, configuration, datasets and reports. They are saved on disk, not committed.
Do not reset, clean, replace the checkout, or assume a clean Git clone contains
this work. Continue in this same workspace. Preserve frozen/closed cohorts,
especially the excluded July 2017–July 2025 evaluation, and all failure receipts.
VIX/VIX3M entitlement investigation remains deferred by the user.

The handoff snapshot in `reports/improvement-plan-3/handoff-20260917/` records Git
state and hashes for current implementation/docs plus existing acceptance evidence.
The older acceptance receipt includes hashes of then-current documentation;
those two documentation files are intentionally updated by this handoff. Keep
that old receipt unchanged and use the new snapshot for current documentation.
No production code or frozen research artifacts were changed just to save this handoff.

Suggested opening instruction for the next session:

> Read docs/IMPROVEMENT_PLAN_3_HANDOFF.md and the current worktree. Continue
> Improvement Plan 3 from synthesis diagnosis: add bounded progress evidence,
> run a small contract-valid Astra probe, then validate the full pipeline. Keep
> existing ETF results diagnostic, preserve frozen cohorts, and handle historical
> qualification separately. Do not restart Phase 1 or repeat blind long retries.
