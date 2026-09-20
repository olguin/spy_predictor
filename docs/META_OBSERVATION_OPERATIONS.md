# META prospective observation operations

This runbook covers the separate META watchlist ledger. It does not modify the
stopped Cycle 1 experiments, open a historical holdout, trade, or qualify an
investment strategy.

## On-demand analysis lane

Ordinary research analysis is no longer restricted to the prospective issue
window. Run the complete non-registering pipeline with:

```bash
npm run meta:analyze -- \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ \
  --runner-config config/meta-agent-pi-codex.example.json
```

The symbols are parameters. The command captures a new packet, builds calculated
panels, runs specialists, critic and synthesis, and writes an on-demand Markdown
report and receipt. It never writes a prospective observation. During an open
session it always preserves the latest completed daily close. Add
`--market-data-mode intraday --intraday-feed iex` for timestamped one-minute and
latest quote/trade context. The free feed is labeled real-time IEX-only evidence,
not consolidated US coverage. `sip-delayed` is the explicit delayed consolidated
alternative. Neither mode requires IBKR Gateway.

Resume a newly generated interrupted agent run without modifying it:

```bash
python/.venv/bin/python -m spy_predictor_quant.meta_analysis agents \
  --resume /exact/path/to/agents-run-directory
```

Only hash-verified completed roles with matching requests, dependencies, results,
stdout and usage receipts are reused in a new linked run directory.

## Trusted local Pi/Codex agent activation

Use Node 22.19 or later. Pi still detects its configured credential, but the
current stored token is expired. Run `npx pi`, use `/login`, then choose **Sign in
with an account → OpenAI Codex** once before the next model run. Browser or
device-code login is valid; routine per-run login should not be necessary after renewal.
Pi stores OAuth credentials privately under `~/.pi/agent`; never copy that file
into the repository and never use `pi auth print-bearer-token` for this workflow.

Verify authentication and the installed model catalog without printing secrets:

```bash
npm run pi:preflight --workspace @spy-predictor/agent-runtime
```

The September 13 Terra/Sol/Astra run validated the earlier agent contract. It
predates the current claim-level numeric-path contract and cannot create a G7
structured forecast. The bounded current-contract smoke remains the next
production check. Run stages over a newly captured immutable packet with:

```bash
UV_CACHE_DIR=.uv-cache uv run --project python python -m spy_predictor_quant.meta_analysis agents \
  --packet /path/to/analysis-run/packet.json \
  --runner-config config/meta-agent-pi-codex.example.json \
  --output reports/meta-analysis
```

The checked configuration uses at most two concurrent calls, one attempt per
stage, no tools, Terra for the five independent specialists, Sol for the critic,
and Astra only for synthesis. `on_stage_failure: stop` prevents the critic and/or
synthesis from starting after an upstream failure. Each adapter has its own
process group: Ctrl-C, SIGTERM and per-stage timeout terminate descendants,
escalate after a bounded grace period, and preserve a cancellation receipt. This
is a manually initiated research workflow, not unattended automation. Plus-plan
limits are shared and may stop a run; failures remain visible rather than
triggering retries.

The clean September 13 qualification run completed with all seven roles and an
Astra synthesis. It is archived at
`reports/meta-analysis/agents-20260913T070543331922Z-888dea7c`; its semantic and
receipt audit is `reports/meta-analysis/audits/20260913-full-terra-sol-astra-run.md`.
Because the source origin was September 11, treat this as harness qualification,
not as a backfilled prospective forecast.

## Post-close issue workflow

The one-command quant-only workflow is:

```bash
npm run meta:postclose -- \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ \
  --etf-holdings SPY=/path/to/current-spy-holdings.csv \
  --etf-holdings QQQ=/path/to/browser-saved-current-qqq-holdings.csv \
  --etf-profile SPY=/path/to/current-spy-sponsor-profile.json \
  --etf-profile QQQ=/path/to/current-qqq-sponsor-profile.json \
  --ibkr-delayed-context=/path/to/quotes.json
```

It is allowed only from 20 minutes after an XNYS close until the next XNYS open.
Before downloading anything it rejects a duplicate symbol/origin already in the
forecast ledger. It then captures fresh prices, macro data, bounded news, SEC
evidence and configured optional sources; builds and validates the packet; and
registers the immutable quant-only observation. Validation requires the completed
origin close for every symbol, all 5/21/63-session scenarios, current FRED inputs,
and normalized SEC evidence for each stock. A supplied holdings file must be no
more than seven calendar days old. Missing unsupplied ETF holdings remain a visible
optional gap.

The command loads `config/meta-primary-sources-v1.json` by default. It archives
the exact official Fed, Federal Register and issuer feed/page responses, then
normalizes releases and announced events offline. Supplemental source failures
remain explicit but do not suppress an otherwise valid quant-only observation.
Use `--primary-sources` only to select another reviewed, versioned configuration.
ETF sponsor profiles are separate dated JSON inputs; they never infer valuation
from quarterly SEC facts. The checked template is
`examples/meta-analysis/etf-profile-template.json`.

Inspect the guard without downloading:

```bash
npm run meta:postclose -- \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ --preflight-only
```

The September 10 and September 11 origins currently return `DUPLICATE_ORIGIN`,
as intended. The next normal issue window follows the September 14 close plus
the 20-minute provider buffer.

## Delayed IBKR context

To capture quote-only context with an explicit futures rollover rule:

```bash
npm run ibkr:delayed -- \
  --auto-roll-futures --minimum-days-to-expiry 10 --duration-seconds 15
```

This chooses the first catalog contract whose expiration is at least ten calendar
days away and records the exact contract decision. Pass its `quotes.json` to the
post-close command. The META importer requires type-3 delayed data, validates its
timestamps, ignores IBKR's `-1` unavailable bid/ask sentinel, and refuses captures
older than two hours. Delayed values remain context and are never substituted for
the official split-adjusted terminal close.

## Outcome and score workflow

Status is always read-only:

```bash
npm run meta:outcomes -- status
```

The states are:

- `NOT_DUE`: target close plus the 20-minute buffer has not arrived.
- `WAITING_FOR_DATA`: the target is mature but no immutable outcome exists.
- `READY`: an outcome exists and has not been scored.
- `SCORED`: the immutable score exists.

Acquire every due close and score every ready record with one command:

```bash
npm run meta:outcomes -- update
```

Outcome files and score files are stored separately under
`datasets/meta-observation/`, keyed by the full forecast hash. The original
forecast is never edited. Raw Alpaca responses are archived with URL, feed,
adjustment convention and content hash. Scores include bear/neutral/bull Brier
and log loss, probability-up Brier, direction accuracy only when the forecast
makes a non-50/50 call, quantile pinball loss, central 80/90% interval coverage,
median price error and analytic lognormal CRPS for the current quantitative
reference. Structured-cohort records additionally score the experimental META
variant, every leave-one-role-out ablation, paired META-minus-reference deltas and
research-action outcomes. Governance summaries count distinct origins and records
per horizon; origin sessions remain dependence clusters. Aggregate summaries
remain descriptive because horizons overlap and the early sample is far too small
to establish calibration or skill.

To issue a structured META record, add the runner only during the normal guarded
post-close window:

```bash
npm run meta:postclose -- \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ \
  --runner-config config/meta-agent-pi-codex.example.json
```

This attaches the exact agent report, `structured-forecast.json`, policy/engine
cohort identity and unchanged quantitative comparator to one forecast record.
Pi `openai-codex` OAuth must pass preflight first. A pre-claim-level report cannot
be upgraded or backfilled into the structured cohort.

For the complete current daily workflow, guarded scheduler, generated product
cockpit and field-by-field interpretation guide, use
[`GOLDEN_GOAL_DAILY_OPERATIONS.md`](GOLDEN_GOAL_DAILY_OPERATIONS.md). Scheduled
prospective execution must use `meta:schedule prospective`, not an unattended
direct call to `meta:postclose`.

The September 10 five-session targets mature on September 17, 2026 at 20:20 UTC;
the September 11 targets mature September 18 at the same UTC time. Until then,
`update` is an idempotent no-op and needs no market-data request.

## Source policy

QQQ holdings stay on the validated manual sponsor-export path. The audited
Invesco terms do not support assuming permission for scheduled scraping. Refresh
the browser-saved input when a fresh report needs it; do not repeatedly automate
the browser-facing JSON endpoint. SEC access uses the configured identifying
`SEC_USER_AGENT`, conservative pacing and bounded retry policy described in the
[META plan](META_ANALYSIS_PLAN.md).
