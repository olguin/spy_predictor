# Agentic Evolutionary Market Prediction Platform

## Project plan, implementation status, and next-session handoff

**Status date:** 2026-09-05
**Repository:** `spy_predictor`
**Current milestone:** `TARGET-TOURNAMENT-001` complete with
`NO_TARGET_ADEQUATE`
**Latest completed work:** immutable two-year Alpaca/Massive dataset, explicit
futures rolls, four-provider comparisons, and sealed-confirmation tournament
**Immediate next task:** review the no-target result and decide whether to widen
the preregistered target search before beginning `REALITY-STORE-001`

### Executive status audit

This table compares the original phase acceptance criteria with code, tests,
generated artifacts, and integration runs present as of the status date.
Overall: two of thirteen phases are complete, three have partial/scaffold work,
and eight have not started.

| Phase | Status | What exists now | What is still required |
|---|---|---|---|
| 0 — `FOUNDATION-001` | **Complete** | Reproducible experiment identity, point-in-time guards, snapshots/targets, purged partitions, resumable filesystem/PostgreSQL persistence, schemas, Parquet/DuckDB materialization, CI, and a provider-neutral runtime interface | No Phase 0 acceptance item remains; keep the foundation green while extending it |
| 1 — `TARGET-TOURNAMENT-001` | **Complete — no target frozen** | Immutable Alpaca SPY/QQQ plus Massive ES/NQ minute data, 18 verified futures contracts, explicit rolls, 779,985 normalized bars, four passing IBKR comparisons, 24 candidate evaluations, and 100 sealed confirmation observations each | No acceptance item remains. The result is `NO_TARGET_ADEQUATE`; any wider target search must be a new preregistered hypothesis set |
| 2 — `REALITY-STORE-001` | **Foundation subset only** | Generic market provider/cutoff guard, source manifests, immutable snapshots, and immutable/hash-addressed IBKR raw/history/live artifacts | A provider-neutral persistent store spanning market, macro, SEC, news, revisions/vintages, quality flags, and deterministic arbitrary-date replay |
| 3 — `BASELINE-001` | **Prototype subset only** | Tournament implementations of logistic/tree/rule baselines, historical/EWMA volatility, walk-forward metrics, calibration, regime/year breakdowns, and simple costs | First freeze the target; then build the production feature set and benchmark artifacts, add the selected boosted-tree equivalent and remaining volatility/reliability work, and pass the Phase 3 acceptance run |
| 4 — `AGENT-RUNTIME-001` | **Scaffold only** | `AgentRuntime` contract and `MockAgentRuntime` | Pi/Ollama adapters, validated signal schema, restricted tools, prompt/genome persistence, deterministic cache, accounting, failure handling, and a persisted cache-hit acceptance test |
| 5 — `AGENTS-001` | **Not started** | None beyond the runtime scaffold | Fixed reviewed agents, distinct inputs/permissions, ensembles, and ablations |
| 6 — `EVOLUTION-001` | **Not started** | No genome or evolutionary code | Genome, mutation/crossover, selection, lineage, checkpoints, budgets, and promotion gates |
| 7 — `ANTI-OVERFITTING-001` | **Not started** | Basic chronological purge/embargo and year/regime summaries exist in earlier phases | Sealed test service, bootstrap intervals, hypothesis ledger, DSR/PBO, and concentration/catastrophic-regime gates |
| 8 — `OPTIONS-001` | **Not started** | Snapshot schema can mark options unavailable | Historical option-chain data, features, evaluation, and fixed Options Agent |
| 9 — `INSTRUMENT-SELECTION-001` | **Not started** | No instrument-expression evaluator | Cost/risk/payoff comparison across SPY, MES, ES, SPY options, and SPX options |
| 10 — `PAPER-TRADING-001` | **Not started** | Alpaca paper credentials and IBKR paper Gateway connectivity are configured for **market data only** | Daily snapshot/forecast/policy/paper-order/outcome workflow and immutable separation from backtests |
| 11 — `CHAMPION-CHALLENGER-001` | **Not started** | None | Official champion, offline challengers, monitoring, and predefined promotion rules |
| 12 — `CONTROLLED-LIVE-001` | **Not started** | No order-submission code; IBKR integration deliberately fails closed to paper/read-only market data | Only after paper evidence: isolated execution plus hard risk, loss, instrument, kill-switch, and manual-disable controls |

The critical path has therefore not reached agents or trading. Phase 1 closed
without a target, so the current decision point is:

```text
review NO_TARGET_ADEQUATE evidence
→ either preregister a bounded target-search extension and rerun
→ or stop target discovery
→ only after a target is frozen: build the broader point-in-time Reality Store
→ complete the production quantitative baseline
→ test fixed agents before evolution
```

### 2026-09-05 TARGET-TOURNAMENT-001 completion

Phase 1 is complete. The free Massive Futures Basic key was verified without
adding a paid subscription. One command now builds or resumes the immutable
dataset, performs four cross-provider comparisons, and runs the tournament:

```bash
npm run phase1
npm run phase1 -- --offline
```

The pinned dataset covers 2024-09-03 through 2026-09-03:

```text
dataset:          phase1-market-e70bdc3ff5238003
dataset hash:     e70bdc3ff5238003978778e6f3f7636eb120f16258a5a9066003e85da029c1e9
normalized bars: 779,985
SPY / QQQ:        503 research sessions
ES / NQ:          500 research sessions
futures:          18 exact contracts, 9 explicit mappings per instrument
provenance:       event-time-only; target-selection admissible, not replay-safe first-seen
```

The comparison gate passed for every instrument. Intersections and maximum
close differences were SPY 853 / 0.260 bps, QQQ 879 / 0.417 bps, ES 1,379 /
0.324 bps, and NQ 1,380 / 0.590 bps.

All 24 instrument/horizon candidates had 100 observations in the final
chronological confirmation segment. Coverage was 98.77% or better. No candidate
passed all promotion gates. In particular, the best apparent result was only a
tiny probability-smoothing improvement over historical frequencies and made
the same directional decisions, so it failed the material Brier-improvement,
incremental-economic-value, stress-cost, and stability gates.

Final report:

```text
decision:     NO_TARGET_ADEQUATE
report hash:  cd393a5b710cd17692648d10e0418be07e7391a7eeb030f6d52371d4c6523072
report path:  reports/phase1-cd393a5b710cd176/report.json
LLM calls:    0
orders:       0
```

An initial validation run exposed that a zero improvement threshold could let
numerically trivial logistic smoothing pass despite identical economic actions.
The acceptance gate was corrected to require an absolute 0.005 Brier improvement
and incremental net return before Phase 1 was closed. The conservative final
result rejects every candidate rather than promoting that artifact.

### 2026-09-04 IBKR adapter update

The Alpaca paper credentials and historical SIP connectivity probe are working.
IB Gateway was verified locally in paper/read-only mode on port 4002 with the
official Python API 10.50.1.

IBKR adapter increment 1 is complete:

1. The one-shot health check now uses a reusable session that owns the network
   loop, enforces localhost/paper/read-only configuration, correlates finite
   request IDs, handles timeouts, and separates informational events from
   request failures.
2. Versioned `reqContractDetails` queries resolve SPY, QQQ, ES, and NQ. Stocks
   must resolve uniquely; futures remain explicit dated contracts and are never
   silently converted to continuous or front-month series.
3. Successful catalogs are immutable, ignored local artifacts containing exact
   `conId` values, contract/trading metadata, capture metadata, and a stable
   content hash.

The verified catalog resolves SPY `conId` 756733 on ARCA and QQQ `conId`
320227571 on NASDAQ. The nearest returned CME contracts at verification time
were ESU6 `conId` 649180671 and NQU6 `conId` 770561204, both expiring
2026-09-18. These examples are dated observations, not a permanent front-month
selection rule.

IBKR adapter increments 2 and 3 are also complete:

1. The recent-history downloader uses exact catalog contracts, one-day chunks,
   trading-weekday windows, a configurable rolling pacing limit, bounded retry
   of transient conditions, and a default twenty-minute end lag. Every run
   preserves raw callbacks, normalized one-minute bars, hashes, request
   failures, duplicates, and gap candidates. Backfill is correctly labeled
   `event-time-only`.
2. The cross-provider reporter archives raw Alpaca SIP pages and compares SPY
   and QQQ coverage, missing/duplicate timestamps, timestamp offsets, session
   boundaries, OHLC, volume, and outliers. ES/NQ are explicitly left
   `not-configured` until the planned Massive Futures dataset exists.
3. Live capture subscribes to exact contracts using IBKR five-second `TRADES`
   bars, records local receipt time immediately, rotates raw files by instrument
   and trading session, suppresses reconnect duplicates, aggregates deterministic
   one-minute bars, marks incomplete minutes, reconnects within a bounded
   policy, and writes a signal-safe manifest.

Final integration evidence on 2026-09-04/05:

```text
IBKR history:    ok, 4,680 bars, zero failed chunks
                 SPY 960, QQQ 960, ESU6 1,380, NQU6 1,380
Alpaca compare:  ok, 853 intersecting SPY minutes and 879 QQQ minutes
                 maximum close difference below 0.42 bps for both
Live capture:    operational but account-entitlement limited
                 IBKR code 354/420: no real-time API permissions for stocks/CME
```

Evidence artifacts (local, immutable, and intentionally Git-ignored):

```text
contracts: datasets/ibkr/contracts/catalog-20260904T233249778093Z-525ae22c5fd89a35.json
history:   datasets/ibkr/history/history-20260905T014403581407Z-c4389d82/manifest.json
compare:   datasets/comparisons/comparison-20260905T014416137105Z-c1160dcc/report.json
live:      datasets/ibkr/live/live-20260905T013756002651Z-f34e6a4a/manifest.json
```

The live adapter emits no fabricated data under that entitlement failure. No
paid real-time entitlement is planned. The bulk Alpaca/Massive acquisition and
all four historical cross-provider comparisons are now complete.

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

### 2026-08-31 market-data decision update

Databento is no longer the planned provider. It has excellent receive/event
timestamp provenance, minute schemas, and continuous-futures support, but its
cost is disproportionate to this pre-signal-discovery phase. Paying premium
data costs before establishing that any candidate target has predictive value
would invert the intended research order.

The selected low-cost architecture is now:

```text
historical SPY/QQQ: Alpaca free historical SIP bars
historical ES/NQ:   Massive Futures Basic (two years free)
live/recent data:   existing personal IBKR account through TWS/IB Gateway
durable truth:      immutable local raw archive with content hashes and
                    locally recorded first-seen timestamps for live events
```

IBKR-only backfill remains a fallback and cross-provider validation source, but
not the preferred bulk source because Interactive Brokers throttles large
historical downloads and generally does not retain expired futures beyond two
years from expiration. If two years of free futures history produces evidence
worth pursuing, a single paid deeper-history acquisition can be considered at
that point rather than becoming a recurring cost now.

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
- Alpaca paper-account authentication and historical SIP connectivity probe
- official IBKR Python API 10.50.1 installed in the project environment
- reusable localhost-only, paper-only, read-only IBKR Gateway session
- immutable SPY/QQQ/ES/NQ contract catalogs with exact contract identifiers
- paced, resumable IBKR one-minute recent-history download with immutable raw
  callbacks, normalized bars, manifests, hashes, and quality reporting
- cross-provider SPY/QQQ comparison against archived Alpaca SIP responses
- locally timestamped IBKR five-second live capture, deterministic one-minute
  aggregation, session rotation, reconnect deduplication, and signal-safe
  manifests
- explicit safety boundary: no account queries, order construction, or order
  submission in the IBKR market-data adapter

### Verified commands and results

```text
npm run check
  reverified: 2026-09-05
  TypeScript build: passed
  TypeScript tests: 15 passed
  Python tests: 23 passed

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

npm run ibkr:contracts
  exact contracts: SPY, QQQ, ESU6, NQU6
  immutable catalog and content hash produced

npm run ibkr:history
  status: ok
  normalized one-minute bars: 4,680
  failed chunks: 0
  provenance: event-time-only

npm run ibkr:compare
  SPY intersection: 853 minutes; maximum close difference: 0.260 bps
  QQQ intersection: 879 minutes; maximum close difference: 0.417 bps
  ES/NQ: not-configured until Massive history exists

npm run ibkr:capture
  adapter reached IBKR and requested all four exact contracts
  status: partial; 0 bars because the account lacks real-time API entitlements
  IBKR rejected subscriptions with code 354/420; no data was fabricated

npm run phase1 -- --offline
  dataset: phase1-market-e70bdc3ff5238003
  normalized one-minute bars: 779,985
  explicit futures contracts / mappings: 18 / 18
  cross-provider gates: SPY, QQQ, ES, and NQ passed
  candidates / confirmation observations each: 24 / 100
  decision: NO_TARGET_ADEQUATE
  LLM calls / orders: 0 / 0
```

Current Docker state on 2026-09-05:

```text
service: postgres:16-alpine
status: stopped / no running container
binding: 127.0.0.1:54329 → container 5432
implementation status: migrations and integration path previously verified
```

The IBKR/Alpaca adapter increment was committed as `ee1bf42`; the Phase 1
implementation was committed as `196f5be`. A clean-source offline rerun from
the pinned bytes reproduced the final identities.

### Clean-tree reproducibility verification

```text
verified commit: 267550d64db3729ea72f1107c0b124d21016c1de
experiment ID at that commit: foundation-21d1daff218c0a0c
manifest dirty flag: false
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

All agent, evolution, news/macro, options, paper-trading, and order-execution
work remains intentionally pending. Market-data-only live capture is
implemented, but a successful live-recording run awaits IBKR real-time market
data entitlements.

### Market-data source analysis and decision

#### Recommended hybrid: Alpaca + Massive + IBKR

**Alpaca for SPY and QQQ historical research.** Alpaca documents minute equity
history since 2016. Its free live feed is IEX-only, but consolidated SIP history
older than the most recent 15 minutes is available for offline queries. This is
adequate for bulk target-tournament history. The bulk downloader now archives
every page immutably, resumes from verified pages, and materializes two years of
SPY/QQQ research-session bars.

- Plans and coverage: https://docs.alpaca.markets/us/docs/about-market-data-api
- SIP versus IEX behavior: https://docs.alpaca.markets/us/docs/market-data-faq

**Massive Futures Basic for ES and NQ historical research.** As checked on
2026-08-31, the free individual futures tier advertises all CME-group futures
tickers, reference data, minute aggregates, two years of history, and five API
calls per minute. That should provide roughly 500 sessions, comfortably above
the current 100 out-of-sample observation gate. The optional Futures Developer
tier advertises deeper history, but this project has an explicit zero-new-cost
constraint and will not upgrade. The free adapter, raw archive, reference and
schedule captures, exact contract verification, and roll mappings are complete.

- Futures plans: https://massive.com/pricing?product=futures

**IBKR for recent-history validation, live capture, and eventual execution.**
The existing personal account avoids adding another real-time provider. The TWS
API supports historical bars, streaming market data, five-second real-time bars,
and `keepUpToDate` historical bars through TWS or IB Gateway. Relevant market
subscriptions and trading permissions are still required. The market-data-only
adapter is implemented and verified against paper IB Gateway on port 4002.
Recent delayed history works; the live diagnostic confirms that the current
account lacks the real-time API subscriptions needed for SPY, QQQ, ES, and NQ.
No execution integration has been implemented.

- Historical bars: https://ibkrcampus.com/docs/tws-api/doc/market-data-historical/historical-bars/requesting-historical-bars
- API/session operation: https://ibkrcampus.com/docs/third-party-integrations/general-third-party-frequently-asked-questions
- Current subscription pricing: https://www.interactivebrokers.com/en/pricing/market-data-pricing.php
- Historical limitations: https://interactivebrokers.github.io/tws-api/historical_limitations.html

IBKR operational constraints to design around:

- TWS or IB Gateway must be running and authenticated; GUI-less operation is
  not officially supported.
- Automatic restart can maintain the session Monday through Saturday, while a
  weekend reauthentication is normally required.
- A username has one brokerage session at a time. Additional usernames can
  incur duplicate market-data subscription fees.
- Bulk history must use a slow, resumable downloader with bounded concurrency,
  retries, pacing, and immutable per-request checkpoints.
- One-minute-and-larger requests no longer have the old hard pacing limit, but
  soft throttling and disconnection remain possible.
- Expired futures older than two years from expiration are generally
  unavailable. Continuous futures also have request restrictions, so explicit
  contracts and stored roll decisions are preferred.
- IBKR historical trades are filtered differently from an unfiltered live feed;
  volume and VWAP may therefore differ. Cross-source comparisons must account
  for this rather than treating discrepancies as corruption.

#### Other acceptable fallbacks

**FirstRate Data** offers one year of free one-minute SPY and QQQ bars. Its paid
ES/NQ files contain individual contracts plus unadjusted, absolute-adjusted, and
ratio-adjusted continuous series going back to 2008. It is useful for a one-time
deep-history purchase, but it has no live API or revision/first-seen lineage.
If used, the platform should ingest individual contracts and construct its own
explicit roll series.

- Free intraday files: https://firstratedata.com/free-intraday-data
- Example NQ history: https://firstratedata.com/i/futures/NQ

**Sierra Chart Denali** provides real-time and historical CME data at relatively
low non-professional exchange fees and normalizes data into its DTC protocol.
It is a viable futures-only backup if IBKR live data proves unreliable, but it
adds another desktop/service dependency, does not solve equities by itself, and
is more complex to integrate than the current hybrid.

- Denali feed and exchange fees: https://www.sierrachart.com/index.php?page=doc%2FDenaliExchangeDataFeed.php

#### Rejected or limited sources

**Databento:** technically the strongest evaluated source for point-in-time
provenance, but rejected on cost for the current stage. Reconsider only after a
cheap-data tournament shows stable predictive value that warrants buying better
history. It should not be a prerequisite for determining whether the research
hypothesis has any signal.

**Yahoo Chart:** retained only as the completed pipeline-qualification fixture.
Its short intraday retention and missing original first-seen/revision metadata
make it unsuitable for target selection.

**Alpaca live free feed:** IEX-only, so it is not accepted as the production
SPY/QQQ live feed. IBKR will provide live data instead.

**Massive free futures:** accepted for the first historical tournament, but not
as the live source. The free tier is historical and rate-limited.

#### Scientific handling of inexpensive data

These lower-cost aggregate-bar services do not provide Databento-style capture
timestamps and full revision lineage. The project will use the following
explicit compromise without weakening the cutoff rules:

1. Store every raw response immutably before normalization and content-hash it.
2. Record provider, query, retrieval time, timezone, contract identifier,
   corporate-action version, and provider quality classification.
3. Mark backfilled aggregate bars as `event-time-only` rather than pretending
   their original first-seen time is known.
4. Never expose an incomplete current bar to a historical snapshot.
5. Build futures histories from explicit contracts and persist every roll rule
   and mapping; do not silently mix adjusted continuous prices with tradable
   prices.
6. Compare overlapping IBKR and bulk-provider periods and report systematic
   price, volume, session, and missing-bar differences.
7. From the first live day onward, persist IBKR events immediately with the
   platform's own receive/first-seen timestamp. This local archive becomes the
   strongest point-in-time dataset over time.
8. Fail closed to `NO_TRADE` when live data is stale, disconnected, incomplete,
   or outside the expected exchange session.

This means the inexpensive historical tournament can rank candidate targets,
but provenance quality remains an explicit promotion dimension. Strong results
must survive cross-provider validation and later forward capture before they can
support paper or controlled-live trading.

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

**Outcome: complete with `NO_TARGET_ADEQUATE`.** The bulk two-year run passed
sample, coverage, provenance-for-target-selection, liquidity, and all four
cross-provider gates. No candidate passed the material forecast, stability,
incremental economic-value, and stressed-cost gates together.

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

Do not proceed directly to agents or trading. The recommended decision is:

1. Treat all 24 current candidates as rejected and keep the final report sealed.
2. Decide whether there is a small, economically motivated target-search
   extension worth preregistering, such as changing neutral thresholds or adding
   one or two horizons. Record it as a new hypothesis family rather than editing
   the completed Phase 1 result.
3. If no bounded extension is justified, stop this research branch; do not add
   complexity to manufacture signal.
4. If a later extension freezes a target, proceed to `REALITY-STORE-001` and
   then `BASELINE-001` before Pi, Ollama, fixed agents, or evolution.
5. Keep the zero-new-cost constraint. Do not purchase deeper futures history or
   IBKR real-time subscriptions.

---

## 8. Next-session startup checklist

Run:

```bash
git status --short
npm run check
npm run db:status
npm run foundation
npm run phase1 -- --offline
```

If Docker is stopped:

```bash
npm run db:up
npm run check:db
```

The database is currently stopped; starting it is only necessary for database
integration work. It is not required for the next historical-provider
increment.

Read these files first:

```text
docs/PROJECT_PLAN_AND_STATUS.md
docs/FOUNDATION-001.md
docs/TARGET-TOURNAMENT-001.md
docs/IBKR_SETUP.md
README.md
config/foundation.json
config/target-tournament.json
config/phase1.json
config/ibkr-contracts.json
config/ibkr-history.json
config/ibkr-live.json
apps/cli/src/foundation.ts
apps/cli/src/alpaca-check.ts
apps/cli/src/ibkr-*.ts
packages/domain/src/*
packages/data-providers/src/provider.ts
packages/snapshot-engine/src/*
python/src/spy_predictor_quant/ibkr_*.py
python/src/spy_predictor_quant/market_archive.py
python/src/spy_predictor_quant/market_comparison.py
python/src/spy_predictor_quant/phase1_*.py
migrations/001_foundation.sql
```

Immediate next task: review the completed `NO_TARGET_ADEQUATE` report and decide
whether to preregister a bounded target-search extension. Do not enable IBKR
order submission and do not begin Pi, Ollama, agents, or evolution.

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
complete the qualifying bulk dataset
→ rerun and close TARGET-TOURNAMENT-001
→ freeze a target or explicitly reject the current candidates
→ complete the Reality Store
→ complete the quantitative benchmark
→ test fixed agent incremental value
→ only then introduce evolution
```
