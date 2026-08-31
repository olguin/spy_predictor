# TARGET-TOURNAMENT-001 qualification report

Dataset version: `yahoo-chart-08906e13b9c5c7f1`

Decision: **NO_TARGET_ADEQUATE**

No V1 target is frozen because the provider lacks first-seen/revision provenance and one or more candidates have fewer than 100 out-of-sample observations.

| Instrument | Horizon | Samples | OOS samples | Best expanding Brier | Best net return |
|---|---:|---:|---:|---:|---:|
| ES | close-next-close | 47 | 32 | 0.575651 | 0.050499 |
| ES | open-15m | 48 | 33 | 0.630055 | 0.010724 |
| ES | open-30m | 48 | 33 | 0.647602 | 0.013722 |
| ES | open-60m | 48 | 33 | 0.633775 | 0.013332 |
| ES | open-close | 48 | 33 | 0.639733 | 0.031179 |
| ES | previous-close-next-open | 48 | 33 | 0.610394 | 0.028238 |
| NQ | close-next-close | 47 | 32 | 0.523274 | 0.042441 |
| NQ | open-15m | 48 | 33 | 0.597805 | 0.041521 |
| NQ | open-30m | 48 | 33 | 0.616185 | 0.061996 |
| NQ | open-60m | 48 | 33 | 0.600698 | 0.060137 |
| NQ | open-close | 48 | 33 | 0.510395 | 0.042638 |
| NQ | previous-close-next-open | 48 | 33 | 0.554206 | 0.033088 |
| QQQ | close-next-close | 58 | 43 | 0.513362 | 0.013802 |
| QQQ | open-15m | 59 | 44 | 0.577433 | 0.041269 |
| QQQ | open-30m | 59 | 44 | 0.589436 | 0.035744 |
| QQQ | open-60m | 59 | 44 | 0.638534 | 0.047140 |
| QQQ | open-close | 59 | 44 | 0.518703 | 0.066107 |
| QQQ | previous-close-next-open | 59 | 44 | 0.542095 | 0.040105 |
| SPY | close-next-close | 58 | 43 | 0.559535 | 0.033611 |
| SPY | open-15m | 59 | 44 | 0.629765 | 0.005308 |
| SPY | open-30m | 59 | 44 | 0.643316 | 0.018403 |
| SPY | open-60m | 59 | 44 | 0.683986 | 0.003905 |
| SPY | open-close | 59 | 44 | 0.625479 | 0.053772 |
| SPY | previous-close-next-open | 59 | 44 | 0.559076 | 0.041343 |

## Data-quality gate

Yahoo Chart does not expose original first-seen timestamps or revision vintages; this run may qualify the pipeline but cannot freeze V1.

No LLM calls were made.
