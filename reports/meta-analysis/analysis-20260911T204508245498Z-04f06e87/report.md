# META analysis research packet

Cutoff: 2026-09-11T20:45:08.098859+00:00

Independent cycle proxies. Reference probabilities are uncalibrated assumptions. Agent views are qualitative.

| Symbol | Price date | Close | RV63 | Price / SMA200 | Status |
|---|---|---:|---:|---:|---|
| SPY | 2026-09-11 | 764.29 | 12.12% | 1.0701 | FRESH |
| QQQ | 2026-09-11 | 714.88 | 22.39% | 1.0829 | FRESH |
| AAPL | 2026-09-11 | 332.27 | 32.12% | 1.1661 | FRESH |
| MSFT | 2026-09-11 | 495.63 | 41.43% | 1.1493 | FRESH |
| NVDA | 2026-09-11 | 218.29 | 40.00% | 1.1054 | FRESH |

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
| VIXCLS | 2026-09-10 | 17.8400 | percent_annualized | FRESH |
| VXVCLS | 2026-09-10 | 19.7300 | percent_annualized | FRESH |
| DFF | 2026-09-10 | 3.6300 | percent | FRESH |
| T10Y2Y | 2026-09-10 | 0.3900 | percentage_points | FRESH |
| MPRIME | 2026-08-01 | 6.7500 | percent | FRESH |
| GS3M | 2026-08-01 | 3.8800 | percent | FRESH |
| NFCI | 2026-09-04 | -0.5640 | standard_deviations | FRESH |
| STLFSI4 | 2026-09-04 | -0.7884 | index | FRESH |
| CPIAUCSL | 2026-08-01 | 334.1310 | index | FRESH |
| INDPRO | 2026-07-01 | 102.9939 | index | FRESH |
| lending_rate_proxy | 2026-08-01 | 287.0000 | basis_points | FRESH |
| vix_term_structure_proxy | 2026-09-10 | 0.9042 | VIX/VIX3M ratio | FRESH |
| survey_fear_greed | — | — | — | MISSING |

## Assumption-based terminal-price reference

Central 80% model interval (10th–90th percentiles), not empirically calibrated coverage. Zero log drift: probability of finishing above the reference close is 50% by construction. These numbers do not incorporate cycle or agent directional views.

| Symbol | Sessions | Bear/bull return boundary | 10th–90th price | Bear / neutral / bull |
|---|---:|---:|---|---|
| SPY | 5 | ±2% | 747.75–781.19 | 11.8% / 75.9% / 12.3% |
| SPY | 21 | ±5% | 730.78–799.33 | 7.1% / 84.7% / 8.2% |
| SPY | 63 | ±10% | 707.19–826.00 | 4.1% / 90.1% / 5.8% |
| QQQ | 5 | ±2% | 686.56–744.37 | 26.1% / 47.4% / 26.5% |
| QQQ | 21 | ±5% | 658.04–776.63 | 21.4% / 56.1% / 22.5% |
| QQQ | 63 | ±10% | 619.32–825.19 | 17.3% / 62.9% / 19.7% |
| AAPL | 5 | ±2% | 313.55–352.11 | 32.8% / 34.2% / 33.1% |
| AAPL | 21 | ±5% | 295.04–374.20 | 29.0% / 41.1% / 29.9% |
| AAPL | 63 | ±10% | 270.46–408.21 | 25.6% / 46.8% / 27.6% |
| MSFT | 5 | ±2% | 459.91–534.12 | 36.5% / 26.8% / 36.7% |
| MSFT | 21 | ±5% | 425.20–577.73 | 33.4% / 32.4% / 34.2% |
| MSFT | 63 | ±10% | 380.07–646.33 | 30.6% / 37.2% / 32.3% |
| NVDA | 5 | ±2% | 203.08–234.64 | 36.0% / 27.7% / 36.3% |
| NVDA | 21 | ±5% | 188.26–253.11 | 32.8% / 33.5% / 33.6% |
| NVDA | 63 | ±10% | 168.93–282.07 | 29.9% / 38.4% / 31.7% |

Fundamentals, political exposure and material news require the specialist evidence review.
See packet.json for source timestamps, macro/credit values and conditional terminal-price ranges.
Specialist execution is separate; generated prompts are not completed agent analyses.
