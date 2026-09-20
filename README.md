# spy-predictor

Research infrastructure for point-in-time, reproducible market forecasting.

The proposed next product iteration is **Agentic Investment System V1**: a
cooperating research team for investment decisions over several weeks to three
months. Start with the [V1 implementation plan](docs/AGENTIC_INVESTMENT_SYSTEM_V1_PLAN.md).
Implementation under that plan has not started.

The existing engineering baseline is **Improvement Plan 3**; see its
[implementation handoff](docs/IMPROVEMENT_PLAN_3_HANDOFF.md) and
[project status](docs/PROJECT_PLAN_AND_STATUS.md). Archived synthesis and a fresh
chain through compact recovery are verified; ordinary-path reliability and other
acceptance work remain. Existing historical ETF results remain diagnostic;
statistical/data qualification is separate from engineering.

The separate Cycle 1 pre-evaluation repair remains preserved; see its
[repair findings](docs/CYCLE1_REPAIR.md).
`npm run cycle1:preflight` audits the pinned dataset without model metrics;
exit code 2 reports the known scientific blockers. The old v4 dataset is
suspended for evaluation, and its repaired offline rebuild fails closed on
missing historical cash-rate publication coverage.

The separate multi-agent **GOLDEN GOAL** watchlist pipeline is implemented
through G10. It accepts a normal set of five symbol/ETF parameters, captures
current evidence, runs five specialists plus critic and synthesis, generates
experimental 5/21/63-session forecasts and recommendations, and writes a
readable local cockpit. Start with the
[`daily operations and interpretation guide`](docs/GOLDEN_GOAL_DAILY_OPERATIONS.md).

The repository contains the hardened **FOUNDATION-001** research spine and a
no-LLM **TARGET-TOURNAMENT-001** qualification pipeline. The foundation uses a
deterministic synthetic dataset; the tournament pins raw real-market responses
and refuses to freeze a target when provenance or sample-size gates fail.

## Prerequisites

- Node.js 22 or newer
- npm
- Python 3.12–3.14
- [`uv`](https://docs.astral.sh/uv/)

## Run the foundation experiment

```bash
npm install
UV_CACHE_DIR=.uv-cache uv sync --project python
npm run foundation
```

The command performs this complete flow:

```text
synthetic point-in-time bars
→ immutable 09:29 ET snapshots
→ separate 09:31–10:00 labels
→ purged chronological partitions
→ historical-frequency baseline
→ JSON experiment artifacts
→ Parquet + DuckDB materialization
```

Run it again to reuse all completed daily checkpoints. To exercise resume
behavior manually:

```bash
npm run foundation -- --stop-after 5
npm run foundation
```

Generated outputs live under `experiments/foundation-*` and
`datasets/foundation/`. They are intentionally ignored by Git.

Experiment manifests separate a configuration-derived `researchDefinitionId`
from a concrete, code-aware `experimentId`. Clean work records the Git commit;
dirty or uncommitted work additionally receives a deterministic source-tree
fingerprint, preventing checkpoint reuse after a code change.

## Verification

```bash
npm run check
```

Tests cover deterministic hashing, code-aware identity, New York daylight-saving conversion,
cutoff rejection, delayed-record leakage, immutable snapshots, target
separation, holidays and early closes, purged chronological partitions,
filesystem and PostgreSQL checkpoint resume behavior, JSON-schema validation,
and DuckDB/Parquet materialization.

## PostgreSQL with Docker

The local database binds only to `127.0.0.1` on port `54329`. Development
defaults are defined in `compose.yaml`; copy `.env.example` to `.env` only when
you need to override them.

```bash
npm run db:up
npm run db:migrate
npm run db:verify
```

`db:migrate` is idempotent. `db:verify` checks the nine foundation tables and
proves that the database rejects a target whose start is before its snapshot
cutoff. `check:db` also runs a database-backed stop/resume integration check.
Set `DATABASE_URL` when running `foundation` to use PostgreSQL as metadata truth:

```bash
DATABASE_URL=postgresql://spy_predictor:spy_predictor_dev@127.0.0.1:54329/spy_predictor npm run foundation
```

Stop the container without deleting its named volume using:

```bash
npm run db:down
```

Backup and destructive-reset precautions are documented in
[`docs/DATA_DURABILITY.md`](docs/DATA_DURABILITY.md).

## Run the target tournament qualification

```bash
npm run tournament
```

This pins raw SPY, QQQ, ES, and NQ responses, generates six horizons, and runs
expanding and rolling evaluations with directional, volatility, calibration,
stability, and transaction-cost metrics. The public qualification feed does
not provide original first-seen/revision timestamps, so its report is required
to return `NO_TARGET_ADEQUATE`; it validates the pipeline but cannot freeze V1.
See [`docs/TARGET-TOURNAMENT-001.md`](docs/TARGET-TOURNAMENT-001.md).

## Complete the Phase 1 target tournament

The production Phase 1 path uses the existing Alpaca account for raw SIP
SPY/QQQ bars and Massive Futures Basic ($0/month) for explicit ES/NQ contracts.
It never requests account data or submits orders. Put `MASSIVE_API_KEY` beside
the existing Alpaca credentials in the ignored `.env`, then run:

```bash
npm run massive:check
npm run phase1
```

The check reports Futures and Indices separately. Phase 1 requires
`futures.status: ok`. The META intraday VIX panel additionally requires
`indices.status: ok` for both `I:VIX` and `I:VIX3M`; `not_entitled` is a visible
current-volatility gap and does not imply the Futures credential is invalid.

`npm run phase1` builds or resumes the immutable two-year raw archive,
normalizes the fixed 09:30–16:00 New York research session, verifies every
configured futures contract and roll, compares all four instruments with the
pinned IBKR history, and runs the 24-candidate sealed-confirmation tournament.
Massive's free Futures five-request-per-minute limit makes the first acquisition slow;
completed pages are always reused.

After the first acquisition, prove that no network access or recomputation is
required and that identities are stable with:

```bash
npm run phase1 -- --offline
```

## Repository boundaries

- `apps/cli`: experiment entry point
- `packages/domain`: research types, hashing, and time invariants
- `packages/data-providers`: provider interface and hard cutoff wrapper
- `packages/snapshot-engine`: immutable snapshots and future target generation
- `packages/evaluation`: chronological partitions and baseline metrics
- `packages/persistence`: resumable local experiment state
- `packages/agent-runtime`: provider-neutral interface and mock runtime
- `python`: DuckDB/Parquet analytical boundary
- `migrations`: PostgreSQL metadata schema
- `schemas`: language-neutral JSON schemas

Pi-based META research is isolated from the Cycle 1 experiment authorities and
has no order path. Ollama and evolutionary optimization remain deferred.

### Improvement Plan 3

The first contract/research engineering release uses v3 forecasts and product views
and v4 agent requests. It adds point-in-time research storage, purged experimental
comparisons, dated event controls, auditable conditions and price-freshness overlays.
The ten-phase plan remains in progress; production probabilities remain heuristic
and uncalibrated. See [delivery evidence, commands and remaining gates](docs/IMPROVEMENT_PLAN_3_IMPLEMENTATION.md).
