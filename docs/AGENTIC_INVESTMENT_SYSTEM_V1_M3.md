# M3 implementation and acceptance record

September 20, 2026. M3's publication, monitoring, review and observation code is
implemented. Engineering checks and an explicitly synthetic five-symbol
publication are recorded below. **M4 remains open and V1 is not released.** No
new live-provider research or live investment publication was performed in that
initial synthetic checkpoint. The subsequent [workspace and real pilot record](AGENTIC_INVESTMENT_RESEARCH_WORKSPACE.md)
tracks the user's newly authorized NVDA/MU/QQQ question separately.

## Delivered behavior

- New runs use telemetry v1: monotonic event sequences, recorded terminal times,
  worker deadlines, final/publication reserves and role omissions. An interrupted
  paid attempt remains visible and is never silently retried. Recovery labels its
  last observed time as uncertain.
- `monitor` serves one local run without acquiring its execution lock. It includes
  a role-grouped timeline, selectable parent/request/reuse paths, shared budgets,
  task findings, evidence manifests, request-specific alias maps, receipts, rejected
  turns and failed attempts. Source/model text is escaped. Raw documents are
  loaded on request. Runtime launch configuration is omitted from browser request
  projections; immutable originals remain on disk. Old missing telemetry remains
  unknown. The same view supports saved replay and one-second polling.
- Mandate v4 freezes a publication policy before research. It reserves enough
  source/tool calls for one price/event refresh, including instrument/benchmark
  prices and declared event coverage. Earlier mandate schemas remain available;
  an accepted M2 draft cannot be silently upgraded or published.
- `publish` performs one bounded refresh within the original aggregate and wall
  budgets. It propagates changed dependencies, recomputes the comparison panel
  and completed-close condition states, and withdraws affected guidance to
  `insufficient_evidence`. It preserves the original findings for audit. Other
  affected calculations are invalidated rather than silently repaired. Unaffected
  instruments retain their assessment. Another research revision requires a new
  run, not an automatic paid retry.
- Publication bundles contain the product, report, refresh coverage, observation
  contract, receipts, state, evidence, source documents and runtime archive. A
  content-addressed journal registration anchors the bundle file hashes. Large
  files are assembled and hashed before publication time. Expired refreshes and
  exhausted budgets stop publication; callers cannot provide a backdated time.
- The thesis journal records each publication, instrument thesis identity and
  parent version. `review` appends a uniquely identified manual review; a new
  research run can publish with `--review-of`. Neither replaces the old thesis,
  recommendation or observation rule. `feedback` supports a specific claim,
  omission, confusing explanation, changed need or usefulness comment.
- A separate observation contract freezes the first XNYS regular open strictly
  after publication, counts that session as 1, and targets session h's close.
  It freezes benchmark mappings, horizons, calendar version and delay. Prices
  remain pending until observed. Paired price returns require aligned times,
  feed/currency/dividend conventions and complete corporate-action coverage;
  raw origin prices are normalized for intervening splits. Incompatible and
  missing cases are retained unscorable. Conditional opportunities remain in a
  separate unscored lane; no intraday fill is inferred from daily conditions.

## Commands

Replay the accepted M2 run (read-only; does not resume execution):

```sh
python/.venv/bin/python -m spy_predictor_quant.investment_research monitor \
  --output reports/investment-research/m2-live-v7 --port 8765
```

Replay the completed synthetic M3 fixture by replacing `--output` with
`reports/investment-research/m3-engineering-fixture-v1`. `--snapshot` emits JSON
without starting a server. The browser endpoint is localhost only and has no
mutation or provider-tool routes.

For new research, use mandate v4 with fresh source acquisition windows. Its new
`publication_policy` has `version: investment-research-publication-policy-v1`,
`refresh_source_ids`, `material_price_move_pct`, `maximum_refresh_age_seconds`
and `maximum_quote_age_seconds`. The versioned schema validates the bounds;
source coverage is also checked against the watchlist and benchmark mapping.
`run --mandate ... --output ...` still ends at an unpublished draft. Manually
publish before its original wall deadline expires:

```sh
python/.venv/bin/python -m spy_predictor_quant.investment_research publish \
  --output reports/investment-research/NEW-RUN \
  --ledger datasets/investment-research/LIVE-LEDGER
```

`publish --review-of PUBLICATION-ID` links a newly researched version. It uses
the same ledger as its parent. `review`, `feedback` and `observe` each take
`--ledger PATH --publication ID --input FILE.json`. For example:

```json
{"category":"omission","symbol":"QQQ","text":"Explain the missing holdings coverage."}
```

```json
{"decision":"needs_research","symbol":"QQQ","reason":"New sponsor holdings are available."}
```

An observation input contains `symbol`, a registered `horizon`, `instrument` and
`benchmarks` keyed by every frozen benchmark. Each instrument record declares
USD, `price_return`, excluded cash dividends and raw share basis; exact origin
and target timestamps/prices/availability/feed/source hashes; and complete
corporate-action coverage with split identities, effective times and ratios.
`test_investment_research_m3.py::observation_data` is an explicitly synthetic
example of that contract. This is a validated ingestion path, not a new
automated market-data acquisition service.

## Retained acceptance evidence

- [Final engineering checks](../reports/investment-research/m3-engineering-checks-v1/acceptance.json):
  **553 Python tests**, **34 JavaScript tests** and TypeScript compilation passed.
  All **27 focused M3 tests** and the browser check also passed after the final
  evidence-date presentation change. Baseline runtime/configuration, comparator
  and frozen-case hashes match; the plan's progress text is the documented exception.
- [Synthetic publication acceptance](../reports/investment-research/m3-engineering-fixture-v1/acceptance.json)
  and [monitor projection](../reports/investment-research/m3-engineering-fixture-v1/monitor-snapshot.json).
- Publication `44935af8-a071-45f7-8609-22d6f0d07c6b`, run
  `0b729490-270d-452d-8ff8-ceeec2703b9b`, retained under
  `datasets/investment-research/m3-engineering-fixture-v1/publications/`.
  Ten tasks and 17 **scripted** model receipts; no paid provider calls. Its $0.17
  receipt total is a synthetic test value, not development spending.
- The synthetic journal includes clearly labeled fixture feedback and a manual
  review. They are not actual user usefulness feedback. The user's confirmation
  that the localhost monitor loads is a reachability check only.
- The focused M3 tests cover publication immutability, linked versions, scoped
  price/news changes and source failure, closure/stale quotes/expiry, strict
  post-publication origins, holidays/half days, split adjustment, incompatible
  bases, pending/unscorable outcomes, queued/two-active-slot projection, unknown
  usage, timeout/interruption/no retry, rejected submission, receipt reconciliation,
  HTTP path/method/origin restrictions and HTML-injection resistance.
- Headless Chrome checks replay the real accepted M2 run: 11 rows, native Enter
  activation from the table, selectable dependency paths, preserved focus and
  inspector scroll during polling, filters retaining selection, reduced motion,
  responsive layout and no browser exceptions. Reproduce with
  `scripts/check-investment-research-monitor.py` (local Chrome and
  `websocket-client` required). Results are saved beside the engineering checks.
- Runtime identity checks remain active. The fixture archives its exact code;
  subsequent monitor presentation changes do not authorize execution under a
  different runtime. Read-only replay remains supported.

## Qualifications carried forward

The existing source adapters supply daily closes, not contemporaneous executable
quotes. Publication reports this explicitly; quote freshness guards reject daily
closes, stale timestamps, delayed/partial-venue data and closed sessions. A
qualitative assessment can remain useful with an unavailable immediate-entry
quote. Event coverage is bounded to the registered sources, not all world news.

M2's underused valuation tools, bounded filings, broad abstention, repeated shared
prose and uncertain live reliability remain product limitations. Full condition
fields now appear together in Markdown and the inspector. This work does not
retroactively improve the accepted M2 findings or establish decision usefulness.

M4 still requires old-pipeline/single-agent/cooperating-system comparisons in both
fixed-evidence and comparable-budget end-to-end settings, actual resources and
failures, reviewed reports, a defect scorecard, zero unresolved critical factual,
numerical or timing errors, versioned keep/change/remove proposals and actual
user usefulness feedback. Frozen release cases remain unevaluated. No protected
historical cohort, legacy observation or previous acceptance bundle was changed.

## Repository retention

The user additionally requested a size audit and authorized removal of disposable
caches after verification. [The audit plan](../reports/repository-retention/2026-09-20-plan/report.md)
distinguishes regenerable package/test/Python caches from retained evidence.
Datasets, accepted and failed runs, source checks, M4 comparators, frozen cases,
installed environments and the backup/restore archive remain protected. A file's
age or absence from current imports is not evidence that it has no future value.
The backup record explicitly lacks verification of an independent durable copy.
Deleting ignored caches reduces local disk usage; Git history is unchanged.

Cleanup completed after the checks: seven cache directories removed, with
521,981,952 bytes (about **498 MiB**) of estimated reclaimable allocation.
See the [completed cleanup audit](../reports/repository-retention/2026-09-20-cleanup/report.md)
and its machine-readable `audit.json`. No research, dataset or backup files were
deleted; no unattended deletion job was installed.
