# Independent review: v2.10 round3, high reasoning

Assistant development review against the unchanged frozen five-axis rubric, not human acceptance. This iteration combines prompt/schema changes, computed asymmetry, aggregated validation feedback, high reasoning and a larger output allowance. Gains cannot be attributed to prompt changes alone. The full run ended EVALUATION_INCOMPLETE at input admission; accepted draft exists, accepted Challenger/final do not.

| Task | Role | Score | Result |
|---|---|---:|---|
| task-3 | company research | 13/20 | BELOW_VERY_GOOD |
| task-4 | macro research | 16/20 | VERY_GOOD |
| task-5 | technical research | 16/20 | VERY_GOOD |
| task-6 | geopolitics research | 17/20 | VERY_GOOD |
| task-7 | commodities research | 17/20 | VERY_GOOD |
| task-8 | director draft | 11/20 | BELOW_VERY_GOOD |
| task-9 | challenger review | 0/20 | NOT_ASSESSED_NO_ACCEPTED_OUTPUT |
| task-10 | director final | 0/20 | NOT_ASSESSED_NO_ACCEPTED_OUTPUT |

Evidence-linked scores: [independent-review.json](independent-review.json). All registered tasks remain in the denominator.

## What improved

Macro, Technical, Geopolitics and Commodities meet provisional VERY_GOOD on this development packet. Scoped nonblocking gaps preserve useful analysis. Geopolitics explains China optionality relative to guidance already excluding it. Commodities adds a two-sided take-or-pay/fixed-or-banded memory-pricing mechanism, with no invented commodity beta. Technical preserves precise dated conditions. Director now completes a schema-valid draft and avoids blanket insufficient-evidence conclusions.

## Material remaining errors

Company and Director still do not meet the threshold. Company arithmetic asymmetry is now correct, but fiscal labels and guidance-range interpretation are not. Director inherits the calendar error, overstates certain comparative claims and loses useful specialist analysis.

### Fiscal calendars are in the archived documents

- NVDA evidence [aaa38c...](evidence/aaa38c73319f8f4075c7919afd11707a91a7fa23edc0f75ad529ab8629277344.json), source `discovered-711a31fe2c33ab05fce3`, normalized text offset15486: FY2027 is53weeks ending last Sunday in January, Q4 is14weeks. Calendar application gives January31,2027, not the grid January25.
- MU latest10-Q [document9c2f...](documents/9c2fd86e183cb9809345162f6051fe6d493980241ec5a88137342faa6e90f40c.json), source `discovered-4eef771bf2efe0e696b5`, normalized offset19515: year ends Thursday closest toAugust31; FY2026 has53weeks and Q4has14. Calendar application gives September3,2026, not grid/report August27. This passage is beyond the standard16,000-character excerpt but inspectable in the archived raw document.
- These are explicitly named fiscal-year models, not declared nonfiscal sensitivity windows. MU still ended before the September21cutoff, so its broad ended-but-unreported characterization is correct. Exact basis and extra-week bridge still need repair.

### MU guide endpoints are mislabeled

The EPS guidance interval30.73+/-1.00 is29.73–31.73. Grid residual27.60 is below and32.60 is above it. The grid repeatedly labels these low/high guided EPS outcomes. Execution/mix pressure can justify a miss/beat stress, but must explicitly identify the miss/beat and its size; merely adding stress language does not make these guidance endpoints.

### Director comparative and synthesis defects

- Draft says NVDA has stronger demand than QQQ without comparable aggregate fund operating data. Historical relative price leadership is supported; comparative operating-demand strength is a different claim.
- Draft prefers QQQ to MU on path risk and stress asymmetry. Lower observed QQQ volatility is supported; QQQ comparative stress asymmetry is not modeled.
- Reverse EPS/multiple thresholds, residual earnings interpretation, concrete Technical close triggers and the two-sided MU contract-pricing insight lose visibility during synthesis. A short useful synthesis can preserve these mechanisms without repeating all specialist text.

## Challenger diagnostic, not an accepted score

The [rejected Challenger response](responses/3fc48a3b7214650faff59182654ef4248106a7931cf664d40db40a5b676bf218.json) focused on NVDA conditional-opportunity labeling given a base near the dated close. It did not identify the fiscal calendar or MU guidance-range errors, or the unsupported QQQ asymmetry comparison. The objection also omitted a referenced claim dimension and was rejected. An earlier inspection queried a scenario artifact as a searchable document and returned NO_SEARCHABLE_DOCUMENT. Admission then blocked another correction turn. These observations are retained for debugging; no accepted Challenger result exists.

## Next focused verification

Expose source-calendar passages before generating named annual grids, validate calendar identity through ordinary code, and require explicit miss/beat language for guidance-external stresses. Keep comparison methods scoped to common evidence. Retain useful specialist mechanisms in Director synthesis. Evaluate Challenger on seeded concrete calendar/range/comparison defects, while preserving unknown usage and failed attempts in the cost denominator.
