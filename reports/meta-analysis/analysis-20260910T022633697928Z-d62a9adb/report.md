# META analysis research packet

Cutoff: 2026-09-10T02:25:49.645619+00:00

Independent cycle proxies. Reference probabilities are uncalibrated assumptions. Agent views are qualitative.

| Symbol | Price date | Close | RV63 | Price / SMA200 | Status |
|---|---|---:|---:|---:|---|
| SPY | 2026-09-09 | 762.40 | 12.82% | 1.0690 | FRESH |
| QQQ | 2026-09-09 | 716.31 | 23.56% | 1.0871 | FRESH |
| AAPL | 2026-09-09 | 315.34 | 31.35% | 1.1090 | FRESH |
| MSFT | 2026-09-09 | 491.65 | 41.81% | 1.1405 | FRESH |
| NVDA | 2026-09-09 | 223.67 | 40.68% | 1.1349 | FRESH |

## Cycle and market evidence

Values have different observation dates. FRESH uses explicit age limits; it does not mean a same-day release.

| Indicator | Observation date | Value | Unit | Status |
|---|---|---:|---|---|
| VIXCLS | 2026-09-08 | 15.7200 | percent_annualized | FRESH |
| DFF | 2026-09-08 | 3.6300 | percent | FRESH |
| T10Y2Y | 2026-09-09 | 0.4000 | percentage_points | FRESH |
| MPRIME | 2026-08-01 | 6.7500 | percent | FRESH |
| GS3M | 2026-08-01 | 3.8800 | percent | FRESH |
| NFCI | 2026-08-28 | -0.5580 | standard_deviations | FRESH |
| STLFSI4 | 2026-09-04 | -0.7884 | index | FRESH |
| CPIAUCSL | 2026-07-01 | 332.8130 | index | FRESH |
| INDPRO | 2026-07-01 | 102.9939 | index | FRESH |
| lending_rate_proxy | 2026-08-01 | 287.0000 | basis_points | FRESH |
| survey_fear_greed | — | — | — | MISSING |

## Assumption-based terminal-price reference

Central 80% model interval (10th–90th percentiles), not empirically calibrated coverage. Zero log drift: probability of finishing above the reference close is 50% by construction. These numbers do not incorporate cycle or agent directional views.

| Symbol | Sessions | Bear/bull return boundary | 10th–90th price | Bear / neutral / bull |
|---|---:|---:|---|---|
| SPY | 5 | ±2% | 744.96–780.25 | 13.2% / 73.2% / 13.6% |
| SPY | 21 | ±5% | 727.09–799.43 | 8.3% / 82.3% / 9.4% |
| SPY | 63 | ±10% | 702.28–827.67 | 5.0% / 88.1% / 6.9% |
| QQQ | 5 | ±2% | 686.48–747.43 | 27.1% / 45.3% / 27.5% |
| QQQ | 21 | ±5% | 656.52–781.55 | 22.5% / 53.8% / 23.7% |
| QQQ | 63 | ±10% | 615.94–833.04 | 18.6% / 60.5% / 20.9% |
| AAPL | 5 | ±2% | 297.99–333.70 | 32.4% / 34.9% / 32.7% |
| AAPL | 21 | ±5% | 280.81–354.11 | 28.5% / 42.0% / 29.5% |
| AAPL | 63 | ±10% | 257.96–385.49 | 25.1% / 47.8% / 27.2% |
| MSFT | 5 | ±2% | 455.90–530.20 | 36.6% / 26.6% / 36.8% |
| MSFT | 21 | ±5% | 421.18–573.90 | 33.5% / 32.2% / 34.3% |
| MSFT | 63 | ±10% | 376.09–642.72 | 30.7% / 36.9% / 32.4% |
| NVDA | 5 | ±2% | 207.84–240.71 | 36.2% / 27.3% / 36.5% |
| NVDA | 21 | ±5% | 192.42–259.99 | 33.1% / 33.0% / 33.9% |
| NVDA | 63 | ±10% | 172.35–290.27 | 30.2% / 37.8% / 32.0% |

Fundamentals, political exposure and material news require the specialist evidence review.
See packet.json for source timestamps, macro/credit values and conditional terminal-price ranges.
Specialist execution is separate; generated prompts are not completed agent analyses.
