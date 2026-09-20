# META analysis: current cycle evidence and a small watchlist

Requested September 9, 2026. This extends the secondary
[cycle application plan](MARU_CAPE_APPLICATION_PLAN.md), using the
[current SPY/QQQ snapshot](WORKBENCH_CURRENT_SNAPSHOT.md) and existing calculation,
archive and calendar infrastructure. The stopped Cycle 1 experiments and frozen
[prospective cohort](PROSPECTIVE_OBSERVATION.md) remain separate. This new tool
has its own inputs, prompts, outputs and future evaluation ledger.

The idea is useful as a dated research assistant: quantify the environment,
analyze each business or fund, connect new events to its exposures, and state
conditions under which a thesis would change. Its strongest immediate benefit
is coverage and traceability. Whether the combined evidence improves price
forecasts is an experiment to run prospectively, not a consequence of having
several articulate agents agree.

The GOLDEN GOAL now makes the on-demand five-symbol analyst the primary product
lane and retains guarded post-close registration as a separate evaluation lane.
The versioned contract is [meta-product-v1.json](../config/meta-product-v1.json),
validated by [its schema](../schemas/meta-product-config-v1.schema.json).

## Concrete first increment

Implemented in [meta_analysis.py](../python/src/spy_predictor_quant/meta_analysis.py)
and [meta_agents.py](../python/src/spy_predictor_quant/meta_agents.py):

- Current FRED downloads for 21 named series, including VIX and three-month VIX,
  archived with URL, retrieval time
  and content hash. Individual acquisition failures remain visible.
- Existing local IBKR daily captures, plus Alpaca split-adjusted daily prices for
  additional US tickers using the existing credentials/feed. At least 200 complete
  sessions are required. An incomplete current session is excluded; stale prices
  do not receive current range estimates.
- A bounded Alpaca news request: latest 50 articles in seven days for the watchlist,
  with explicit truncation. This is limited ticker-news coverage, not exhaustive
  geopolitical, sector or global news retrieval.
- Deterministic macro, credit, volatility and technical panels; uncalibrated
  reference price distributions; JSON and a compact Markdown report.
- Seven versioned prompt requests: five independent specialists, then critic,
  then synthesis. One immutable source packet is used for all instruments;
  deterministic role-specific projections limit repeated context while preserving
  source-packet identity and the critic's complete omission-audit view.
- A provider-neutral executable adapter: JSON stdin/stdout, schema validation,
  input identity, citation membership, per-symbol coverage, timeouts, three-way
  concurrency and recorded failures. Every run gets a fresh directory.
- SEC ticker resolution, recent 10-K/10-Q/8-K metadata and standardized US-GAAP
  company facts. SEC access activates only with an identifying `SEC_USER_AGENT`.
- Sponsor-table/export ETF holdings with weight validation, overlap calculation,
  and holdings-driven ticker-news expansion. The current generic adapter is
  manual; an automated QQQ holdings adapter needs its own endpoint/terms audit.
- An external-evidence import for dated filings, ETF holdings, policy releases,
  surveys or articles. This validates structure and timing; it does not authenticate
  the author or verify extraction accuracy.
- A separate read-only `ibkr:delayed` capture for SPY/QQQ and ES/NQ contracts.
  It records delayed market-data type, raw callbacks, exact selected contracts,
  exchange last-trade timestamps and measured age. An optional META importer
  preserves it as context, and an opt-in ten-day minimum-expiry rule selects the
  first eligible ES/NQ contract from the verified catalog.
- An immutable outcome loop with `NOT_DUE`, `WAITING_FOR_DATA`, `READY` and
  `SCORED` states, independent Alpaca terminal-close capture, per-record scores
  and descriptive aggregate summaries.
- A guarded one-command post-close workflow that checks the issue window and
  duplicate origin before acquisition, then captures, builds, validates and
  registers the quant-only observation.
- A frozen primary-source configuration covering the official FOMC calendar,
  Fed monetary-policy releases, Federal Register science/technology documents,
  NVIDIA investor events and NVIDIA press releases. Raw responses are archived;
  normalized records preserve publisher, publication/retrieval cutoff, source
  family and any separately stated scheduled date.
- Dated manual sponsor-profile JSON for ETF fees, valuation, profitability,
  growth, yield, tracking difference and holdings count. Values are bounded and
  reported as sponsor metrics; missing fields remain absent. Holdings-derived
  coverage, top-ten concentration and sector HHI stay separate.

The first production provider adapter is now bundled at
[`pi-codex-adapter.ts`](../packages/agent-runtime/src/pi-codex-adapter.ts). It pins
Pi 0.85.1, uses the `openai-codex` OAuth provider, disables tools and all discovered
extensions/skills/prompts/context files, creates an in-memory session, and returns
an archived usage receipt alongside the schema-bound result. The runner supports
per-role model selection; the example uses Terra for independent specialists and
Sol for the critic and Astra only for final synthesis. This is authorized only for
manually initiated, trusted local runs. Pi OAuth preflight and isolated schema
smokes passed on September 13 for Terra, Sol and Astra. A substantive Terra
technical pass and Sol critic pass over the latest September 11 packet also passed
schema validation and a manual audit of every citation occurrence; see
[`20260913-terra-sol-stage-gate.md`](../reports/meta-analysis/audits/20260913-terra-sol-stage-gate.md).
These checks qualify the requested model routing for one full research run; they
do not establish forecasting skill.

The first full-run attempt is retained at
`reports/meta-analysis/agents-20260913T033409060631Z-5a6bd550`. A macro response
violated a cross-field abstention rule that was then exposed directly in the
model-visible JSON Schema. The operator stopped the run before Astra completed;
the partial specialist and critic receipts remain audit evidence, not a completed
META report. The harness now starts each adapter in a separate process group,
terminates the whole descendant group on timeout, SIGINT or SIGTERM, escalates to
SIGKILL after a bounded grace period, writes `cancellation.json`, and supports
fail-closed dependent-stage gating. The checked production config sets
`on_stage_failure` to `stop`, so any specialist or critic failure prevents later
critic/synthesis spending.

A clean rerun then completed all seven stages at
[`agents-20260913T070543331922Z-888dea7c`](../reports/meta-analysis/agents-20260913T070543331922Z-888dea7c/meta-report.json):
five Terra specialists, one Sol critic and one Astra synthesis, with no failures
or skipped roles. Requested and responding model identities matched in every
receipt. The Astra result's 50 citation occurrences (36 unique sources) and its
material factual claims were reviewed against the packet and passed with the
limitations preserved in the output. The complete decision and hashes are in the
[`full-run audit`](../reports/meta-analysis/audits/20260913-full-terra-sol-astra-run.md).
This qualifies the harness as a manually operated research path, not the agents'
predictive value and not a retrospective September 11 forecast.

The G0–G3 continuation adds strict dual-lane contracts, claim-level
`FACT`/`INFERENCE` output with deterministic citation/numeric-path validation,
hash-verified role reuse through `agents --resume`, and a non-registering
`meta:analyze` command. Resume always creates a new linked directory; it never
edits its source run. Incomplete stdout or missing receipts are not reused, while
identity and dependency mismatches fail closed. The changed model-visible claim
schema has passed offline fixtures but still needs one bounded production schema
smoke before another complete model run.

The G4–G6 bounded implementation adds free Alpaca IEX one-minute bars and latest
trade/quote evidence with explicit limited-venue semantics; rolling 1/5/15/60
minute, daily and weekly technical views; same-date Treasury and real-rate panels;
SOFR, dollar, oil and credit-condition series; and a declared cross-market ETF
proxy basket. It also adds per-instrument evidence completeness, conservative
SEC market-cap/price-book proxies and validated geopolitical event/transmission
fields. A live one-symbol IEX capture/build smoke passed. These additions expose
missing halt, foreign-central-bank, surprise, positioning, issuer and geographic
data rather than treating proxy availability as exhaustive coverage.

Not yet bundled: issuer-specific custom-tag normalization, automated sponsor
adapters beyond permitted sources, broad geopolitical retrieval, licensed
options/sentiment feeds, a trained/calibrated probability model, automatic
scheduling or notebook integration. Generated prompts do not mean that agents
have run.

## Inputs and calculations

“Fed tax” is provisionally interpreted as **tasa Fed / Fed interest rate**.
Use effective DFF initially; add the target range and expectations separately.
If the intended indicator is fiscal taxes or Treasury liquidity, that requires
a distinct definition and source, not a relabeling of DFF.

The public cycle material in the existing application plan does not establish
proprietary numerical formulas for fear, greed or a master cycle score. All rules
below are our explicit operational definitions. Do not call them an exact
reproduction of Mariela Capezzuoli's method or of CNN's Fear & Greed Index.

| Evidence family | First implementation | Interpretation / next addition |
|---|---|---|
| Growth and inflation | INDPRO and CPIAUCSL: exact year-earlier monthly percentage change | Latest retrieved vintage; employment and release surprises later |
| Fed policy | DFF level and change against latest observation at least 90 calendar days earlier | Effective overnight rate; target range, real-rate and expectations panel later |
| Yield curve | T10Y2Y level and 90-day change | Percentage-point Treasury slope; not a timing signal by itself |
| Credit / lending | `100*(MPRIME-GS3M)` for the same calendar month; exact 3-month change in bps | Existing project's lending-rate proxy, not a corporate default spread |
| Financial conditions | NFCI and STLFSI4 level and 90-day change | Broad conditions/stress; SLOOS lending standards next |
| Fear proxy | VIXCLS level and midrank percentile in up to 756 observations, minimum 60 | Volatility expectations; record actual history count, not a claimed sentiment survey |
| Volatility curve | Same-date `VIXCLS / VXVCLS` ratio and point spread | Transparent spot/three-month proxy; not a complete tradable term structure |
| Greed proxy | Per-instrument RSI14 and trend position displayed separately | Momentum/risk-appetite hypothesis; qualified positioning/survey evidence remains missing |
| Transparent risk appetite | Equal mean of inverse VIX percentile, mean watchlist RSI14 and watchlist breadth | 0–100 research proxy with every component exposed; not CNN Fear & Greed and not calibrated |
| Trend and timing | SMA20/50/200, price/SMA, 5/21/63-session returns | Price position; not business valuation |
| Volatility and range | Sample SD of 5/21/63 daily log returns × sqrt(252); 14-day simple ATR | Instrument-specific; daily OHLC price convention recorded |
| Momentum and drawdown | RSI14 with simple average gains/losses; drawdown from up to 252 closes | RSI is explicitly the simple-window variant, not Wilder's smoothing |
| Breadth | Percentage of fresh requested instruments above SMA200 | Watchlist coverage only; not S&P 500 breadth |
| Fundamentals | Supplied dated filings / holdings → specialist analysis | Automatic ratios and standardized peer comparisons follow later |
| Events / geopolitics | Bounded ticker-news feed plus supplied source material | Expand issuer, sector and exposure-based retrieval, not ticker search alone |

VIX measures annualized expected S&P 500 volatility over a constant 30-day horizon;
it is neither a direction probability nor a stock-specific IV estimate.
[Cboe definition](https://www.cboe.com/tradable-products/volatility-trading).
NFCI positive readings indicate tighter-than-average conditions and negative
readings looser conditions, under its published construction.
[Chicago Fed methodology](https://www.chicagofed.org/research/data/nfci/about).
Source definitions: [DFF](https://fred.stlouisfed.org/series/DFF),
[MPRIME](https://fred.stlouisfed.org/series/MPRIME),
[GS3M](https://fred.stlouisfed.org/series/GS3M).

Preserve the repository's ICE/Moody's and Tiingo exclusions. Public availability
does not undo the recorded source restrictions. Review source reuse terms before
redistributing raw data; there is no new paid-source dependency in this increment.

## Forecast output and improvements to the proposal

Use 5, 21 and 63 **trading sessions**, initially for US-listed stocks/ETFs in USD.
These are new workbench targets, not the prospective cohort's annual excess-return
target. Commodity ETCs, leveraged/inverse funds, other countries and currencies
need instrument-specific conventions before inclusion.

Define the forecast event before assigning probabilities. V1 defines bear / neutral /
bull as terminal price returns below / within / above ±2%, ±5%, and ±10% for the
three horizons. Boundaries and probabilities are reported together. These choices
are starting specifications, not tuned or validated economic thresholds.
Report terminal price quantiles separately from path-dependent maximum drawdown
and high/low ranges; the latter are not implemented by a terminal distribution.

The implemented numeric **reference** is:

`log(P_h/P_0) ~ Normal(0, (RV63/100)^2 * h/252)`.

It produces 5/10/25/50/75/90/95th price percentiles and coherent event probabilities.
Its probability of finishing above today's price is always 50%, by construction.
It assumes constant volatility, zero log-return median and no jumps. Dividends
are excluded. These are assumption-based ranges, not a fitted directional signal,
empirically calibrated confidence intervals, or a combined cycle/agent forecast.
Missing or zero volatility, or stale prices, suppresses the ranges. The JSON field
`calibrated_forecast` remains null. Agents cannot replace its numeric values through
their structured response, although semantic review is still required for prose.

G7 v2 adds a deterministic **experimental META challenger** after the critic and
before Astra synthesis. Specialists emit separate 5/21/63-session directions and
claim stance. The critic gives every material claim an `ACCEPT`, `REJECT` or
`NEEDS_VERIFICATION` decision; only accepted claims can become contextual
features. `MIXED` is a conflict gate and never scores as `NEUTRAL`. Exact duplicate
evidence signatures do not receive a second role weight. The frozen assumptions
are in `config/meta-forecast-policy-v2.json`, with a new cohort identity. The
engine emits coherent terminal-event probabilities, P(terminal gain), expected
and median return, price quantiles and leave-one-role-out ablations. Each row binds
its completed-close reference, observation date, forecast origin, exact target
session and event definitions. It explicitly excludes intraday-entry profitability
and path events such as touching a target or stop.

G8 v2 maps the challenger to one action now plus separate new-position and
existing-holding implications. Critical gaps, unresolved material claims and
conflict force `WAIT`. A conditional positive setup becomes `ENTER_IF_CONFIRMED`
only with a cited numeric trigger containing comparison, units, interval and
expiry; otherwise it remains `WAIT`. Coverage is reported as available evidence
families and limitations, without a claim-count confidence percentage. Astra then
receives the immutable probabilities, actions and accepted claim IDs and may
explain but not modify them. Portfolio sizing remains excluded.

Recommended forecasting extension: first record quant-only forecasts prospectively;
then compare a small fixed empirical/volatility reference, a regularized cycle
model, and one quant-plus-context challenger. Use mature labels only. Fit a
regularized distributional model or constrained ensemble weights on permitted
development data and calibrate on a later chronological slice. Every horizon
needs its own calibration. Treat LLM views as timestamped features, never as
votes to average into an invented probability. Until there are enough labels,
show the challenger numerically but explicitly uncalibrated and keep the
zero-drift comparator beside it.

The most useful improvements are:

1. Group correlated evidence. VIX, realized volatility, stress indices and a
   fear/greed composite often reuse similar information. Agent agreement about
   the same event adds no independent source. Preserve family and event identities.
2. Separate market regime from asset attractiveness. Good macro context can
   coexist with poor valuation; a good company can still have adverse timing.
   ETFs require holdings and factor exposures, not corporate accounting ratios.
3. Use timestamped catalyst and surprise evidence: earnings, guidance, FOMC,
   inflation releases, regulation, tariffs and sanctions. Distinguish an expected
   event from a genuinely unexpected change; do not invent consensus.
4. Add a portfolio view for overlapping holdings, sector concentration, shared
   countries, correlation and common downside scenarios. Five tech names and QQQ
   are not six independent bets. A watchlist does not specify position sizes.
5. Separate evidence completeness, analyst disagreement and forecast calibration.
   None can be substituted for another. Make missing inputs visible at ticker and
   horizon level; “no retrieved article” does not mean “no relevant risk.”
6. Freeze inputs before reasoning. If agents discover new evidence, create a new
   snapshot and rerun affected stages instead of mixing information cutoffs.
   Latest FRED CSV downloads are not historical ALFRED vintages.

## Specialist orchestration and efficiency

The order is: acquire and validate → calculate → five independent specialists
(macro/cycle, technical, fundamental, news, geopolitical) → critic claim
decisions → deterministic numerical forecast and action gates → Astra synthesis
→ consistency validation → immutable product → later outcomes.

Five independent requests each cover the whole watchlist; critic and synthesis
add two more. This is seven calls per run, not seven calls per ticker. The current
runner limits concurrency to three and makes one attempt per stage. It records
failure as missing evidence and passes failures to the dependent stages. There
is no unbounded debate or autonomous prompt evolution.

V1's trusted adapter contract accepts JSON on stdin and returns one JSON object
on stdout, or the backward-compatible `{result, receipt}` envelope used by the Pi
adapter. The checked local configuration is
[`meta-agent-pi-codex.example.json`](../config/meta-agent-pi-codex.example.json):

```json
{
  "argv": ["node", "--import", "tsx", "packages/agent-runtime/src/pi-codex-adapter.ts"],
  "model": "openai-codex/gpt-5.6-terra",
  "models": {
    "critic": "openai-codex/gpt-5.6-sol",
    "synthesis": "openai-codex/gpt-5.6-sol"
  },
  "reasoning_effort": "medium",
  "timeout_seconds": 600,
  "max_parallel": 2
}
```

Requests contain `instructions`, `packet`,
`prior_results`, `output_schema` and runtime settings. It must enforce its token
cap, disable external tools for reasoning stages, keep credentials out of stdout
and stderr, and return the exact schema. Never put credentials into the config's
argv: the runner archives configuration and raw outputs locally. Timeouts bound
the direct process; an adapter must cancel provider work and child processes too.
Do not describe the v1 token request as a verified provider spending cap.

Pi requires Node 22.19 or later. Authentication is an interactive local operation
through Pi's `/login` flow; use **Sign in with an account → OpenAI Codex**.
Credentials remain in Pi's private `~/.pi/agent/auth.json` store and must never be
copied into this repository or printed with Pi's bearer-token command. Verify only
non-secret configuration/catalog status with `npm run pi:preflight --workspace
@spy-predictor/agent-runtime`. Preflight does not prove the token can complete a
provider request. The September 13 actual current-contract Terra request
reached the provider but returned `Provided authentication token is expired`, so
Pi login must be renewed once before the next model run.
See [Pi providers](https://pi.dev/docs/latest/providers) and the
[Pi SDK](https://pi.dev/docs/latest/sdk).

G7–G9 provide the frozen experimental challenger, research-action policy and
prospective paired-evaluation machinery. G10 now adds the immutable Markdown/HTML/
JSON product cockpit, local read-only dashboard, rate-aware release/TTL cache,
budgets, operation/alert ledgers and guarded scheduler. No unattended launchd/
cron job is installed. Renew Pi login, pass the claim-level production smoke and
then issue the first structured prospective cohort. A model, prompt, feature or
policy change invalidates affected reuse and begins a separately identified
evaluation cohort. See [daily GOLDEN GOAL operations](GOLDEN_GOAL_DAILY_OPERATIONS.md).

## Running the first version

Existing Python environment suffices; no new dependencies were added.
The Node wrapper loads the existing ignored `.env` without shell evaluation.

```bash
node --env-file=.env scripts/meta-analysis.mjs capture \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ \
  --etf-holdings SPY=/path/to/current-spy-holdings.csv \
  --etf-holdings QQQ=/path/to/current-qqq-holdings.csv \
  --etf-profile SPY=/path/to/current-spy-sponsor-profile.json \
  --etf-profile QQQ=/path/to/current-qqq-sponsor-profile.json
```

This returns the exact new `snapshot.json` path. To reuse the verified local
SPY/QQQ prices while refreshing macro/news, add:

```text
--local-prices datasets/workbench/current-20260909/raw
```

Other symbols still request Alpaca. Old local prices remain labeled stale on
later trading days, so omit the option when refreshing their prices. The feed is
the configured `ALPACA_DATA_FEED`; an IEX result is never relabeled SIP.
The capture command currently permits partial results and records each failure.
Inspect coverage in the built packet, not just its process exit code.
Alpaca daily requests end 20 minutes before retrieval to accommodate delayed SIP
entitlements. The effective end is recorded and partial daily bars are excluded
against both that end and receipt time. Immediately after the bell, the previous
session can therefore remain the last eligible close and be labeled stale until
the delay passes. This is current daily analysis, not a real-time quote terminal.

ETF CSV files use the checked contract shown in
[`examples/meta-analysis/etf-holdings-template.csv`](../examples/meta-analysis/etf-holdings-template.csv):
`as_of,source_url,ticker,name,weight_pct,sector`. All rows must have one nonfuture date,
unique tickers, positive weights, and a total no greater than 100.5%. Partial
top-holdings files are accepted but their reported weight and limited-overlap
coverage stay visible. Use one HTTPS sponsor URL across the file. The current
import proves file structure, timing and arithmetic, not
publisher authenticity. For QQQ, the generic v1 path accepts a normal-browser
sponsor table/export. The existing Invesco audit applies to Cycle 1's historical
distribution table; it does not by itself decide whether a distinct current-holdings
download can be automated. Audit that endpoint and its terms separately.
The post-close registrar additionally requires every supplied holdings file to be
no more than seven calendar days old. It does not pretend that an omitted file is
complete evidence.

Primary issuer/sector/policy sources default to
`config/meta-primary-sources-v1.json`. The source URL must match an explicit
publisher domain. RSS/Atom, the Federal Register JSON API and the official FOMC
calendar HTML have bounded format-specific parsers. Feed publication timestamps
and scheduled calendar dates are separate fields. Failed optional feeds appear
under `supplemental_acquisition_errors`; they do not weaken price, macro or SEC
requirements for quant-only registration. The Federal Register API is an
informational index; legal reliance still requires its linked official edition.

Before SEC acquisition, set a monitored identifying string in the ignored `.env`,
for example `SEC_USER_AGENT=spy-predictor <contact-address>`. It is sent only in
request headers and is not written to artifacts. Missing identity produces
`SEC_USER_AGENT_REQUIRED` per stock. The adapter resolves the ticker through the
SEC map, verifies matching CIKs between submissions and company facts, admits only
facts linked to the latest accepted 10-K/10-Q by cutoff, and excludes custom tags.
All SEC endpoints share one conservative two-request-per-second client. It retries
only transient network failures and HTTP 408/429/5xx responses, makes at most four
attempts with exponential backoff, honors bounded `Retry-After` instructions, and
fails closed rather than retrying permanent errors or an unusually long server
pause. Raw successful responses are archived once for offline packet rebuilds.
The SEC states that company facts aggregate standardized taxonomy data for the
whole filing entity; issuer custom facts and valuation multiples need separate
work. [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

```bash
python/.venv/bin/python -m spy_predictor_quant.meta_analysis build \
  --snapshot /exact/path/returned/by/capture/snapshot.json

python/.venv/bin/python -m spy_predictor_quant.meta_analysis agents \
  --packet /exact/path/returned/by/build/packet.json \
  --runner-config /path/to/your/runner-config.json

python/.venv/bin/python -m spy_predictor_quant.meta_analysis agents \
  --resume /exact/path/to/interrupted/agents-run

python/.venv/bin/python -m spy_predictor_quant.meta_analysis observe \
  --packet /exact/path/returned/by/build/packet.json

python/.venv/bin/python -m pytest python/tests/test_meta_analysis.py -q
```

For a complete non-registering on-demand run using the latest completed daily
session plus evidence retrieved through the actual packet cutoff:

```bash
npm run meta:analyze -- \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ \
  --runner-config config/meta-agent-pi-codex.example.json
```

This command may run in any market period and emits `on-demand-report.md` plus a
hash-bound receipt. It never writes to the prospective ledger. Add
`--market-data-mode intraday --intraday-feed iex` for free real-time IEX-only
context, or `--intraday-feed sip-delayed` for explicitly delayed consolidated
context subject to entitlement.

`build` is offline and verifies raw hashes and receipt cutoffs. It generates
`packet.json`, `report.md`, and `prompts/`. `agents` produces staged requests,
responses and `meta-report.json`. Generated prompts alone require no model API.
The full [orchestrating META prompt](META_ANALYSIS_PROMPT.md) also supports running
specialists in a tool-capable assistant environment.

`observe` writes one immutable prospective record for each fresh instrument and
resolves the exact 5/21/63-session XNYS target dates. It can run immediately for
the quant-only baseline. After a real agent run, pass `--meta-report` to record
the validated synthesis as a separate context-bearing observation. Duplicate
packet registration refuses replacement. The record still sets
`calibrated_meta_forecast` to null; target endpoints and a scoring plan do not
turn the volatility reference into a calibrated prediction.

For routine prospective operation, use the guarded commands documented in the
[META observation runbook](META_OBSERVATION_OPERATIONS.md):

```bash
npm run meta:postclose -- \
  --symbols SPY QQQ AAPL MSFT NVDA --etfs SPY QQQ \
  --etf-holdings SPY=/path/to/current-spy-holdings.csv

npm run meta:outcomes -- status
npm run meta:outcomes -- update
```

`meta:postclose` rejects intraday, pre-buffer, post-next-open and duplicate-origin
runs before acquisition. `meta:outcomes -- update` makes no provider request when
nothing is due. Forecast, outcome and score records are separate hash-linked files.

Optional `capture --evidence evidence.json` imports an array such as:

```json
[
  {
    "id": "ext-issuer-release",
    "kind": "filing",
    "url": "https://issuer.example/actual-release",
    "symbols": ["AAPL"],
    "published_at": "2026-09-09T12:00:00+00:00",
    "retrieved_at": "2026-09-09T13:00:00+00:00",
    "text": "Replace this illustrative text and URL with verified extracted evidence."
  }
]
```

This is a schema illustration, not real evidence. Store actual publication and
retrieval timestamps; never substitute fiscal period end for publication time.
Evidence collected after an existing packet's cutoff requires a fresh capture.
Policy/news records may additionally declare `event_status` as `ENACTED`,
`PROPOSED`, `SCHEDULED`, `REPORTED` or `SCENARIO`, and a nonempty `transmission`
array. Every transmission supplies a validated channel, direction, mechanism and
5/21/63-session horizon list. Without those fields the packet reports that a
specialist mapping is still required; it does not infer causality from a mention.

## Prompt implementation plan

Effort estimates below are focused engineering days, assuming existing data
access and a selected model provider. They are not estimates of the market time
needed to establish forecast skill.

| Increment | Approximate effort | Reviewable completion condition |
|---|---|---|
| 1. Current indicator packet and prompt contract | Implemented starter | Offline replay, arithmetic/cutoff tests, missingness, staged mock-run validation and current capture smoke check |
| 2. Complete evidence for 5–10 assets | 2–3 days | SEC company submissions/facts and issuer ETF holdings with dated extraction checks; event calendar; linked macro/sector/policy news; source-specific release freshness |
| 3. One production agent adapter and readable synthesis | 1–2 days | Seven bounded calls, actual cost/latency receipts, cache, supported-claim audit, Markdown/notebook instrument comparison and correlation/exposure panel |
| 4. Prospective forecast ledger and evaluation | 1–2 days engineering, then accumulating outcomes | Fixed target/model/prompt versions; independent outcome acquisition; mature-label scoring and paired quant-only/context comparison |
| 5. Probability model and calibration | Conditional on suitable evidence | Held-out calibration, useful incremental scores and interval coverage, stability across times/assets and explicit failure/abstention behavior |

The practical target is a useful descriptive end-to-end tool in about **4–7
additional engineering days**. Calibrated forecasts cannot be promised on that
schedule. A 63-session target alone takes roughly three months to mature once;
many instruments on the same dates share shocks and do not substitute for
independent time periods. No historical LLM replay can erase knowledge embedded
in model weights. Do not reopen the repository's reserved final evaluation or
retune on its 42 scored development origins for this work.

Evaluation should retain every scheduled forecast, including failures, and use
Brier/log loss for defined events, CRPS/pinball loss and empirical interval coverage
for distributions, and calibration plots by horizon. Apply time-block uncertainty
estimates to overlapping forecasts. Compare quant-only, quant+cycle and quant+context
on common dates; ablate evidence families. Check relevant baselines, costs,
turnover and missingness before making any trading-performance claim. Prompt
quality also needs sampled source-entailment review, timestamp correctness,
deduplication and instrument-relevance checks; schema validation alone is not a
factuality or forecast-accuracy evaluation.

Source implementation references: [Alpaca daily bars](https://docs.alpaca.markets/us/reference/stockbars),
[Alpaca news](https://docs.alpaca.markets/us/reference/news-3),
[SEC submissions and company facts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
SEC facts must be joined to filing availability, correct fiscal periods and
amendments; an ETF's own company facts do not supply look-through valuation.

### Current-source access audit (2026-09-10)

- State Street's sponsor-provided SPY daily-holdings XLSX returned an
  unauthenticated HTTP 200 and a valid workbook. No account or API key is needed.
  Use only for local analysis, retain attribution, and do not redistribute the
  raw workbook or sponsor content; the product page restricts reproduction and
  transmission without consent.
- Invesco's QQQ page and its browser-facing holdings JSON returned unauthenticated
  HTTP 200 responses (107 holdings dated 2026-09-08). This technical availability
  does **not** authorize a scheduled collector: Invesco's terms prohibit repeated
  automated access except mechanisms it makes generally available and prohibit
  data-mining/extraction tools. The UI endpoint's status under that exception is
  ambiguous. Keep QQQ as browser-saved/manual input unless Invesco gives written
  permission or publishes an expressly supported download/feed.
- Apple and Microsoft investor-relations pages are public. NVIDIA publishes
  public press-release, event, presentation and SEC-filing RSS feeds even though
  a generic scripted request to its main IR page returned HTTP 403. Prefer the
  feeds and SEC documents; none requires an account or API key.
- Federal Reserve pages/RSS, BIS and USTR public releases, the Federal Register
  API, OFAC Sanctions List Service, OFR FSI CSV, and FINRA's margin-statistics XLSX
  were reachable without authentication. Federal Register explicitly requires no
  API key; OFAC automated downloads require a declared User-Agent. Cache by
  publication/update date and apply bounded source-specific pacing and retries.
- Cboe's daily page publicly displayed put/call ratios without authentication,
  but its website terms limit downloads to one personal non-commercial copy and
  restrict storage/reuse; current data policy also treats machine/AI ingestion as
  non-display usage. Do not automate or send Cboe values to an LLM without
  permission or an applicable license.
- AAII exposes the current and a few recent survey readings publicly, but blocks
  a generic scripted client, offers no public API, and reserves the complete
  history for paid members. Do not automate it in v1; membership alone should not
  be assumed to grant machine-ingestion or redistribution rights.

## Verified first run

Five-symbol smoke test: SPY, QQQ, AAPL, MSFT and NVDA (an illustrative watchlist,
not a selected investment portfolio). Cutoff September 9, 2026 at 23:25:49 Buenos
Aires / September 10 at 02:25:49 UTC. All five price panels reached the September 9
completed session; nine FRED series and the bounded news feed were acquired with
no acquisition errors. SPY/QQQ reuse the verified IBKR captures; the three company
prices use Alpaca SIP. Macro observation dates differ and are displayed.

- [Readable report](../reports/meta-analysis/analysis-20260910T022633697928Z-d62a9adb/report.md)
- [Full packet and generated-prompt inputs](../reports/meta-analysis/analysis-20260910T022633697928Z-d62a9adb/packet.json)
- [Immutable source manifest](../datasets/workbench/meta/capture-20260910T022544282533Z-17ee8a8c/snapshot.json)

The first latest-time SIP stock requests returned HTTP 403. A read-only check
confirmed that excluding the latest 20 minutes succeeded; the finalized adapter
records that buffer and rejects partial bars against its effective end. Failed
earlier captures remain separate artifacts. The final verification ran 55 tests
across the new META and existing workbench/input/snapshot modules successfully;
the rendered live report was inspected. Agent staging was exercised with a local
fixture including a failed specialist. No production LLM agents ran, and no
fundamental/geopolitical conclusion or calibrated forecast is claimed by this test.

Evidence-layer continuation on September 10 added SEC identity/submission/fact
normalization, current sponsor-holdings imports, ETF overlap and holdings-linked
news relevance. A manually transcribed, source-linked
[SPY top-holdings table](../datasets/workbench/manual-sources/spy-top-holdings-20260909.csv)
uses State Street's September 9 published top ten; its 38.00% reported weight is
partial coverage, not the full 504-holding portfolio. State Street displays the
fund date, holdings and weights on the official product page.
[Official SPY product data](https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy).

The latest five-symbol smoke run retained complete price, macro and ticker-news
coverage. With the SPY top-ten table it expanded news retrieval to 12 unique direct
or holding tickers; 47 of the bounded 50 articles had an explicit indirect SPY
holding link. It correctly reported `SEC_USER_AGENT_REQUIRED` for AAPL, MSFT and
NVDA because no contact identity was configured. QQQ holdings also remain absent;
v1 has no audited automated current-holdings adapter, while manual sponsor input
is already supported.
The evidence and observation modules currently pass 68 targeted tests. A first
attempt to register the September 9 reference occurred after the September 10
XNYS open; it was removed and the registrar now refuses all post-open backfills.
The quant-only baseline can begin with the next packet captured after a close and
registered before the following open.

Latest evidence-layer artifacts:

- [Five-symbol report with SPY exposure evidence](../reports/meta-analysis/analysis-20260910T134802762458Z-6e5e6df9/report.md)
- [Full analysis packet and prompts](../reports/meta-analysis/analysis-20260910T134802762458Z-6e5e6df9/packet.json)
- [Immutable extended source snapshot](../datasets/workbench/meta/capture-20260910T134415989989Z-59e7f7a1/snapshot.json)

That report predates configuration of the required SEC contact identity and is
retained as an immutable earlier attempt rather than rewritten.

### First registered post-close observation (2026-09-10)

After the September 10 XNYS close and the configured 20-minute market-data buffer,
a completely fresh five-symbol capture ran without reusing the September 9 local
prices. All acquisition requests succeeded. The snapshot contains September 10
Alpaca daily bars for SPY, QQQ, AAPL, MSFT and NVDA; all nine FRED series; bounded
news; the dated SPY top-ten holdings table; and policy-compliant SEC ticker,
submission and company-facts responses for AAPL, MSFT and NVDA. SEC normalization
produced eight recent filings per company and 12 standardized metrics for AAPL
and MSFT, 11 for NVDA. QQQ holdings and survey sentiment remain explicitly missing.

- [SEC-enabled source snapshot](../datasets/workbench/meta/capture-20260910T205420600946Z-6c0bbfe6/snapshot.json)
- [Built report](../reports/meta-analysis/analysis-20260910T205445122807Z-14dfd39d/report.md)
- [Packet](../reports/meta-analysis/analysis-20260910T205445122807Z-14dfd39d/packet.json), hash `6a5d97828bc216d5ba05028e7f5d6db55c8a40a013e4d8c1bcea07e5884b0ba3`
- [Quant-only observation](../datasets/meta-observation/forecasts/2026-09-10-6a5d97828bc216d5.json), hash `f5c0610172460dd47e46c2ebfae96bb3283d266fe6db3840ce57310e6f9ef5a5`

All five forecasts use the September 10 completed close. Their fixed target
sessions are September 17, October 9 and December 9 for the 5/21/63-session
horizons. The observation retains the code-generated uncalibrated reference and
sets `calibrated_meta_forecast` to null; no specialist result was attached.
The outcome/maturity/scoring runner and guarded post-close workflow are now
implemented. Current status is 15 `NOT_DUE`, zero waiting, ready or scored; the
first outcome window opens September 17 at 20:20 UTC. Optional delayed-IBKR packet
context, VIX/VIX3M structure, a transparent three-component risk-appetite proxy,
seven-day supplied-holdings freshness and explicit ES/NQ rollover are also ready
for the next origin. QQQ remains manual by source-policy design. See the
[operations runbook](META_OBSERVATION_OPERATIONS.md).

A live read-only rollover check on September 10 selected ESZ6 and NQZ6 under the
ten-day rule and captured type-3 quotes without an order path:
[manifest](../datasets/ibkr/delayed/delayed-20260910T213722560270Z-17390a1b/manifest.json).

Repository verification after the September 13 agent-control increment:
TypeScript compilation, 18 TypeScript tests and all 371 Python tests passed. The read-only status and
duplicate-origin preflight were exercised against the registered observation.

### Primary event/calendar and ETF-profile continuation (2026-09-11)

The September 11 post-close observation registered before this code increment,
with packet hash `35d07e5f0045f9591bf92c6bd80d1ae8f8e099d0347f77317df11f20914b1b18`
and forecast hash
`99a6064495d5a034b6eb945ee44382633cae64b79882f1b9dfdbc5eaba085b20`.
Its delayed context is missing because IB Gateway closed the API session; the
official-close capture and all core guards passed. Outcome status now contains 30
`NOT_DUE` records across the September 10 and 11 origins.

The frozen `config/meta-primary-sources-v1.json` adds publisher-domain-bound,
bounded adapters for the official FOMC calendar, Fed monetary releases, Federal
Register science/technology documents, NVIDIA investor events and NVIDIA releases.
The final live evidence-only smoke packet is
`reports/meta-analysis/analysis-20260911T205359598727Z-0cf0208e/packet.json`, hash
`59d8445181abcf42785c1bc4022920ec1a89dae6b49dc9d3bb948891e9a4ec31`.
It has zero acquisition failures and normalized 11 FOMC scheduled dates, 15 policy
releases, 20 sector/regulatory records and 20 NVIDIA releases. NVIDIA's valid event
feed contained no items, which remains zero coverage rather than an inferred event.

ETF quality/valuation now joins holdings-derived coverage, concentration and
sector HHI to optional dated sponsor-reported profile metrics. It never creates a
multiple from mismatched quarterly SEC facts. QQQ holdings and sponsor metrics
remain absent until the operator supplies fresh browser-saved files; no automated
Invesco collection was added. The production Terra/Sol/Astra harness completed
the earlier pre-claim-level manual research run. Pi still sees its credential and
model catalog, but the outside-sandbox current-contract smoke reached the provider
and returned `Provided authentication token is expired`. Renew Pi's OpenAI Codex
login once, then rerun the claim-level smoke; older pre-claim-level reports remain
intentionally ineligible for structured forecasts.
