# META analysis research packet

Cutoff: 2026-09-15T14:30:31.852220+00:00

Independent cycle proxies. Reference probabilities are uncalibrated assumptions. Agent views are qualitative.

| Symbol | Price date | Close | RV63 | Price / SMA200 | Status |
|---|---|---:|---:|---:|---|
| ANET | 2026-09-14 | 187.81 | 57.55% | 1.2217 | FRESH |
| QQQ | 2026-09-14 | 709.18 | 22.42% | 1.0734 | FRESH |
| MU | 2026-09-14 | 924.03 | 93.53% | 1.4771 | FRESH |
| META | 2026-09-14 | 665.60 | 46.88% | 1.0675 | FRESH |
| NVDA | 2026-09-14 | 210.96 | 40.62% | 1.0675 | FRESH |

## Fundamental and ETF evidence

| Symbol | Evidence type | Coverage | Latest period/as-of |
|---|---|---|---|
| ANET | SEC company facts | 11 standardized metrics | 2026-06-30 |
| QQQ | Sponsor holdings table/export | 103 holdings / 100.05% weight | 2026-09-12 |
| MU | SEC company facts | 11 standardized metrics | 2026-05-28 |
| META | SEC company facts | 11 standardized metrics | 2026-06-30 |
| NVDA | SEC company facts | 11 standardized metrics | 2026-07-26 |

## Primary issuer, sector and policy evidence

Normalized records: 66. Supplemental acquisition failures remain visible and do not weaken the quant-only close guard.

| Family | Records |
|---|---:|
| issuer_event | 0 |
| issuer_release | 20 |
| sector_release | 20 |
| policy_event | 11 |
| policy_release | 15 |

## Cycle and market evidence

Values have different observation dates. FRESH uses explicit age limits; it does not mean a same-day release.

| Indicator | Observation date | Value | Unit | Status |
|---|---|---:|---|---|
| VIXCLS | 2026-09-14 | 17.1000 | percent_annualized | FRESH |
| VXVCLS | 2026-09-14 | 19.2800 | percent_annualized | FRESH |
| DFF | 2026-09-11 | 3.6300 | percent | FRESH |
| T10Y2Y | 2026-09-14 | 0.3200 | percentage_points | FRESH |
| MPRIME | 2026-08-01 | 6.7500 | percent | FRESH |
| GS3M | 2026-08-01 | 3.8800 | percent | FRESH |
| NFCI | 2026-09-04 | -0.5640 | standard_deviations | FRESH |
| STLFSI4 | 2026-09-04 | -0.7884 | index | FRESH |
| CPIAUCSL | 2026-08-01 | 334.1310 | index | FRESH |
| INDPRO | 2026-07-01 | 102.9939 | index | FRESH |
| DGS2 | 2026-09-11 | 4.6300 | percent | FRESH |
| DGS5 | 2026-09-11 | 4.7800 | percent | FRESH |
| DGS10 | 2026-09-11 | 4.9600 | percent | FRESH |
| DGS30 | 2026-09-11 | 5.3500 | percent | FRESH |
| T10Y3M | 2026-09-14 | 0.8600 | percentage_points | FRESH |
| DFII10 | 2026-09-11 | 2.6000 | percent | FRESH |
| T10YIE | 2026-09-14 | 2.3700 | percent | FRESH |
| SOFR | 2026-09-14 | 3.6200 | percent | FRESH |
| NFCICREDIT | 2026-09-04 | -0.0600 | standard_deviations | FRESH |
| DTWEXBGS | 2026-09-11 | 118.2126 | index | FRESH |
| DCOILWTICO | 2026-09-09 | 97.2600 | usd_per_barrel | FRESH |
| lending_rate_proxy | 2026-08-01 | 287.0000 | basis_points | FRESH |
| vix_term_structure_proxy | 2026-09-14 | 0.8869 | VIX/VIX3M ratio | FRESH |
| survey_fear_greed | — | — | — | MISSING |
| current_volatility | — | — | — | MISSING_INTRADAY |

## Assumption-based terminal-price reference

Central 80% model interval (10th–90th percentiles), not empirically calibrated coverage. Zero log drift: probability of finishing above the reference close is 50% by construction. These numbers do not incorporate cycle or agent directional views.

| Symbol | Sessions | Bear/bull return boundary | 10th–90th price | Bear / neutral / bull |
|---|---:|---:|---|---|
| ANET | 5 | ±2% | 169.28–208.37 | 40.2% / 19.5% / 40.3% |
| ANET | 21 | ±5% | 151.80–232.37 | 37.9% / 23.7% / 38.4% |
| ANET | 63 | ±10% | 129.89–271.56 | 35.7% / 27.3% / 37.0% |
| QQQ | 5 | ±2% | 681.05–738.47 | 26.1% / 47.4% / 26.5% |
| QQQ | 21 | ±5% | 652.74–770.50 | 21.4% / 56.1% / 22.5% |
| QQQ | 63 | ±10% | 614.29–818.73 | 17.4% / 62.9% / 19.8% |
| MU | 5 | ±2% | 780.48–1093.98 | 43.9% / 12.1% / 44.0% |
| MU | 21 | ±5% | 653.76–1306.03 | 42.5% / 14.7% / 42.8% |
| MU | 63 | ±10% | 507.48–1682.49 | 41.1% / 17.0% / 41.9% |
| META | 5 | ±2% | 611.59–724.38 | 38.0% / 23.8% / 38.2% |
| META | 21 | ±5% | 559.62–791.64 | 35.2% / 28.8% / 35.9% |
| META | 63 | ±10% | 492.90–898.80 | 32.7% / 33.1% / 34.2% |
| NVDA | 5 | ±2% | 196.05–227.01 | 36.2% / 27.3% / 36.5% |
| NVDA | 21 | ±5% | 181.53–245.16 | 33.1% / 33.0% / 33.9% |
| NVDA | 63 | ±10% | 162.62–273.67 | 30.2% / 37.9% / 31.9% |

Fundamentals, political exposure and material news require the specialist evidence review.
See packet.json for source timestamps, macro/credit values and conditional terminal-price ranges.
Specialist execution is separate; generated prompts are not completed agent analyses.
