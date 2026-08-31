# spy-predictor

Research infrastructure for point-in-time, reproducible market forecasting.

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

Pi, Ollama, and evolutionary optimization remain deliberately deferred.
