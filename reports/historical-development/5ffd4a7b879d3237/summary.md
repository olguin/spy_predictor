# Historical development: first fixed-roster walk-forward run

Completed 2026-09-09. **Development only; final evaluation unopened.**

200 SPY origins; 174 complete feature origins. Two missing archived daily sessions invalidate 26 feature origins. All 68 forecast months per mode remain in the output: 42 scored (January 2013–June 2016), 26 unavailable for insufficient mature complete labels.

Neither cycle challenger has lower CRPS than every fixed baseline in both modes. These are descriptive scores over overlapping annual outcomes, not a research qualification or significance result.

Lower CRPS and RMSE are better. Coverage is the fraction of realized outcomes inside the nominal 90% predictive interval.

| Model | Expanding CRPS | Rolling CRPS | Expanding RMSE | Rolling RMSE | Expanding / rolling 90% coverage |
|---|---:|---:|---:|---:|---:|
| unconditional-history | 0.059738 | 0.057473 | 0.103836 | 0.099330 | 100.0% / 100.0% |
| volatility-conditioned-history | 0.060755 | 0.058429 | 0.098665 | 0.088477 | 76.2% / 76.2% |
| valuation-only | 0.064790 | 0.054885 | 0.109873 | 0.091616 | 100.0% / 100.0% |
| direction-only | 0.060558 | 0.055182 | 0.102185 | 0.092136 | 100.0% / 100.0% |
| position-plus-direction | 0.065322 | 0.055291 | 0.110810 | 0.092403 | 100.0% / 100.0% |
| fixed-cycle-score | 0.072543 | 0.062709 | 0.115201 | 0.097756 | 97.6% / 97.6% |
| regularized-cycle | 0.069433 | 0.056510 | 0.120946 | 0.096975 | 100.0% / 100.0% |

All comparisons use the same 42 dates. The unconditional model has the lowest expanding CRPS; position-only ridge (`valuation-only`) has the lowest rolling CRPS. The regularized cycle model improves over unconditional and volatility-conditioned history in rolling mode, but trails the three other baselines and all baselines in expanding mode. Fixed cycle-score tertiles trail every baseline in both modes.

No model is promoted, no policy or QQQ transfer evaluation ran, and both stopped power experiments remain unchanged. No parameter or feature search was performed.

Artifacts: [machine-readable report](report.json), [pre-fit ledger](ledger.json), [fold memberships](folds.json), [forecast distributions and unavailable statuses](forecasts.ndjson).

Dataset identity: `03608a029ae355172a880777f31ac53ede175000678bc7798392319da3b217ad`.

Report identity: `9beaf08eb44d589c48622516bf09aa9847b11e9f94dc78acc45814b5a886a8a2`.

Qualification: [development dataset manifest](../../../datasets/historical-development/03608a029ae35517/manifest.json) and [qualification audit](../../../datasets/historical-development/03608a029ae35517/qualification.json).

Plan and source limitations: [historical development](../../../docs/HISTORICAL_DEVELOPMENT.md).
