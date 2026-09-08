# Agentic Evolutionary Market Prediction Platform

## Project plan, implementation status, and next-session handoff

**Status date:** 2026-09-07
**Repository:** `spy_predictor`
**Current milestone:** `CYCLE-ASYMMETRY-001` pre-evaluation repair. Acquisition
and reproduction completed, but v4 is suspended for evaluation: cash
publication coverage and selection feasibility failed deeper review.
**Latest completed work:** preregistration v4 and source audit v3, immutable
MPRIME-minus-GS3M credit-spread vintages, inception-length IBKR-plus-sponsor
ETF histories, exact XNYS cutoffs, targets, trailing-only features and states,
resolved sealed partitions, a fail-closed dataset runner, exploratory cycle
tools, and two execution-verified explanatory notebooks
**Immediate next task:** resolve cash-source and evaluation-contract
prerequisites in [CYCLE1_REPAIR.md](CYCLE1_REPAIR.md), then issue a versioned
amendment and rebuild. Do not begin increment 5 or open confirmation output.

### 2026-09-07 repair authority — supersedes the earlier handoff

Cash accrual now respects vintage publication at each holding-period start;
the spread change uses exactly three observation months; dataset construction
checks mature training labels and consecutive calendar partitions. Candidate
evaluation under v4 is explicitly suspended.

`npm run cycle1:preflight` produces a deterministic metadata-only audit (exit
code 2 means blocked). SPY has 68 selection forecasts under archived eligibility,
but only one after removing starts without published DGS3MO. QQQ has zero
selection forecasts with 120 matured labels. The earliest pinned DGS3MO
publication is 2005-06-28; older observations are not earlier publication evidence.

The repaired offline dataset build deliberately fails on cash publication
coverage. Existing archives and dataset identities are preserved historical
artifacts, **not evaluation-approved inputs**. No replacement dataset is
qualified. Zero candidate evaluations and no confirmation metrics have been
opened. Earlier completion tables and work orders below describe pre-repair
status and are superseded wherever they conflict with this section. Full
findings, proposed contract, and remaining work are in
[CYCLE1_REPAIR.md](CYCLE1_REPAIR.md).

The date-only alternative audit now establishes the concrete unblock: GS3M
has publication-admissible coverage for every model-eligible start, SPY retains
68 selection forecasts, and QQQ has 126 mature selection labels at the first
confirmation cutoff. The next amendment will use GS3M, make SPY the development
track, and make QQQ a non-promotable external transfer check. The remaining
blocker is the exact evaluation contract and its synthetic whole-procedure
power audit, not source acquisition.

### Current worktree continuation note

The validated active authority remains `config/cycle1.json` (v4), with its
matching schema and `config/cycle1-source-audit-v3.json`. Proposed v5 changes
are preserved separately in `config/cycle1-v5-draft.json`; they are not yet a
valid runnable authority. `config/cycle1-v4.json` and
`schemas/cycle1-config-v4.schema.json` are retained as explicit v4 archives.
Do not run candidate evaluation against the v5 draft until its schema,
semantic loader, source audit, dataset identity, and power-audit gate are
implemented and tested.

Repair implementation files are `python/src/spy_predictor_quant/cycle1_targets.py`,
`cycle1_features.py`, and `cycle1_feasibility.py`; tests include
`python/tests/test_cycle1_feasibility.py` and the expanded target/feature tests.
Run the metadata-only audit with:

```bash
npm run cycle1:preflight
```

Expected result for the preserved v4 archive is exit code 2 with
`V5_AMENDMENT_NOT_YET_FROZEN`, `EVALUATION_CONTRACT_INCOMPLETE`, and
`ARCHIVED_SPREAD_LAG_REQUIRES_REBUILD`. Candidate and confirmation metrics
remain unopened. The latest deterministic audit is
`docs/audits/cycle1-repair-352a046a5c12b63e.json`.

Before continuing, run `git status --short` and `npm run check`. Preserve the
existing uncommitted work and ignored raw archives. Finish the v5 schema/loader
and source-audit amendment, then run the synthetic power audit. Only after
those pass should the monthly dataset be rebuilt and model code begin.

### Executive status audit

This table compares the original phase acceptance criteria with code, tests,
generated artifacts, and integration runs present as of the status date.
Overall: two of thirteen original phases are complete, one bounded Phase 1B
extension is active, three phases have partial/scaffold work, and eight have not
started.

| Phase | Status | What exists now | What is still required |
|---|---|---|---|
| 0 — `FOUNDATION-001` | **Complete** | Reproducible experiment identity, point-in-time guards, snapshots/targets, purged partitions, resumable filesystem/PostgreSQL persistence, schemas, Parquet/DuckDB materialization, CI, and a provider-neutral runtime interface | No Phase 0 acceptance item remains; keep the foundation green while extending it |
| 1 — `TARGET-TOURNAMENT-001` | **Complete — no target frozen** | Immutable Alpaca SPY/QQQ plus Massive ES/NQ minute data, 18 verified futures contracts, explicit rolls, 779,985 normalized bars, four passing IBKR comparisons, 24 candidate evaluations, and 100 sealed confirmation observations each | No acceptance item remains. The result is `NO_TARGET_ADEQUATE`; any wider target search must be a new preregistered hypothesis set |
| 1B — `CYCLE-ASYMMETRY-001` | **Active — increments 1–4 complete; dataset qualified** | Frozen ten-candidate preregistration v4, immutable source audit v3, inception-length IBKR-plus-sponsor data, point-in-time MPRIME-minus-GS3M credit spread, three-track dataset, 100% core-feature coverage, exact sealed partitions, targets, states, schemas, tests, safe runner, analysis tools, and two notebooks | Implement the five frozen models per instrument and hypothesis ledger; run selection-only development, then purged walk-forward and the one-time sealed confirmation; issue `FREEZE_CYCLE_TARGET` or `NO_CYCLE_TARGET_ADEQUATE` |
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
without a target. The approved next path is:

```text
preserve TARGET-TOURNAMENT-001 and its NO_TARGET_ADEQUATE result unchanged
→ preregister CYCLE-ASYMMETRY-001 before inspecting candidate outputs
→ build the minimal point-in-time monthly SPY/QQQ cycle dataset
→ test the frozen SPY and QQQ candidates and issue one immutable decision
→ if all fail: stop or explicitly design a new hypothesis family
→ only if one target is frozen: build the broader point-in-time Reality Store
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

### Next-session handoff: CYCLE-ASYMMETRY-001 (Phase 1B)

**Status:** increments 1–4 and the safe dataset runner are complete and tested.
The final online acquisition and offline reproduction both passed. No candidate
model has been run, no confirmation output has been opened, and the hypothesis
counter remains zero. This section is the next-session authority.

#### 2026-09-07 final v4/v3 dataset qualification

The first complete source composition exposed an honest scientific
incompatibility: ALFRED's first `NFCI` vintage is 2011-05-25. After the frozen
24-month percentile warm-up, NFCI produced features only from April 2013 and
left 147 complete feature/12-month-target rows, below the immutable 228-row
minimum. The gate failed before any candidate output.

Moody's `BAA` was reconsidered but remains prohibited: its source restriction
is incompatible with persistent immutable storage. Preregistration v4 therefore
replaces only the two NFCI-derived core features with the Federal Reserve H.15
bank-prime-minus-three-month-Treasury spread:

```text
credit spread level:      MPRIME_t - GS3M_t
credit spread change 3m:  spread_t - spread_t-3m
alignment:                latest common observation month for which both
                          ALFRED vintages were published by the cutoff
```

Both series have ALFRED vintages beginning 1996-12-03. Higher spread is signed
as higher stress; a widening spread is signed as weaker direction. NFCI remains
diagnostic-only in the hash-linked v2 archive and is neither reacquired nor
consumed by the v4 core dataset. Targets, state rules, other features, models,
partitions, gates, thresholds, seed 42, no-HMM rule, and the exact five-model by
two-instrument budget did not change. No candidate result existed before the
v4 amendment.

Frozen identities:

```text
preregistration:  cycle1-preregistration-v4
config hash:      887ab9410f79e7fd2884af731c029d81ba2f0d57d4d3c3e22b9bb68671bfdbc8
source audit:     cycle1-source-audit-v3
audit hash:       80a80d252c65abe9b13a8533e6d5ad23d65e68e3df993ab2734594c5ab8f3a90
dataset version:  cycle1-monthly-19ccd95384e690de
dataset hash:     19ccd95384e690dee2fd529c3889a5b1ce17d956f8b9a1efffe551ec73e87753
hypotheses run:   0
```

Final manifest:

```text
datasets/cycle1/cycle1-monthly-19ccd95384e690de/manifest.json
```

The preceding `cycle1-monthly-905652bac5f970d7` directory is an intermediate
pre-partition-manifest identity and is not the evaluation input. Use only the
final `19ccd95384e690de` dataset above.

Source results:

- Shiller: 1,833 reconstructed discovery months, 1871-01 through 2023-09.
- FRED/ALFRED core: DGS3MO 11,749 intervals; CPIAUCSL 3,361; INDPRO
  39,356; MPRIME 936; GS3M 540. The configured FRED key and all endpoints
  worked. No current FRED outage exists.
- IBKR paper/read-only: 8,456 SPY sessions and 6,916 real QQQ sessions from
  inception through 2026-09-04. One QQQ row dated 2005-02-21 was an IBKR
  zero-volume, zero-trade, flat-OHLC holiday placeholder; raw bytes remain
  pinned, while normalization excludes only that exact class of non-session
  placeholder and fails on any non-session activity.
- State Street: 135 exact SPY cash distributions, 1993-03-19 through
  2026-06-18.
- Invesco: 88 exact QQQ distributions, 2003-12-24 through 2026-06-22,
  including 2004-12-17 and 2005-06-17. The browser-saved source and immutable
  copy both hash to
  `dbe9351a005efbc97387a767b3cfd31a93f22cc703974b7172097e2ed2d4c938`.
  The importer accepts Invesco's literal `--` empty-value representation.
- Invesco automated access still returns HTTP 406; the supplied one-time
  browser snapshot resolves that limitation. Tiingo Starter and Moody's BAA
  remain excluded for storage-license reasons. No external service currently
  blocks the next phase.

Validation coverage and sealed partitions are recorded in each track manifest:

| Track | Features | Coverage | Eligible labels | Selection | Embargo | Sealed confirmation |
|---|---:|---:|---:|---|---|---|
| SPY | 322 | 100% | 308 (`1999-11-30`–`2025-07-31`) | 200 (`1999-11-30`–`2016-06-30`) | 12 (`2016-07-29`–`2017-06-30`) | 96 (`2017-07-31`–`2025-07-31`) |
| QQQ | 248 | 100% | 234 (`2006-01-31`–`2025-07-31`) | 126 (`2006-01-31`–`2016-06-30`) | 12 (`2016-07-29`–`2017-06-30`) | 96 (`2017-07-31`–`2025-07-31`) |

Each confirmation block is mechanically split into two 48-month halves:
2017-07-31 through 2021-06-30 and 2021-07-30 through 2025-07-31.

Both commands completed with the identical dataset and track identities:

```bash
npm run cycle1 -- --dataset-only
npm run cycle1 -- --dataset-only --offline
```

The exact scheduled XNYS close is used for every cutoff, including early
closes. Incomplete trailing months are excluded; completed months missing their
final session fail closed. Resolved partitions are part of the dataset identity,
so changing them creates a new dataset instead of overwriting this one.

Reusable manual-analysis tools remain in
`python/src/spy_predictor_quant/cycle_analysis_tools.py`, separately from the
frozen candidate set. The two notebooks under `notebooks/` cover structural
trend, log-price deviation, expectations, credit/risk feedback, deterministic
and optional latent states, nested cycles, top score, and defensive/aggressive
exposure. An HMM is illustrative notebook material only and is prohibited from
the first Cycle 1 evaluation.

#### Exact next-session work order

1. Read this handoff, `docs/CYCLE-ASYMMETRY-001.md`, `config/cycle1.json`,
   `config/cycle1-source-audit-v3.json`, and the final dataset manifest.
2. Run `git status --short` and `npm run check`; preserve the current uncommitted
   work and ignored raw archives. Do not clean or overwrite them.
3. Implement increment 5 only: unconditional-history, valuation-only,
   direction-only, fixed-cycle-score tertile, and regularized-cycle models for
   SPY and QQQ. Do not add variants, tune hyperparameters, or add an HMM.
4. Create an immutable hypothesis ledger containing exactly ten primary entries
   before producing candidate metrics.
5. Implement fold-local preprocessing and target-aware eligibility using the
   resolved partitions. Develop and debug on the selection partition only.
6. Implement both expanding and rolling walk-forward modes, purge/embargo,
   CRPS and drawdown metrics, dependence-aware bootstrap, calibration,
   monotonicity, era/stability, concentration, multiple-testing, and policy
   gates exactly as frozen.
7. Add an explicit one-time confirmation-opening guard. Do not inspect the
   2017-07-31 through 2025-07-31 confirmation metrics while implementing or
   debugging selection evaluation.
8. Only after tests and selection-only artifacts are complete, open the sealed
   confirmation once, write one immutable report, and issue either
   `FREEZE_CYCLE_TARGET` or `NO_CYCLE_TARGET_ADEQUATE`.

Bare `npm run cycle1` must continue to fail closed until the complete candidate
evaluation/report layer and its guards exist. No order, account-query, agent,
LLM, leverage, or paper/live execution code belongs in this phase.

#### Why this extension exists

`TARGET-TOURNAMENT-001` tested whether recent market-price behavior could
support calibrated directional forecasts over minutes, overnight, or one
trading session. It found no defensible predictive and economic edge. That
negative result remains final and must not be edited or reinterpreted as a
partial success.

The proposed extension asks a different question:

> At a monthly point-in-time cutoff, do valuation, credit/risk conditions,
> macro conditions, market stress, and technical direction materially alter
> the distribution of SPY or QQQ real excess returns and drawdown risk over the
> following 12 months?

This is not an attempt to rescue an intraday result by adding features. It is a
new, economically motivated hypothesis family with different observations,
targets, horizons, data, baselines, and gates. A market may be unpredictable
tomorrow while still offering different medium-term return distributions after
extreme valuation, stress, or recovery conditions.

#### Intellectual origin and attribution boundary

The design is inspired by the user's synthesis of Howard Marks's public cycle
framework and public descriptions of Mariela Capezzuoli's ("Maru Cape")
cyclical approach. In this document the combined idea is called a
**multivariable contracyclical investment model** or **cycle-asymmetry model**.

The public conceptual material does not provide a complete mathematical
formula, fixed weights, thresholds, or a reproducible algorithm attributable to
Maru Cape. Therefore this project must:

- describe the implementation as an independent quantitative formalization
  inspired by those concepts, not as Maru Cape's proprietary or exact model;
- never invent weights or rules and attribute them to her;
- cite the original public sources if a later research report discusses the
  intellectual history;
- freeze every implemented transform, sign, weight, state rule, and threshold
  as this project's own preregistered specification.

#### Conceptual model to preserve

The foundational proposition is that a market cycle is not a clock or a fixed
periodic function:

```text
cycle != periodic_function(time)
cycle = nonlinear feedback among fundamentals, expectations, credit,
        risk tolerance, prices, leverage, and subsequent corrections
```

A favorable causal sequence can create its own future fragility:

```text
good results
→ optimism
→ easier credit and greater risk tolerance
→ investment, leverage, and rising prices
→ extrapolation and overpricing
→ low margin of safety and latent fragility
→ disappointment or constraint
→ selling, tighter credit, fear, and falling prices
→ underpricing and improved future asymmetry
→ recovery
```

The mechanism is **excess followed by correction**, not a recession or market
turn that must occur every fixed number of years.

Psychology is part of the state, not independent noise. Markets can move
between fear and greed, skepticism and credulity, risk aversion and risk
tolerance, forced selling and urgency to buy. Price changes reinforce the
narrative that produced them:

```text
price rises → optimism / narrative confirmation → FOMO / buying → price rises
price falls → perceived risk / fear → selling / withdrawal → price falls
```

That feedback can invert the ordinary demand response: higher financial-asset
prices sometimes attract rather than repel demand. Consequently perceived risk
and actual forward risk can diverge:

```text
low perceived risk + high price + low margin of safety
    may imply high future downside risk

high perceived risk + forced selling + low price
    may imply favorable future return asymmetry
```

Neither statement is unconditional. A cheap asset can have permanent
fundamental impairment, and an expensive asset can keep rising for a long time.
The method estimates an asymmetry or probability distribution; it does not know
the date of the next reversal.

The central investment question is therefore not merely whether the economy or
company is good. It is:

> How does price compare with normalized fundamentals and with the expectations
> already embedded in that price?

Excellent news can be a poor investment setup when perfection is already
priced. Terrible news can be a favorable setup when the price discounts an even
worse future, provided the asset remains viable.

#### Structural trend, excess, and normalization

The qualitative idea of a long-run structural mean can be represented as:

```text
log(real_price[t]) = structural_trend[t] + cyclical_deviation[t] + noise[t]
```

Large negative deviations may identify crisis or undervaluation; values near
the trend may be reasonable; large positive deviations may indicate greed or
euphoria. This is only an operational hypothesis. A structural trend is not
known truth and may shift because of productivity, inflation, tax, monetary,
market-composition, accounting, or institutional changes.

The implementation must never estimate the trend on the complete sample. At
each timestamp `t`, the regression, smoother, scale, percentile, or other
normalizer may see only data known by `t`. Full-sample detrending would leak
future information and make old extremes look artificially obvious.

The preregistration must select at most a very small number of trailing-only
definitions, such as a robust trailing log-real-price trend standardized by a
trailing median absolute deviation and an expanding or trailing historical
percentile. Every alternative counts as a separate hypothesis. The project may
not try many windows and retain the one with the best historical story.

#### Cycles within cycles

The framework permits a long structural or "mega" cycle to contain smaller
rallies, corrections, and recoveries:

```text
structural cycle
├── minor cycle: rally → correction → recovery
├── minor cycle: rally → correction → recovery
└── late-cycle excess → major correction or regime change
```

A correction does not by itself prove the end of a secular trend. Conversely,
a renewed rally does not prove that valuation risk disappeared. Phase 1B will
not attempt to fit simultaneous short, medium, and mega-cycle turning points.
Its initial scope is one monthly decision frequency and a 12-month primary
horizon. Longer-horizon output is diagnostic only.

#### Valuation is not timing

The method explicitly separates cheapness from entry confirmation:

```text
cheap != immediate bottom
cheap + extreme stress + continuing deterioration != confirmed recovery
cheap + improving direction / easing stress = stronger recovery evidence
```

Prices may fall substantially after first becoming cheap. Technical direction
is therefore used in context rather than as a standalone `RSI < 30` rule.
Macro/credit/valuation estimate location and risk temperature; trend helps
distinguish deterioration from recovery.

The eventual policy vocabulary is **more aggressive versus more defensive**,
not **all-in versus all-out**. No-stop-loss language must never be interpreted
as no risk management. Position sizing, diversification, fundamental viability,
and maximum-risk constraints would remain mandatory in later phases.

Phase 1B itself predicts outcomes and evaluates a simple research policy only
after predictive gates pass. It does not submit orders, recommend leverage, or
authorize live trading.

#### Credit as an amplifier

Credit is included because successful, low-default periods can reduce risk
aversion, compress spreads, weaken underwriting, and increase leverage. Those
actions manufacture later fragility. After failures, the reverse process can
produce tighter standards and better prospective pricing:

```text
success → confidence → risk taking → leverage / fragility → failure
failure → fear → risk avoidance → tighter credit / better pricing
        → improved future opportunity
```

This is a feedback hypothesis, not proof that a particular spread causes equity
returns. Price, credit, macro data, and expectations are endogenous. Reports
must use predictive language and must not convert correlation into a causal
claim.

#### Translation from the Argentina-specific formulation to US markets

The Argentina examples motivate the architecture but cannot be copied
literally. Phase 1B uses US-market analogues:

| Argentina-oriented concept | US Phase 1B analogue | Caveat |
|---|---|---|
| Merval in real CCL dollars | Real S&P composite/total-return history for discovery; actual SPY and QQQ adjusted returns for modern validation | A reconstructed historical S&P composite is not identical to SPY; QQQ has a much shorter live history |
| Country risk | Corporate-credit spread and broad financial-conditions measures | These are correlated risk-temperature proxies, not direct causal variables |
| GDP/activity growth | Point-in-time industrial production and a minimal preregistered growth indicator | Use original release vintages and publication lags, not revised history |
| Real exchange-rate/peso strength | US real-rate, curve, dollar, or liquidity measures only if a no-cost, long, point-in-time source passes the audit | Do not add variables merely because they improve the backtest |
| Historical P/B or local valuation | S&P CAPE/earnings yield and instrument-specific valuation only when provenance is adequate | S&P CAPE is not QQQ-specific valuation and must not be mislabeled as such |
| Fear/euphoria | Credit stress, financial conditions, volatility, drawdown, and price-derived momentum | VIX history is shorter than the price history |
| Technical trend | Six-/twelve-month momentum and price versus a preregistered long trend | Technical evidence confirms direction; it does not define value |

#### Research instruments and the SPY/QQQ distinction

Both SPY and QQQ must receive the same target-level analysis, report structure,
walk-forward protocol, economic-cost treatment, and pass/fail discipline. They
must not be pooled as if their monthly observations were independent.

**SPY track:** SPY is the primary tradable expression. The long-run S&P
composite can support discovery of valuation relationships across many decades;
actual SPY history must validate whether those relationships transfer to the
ETF. The full model may use S&P valuation inputs, with their provenance and
reconstruction limitations explicitly reported.

**QQQ track:** QQQ is a full secondary instrument candidate, not an ignored
appendix. It receives QQQ-specific real returns, structural-price deviation,
momentum, realized volatility, drawdown targets, costs, metrics, state outcomes,
and an independent eligibility decision. It may share macro, credit, and broad
US risk-temperature inputs with SPY.

QQQ's shorter live history contains far fewer independent major cycles.
Consistent, no-cost, point-in-time Nasdaq-100 valuation history may also be
unavailable. Therefore:

- S&P CAPE may be used only as a broad-market temperature input for QQQ and
  must never be described as QQQ valuation;
- a QQQ-specific valuation feature is included only if the source audit finds
  a reproducible, legally usable, point-in-time or honestly reconstructed
  series with adequate coverage;
- missing QQQ valuation must not be silently filled by present-day constituent
  fundamentals or a survivorship-biased reconstruction;
- SPY-selected weights and thresholds may be applied to QQQ as an external
  transfer test without QQQ retuning;
- any QQQ-specific fitted model is a separately counted candidate and must pass
  its own coverage, sample, stability, and sealed-confirmation gates;
- a strong SPY result cannot promote QQQ, and a strong QQQ result cannot promote
  SPY.

The final report can freeze either instrument, both exact independently
qualified targets, or neither. It must not select whichever instrument happened
to have the prettier full-history curve.

#### Frozen target family to preregister

The next session must turn the following recommendation into a versioned schema
and configuration before computing results:

```text
decision frequency: monthly
snapshot cutoff:     after the final US equity session close of each month
                     using only records released/known by that cutoff
primary horizon:     12-month forward real total return in excess of the
                     contemporaneously observable 3-month Treasury-bill return
secondary target:    maximum drawdown during the following 12 months
diagnostic horizon:  24-month forward real excess return
instruments:         SPY and QQQ, evaluated separately
```

The exact return endpoints, dividend treatment, CPI lag, Treasury compounding,
next-tradable-price rule, and behavior when the endpoint is not a trading day
must be frozen. Predictive evaluation and any economic policy simulation must
remain separate. If a signal is finalized after a month-end close, a policy
cannot pretend it transacted at that already-observed close; the economic
simulation must trade no earlier than its preregistered next executable price.

The 24-month target is diagnostic only in the initial run because its overlapping
labels sharply reduce effective sample size. It cannot rescue failure of the
12-month primary target.

#### Defensible cycle representation

Do not begin with a six-state Hidden Markov Model. With few independent cycles,
an unconstrained HMM can create attractive state histories whose labels and
transition probabilities are unstable outside the sample.

Start with three transparent dimensions:

```text
CycleState[t] = f(Valuation[t], Stress[t], Direction[t])
```

1. **Valuation / structural position**
   - CAPE or earnings-yield historical percentile for the S&P track.
   - Real price deviation from a trailing-only structural trend.
   - QQQ-specific valuation only if it passes the source/provenance audit.

2. **Stress / risk temperature**
   - A long-lived corporate-credit spread.
   - A Federal Reserve financial-conditions measure where available.
   - Realized volatility and VIX where available.
   - Drawdown from the trailing market high.

3. **Direction / confirmation**
   - Six- and twelve-month momentum.
   - Price relative to a preregistered long moving average or trailing trend.
   - Credit stress rising or falling.
   - Point-in-time industrial production accelerating or deteriorating.

Each component must have an economic sign fixed in advance. Scaling must use
only expanding or trailing data. The primary composite should use simple fixed
or equal weights within each dimension; optimized weights belong only to a
regularized challenger and count as additional model selection.

Descriptive states can then be assigned by frozen observable rules:

| State | Approximate observable evidence |
|---|---|
| `EUPHORIA` | Expensive, easy credit, low stress, strong positive direction |
| `CORRECTION` | Expensive or formerly expensive, direction deteriorating, stress rising |
| `CRISIS` | Cheap, high stress, weak direction |
| `EARLY_RECOVERY` | Cheap, stress declining, direction improving |
| `NORMAL` | No valuation/stress extreme and mixed or ordinary direction |
| `GREED` | Expensive and positively trending, but below the preregistered euphoria extreme |

These names are deterministic descriptions of current observables. Never hand
label 2000, 2008, 2020, or any other famous episode and train a model to
rediscover those labels.

A small two- or three-state HMM may be a challenger only if its feature set,
state-count choices, fitting rules, label-mapping rule, seed handling, and
promotion eligibility are preregistered before confirmation. It must beat the
transparent fixed-score model, not merely draw a plausible historical chart.

#### Minimal candidate budget

The first run should remain deliberately small. Recommended promotion-eligible
models per instrument are:

```text
1. unconditional historical distribution
2. structural-position / valuation-only baseline
3. direction / momentum-only baseline
4. fixed-weight transparent cycle score
5. regularized statistical cycle challenger
```

This produces ten primary instrument/model evaluations for the 12-month target
before any optional HMM. The secondary drawdown output accompanies the same
monthly forecasts; the 24-month result is diagnostic. If an HMM is included,
it increases the hypothesis count and must be present in the initial config.

Do not add dozens of indicator windows, technical oscillators, state counts, or
weight grids. Every variation counts in the hypothesis ledger and the
multiple-testing correction.

#### Zero-paid-data source plan

No new paid subscription is authorized for Phase 1B. Candidate no-cost sources
and their roles are:

| Source | Intended role | Required handling |
|---|---|---|
| Robert Shiller, Yale, US Stock Markets 1871-present and CAPE | Long-run monthly S&P price, dividends, earnings, CPI, valuation discovery | Archive exact raw bytes and source metadata; document that reconstructed/composite history is not identical to SPY and audit whether observations are monthly averages or endpoints before defining targets |
| FRED/ALFRED | Macro, Treasury, credit/financial conditions, release and revision vintages | A free API account/key may be required; persist real-time/vintage fields, release dates, revisions, raw responses, terms, and attribution |
| Existing Alpaca account | Modern actual SPY/QQQ adjusted/daily validation subject to the account's available history | Reuse the provider boundary and immutable-page/hash design; audit adjustment semantics and daily coverage rather than assuming the minute plan applies unchanged |
| Existing IBKR account | Limited recent cross-provider checks only | Market-data/read-only mode; no orders and no paid real-time entitlement |
| Public issuer/exchange source, only if found in the audit | Possible QQQ-specific valuation or total-return validation | Exclude if history, licensing, constituent methodology, or point-in-time provenance is inadequate |

Reference starting points:

- Shiller data: https://www.econ.yale.edu/~shiller/data.htm
- FRED/ALFRED API: https://fred.stlouisfed.org/docs/api/fred/overview.html
- ALFRED archive behavior: https://fred.stlouisfed.org/docs/api/fred/alfred.html
- FRED terms: https://fred.stlouisfed.org/legal/
- Alpaca plan/history documentation:
  https://docs.alpaca.markets/us/docs/about-market-data-api

The ICE BofA high-yield OAS series must not be a core long-history dependency;
FRED currently indicates that it exposes only a short recent window. Prefer a
longer-lived Baa-versus-Treasury spread or a Federal Reserve financial-conditions
measure, subject to a series-level license and availability audit. Do not assume
that because a series is visible through FRED it can be redistributed without
restriction.

Massive futures data are not required for this experiment. The completed Phase
1 Massive archive remains immutable but should not be expanded for Phase 1B.

#### Point-in-time and provenance rules

The monthly dataset needs two evidence tiers:

1. **Point-in-time admissible:** the exact value and release/revision record
   known by the historical snapshot cutoff can be reconstructed, normally
   through ALFRED or an equivalent release archive.
2. **Reconstructed research-only:** a present-day historical series is used
   because original vintages are unavailable. It is clearly flagged and cannot
   silently support a strong replay-safe claim.

For every observation persist, where applicable:

```text
observation/effective date
publication/release timestamp
first-seen or vintage interval
revision identifier
local ingestion timestamp
source request and response hash
availability and quality flags
```

Macro values enter a snapshot only after publication. Later revisions never
replace the value that would have been known at an earlier cutoff. Slow-moving
earnings/CAPE inputs need their own availability assumptions; a month printed
on a spreadsheet is not automatically its historical publication timestamp.

If long-run valuation data cannot be made point-in-time safe, the first report
must separate exploratory reconstructed-history evidence from a stricter modern
vintage-aware confirmation. It must not blend the two and call the result fully
replay safe.

#### Evaluation design

Monthly rows are not independent when labels cover the next 12 or 24 months.
A dataset with hundreds of overlapping monthly labels may contain only dozens
of effectively independent annual outcomes and few major cycles. Report both
the row count and an effective non-overlapping block count.

Required evaluation behavior:

- chronological expanding and rolling walk-forward modes;
- a purge/embargo at least as long as the primary target overlap, and long
  enough for any promotion-eligible 24-month target if that policy changes;
- no random train/test split;
- all preprocessing fitted inside each training fold;
- block bootstrap or another dependence-aware uncertainty estimate;
- a sealed final chronological confirmation segment whose minimum calendar
  span and labeled observations are frozen after the source-coverage audit;
- metrics by instrument, era, cycle state, and both confirmation halves;
- concentration reporting so one famous crash/recovery cannot dominate the
  claimed edge;
- missing-feature and coverage reports for every candidate;
- explicit hypothesis count and multiple-testing adjustment.

Because the project team already knows the broad history of famous US crises,
the historical holdout can be mechanically sealed from model output but is not
honestly a human-unknown market history. The report must disclose this. The
strongest evidence for a later positive claim would be forward data accumulated
after the specification is frozen. Phase 1B may still reject a candidate using
historical evidence; it must be more conservative about claiming discovery.

#### What the cycle model must beat

A complicated cycle model is useful only if it improves on all relevant simple
alternatives:

- the unconditional historical return/drawdown distribution;
- valuation or structural deviation alone;
- momentum/direction alone;
- a simple valuation-plus-trend rule;
- for economic evaluation, a static risk-matched allocation after transaction
  costs, not merely an unmatched all-equity or all-cash comparison.

The preregistration must choose continuous-return metrics and a probabilistic
drawdown definition before results. Expected candidates include MAE/RMSE or a
proper distributional score for forward real excess return, and Brier/log loss,
calibration, and discrimination for a frozen drawdown event threshold.

Promotion must require, at minimum:

- material out-of-sample predictive improvement over the required baselines;
- calibrated drawdown probabilities if the drawdown output is used;
- sensible monotonic or otherwise preregistered ordering across cycle-score
  groups;
- stability across expanding and rolling modes, predeclared eras, and both
  confirmation halves;
- no dependence on a single crash, rebound, or decade;
- a dependence-aware uncertainty interval supporting the claimed improvement;
- adequate source coverage and effective independent blocks;
- after costs, improved return/drawdown trade-off for any derived policy versus
  a risk-matched static allocation;
- low enough turnover for a monthly regime policy;
- no threshold or feature changes after confirmation metrics are opened.

Numeric thresholds are intentionally not invented in this handoff. They must be
justified, encoded, reviewed, and committed during preregistration before the
candidate-output command is allowed to run.

#### Prediction before exposure policy

The first scientific product is a forecast, for example:

```text
expected 12-month real excess return
return prediction interval or distribution quantiles
probability of the frozen 12-month drawdown event
valuation, stress, and direction component scores
deterministic descriptive cycle state
data quality and confidence flags
```

Only after predictive gates pass may the experiment evaluate a deliberately
simple long/cash aggressive-to-defensive policy. The cash return must use the
same observable Treasury series as the excess-return target. The simulation
must be executable with a defined one-session lag, costs, no hidden leverage,
and risk-matched static baselines.

An attractive policy backtest cannot compensate for a failed or uncalibrated
forecast. Policy, instrument expression, and execution remain later layers.

#### Phase 1B implementation plan

1. **Preregister the hypothesis — complete (v4).**
   - Create `docs/CYCLE-ASYMMETRY-001.md`.
   - Create a versioned config and JSON Schema.
   - Freeze SPY/QQQ roles, exact monthly cutoff, target formulas, adjustment and
     CPI rules, feature signs/windows, models, seeds, partitions, embargo,
     metrics, numeric gates, hypothesis budget, and final decision vocabulary.
   - Add a guard that refuses candidate evaluation when required preregistration
     fields or numeric gates are missing.

2. **Audit and pin the no-cost sources — complete (audit v3).**
   - Confirm exact Shiller field semantics and update/release behavior.
   - Inventory required FRED/ALFRED series, start dates, revisions, licenses,
     release lags, and vintage coverage.
   - Determine the longest honest actual-SPY and actual-QQQ history obtainable
     from existing no-cost accounts/sources.
   - Decide before modeling which rows are point-in-time admissible versus
     reconstructed research-only.
   - Do not add a paid source to repair a coverage failure.

3. **Build the immutable monthly dataset — complete and reproduced offline.**
   - Implement resumable raw downloads with request identity, response hashes,
     and offline verification.
   - Normalize calendars, CPI/real returns, dividends, rates, macro vintages,
     and missingness without overwriting raw records.
   - Produce separate long-run S&P discovery, actual-SPY validation, and
     actual-QQQ validation manifests.
   - Emit source-level and feature-level coverage/quality reports.

4. **Calculate trailing-only features and states — complete.**
   - Fit trend, scaling, percentiles, imputation, and any regularization only on
     information available at each cutoff and inside each fold.
   - Emit valuation, stress, and direction components independently.
   - Apply the frozen deterministic state rules.
   - Add tests proving future observations and revisions cannot affect an old
     feature vector or state.

5. **Build the minimal baselines and challengers — next.**
   - Implement the unconditional, valuation-only, direction-only, fixed-cycle,
     and regularized challenger models for both instruments.
   - Apply SPY-frozen parameters to QQQ as a transfer test where specified.
   - Include an HMM only if it was already preregistered; otherwise defer it.
   - Record every candidate and variation in the hypothesis ledger.

6. **Run purged walk-forward evaluation — pending increment 5.**
   - Use rolling and expanding modes with the frozen embargo.
   - Produce continuous-return, drawdown, calibration, regime/era, coverage,
     concentration, and uncertainty metrics.
   - Report overlapping monthly rows and non-overlapping effective blocks.
   - Run prediction metrics before constructing any policy result.

7. **Open the sealed confirmation once — pending and still sealed.**
   - Require the configured minimum span, labeled observations, effective
     blocks, and coverage for SPY and QQQ independently.
   - Do not change features, models, weights, thresholds, or gates after opening
     aggregate confirmation output.
   - If a defect requires a scientific-policy change, invalidate that
     confirmation use, document it, and require a new unseen/forward block for
     any later positive claim.

8. **Issue one immutable report and decision — pending confirmation.**
   - Report every SPY and QQQ candidate, gate, failure reason, source caveat,
     and hypothesis count.
   - Freeze only the exact instrument/target/model/config that passes all gates.
   - Otherwise emit `NO_CYCLE_TARGET_ADEQUATE` and stop rather than adding
     complexity.
   - Keep LLM calls, agents, account queries, order construction, and order
     submission out of the Phase 1B path.

Target operational interface after implementation:

```bash
npm run cycle1
npm run cycle1 -- --offline
```

One command should ultimately build or resume the immutable dataset and run the
complete evaluation; the offline form should reproduce all dataset/report
identities from the same pinned raw bytes. The safe runner currently supports
the acquisition stage explicitly:

```bash
npm run cycle1 -- --dataset-only
npm run cycle1 -- --dataset-only --offline
```

Until candidate evaluation is implemented, the bare command fails closed after
validating the preregistration and source audit.

#### Phase 1B acceptance criteria

Phase 1B is complete only when:

```text
one command reproducibly builds/resumes the monthly dataset and evaluation
same raw bytes + config + code reproduce dataset and report identities
SPY and QQQ have separate explicit coverage, provenance, metrics, and gates
all candidate variations are present in the hypothesis ledger
all features and macro releases obey the historical cutoff
overlap-aware purge/embargo and uncertainty handling are tested
the sealed confirmation meets frozen observation, span, block, and coverage minima
the report distinguishes reconstructed from point-in-time-admissible evidence
no paid data subscription was added
no LLM, agent, account-query, leverage recommendation, or order code is involved
a clean-commit run freezes an exact target or rejects every candidate explicitly
```

#### Interpretation boundaries

A successful result could support only this conclusion:

> The frozen observable conditions materially alter the out-of-sample
> distribution of an exact instrument's 12-month real excess return or drawdown
> risk enough to justify later testing of an aggressive/defensive exposure
> overlay.

It would not establish the exact top or bottom, the date of a crash, causal
control of markets, next-day predictability, one objectively true six-state
cycle, transfer from SPY to QQQ without testing, or a reason to buy financially
impaired individual companies. It would not authorize paper or live trading.

If Phase 1B returns `NO_CYCLE_TARGET_ADEQUATE`, the project should preserve that
negative result, avoid post-hoc indicator proliferation, and stop or require a
new explicitly justified hypothesis family. If it freezes a target, proceed to
the broader `REALITY-STORE-001` and production `BASELINE-001` using that exact
target before introducing LLM agents or evolution.

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

## 2. Research targets and current decision

The original default hypothesis was:

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

`TARGET-TOURNAMENT-001` tested this target and 23 alternatives across SPY, QQQ,
ES, and NQ. It completed with `NO_TARGET_ADEQUATE`; the SPY 30-minute target was
not frozen and is no longer the active default.

The approved next target-search family is `CYCLE-ASYMMETRY-001`:

```text
instruments:        SPY and QQQ, evaluated and promoted independently
decision frequency: monthly
primary target:     12-month forward real total return minus observable
                    3-month Treasury-bill return
secondary target:   maximum drawdown during the following 12 months
diagnostic target:  24-month forward real excess return
```

The detailed next-session handoff above controls its preregistration. No cycle
target is frozen, and no cycle result exists yet.

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

**Outcome:** complete with `NO_TARGET_ADEQUATE`. All 24 candidates are rejected.

### Phase 1B — CYCLE-ASYMMETRY-001

No LLM calls, agents, account queries, or orders. No new paid subscription.

Evaluate SPY and QQQ independently at a monthly decision frequency using a
preregistered multivariable contracyclical model:

```text
structural position / valuation
+ credit and financial stress
+ macro direction
+ technical direction / recovery confirmation
→ calibrated 12-month real excess-return and drawdown forecasts
```

Use a transparent fixed-score model as the primary cycle representation and
simple unconditional, valuation-only, direction-only, and regularized
challengers. No HMM is included in the first Cycle 1 run. Use immutable no-cost source archives,
ALFRED-style release vintages where available, trailing-only transforms,
overlap-aware purged walk-forward evaluation, dependence-aware uncertainty,
and separate SPY/QQQ promotion gates.

Acceptance is defined in the detailed next-session handoff above. Freeze an
exact monthly target only after the report; otherwise close with
`NO_CYCLE_TARGET_ADEQUATE`.

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

### Approved and partially implemented

- `CYCLE-ASYMMETRY-001` Phase 1B is the current bounded target-search extension.
- Its detailed SPY/QQQ philosophy, source plan, preregistration requirements,
  eight implementation steps, acceptance criteria, and interpretation limits
  are recorded in the next-session handoff near the top of this document.
- Preregistration v4, source audits v1/v2/v3, provider acquisition, immutable
  dataset construction, targets, trailing-only features, deterministic states,
  resolved partitions, schemas, exploratory cycle-analysis tools, notebooks,
  and tests exist. The final Cycle 1 dataset passes online/offline identity and
  coverage gates. No model result or report has been produced yet.
- `npm run cycle1 -- --dataset-only` is the live acquisition interface;
  `--offline` refuses network access and requires the pinned raw archive.
- Candidate evaluation remains unavailable and fails closed. No candidate
  performance or sealed-confirmation result has been computed or viewed.

### Verified commands and results

```text
npm run check
  reverified: 2026-09-07
  TypeScript build: passed
  TypeScript tests: 15 passed
  Python tests: 88 passed

npm run cycle1 -- --dataset-only
  status: dataset-ready
  dataset: cycle1-monthly-19ccd95384e690de
  identity: 19ccd95384e690dee2fd529c3889a5b1ce17d956f8b9a1efffe551ec73e87753
  SPY eligible/core coverage: 308 / 100%
  QQQ eligible/core coverage: 234 / 100%
  hypotheses evaluated: 0

npm run cycle1 -- --dataset-only --offline
  status: dataset-ready
  identity: identical to online build
  track identities: identical to online build
  network access: disabled

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
implementation was committed as `196f5be`; and the final clean-run closure was
committed as `cda7003`. A clean-source offline rerun from the pinned bytes
reproduced the final identities.

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
2. Implement `CYCLE-ASYMMETRY-001` as the separately preregistered Phase 1B
   hypothesis family documented above. Do not alter Phase 1 candidates or gates.
3. Analyze both SPY and QQQ with the same target-level protocol while preserving
   separate inputs, limitations, metrics, gates, and promotion decisions.
4. Preserve the completed v4 preregistration, v3 source audit, final dataset,
   and resolved partitions unchanged while implementing candidate evaluation.
5. If Phase 1B rejects all candidates, stop or require a genuinely new,
   explicitly justified hypothesis family; do not add indicators post hoc.
6. If Phase 1B freezes an exact target, proceed to `REALITY-STORE-001` and then
   `BASELINE-001` before Pi, Ollama, fixed agents, or evolution.
7. Keep the zero-new-cost constraint. Do not purchase valuation history, deeper
   futures history, or IBKR real-time subscriptions for Phase 1B.

---

## 8. Next-session startup checklist

Run:

```bash
git status --short
npm run check
```

The completed Phase 1 result does not need to be rerun before writing the new
specification. If a regression audit is desired, its reproducible offline
command remains:

```bash
npm run phase1 -- --offline
```

If Docker is stopped:

```bash
npm run db:up
npm run check:db
```

The database was stopped at the last verification. Starting it is unnecessary
for the initial Phase 1B specification and source audit; use `npm run db:status`
and the commands above only when database integration work begins.

Read these files first:

```text
docs/PROJECT_PLAN_AND_STATUS.md
docs/CYCLE-ASYMMETRY-001.md
docs/FOUNDATION-001.md
docs/TARGET-TOURNAMENT-001.md
README.md
config/cycle1.json
config/cycle1-source-audit-v3.json
datasets/cycle1/cycle1-monthly-19ccd95384e690de/manifest.json
config/foundation.json
config/target-tournament.json
config/phase1.json
apps/cli/src/foundation.ts
apps/cli/src/alpaca-check.ts
packages/domain/src/*
packages/data-providers/src/provider.ts
packages/snapshot-engine/src/*
python/src/spy_predictor_quant/market_archive.py
python/src/spy_predictor_quant/phase1_*.py
migrations/001_foundation.sql
```

Next-session work order:

1. Treat `cycle1-monthly-19ccd95384e690de` as the only final Cycle 1 dataset.
2. Optionally rerun `npm run cycle1 -- --dataset-only --offline`; require hash
   `19ccd95384e690dee2fd529c3889a5b1ce17d956f8b9a1efffe551ec73e87753`.
3. Implement the five preregistered models per instrument and an immutable
   hypothesis ledger containing exactly ten primary entries.
4. Develop and test walk-forward machinery on the selection partitions only.
   Keep the final 96-month confirmation block sealed until the explicit
   one-time opening guard and immutable report path are ready.

Do not enable IBKR order submission and do not begin Pi, Ollama, agents,
evolution, or candidate-result exploration during preregistration.

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
preserve the completed TARGET-TOURNAMENT-001 rejection
→ preregister CYCLE-ASYMMETRY-001
→ build immutable point-in-time monthly SPY/QQQ evidence at zero added cost
→ freeze one exact cycle target or explicitly reject every candidate
→ complete the Reality Store only for a frozen target
→ complete the quantitative benchmark
→ test fixed agent incremental value
→ only then introduce evolution
```
