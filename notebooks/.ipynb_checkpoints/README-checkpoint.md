# Cycle analysis notebooks

These notebooks are a manual, auditable companion to `CYCLE-ASYMMETRY-001`.
They explain the indicators in Spanish and English, render diagnostic charts,
and keep exploratory additions separate from the frozen first Cycle 1 run.

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

- `"auto"` (default): use the newest verified Cycle 1 validation manifest for
  `INSTRUMENT` when available; otherwise use deterministic synthetic data.
- `"cycle1"`: require a Cycle 1 manifest and fail if none is available.
- `"synthetic"`: always use the deterministic demonstration series.

The selected source, manifest path, evidence tier, and synthetic seed are
printed near the top of every run. Cycle 1 artifact hashes are checked against
their track manifest before any rows are loaded.

## Method boundary

This is an independent, transparent implementation inspired by public cycle
investing concepts associated with Maru Cape and Howard Marks. It is not their
proprietary model. The exploratory score, nested-cycle diagnostic, latent-state
filter, and exposure mapping are not part of the frozen first Cycle 1 candidate
evaluation. Notebook output is research material, not investment advice.
