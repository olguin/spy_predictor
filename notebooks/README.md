# Cycle analysis notebooks

These notebooks are a manual, auditable companion to `CYCLE-ASYMMETRY-001`.
They explain the indicators in Spanish and English, render diagnostic charts,
and keep exploratory additions separate from the frozen first Cycle 1 run.
They are also the starting interface for the parallel
[Maru Cape application plan](../docs/MARU_CAPE_APPLICATION_PLAN.md): extend these
views with market/instrument assessments, shared workbench calculations, explicit
cutoffs, source freshness and conditional investment explanations.

- `01_structural_trend_and_expectations.ipynb`: long-run structural trend,
  average structural trend, log-price deviation, valuation, embedded
  expectations, surprise, and undervaluation-to-normalization analysis.
- `02_cycle_architecture_credit_and_risk.ipynb`: macro, fundamental,
  technical, psychology/credit dimensions; credit feedback; deterministic
  states; nested minor cycles; exploratory top score; optional latent-state
  filtering; and an aggressive-to-defensive research mapping.

## Install and launch

From the repository root:

```bash
UV_CACHE_DIR=.uv-cache uv sync --project python --group dev --group notebooks
UV_CACHE_DIR=.uv-cache uv run --project python --group notebooks jupyter lab notebooks
```

The notebooks use only NumPy, Matplotlib, the Python standard library, and the
local `spy_predictor_quant` package. They do not require pandas.

## Data modes

Each notebook has one `DATA_MODE` setting in its adapter cell:

- `"synthetic"` (default): always use the deterministic demonstration series.
- `"auto"` and `"cycle1"`: now rejected before the legacy archive adapter runs.

The old Cycle 1 adapter code is retained for reference but cannot be
selected through `DATA_MODE`. Current observed data is confined to the separate
workbench manifest panel described below.

## New market and instrument workbench

Both notebooks now include a shared assessment panel connected to validated local
input manifests. Set `WORKBENCH_INPUT_MODE='manifest'`, `WORKBENCH_MANIFEST`,
`WORKBENCH_INPUT_ROOT`, and timezone-aware `WORKBENCH_AS_OF`. The default manifest
is now `datasets/workbench/current-20260909-macro/SPY-manifest.json`, a verified
observed macro-only snapshot. Its cutoff is read from `verification.json`; choose
`QQQ-manifest.json` for the other instrument panel. Price/volatility and the other
missing components stay unavailable pending their own inputs. See
[verification and source scope](../docs/WORKBENCH_CURRENT_SNAPSHOT.md).
The symbol comes from the manifest; changing a label never fetches market data.
The original synthetic manifest remains under `examples/cycle-workbench`.

The adapter verifies the schema, file SHA-256, confined paths, source timestamps,
units, metric identity and instrument type, then derives scores from versioned
illustrative transforms. It rejects supplied score fields, withdrawn values,
ambiguous revisions and inappropriate company fundamentals for ETFs. Missing or
stale evidence remains explicit. Integrity validation is not independent publisher
authentication, validation of extraction accuracy or proof of prediction quality.

Choose `WORKBENCH_INPUT_MODE='fixture'` for the earlier handcrafted-score examples.
The synthetic six-scenario comparison remains separately labelled. The first
educational price-series sections are still synthetic and do not change mode
when a workbench manifest is selected.

The panel shows market posture, instrument action, supporting reasons,
counterevidence, component freshness and publication times, and reassessment
conditions. Missing or stale required inputs cause an incomplete assessment.
No success probability or personal position size is produced. Set
`EXPORT_WORKBENCH=True` to save matching JSON and standalone HTML reports.

The same functions are runnable without Jupyter:

```bash
npm run cycle:workbench -- instrument --fixture cheap-deteriorating --as-of 2026-08-31T20:00:00+00:00 --output reports/cycle-workbench/demo
npm run cycle:workbench -- compare --as-of 2026-08-31T20:00:00+00:00 --output reports/cycle-workbench/demo
npm run cycle:workbench -- validate-inputs --manifest examples/cycle-workbench/synthetic-manifest.json --input-root examples/cycle-workbench --as-of 2026-08-31T23:59:59+00:00
npm run cycle:workbench -- instrument --manifest examples/cycle-workbench/synthetic-manifest.json --input-root examples/cycle-workbench --as-of 2026-08-31T23:59:59+00:00 --output reports/cycle-workbench/validated-demo
```

Both notebooks previously executed end-to-end on synthetic inputs. Executed verification
copies for the manifest-connected version are under `/tmp/cycle-workbench-input-check`; repository notebooks
retain their editable code without adding generated execution output.

Manifest reports show the raw metric, unit, transformation and source evidence.
Export writes JSON, HTML and a separate whole-file input-audit receipt. Appending
future records may change source-file audit hashes but cannot change the selected
earlier assessment. The current snapshot adds observed macro inputs; earlier educational charts and
scenario comparisons remain synthetic and are labeled separately.

## Method boundary

This is an independent, transparent implementation inspired by public cycle
investing concepts associated with Maru Cape and Howard Marks. It is not their
proprietary model. The exploratory score, nested-cycle diagnostic, latent-state
filter, and exposure mapping are not part of the frozen first Cycle 1 candidate
evaluation. Notebook output is research material, not investment advice.

Current-data verification on 2026-09-09: both notebooks executed successfully
using the observed macro-only snapshot. Executed copies are under
`/tmp/cycle-workbench-current-check`. No Gateway is needed to rerun these saved
inputs; Gateway is needed for the pending fresh SPY/QQQ price capture.
