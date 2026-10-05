# Technical analysis expert standard

October 3, 2026: the reviewed Technical prompt and Sol/high configuration are
now active for new v6 runs through [default promotion](AGENTIC_INVESTMENT_SYSTEM_V1_PROMOTION.md).
The qualifications and broader acceptance requirements below still apply.

Date: 2026-09-22. Status: focused development result; defaults promoted October 3,
2026. General reliability remains open.

## Objective

Produce an investment-professional market-behavior contribution for a declared
horizon. The contribution must explain the observable setup, leadership, path
risk, opposing path and conditions that change the interpretation. It does not
substitute technical behavior for business value, forecast probability or an
execution instruction.

## Required analytical layers

1. **Point-in-time integrity:** completed sessions only; explicit cutoff, feed,
   adjustment and return basis. Later or unfinished bars are excluded.
2. **Absolute trend:** matched 5/21/63-session returns, price versus 20/50/200
   session averages, short change in the moving average and distance from a
   recent completed-close high.
3. **Relative leadership:** instrument versus declared benchmark and sector at
   every horizon. Mixed signs and sign transitions must be stated explicitly.
4. **Path risk:** realized volatility, mandate-window maximum close drawdown and
   distance from the longer-window high, without turning history into probability.
5. **Participation:** last and recent average volume versus a preceding median.
   A single high-volume session is not sustained confirmation.
6. **Decision use:** strongest continuation case, strongest opposing path, and
   two review rules per instrument when supported: a frozen price checkpoint and
   a recomputed relative-leadership rule.
7. **Visual evidence:** indexed price paths against benchmark and sector, volume,
   signed excess-return comparison and a risk snapshot, all produced
   deterministically from the same cutoff-bound evidence.

## Deterministic gates

- Every comparison-panel pair requires a source-linked machine-readable row with
  signed 5/21/63-session values. The controller rejects a mismatched sign/value.
- Broad all-window lead/lag claims are rejected when they conflict with the
  panel. Contrastive clauses are scoped separately so another benchmark's true
  lag does not create a false rejection.
- Archived OHLCV must be ordered, satisfy price/volume bounds, end at the declared
  completed-session date, match the normalized close and reproduce normalized
  5/21/63-session returns before derived metrics or charts are admitted.

## Focused result

The registered [`technical-v216-sol-expert2`](../reports/investment-research/evaluation-v1/technical-v216-sol-expert2/evaluation-report.md)
run used GPT-5.6 Sol at high effort on the preserved September 21 evidence
capture. It completed three calls, zero source requests, 82,707 input and 8,054
output tokens, and a $0.655155 catalog estimate. One submission was rejected;
the final accepted response contains all six signed pairs, differentiated analysis
for NVDA, MU and QQQ, OHLCV-derived evidence and five charts.

The evidence-linked assistant review scored 20/20, EXCELLENT under the frozen
specialist rubric. This establishes a strong result on one archived case. It does
not establish reliability across instruments or regimes, current research,
investment performance, human usefulness or release acceptance.

## Remaining acceptance work

- Human review of the memo and charts for actual usefulness.
- Held-out cases containing mixed signs, missing bars, corporate actions and
  planted comparison errors, with zero unresolved material errors.
- Prospective tracking after publication; report calibration and investment
  performance separately from research quality.
- Add rolling beta/correlation, downside participation, gap behavior and broader
  sector/market internals only when qualified evidence and a decision use justify
  them. More indicators alone do not establish expertise.
