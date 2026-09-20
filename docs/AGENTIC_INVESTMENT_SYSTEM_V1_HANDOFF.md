# V1 handoff — start M3, then M4

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
