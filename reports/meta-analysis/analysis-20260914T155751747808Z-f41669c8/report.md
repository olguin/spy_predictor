# META analysis research packet

Cutoff: 2026-09-14T15:57:51.402539+00:00

Independent cycle proxies. Reference probabilities are uncalibrated assumptions. Agent views are qualitative.

| Symbol | Price date | Close | RV63 | Price / SMA200 | Status |
|---|---|---:|---:|---:|---|
| ANET | 2026-09-11 | 199.59 | 56.66% | 1.3011 | FRESH |
| QQQ | 2026-09-11 | 714.88 | 22.39% | 1.0829 | FRESH |
| MU | 2026-09-11 | 975.26 | 92.95% | 1.5678 | FRESH |
| META | 2026-09-11 | 648.03 | 46.63% | 1.0398 | FRESH |
| NVDA | 2026-09-11 | 218.29 | 40.00% | 1.1054 | FRESH |

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
| VIXCLS | 2026-09-11 | 15.8400 | percent_annualized | FRESH |
| VXVCLS | 2026-09-11 | 18.6000 | percent_annualized | FRESH |
| DFF | 2026-09-10 | 3.6300 | percent | FRESH |
| T10Y2Y | 2026-09-11 | 0.3300 | percentage_points | FRESH |
| MPRIME | 2026-08-01 | 6.7500 | percent | FRESH |
| GS3M | 2026-08-01 | 3.8800 | percent | FRESH |
| NFCI | 2026-09-04 | -0.5640 | standard_deviations | FRESH |
| STLFSI4 | 2026-09-04 | -0.7884 | index | FRESH |
| CPIAUCSL | 2026-08-01 | 334.1310 | index | FRESH |
| INDPRO | 2026-07-01 | 102.9939 | index | FRESH |
| DGS2 | 2026-09-10 | 4.5600 | percent | FRESH |
| DGS5 | 2026-09-10 | 4.7500 | percent | FRESH |
| DGS10 | 2026-09-10 | 4.9500 | percent | FRESH |
| DGS30 | 2026-09-10 | 5.3700 | percent | FRESH |
| T10Y3M | 2026-09-11 | 0.8900 | percentage_points | FRESH |
| DFII10 | 2026-09-10 | 2.5500 | percent | FRESH |
| T10YIE | 2026-09-11 | 2.3600 | percent | FRESH |
| SOFR | 2026-09-11 | 3.6200 | percent | FRESH |
| NFCICREDIT | 2026-09-04 | -0.0600 | standard_deviations | FRESH |
| DTWEXBGS | 2026-09-04 | 118.0732 | index | STALE |
| DCOILWTICO | 2026-09-09 | 97.2600 | usd_per_barrel | FRESH |
| lending_rate_proxy | 2026-08-01 | 287.0000 | basis_points | FRESH |
| vix_term_structure_proxy | 2026-09-11 | 0.8516 | VIX/VIX3M ratio | FRESH |
| survey_fear_greed | — | — | — | MISSING |

## Assumption-based terminal-price reference

Central 80% model interval (10th–90th percentiles), not empirically calibrated coverage. Zero log drift: probability of finishing above the reference close is 50% by construction. These numbers do not incorporate cycle or agent directional views.

| Symbol | Sessions | Bear/bull return boundary | 10th–90th price | Bear / neutral / bull |
|---|---:|---:|---|---|
| ANET | 5 | ±2% | 180.19–221.08 | 40.0% / 19.8% / 40.2% |
| ANET | 21 | ±5% | 161.85–246.13 | 37.7% / 24.0% / 38.3% |
| ANET | 63 | ±10% | 138.83–286.95 | 35.5% / 27.7% / 36.8% |
| QQQ | 5 | ±2% | 686.56–744.37 | 26.1% / 47.4% / 26.5% |
| QQQ | 21 | ±5% | 658.04–776.63 | 21.4% / 56.1% / 22.5% |
| QQQ | 63 | ±10% | 619.32–825.19 | 17.3% / 62.9% / 19.7% |
| MU | 5 | ±2% | 824.62–1153.42 | 43.9% / 12.1% / 44.0% |
| MU | 21 | ±5% | 691.49–1375.49 | 42.4% / 14.8% / 42.8% |
| MU | 63 | ±10% | 537.60–1769.21 | 41.0% / 17.1% / 41.9% |
| META | 5 | ±2% | 595.72–704.94 | 37.9% / 23.9% / 38.2% |
| META | 21 | ±5% | 545.36–770.04 | 35.2% / 29.0% / 35.8% |
| META | 63 | ±10% | 480.66–873.68 | 32.6% / 33.3% / 34.1% |
| NVDA | 5 | ±2% | 203.08–234.64 | 36.0% / 27.7% / 36.3% |
| NVDA | 21 | ±5% | 188.26–253.11 | 32.8% / 33.5% / 33.6% |
| NVDA | 63 | ±10% | 168.93–282.07 | 29.9% / 38.4% / 31.7% |

Fundamentals, political exposure and material news require the specialist evidence review.
See packet.json for source timestamps, macro/credit values and conditional terminal-price ranges.
Specialist execution is separate; generated prompts are not completed agent analyses.
