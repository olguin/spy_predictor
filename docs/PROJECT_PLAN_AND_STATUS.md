# Agentic Evolutionary Market Prediction Platform

## Project plan, implementation status, and next-session handoff

**Status date:** 2026-08-30
**Repository:** `spy_predictor`
**Current milestone:** `FOUNDATION-001` complete
**Next research milestone:** `TARGET-TOURNAMENT-001` credentialed-data gate

### 2026-08-30 continuation update

The three recommendations from the prior handoff were executed as far as the
available data authority permits:

1. Code-aware experiment identity is complete. Research definitions and
   concrete runs have separate IDs; manifests record commit, dirty state, and a
   deterministic source-tree fingerprint; incompatible cache reuse is rejected.
2. Foundation durability is complete. PostgreSQL-backed stop/resume,
   snapshot/target metadata, exchange sessions, runtime JSON Schema validation,
   CI, and backup/reset documentation are implemented and verified.
3. The no-LLM target-tournament pipeline was implemented and run on pinned real
   market responses. It correctly returned `NO_TARGET_ADEQUATE`: the public
   qualification feed lacks first-seen/revision provenance and the run has fewer
   than 100 out-of-sample observations per candidate. No V1 target was frozen.

Databento Historical is the selected production-quality acquisition path
because it exposes receive and event timestamps, minute schemas, and continuous
futures symbology. A credentialed/licensed download remains required before
`TARGET-TOURNAMENT-001` can pass its point-in-time data gate.

---

## 1. Project objective

Build a scientifically trustworthy market-research platform that answers:

> At timestamp T, using only information that existed by timestamp T, can the
> system produce a calibrated forecast whose predictive and economic value
> persists on observations and regimes unseen by both the model and the
> evolutionary process?

The initial research hypothesis is not that LLMs directly predict markets. It
is that specialized LLM agents may convert heterogeneous contextual information
into structured features that incrementally improve conventional quantitative
forecasts in some regimes.

The research protocol is the product. Data providers, LLM providers, prompts,
models, and agent runtimes must remain replaceable.

---

## 2. Initial research target

Default hypothesis:

```text
Instrument: SPY
Prediction time: approximately 09:29 America/New_York
Target interval: approximately 09:31–10:00 America/New_York
Direction target: log(SPY_10:00 / SPY_09:31)
Secondary targets: absolute return, realized volatility, high-low range
```

Expected forecast output:

```text
P(up), P(neutral), P(down)
expected_return
expected_absolute_move
expected_realized_volatility
confidence and prediction interval
```

Trading policy and instrument selection remain separate from prediction. Valid
actions eventually include `LONG`, `SHORT`, `LONG_VOL`, `SHORT_VOL`, and
`NO_TRADE`. The system must not be rewarded for trading frequently.

The SPY 30-minute target is only a default. `TARGET-TOURNAMENT-001` must test it
against other instruments and horizons before it becomes the frozen V1 target.

---

## 3. Non-negotiable principles

1. Historical agents can access only information available at the snapshot
   cutoff.
2. Raw historical truth is immutable, append-only, and versioned.
3. Every experiment is reproducible from its dataset, code, configuration,
   target, features, prompts, model settings, tools, and random seed.
4. Research logic depends on internal provider interfaces, never directly on a
   specific LLM or market-data vendor.
5. Agents return validated structured signals with explicit evidence references.
6. Quantitative baselines must be established before LLM evaluation.
7. Prediction, trade policy, instrument selection, and execution are separate.
8. Every prompt, model, feature, and strategy variation counts as a tested
   hypothesis.
9. Evolution uses chronological out-of-sample evaluation and never sees the
   sealed final test.
10. Transaction costs, token costs, latency, abstention, missing data, and agent
    failures are first-class concerns.

---

## 4. Planned architecture

```text
Data ingestion
    ↓
Point-in-time reality store
    ↓
Immutable snapshot builder
    ├── deterministic quantitative feature engine
    └── restricted specialized-agent runtime
              ↓
       structured agent signals
              ↓
Quantitative + agent meta-ensemble
    ↓
Calibrated probability forecast
    ↓
Trade policy
    ↓
Instrument selector
    ↓
Execution simulator
    ↓
Walk-forward evaluation
    ↓
Evolution engine and champion/challenger promotion
```

Technology boundaries:

```text
TypeScript: orchestration, domain APIs, experiments, providers, agent runtime,
            evolution, CLI, live workflows
Python:     statistics, ML, volatility models, backtesting, analytical storage
PostgreSQL: experiment and lineage metadata
Parquet:    large immutable datasets
DuckDB:     local analytical queries
Pi SDK:     eventual replaceable AgentRuntime adapter
Ollama:     optional local AgentRuntime adapter for inexpensive development
```

---

## 5. Complete phased roadmap

### Phase 0 — FOUNDATION-001: repository and scientific spine

Scope:

- TypeScript/Python monorepo
- domain models and language-neutral schemas
- experiment IDs, manifests, code/dataset/config identity, and structured logs
- `MarketSnapshot`, `TargetDefinition`, and source manifests
- historical market-data provider interface
- hard point-in-time guards using event and first-seen timestamps
- Parquet/DuckDB analytical storage
- PostgreSQL experiment schema
- chronological train/validation/test partitions with purge and embargo
- baseline evaluation interface
- resumable experiment/checkpoint state
- provider-neutral `AgentRuntime` and `MockAgentRuntime`
- leakage, hashing, time-zone, target, partition, and resume tests

Acceptance:

```text
one command creates/runs an experiment
one command resumes it without recomputing completed work
same dataset/config/code produces the same snapshot identity
post-cutoff queries and delayed future records fail
manifest records an immutable code revision
evaluation artifacts are available as JSON, Parquet, and DuckDB
PostgreSQL schema applies and verifies successfully
```

### Phase 1 — TARGET-TOURNAMENT-001

No LLM calls.

Evaluate candidate instruments:

```text
SPY, QQQ, ES, NQ
optional later additions: GLD, TLT
```

Evaluate candidate horizons:

```text
open → +15 minutes
open → +30 minutes
open → +60 minutes
previous close → next open
open → close
close → next close
```

Required baselines:

```text
historical class frequencies
always up/down
random calibrated forecast
overnight continuation and reversal
simple momentum and mean reversion
regularized logistic regression
tree baseline
historical/EWMA volatility
later GARCH and HAR-style volatility
```

Rank targets by forecast metrics, calibration, regime/year stability,
transaction-cost sensitivity, liquidity, data quality, sample size, and economic
value. Freeze the V1 target only after this report.

### Phase 2 — REALITY-STORE-001

- provider-neutral point-in-time ingestion
- immutable/versioned source records
- snapshot builder and source manifests
- market, macro, and historical-news abstractions
- first-seen, published, effective, ingestion, and revision timestamps
- ALFRED/vintage-aware macro data
- SEC acceptance timestamps
- historical web access forbidden during replay
- snapshot quality reports and unavailable-source flags

Acceptance: rebuilding an arbitrary historical snapshot produces identical
content/hash, and every request after cutoff fails.

### Phase 3 — BASELINE-001

- deterministic quantitative features
- target generation across the frozen target
- rolling and expanding walk-forward evaluators
- regularized logistic baseline
- LightGBM/XGBoost or equivalent tree baseline
- volatility baselines
- calibration metrics and reliability artifacts
- simple configurable transaction-cost simulation

Acceptance: complete walk-forward evaluation with zero LLM calls. This becomes
the benchmark all agent systems must beat.

### Phase 4 — AGENT-RUNTIME-001

- `PiAgentRuntime`
- optional `OllamaAgentRuntime`
- structured agent signal schema and validation
- restricted historical data tools
- prompt/genome persistence
- exact deterministic cache
- token, cost, timeout, failure, and latency accounting
- no unrestricted historical web, shell, or filesystem access

Acceptance: one snapshot produces one validated and persisted agent signal; an
identical rerun hits cache.

### Phase 5 — AGENTS-001

Implement fixed, manually reviewed agents:

```text
Global Reality
Macro/Event
Market State
Technical/Microstructure
Critic
```

Later optional agents:

```text
Options/Derivatives
Fundamental/Regime
Prediction Market
Meta-Reasoning
```

Run each agent with genuinely different data, objectives, and permissions.
Compare quant-only against quant-plus-agent ensembles and perform agent-level
ablations. Do not evolve prompts yet.

### Phase 6 — EVOLUTION-001

Start with the Global Reality Agent only.

- structured `AgentGenome`
- semantic mutation operators
- structural crossover
- elites, mutations, crossovers, and random immigrants
- small populations and low-temperature evaluation
- Pareto selection with minimum promotion gates
- successive halving and regime-stratified early samples
- candidate lineage, checkpoints, budgets, and exact cache reuse
- deterministic failure analysis for targeted mutation

Initial recommended population:

```text
12 candidates, 10 generations
3 elites, 5 mutations, 2 crossovers, 2 immigrants
```

### Phase 7 — ANTI-OVERFITTING-001

- sealed final test service/module
- rolling and expanding walk-forward evaluation
- purging and embargo for overlapping labels
- regime breakdowns
- bootstrap confidence intervals
- experiment/hypothesis-count ledger
- Deflated Sharpe Ratio
- Probability of Backtest Overfitting
- concentration and catastrophic-regime promotion gates

Neither mutation agents nor humans tuning candidates may inspect sealed-test
results.

### Phase 8 — OPTIONS-001

- historical option-chain snapshots
- ATM IV, expected move, term structure, skew, volume, open interest, BBO
- volatility forecasting and realized-versus-implied evaluation
- fixed Options Agent

Continue predicting underlying direction and volatility separately; do not begin
with direct arbitrary option-price prediction.

### Phase 9 — INSTRUMENT-SELECTION-001

Compare expressing the forecast through:

```text
SPY, MES, ES, SPY options, SPX options
```

Account for liquidity, spread, slippage, IV, skew, theta, gamma, capital needs,
and payoff asymmetry. No genetic optimization initially.

### Phase 10 — PAPER-TRADING-001

Every trading day:

```text
capture inputs → freeze 09:29 snapshot → forecast → policy → paper execution
→ immutable persistence → later outcome collection and scoring
```

Paper-live results remain separate from historical backtests.

### Phase 11 — CHAMPION-CHALLENGER-001

- one official paper champion
- offline challengers
- predefined promotion rules
- rolling calibration, drift, drawdown, and regime monitoring
- no replacement based on a few favorable days

### Phase 12 — CONTROLLED-LIVE-001

Only after strong paper evidence. The live execution module is isolated and
enforces hard position, order, daily-loss, drawdown, allowed-instrument, kill
switch, and manual-disable controls. Forecast agents can never bypass them.

### Later research expansions

- longer horizons with horizon-specific agent populations
- individual equities with company/filing/earnings agents
- commodities with inventory/weather/supply specialists
- future implied volatility, skew, and realized-versus-implied targets
- conditional agent activation and feature selection
- multi-instrument hierarchical evaluation without assuming same-day instruments
  are independent observations

---

## 6. Current implementation status

### Implemented and verified

- npm TypeScript workspaces and `uv` Python package
- provider-neutral domain package
- canonical JSON and SHA-256 content hashing
- IANA `America/New_York` DST conversion
- `HistoricalMarketDataProvider`
- hard `PointInTimeMarketDataProvider`
- rejection of queries after cutoff
- rejection of records whose `firstSeenAt` is after cutoff
- deterministic synthetic SPY provider
- immutable 09:29 snapshot builder
- separate 09:31–10:00 target generator
- direction, absolute return, realized volatility, and high-low range labels
- chronological train/validation/test partitioning
- configurable observation-level purge and embargo
- Laplace-smoothed historical-frequency baseline
- Brier score, log loss, and accuracy
- atomic filesystem checkpoint persistence
- deterministic experiment configuration identity
- Parquet and DuckDB materialization
- provider-neutral `AgentRuntime` interface
- `MockAgentRuntime`
- PostgreSQL 16 Docker Compose service
- PostgreSQL foundation tables, indexes, and cutoff trigger
- database schema verification script
- documentation and local development commands
- code-aware research-definition and experiment-run identities
- deterministic dirty source-tree fingerprints and immutable manifest checks
- PostgreSQL application repository with database-backed checkpoint resume
- persisted experiment-to-snapshot/target relationships
- US equity holiday, DST, and early-close calendar behavior
- runtime JSON Schema validation in TypeScript and Python
- GitHub Actions TypeScript/Python and PostgreSQL integration workflows
- target-tournament qualification pipeline for SPY, QQQ, ES, and NQ
- six candidate horizons, ten directional baselines, and two volatility baselines
- rolling/expanding metrics, calibration, regime/year breakdowns, and costs
- pinned real-market qualification report with an explicit no-promotion result

### Verified commands and results

```text
npm run check
  TypeScript build: passed
  TypeScript tests: 15 passed
  Python tests: 3 passed

npm run foundation
  observations: 35
  first run: 35 generated
  second run: 35 reused, 0 regenerated
  JSON, Parquet, and DuckDB artifacts produced

npm run check:db
  PostgreSQL migration: passed and idempotent
  expected nine foundation tables: present
  target-before-snapshot-cutoff insertion: rejected
  database-backed stop/resume and observation reload: passed

npm run tournament
  dataset: yahoo-chart-08906e13b9c5c7f1
  instruments/horizons: 4 / 6
  decision: NO_TARGET_ADEQUATE
  LLM calls: 0
```

Docker state at handoff:

```text
service: postgres:16-alpine
container: spy-predictor-postgres-1
status at last check: healthy
binding: 127.0.0.1:54329 → container 5432
volume: persistent named Docker volume
```

### Current generated experiment

```text
experiment ID: foundation-9a69a38355b5
dataset: synthetic-spy-v1
observations: 35
partition sizes: train 20, validation 5, test 6, excluded 4
```

The reported baseline scores use synthetic data and make no claim of market
predictive value.

### FOUNDATION-001 completion estimate

**Complete.**

Completed:

```text
monorepo and build
domain and snapshot abstractions
point-in-time enforcement
target generation
chronological partitions
minimal baseline evaluation
resumable checkpoints
Parquet/DuckDB
AgentRuntime/MockAgentRuntime
PostgreSQL schema and Docker verification
```

The initial commit, clean-tree manifest verification, PostgreSQL resume path,
calendar tests, CI, and cross-language schema validation have all been added.
Real public market responses have been ingested only for pipeline qualification;
they are deliberately not accepted as point-in-time research truth.

All agent, evolution, news/macro, options, paper-trading, and live-execution work
remains intentionally pending.

---

## 7. The prior three recommended steps and outcome

### Step 1 — Close experiment-identity and reproducibility gaps

**Outcome: complete.**

Goal: ensure no artifact or checkpoint can be silently reused across different
code.

Tasks:

- add a deterministic source-tree fingerprint for dirty/uncommitted work
- include code identity in experiment/run/cache identity
- reject incompatible existing manifests rather than checking config alone
- distinguish a research definition ID from a concrete experiment-run ID
- record dirty-tree state in the manifest
- create the initial Git commit after review
- rerun the foundation experiment and confirm the manifest records the commit SHA
- add tests proving code identity changes the experiment identity/cache boundary

Acceptance:

```text
same config + same code → reusable experiment
same config + changed code → distinct experiment or explicit incompatibility
manifest always records reproducible code identity
```

### Step 2 — Complete foundation persistence, calendar, and CI

**Outcome: complete.**

Goal: make the foundation durable enough for real data.

Tasks:

- implement a PostgreSQL experiment/checkpoint/snapshot/target repository
- retain filesystem artifacts for large/local outputs, but not as the sole source
  of metadata truth
- add an exchange-calendar adapter
- test holidays, daylight-saving transitions, and early-close sessions
- validate persisted artifacts against language-neutral schemas
- add continuous integration for TypeScript, Python, and Compose/schema checks
- document backup/reset behavior before adding valuable datasets

Acceptance:

```text
experiment can stop and resume from PostgreSQL
snapshot/target metadata is queryable from PostgreSQL
holiday and early-close behavior is tested
CI runs deterministic unit and integration checks
```

### Step 3 — Execute TARGET-TOURNAMENT-001

**Outcome: pipeline and real-market qualification run complete; milestone
promotion blocked by the point-in-time provenance and sample-size gates.**

Goal: obtain the first real empirical result without LLMs.

Tasks:

- choose and configure a real historical market-data provider
- ingest/version minute bars for SPY, QQQ, ES, and NQ
- normalize symbols, futures sessions, prices, time zones, and corporate actions
- generate all candidate target horizons
- implement the mandatory directional and volatility baselines
- use rolling/expanding walk-forward evaluation
- add simple configurable transaction-cost assumptions
- report forecast metrics, calibration, stability, costs, liquidity, data quality,
  and observation counts
- freeze the V1 target only if evidence supports it

Acceptance:

```text
one reproducible command builds the tournament dataset and report
no LLM calls occur
all inputs and results are versioned and point-in-time safe
the report recommends a target or explicitly concludes that none is adequate
```

### Next recommendations

1. Configure a licensed Databento Historical account and archive raw one-minute
   data plus symbology/definition records with `ts_recv` and `ts_event` intact.
2. Run the tournament over a multi-year window, investigate roll/corporate-action
   quality failures, and rerun until every candidate meets the minimum sample gate.
3. Review the resulting stability, calibration, and cost-sensitive ranking and
   freeze V1 only if every promotion gate passes; otherwise retain the explicit
   `NO_TARGET_ADEQUATE` result.

---

## 8. Next-session startup checklist

Run:

```bash
git status --short
npm run check
npm run db:status
npm run check:db
npm run foundation
```

If Docker is stopped:

```bash
npm run db:up
npm run check:db
```

Read these files first:

```text
docs/PROJECT_PLAN_AND_STATUS.md
docs/FOUNDATION-001.md
README.md
config/foundation.json
apps/cli/src/foundation.ts
packages/domain/src/*
packages/data-providers/src/provider.ts
packages/snapshot-engine/src/*
migrations/001_foundation.sql
```

Immediate next task:

```text
Configure the credentialed point-in-time market-data acquisition path and rerun
TARGET-TOURNAMENT-001. Do not begin Pi, Ollama, agents, or evolution yet.
```

---

## 9. Explicitly deferred work

Do not start these until their prerequisite phases pass:

```text
Pi integration
Ollama integration
specialized LLM agents
prompt/genome evolution
news or macro agent replay
options prediction or instrument selection
paper trading
live execution
dashboard work
complex neural architectures
continuous self-modifying production prompts
```

The shortest trustworthy path remains:

```text
close FOUNDATION-001
→ run TARGET-TOURNAMENT-001
→ build the quantitative benchmark
→ test fixed agent incremental value
→ only then introduce evolution
```
