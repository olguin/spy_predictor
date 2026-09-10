# META prospective observation operations

This runbook covers the separate META watchlist ledger. It does not modify the
stopped Cycle 1 experiments, open a historical holdout, trade, or qualify an
investment strategy.

## Post-close issue workflow

The one-command quant-only workflow is:

```bash
npm run meta:postclose -- \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ \
  --etf-holdings SPY=/path/to/current-spy-holdings.csv \
  --etf-holdings QQQ=/path/to/browser-saved-current-qqq-holdings.csv \
  --ibkr-delayed-context=/path/to/quotes.json
```

It is allowed only from 20 minutes after an XNYS close until the next XNYS open.
Before downloading anything it rejects a duplicate symbol/origin already in the
forecast ledger. It then captures fresh prices, macro data, bounded news, SEC
evidence and configured optional sources; builds and validates the packet; and
registers the immutable quant-only observation. Validation requires the completed
origin close for every symbol, all 5/21/63-session scenarios, current FRED inputs,
and normalized SEC evidence for each stock. A supplied holdings file must be no
more than seven calendar days old. Missing unsupplied ETF holdings remain a visible
optional gap.

Inspect the guard without downloading:

```bash
npm run meta:postclose -- \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ --preflight-only
```

The September 10 origin currently returns `DUPLICATE_ORIGIN`, as intended.

## Delayed IBKR context

To capture quote-only context with an explicit futures rollover rule:

```bash
npm run ibkr:delayed -- \
  --auto-roll-futures --minimum-days-to-expiry 10 --duration-seconds 15
```

This chooses the first catalog contract whose expiration is at least ten calendar
days away and records the exact contract decision. Pass its `quotes.json` to the
post-close command. The META importer requires type-3 delayed data, validates its
timestamps, ignores IBKR's `-1` unavailable bid/ask sentinel, and refuses captures
older than two hours. Delayed values remain context and are never substituted for
the official split-adjusted terminal close.

## Outcome and score workflow

Status is always read-only:

```bash
npm run meta:outcomes -- status
```

The states are:

- `NOT_DUE`: target close plus the 20-minute buffer has not arrived.
- `WAITING_FOR_DATA`: the target is mature but no immutable outcome exists.
- `READY`: an outcome exists and has not been scored.
- `SCORED`: the immutable score exists.

Acquire every due close and score every ready record with one command:

```bash
npm run meta:outcomes -- update
```

Outcome files and score files are stored separately under
`datasets/meta-observation/`, keyed by the full forecast hash. The original
forecast is never edited. Raw Alpaca responses are archived with URL, feed,
adjustment convention and content hash. Scores include bear/neutral/bull Brier
and log loss, probability-up Brier, direction accuracy only when the forecast
makes a non-50/50 call, quantile pinball loss, central 80/90% interval coverage,
median price error and analytic lognormal CRPS for the current quantitative
reference. Aggregate summaries remain descriptive because horizons overlap and
the early sample is far too small to establish calibration or skill.

The first five-session targets mature on September 17, 2026 at 20:20 UTC. Until
then, `update` is an idempotent no-op and needs no market-data request.

## Source policy

QQQ holdings stay on the validated manual sponsor-export path. The audited
Invesco terms do not support assuming permission for scheduled scraping. Refresh
the browser-saved input when a fresh report needs it; do not repeatedly automate
the browser-facing JSON endpoint. SEC access uses the configured identifying
`SEC_USER_AGENT`, conservative pacing and bounded retry policy described in the
[META plan](META_ANALYSIS_PLAN.md).
