# Reviewed default configuration — October 3, 2026

The user requested promoting the improved agents into the default configuration.
New v6 research runs now use **v2.17**: the exact reviewed shared and role prompts
from the archived full-team development run, with Technical taken from its later
EXCELLENT focused replay. This updates the default configuration; V1 release
acceptance and the broader evaluation campaign remain open.

## What is active

| Role | Reviewed source | Assistant development score | Default model |
|---|---|---|---|
| Company | `all-roles-v213-round8-high` | 16/20, VERY GOOD | Mandate model |
| Macro | Same full-team run | 16/20, VERY GOOD | Mandate model |
| Geopolitics | Same full-team run | 17/20, VERY GOOD | Mandate model |
| Commodities | Same full-team run | 16/20, VERY GOOD | Mandate model |
| Challenger | Same full-team run | 16/20, VERY GOOD | Mandate model |
| Director | Same full-team run, draft and final | 16/20, VERY GOOD | Mandate model |
| Technical | `technical-v216-sol-expert2` | 20/20, EXCELLENT | `openai-codex/gpt-5.6-sol` |

The regular NVDA/MU/QQQ workspace retains its configured Terra model for the
other roles. The existing single-company ANET mandate retains its explicitly
configured Sol model. New default v6 runs use high reasoning effort, a
10,000-token response ceiling and `role-research-v1` evidence projections for
both single- and multi-instrument work. Director draft capacity is three turns.
The controller freezes each task's actual runtime and dispatches that runtime;
Technical's model selection is reflected in both the request and monitor.
Aggregate budgets and publication reserves still govern admission.

The [promotion manifest](../prompts/investment-research/v2.17/promotion.json)
records the user authorization, each source registration, prompt hash and rating.
Every combined prompt hash matches its scored registration. The current v6 tool
contract retains later timestamp constraints and the additional valuation-method
tool; those adaptations are explicitly recorded separately from reviewed prompts.
Creation rejects altered promoted prompts or tools. Existing v2.16 extensions
remain available in their own directory.

Explicit evaluation prompt selection preserves the chosen baseline's settings
and model. The evaluation CLI's historical v2.7 baseline default remains explicit;
it does not silently inherit the new production configuration. Prior states,
scores, publications and failed attempts retain their original records. A server
already running must reload current code before creating runs with these defaults.

## Evidence and limits

The archived outputs show materially deeper conditional analysis, numerical
valuation interpretation and concrete review conditions than the original
rejected report. Improvements also involved context, deterministic tools and
reasoning/model settings; they cannot be attributed to prompt wording alone.

The last full-team development run still failed because of Technical's sign
error. Its later focused replacement does not rescore that run. The missing-data
and planted-error campaign, full production orchestration evaluation, fresh live
usefulness review and M4 comparisons remain incomplete. Individual assistant
ratings establish neither general reliability nor investment performance.

This promotion creates no new paid research run or publication. Its verification
checks prompt identity, effective model dispatch, explicit baseline isolation,
artifact tampering and the surrounding research regression tests.

Verification on October 3: **90 tests passed** across promotion, workspace,
evaluation, readiness, Technical signs/path, M2 cooperation and M3 publication.
The synthetic worker fixture now honors the draft identity-map transport required
by the promoted multi-instrument context. `git diff --check` passed. The tests
made no research-provider or model calls.
