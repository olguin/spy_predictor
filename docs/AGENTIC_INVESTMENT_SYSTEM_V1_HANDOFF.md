# V1 handoff — M3 continuation and preserved M4 gates

## Session stop checkpoint — September 21, 2026

**The user requested saving the handoff and ending this session. The next session
starts by assessing the real pilot's results, usefulness, improvements and next
steps with the user. Do not start another research run or implementation merely
by reading this handoff.** M3 has engineering checks and a real local publication;
M4 acceptance remains open and V1 is not released.

### Current result and where to resume

Question: “Research NVDA and MU over the next three months. Compare their
valuation assumptions, demand drivers, and downside risks against QQQ. Explain
what evidence would change each assessment.”

- Workspace job: `cc7276bf-94d6-4137-a6e9-8ce2abc7ee7d`.
- Run: `04bc90a5-dc91-4fe7-8df8-f0a88d7f3c31`, **PUBLISHED**.
- Publication: `20a51b05-4441-464b-abcd-e36f088da231`, published
  `2026-09-21T03:10:20.148513+00:00`.
- Ten tasks, 28 real model calls, 565,541 input / 18,568 output tokens,
  **$1.3393828 catalog estimate**; all usage known. Research took 822.46 seconds;
  review and publication completed 972.22 seconds after start, within 1,200 seconds.
- All 12 final refresh sources succeeded, with no material change detected.
  Seven final claims received manual source review; no critical factual/numerical
  output error was identified. This is not a release-case score or proof of
  usefulness. No trade, order or performance evaluation occurred.
- All three assessments are **`insufficient_evidence`**. Demand/risk narratives
  and review conditions are differentiated, but no numerical company valuation
  scenarios or supported relative preference were produced. Actual user feedback
  on the research remains pending. Prior browser feedback concerned usability.

Read these saved artifacts before proposing changes:

1. [Published report](../datasets/investment-research/workspace-v1/publications/20a51b05-4441-464b-abcd-e36f088da231/report.md)
   and [immutable publication record](../datasets/investment-research/workspace-v1/publications/20a51b05-4441-464b-abcd-e36f088da231/publication.json).
2. [Pilot acceptance and limitations](../reports/investment-research/workspace-v1/cc7276bf-94d6-4137-a6e9-8ce2abc7ee7d/acceptance.json)
   and [manual final-claim review](../reports/investment-research/workspace-v1/cc7276bf-94d6-4137-a6e9-8ce2abc7ee7d/semantic-review.json).
3. Structural audits in that same job directory: `structural-draft.json`,
   `structural-published.json`, `structural-replay.json`; `run/state.json` contains
   tasks, tool histories and receipts. Technical→Macro reused an existing answer;
   all five questions and eight objections have recorded dispositions.
4. [Workspace usage and implementation record](AGENTIC_INVESTMENT_RESEARCH_WORKSPACE.md)
   and [M3 contracts and qualifications](AGENTIC_INVESTMENT_SYSTEM_V1_M3.md).

### Pending assessment and implementation decisions

The items below are candidates for the next iteration, **not completed work or
authorization to launch another paid pilot without the next-session discussion**.

1. **Assess the actual answer first.** Review how well it answers valuation,
   demand, downside and change-of-view evidence. Separate correct abstention from
   missing analytical work. Collect the user's usefulness feedback and produce a
   prioritized defect/keep/change/remove record before choosing implementation.
2. **Valuation inputs and explicit scenarios.** Investigate why Company used no
   `scenario_price` calculations despite tool availability. Add or improve
   period/accounting/share-basis-qualified annual or forward inputs and explicitly
   labeled assumptions; exercise deterministic bear/base/bull scenario math and
   comparisons. Do not invent consensus or silently annualize partial-period EPS.
   Review Director assignment, specialist turn allocation and prompts together.
3. **Acquisition coverage and relevant filing sections.** Address FRED timeouts,
   inaccessible BIS material and missing current QQQ holdings. Retrieve targeted
   company geographic/customer/supply-chain disclosures instead of relying on
   bounded opening excerpts. Retain the original dates of sponsor captures and
   all failed acquisitions; verify replacement sources before a new registration.
4. **Scope uncertainty more precisely.** Determine whether a missing policy or
   valuation input should block only that conclusion rather than every overall
   assessment. Preserve valid operating/market observations without turning them
   into unsupported valuation preferences. Test materially different missingness
   cases; do not weaken evidence checks merely to obtain a non-abstaining result.
5. **Choose any further product work after review.** Question entry, conclusions,
   prominent execution status and the exact monitor question heading are already
   delivered. Current entry scope is fixed to NVDA/MU/QQQ and 63 sessions. General
   ticker/horizon selection, browser feedback/review controls (CLI contracts exist),
   and clearer source-gap/assumption presentation are possible additions, not
   implemented features. The published summary still contains the model's word
   “draft”; status/timestamp are authoritative. Do not rewrite the frozen report.
6. **Then plan M4 under the unchanged gates.** Compare the preserved old pipeline,
   one capable agent with the same tools, and the cooperating system. Keep
   fixed-evidence synthesis separate from comparable-budget end-to-end research;
   account for usage and failures, review outputs, maintain a defect scorecard and
   versioned keep/change/remove proposal, require zero unresolved critical release
   output errors and actual user usefulness feedback. Frozen release cases remain
   unevaluated and must not become iterative tuning data.

Any future research iteration needs a new mandate/run with freshly checked source
windows and a frozen version. The exact-question monitor change was made **after
publication**; the current source identity differs from this pilot's archived
runtime. Read-only replay and publication integrity checks work; execution resume
under current code is intentionally rejected. Never change old state/code to bypass
that check. Observation prices/outcomes remain pending; no result can be scored
before the registered origin/target observations exist.

### Verification, services and preservation

- Before launch: 32 workspace/M3 tests and 15 M2 tests passed; workspace and
  standalone monitor browser checks passed. After the final heading change:
  32 focused tests and updated browser checks passed; the real published-report
  API, exact question/scope and port-8765 routing were verified. Records are in
  `reports/investment-research/m3-workspace-checks-v1/`. Earlier 553-Python /
  34-JavaScript / TypeScript results belong to the earlier M3 checkpoint.
- No research is active. At handoff, the idle workspace listens on port 8766 and
  its read-only compatibility relay on 8765. These local processes may not survive
  a session/app restart; saved results do. The workspace only starts provider work
  when a new question is submitted. Restart commands, if needed:

  ```sh
  node --env-file=.env scripts/investment-research.mjs workspace --port 8766
  python/.venv/bin/python scripts/redirect-investment-research-monitor.py
  ```

  Run the servers in separate terminals. Entry: <http://127.0.0.1:8766/>;
  latest monitor: <http://127.0.0.1:8765/>;
  [pilot conclusions](http://127.0.0.1:8766/reports?run=cc7276bf-94d6-4137-a6e9-8ce2abc7ee7d).
- Changes and evidence are local, **uncommitted and unpushed**. Continue in this
  same workspace; a fresh clone will not contain the work. Preserve existing edits.
- Only disposable caches were removed after checks: the original approximately
  498 MiB cleanup plus 798,720 bytes regenerated by the latest checks. Audits:
  `reports/repository-retention/2026-09-20-cleanup/` and
  `reports/repository-retention/2026-09-21-workspace-cleanup/`. No dataset, report,
  backup, failed run, comparator or frozen case was deleted; no deletion job exists.
- Frozen-case and comparator artifact hashes still match their registrations.

## Latest continuation

The [local research workspace](AGENTIC_INVESTMENT_RESEARCH_WORKSPACE.md) now adds
question entry, saved reports/conclusions and prominent execution-state banners.
The user-authorized real NVDA/MU/QQQ development pilot was launched through the
browser after those screens passed checks. Its registration is
`reports/investment-research/nvda-mu-qqq-pilot-launch-v1.json`; inspect the linked
workspace run for the outcome: **PUBLISHED**, 28 real calls, $1.3393828 catalog
estimate, publication `20a51b05-4441-464b-abcd-e36f088da231`. It reports distinct
business/risk observations but abstains on all three assessments; numerical
company valuation scenarios remain missing. See its `acceptance.json`,
`semantic-review.json` and structural audits. No research remains active.
Do not launch a duplicate or resume paid work automatically. The final monitor
question-heading change happened after publication; archived hashes remain valid
but current runtime identity differs, so only read-only replay is supported.
Port 8765 now follows the latest workspace run through a compatibility relay;
the workspace/question/report screens are on port 8766. The pilot is not a frozen
M4 release evaluation, and actual user usefulness feedback remains pending.

M3 publication, review/feedback, observation contracts and the graphical monitor
are implemented. Start with the [M3 implementation and acceptance record](AGENTIC_INVESTMENT_SYSTEM_V1_M3.md)
for commands, the retained synthetic publication, browser checks and limitations.
The monitor was confirmed reachable by the user. This is not research usefulness
feedback. M4 comparisons and V1 release remain open; no release case was evaluated.

The user also authorized disposable-cache removal after checks. The retention
audit is under `reports/repository-retention/`; datasets, reports, prior failed
runs, M4 comparators and backups remain protected. Changes are local and uncommitted.

The original pre-M3 checkpoint and requirements below are retained for provenance.
They are historical: the old “M3 next work” list and version descriptions are not
the current pending implementation queue. Use the session stop checkpoint above.

## Original checkpoint

Saved September 20, 2026. This file is the entry point for a new Codex session in
the same workspace. M0 inputs/comparator are registered; M1 and M2 engineering
acceptance passed. **M3 and M4 are open; V1 is not released.**

## Read first

1. [Full implementation plan](AGENTIC_INVESTMENT_SYSTEM_V1_PLAN.md), especially
   sections 6–9 and the original M3/M4 acceptance gates.
2. [Implementation record](AGENTIC_INVESTMENT_SYSTEM_V1_IMPLEMENTATION.md), especially
   “M2 engineering acceptance result,” commands and retained failed candidates.
3. [Conformance audit](AGENTIC_INVESTMENT_SYSTEM_V1_AUDIT.md).
4. [Required M3 graphical monitor](AGENTIC_INVESTMENT_RUN_MONITOR.md).
5. [M2 final-claim review and limitations](../reports/investment-research/m2-live-v7/acceptance-semantic.json).

## Accepted checkpoint

- M1: `reports/investment-research/m1-live-v4/`.
- M2: `reports/investment-research/m2-live-v7/`, run
  `67c78337-5e14-4913-8ffb-3d915ca9db8c`, terminal status `DRAFT`.
- M2 includes `draft.md`, structured product, state, 34 request/response pairs,
  28 evidence records, 44 manifests, source documents, archived runtime code,
  structural acceptance and semantic review. Registration is the adjacent
  `m2-live-v7-registration.json` file.
- Eleven tasks, 34 model invocations, 920.36 seconds, 842,864 input tokens,
  20,456 output tokens, $1.9118464 catalog estimate. All usage is known.
- Actual cooperation: Technical→Macro answer reuse and Geopolitics→Company new
  follow-up. All six questions and six Challenger objections receive dispositions.
- All five assessments are `insufficient_evidence`, with differentiated facts,
  theses and limitations. This is engineering acceptance, not user usefulness or
  investment-performance evidence. Nothing has been published or issued for scoring.
- Current synthetic fixture: `reports/investment-research/m2-engineering-fixture-v7/`.
  It is explicitly labeled synthetic. Preserve all six incomplete live candidates.

## Implementation map and invariants

- Python: `python/src/spy_predictor_quant/investment_research/`.
  `controller.py` owns scheduling, budgets and snapshots; `broker.py`/`sources.py`
  own bounded acquisition; `panels.py` owns comparisons; `multi_instrument.py`
  owns scoped validation/products; `rendering.py` emits stored numerical values.
- Worker: `packages/agent-runtime/src/pi-research-worker.ts` and
  `pi-research-contract.ts`. One admitted provider call per worker invocation;
  explicit later turns are separately receipted. Paid failures are not auto-retried.
- Current versions: prompts `v2.5`, runtime `investment-research-m2-v7`,
  mandate/findings/product schemas v3, action schema v4, worker protocol v2.
  Keep earlier versions and archived artifacts intact when adding M3 versions.
- `context.py` projects compact evidence. `evidence_transport.py` maps short model
  aliases to immutable IDs using each saved request's map. `result_transport.py`
  enforces stage/role-specific fields and exact final identity maps. These restore
  typed structure only; they do not repair judgments or rewrite numerical prose.
- `config/investment-research-m2-live-v7.json` is the frozen accepted mandate.
  Its acquisition window is dated: create a new mandate for fresh research.
- Terminal resume is a no-op with identical source identity; runtime changes
  invalidate execution resume. Read-only inspection still works. Do not edit old
  state/code archives to bypass this or relaunch M2 merely to recover chat context.

## M3 next work

Implement the original publication and feedback gate together with the user's
explicit monitor addition. A useful order is:

1. Version telemetry and its read-only projection: sequence numbers, terminal
   timestamps on every stop path, worker deadline, omissions and budget reserves.
2. Build the local single-run timeline grouped by role, with spawn/request/reuse
   links, shared budgets, elapsed/remaining/finish times, and a task inspector for
   individual findings, evidence, usage and recorded request/tool/output traces.
   Support live viewing and saved replay; follow the monitor acceptance fixtures.
3. Add one bounded final price/event refresh, affected-dependency invalidation,
   freshness/expiry validation and immutable publication bundles. Never backdate
   publication or treat a daily close as an executable quote.
4. Add thesis journal, linked review versions and structured user feedback.
5. Implement the separate publication-origin observation contract before scoring:
   first regular-session opening strictly after publication, origin session is
   session 1; target is session h close. Pair instrument/benchmark consistently,
   normalize corporate actions, and keep conditional observations separate.

The monitor does not replace the rest of M3. Required fixtures include material
price/news changes, market closure, stale quotes, expired conditions, splits and
incompatible return bases, plus monitor failures/reuse/interruption/replay.

Carry forward the semantic review's limitations: underused valuation tools,
bounded filing sections, broad abstention, repeated shared prose, and Markdown
conditions that need threshold/basis/expiry shown together. Exact scenario math
is tested; the accepted live run did not produce company valuation scenarios.

## M4 after M3 acceptance

Compare preserved old pipeline, one capable research agent with the same tools,
and the cooperating system. Separate fixed-evidence synthesis comparison from
end-to-end research under comparable budgets; report actual usage and failures.
Use frozen release cases only for the registered evaluation, not iterative tuning.

`examples/investment-research/` contains baseline/comparator records and separate
development/release v2 cases with SHA256 files. Release cases remain unevaluated;
protected historical cohorts and legacy observations remain untouched. Require
reviewed reports, defect scorecard, zero unresolved critical output errors, a
versioned keep/change/remove proposal, and actual user usefulness feedback.
Do not mark M4 complete based only on infrastructure tests or fluent reports.

## Verification and workspace state

Last implementation checks: 526 Python tests (43 focused research cases),
34 JavaScript tests and TypeScript compilation passed. Accepted M2 structural
audit and manual final-claim review passed with recorded limitations.

```sh
python/.venv/bin/python -m pytest python/tests -q
python/.venv/bin/python scripts/audit-investment-research-m2.py reports/investment-research/m2-live-v7
source /Users/juanpablo/.nvm/nvm.sh
nvm use 22
npm run build
npm run test
```

The workspace contains substantial pre-existing changes plus uncommitted/untracked
V1 work and artifacts. Preserve them; do not reset, clean or overwrite the legacy
work. Baseline META runtime/configuration hashes still match; the plan document is
the intentional baseline exception. Files are saved locally, **not committed or
pushed**. A new session must open this same workspace (a fresh clone will not
contain these local changes). No live M2 run remains active.
