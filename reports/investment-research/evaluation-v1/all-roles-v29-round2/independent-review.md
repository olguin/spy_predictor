# Independent review: v2.9 round2

Assistant development review, not human acceptance. Same frozen five-axis rubric. Two specialists reach provisional VERY_GOOD on this single development packet; three do not. The run is EVALUATION_INCOMPLETE, so required synthesis/challenge outputs receive zero for delivery failure and are explicitly not assessed for semantic quality.

| Task | Role | Score | Result |
|---|---|---:|---|
| task-3 | company research | 12/20 | BELOW_VERY_GOOD |
| task-4 | macro research | 14/20 | BELOW_VERY_GOOD |
| task-5 | technical research | 16/20 | VERY_GOOD |
| task-6 | geopolitics research | 15/20 | BELOW_VERY_GOOD |
| task-7 | commodities research | 16/20 | VERY_GOOD |
| task-8 | director draft | 0/20 | NOT_ASSESSED_NO_ACCEPTED_OUTPUT |
| task-9 | challenger review | 0/20 | NOT_ASSESSED_NO_ACCEPTED_OUTPUT |
| task-10 | director final | 0/20 | NOT_ASSESSED_NO_ACCEPTED_OUTPUT |

Evidence-linked scores: [independent-review.json](independent-review.json).

## Improvements that survived inspection

Technical provides matched multiwindow comparisons and three exact frozen-SMA completed-close review thresholds, with precise limits on causal and fundamental interpretation. Commodities inspected actual inventory notes and discovered a relevant NVDA land/power/shell guarantee channel, then scoped its no-independent-commodity-signal conclusion without blocking other roles. Geopolitics now clearly separates China-access upside optionality from NVDA guidance already excluding China compute revenue. Company now interprets residual EPS and break-even multiples rather than merely listing grids.

## Remaining blockers

1. Company makes a material false downside comparison: task-3-mu-price-threshold says downside is larger than upside even though the quoted percentages are -36.01% and +38.22%. Correct arithmetic alone does not ensure truthful prose.
2. Company incorrectly generalizes that both fiscal earnings periods extend beyond the63-session horizon. MU FY26 ended before the evaluation date.
3. Company and Macro preserve narrow conditional analysis in prose but still mark valuation/relative-preference gaps critical across all instruments. Geopolitics similarly overblocks MU relative preference for unavailable quantified policy impact. These structured declarations can erase valid analysis downstream.
4. Director draft made three submissions and received three validation rejections, then exhausted its call allowance. No accepted Director draft exists, so Challenger and final synthesis were not evaluated. Rejections were, in sequence:
- Unresolved dependency blocks NVDA valuation, not unrelated conclusions
- Unresolved dependency blocks NVDA policy_exposure, not unrelated conclusions
- Conclusion claims require matching instrument and dimension scope

The Director validation failures are evidence of remaining contract/scope problems, not successful uncertainty management. The original prompt cohort, evidence packet and scoring threshold remain unchanged in this review. No score is upgraded because a response is longer or contains more numerical detail.

## Next targeted changes

Calculate and expose exact downside/upside direction, keep fiscal timing explicit per instrument, and clarify critical-gap semantics at the actual structured field. Return all validation defects together within the existing retry budget. Preserve Technical and Commodities improvements. Any change in reasoning effort or runtime should be registered as a separate intervention before attributing gains to prompts.
