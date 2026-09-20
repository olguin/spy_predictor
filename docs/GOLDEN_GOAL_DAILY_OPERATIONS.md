# GOLDEN GOAL daily operations and interpretation

This is the operator runbook for the complete research system: capture current
market, macro, issuer, ETF, policy and news evidence; run five independent
specialists, a critic and final synthesis; generate deterministic 5/21/63-session
probabilities and research recommendations; render the product cockpit; and keep
an immutable prospective evaluation record after the close.

The system is research support. It does not size positions, submit orders or
claim calibrated predictive skill. Until a prospective cohort passes its frozen
sample and statistical-review gates, all META probabilities remain explicitly
`EXPERIMENTAL_UNCALIBRATED`.

Operational limits are frozen in `config/meta-operations-v1.json`: at most seven
agent calls, two concurrent agents, one prospective attempt per role, one hour of
wall time, bounded acquisition requests/bytes and token ceilings. The $25 catalog
cost-estimate ceiling is a conservative run guard over Pi's receipt estimate; it
is not a statement that the ChatGPT plan will bill that amount.

## One-time setup

From the repository root:

```bash
cd /Users/juanpablo/jp/projects/spy_predictor
UV_CACHE_DIR=.uv-cache uv sync --project python --group dev
npm install
```

Keep the existing `.env` file local and uncommitted. The normal live-data path
uses the existing Alpaca credentials and `SEC_USER_AGENT`. Pi keeps its OAuth
credentials in its private `~/.pi/agent` store. Never copy either credential
store into a report or use a token-printing command.

Verify local readiness without printing secrets:

```bash
npm run pi:preflight --workspace @spy-predictor/agent-runtime
npm run meta:ops -- doctor
```

Expected Pi preflight fields include `oauth_configured: true` and the configured
Terra, Sol and Astra models. This proves that Pi can see a credential and catalog;
it does not prove that an actual model request can use the token. The OAuth session
was renewed and a claim-validated five-symbol Terra stage gate passed on September
13/14. If a future request reports an expired token, activate the already-installed
Node 22 first; the default Node 20 cannot start Pi 0.85.1 because
`node:fs.globSync` is unavailable:

```bash
source /Users/juanpablo/.nvm/nvm.sh
nvm use 22
node --version
npx pi
```

Confirm `node --version` prints `v22.22.0` or another version at least 22. Inside
Pi, use `/login`, choose **Sign in with an account → OpenAI Codex**, finish the
browser/device flow, then exit Pi. The entry currently appears as
`OpenAI Codex ✓ stored`; stored means present, not necessarily unexpired. Do not
print or copy the bearer token.

In a sandboxed agent session, Pi must also be allowed to create its private lock
beside `~/.pi/agent/auth.json`; an `EPERM` for `auth.json.lock` is a filesystem-
permission failure. A normal terminal should not need a new device login for each
run after the renewed cached session is functioning.

IB Gateway is **not required** for the GOLDEN GOAL pipeline. A supplied delayed
IBKR snapshot is optional context only. No paid data subscription is required by
the current default path; Alpaca IEX is limited-venue real-time coverage and is
labeled as such.

## Symbols are parameters

The examples use:

```text
SPY QQQ AAPL MSFT NVDA
```

Replace them with any 1–10 supported US symbols; five is the normal product
size. Put only ETF symbols in `--etfs`. The order supplied is preserved in the
report.

## Everyday operator checklist

For the normal five-symbol routine:

1. Before the first important run, renew Pi OAuth if the real-call smoke reports
   an expired token. Refresh QQQ manual evidence only when its sponsor date
   changes or its 7/31-day age limit is reached.
2. At any moment you want a current opinion, run section A. During the regular
   session, use the intraday IEX flags; outside it, completed-close evidence is
   the safer default.
3. On each XNYS trading day, after close plus 25 minutes, run the section B
   prospective command without `--execute`; execute only when `would_execute`
   is true. A convenient fixed Buenos Aires operator time is 18:30 on weekdays:
   this is after the guarded window in both New York daylight and standard time,
   while holidays still abstain safely.
4. Run the section C outcome dry-run and update after the same close buffer.
5. Open the generated `product_bundle/index.html`. First read the run/probability
   badges, then missing/failed evidence, then each symbol's 5/21/63-session row,
   counter-case and review triggers. Never act from the directional label alone.

The prospective command itself is calendar-aware and idempotent. The clock time
above is an operator convenience, not the source of truth; the XNYS guard is.

## Manual ETF evidence before an important QQQ run

Price, macro, SEC, primary-release and news data are acquired by the command.
QQQ holdings and sponsor valuation/quality remain manual because automated
Invesco scraping is not authorized.

Use the procedure in `PROJECT_PLAN_AND_STATUS.md`, section “Manual QQQ refresh
runbook.” Supply:

```text
datasets/workbench/manual-sources/qqq-holdings-YYYYMMDD.csv
datasets/workbench/manual-sources/qqq-profile-YYYYMMDD.json
```

The embedded sponsor `as of` date is authoritative. Holdings may be at most seven
calendar days old; the sponsor profile may be at most 31 days old. If omitted,
the pipeline still runs but shows those families as `MISSING` and may emit
`INSUFFICIENT_EVIDENCE`.

## A. Run the whole GOLDEN GOAL on demand

Use this whenever you want an analysis during premarket, the regular session,
postmarket or a closed market. During the trading session, add intraday IEX
context up to the run cutoff:

```bash
npm run meta:analyze -- \
  --symbols SPY QQQ AAPL MSFT NVDA \
  --etfs SPY QQQ \
  --runner-config config/meta-agent-pi-codex.example.json \
  --market-data-mode intraday \
  --intraday-feed iex \
  --etf-holdings SPY=datasets/workbench/manual-sources/spy-top-holdings-20260909.csv \
  --etf-holdings QQQ=datasets/workbench/manual-sources/qqq-holdings-YYYYMMDD.csv \
  --etf-profile QQQ=datasets/workbench/manual-sources/qqq-profile-YYYYMMDD.json
```

For a completed-close-only run, omit these two arguments:

```text
--market-data-mode intraday --intraday-feed iex
```

The command performs the full chain:

1. Captures and hashes evidence, using rate-aware caching.
2. Builds the validated immutable packet.
3. Runs macro/cycle, technical, fundamental, news and geopolitical specialists.
4. Runs the critic and records one decision for every material specialist claim.
5. Generates deterministic experimental probabilities and gated actions from
   critic-accepted claims.
6. Gives the frozen probabilities/actions to Astra for final explanation and
   validates that Astra did not alter them.
7. Produces the Markdown/HTML/JSON product bundle.

An on-demand run is never registered as a prospective forecast. The final JSON
receipt prints `product_bundle`; open its `index.html` directly or serve it:

```bash
npm run meta:product -- serve --bundle reports/meta-analysis/agents-.../product
```

Then open <http://127.0.0.1:8765>. The server is local-only and read-only. It
supports `GET /`, `GET /summary.json`, `GET /report.md`, `GET /api/v1/latest`
and `GET /healthz`; write requests are rejected. The site serves one immutable
run bundle. Browser reload does not acquire newer evidence; execute a new run and
serve its new `product_bundle` path to advance the cutoff.

The first dashboard section is **GOLDEN RECOMMENDATIONS / GOLDEN CONCLUSIONS**.
It opens with the overall conclusion, at most five cross-market findings and one
decision row per symbol/horizon: action now, separate new-position and
existing-holding implications, P(terminal gain), condition, invalidation,
blocker and next review. Research priority is separate from buy attractiveness,
and ties or no attractive setup are valid. Astra explains the deterministic,
uncalibrated board it received; it cannot rewrite its numbers or actions.

## B. Issue the daily prospective GOLDEN GOAL forecast

This is the evidence-building lane for G9. Run it once after the XNYS close plus
25 minutes and before the next XNYS open. Always dry-run first:

```bash
npm run meta:schedule -- prospective \
  --symbols SPY QQQ AAPL MSFT NVDA \
  --etfs SPY QQQ \
  --runner-config config/meta-agent-pi-codex.example.json \
  --etf-holdings SPY=datasets/workbench/manual-sources/spy-top-holdings-20260909.csv \
  --etf-holdings QQQ=datasets/workbench/manual-sources/qqq-holdings-YYYYMMDD.csv \
  --etf-profile QQQ=datasets/workbench/manual-sources/qqq-profile-YYYYMMDD.json
```

Proceed only when it reports:

```json
{"status":"DRY_RUN","would_execute":true}
```

Execute the identical command with `--execute` appended:

```bash
npm run meta:schedule -- prospective \
  --symbols SPY QQQ AAPL MSFT NVDA \
  --etfs SPY QQQ \
  --runner-config config/meta-agent-pi-codex.example.json \
  --etf-holdings SPY=datasets/workbench/manual-sources/spy-top-holdings-20260909.csv \
  --etf-holdings QQQ=datasets/workbench/manual-sources/qqq-holdings-YYYYMMDD.csv \
  --etf-profile QQQ=datasets/workbench/manual-sources/qqq-profile-YYYYMMDD.json \
  --execute
```

The scheduler uses the XNYS calendar, including holidays, early closes and DST.
It creates the immutable attempt identity before acquisition, records every
stage, prevents a second forecast for the same origin/configuration, and records
blocked/degraded outcomes. An existing interrupted attempt is not silently
replaced; it reports `EXISTING_NONTERMINAL_REQUIRES_RESUME` for operator review.

Do not run the unguarded `meta:postclose` command from an unattended scheduler;
use `meta:schedule prospective`.

## C. Acquire and score matured outcomes

Check first without writes:

```bash
npm run meta:schedule -- outcomes
```

After the daily close plus its data buffer, execute:

```bash
npm run meta:schedule -- outcomes --execute
```

This captures due terminal closes, scores ready 5/21/63-session records and
updates the descriptive cohort aggregate. It is separate from forecast issuance,
so later outcomes cannot change the original forecast.

Read status at any time:

```bash
npm run meta:outcomes -- status
```

## D. Safe unattended invocation

The scheduler is designed to be called by `launchd`, cron or another local
supervisor, but installation is intentionally not automatic. Invoke prospective
dry-run/execute only in the post-close period and the outcome update after the
same data buffer. Keep the computer awake and preserve `.env` and Pi credential
access.

Before installing a schedule, exercise the exact command manually. The guard is
idempotent, but repeated blind invocations should not replace operational
monitoring. Review:

```text
datasets/meta-operations/attempts/
datasets/meta-operations/outcome-attempts/
datasets/meta-operations/alerts/
```

Every alert is append-only and deduplicated while its condition remains open.

## How to read the result

### Top badges

- `COMPLETE`: all configured stages completed and no displayed evidence family
  is stale, missing, partial or failed.
- `DEGRADED`: a usable partial report exists, but one or more evidence/agent
  families are missing, stale, partial or failed. Read the evidence table.
- `BLOCKED`: a required invariant, acquisition, validation, budget or prospective
  guard prevented completion. No recommendation should be inferred.
- `EXPERIMENTAL_UNCALIBRATED`: probabilities are deterministic research-model
  outputs but have not earned a calibration claim.
- `PROSPECTIVELY_CALIBRATED`: reserved for a future cohort that passes all frozen
  sample and statistical-review gates; the current project has not reached it.

### Recommendation vocabulary

- `BULLISH_RESEARCH`: strongest positive research classification under the
  frozen thresholds; not an order.
- `ENTER_IF_CONFIRMED`: the positive probability threshold passed and a cited,
  numeric confirmation rule is available; the rule includes comparison, units,
  confirmation interval and expiry.
- `WAIT`: names the critical evidence, contradiction or measurable trigger being
  awaited and the event/time for reassessment.
- `HOLD_OR_WAIT`: no directional edge under the frozen thresholds; read the
  separate existing-holding implication.
- `REDUCE_RISK`: downside classification intended for risk review, not automatic
  selling.
- `BEARISH_RESEARCH`: strongest negative research classification.
- `UNAVAILABLE`: only the zero-drift quantitative reference exists; no structured
  META recommendation was produced.

Portfolio sizing and trade execution remain `OUT_OF_SCOPE`.

### Probabilities and ranges

For each symbol and 5/21/63-session horizon:

- `P↑` is the modeled probability that the terminal completed-session close
  exceeds the displayed reference completed-session close. It is not the chance
  of profit from buying at a displayed intraday quote.
- Bear/neutral/bull are mutually exclusive terminal-return events. Boundaries are
  ±2% at 5 sessions, ±5% at 21 and ±10% at 63.
- Expected return is the mean of the experimental lognormal distribution.
- Median return is the 50th-percentile terminal outcome and can differ from the
  expected return. Neither value is a price target.
- The 80% price interval is the 10th–90th percentile range, not a guarantee or a
  calibrated confidence interval.
- These are terminal events. They do not estimate whether price touches a target
  or stop, or avoids drawdown, before the target session.

Do not compare a 5-session bull probability directly with a 63-session bull
probability without noticing that their event boundaries differ.

### Evidence coverage and disagreement

- Coverage reports available quantitative features and critic-accepted specialist
  families. It is not calibrated confidence or measured predictive reliability.
- Repetition and exact duplicate evidence do not increase coverage. A rejected
  claim cannot influence the probability. A material `NEEDS_VERIFICATION` claim
  restricts action to `WAIT`.
- `MIXED` is a conflict and is kept separate from a supported `NEUTRAL` view.
  Conflict or excessive directional disagreement restricts action to `WAIT`.
- Agent confidence is never converted into probability.
- Click/read each specialist view to see whether a claim is fact, inference,
  missing, contradicted or invalidated.

### Catalysts, counter-case and review triggers

A recommendation is incomplete unless these are read together:

- Supporting conditions explain what must remain true.
- Counter-case preserves the strongest opposing evidence.
- Review triggers identify events or levels requiring reevaluation.
- Missing inputs identify what the system could not establish.

### Freshness and coverage

- `LIVE_INTRADAY`: timestamped current feed inside its strict age limit, with
  provider and exchange coverage displayed.
- Every displayed intraday bar, trade and quote is bound to its own provider
  timestamp. A newer quote cannot make an older displayed bar appear fresh.
- Publication age is recomputed when the bundle is generated. An intraday value
  older than 15 minutes becomes `STALE_AT_PUBLICATION`; browser refresh alone
  never changes that immutable result.
- `LIVE_INTRADAY_PARTIAL`: a current feed exists but bar gaps or bounded coverage
  make that row degraded.
- `DELAYED`: intentionally delayed data; never executable pricing.
- `LATEST_COMPLETED_CLOSE`: most recent validated complete session.
- `LATEST_OFFICIAL_RELEASE`: most recently published macro observation within
  that series' release-specific age policy; not necessarily observed today.
- `CURRENT_NEWS`: at least one eligible article was published on the packet
  cutoff's UTC date. The row also shows total items and same-day items.
- `FRESH`/`CURRENT`/`AVAILABLE`: internal or non-time-series validation states;
  never assume they mean observed today.
- `MISSING_INTRADAY`: the run could not establish a qualified same-session value.
- `STALE`: known data outside its permitted age.
- `MISSING`: no qualified evidence.
- `FAILED`: attempted stage/source did not produce a valid result.

The “observed/as of” timestamp describes the evidence itself. “Retrieved at” only
describes acquisition. Downloading an old observation today does not make it
current.

### Current VIX / VIX3M source

The implemented trusted current path is Massive's licensed Indices Snapshot API
for exact tickers `I:VIX` and `I:VIX3M`. Run `npm run massive:check` before an
important session. The result separately reports Futures authentication and the
Indices entitlement. `indices.status: not_entitled` means the key is valid but
the account cannot supply current VIX; enable a Massive Indices plan that exposes
the snapshot endpoint (delayed is accepted and labeled `DELAYED`; real-time is
labeled `LIVE_INTRADAY`). Then rerun `npm run massive:check` and require both
tickers in `returned`.

Do not browser-save or scrape Cboe's delayed-quote page for automation. If Massive
is not selected, an alternative implementation can use an IBKR account subscribed
to CBOE Streaming Market Indexes, but no IBKR VIX/VIX3M adapter is currently wired
into this pipeline. Until one path is entitled, the report displays
`MISSING_INTRADAY` and preserves FRED VIX/VIX3M solely as completed-close fallback
context.

### Ablations and prospective evaluation

The leave-one-role-out probabilities show sensitivity to macro, technical,
fundamental, news and geopolitical context. A large change when one role is
removed means the result depends heavily on that evidence family; it does not
prove that the role is correct.

In the G9 evaluation panel:

- `NOT_DUE`: target session has not matured.
- `WAITING_FOR_DATA`: target matured but the independent outcome is unavailable.
- `READY`: outcome exists but has not been scored.
- `SCORED`: immutable score exists.
- Negative META-minus-reference Brier deltas favor META descriptively.

No skill claim is allowed until the cohort has at least 180 scored records, 60
distinct origins and 40 records per horizon, followed by origin-clustered/time-
block statistical review.

## When to stop and investigate

Do not use the recommendation when:

- The run is `BLOCKED`.
- The symbol says `NO_FORECAST` or `INSUFFICIENT_EVIDENCE`.
- A required price or volatility input is stale/missing.
- The packet, report or structured hashes do not match.
- The run cutoff is later than evidence that should have been unavailable at the
  decision time.
- A prospective run reports a duplicate or nonterminal prior attempt.
- A budget is exhausted.
- A partial failure is unexplained.

Preserve every failed/partial run. Do not delete it and rerun merely to obtain a
more favorable forecast.
