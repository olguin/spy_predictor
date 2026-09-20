# Terra technical → Sol critic stage-gate audit

Audited run: `agents-20260913T032304124915Z-1d6aa50f`  
Source packet: `analysis-20260911T205359598727Z-0cf0208e`

## Identity

- Source packet SHA-256: `ea3e47c76926072103a4ed05c9d955f1dcde13f498924343b6b2616c8d6e784f`
- Terra technical result SHA-256: `2a8b157d3f5b9b707467561807671b56b14c952e2f8b6a84adc2390814886b06`
- Sol critic result SHA-256: `75eb6abc07b89733024f9b646dbb82419ec9cb49553b3eaada1a2109f4f8de84`

## Audit result

`PASS_FOR_FULL_ORCHESTRATION_TEST`

The schema validator accepted both results. The technical output contains five
citation occurrences, one instrument-specific price source per symbol. Every
reported close-relative moving-average condition, RSI14, 21/63-session return,
252-session drawdown, ATR14 and 21/63-session realized-volatility value was
checked against the calculated instrument panel and agrees at the displayed
precision. Moving-average support/resistance language is conditional. ATR14 is
correctly described as an average one-session true range and is not rescaled.
Fields excluded by projection are described as not supplied to that role.

The critic output contains 45 citation occurrences across 32 unique packet
sources: SPY 10, QQQ 7, AAPL 9, MSFT 7 and NVDA 12. Every ID exists in the source
packet and is permitted by the critic request schema. Material claims were
checked as follows:

- FRED claims match the dated calculated market fields for CPI, NFCI, STLFSI4,
  T10Y2Y and VIX rather than being inferred from headlines.
- SPY look-through uses the supplied September 9 top-ten table: 38% reported
  coverage, including NVDA 8.22%, AAPL 7.04% and MSFT 5.55%. It is explicitly
  described as incomplete. No QQQ weight is invented.
- The September 16 FOMC date matches the official-calendar evidence and retains
  its tentative-date limitation.
- Apple, Microsoft, QQQ and macro catalyst descriptions match their cited news
  text and are consistently labeled secondary, truncated, conflicting or
  unverified where applicable.
- NVIDIA revenue growth and infrastructure claims match cited issuer releases;
  the critic explicitly identifies those releases as correlated promotional
  primary sources rather than independent confirmations.
- SEC-derived margin, cash-flow and debt statements retain period/comparability
  limitations and do not invent valuation multiples or growth comparisons.

No unsupported cited claim was found. This is a content audit of the bounded
packet, not validation of market direction, calibration or investment value.

## Rejected predecessor

The earlier immutable gate `agents-20260913T031150875675Z-5993c53b` is not the
accepted gate. Review found projection-missingness wording and ATR-horizon
ambiguity. Prompt contract changes corrected both before the accepted rerun.
