# Verified current macro snapshot and pending price capture

2026-09-09. The secondary notebooks now have an observed-data input beyond their
synthetic examples. This first snapshot is deliberately **macro-only**. It cannot
support a complete market/instrument assessment; both SPY and QQQ reports abstain
with missing inputs visible.

Snapshot root: `datasets/workbench/current-20260909-macro`.
Cutoff/first-seen bound: `2026-09-09T15:28:59.500746+00:00`.

The Federal Reserve's August 18, 2026 G.17 release reports **July industrial
production 1.1% above July 2025**, seasonally adjusted and preliminary. We extracted
the narrative value and independently parsed the corresponding Total IP year-on-year
cell in Table 1, requiring matching values, release dates and observation year.
These are two extraction routes from the **same publisher**, not two independent
economic estimates. [Fed release](https://www.federalreserve.gov/releases/g17/20260818/default.htm),
[Table 1](https://www.federalreserve.gov/releases/g17/20260818/table1.htm).

Both original HTML files are archived with SHA256 in
[verification.json](../datasets/workbench/current-20260909-macro/verification.json).
Date-only publication is conservatively admitted at the end of August 18. The
first-seen time is the current verification instant; no historical first-seen
claim is inferred from the dated release. The latest-release source was checked
on the Fed website at acquisition. The 75-day observation-age allowance is an
explicit snapshot choice for this monthly release, not a daily freshness claim.

The [SPY manifest](../datasets/workbench/current-20260909-macro/SPY-manifest.json)
and [QQQ manifest](../datasets/workbench/current-20260909-macro/QQQ-manifest.json)
pin their raw-metric extracts, which use the existing illustrative growth transform.
JSON/HTML assessments and input-audit receipts are under `assessments/SPY` and
`assessments/QQQ`. Only industrial production is currently measured. Credit,
psychology, realized volatility, timing, ETF quality and ETF valuation remain
missing. No synthetic row fills a gap, and no company P/E or operating margin
is passed off as ETF fundamentals.

`cycle_workbench_snapshot.py` also implements a bounded read-only IBKR capture:
resolve exact SPY/QQQ stock contracts, request one year of regular-session daily
TRADES bars, and archive replies separately from Cycle 1. The metric verifier
requires 200 consecutive scheduled closes through the latest completed session,
rejects duplicates/gaps/stale captures/invalid OHLC, and excludes the current
unfinished session. It cross-checks NumPy and scalar calculations of price/SMA200
and 63-session sample log-return volatility annualized by sqrt(252). These are
split-adjusted **price** statistics excluding cash dividends. SPY volatility
represents the broad-equity stress proxy in both instrument reports; QQQ volatility
is a separate diagnostic. Today's historical download is not a historical
point-in-time panel.

Gateway connection attempts failed at localhost:4002. Once the read-only paper
Gateway is running, capture into the already prepared, separate full-snapshot root:

```bash
IBKR_MODE=paper IBKR_READ_ONLY=true npm run cycle:current-snapshot -- capture-prices --root datasets/workbench/current-20260909
npm run cycle:current-snapshot -- build --root datasets/workbench/current-20260909
```

That root already contains the pinned Fed source files but no published manifests.
The macro-only snapshot remains immutable. Switch both notebooks' `WORKBENCH_INPUT_ROOT`
to the completed full-snapshot directory after its verification succeeds. Do not
overwrite a published snapshot to refresh it; create a separately identified one.
The notebook workbench panels use observed inputs; their earlier educational
price-history charts and six scenario comparisons remain explicitly synthetic.

Public-source verification and deterministic calculation checks establish this
snapshot's stated scope, not predictive value or a qualified allocation policy.
This track cannot reopen either stopped Cycle 1 experiment.

Verification: both notebooks executed end-to-end on this macro-only snapshot;
executed copies are in `/tmp/cycle-workbench-current-check`. `npm run check`
passed (15 TypeScript and 296 Python tests), including source cross-checks,
independent price-metric arithmetic, missing-session rejection and cutoff tests.
