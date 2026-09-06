# TARGET-TOURNAMENT-001

## Final result

`TARGET-TOURNAMENT-001` is complete with `NO_TARGET_ADEQUATE`; no V1 target was
frozen. The earlier Yahoo run remains a pipeline fixture only. The acceptance
run uses immutable Alpaca SIP SPY/QQQ bars and free Massive Futures Basic ES/NQ
bars from 2024-09-03 through 2026-09-03.

```text
dataset:          phase1-market-e70bdc3ff5238003
dataset hash:     e70bdc3ff5238003978778e6f3f7636eb120f16258a5a9066003e85da029c1e9
normalized bars: 779,985
report hash:      cd393a5b710cd17692648d10e0418be07e7391a7eeb030f6d52371d4c6523072
decision:         NO_TARGET_ADEQUATE
```

Run or resume the workflow with `npm run phase1`. Reproduce it without network
access using `npm run phase1 -- --offline`; every page's request, count, and hash
is verified before reuse.

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

## Acceptance evidence

Every one of the 24 candidates has exactly 100 observations in the sealed final
chronological confirmation segment. Candidate coverage is at least 98.77%.
SPY, QQQ, ES, and NQ all pass cross-provider comparison against pinned IBKR
history; their maximum close differences are below 0.60 bps.

No candidate passed the material Brier-improvement, incremental-economic-value,
stress-cost, and stability gates together. A preliminary validation run showed
that a zero improvement threshold could promote numerically trivial logistic
smoothing that made the same directional decisions as historical frequencies.
The final acceptance policy requires an absolute 0.005 Brier improvement and
incremental net return, and conservatively rejects all candidates.

No LLM runtime, account query, order construction, or order-submission code is
used by this workflow.

## Production-quality provider gate

Databento was evaluated as the technically strongest provenance option because
it distinguishes event and receive timestamps, but it was rejected on cost for
the current pre-signal-discovery phase. The low-cost plan is now Alpaca
historical SIP bars for SPY/QQQ, Massive Futures Basic for two years of ES/NQ,
and the existing IBKR account for live capture and recent-history validation.

The cheaper historical providers do not supply Databento-style revision
lineage. Every raw response is therefore frozen and content-hashed, backfilled
bars are marked `event-time-only`, futures use 18 verified explicit contracts
and fixed roll mappings, and overlapping IBKR history is used for quality
comparison. This provenance is accepted for target selection only; it is not
misrepresented as replay-safe first-seen history.

Any future target-search extension must be separately preregistered and must
not rewrite this completed result. No paid data upgrade is planned.
