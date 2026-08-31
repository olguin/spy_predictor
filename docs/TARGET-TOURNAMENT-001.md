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

The selected next provider is Databento Historical because its normalized
records distinguish event time from capture-server receive time (`ts_recv`),
and its historical filtering uses the schema's index timestamp. Its official
documentation also supports one-minute OHLCV and continuous futures symbology.
An API key and licensed dataset selection are required, so acquisition is not
silently substituted with weaker data.

- Timestamp semantics: https://databento.com/docs/standards-and-conventions/common-fields-enums-types
- OHLCV schema: https://databento.com/docs/schemas-and-data-formats
- Historical API key requirement: https://databento.com/docs/quickstart
- Continuous futures: https://databento.com/docs/standards-and-conventions/symbology

Before a target can be frozen, a credentialed run must archive raw DBN/metadata,
preserve `ts_recv`/`ts_event`, resolve equity venue coverage, record continuous
contract mappings and roll boundaries, apply corporate actions point in time,
and meet the configured observation gate across all candidates.
