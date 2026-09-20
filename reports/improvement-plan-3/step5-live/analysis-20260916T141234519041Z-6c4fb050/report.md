# META analysis research packet

Cutoff: 2026-09-16T14:10:10.463607+00:00

Independent cycle proxies. Reference probabilities are uncalibrated assumptions. Agent views are qualitative.

| Symbol | Price date | Close | RV63 | Price / SMA200 | Status |
|---|---|---:|---:|---:|---|
| ANET | 2026-09-15 | 192.84 | 57.37% | 1.2517 | FRESH |
| QQQ | 2026-09-15 | 704.54 | 21.53% | 1.0656 | FRESH |
| MU | 2026-09-15 | 927.60 | 91.12% | 1.4745 | FRESH |
| META | 2026-09-15 | 670.24 | 46.06% | 1.0747 | FRESH |
| NVDA | 2026-09-15 | 212.17 | 40.03% | 1.0727 | FRESH |

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
| VIXCLS | 2026-09-15 | 17.2000 | percent_annualized | FRESH |
| VXVCLS | 2026-09-15 | 19.3600 | percent_annualized | FRESH |
| DFF | 2026-09-14 | 3.6300 | percent | FRESH |
| T10Y2Y | 2026-09-15 | 0.3300 | percentage_points | FRESH |
| MPRIME | 2026-08-01 | 6.7500 | percent | FRESH |
| GS3M | 2026-08-01 | 3.8800 | percent | FRESH |
| NFCI | 2026-09-11 | -0.5600 | standard_deviations | FRESH |
| STLFSI4 | 2026-09-04 | -0.7884 | index | FRESH |
| CPIAUCSL | 2026-08-01 | 334.1310 | index | FRESH |
| INDPRO | 2026-07-01 | 102.9939 | index | FRESH |
| DGS2 | 2026-09-14 | 4.6500 | percent | FRESH |
| DGS5 | 2026-09-14 | 4.8000 | percent | FRESH |
| DGS10 | 2026-09-14 | 4.9700 | percent | FRESH |
| DGS30 | 2026-09-14 | 5.3400 | percent | FRESH |
| T10Y3M | 2026-09-15 | 0.8900 | percentage_points | FRESH |
| DFII10 | 2026-09-14 | 2.6000 | percent | FRESH |
| T10YIE | 2026-09-15 | 2.3800 | percent | FRESH |
| SOFR | 2026-09-15 | 3.6400 | percent | FRESH |
| NFCICREDIT | 2026-09-11 | -0.0710 | standard_deviations | FRESH |
| DTWEXBGS | 2026-09-11 | 118.2126 | index | FRESH |
| DCOILWTICO | 2026-09-09 | 97.2600 | usd_per_barrel | FRESH |
| lending_rate_proxy | 2026-08-01 | 287.0000 | basis_points | FRESH |
| vix_term_structure_proxy | 2026-09-15 | 0.8884 | VIX/VIX3M ratio | FRESH |
| survey_fear_greed | — | — | — | MISSING |
| current_volatility | — | — | — | MISSING_INTRADAY |

## Assumption-based terminal-price reference

Central 80% model interval (10th–90th percentiles), not empirically calibrated coverage. Zero log drift: probability of finishing above the reference close is 50% by construction. These numbers do not incorporate cycle or agent directional views.

| Symbol | Sessions | Bear/bull return boundary | 10th–90th price | Bear / neutral / bull |
|---|---:|---:|---|---|
| ANET | 5 | ±2% | 173.87–213.88 | 40.1% / 19.6% / 40.3% |
| ANET | 21 | ±5% | 155.96–238.43 | 37.8% / 23.7% / 38.4% |
| ANET | 63 | ±10% | 133.52–278.51 | 35.7% / 27.3% / 37.0% |
| QQQ | 5 | ±2% | 677.68–732.47 | 25.3% / 49.0% / 25.7% |
| QQQ | 21 | ±5% | 650.59–762.96 | 20.5% / 57.9% / 21.6% |
| QQQ | 63 | ±10% | 613.74–808.78 | 16.4% / 64.8% / 18.8% |
| MU | 5 | ±2% | 786.91–1093.45 | 43.7% / 12.4% / 43.9% |
| MU | 21 | ±5% | 662.15–1299.47 | 42.3% / 15.1% / 42.6% |
| MU | 63 | ±10% | 517.35–1663.18 | 40.9% / 17.4% / 41.7% |
| META | 5 | ±2% | 616.76–728.35 | 37.8% / 24.2% / 38.0% |
| META | 21 | ±5% | 565.23–794.76 | 35.0% / 29.3% / 35.7% |
| META | 63 | ±10% | 498.94–900.35 | 32.4% / 33.7% / 33.9% |
| NVDA | 5 | ±2% | 197.38–228.07 | 36.0% / 27.7% / 36.3% |
| NVDA | 21 | ±5% | 182.97–246.04 | 32.9% / 33.5% / 33.6% |
| NVDA | 63 | ±10% | 164.17–274.21 | 29.9% / 38.4% / 31.7% |

Fundamentals, political exposure and material news require the specialist evidence review.
See packet.json for source timestamps, macro/credit values and conditional terminal-price ranges.
Specialist execution is separate; generated prompts are not completed agent analyses.
