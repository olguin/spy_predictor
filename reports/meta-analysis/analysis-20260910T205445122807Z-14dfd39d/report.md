# META analysis research packet

Cutoff: 2026-09-10T20:54:33.154432+00:00

Independent cycle proxies. Reference probabilities are uncalibrated assumptions. Agent views are qualitative.

| Symbol | Price date | Close | RV63 | Price / SMA200 | Status |
|---|---|---:|---:|---:|---|
| SPY | 2026-09-10 | 757.83 | 12.45% | 1.0618 | FRESH |
| QQQ | 2026-09-10 | 708.69 | 23.30% | 1.0746 | FRESH |
| AAPL | 2026-09-10 | 326.57 | 32.06% | 1.1473 | FRESH |
| MSFT | 2026-09-10 | 492.44 | 41.65% | 1.1422 | FRESH |
| NVDA | 2026-09-10 | 218.36 | 40.22% | 1.1069 | FRESH |

## Fundamental and ETF evidence

| Symbol | Evidence type | Coverage | Latest period/as-of |
|---|---|---|---|
| SPY | Sponsor holdings table/export | 10 holdings / 38.00% weight | 2026-09-09 |
| QQQ | ETF holdings | MISSING | — |
| AAPL | SEC company facts | 12 standardized metrics | 2026-06-27 |
| MSFT | SEC company facts | 12 standardized metrics | 2026-06-30 |
| NVDA | SEC company facts | 11 standardized metrics | 2026-07-26 |

## Cycle and market evidence

Values have different observation dates. FRESH uses explicit age limits; it does not mean a same-day release.

| Indicator | Observation date | Value | Unit | Status |
|---|---|---:|---|---|
| VIXCLS | 2026-09-09 | 16.4600 | percent_annualized | FRESH |
| DFF | 2026-09-09 | 3.6300 | percent | FRESH |
| T10Y2Y | 2026-09-09 | 0.4000 | percentage_points | FRESH |
| MPRIME | 2026-08-01 | 6.7500 | percent | FRESH |
| GS3M | 2026-08-01 | 3.8800 | percent | FRESH |
| NFCI | 2026-09-04 | -0.5640 | standard_deviations | FRESH |
| STLFSI4 | 2026-09-04 | -0.7884 | index | FRESH |
| CPIAUCSL | 2026-07-01 | 332.8130 | index | FRESH |
| INDPRO | 2026-07-01 | 102.9939 | index | FRESH |
| lending_rate_proxy | 2026-08-01 | 287.0000 | basis_points | FRESH |
| survey_fear_greed | — | — | — | MISSING |

## Assumption-based terminal-price reference

Central 80% model interval (10th–90th percentiles), not empirically calibrated coverage. Zero log drift: probability of finishing above the reference close is 50% by construction. These numbers do not incorporate cycle or agent directional views.

| Symbol | Sessions | Bear/bull return boundary | 10th–90th price | Bear / neutral / bull |
|---|---:|---:|---|---|
| SPY | 5 | ±2% | 740.99–775.06 | 12.5% / 74.6% / 12.9% |
| SPY | 21 | ±5% | 723.71–793.56 | 7.7% / 83.6% / 8.7% |
| SPY | 63 | ±10% | 699.71–820.77 | 4.5% / 89.2% / 6.3% |
| QQQ | 5 | ±2% | 679.50–739.14 | 26.9% / 45.8% / 27.3% |
| QQQ | 21 | ±5% | 650.15–772.50 | 22.3% / 54.3% / 23.4% |
| QQQ | 63 | ±10% | 610.39–822.82 | 18.3% / 61.0% / 20.7% |
| AAPL | 5 | ±2% | 308.21–346.03 | 32.7% / 34.2% / 33.1% |
| AAPL | 21 | ±5% | 290.04–367.69 | 29.0% / 41.1% / 29.9% |
| AAPL | 63 | ±10% | 265.92–401.05 | 25.6% / 46.8% / 27.6% |
| MSFT | 5 | ±2% | 456.77–530.89 | 36.5% / 26.7% / 36.8% |
| MSFT | 21 | ±5% | 422.12–574.48 | 33.5% / 32.3% / 34.2% |
| MSFT | 63 | ±10% | 377.09–643.08 | 30.6% / 37.0% / 32.4% |
| NVDA | 5 | ±2% | 203.07–234.80 | 36.1% / 27.6% / 36.3% |
| NVDA | 21 | ±5% | 188.17–253.39 | 32.9% / 33.4% / 33.7% |
| NVDA | 63 | ±10% | 168.75–282.55 | 30.0% / 38.2% / 31.8% |

Fundamentals, political exposure and material news require the specialist evidence review.
See packet.json for source timestamps, macro/credit values and conditional terminal-price ranges.
Specialist execution is separate; generated prompts are not completed agent analyses.
