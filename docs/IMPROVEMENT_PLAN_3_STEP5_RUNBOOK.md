# Improvement Plan 3: five-step work package

This runbook covers the five next-work steps requested after the first engineering
release. They are distinct from the original ten research phases. The software
can capture, reconstruct, freeze, diagnose and collect new evidence; its research
qualification gates remain enforceable. A diagnostic scorecard is not a qualified
predictive result.

## Continuation decision — September 17

The [synthesis diagnosis record](IMPROVEMENT_PLAN_3_SYNTHESIS_DIAGNOSIS.md) now
documents a repaired exact-decimal transport defect, two passing small probes,
successful full archived Astra synthesis, and a new product with all 15 frozen
rows verified. Python contracts remain strict. The latest full check passed
27 JavaScript and 483 Python tests; final logging changes passed build and
28 JavaScript tests with Python unchanged. The newly captured chain also passed
through registered recovery, with all 15 product rows verified. Its initial
single-pass run remains partial, and publication freshness remains gated. Earlier
failure records below remain preserved.

Start with [the saved handoff](IMPROVEMENT_PLAN_3_HANDOFF.md). The original
diagnosis work order has been executed with bounded progress evidence, small
contract-valid probes and full archived verification. The causes of individual
old silent timeouts remain unproven; the newly observed decimal validation defect
has a tested repair.

Historical qualification limits predictive claims but does not block independent
engineering. The fixed ETF price diagnostic does not require historical membership
of every stock; that requirement belongs to broader stock-selection/exposure
models. Preserve all existing NOT_QUALIFIED flags, frozen designs and closed
periods. No new data purchase is the immediate next step.

## Delivered paths

1. **Historical reconstruction.** V2 observations bind SEC accession acceptance
   or ALFRED real-time vintages to source hashes. Actual first-seen/download times
   remain current. A date-only vintage becomes usable after its whole Eastern
   calendar day. Historical reconstruction requires an explicit lane; default
   live selection still rejects later downloads. Unknown availability stays out.
2. **Quantitative-only experiment.** V2 protocols name candidates and challenger
   before evaluation. Missing agent history no longer blocks a separately
   registered quantitative experiment. Candidate pairing, purging, immutable
   registration, held-out final period and promotion restrictions remain intact.
3. **Source capture and qualification.** Existing access captured SPY/QQQ/XLK raw
   and split-adjusted SIP bars, corporate actions, CPI and unemployment vintages,
   and AAPL SEC submissions/company facts. SEC histories paginate when needed;
   facts join by accession and preserve amendments. Optional news, consensus,
   historical ETF holdings and broad-stock universe gaps are explicit.
4. **Feasibility before model results.** Date/label-availability counts and an
   assumed-variance power sensitivity grid are saved before labels are calculated
   by the pilot builder. Effective-block and multiplicity thresholds remain fixed.
5. **Independent product readiness.** Four frozen semantic prompt fixtures, a
   report reading guide, a separate prospective collection command, and bounded
   live v4 qualification/recovery receipts are implemented. Failures are preserved.

## Reproduce the bounded source capture

Use a new root for a new capture. Repeating the same request/root reuses its
hash-verified receipts; it does not overwrite observations. Existing `.env`
credentials are loaded by the Node wrapper. No IBKR Gateway is required.

```sh
npm run meta:research -- sources --root datasets/meta-research/NEW_CAPTURE --start 2025-08-01 --end 2026-09-15
npm run meta:research:data -- audit --root datasets/meta-research/NEW_CAPTURE
npm run meta:research:data -- freeze --root datasets/meta-research/NEW_CAPTURE --input datasets/meta-research/quant-pilot-20260916/source-feature-registry.json --cutoff 2026-03-15T12:00:00Z --lane HISTORICAL_RECONSTRUCTION
```

The source adapter is deliberately bounded to the post-July-2025 window and a
small fixed universe. It cannot reopen the protected July 2017–July 2025 evaluation.
It fails rather than silently dropping pagination or substituting another feed.
SEC requests use the configured identifying User-Agent; no API keys appear in
saved FRED request URLs or error strings.

Source policy references:
[Alpaca bars](https://docs.alpaca.markets/us/reference/stockbars),
[corporate actions and availability limitation](https://docs.alpaca.markets/us/reference/corporateactions-1),
[ALFRED observation vintages](https://fred.stlouisfed.org/docs/api/fred/series_observations.html),
[SEC submissions and company facts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
Authenticated API access does not itself certify all historical/reuse licenses.

## Real-data diagnostic and its limits

The frozen pilot uses 282 sessions, three named ETFs, a 63-session warmup and
126 training origins. The smaller training window was specified before this
panel was built to exercise the permitted short history; the 30-effective-block
threshold and materiality/multiplicity criteria were unchanged.

| Horizon | Evaluated market dates | Paired instrument observations per candidate | Effective blocks | Required test dates |
|---|---:|---:|---:|---:|
| 5 sessions | 67 | 201 | 6 | 300 |
| 21 sessions | 51 | 153 | 1 | 1,260 |
| 63 sessions | 0 | 0 | 0 | 3,780 |

All five quantitative candidates completed the eligible folds without a failed
fold. The 63-session result is empty, not a zero-error result. Each symbol at a
market date remains together; more ETFs cannot manufacture independent dates.

[Scorecard](../reports/improvement-plan-3/quant-pilot-20260916/scorecard.md),
[registration](../reports/improvement-plan-3/quant-pilot-20260916/registration.json),
[panel manifest](../datasets/meta-research/quant-pilot-20260916/panel-v1/manifest.json),
[pre-outcome feasibility](../datasets/meta-research/quant-pilot-20260916/panel-v1/feasibility.json),
[source qualification](../datasets/meta-research/quant-pilot-20260916/qualification-3481b38eb5ce59ad.json).

The manifest intentionally retains failed audit flags. Its dataset kind is
`REVISED_PRICE_DIAGNOSTIC`, and all development promotion gates are disabled.
The qualified runner still rejects unaudited data. The final period starting
2026-09-16 remains unopened. No candidate was selected or retuned from these results.

For a separately designed diagnostic, freeze its design first and use new roots:

```sh
npm run meta:research -- panel --source datasets/meta-research/NEW_CAPTURE --output datasets/meta-research/NEW_CAPTURE/panel --protocol config/meta-experiment-quant-pilot-v2.json
npm run meta:research:experiment -- preregister --root reports/improvement-plan-3/NEW_EXPERIMENT --protocol config/meta-experiment-quant-pilot-v2.json --manifest datasets/meta-research/NEW_CAPTURE/panel/manifest.json
npm run meta:research:experiment -- run --root reports/improvement-plan-3/NEW_EXPERIMENT --panel datasets/meta-research/NEW_CAPTURE/panel/panel.json
```

Do not rerun/model-search this pilot as if it were a fresh independent experiment.
Registration pins code dependencies; changing code requires a new declared trial.
The exact registered Python dependencies were preserved in
[registered-code](../reports/improvement-plan-3/quant-pilot-20260916/registered-code/)
before the subsequent FRED HTTP transport repair. The original trial is not rerun
under the changed source hash.

## Source reconstruction evidence

The store contains 111 historical reconstruction records: 16 CPI vintages,
13 unemployment vintages and 82 SEC financial observations. The SEC import had
zero unmatched accession facts and zero conflicting values for this bounded
sample. All records passed the v2 schema with timestamp format validation.

A frozen March 15, 2026 feature snapshot selects then-available CPI, unemployment,
AAPL assets and liabilities while preserving September download timestamps:
[reconstruction receipt](../datasets/meta-research/quant-pilot-20260916/reconstruction-verification.json).
This verifies the source reconstruction path; it does not qualify market-price
features, a broad universe, fiscal-flow ratios, or missing analyst expectations.

## Prompt and report checks

[Semantic review](../reports/improvement-plan-3/prompt-eval-20260916/semantic-review.md)
covers missing news, embedded source instructions, revenue growth without
consensus, and syndicated repetition. All four bounded rubrics pass after one
provider-schema repair. The empty-news failure and identical-input retest remain
archived. The sampling adapter accommodates boolean subschemas while Python still
enforces the original full schema, including impossible evidence references.

The semantic reviewer was Codex comparing the source fixtures and outputs. This
is not a human reader study or an estimate of population semantic error rates.
The report guide explains terminal probabilities, session horizons, uncertainty
intervals, current-entry checks and unmeasured predictive value.

The first live seven-stage run and one synthesis-only resume preserved all six
completed specialist/critic stages but timed out at synthesis. The recovery
command uses verified parent completion receipts, retains all claims and critic
decisions, preserves numeric JSON Pointer positions, and copies distributions,
references and recommendations exactly. It records the projection and permits
one 900-second attempt per immutable registration. The first compact Astra attempt
also timed out. A separately declared Sol attempt failed with WebSocket close
1006. Both receipts remain archived; neither counts as a completed synthesis.
The next registered attempt used the original Astra model over explicit SSE
and also timed out after 900 seconds without a result. The transport change did
not resolve synthesis completion. No successful seven-stage v4 live run is
claimed. Model changes are explicit, never automatic.

Final bounded attempt:
[registration](../reports/improvement-plan-3/step5-live/synthesis-recovery-20260917T023626062513Z-005dea0d/registration.json),
[failure](../reports/improvement-plan-3/step5-live/synthesis-recovery-20260917T023626062513Z-005dea0d/failed.json).
Together the archived attempts contain four timeouts (two full requests and two
compact Astra requests) and one Sol WebSocket failure. No further model call was
started after this final attempt. Earlier timeout usage remains unknown.

The installed Pi runtime supports a transport setting. The adapter now requests
SSE by default and includes the requested transport in its usage receipt. This
avoids selecting the observed WebSocket transport; it does not alter prompts,
model selection, numerical outputs or provider-side quotas. OpenAI documents
[SSE response streaming](https://developers.openai.com/api/docs/guides/streaming-responses)
and [WebSocket mode](https://developers.openai.com/api/docs/guides/websocket-mode)
as separate transport paths.

A [degraded report](../reports/improvement-plan-3/step5-live/fallback-product/index.html)
is available even without synthesis. Its failure remains visible. All 15 frozen
numerical rows, reference contracts, actions, invalidations, review text and
summary decision rows passed schema and parity checks against the original
synthesis request:
[verification](../reports/improvement-plan-3/step5-live/fallback-product/product-parity-verification.json).
The delayed publication is stale for current entry; the report retains that gate.

## Prospective collection

```sh
npm run meta:research -- collection prepare
npm run meta:research -- collection collect
```

The configuration is `config/meta-research-collection-v1.json`. Captures, reports,
observations and receipts use new research roots. Three captured five-symbol
packets have produced 120 observations in the separate prospective store. Importing the same packet again
reuses its observations; a new packet retains its actual new capture/ingestion
time. `--packet PATH` can import a verified packet without new network requests.

`prepare` reports credential presence, source-file hashes, coverage and the next
XNYS completed-close collection time, including early closes. It does not install
an unattended schedule. Collection creates no forecast registration and submits
no orders. The existing prospective forecast ledger remains separate.

Public FRED graph requests now use bounded HTTPS curl transport after urllib
requests repeatedly timed out while the same endpoint succeeded with curl.
Authenticated provider requests retain their existing HTTP/header handling.
The latest capture reduced 21 FRED failures to one (`DGS5`); price and SEC capture
succeeded. Missing macro evidence remains in the packet's acquisition errors.
The collector reports `COLLECTED_WITH_SOURCE_GAPS` for partial captures and exits
unsuccessfully if no qualified numerical observations were imported. This is
source availability monitoring, not a guarantee that every provider always works.

Latest successful capture:
[receipt](../datasets/meta-research/prospective-v1/receipts/collection-20260917T024314040889Z-ce3a55e7/completed.json).
A verified re-import reused the same observation hashes, kept the store at 120
records, and emitted the new partial-capture status:
[idempotence/partial-status receipt](../datasets/meta-research/prospective-v1/receipts/collection-20260917T025216020611Z-00f40b96/completed.json).
Credential and calendar preparation:
[readiness](../reports/improvement-plan-3/collection-readiness-env-20260916.json).

## Validation

`npm run check` passed the TypeScript build, all 20 JavaScript tests and all 477
Python tests. The source reconstruction schema check covers all 111 records;
the bounded semantic review covers four fixtures. These checks establish the
implemented behavior within those cases, not empirical forecast accuracy.

## Open engineering and empirical acceptance gates

- Ordinary-path streaming reliability and timely publication. Archived and newly
  captured chains now pass through registered synthesis recovery. The fresh
  single-pass attempt remains partial; its recovered report retains the actual
  cutoff, publication lag and freshness/evidence gates.
- Verified historical price revision/availability evidence and sufficient
  independently eligible history. Current downloaded historical bars are revised
  observations; their session date is not proof of their historical first-seen time.
- A historically defined stock universe, delistings and action coverage before
  making broad-stock claims. Three selected ETFs cannot qualify that scope.
- Source/use license qualification for any broader training or redistribution.
- More independent dates for horizon-specific uncertainty, and actual future
  outcomes for prospective confirmation. A power sensitivity grid is not measured power.
- Timestamped consensus and dated exposure histories for models that require
  those features. They do not block this quantitative engineering diagnostic.

An existing archive can be assessed without purchasing anything. Its minimum
handoff is the provider/export path, covered dates and instruments, original
publication/first-seen timestamps plus correction versions, feed/adjustment basis,
corporate-action records with their availability, historically dated membership
and delisting records for a broad universe, and the applicable research-use
terms. Preserve the original files and delivery receipts. A fresh export of the
latest corrected bars alone does not meet that requirement. A qualified import
adapter must be designed against the actual archive contract and audited before
any manifest can claim qualification.

If no archive is available, continue collecting actual new observations with the
command above. That builds forward history; it cannot immediately produce the
independent market dates or matured 63-session outcomes the fixed gates require.
Any future change to the experiment's window or design requires a new preregistered
protocol and must preserve the closed evaluation periods.

These are acceptance requirements, not software flags to turn on. No improvement
in predictive accuracy, completed original ten-phase plan, or production promotion
is asserted by this work package.
