# IB Gateway and official Python API setup

**Verified:** 2026-09-04

This project connects only to a locally authenticated IB Gateway paper session.
IBKR usernames, passwords, and MFA responses must never be stored in this
repository or its `.env` file.

## Version selection

Use the Apple Silicon Latest IB Gateway and TWS API Latest 10.50 together. As of
the verification date, the Mac/Unix Stable API 10.45 does not contain the
official Python client; Latest 10.50 does.

Official download pages:

- IB Gateway: https://portal.interactivebrokers.com/en/trading/ibgateway-latest.php
- TWS API license and downloads: https://interactivebrokers.github.io/

The user must accept IBKR's license and perform both downloads. Do not download
the API SDK from PyPI or another package registry.

## Gateway configuration

1. Install and start IB Gateway.
2. Select Paper Trading and authenticate interactively, including MFA.
3. Open Configure -> Settings -> API -> Settings.
4. Confirm the socket port is `4002`.
5. Keep Read-Only API enabled.
6. Allow connections from localhost only.
7. Apply the settings and leave Gateway running.

Local adapter settings are kept in the ignored `.env` file:

```dotenv
IBKR_HOST=127.0.0.1
IBKR_PORT=4002
IBKR_CLIENT_ID=71
IBKR_MODE=paper
IBKR_READ_ONLY=true
```

## Python API handoff

After downloading the TWS API Mac/Unix ZIP, leave it in `~/Downloads` and tell
the coding agent that both downloads are complete. The agent will:

1. verify the archives and versions;
2. install the official Python client into the project environment from the
   SDK's `source/pythonclient` directory;
3. add a read-only connection probe;
4. verify server time and contract-detail requests;
5. add recent-history and live-capture functionality only after the probe
   passes.

No order method will be used or exposed by the market-data service.

## Local installation record

The 10.50.1 SDK archive was verified with SHA-256:

```text
aa065722ca732a41aab202c7bb72932e179b86e7ec51cefa063eb1983fe9f597
```

It is unpacked under the ignored `.vendor-local/IBJts` directory and installed
into the isolated `.vendor-local/ibkr-python` environment. Keeping the licensed
SDK separate prevents a normal project `uv sync` from removing it. Run the safe
connectivity probe while a paper Gateway session is active:

```bash
npm run ibkr:check
```

## Contract resolution

The first market-data increment uses `reqContractDetails` to resolve permanent
IBKR contract IDs and metadata for SPY, QQQ, ES, and NQ. Its query definitions
are versioned in `config/ibkr-contracts.json`. Futures results are individual,
expiring contracts; the resolver does not substitute a continuous future or
silently select a front month.

With the paper Gateway running, create an immutable contract catalog:

```bash
npm run ibkr:contracts
```

Catalogs are written under the ignored `datasets/ibkr/contracts` directory.
Each file records the exact queries, resolved `conId` values, trading metadata,
Gateway/API versions, capture time, warnings, and a deterministic catalog hash.
The resolver exposes no order or account-data operation.

## Recent historical bars

`config/ibkr-history.json` pins one exact catalog contract for each instrument.
Refresh both the catalog and the configured `conId`/`localSymbol` values before
a configured futures expiration. The default plan downloads twenty recent
trading weekdays in one-day chunks; its rolling-window limiter deliberately
pauses after 55 requests to remain below the configured HMDS pacing budget.

Run the full configured window:

```bash
npm run ibkr:history
```

Run a fast one-chunk integration sample:

```bash
npm run ibkr:history -- --chunks 1
```

The command writes a new directory under `datasets/ibkr/history`. It contains
the append-only raw callback stream, normalized one-minute bars, and a manifest
with exact contract/request parameters, API/catalog versions, byte hashes,
duplicate and gap diagnostics, and any failed chunks. A failure never replaces
an earlier capture.

Historical records are marked `event-time-only`. Their market event timestamp
is historical, but `firstSeenAt` is the local time this project downloaded the
record; the adapter does not claim that the record was originally observable at
its market timestamp. Requests default to twenty minutes behind real time so an
account without up-to-the-second API data can still retrieve recent history.

## Alpaca/IBKR comparison

Compare the newest successful IBKR archive against raw, one-minute Alpaca SIP
bars for SPY and QQQ:

```bash
npm run ibkr:compare
```

The ignored `datasets/comparisons` run directory preserves the exact Alpaca
response pages, normalized reference bars, and a content-hashed report. The
report covers missing and duplicate timestamps, nearest timestamp offsets,
intersection coverage, OHLC and volume differences, session boundaries, and
large-difference samples. IBKR filters its consolidated history, so volume is
expected to differ from Alpaca SIP and is reported rather than corrected.

ES/NQ reference comparison remains explicitly `not-configured` until Massive
Futures data is integrated; the report never substitutes a stock or continuous
futures series.

## Locally timestamped live capture

`config/ibkr-live.json` pins the same exact contracts. With suitable real-time
API market-data subscriptions, run until Ctrl-C/SIGTERM:

```bash
npm run ibkr:capture
```

For an automatic bounded check:

```bash
npm run ibkr:capture -- --duration-seconds 30
```

IBKR five-second `TRADES` bars receive a local `receivedAt` timestamp as the
first callback operation. Exact repeats after reconnect are suppressed;
conflicting repeats stop the capture. Files rotate by instrument and trading
session, and one-minute aggregates include their component count and a
`complete` flag rather than fabricating missing five-second components. An
aggregate's `firstSeenAt` is the last component receipt time—the instant the
aggregate became knowable—while the first and last component timestamps are
also retained. A signal-safe shutdown writes a valid manifest even for a
partial minute.

The verified paper account currently returns API code `354` or `420` for these
live subscriptions, depending on the responding market-data farm: it has no
real-time US stock or CME futures API entitlements.
Historical retrieval is unaffected and is verified working. Until the account
is subscribed, bounded live captures intentionally exit non-zero with status
`partial`, preserve the permission diagnostics, and emit zero synthetic bars.

All commands enforce `IBKR_MODE=paper`, `IBKR_READ_ONLY=true`, localhost, and
port 4002. None imports, constructs, or sends an order.
