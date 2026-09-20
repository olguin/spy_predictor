# META analysis research packet

Cutoff: 2026-09-17T01:02:25.784564+00:00

Independent cycle proxies. Reference probabilities are uncalibrated assumptions. Agent views are qualitative.

| Symbol | Price date | Close | RV63 | Price / SMA200 | Status |
|---|---|---:|---:|---:|---|
| ANET | 2026-09-16 | 197.54 | 57.51% | 1.2793 | FRESH |
| QQQ | 2026-09-16 | 704.72 | 21.21% | 1.0652 | FRESH |
| MU | 2026-09-16 | 926.55 | 90.27% | 1.4648 | FRESH |
| META | 2026-09-16 | 673.31 | 46.03% | 1.0793 | FRESH |
| NVDA | 2026-09-16 | 213.90 | 39.76% | 1.0806 | FRESH |

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
| VIXCLS | — | — | — | MISSING |
| VXVCLS | — | — | — | MISSING |
| DFF | — | — | — | MISSING |
| T10Y2Y | — | — | — | MISSING |
| MPRIME | — | — | — | MISSING |
| GS3M | — | — | — | MISSING |
| NFCI | — | — | — | MISSING |
| STLFSI4 | — | — | — | MISSING |
| CPIAUCSL | — | — | — | MISSING |
| INDPRO | — | — | — | MISSING |
| DGS2 | — | — | — | MISSING |
| DGS5 | — | — | — | MISSING |
| DGS10 | — | — | — | MISSING |
| DGS30 | — | — | — | MISSING |
| T10Y3M | — | — | — | MISSING |
| DFII10 | — | — | — | MISSING |
| T10YIE | — | — | — | MISSING |
| SOFR | — | — | — | MISSING |
| NFCICREDIT | — | — | — | MISSING |
| DTWEXBGS | — | — | — | MISSING |
| DCOILWTICO | — | — | — | MISSING |
| lending_rate_proxy | — | — | — | MISSING |
| vix_term_structure_proxy | — | — | — | MISSING |
| survey_fear_greed | — | — | — | MISSING |
| current_volatility | — | — | — | MISSING_INTRADAY |

## Assumption-based terminal-price reference

Central 80% model interval (10th–90th percentiles), not empirically calibrated coverage. Zero log drift: probability of finishing above the reference close is 50% by construction. These numbers do not incorporate cycle or agent directional views.

| Symbol | Sessions | Bear/bull return boundary | 10th–90th price | Bear / neutral / bull |
|---|---:|---:|---|---|
| ANET | 5 | ±2% | 178.06–219.15 | 40.2% / 19.5% / 40.3% |
| ANET | 21 | ±5% | 159.68–244.37 | 37.9% / 23.7% / 38.4% |
| ANET | 63 | ±10% | 136.65–285.56 | 35.7% / 27.3% / 37.0% |
| QQQ | 5 | ±2% | 678.25–732.22 | 24.9% / 49.7% / 25.4% |
| QQQ | 21 | ±5% | 651.54–762.24 | 20.1% / 58.6% / 21.3% |
| QQQ | 63 | ±10% | 615.17–807.31 | 16.0% / 65.5% / 18.4% |
| MU | 5 | ±2% | 787.23–1090.53 | 43.7% / 12.5% / 43.8% |
| MU | 21 | ±5% | 663.49–1293.90 | 42.2% / 15.2% / 42.6% |
| MU | 63 | ±10% | 519.60–1652.23 | 40.8% / 17.6% / 41.6% |
| META | 5 | ±2% | 619.63–731.64 | 37.8% / 24.2% / 38.0% |
| META | 21 | ±5% | 567.89–798.30 | 35.0% / 29.4% / 35.7% |
| META | 63 | ±10% | 501.34–904.27 | 32.4% / 33.7% / 33.9% |
| NVDA | 5 | ±2% | 199.08–229.82 | 35.9% / 27.9% / 36.2% |
| NVDA | 21 | ±5% | 184.64–247.80 | 32.7% / 33.7% / 33.5% |
| NVDA | 63 | ±10% | 165.79–275.97 | 29.8% / 38.6% / 31.6% |

Fundamentals, political exposure and material news require the specialist evidence review.
See packet.json for source timestamps, macro/credit values and conditional terminal-price ranges.
Specialist execution is separate; generated prompts are not completed agent analyses.
