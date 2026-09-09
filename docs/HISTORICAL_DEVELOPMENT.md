# Historical development track

Authorized 2026-09-09 by the user's instruction to qualify historical development
data and start walk-forward training against the fixed baselines, preserving the
stopped experiments and excluding the designated final evaluation period.

This is a separate development plan. It does not activate Cycle 1 v5, reopen
either power experiment, restore the consumed redesign slot, or authorize final
evaluation. The earlier strategy's dependency on passing synthetic power still
applies to its research qualification procedure. It does not govern this newly
authorized descriptive development run.

The executable authority is [historical-development-v1.json](../config/historical-development-v1.json).
It pins the existing feature/model specification and source manifest by SHA256,
plus both stopped decisions. Implementation is isolated in
[historical_development.py](../python/src/spy_predictor_quant/historical_development.py);
the registered experiment implementation files are unchanged.

## Dataset and qualification scope

Use SPY only. Reuse the pinned, hash-verified IBKR trades, sponsor cash
distributions, and ALFRED CPIAUCSL/INDPRO/MPRIME/GS3M normalized inputs. Verify all
198 raw resource hashes referenced by the source manifest. Never deserialize
the archived features or target files. Retain source limitations: ETF inputs
are reconstructed research evidence, and GS3M is a cash-yield proxy, not an
investable total-return index. No paid data or new source acquisition is used.

The separate dataset contains 200 development origins, November 1999–June 2016.
Prices needed for warmup begin January 1993. Label paths end no later than
June 30, 2017. Features end June 30, 2016. The embargo has no training or forecast
origins; its price observations are used only to finish development labels.
July 2017–July 2025 is excluded from development inputs, training, forecasts,
and scores. QQQ transfer and 24-month, downside and policy targets are not built.

Primary labels use equity total log return minus twelve actual/365 cash
accruals. All monthly endpoints and distribution ex-sessions must exist.
Publication timestamps must be strictly before each cash holding start and
feature cutoff. Missing macro revisions remove the prior observation instead
of resurrecting it. CPI is a causal feature input, not a release-delay gate on
the inflation-cancelling primary label. The spread change uses the exact common
observation month minus three.

### Pre-output missingness amendment

The first qualification attempt rejected two missing SPY daily sessions:
**2004-07-12 and 2007-07-02**. Both are also absent from the pinned raw TRADES and
ADJUSTED_LAST responses. Gateway port 4002 had no listening service. No prices
were invented or substituted.

Daily path completeness is necessary for volatility and trailing daily-high
features. Mark every origin whose longest configured daily window contains one
of these gaps unavailable; omit that origin from normalization history and
training, while retaining it in the monthly dataset. The existing window starts
after the first day of the month twelve months earlier, so each gap affects
13 origins. This leaves **174/200 complete feature origins (87%)**. Monthly
primary returns remain computable: all monthly endpoints and all 99 distribution
ex-sessions exist; missing non-action closes telescope out of the total-return
product. Daily drawdown targets are outside this dataset's qualification scope.

This amendment was documented before fitting any market candidate. It preserves
all **68 scheduled forecast months per mode**, November 2010–June 2016, and the
120-label minimum. **42 months per mode** have enough mature complete labels;
the first 26 remain unavailable. Counts are pinned and further changes fail
qualification before fitting. Neither 87% feature coverage nor 42 trainable
months meets the old Cycle 1 research requirements. The dataset is qualified
only for the explicit missingness-aware development scope above.

Qualification recomputes features/labels, checks all 2,400 monthly cash accruals,
validates session times and adjustment units, and proves identical reconstruction
after independently deserializing the bounded inputs. The new dataset and reports
are immutable and linked to code/config/source hashes. A separate durable backup
restore remains unverified; this workflow makes new local copies without migrating
or overwriting source archives.

## Fixed walk-forward run

Persist the 14-entry model/mode ledger before fitting. Use expanding and
180-calendar-month rolling training, with at least 120 complete labels whose
endpoint and availability are strictly earlier than the forecast cutoff. Do not
apply a second overlap purge. Fit preprocessing only on those training rows.

Retain the seven models and their existing fixed arithmetic: unconditional
history, volatility-conditioned history, position-only ridge (`valuation-only`),
direction-only ridge, position-plus-direction ridge, fixed cycle-score tertiles,
and regularized cycle. Ridge alpha remains 10 and minimum bin support 20.
There is no feature or hyperparameter search.

Store every scheduled forecast status, fitted predictive samples for available
forecasts, training origin lists, CRPS, RMSE and 90% interval coverage. Compare
each of the two cycle models against all five baselines on common dates within
each mode. These are descriptive development comparisons, not significance,
power, historical research qualification, or deployment evidence. Nearby annual
labels overlap and do not constitute independent observations.

Commands:

```bash
python/.venv/bin/python -m spy_predictor_quant.historical_development qualify
python/.venv/bin/python -m spy_predictor_quant.historical_development train --manifest datasets/historical-development/<identity>/manifest.json
```

`run` combines qualification and training. An identical completed run returns its
verified immutable report. Source, data, code or contract mismatches fail closed.
There is no final-evaluation CLI option. Tests cover future-price/vintage/outcome
invariance, strict maturity, missing revisions, session gaps, final-period
rejection, tampered artifacts, unavailable-date accounting, and exact resume.

## Current run

Completed 2026-09-09. [Readable results](../reports/historical-development/5ffd4a7b879d3237/summary.md)
and [machine-readable report](../reports/historical-development/5ffd4a7b879d3237/report.json).
`npm run check` passed: 15 TypeScript and 304 Python tests, including eight new
development tests. Offline reconstruction and completed-report resume reproduced
the same identities. Both stopped decision commands returned their expected
terminal statuses; all five stopped-experiment files retained identical hashes.
All seven models scored the same 42 months per mode, January 2013–June 2016;
26 earlier months per mode remain unavailable. Neither challenger beats every
fixed baseline in both modes. Lowest CRPS: unconditional history in expanding
mode (0.059738), position-only ridge in rolling mode (0.054885). No tuning followed
these outputs and no model was promoted.

Dataset: `datasets/historical-development/03608a029ae35517/manifest.json`.
Full identity: `03608a029ae355172a880777f31ac53ede175000678bc7798392319da3b217ad`.
Report identity: `9beaf08eb44d589c48622516bf09aa9847b11e9f94dc78acc45814b5a886a8a2`.
The earlier local preparation artifact `54d9cfcfa358f732` predates the final
missingness/count contract and code checks. It was never trained and is not an
accepted input to the current trainer.

## Gateway repair attempt, 2026-09-09

Gateway became available and the user authorized the planned repair/rerun.
The [repair audit](../reports/historical-development/gap-audit-6d79f6498c132ac6/summary.md)
records **DATA_REPAIR_NOT_QUALIFIED** after ten bounded read-only requests.
SMART daily and hourly windows omit both missing dates. AMEX also omits the
2004 session. ARCA supplies the 2007 session, but eight of nine neighboring
closes differ from the SMART archive, so it is not a compatible replacement.
No venue-specific bars were substituted, no new dataset was built, and no models
were refitted. The first run and all five stopped-experiment files retain their
hashes; final evaluation remains unopened.

New code: `historical_gap_capture.py` captures/replays four immutable request
bundles; `historical_gap_audit.py` verifies their hashes and checks bracketing
price compatibility. Thirteen targeted tests passed (five new repair-audit tests
and the eight development tests). All bundles replayed offline identically.
Raw captures remain in Git-ignored `datasets/historical-development/`.

Next bounded work: obtain and separately qualify a compatible historical source
or an IBKR data correction for the missing dates. Gateway connectivity is no
longer the blocker; source completeness and series compatibility are. Preserve
the first development scores, unchanged models, and the sealed final period.

## Follow-up: verify request correctness

The user challenged whether the Gateway was being queried correctly. Four more
bounded controls were captured: both SMART daily windows with `useRTH=0`, then
both windows using only conId 756733, SMART, USD and canonical UTC end times.
All still omit the target dates. The original callbacks save raw responses before
any feature or dataset filtering, so those omissions are not introduced by the
normalizer. Wider windows contain dates on both sides of each gap.

No request-construction defect has been demonstrated. A gap in the requested
SMART historical series is the leading interpretation, **not a confirmed root
cause**. The earlier statement that IBKR cannot provide the data was too broad;
we have established absence under the tested configurations only. A TWS chart
comparison and/or IBKR historical-data support diagnosis can help distinguish a
service data gap from a remaining configuration issue. No support message was
sent, and no training or final evaluation ran.

Control evidence: [query-review-c1efb46f374ee6c4](../reports/historical-development/query-review-c1efb46f374ee6c4/report.json).
