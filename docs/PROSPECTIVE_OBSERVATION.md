# Prospective observation cohort v1

Registered 2026-09-09 after the first development run and its stability review.
This cohort is the next evidence-acquisition step. It does not trade, allocate,
open the reserved historical evaluation period, or claim that a model is
qualified for deployment.

## Decision

The first development run has only 42 common scored origins per mode, with
overlapping 12-month outcomes. Model rankings change materially by origin year
and under leave-one-year-out diagnostics. The cycle models did not beat every
fixed baseline in both modes. Searching this small sample for another winner
would spend the remaining development evidence without creating independence.

The cohort therefore freezes the simplest reference:
`unconditional-history-expanding-static`. Its empirical distribution consists
of the 161 complete, mature development labels available to the June 30, 2016
expanding fold. It has no current feature inputs and no update rule during the
cohort. This is intentionally a benchmark for prospective calibration and
operational integrity, not a selected predictive winner.

The frozen annual excess-log-return distribution has mean 0.0532 and median
0.0895. Its 5th/25th/75th/95th percentiles are -0.2605, -0.0112, 0.1569 and
0.2642. Those values describe the historical reference distribution; they are
not a current market call and will remain unchanged throughout the cohort.

Authority: [prospective-observation-v1.json](../config/prospective-observation-v1.json).
Registration:
[registration.json](../experiments/prospective-observation-415e6dcbc1f49640/registration.json).
Full cohort identity:
`415e6dcbc1f4964095147591850400e26d81eecb7840e46ab3b8b94483dc1592`.

The earlier local registrations `dab1b10fcb4de22f` and `9812125bf6189492` were
created while operational controls were being finalized. They issued no forecasts
and are superseded by the identity above. The final runner makes status strictly
read-only, records target endpoints, and reports any missed issue window.

## Schedule and controls

The cohort contains 12 literal XNYS month-end origins from September 30, 2026
through August 31, 2027. A forecast may be written only after that origin's XNYS
close and before the next XNYS session opens. Status checks never issue a
forecast. Missed issue windows remain missed; the runner does not backfill them.

Each forecast records the immutable distribution hash, predictive mean, 5/25/50/75/95
percentiles, issue time, forecast cutoff, and 12-month target endpoint. Outcomes
may be attached only to a previously issued forecast after their recorded
availability. Aggregate performance review remains closed until all 12 outcomes
mature. Because the outcomes overlap, even that review will be descriptive and
will not treat the 12 observations as independent replications.

```bash
npm run prospective:status
npm run prospective:issue
```

The first issue window follows the September 30, 2026 market close. The first
annual outcome cannot mature before September 2027; the complete 12-origin cohort
cannot finish maturing before August 2028. No scheduler is deployed by this
registration. The issue command is ready for an external monthly scheduler or a
manual post-close run.

## Current operational snapshot

The formerly blocked current snapshot is complete at
`datasets/workbench/current-20260909`. Read-only IBKR captures contain complete,
verified 200-session SPY and QQQ windows through September 9, 2026. SPY closed
at 762.40, 6.90% above its 200-session mean, with 12.82% annualized 63-session
realized volatility. QQQ closed at 716.31, 8.71% above its mean, with 23.56%
volatility. These values are current descriptive evidence and are not inputs to
the static prospective forecast.

Credit, psychology, ETF quality, and fundamental valuation remain absent from
the workbench. The snapshot reports those components as missing. Its price
series and calculations passed session-continuity and independent arithmetic
checks. Both notebooks now default to this completed snapshot.

Verification on registration: `npm run check` passed 15 TypeScript and 316 Python
tests. Four cohort-specific tests cover the literal schedule, read-only status,
the narrow issue window, immutable repeat behavior, and outcome-availability
guards. Both notebooks executed successfully against the completed snapshot.
