# Synthesis diagnosis — September 17, 2026

Full archived Astra synthesis now passes the actual v4 Python contract and all
15 rendered frozen-row parity checks after repairing decimal-enum transport.
The newly captured five-symbol chain also passes through a separately registered
synthesis recovery. Its initial single-pass attempt remains partial. No
predictive-performance qualification follows from these engineering checks.

## Runtime findings and changes

The installed Pi coding agent is 0.85.1. The existing executable wrapper selected
Node 22.20.0; the repository build used the existing Node 22 installation selected
by `nvm use 22`. No dependency installation or model substitution was performed.
The readiness check initially hit a sandbox denial creating Pi's OAuth lock;
after ordinary tool escalation, the OAuth/model readiness check passed.

Inspection of the installed runtime established:

- `Agent.onPayload` runs after provider request preparation. It does not prove
  dispatch. The supported per-request `fetch` hook records actual SSE dispatch.
- `Agent.onResponse` exposes HTTP status and headers. Only the status is logged.
- Pi maps a provider stream `start` to assistant `message_start`; subsequent
  `message_update` events expose thinking/tool-argument activity. No content,
  arguments, headers, credential values or full provider errors are logged.
- Progress uses a fixed vocabulary and emits each stage at most once. Stderr
  holds these markers; stdout remains the result/usage JSON envelope. Parent
  deadline termination records a terminal marker where SIGTERM is deliverable.
- Agent retry and provider retry are separate settings. The old `retry.enabled:
  false` did **not** disable provider retries. The adapter now sets provider
  `maxRetries: 0` and rejects a second model invocation in the same request.
- Pi's Codex request builder does **not** serialize `max_output_tokens` or use the
  model's `maxTokens` to enforce a server output cap. Registrations and new
  receipts explicitly record this limitation. Model-call count and the parent's
  wall deadline are enforced; an unknown timeout's usage is not zero.

The official OpenAI documentation describes
[SSE response streaming and typed events](https://developers.openai.com/api/docs/guides/streaming-responses).
The installed Pi implementation, rather than that general API guide, establishes
the precise hooks and Codex transport behavior above. Relevant installed files
are archived with the full diagnostic registration.

## Immutable small probe

Directory:
`reports/improvement-plan-3/synthesis-diagnosis-20260917/synthesis-diagnostic-20260917T033311989799Z-9cc2abb9/`.

Registered before execution: one archived ANET symbol, 5/21/63-session decisions,
27,888 compact JSON bytes, v4 output schema, Astra/medium/SSE, one call and a
180-second deadline. The requested 5,000-output-token setting was subsequently
found to lack provider enforcement; the original registration is preserved,
with the correction recorded here. The probe deliberately excludes specialist
claims and cannot qualify their synthesis or a current market assessment.

Observed stages: dispatch 40 ms, HTTP 200 at 1,755 ms, first streamed response
event at 3,855 ms, result-tool execution at 47,220 ms, completion at 47,223 ms.
The Python validator passed. Receipt: requested and actual model
`openai-codex/gpt-6-astra`, medium reasoning, 7,631 input tokens, 1,479 output
tokens, 9,110 total tokens. Catalog cost estimate: $0.15026, not an invoice.

The small probe used the first instrumentation revision, which incorrectly
listened for stream `start` inside `message_update`; that marker is absent.
HTTP and first-content evidence were recorded correctly. Subsequent runs listen
for assistant `message_start` and distinguish thinking/tool-argument start.
The exact source revision used by the small probe remains archived beside it.

## Preservation and interpretation

`preservation-before.json` in the diagnosis root hashes 2,474 pre-existing files
under Improvement Plan 3 reports and research datasets. The prior adapter,
contract and recovery implementation are saved in `before/`. Existing failure
attempts and frozen research artifacts remain unchanged. New recovery
registrations pin request, parent evidence, code and runtime dependencies and
archive their source; changed registrations and terminal attempts cannot rerun.

The small success narrows the diagnosis: this account/runtime/model can return
a valid v4 synthesis result. It does not prove the cause of the previous silent
timeouts, a quota outage, context-size failure, or an output-schema defect.
The separate provider-retry issue is proven by source inspection; its causal
role in any earlier timeout is unknown.

## Full-input attempts

All directories below are under the same diagnosis root. All requests preserve
the configured Astra model and all specialist claims, critic decisions and
frozen numerical rows. Each registration authorizes one model call.

- `synthesis-recovery-20260917T033557838107Z-553aa449`: HTTP 200 at
  2,121 ms, thinking at 3,747 ms, tool arguments at 11,689 ms, tool execution
  start at 266,591 ms, failure at 266,600 ms. The result handler was never
  entered. This locates failure before result acceptance, but that revision
  did not retain rejected arguments or completed-response usage. Usage is
  unknown; no specific validation defect is established by those markers.
- `synthesis-recovery-20260917T034335274025Z-d5fd05a8`: identical input with
  rejected-output/usage retention added. HTTP 200 at 2,005 ms; no content event
  or tool invocation; terminal adapter failure at 667,134 ms. Stdout is empty,
  so no completed-response usage is available. The declared subprocess timeout
  was 600 seconds; the observed terminal time exceeded it. The reason for that
  scheduling/timing overrun has not been established. Do not describe the
  timeout setting as a guaranteed real-time deadline.
- `synthesis-recovery-20260917T133736177995Z-1f320225`: separately registered
  concise-response variant. All input evidence and frozen rows remain; the
  prompt asks for at most one claim per symbol and short prose without rounding
  probabilities. This is a response instruction, not a provider token cap.
  It failed tool validation after 216,614 ms and preserved its candidate and
  usage: 75,591 input and 7,055 output tokens, Astra/medium. The candidate had
  exactly two probability-enum errors, detailed below.

The adapter now retains a bounded rejected candidate output (never the request
or provider error text) on stdout with `failure: RESULT_NOT_ACCEPTED` and the
completed assistant's usage receipt when available. Its nonzero exit prevents
that candidate from being treated as a completed run. Stderr distinguishes a
known Pi tool-validation failure from other tool failures. Failed/incomplete
responses without reported usage retain unknown usage.

An offline, explicitly synthetic five-symbol output passed both the actual
Python v4 validator and installed Pi `validateToolArguments`, unchanged after
Pi validation. See `offline-five-symbol-validator-receipt.json`. This proves
the full schema can accept a conforming output, not that a model produced it.

## Proven decimal defect and repair

The retained concise candidate returned QQQ's 5-session probability as
`0.4881913325931084` instead of `0.48819133259310843`, and NVDA's as
`0.4488934582748548` instead of `0.44889345827485483`. Pi's exact enum validation
rejected those last-digit changes. An offline counterfactual replacing only
those two fields with their authoritative frozen values passes the original
Python v4 contract. That candidate remains rejected; it is not promoted into a
successful run. See `rejected-candidate-review.json` for hashes and evidence.

`resultToolSchema` now represents decimal-number enum choices as their exact
decimal strings on the model tool wire. `restoreNumericEnums` accepts only an
exact string match to one original schema member and retrieves that original
number; it performs no float parsing, rounding, tolerance, nearest-value match,
or recalculation. The returned result still uses the unchanged Python v4 number
contract. Per-field string-to-frozen-number mappings are retained in stdout,
and receipts identify `exact_decimal_strings_v1`. Integer enums remain numbers.

Regression tests reject the rounded strings and even unencoded numeric inputs;
the Python validator still rejects wrong symbol/horizon/action/forecast tuples.
An offline round trip through the installed Pi validator preserves all 15 rows
exactly (`exact-decimal-transport-offline.json`).

Live repaired small probe:
`synthesis-diagnostic-20260917T134452640213Z-8dc85e98/`.
NVDA's three horizons passed in 43,665 ms, including the exact previously failing
probability. Receipt: Astra/medium, 7,650 input and 1,348 output tokens. This
supports the transport repair; it does not by itself qualify full synthesis.

The old silent timeouts remain unexplained individually. The demonstrated
decimal failure could cause additional correction turns under the previous
adapter, but no retained evidence proves that was the cause of every timeout.

## Full archived verification

`synthesis-recovery-20260917T134617308467Z-bd39cbd7/` completed with the configured
Astra/medium model in 222,993 ms. The actual Python v4 contract passed. The run
contains the recovered report, an exact copy of the original frozen numerical
rows with the new report identity, and an HTML/Markdown/JSON product. The
original parity helper passed all 15 rows against the original synthesis request;
the receipt is `product/product-parity-verification.json` inside that run.

This is archived evidence with its original cutoff and stale/current-entry
gates retained. It is not relabeled as a current forecast. A fresh on-demand
seven-role run is separately registered in `fresh-live-registration.json`, with
new capture and analysis roots and no prospective registration.

Validation: `npm run check` passed TypeScript, 27 JavaScript tests, and 483 Python
tests. Tests cover progress confidentiality/bounds, single-call enforcement,
rejected-output usage retention, exact-decimal transport, frozen decision
validation, source/runtime mutation rejection, and terminal-attempt replay.

## Newly captured chain and remaining limitations

Fresh packet:
`fresh-live/analysis-20260917T135146950254Z-9c23f052/packet.json`, cutoff
2026-09-17T13:51:46.610192Z. All five completed-close price panels were fresh;
primary acquisition errors were empty. Deferred VIX/VIX3M entitlement gaps
remain explicit. This capture was not imported into the separate prospective
observation store, which remains at 120 observations.

The initial `fresh-live/agents-20260917T135146992101Z-e9657f1d/` run completed
all five Terra specialists and the Sol critic. Its full-payload Astra stream
ended after 194,143 ms without a complete assistant result or usage receipt.
There was no result-tool invocation. Its on-demand receipt stays `PARTIAL`;
the cause of that interruption is not established and usage is unknown.

`fresh-live/synthesis-recovery-20260917T140959948174Z-b712976d/` then reused
those six verified fresh results and completed one registered compact/concise
Astra call in 215,436 ms. Receipt: 72,580 input and 6,732 output tokens, medium
reasoning, exact decimal string transport. Its Python contract and all 15
rendered frozen rows passed. There were seven initial role attempts plus one
separate recovery call; this was not a single-pass success.

Independent verification: `fresh-chain-verification.json`. The reproducible
helper is `verify_fresh_run.py`, accepting the initial run, a new receipt output
path, and optionally its recovery run. It verifies request/completion/model
identities, every accepted role, the original partial receipt, and frozen
numerical/product parity without issuing a forecast.

The recovered HTML is
`fresh-live/synthesis-recovery-20260917T140959948174Z-b712976d/product/index.html`.
Publication lag was 1,436.55 seconds. The product remains `DEGRADED` with honest
freshness/evidence gates. A current capture does not make an older published
snapshot an actionable current quote. No prospective forecast, trade, data
purchase or unattended scheduler was created.

After this stream interruption, the adapter gained fixed failure categories
without exposing provider text. TypeScript compilation and all 28 JavaScript
tests passed. Python sources match the preceding 483-test full check; see
`test-validation-final-progress.json`. All model attempts in this session are
terminal, with failures preserved. There is no running model job to resume.

Next engineering work is to improve the ordinary full-payload path's reliability
or integrate the verified compact path with explicit budgets and registrations.
Do not repeat the completed six roles merely to retry synthesis. A future
current-entry demonstration needs a new capture and publication within its
freshness contract. Historical qualification, independent sample size and
matured prospective outcomes remain separate open gates; no frozen audit or
holdout was changed to pass this engineering work.
