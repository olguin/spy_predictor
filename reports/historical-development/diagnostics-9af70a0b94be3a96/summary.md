# Development diagnostics

Post-output review of the first run. No new fitting, parameter search, promotion, or final evaluation.

All seven models use the same 42 scored forecast dates per mode. The other 26 dates remain unavailable.

CRPS and bias are in annual excess log-return units. Bias = forecast mean minus realized outcome.

| Mode | Model | CRPS | Mean bias | 50% coverage | 90% coverage | Mean 90% width |
|---|---|---:|---:|---:|---:|---:|
| expanding | unconditional-history | 0.059738 | -0.0641 | 64.3% | 100.0% | 0.5524 |
| expanding | volatility-conditioned-history | 0.060755 | -0.0583 | 38.1% | 76.2% | 0.3948 |
| expanding | valuation-only | 0.064790 | -0.0711 | 57.1% | 100.0% | 0.5562 |
| expanding | direction-only | 0.060558 | -0.0587 | 64.3% | 100.0% | 0.5627 |
| expanding | position-plus-direction | 0.065322 | -0.0710 | 57.1% | 100.0% | 0.5523 |
| expanding | fixed-cycle-score | 0.072543 | -0.0613 | 57.1% | 97.6% | 0.5642 |
| expanding | regularized-cycle | 0.069433 | -0.0783 | 59.5% | 100.0% | 0.5175 |
| rolling | unconditional-history | 0.057473 | -0.0553 | 66.7% | 100.0% | 0.5407 |
| rolling | volatility-conditioned-history | 0.058429 | -0.0439 | 47.6% | 76.2% | 0.3818 |
| rolling | valuation-only | 0.054885 | -0.0524 | 71.4% | 100.0% | 0.5420 |
| rolling | direction-only | 0.055182 | -0.0470 | 69.0% | 100.0% | 0.5403 |
| rolling | position-plus-direction | 0.055291 | -0.0507 | 69.0% | 100.0% | 0.5425 |
| rolling | fixed-cycle-score | 0.062709 | -0.0415 | 61.9% | 97.6% | 0.5483 |
| rolling | regularized-cycle | 0.056510 | -0.0580 | 64.3% | 100.0% | 0.5069 |

## Stability across forecast-origin years

The table shows the lowest CRPS in each slice. This is a diagnostic, not a model-selection rule. Annual targets overlap; 2016 covers six months.

| Mode | Origin year | Lowest-CRPS model | CRPS |
|---|---|---|---:|
| expanding | 2013 | fixed-cycle-score | 0.069273 |
| expanding | 2014 | volatility-conditioned-history | 0.037339 |
| expanding | 2015 | volatility-conditioned-history | 0.048791 |
| expanding | 2016 | unconditional-history | 0.058287 |
| rolling | 2013 | fixed-cycle-score | 0.069273 |
| rolling | 2014 | volatility-conditioned-history | 0.037501 |
| rolling | 2015 | position-plus-direction | 0.042734 |
| rolling | 2016 | fixed-cycle-score | 0.036988 |

## Sensitivity to excluding a year

These calculations reuse saved forecasts; they do not retrain models. They are post-output sensitivity checks, not additional validation samples.

| Mode | Excluded origin year | Lowest-CRPS model on remaining dates | CRPS |
|---|---|---|---:|
| expanding | 2013 | volatility-conditioned-history | 0.046904 |
| expanding | 2014 | unconditional-history | 0.064542 |
| expanding | 2015 | unconditional-history | 0.063343 |
| expanding | 2016 | direction-only | 0.056219 |
| rolling | 2013 | volatility-conditioned-history | 0.043648 |
| rolling | 2014 | valuation-only | 0.058645 |
| rolling | 2015 | fixed-cycle-score | 0.058420 |
| rolling | 2016 | regularized-cycle | 0.053928 |

PIT histograms, positive-excess-return Brier scores, and every model/year result are in [report.json](report.json). Positive excess return is not a drawdown event or a policy backtest.

Coverage alone does not establish calibration: wide intervals can cover nearly every outcome. No interval rescaling is selected from this small sample.
