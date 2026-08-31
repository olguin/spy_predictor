# TARGET-TOURNAMENT-001

## Current result

The first real-market qualification run produced
`NO_TARGET_ADEQUATE`. It exercised all instruments, horizons, baselines,
walk-forward modes, costs, and report artifacts, but it did not freeze V1.

The public Yahoo Chart qualification feed is intentionally marked
`pointInTimeSafe: false`: it does not expose original first-seen timestamps or
revision vintages, and its short intraday retention leaves fewer than the
configured 100 out-of-sample observations. Favorable metrics from this dataset
must not pass promotion gates.

The pinned dataset and report identities are content hashes of the provider
configuration and raw responses. Re-running without explicitly replacing the
raw directory reuses those bytes. No LLM runtime is imported or called.

## Implemented candidates

Instruments: SPY, QQQ, volume/front-month vendor series for ES and NQ.

Horizons: open to 15, 30, and 60 minutes; previous close to next open; open to
close; and close to next close.

Directional baselines: historical frequencies, always up/down, seeded random
calibrated probabilities, overnight continuation/reversal, momentum,
mean-reversion, L2 logistic regression, and a depth-limited tree.

Volatility baselines: historical mean and EWMA. Evaluation reports multiclass
Brier score, log loss, accuracy, expected calibration error, year and
volatility-regime breakdowns, and net returns under configurable round-trip
costs. Both expanding and rolling walk-forward modes are emitted.

## Production-quality provider gate

Databento was evaluated as the technically strongest provenance option because
it distinguishes event and receive timestamps, but it was rejected on cost for
the current pre-signal-discovery phase. The low-cost plan is now Alpaca
historical SIP bars for SPY/QQQ, Massive Futures Basic for two years of ES/NQ,
and the existing IBKR account for live capture and recent-history validation.

The cheaper historical providers do not supply Databento-style revision
lineage. Every raw response must therefore be frozen and content-hashed,
backfilled bars must be marked `event-time-only`, futures must use explicit
contract/roll mappings, and overlapping IBKR history must be used for quality
comparison. Locally captured IBKR live events will receive a genuine local
first-seen timestamp and become the strongest point-in-time dataset over time.

The detailed source analysis, operational constraints, links, and exact
implementation sequence are maintained in `docs/PROJECT_PLAN_AND_STATUS.md`.
No target can be frozen until sample, provenance, stability, calibration, and
cost gates pass together.
