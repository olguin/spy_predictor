# Verified current SPY/QQQ snapshot

Completed 2026-09-09. Snapshot root:
`datasets/workbench/current-20260909`. Cutoff:
`2026-09-10T00:29:26.933636+00:00` (September 9 in New York and Buenos Aires).

The read-only paper Gateway resolved exact SPY and QQQ contracts and returned one
year of regular-session daily TRADES bars. The verifier selected 200 consecutive
XNYS sessions through September 9, rejected duplicates, gaps, stale captures and
invalid OHLC, and independently recomputed every reported price statistic using
NumPy and scalar arithmetic.

| Instrument | Latest close | Price / SMA200 | 63-session realized volatility |
|---|---:|---:|---:|
| SPY | 762.40 | 1.0690 | 12.82% |
| QQQ | 716.31 | 1.0871 | 23.56% |

The prices are split-adjusted and exclude cash dividends. Volatility is the
sample standard deviation of 63 daily log returns, annualized by sqrt(252).
SPY volatility supplies the broad-equity stress component in both assessments;
QQQ volatility is an instrument diagnostic. The current capture does not claim
historical point-in-time availability.

The Federal Reserve's August 18, 2026 G.17 release reports July industrial
production 1.1% above July 2025, seasonally adjusted and preliminary. The release
narrative and its Table 1 cell independently produce the same number; they remain
two extraction routes from one publisher. The HTML inputs and every price capture
are hash-pinned in [verification.json](../datasets/workbench/current-20260909/verification.json).

[SPY inputs](../datasets/workbench/current-20260909/SPY-manifest.json) and
[QQQ inputs](../datasets/workbench/current-20260909/QQQ-manifest.json) now include
growth, timing and stress measurements. Credit, psychology, ETF quality, and
fundamental valuation remain explicitly missing. The assessments therefore remain
conditional and cannot establish predictive performance or support an allocation.
No synthetic value fills a missing component.

Reports and input-audit receipts:

- [SPY assessment](../datasets/workbench/current-20260909/assessments/SPY/1d0e9a2fb4b544adc7763672028cf73977f8386b41395acc66eef1f1f86580b4.html)
- [QQQ assessment](../datasets/workbench/current-20260909/assessments/QQQ/23c4464ebda94cd0683ffea7b2ce0833964d5fad32e3e6187384827b4df57eb3.html)

Both notebooks now default to this full snapshot. The earlier
`current-20260909-macro` snapshot remains immutable as the initial macro-only
artifact. Refreshes must use a new directory instead of overwriting either
published snapshot.

The operational capture completed the previously blocked secondary increment.
It remains separate from Cycle 1 and from the
[prospective observation cohort](PROSPECTIVE_OBSERVATION.md).
