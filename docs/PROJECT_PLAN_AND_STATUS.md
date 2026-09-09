# Project plan, status, and next-session handoff

Status reviewed: 2026-09-09. Repository: `spy_predictor`.

## Current decision and next action

The user authorized a **separate historical development track on 2026-09-09**:
qualify development inputs and start fixed-baseline walk-forward training,
preserving stopped experiments and excluding the final evaluation period.
Follow [HISTORICAL_DEVELOPMENT.md](HISTORICAL_DEVELOPMENT.md) and its versioned
[contract](../config/historical-development-v1.json). This explicit new instruction
supersedes the previous “secondary snapshot only” work order for development.

**Cycle 1 remains suspended and both power experiments remain stopped.** The
original v1 stop is immutable. The registered successor's first complete
replication took 88.75 seconds and projected 20.5 days against its one-hour budget.
Its terminal decision remains `INSUFFICIENT_EVIDENCE_COMPUTATIONAL_BUDGET`;
no locked replications ran, no statistical power failure was established, and
the single redesign slot remains consumed. No Cycle 1 real-data authority,
research qualification, or confirmation opening is released.

The development-only runner rebuilds SPY features and primary labels in separate
artifacts and uses the seven fixed models. Qualification found two missing daily
sessions; the pre-output amendment explicitly excludes affected daily-feature
windows while preserving every scheduled forecast date. There are 200 monthly
origins, 174 complete feature origins, and 42 trainable dates out of 68 scheduled
forecast months per mode. See the development note for the exact scope and
limitations. July 2017–July 2025 remains excluded from development.

The first run is complete: [development results](../reports/historical-development/5ffd4a7b879d3237/summary.md).
Both cycle challengers fail to beat every baseline in both modes on the 42 common
dates. The result is descriptive and no model is promoted. Dataset identity
`03608a029ae35517`, report folder `5ffd4a7b879d3237`; the development note contains
full hashes.

The user subsequently made Gateway available and authorized the repair/rerun.
Ten bounded IBKR requests found no compatible replacements: SMART daily/hourly
responses still omit both dates; ARCA returns the 2007 date but its neighboring
closes differ from SMART. The [repair audit](../reports/historical-development/gap-audit-6d79f6498c132ac6/summary.md)
is `DATA_REPAIR_NOT_QUALIFIED`. No new dataset or training run was produced.
Next: obtain a compatible source correction or separately qualify another source;
connectivity is resolved, data completeness is not. Keep final evaluation closed.

## Goal and critical path

Produce reproducible, calibrated forecasts from information available at the
cutoff, then establish incremental predictive and executable economic value on
unseen evidence. A quantitative-only system is an acceptable endpoint. LLM agents
and evolution are conditional experiments, not prerequisites for success.

```text
coherent amendment and scientific contract
→ synthetic evaluator plus whole-procedure false-positive/power audit
→ new full-path-qualified immutable monthly dataset
→ SPY selection only
→ one historical confirmation decision, if selection qualifies
→ prospective monthly forecast capture and a narrow operational quant system
→ separately qualify an allocation policy and paper workflow
→ add agents/evolution/options only for demonstrated incremental value
```

Every stage can end in a documented rejection, insufficient-evidence decision,
or invalid-evaluation report. None of those outcomes permits automatic promotion.
See the strategy for exact deliverables, stop conditions, and conditional phases.

## Parallel secondary goal: practical Maru Cape analysis

User direction on 2026-09-08 adds a parallel application track. Follow
[MARU_CAPE_APPLICATION_PLAN.md](MARU_CAPE_APPLICATION_PLAN.md) for sourced method
components, reusable tools, market-state and instrument assessments, and phased
implementation. The first synthetic workbench is now runnable in both notebooks
and via `npm run cycle:workbench`: component evidence, explicit missingness,
conditional market/instrument assessments, scenario charts and JSON/HTML export.
Both notebooks executed successfully. Legacy Cycle 1 `DATA_MODE=auto/cycle1`
access is blocked; the separate manifest adapter can accept explicitly identified
observed-as-of or reconstructed research inputs after structural validation.
Validated local manifests and raw-metric transformations are now connected to
both notebooks. The included input sample is synthetic; schema/hash/unit/time
validation does not authenticate a publisher or establish investment performance.
A verified current macro snapshot now supplies observed industrial-production
growth in both notebooks; [snapshot details](WORKBENCH_CURRENT_SNAPSHOT.md).
SPY/QQQ price capture is implemented but Gateway at localhost:4002 was unavailable.
Next: add fresh prices/realized volatility, then expand remaining components. Public method descriptions and our independent proxies must remain
distinguishable. This exploratory track can advance while Cycle 1 is stopped;
its outputs cannot qualify Cycle 1 or imply tested investment performance.

## Verified state

The separate development run completed on 2026-09-09. `npm run check` passed
(15 TypeScript and 304 Python tests), including eight dedicated development tests
for future-input forecast invariance and immutable resume. Offline
reconstruction and report resume reproduced identical identities; the
[verification receipt](../reports/historical-development/5ffd4a7b879d3237/verification.json)
checks all five stopped-experiment files and all 952 scheduled model/mode forecast
records (588 scored, 364 unavailable). Both stopped status commands reproduced
their terminal decisions with expected exit 2.

| Area | Current status |
|---|---|
| Foundation — Phase 0 | Complete research spine: identity, snapshots, cutoff guards, resumability, schemas, calendars, storage, CI; synthetic baseline is infrastructure evidence |
| Target tournament — Phase 1 | Complete: `NO_TARGET_ADEQUATE`; 24 SPY/QQQ/ES/NQ instrument/horizon candidates, no target frozen |
| Cycle research — Phase 1B | Unqualified v4 archive; synthetic evaluator and downstream fixture implementations exist; frozen simulation v1 stopped for insufficient evidence scope; no locked validation |
| Reality Store / production baseline — Phases 2–3 | Foundation subsets only; extend them for a surviving target rather than build the full platform upfront |
| Agent runtime — Phase 4 | Interface and mock only |
| Anti-overfitting — original Phase 7 | Some chronological controls exist; Cycle 1 claim tests, power gate, ledger, and one-time confirmation mechanism are prerequisites now |
| Agents, evolution, options, expression, paper, live — remaining phases | Not implemented; conditional on evidence, with separate live authorization |
| IBKR integration | Paper/read-only market-data adapter; no order submission; prior live capture was entitlement-limited, current entitlement not rechecked |

Passing tests establish implemented behavior, not statistical power or market
predictive value. The old online/offline dataset identity match established
reproduction; later correctness findings superseded its qualification.

## Authorities and evidence

| File/artifact | Role |
|---|---|
| [PROJECT_STRATEGY.md](PROJECT_STRATEGY.md) | Current recommended strategy and implementation order |
| [CYCLE1_REPAIR.md](CYCLE1_REPAIR.md) | Detailed implemented repairs and metadata findings; earlier proposed work order is historical context |
| [CYCLE-ASYMMETRY-001.md](CYCLE-ASYMMETRY-001.md) | Suspended v4 scientific specification and amendment history |
| [config/cycle1.json](../config/cycle1.json) | Currently validated v4 configuration, explicitly blocked for evaluation |
| [config/cycle1-v4.json](../config/cycle1-v4.json) | Explicit v4 archive; archived schema is `schemas/cycle1-config-v4.schema.json` |
| [config/cycle1-v5-draft.json](../config/cycle1-v5-draft.json) | Validated `proposed-synthetic-only` contract; frozen simulation v1 stopped; no power approval |
| [successor repairs](CYCLE1_SUCCESSOR_REPAIRS.md) | Positive-price and annual-null repairs implemented/proved; single redesign slot now consumed |
| [successor integration](CYCLE1_SUCCESSOR_INTEGRATION.md) | Full deterministic evaluator integration implemented |
| [successor profile](CYCLE1_SUCCESSOR_PROFILE.md) | Single successor registered and stopped for compute budget; 1 development replication, 0 locked replications |
| [proposed source audit v4](../config/cycle1-source-audit-v4-draft.json) | Hash-linked v5 proposal, archive reuse only; acquisition/migration blocked |
| [source audit v3](../config/cycle1-source-audit-v3.json) | Current hash-linked acquisition authority; must be amended for v5 |
| [repair audit](audits/cycle1-repair-352a046a5c12b63e.json) | Deterministic metadata evidence; no candidate scores |
| [v4 dataset manifest](../datasets/cycle1/cycle1-monthly-19ccd95384e690de/manifest.json) | Local, Git-ignored archive; suspended for evaluation |
| [Phase 1 final report](../reports/phase1-cd393a5b710cd176/report.json) | Completed negative result; preserve unchanged |
| [DATA_DURABILITY.md](DATA_DURABILITY.md) | Archive/database backup and separate restore verification; local restore verified; independent archive restore remains unverified |

Historical identities, for verification rather than evaluation approval:

```text
v4 config:  887ab9410f79e7fd2884af731c029d81ba2f0d57d4d3c3e22b9bb68671bfdbc8
audit v3:   80a80d252c65abe9b13a8533e6d5ad23d65e68e3df993ab2734594c5ab8f3a90
v4 dataset: 19ccd95384e690dee2fd529c3889a5b1ce17d956f8b9a1efffe551ec73e87753
Phase 1:    cd393a5b710cd17692648d10e0418be07e7391a7eeb030f6d52371d4c6523072
```

Validated proposal identities (not an active experiment):

```text
v5 proposal: 74a486ed3c65bfb116ca28eca06c831dbce213bbafe08396310a3677b51ebeda
audit draft: e0728302088de54c57080bc6837f9e084bf0c941cc554323c451eabfe1870886
ledger:      0ca02c67ffdfeaa6bac3bdd48e4a9ece6bd35ca8b8e27d861b6cd4069d1d86e0
```

The [proposal validation report](audits/cycle1-v5-proposal-bbba14d7491f5c21.json)
records code hashes and outstanding gates; it contains no candidate scores.

## Blockers and design constraints

| Finding | Implication / next action |
|---|---|
| DGS3MO's first pinned publication is 2005-06-28 | Archived observations cannot establish earlier availability; use the proposed GS3M amendment with strict vintage rules |
| GS3M's first pinned publication is 1996-12-03 | Selection-start coverage passes, but full paths still need checking; preserve earlier prices for warm-up and avoid generating inadmissible warm-up targets from January 1993 |
| SPY: 200 selection rows, 68 forecasts with 120 mature labels | About 5.7 calendar years of overlapping annual forecasts; enough to run mechanically, power unestablished |
| QQQ: 126 selection rows, zero selection forecasts | Proposed role is transfer-only; 126 mature labels at confirmation start can support its reference distribution |
| Both modes share dates; both instruments share market shocks | Do not count them as independent replications; 97 fixed confirmation months are not 97 independent annual outcomes |
| Spread change previously used the wrong lag | Recompute features with the exact common observation month minus three; old feature hashes are not repaired by changing a report |
| v5 proposal/schema/loader/audit/CLI transition implemented | `npm run cycle1 -- --contract-only` validates the proposal; full synthetic procedure, power approval, and dataset qualification remain blocked |
| Full ETF tracks are reconstructed research evidence | Historical qualification cannot establish replay-safe or deployment-ready evidence |
| Legacy notebook full-history access is now blocked | Use the separate validated-manifest workflow; this does not grant Cycle 1 confirmation access |
| Legacy candidate dividend equation fails on supported shocks | Final repaired configuration selects the passing reserve/compensation construction; registered successor stopped for compute budget |
| Original nulls could contain extra information | Repaired nulls separate iid monthly return scale from persistent daily bridges; strong-baseline control reveals a Markov regime through actual valuation; freeze these explicit scenario amendments |

The archived selection ends 2016-06-30. The embargo is 2016-07-29 through
2017-06-30. Confirmation is 2017-07-31 through 2025-07-31, split after
2021-06-30. Keep these dates fixed in the amendment; new ingestion must not
silently move the holdout.

Source assets already exist: IBKR daily SPY/QQQ bars, sponsor cash distributions,
and ALFRED CPIAUCSL/INDPRO/MPRIME/GS3M vintages. The Invesco manual snapshot is
pinned under the source-audit chain; reuse it instead of repeated automated
acquisition. Shiller/CAPE and NFCI remain diagnostics. Previously excluded
Moody's/ICE and Tiingo inputs remain excluded under their recorded source audits.
Zero new paid data remains the Cycle 1 constraint. No additional source purchase
is the current critical path.

## Next-session startup and work order

Read this file and the strategy, then inspect the repair note, draft config,
current loader/schema, and source-audit chain. Run separately:

```bash
git status --short
npm run check
npm run cycle1:preflight
```

The preflight's expected exit 2 reports:

```text
V5_AMENDMENT_NOT_YET_FROZEN
EVALUATION_CONTRACT_INCOMPLETE
ARCHIVED_SPREAD_LAG_REQUIRES_REBUILD
```

Exit 1 indicates invalid audit input and needs investigation. Do not use
`npm run cycle1 -- --dataset-only --offline` as a passing startup check: the
corrected v4 build intentionally fails on historical cash publication coverage.
Bare `npm run cycle1` is also blocked. Database startup and Phase 1 reruns are
unnecessary for the amendment work.

1. Verify `npm run cycle1:successor -- status` (expected exit 2); preserve both
   stopped experiments and their artifacts unchanged.
2. Continue the separately authorized [historical development track](HISTORICAL_DEVELOPMENT.md):
   verify its qualification receipt, run the fixed baseline/challenger roster,
   and review development-only scores and missingness. No final evaluation access.
3. The [secondary snapshot](WORKBENCH_CURRENT_SNAPSHOT.md) remains independently
   available. Gateway on port 4002 was reachable during the gap repair; current
   snapshot refresh is separate from this historical-data task.

## Remaining phases at a glance

| Work package | Status | Concrete completion condition / next step |
|---|---|---|
| A — Scientific contract and feasibility | Synthetic successor frozen; primary progression stopped | Preserve final registered authorities; real-data amendment cannot activate after failed B |
| B1 — Model/evaluation code | Implemented and fixture-tested | Retain shared primary, downside, policy and transfer arithmetic |
| B2 — Complete synthetic evidence paths | Repaired config and full evaluator adapter fixture-tested | Full generated calendar reaches primary, drawdown, costed policy and transfer arithmetic; no random power evidence |
| B3 — Register and profile successor | Complete with computational stop | First full replication 88.75s; projected 20.5 days versus 1 hour; redesign slot consumed |
| B4 — Locked false-positive/power audit | Not released; 0/20,000 replications | B3 failed compute budget; statistical false-positive/power evidence unavailable |
| C — Rebuild and qualify real dataset | Pending passing B | Final authorities, independent restore, admissible cash paths, corrected spread lag, role-aware coverage and identical offline rebuild |
| D — SPY selection | Pending C | Evaluate fixed candidates on selection only; publish survivors or a negative decision |
| E — One historical confirmation | Conditional on D | Persist opening identity before scoring; publish one immutable decision including eligible QQQ/secondary checks |
| Operational forecasts and prospective evidence | Conditional on research qualification | Timestamp monthly forecasts before outcomes and test calibration on newly arriving evidence |
| Allocation/paper workflow | Later, separately qualified | Validate costs, risk and operational reliability; historical forecast success alone is insufficient |
| Agents, evolution, options, live execution | Conditional later work | Demonstrate incremental value; live execution needs separate authorization |

The goal is useful suggestions with explicit reasoning and measured uncertainty,
not universal success across instruments or situations. Neither a passing code
suite nor a descriptive notebook score establishes a high probability of success.

### Parallel notebook track

Completed: reusable market/instrument assessments, raw-metric transforms,
cutoff/revision/missingness handling, manifest hashes and confined input roots,
component provenance panels, and JSON/HTML exports in both expanded notebooks.
The included manifest is synthetic and both notebooks ran successfully on it.

Current macro-only snapshot: `datasets/workbench/current-20260909-macro`. Fed
release narrative and Table 1 independently extract the same July 2026 IP growth;
source files, SHA256, availability times, SPY/QQQ manifests and assessments exist.
Both notebooks use this snapshot. Gateway was unavailable for fresh price capture.
Next: capture and verify SPY/QQQ daily prices to add timing and realized volatility.
Expand missing components and instrument-specific definitions (especially ETF
quality/valuation), keeping public method descriptions separate from our proxy
formulas. Later predictive claims need a separate frozen evaluation. This work
can proceed independently while the main simulator is not ready to freeze.

Implementation entry points:

- `python/src/spy_predictor_quant/cycle1_config.py` and `schemas/cycle1-config.schema.json`
- `python/src/spy_predictor_quant/cycle1_source_audit.py` and `apps/cli/src/cycle1.ts`
- `python/src/spy_predictor_quant/cycle1_targets.py`, `cycle1_features.py`, `cycle1_dataset.py`, `cycle1_feasibility.py`
- `python/tests/test_cycle1_*.py`; synthetic model/evaluator/procedure/downside,
  optimization, and power-stop modules exist. Full-path locked power evidence
  remains unavailable under the stopped design.

Preserve unrelated work, ignored raw archives, source snapshots, and historical
reports. Keep source credentials private. No account-query, order, agent, or
LLM work belongs in Cycle 1. Trading and scheduler deployment are separate work.

Latest verification, 2026-09-09: `npm run check` passed (15 TypeScript and
296 Python tests). Both notebooks executed on the observed macro-only snapshot;
executed copies are in `/tmp/cycle-workbench-current-check`. The registered
successor's one development replication completed in 88.75 seconds and caused
the computational stop, with decision identity
`238b3770f41551a2ff85480739c5552b28bef0bf10825d9618984615b7d54268`.
`cycle1:successor -- status` verifies and reproduces the stop without another draw.
Registration identity is
`88b0d0498607721d6140b45fe4dcec8cca974fb884dae17ec140d2083a12d59f`.
The secondary input receipt is
`datasets/workbench/current-20260909-macro/verification.json`; current-price
capture is waiting for the paper/read-only Gateway on localhost:4002.

Earlier integration verification on 2026-09-09: `npm run check` passed (15 TypeScript,
283 Python tests). `cycle1:integration-check` published report
`0f15218dc8e60926170ab6bfa4dde676db5b750edb1c0b1e1067020efae0a286`,
status `FULL_PIPELINE_FIXTURE_NOT_REGISTERED`. Final repaired config identity is
`2a4b1daf12b3665d78ca25b369320cd2c23c310103818a1c548d5cf1ec37ad6f`.
The 439-cutoff fixture reaches the shared primary, drawdown forecast, costed policy
and transfer arithmetic. The original repair report and blocked preflight reproduced.
No successor random draw, registration or locked validation occurred. See the
[integration note](CYCLE1_SUCCESSOR_INTEGRATION.md) for exact scope and remaining gates.

Prior implementation verification on 2026-09-08: `npm run check` passed (15 TypeScript,
276 Python tests, including 27 new repair tests). `cycle1:repair-check` passed
and published report hash
`eed1ed473b64a721b479074e2c4d4905a2123e9015de77722567d02c14f09577`.
Evidence includes the formerly failing price shock, monthly accounting in all ten
scenarios, exact regime-law checks, both observable regimes through all nine
features, different-stress/same-annual-return coupling, and future-input invariance.
The new null construction is an explicit amendment, not approval of the old one.
The strong-baseline CPI control is synthetic-only and must not feed the secondary
notebooks as observed market evidence.

In prior verification, both notebooks executed without errors using the validated synthetic raw-metric
manifest. A standalone manifest assessment and separate input audit were exported.
`cycle1:equation-check` published a deterministic no-random-draw report.
The historical `cycle1:successor-readiness` returned `NOT_READY_TO_FREEZE` (expected exit 2),
reproducing the supported-shock price failure and reporting the limited latent
annual-variance analysis. Its report hash is
`3b7d5d92f7457de2a0050761a4b1c2d4e465755d73aaea24f848fab79688d58d`.
At that earlier milestone no successor profile/draw had run and the redesign
slot was unused; the registered computational stop above supersedes that state. The new
`cycle1:redesign-review` returned `VALID_PROPOSAL_NOT_FROZEN` (exit 0), with all
draw/execution permissions false. In the retained baseline verification,
contract-only returned `STOPPED_INSUFFICIENT_EVIDENCE` (exit 0);
power-audit reproduced stop report `7d7b93257f67e058` (expected exit 2).
The cached optimized profile reproduced exact equivalence and a 1,801-second
available-branch projection. Original preflight exit 2 and hash reproduced.
Synthetic development metrics exist. No real candidate metrics, locked power
result, source migration, or real confirmation opening occurred. Detailed artifacts and remaining work are recorded in
[CYCLE1_SYNTHETIC_DESIGN.md](CYCLE1_SYNTHETIC_DESIGN.md).

## Maintaining this handoff

Replace stale current instructions when a milestone changes. Keep one next
increment, exact artifact identities, dated verification, and explicit blockers.
Put detailed rationale in the strategy and scientific changes in versioned
contracts. The 1,965-line pre-review handoff is recoverable from Git at
`c2302aa:docs/PROJECT_PLAN_AND_STATUS.md`; duplicate chronological updates,
obsolete provider shopping, completed task inventories, and contradictory
“dataset qualified / start models” instructions have been compacted here.
