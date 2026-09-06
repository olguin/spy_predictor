# TARGET-TOURNAMENT-001 final report

Dataset: `phase1-market-e70bdc3ff5238003`

Decision: **NO_TARGET_ADEQUATE**

No instrument/horizon candidate passed every preregistered gate on the sealed confirmation sample.

| Candidate | Samples | Confirmation | Coverage | Champion | Passed gates | Result |
|---|---:|---:|---:|---|---:|---|
| ES/close-next-close | 467 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| ES/open-15m | 481 | 100 | 98.97% | logistic-l2 | 6/11 | REJECT |
| ES/open-30m | 481 | 100 | 98.97% | logistic-l2 | 6/11 | REJECT |
| ES/open-60m | 481 | 100 | 98.97% | logistic-l2 | 6/11 | REJECT |
| ES/open-close | 481 | 100 | 98.97% | logistic-l2 | 6/11 | REJECT |
| ES/previous-close-next-open | 481 | 100 | 98.97% | logistic-l2 | 6/11 | REJECT |
| NQ/close-next-close | 467 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| NQ/open-15m | 481 | 100 | 98.97% | logistic-l2 | 6/11 | REJECT |
| NQ/open-30m | 481 | 100 | 98.97% | logistic-l2 | 6/11 | REJECT |
| NQ/open-60m | 480 | 100 | 98.77% | logistic-l2 | 5/11 | REJECT |
| NQ/open-close | 481 | 100 | 98.97% | logistic-l2 | 6/11 | REJECT |
| NQ/previous-close-next-open | 481 | 100 | 98.97% | logistic-l2 | 6/11 | REJECT |
| QQQ/close-next-close | 501 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| QQQ/open-15m | 502 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| QQQ/open-30m | 502 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| QQQ/open-60m | 502 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| QQQ/open-close | 502 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| QQQ/previous-close-next-open | 502 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| SPY/close-next-close | 501 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| SPY/open-15m | 502 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| SPY/open-30m | 502 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| SPY/open-60m | 502 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| SPY/open-close | 502 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |
| SPY/previous-close-next-open | 502 | 100 | 100.00% | logistic-l2 | 6/11 | REJECT |

The champion model for each target was selected using the selection period only.
All promotion gates were then evaluated on the final sealed chronological sample.
No LLM calls or order-submission code were used.
