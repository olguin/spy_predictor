# SPY historical gap repair: not qualified

2026-09-09. Gateway connection succeeded. Ten bounded, read-only historical requests produced **no compatible replacement sessions**. No new dataset or model run was produced.

| Session | Request | Result |
|---|---|---|
| 2004-07-12 | SMART / 1 day | Target absent (8 neighboring bars returned) |
| 2007-07-02 | SMART / 1 day | Target absent (9 neighboring bars returned) |
| 2004-07-12 | ARCA / 1 day | IBKR 162: no data |
| 2004-07-12 | SMART / 1 day | IBKR 162: no data |
| 2007-07-02 | ARCA / 1 day | Target returned; no bracketing bars in this request |
| 2007-07-02 | SMART / 1 day | IBKR 162: no data |
| 2004-07-12 | AMEX / 1 day | Target absent (9 neighboring bars returned) |
| 2007-07-02 | ARCA / 1 day | Target returned; 8/9 neighboring closes differ from SMART |
| 2004-07-12 | SMART / 1 hour | Target absent (16 neighboring bars returned) |
| 2007-07-02 | SMART / 1 hour | Target absent (16 neighboring bars returned) |

SMART daily and hourly responses omit both dates. AMEX also omits July 12, 2004. ARCA returns July 2, 2007, but eight of nine neighboring closes and all nine neighboring OHLC bars differ from the pinned SMART series. The recovered venue-specific bar was not spliced into the consolidated series.

The first development dataset/report and all five stopped-experiment files retain their recorded hashes. The designated final evaluation period remains unopened. Thirteen targeted tests passed, and all four capture bundles reproduced offline without network requests.

Next: qualify a separate source or obtain a compatible IBKR correction before creating another dataset and rerunning the unchanged models. No additional source was acquired and no prices were imputed.

[Machine-readable audit and artifact hashes](report.json).

Audit identity: `6d79f6498c132ac617c54592049acae2758e669492361c298e274f16f02d64fc`.
