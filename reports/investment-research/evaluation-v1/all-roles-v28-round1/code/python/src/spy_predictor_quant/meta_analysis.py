"""Current US-equity research packets; separate from all Cycle 1 experiments.

Capture once, replay locally, calculate indicators, and emit specialist prompts.
Current downloads are never represented as historical point-in-time vintages.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
from threading import Lock
import time
from statistics import NormalDist
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
from jsonschema import Draft202012Validator
import numpy as np

from spy_predictor_quant.cycle_workbench import _instant
from spy_predictor_quant.market_archive import (
    create_immutable_run_directory, file_sha256, write_bytes_exclusive,
    write_json_exclusive, utc_now,
)
from spy_predictor_quant.meta_evidence import (
    company_fundamentals, etf_overlap, etf_quality_valuation, exposure_news_symbols,
    geopolitical_transmission_coverage, instrument_evidence_profile, parse_holdings_csv,
    parse_etf_profile, primary_source_evidence, recent_filings, sec_ticker_map,
    validate_primary_source_config,
)

VERSION = "meta-analysis-v1"
ROOT = Path(__file__).resolve().parents[3]
# Series-specific observation-age limits, in calendar days. These are explicit
# first-version SLAs, not a release-calendar implementation.
CORE_SERIES = {
    "VIXCLS": ("percent_annualized", 7),
    "VXVCLS": ("percent_annualized", 7),
    "DFF": ("percent", 7),
    "T10Y2Y": ("percentage_points", 7),
    "MPRIME": ("percent", 75),
    "GS3M": ("percent", 75),
    "NFCI": ("standard_deviations", 21),
    "STLFSI4": ("index", 21),
    "CPIAUCSL": ("index", 90),
    "INDPRO": ("index", 90),
}
GLOBAL_SERIES = {
    "DGS2": ("percent", 7),
    "DGS5": ("percent", 7),
    "DGS10": ("percent", 7),
    "DGS30": ("percent", 7),
    "T10Y3M": ("percentage_points", 7),
    "DFII10": ("percent", 7),
    "T10YIE": ("percent", 7),
    "SOFR": ("percent", 7),
    "NFCICREDIT": ("standard_deviations", 21),
    "DTWEXBGS": ("index", 7),
    "DCOILWTICO": ("usd_per_barrel", 7),
}
SERIES = {**CORE_SERIES, **GLOBAL_SERIES}
HORIZONS = (5, 21, 63)
MARKET_CONTEXT = {
    "SPY": "US_LARGE_CAP", "QQQ": "US_GROWTH_TECH", "IWM": "US_SMALL_CAP", "DIA": "US_BLUE_CHIP",
    "XLK": "US_TECH_SECTOR", "XLF": "US_FINANCIALS_SECTOR", "XLE": "US_ENERGY_SECTOR",
    "XLV": "US_HEALTHCARE_SECTOR", "EFA": "DEVELOPED_EX_US", "EEM": "EMERGING_MARKETS",
    "EWJ": "JAPAN_EQUITY_PROXY", "FEZ": "EUROZONE_EQUITY_PROXY", "HYG": "HIGH_YIELD_PRICE_PROXY",
    "LQD": "INVESTMENT_GRADE_PRICE_PROXY", "TLT": "LONG_TREASURY_PRICE_PROXY",
    "UUP": "US_DOLLAR_ETF_PROXY", "GLD": "GOLD_ETF_PROXY", "CPER": "COPPER_ETF_PROXY",
    "USO": "OIL_ETF_PROXY",
}
DEFAULT_PRIMARY_SOURCES = ROOT / "config/meta-primary-sources-v1.json"
DEFAULT_PRODUCT_CONFIG = ROOT / "config/meta-product-v1.json"
DEFAULT_FORECAST_POLICY = ROOT / "config/meta-forecast-policy-v2.json"
DEFAULT_OPERATIONS_POLICY = ROOT / "config/meta-operations-v1.json"
PRODUCT_SCHEMA = ROOT / "schemas/meta-product-config-v1.schema.json"
MASSIVE_VOLATILITY_TICKERS = {"VIX": "I:VIX", "VIX3M": "I:VIX3M"}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(",", ":")).encode()).hexdigest()


def symbols(values: list[str]) -> list[str]:
    result = [v.upper() for v in values]
    if not 1 <= len(result) <= 10 or len(set(result)) != len(result):
        raise ValueError("Supply 1–10 unique symbols (5–10 intended; fewer supported for verification)")
    if any(not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", s) for s in result):
        raise ValueError("Unsupported US ticker syntax")
    return result


def load_product_contract(path: Path = DEFAULT_PRODUCT_CONFIG) -> dict:
    contract = json.loads(path.read_text())
    schema = json.loads(PRODUCT_SCHEMA.read_text())
    Draft202012Validator(schema).validate(contract)
    if tuple(contract["horizons_sessions"]) != HORIZONS:
        raise ValueError("META product horizons differ from implemented horizons")
    if (contract["minimum_symbols"], contract["maximum_symbols"]) != (1, 10):
        raise ValueError("META product symbol bounds differ from implementation")
    return contract


def market_period_at(value: datetime) -> str:
    """Classify the actual XNYS market period at a UTC-aware cutoff."""
    cutoff = value.astimezone(timezone.utc)
    cal = xcals.get_calendar("XNYS")
    day = cutoff.date().isoformat()
    if not cal.is_session(day):
        return "CLOSED"
    market_open = cal.session_open(day).to_pydatetime()
    market_close = cal.session_close(day).to_pydatetime()
    if cutoff < market_open:
        return "PREMARKET"
    if cutoff <= market_close:
        return "REGULAR"
    return "POSTMARKET"


def get_raw(url: str, headers: dict | None = None) -> bytes:
    # The public FRED graph endpoint can stall with urllib while its curl route
    # succeeds. Use a bounded HTTPS-only client for this exact public endpoint;
    # authenticated providers continue through the existing header-aware client.
    parsed = urlsplit(url)
    if (not headers and parsed.scheme == "https" and parsed.hostname == "fred.stlouisfed.org"
            and parsed.path == "/graph/fredgraph.csv"):
        result = subprocess.run([
            "curl", "--location", "--fail", "--silent", "--show-error",
            "--proto", "=https", "--proto-redir", "=https", "--max-redirs", "3",
            "--connect-timeout", "5", "--max-time", "25", "--max-filesize", "20000000", "--url", url,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
        if result.returncode:
            raise URLError(f"Public FRED transport failed (curl exit {result.returncode})")
        if len(result.stdout) > 20_000_000:
            raise ValueError("Source exceeds bounded response size")
        return result.stdout
    request = Request(url, headers={"User-Agent": "spy-predictor-current-research/1.0",
                                    **(headers or {})})
    with urlopen(request, timeout=25) as response:
        raw = response.read(20_000_001)
    if len(raw) > 20_000_000:
        raise ValueError("Source exceeds bounded response size")
    return raw


class SecHttpClient:
    """Conservative, identified access to public SEC/EDGAR data endpoints."""

    RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})

    def __init__(self, user_agent: str, *, requests_per_second: float = 2,
                 max_attempts: int = 4, retry_base_seconds: float = .5,
                 maximum_server_wait_seconds: float = 60,
                 sleeper=time.sleep, monotonic=time.monotonic) -> None:
        if not user_agent.strip():
            raise ValueError("SEC User-Agent is required")
        if not 0 < requests_per_second < 10:
            raise ValueError("SEC request rate must remain below 10 requests/second")
        if max_attempts < 1:
            raise ValueError("SEC max_attempts must be positive")
        self.user_agent = user_agent.strip()
        self.minimum_interval = 1 / requests_per_second
        self.max_attempts = max_attempts
        self.retry_base_seconds = retry_base_seconds
        self.maximum_server_wait_seconds = maximum_server_wait_seconds
        self.sleeper = sleeper
        self.monotonic = monotonic
        self._last_request_started: float | None = None
        self._pace_lock = Lock()

    def get(self, url: str) -> bytes:
        for attempt in range(self.max_attempts):
            self._pace()
            try:
                return get_raw(url, {"User-Agent": self.user_agent})
            except HTTPError as exc:
                if exc.code not in self.RETRYABLE_STATUS or attempt + 1 == self.max_attempts:
                    raise
                retry_after = self._retry_after_seconds(exc)
                # Do not retry sooner than the SEC requested. For an unusually
                # long pause, fail closed and let a later capture retry instead.
                if retry_after is not None and retry_after > self.maximum_server_wait_seconds:
                    raise
                self.sleeper(retry_after if retry_after is not None else
                             self.retry_base_seconds * (2**attempt))
            except (URLError, TimeoutError, OSError):
                if attempt + 1 == self.max_attempts:
                    raise
                self.sleeper(self.retry_base_seconds * (2**attempt))
        raise AssertionError("unreachable")

    def _pace(self) -> None:
        # One client is shared by every SEC endpoint in a capture, so this also
        # remains safe if acquisition is parallelized in a later increment.
        with self._pace_lock:
            now = self.monotonic()
            if self._last_request_started is not None:
                delay = self.minimum_interval - (now - self._last_request_started)
                if delay > 0:
                    self.sleeper(delay)
                    now = self.monotonic()
            self._last_request_started = now

    @staticmethod
    def _retry_after_seconds(error: HTTPError) -> float | None:
        value = error.headers.get("Retry-After") if error.headers else None
        if not value:
            return None
        try:
            return max(0, float(value))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None


def archive(root: Path, identity: str, url: str, raw: bytes, *, kind: str,
            received_at: str | None = None, **metadata) -> dict:
    path = root / "raw" / (identity + ".raw")
    write_bytes_exclusive(path, raw)
    return {"id": identity, "url": url, "kind": kind,
            "path": str(path.relative_to(root)), "sha256": file_sha256(path),
            "retrieved_at": received_at or utc_now(), **metadata}


def _capture_intraday_bars(run: Path, url: str, headers: dict, symbol: str,
                           feed: str, data_end: datetime, evidence_state: str,
                           coverage: str, expected_delay: int,
                           fetcher=get_raw) -> dict:
    raw = fetcher(url, headers)
    payload = json.loads(raw)
    if payload.get("symbol") != symbol or not isinstance(payload.get("bars"), list):
        raise ValueError("Malformed or mismatched Alpaca intraday bars")
    if payload.get("next_page_token"):
        raise ValueError("Unexpected intraday pagination; refusing partial coverage")
    return archive(run, f"intraday-bars-{symbol}", url, raw, kind="alpaca_intraday_bars",
                   symbol=symbol, symbols=[symbol], feed=feed, timeframe="1Min", adjustment="split",
                   data_end=data_end.isoformat(), evidence_state=evidence_state,
                   exchange_coverage=coverage, expected_delay_minutes=expected_delay)


def _capture_intraday_snapshot(run: Path, url: str, headers: dict, symbol: str,
                               feed: str, evidence_state: str, coverage: str,
                               expected_delay: int, fetcher=get_raw) -> dict:
    raw = fetcher(url, headers)
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not any(
            isinstance(payload.get(key), dict) for key in ("latestTrade", "latestQuote", "minuteBar")):
        raise ValueError("Malformed Alpaca intraday snapshot")
    return archive(run, f"intraday-latest-{symbol}", url, raw, kind="alpaca_intraday_snapshot",
                   symbol=symbol, symbols=[symbol], feed=feed, evidence_state=evidence_state,
                   exchange_coverage=coverage, expected_delay_minutes=expected_delay)


def parse_massive_index_snapshot(raw: bytes, expected_ticker: str, cutoff: datetime) -> dict:
    """Validate one licensed Massive index snapshot without inferring entitlement."""
    payload = json.loads(raw)
    rows = payload.get("results") if isinstance(payload, dict) else None
    if payload.get("status") != "OK" or not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("Massive index snapshot must contain exactly one successful result")
    row = rows[0]
    if row.get("ticker") != expected_ticker or row.get("error"):
        raise ValueError("Massive index snapshot ticker or entitlement mismatch")
    timeframe = row.get("timeframe")
    if timeframe not in {"REAL-TIME", "DELAYED"}:
        raise ValueError("Massive index snapshot lacks an explicit timeframe")
    value = row.get("value")
    timestamp_ns = row.get("last_updated")
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0
            or isinstance(timestamp_ns, bool) or not isinstance(timestamp_ns, int)
            or timestamp_ns <= 0):
        raise ValueError("Massive index snapshot requires positive numeric value and timestamp")
    observed = datetime.fromtimestamp(timestamp_ns / 1_000_000_000, timezone.utc)
    cutoff = _instant(cutoff)
    if observed > cutoff + timedelta(seconds=5):
        raise ValueError("Massive index snapshot timestamp follows packet cutoff")
    age_seconds = max(0, round((cutoff - observed).total_seconds()))
    maximum_age = 120 if timeframe == "REAL-TIME" else 30 * 60
    status = ("LIVE_INTRADAY" if timeframe == "REAL-TIME" else "DELAYED")
    if age_seconds > maximum_age:
        status = "STALE"
    return {
        "ticker": expected_ticker, "value": float(value), "unit": "percent_annualized",
        "observed_at": observed.isoformat(), "age_at_cutoff_seconds": age_seconds,
        "maximum_age_seconds": maximum_age, "status": status,
        "provider_timeframe": timeframe, "market_status": row.get("market_status"),
        "session": row.get("session") if isinstance(row.get("session"), dict) else {},
        "source": "MASSIVE_LICENSED_INDICES_SNAPSHOT",
    }


def capture(root: Path, targets: list[str], etfs: list[str], local_prices: Path | None,
            evidence_file: Path | None, holdings_files: dict[str, Path] | None = None,
            macro_only: bool = False, delayed_context_file: Path | None = None,
            primary_sources_file: Path | None = DEFAULT_PRIMARY_SOURCES,
            etf_profile_files: dict[str, Path] | None = None,
            market_data_mode: str = "completed-close",
            intraday_feed: str = "iex",
            operations_policy_path: Path | None = None,
            cache_root: Path | None = None) -> Path:
    if market_data_mode not in {"completed-close", "intraday"}:
        raise ValueError("market_data_mode must be completed-close or intraday")
    if intraday_feed not in {"iex", "sip-delayed"}:
        raise ValueError("intraday_feed must be iex or sip-delayed")
    run = create_immutable_run_directory(root, "capture")
    (run / "raw").mkdir()
    start = max(date(2025, 8, 1), datetime.now(timezone.utc).date() - timedelta(days=420))
    sources, errors = {}, {}
    cache = None
    cache_stats = {"hits": 0, "stored": 0}
    cache_stats_lock = Lock()
    capture_started = datetime.now(timezone.utc)
    cache_calendar = xcals.get_calendar("XNYS")
    cache_sessions = cache_calendar.sessions_in_range(
        (capture_started.date() - timedelta(days=14)).isoformat(), capture_started.date().isoformat())
    cache_eligible = [session for session in cache_sessions
                      if cache_calendar.session_close(session).to_pydatetime() + timedelta(minutes=20)
                      <= capture_started]
    completed_close_identity = (cache_eligible[-1].date().isoformat()
                                if cache_eligible else "no-completed-close")
    if operations_policy_path:
        from spy_predictor_quant.meta_operations import ReleaseCache, load_operations_policy
        cache = ReleaseCache(cache_root or ROOT / "datasets/meta-cache",
                             load_operations_policy(operations_policy_path))

    def acquire(category: str, source: str, release_identity: str,
                url: str, headers: dict | None = None, fetch_override=None) -> bytes:
        if not cache:
            return fetch_override() if fetch_override else get_raw(url, headers)
        policy = cache.policy["cache_policies"][category]
        identity = release_identity
        if policy["mode"] == "ttl":
            bucket = int(capture_started.timestamp()) // policy["ttl_seconds"]
            identity = f"{release_identity}:bucket-{bucket}"
        result = cache.fetch(category, source, identity,
                             fetch_override or (lambda: get_raw(url, headers)), capture_started)
        with cache_stats_lock:
            cache_stats["hits" if result["status"] == "HIT" else "stored"] += 1
        return result["payload"]

    def fred(series):
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urlencode({
            "id": series, "cosd": (date.today() - timedelta(days=1100)).isoformat()})
        raw = acquire("macro_release", f"fred:{series}",
                      f"{series}:poll:{capture_started.date().isoformat()}", url)
        # Validate before marking an HTTP-successful HTML response as usable.
        parse_fred(raw, series)
        return archive(run, series, url, raw, kind="fred_csv")

    def guarded(identity, function):
        try:
            return identity, function(), None
        except (HTTPError, URLError, TimeoutError, subprocess.TimeoutExpired, OSError, ValueError, KeyError) as exc:
            # Do not print request headers, credentials or provider response bodies.
            reason = f"HTTP_{exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__
            return identity, None, reason

    with ThreadPoolExecutor(max_workers=3) as pool:
        for identity, source, error in pool.map(
                lambda key: guarded(key, lambda: fred(key)), SERIES):
            if source:
                sources[identity] = source
            else:
                errors[identity] = error

    holdings_profiles = {}
    for fund, holding_path in (holdings_files or {}).items():
        try:
            raw = holding_path.read_bytes()
            profile = parse_holdings_csv(raw, fund, _instant(utc_now()))
            identity = f"holdings-{fund}"
            sources[identity] = archive(run, identity, profile["source_url"], raw,
                                        kind="etf_holdings_csv", symbol=fund,
                                        holdings_as_of=profile["as_of"],
                                        acquisition_method="manual-sponsor-table-or-export")
            holdings_profiles[fund] = profile
        except (OSError, UnicodeError, ValueError, KeyError) as exc:
            errors[f"holdings-{fund}"] = type(exc).__name__

    for fund, profile_path in (etf_profile_files or {}).items():
        try:
            raw = profile_path.read_bytes()
            profile = parse_etf_profile(json.loads(raw), fund, _instant(utc_now()))
            identity = f"etf-profile-{fund}"
            sources[identity] = archive(
                run, identity, profile["source_url"], raw, kind="etf_sponsor_profile",
                symbol=fund, profile_as_of=profile["as_of"],
                acquisition_method="manual-browser-saved-sponsor-profile")
        except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            errors[f"etf-profile-{fund}"] = type(exc).__name__

    supplemental_errors = {}
    if primary_sources_file and not macro_only:
        try:
            config_raw = primary_sources_file.read_bytes()
            primary_sources = validate_primary_source_config(json.loads(config_raw))
            sources["primary-source-config"] = archive(
                run, "primary-source-config", "repository-config://meta-primary-sources-v1",
                config_raw, kind="primary_source_config")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            primary_sources = []
            supplemental_errors["primary-source-config"] = type(exc).__name__
        for definition in primary_sources:
            identity = f"primary-source-{definition['id']}"
            try:
                raw = acquire("publisher_feed", f"primary:{definition['id']}",
                              definition["url"], definition["url"])
                # Parse before archiving so an HTML/error response cannot masquerade as a feed.
                primary_source_evidence(raw, definition, _instant(utc_now()), targets, utc_now())
                sources[identity] = archive(
                    run, identity, definition["url"], raw, kind="primary_source_feed",
                    source_id=definition["id"], primary_kind=definition["kind"],
                    source_format=definition["format"], publisher=definition.get("publisher"))
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError,
                    KeyError, json.JSONDecodeError) as exc:
                supplemental_errors[identity] = (
                    f"HTTP_{exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__)

    stocks = [symbol for symbol in targets if symbol not in etfs]
    sec_user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if stocks and not macro_only and not sec_user_agent:
        for symbol in stocks:
            errors[f"sec-{symbol}"] = "SEC_USER_AGENT_REQUIRED"
    elif stocks and not macro_only:
        sec = SecHttpClient(sec_user_agent)
        ticker_url = "https://www.sec.gov/files/company_tickers.json"
        try:
            ticker_raw = acquire("sec_filing", "sec:company-tickers",
                                 f"company-tickers:{capture_started.date().isoformat()}",
                                 ticker_url, {"User-Agent": sec.user_agent},
                                 lambda: sec.get(ticker_url))
            mapping = sec_ticker_map(json.loads(ticker_raw))
            sources["sec-tickers"] = archive(run, "sec-tickers", ticker_url, ticker_raw, kind="sec_ticker_map")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            mapping = {}
            errors["sec-tickers"] = f"HTTP_{exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__
        for symbol in stocks:
            if symbol not in mapping:
                errors[f"sec-{symbol}"] = "TICKER_NOT_RESOLVED"
                continue
            cik = mapping[symbol]["cik"]
            for suffix, url, kind in (
                ("submissions", f"https://data.sec.gov/submissions/CIK{cik}.json", "sec_submissions"),
                ("facts", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", "sec_companyfacts"),
            ):
                identity = f"sec-{suffix}-{symbol}"
                try:
                    raw = acquire("sec_filing", f"sec:{symbol}:{suffix}",
                                  f"{symbol}:{suffix}:poll:{capture_started.date().isoformat()}",
                                  url, {"User-Agent": sec.user_agent}, lambda: sec.get(url))
                    data = json.loads(raw)
                    if suffix == "submissions":
                        recent_filings(data, symbol, _instant(utc_now()))
                    elif str(data.get("cik", "")).zfill(10) != cik:
                        raise ValueError("SEC companyfacts CIK mismatch")
                    sources[identity] = archive(run, identity, url, raw, kind=kind,
                                                symbol=symbol, cik=cik,
                                                entity_name=mapping[symbol]["entity_name"])
                except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                    errors[identity] = f"HTTP_{exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__

    key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret} if key and secret else None
    feed = os.environ.get("ALPACA_DATA_FEED", "sip")
    if feed not in {"sip", "iex"}:
        raise ValueError("ALPACA_DATA_FEED must be sip or iex; no silent feed fallback")
    for symbol in ([] if macro_only else targets):
        def price_source():
            local = local_prices / f"{symbol}-daily.json" if local_prices else None
            if local and local.is_file():
                raw = local.read_bytes()
                data = json.loads(raw)
                if (data["symbol"] != symbol or data["whatToShow"] != "TRADES"
                        or data["barSize"] != "1 day" or data["useRTH"] != 1):
                    raise ValueError("Local capture has incompatible symbol or price convention")
                return archive(run, f"price-{symbol}",
                    "https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/", raw,
                    kind="ibkr_daily", received_at=data["received_at"], symbol=symbol,
                    symbols=[symbol],
                    adjustment="split;cash-dividends-excluded", feed="IBKR-TRADES-RTH")
            if not headers:
                raise ValueError("Alpaca credentials required for uncaptured prices")
            # Historical SIP access may exclude the latest 15 minutes even
            # outside RTH. A fixed 20-minute buffer supports delayed entitlements.
            data_end = (datetime.now(timezone.utc)-timedelta(minutes=20)).isoformat()
            url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars?" + urlencode({
                "timeframe": "1Day", "start": start.isoformat() + "T00:00:00Z",
                "end": data_end, "adjustment": "split", "feed": feed,
                "sort": "asc", "limit": 10000})
            raw = acquire("completed_close", f"alpaca:{symbol}:daily",
                          f"{symbol}:{feed}:{completed_close_identity}:split", url, headers)
            data = json.loads(raw)
            if data.get("symbol") != symbol:
                raise ValueError("Alpaca returned a different instrument identity")
            if data.get("next_page_token"):
                raise ValueError("Unexpected price pagination; refusing a partial price window")
            return archive(run, f"price-{symbol}", url, raw, kind="alpaca_daily",
                           symbol=symbol, symbols=[symbol], adjustment="split;cash-dividends-excluded", feed=feed,
                           data_end=data_end, request_delay_minutes=20)
        identity, source, error = guarded(f"price-{symbol}", price_source)
        if source:
            sources[identity] = source
        else:
            errors[identity] = error

    if headers and not macro_only:
        def context_price_source(symbol: str):
            data_end = (datetime.now(timezone.utc)-timedelta(minutes=20)).isoformat()
            url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars?" + urlencode({
                "timeframe": "1Day", "start": start.isoformat() + "T00:00:00Z",
                "end": data_end, "adjustment": "split", "feed": feed,
                "sort": "asc", "limit": 10000})
            raw = acquire("completed_close", f"alpaca:{symbol}:context-daily",
                          f"{symbol}:{feed}:{completed_close_identity}:split", url, headers)
            data = json.loads(raw)
            if data.get("symbol") != symbol or data.get("next_page_token"):
                raise ValueError("Alpaca context price identity or pagination failure")
            return archive(run, f"context-price-{symbol}", url, raw, kind="alpaca_daily_context",
                           symbol=symbol, symbols=[symbol], context_family=MARKET_CONTEXT[symbol],
                           adjustment="split;cash-dividends-excluded", feed=feed,
                           data_end=data_end, request_delay_minutes=20)
        missing_context = [symbol for symbol in MARKET_CONTEXT if symbol not in targets]
        with ThreadPoolExecutor(max_workers=3) as pool:
            for identity, source, error in pool.map(
                    lambda symbol: guarded(f"context-price-{symbol}",
                                           lambda: context_price_source(symbol)), missing_context):
                if source:
                    sources[identity] = source
                else:
                    supplemental_errors[identity] = error

    if market_data_mode == "intraday" and not macro_only:
        if not headers:
            for symbol in targets:
                errors[f"intraday-{symbol}"] = "ALPACA_CREDENTIALS_REQUIRED"
        else:
            requested_at = datetime.now(timezone.utc)
            if intraday_feed == "iex":
                bars_feed, latest_feed = "iex", "iex"
                data_end = requested_at - timedelta(minutes=1)
                evidence_state, coverage = "REAL_TIME", "IEX_ONLY"
                expected_delay = 0
            else:
                bars_feed, latest_feed = "sip", "delayed_sip"
                data_end = requested_at - timedelta(minutes=20)
                evidence_state, coverage = "DELAYED", "ALL_US_EXCHANGES"
                expected_delay = 15
            for symbol in targets:
                bars_identity = f"intraday-bars-{symbol}"
                bars_url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars?" + urlencode({
                    "timeframe": "1Min",
                    "start": (requested_at - timedelta(days=14)).isoformat(),
                    "end": data_end.isoformat(),
                    "adjustment": "split",
                    "feed": bars_feed,
                    "sort": "asc",
                    "limit": 10000,
                })
                identity, source, error = guarded(bars_identity, lambda url=bars_url, symbol=symbol: (
                    _capture_intraday_bars(
                        run, url, headers, symbol, bars_feed, data_end,
                        evidence_state, coverage, expected_delay,
                        lambda request_url, request_headers: acquire(
                            "intraday_market", f"alpaca:{symbol}:intraday-bars",
                            request_url, request_url, request_headers))))
                if source:
                    sources[identity] = source
                else:
                    errors[identity] = error
                latest_identity = f"intraday-latest-{symbol}"
                latest_url = f"https://data.alpaca.markets/v2/stocks/{symbol}/snapshot?" + urlencode({
                    "feed": latest_feed,
                })
                identity, source, error = guarded(latest_identity, lambda url=latest_url, symbol=symbol: (
                    _capture_intraday_snapshot(
                        run, url, headers, symbol, latest_feed,
                        evidence_state, coverage, expected_delay,
                        lambda request_url, request_headers: acquire(
                            "intraday_market", f"alpaca:{symbol}:snapshot",
                            request_url, request_url, request_headers))))
                if source:
                    sources[identity] = source
                else:
                    errors[identity] = error

    if not macro_only:
        massive_key = os.environ.get("MASSIVE_API_KEY", "").strip()
        if not massive_key:
            supplemental_errors["current-volatility"] = "MASSIVE_API_KEY_REQUIRED"
        else:
            massive_headers = {"Authorization": f"Bearer {massive_key}"}
            for label, ticker in MASSIVE_VOLATILITY_TICKERS.items():
                identity = f"current-volatility-{label}"
                url = "https://api.massive.com/v3/snapshot/indices?" + urlencode({"ticker": ticker})

                def volatility_source(identity=identity, label=label, ticker=ticker, url=url):
                    raw = acquire("intraday_market", f"massive:{ticker}:snapshot", url,
                                  url, massive_headers)
                    point = parse_massive_index_snapshot(raw, ticker, _instant(utc_now()))
                    return archive(
                        run, identity, url, raw, kind="massive_index_snapshot",
                        ticker=ticker, index_name=label, observed_at=point["observed_at"],
                        provider_timeframe=point["provider_timeframe"],
                        market_data_type=point["status"],
                        acquisition_method="licensed-massive-indices-snapshot")

                found_identity, source, error = guarded(identity, volatility_source)
                if source:
                    sources[found_identity] = source
                else:
                    supplemental_errors[found_identity] = error

    if headers and not macro_only:
        def news_source():
            holding_symbols, exposures = exposure_news_symbols(holdings_profiles)
            query_symbols = list(dict.fromkeys(targets + holding_symbols))
            url = "https://data.alpaca.markets/v1beta1/news?" + urlencode({
                "symbols": ",".join(query_symbols), "start": (date.today()-timedelta(days=7)).isoformat(),
                "sort": "desc", "limit": 50, "include_content": "false"})
            raw = acquire("publisher_feed", "alpaca:news", url, url, headers)
            data = json.loads(raw)
            if not isinstance(data.get("news"), list):
                raise ValueError("Malformed news response")
            return archive(run, "news", url, raw, kind="alpaca_news",
                           coverage="LATEST_50_IN_7_DAYS", truncated=bool(data.get("next_page_token")),
                           queried_symbols=query_symbols, etf_exposure_map=exposures)
        identity, source, error = guarded("news", news_source)
        if source:
            sources[identity] = source
        else:
            errors[identity] = error
    else:
        errors["news"] = "NO_NEWS_CAPTURE"
    if evidence_file:
        raw = evidence_file.read_bytes()
        validate_external(json.loads(raw), _instant(utc_now()))
        sources["external"] = archive(run, "external", "user-supplied-evidence",
                                       raw, kind="external_evidence")
    if delayed_context_file:
        try:
            raw = delayed_context_file.read_bytes()
            profile = validate_delayed_context(json.loads(raw), _instant(utc_now()))
            sources["ibkr-delayed-context"] = archive(
                run, "ibkr-delayed-context",
                "https://www.interactivebrokers.com/campus/ibkr-api-page/market-data-subscriptions/",
                raw, kind="ibkr_delayed_quotes", observed_at=profile["observed_at"],
                instruments=sorted(profile["instruments"]),
                market_data_type="DELAYED", source_path=str(delayed_context_file.resolve()))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            errors["ibkr-delayed-context"] = type(exc).__name__
    payload = {"version": VERSION, "as_of": utc_now(), "symbols": targets,
               "etfs": etfs, "context_symbols": MARKET_CONTEXT,
               "sources": sources, "acquisition_errors": errors,
               "supplemental_acquisition_errors": supplemental_errors,
               "market_data_request": {"mode": market_data_mode,
                                       "intraday_feed": intraday_feed if market_data_mode == "intraday" else None},
               "operational_acquisition": ({"cache": cache_stats,
                                             "budget": cache.budget.snapshot()}
                                            if cache else None),
               "evidence": "CURRENT_RETRIEVAL;NOT_HISTORICAL_POINT_IN_TIME",
               "implementation_sha256": file_sha256(Path(__file__))}
    payload["snapshot_hash"] = digest(payload)
    path = run / "snapshot.json"
    write_json_exclusive(path, payload)
    return path


def parse_fred(raw: bytes, series: str) -> list[tuple[date, float]]:
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if not rows or series not in rows[0]:
        raise ValueError("Missing expected FRED series column")
    output = []
    for row in rows:
        value = row[series]
        day = date.fromisoformat(row.get("observation_date", row.get("DATE", "")))
        if value in {".", ""}:
            continue
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Nonfinite macro observation")
        output.append((day, number))
    if not output or [r[0] for r in output] != sorted({r[0] for r in output}):
        raise ValueError("Need distinct ordered FRED observations")
    return output


def validate_external(payload: object, cutoff: datetime) -> list[dict]:
    if not isinstance(payload, list):
        raise ValueError("External evidence must be a list")
    identities = set()
    for item in payload:
        if (not isinstance(item, dict) or not re.fullmatch(r"ext-[a-zA-Z0-9_-]+", item.get("id", ""))
                or item["id"] in identities or not item.get("url", "").startswith("https://")
                or item.get("kind") not in {"filing", "etf_holdings", "news", "policy", "survey"}
                or not isinstance(item.get("text"), str) or not 1 <= len(item["text"]) <= 16000
                or not isinstance(item.get("symbols"), list)
                or any(not isinstance(s, str) for s in item["symbols"])):
            raise ValueError("Invalid external evidence identity, kind, text, symbols, or URL")
        event_status = item.get("event_status")
        if event_status is not None and event_status not in {
                "ENACTED", "PROPOSED", "SCHEDULED", "REPORTED", "SCENARIO"}:
            raise ValueError("Invalid geopolitical event status")
        transmission = item.get("transmission")
        if transmission is not None:
            if not isinstance(transmission, list) or not transmission:
                raise ValueError("Geopolitical transmission must be a nonempty list")
            for link in transmission:
                if (not isinstance(link, dict) or link.get("channel") not in {
                        "REVENUE", "COST", "SUPPLY_CHAIN", "COUNTRY", "CURRENCY",
                        "REGULATION", "SANCTIONS", "TARIFF", "RATES"}
                        or link.get("direction") not in {"POSITIVE", "NEGATIVE", "MIXED", "UNKNOWN"}
                        or not isinstance(link.get("mechanism"), str) or not link["mechanism"].strip()
                        or not isinstance(link.get("horizon_sessions"), list)
                        or any(value not in HORIZONS for value in link["horizon_sessions"])):
                    raise ValueError("Invalid geopolitical transmission link")
        if not _instant(item["published_at"]) <= _instant(item["retrieved_at"]) <= cutoff:
            raise ValueError("External evidence timing violates cutoff")
        identities.add(item["id"])
    return payload


def validate_delayed_context(payload: object, cutoff: datetime,
                             maximum_age: timedelta = timedelta(hours=2)) -> dict:
    """Normalize a bounded IBKR delayed capture without treating it as a close."""
    if (not isinstance(payload, dict) or payload.get("schemaVersion") != "ibkr-delayed-quotes-v1"
            or payload.get("status") not in {"ok", "partial"}
            or not isinstance(payload.get("quotes"), dict)):
        raise ValueError("Malformed IBKR delayed quote context")
    observed = _instant(payload["observedAt"])
    if observed > cutoff or cutoff - observed > maximum_age:
        raise ValueError("IBKR delayed quote context is future-dated or too old")
    instruments = {}
    for instrument, quote in payload["quotes"].items():
        if (not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", instrument)
                or not isinstance(quote, dict) or quote.get("marketDataType") != 3
                or not isinstance(quote.get("ticks"), dict)):
            raise ValueError("IBKR context contains an invalid instrument or market-data type")
        prices = {}
        for field in ("DELAYED_BID", "DELAYED_ASK", "DELAYED_LAST", "MARK_PRICE"):
            tick = quote["ticks"].get(field)
            if tick is None:
                continue
            value = float(tick["value"])
            received = _instant(tick["receivedAt"])
            if value == -1:  # IBKR's explicit unavailable bid/ask sentinel.
                continue
            if not math.isfinite(value) or value <= 0 or received > observed + timedelta(seconds=5):
                raise ValueError("IBKR context contains an invalid price or receipt time")
            prices[field.lower()] = value
        if not prices:
            continue
        last_as_of = _instant(quote["lastAsOf"]) if quote.get("lastAsOf") else None
        if last_as_of and last_as_of > observed:
            raise ValueError("IBKR delayed last timestamp follows capture time")
        instruments[instrument] = {
            **prices,
            "con_id": quote.get("conId"), "local_symbol": quote.get("localSymbol"),
            "last_as_of": last_as_of.isoformat() if last_as_of else None,
            "age_at_capture_seconds": quote.get("lastAgeSeconds"),
        }
    if not instruments:
        raise ValueError("IBKR context contains no usable delayed prices")
    return {"status": payload["status"].upper(), "observed_at": observed.isoformat(),
            "age_at_packet_seconds": round((cutoff-observed).total_seconds()),
            "market_data_type": "DELAYED", "instruments": instruments,
            "limitations": ["informational delayed quotes, not executable prices",
                            "stock quotes are normally about 15 minutes delayed; futures about 10 minutes",
                            "timestamps and entitlements determine actual age"]}


def month_shift(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def macro_metrics(histories: dict, cutoff: datetime) -> dict:
    out = {}
    for key, (unit, max_age) in SERIES.items():
        rows = [(day, value) for day, value in histories.get(key, []) if day <= cutoff.date()]
        if not rows:
            out[key] = {"status": "MISSING", "value": None}
            continue
        day, value = rows[-1]
        age = (cutoff.date() - day).days
        out[key] = {"status": "FRESH" if age <= max_age else "STALE", "value": value,
                    "observed_date": day.isoformat(), "age_days": age, "unit": unit,
                    "source_ids": [key], "max_age_days": max_age}
        previous = next((v for d, v in reversed(rows) if d <= day-timedelta(days=90)), None)
        out[key]["change_90_calendar_days"] = value - previous if previous is not None else None
        if key in {"CPIAUCSL", "INDPRO"}:
            prior = dict(rows).get(month_shift(day, -12))
            out[key]["yoy_pct"] = 100*(value/prior-1) if prior and prior > 0 else None
        if key == "VIXCLS":
            history = [v for _, v in rows[-756:]]
            out[key]["fear_proxy_percentile"] = (100*(sum(v < value for v in history)
                + .5*sum(v == value for v in history))/len(history)) if len(history) >= 60 else None
            out[key]["percentile_observations"] = len(history)
            out[key]["meaning"] = "Volatility-expectations proxy; not a survey or directional forecast"
    prime = dict(histories.get("MPRIME", []))
    bills = dict(histories.get("GS3M", []))
    common = sorted(d for d in prime.keys() & bills.keys() if d <= cutoff.date())
    if common:
        day = common[-1]
        value = 100*(prime[day]-bills[day])
        earlier = month_shift(day, -3)
        change = value-100*(prime[earlier]-bills[earlier]) if earlier in prime and earlier in bills else None
        out["lending_rate_proxy"] = {"value": value, "unit": "basis_points",
            "observed_date": day.isoformat(), "change_exact_3_months_bps": change,
            "status": "FRESH" if (cutoff.date()-day).days <= 75 else "STALE",
            "source_ids": ["MPRIME", "GS3M"],
            "formula": "100*(MPRIME-GS3M), same month; not corporate default spread"}
    else:
        out["lending_rate_proxy"] = {"status": "MISSING", "value": None}
    vix = dict(histories.get("VIXCLS", []))
    vxv = dict(histories.get("VXVCLS", []))
    common_vix = sorted(day for day in vix.keys() & vxv.keys() if day <= cutoff.date())
    if common_vix:
        day = common_vix[-1]
        ratio = vix[day] / vxv[day] if vxv[day] > 0 else None
        out["vix_term_structure_proxy"] = {
            "status": "FRESH" if (cutoff.date()-day).days <= 7 else "STALE",
            "value": ratio, "unit": "VIX/VIX3M ratio", "observed_date": day.isoformat(),
            "spread_points": vix[day]-vxv[day], "source_ids": ["VIXCLS", "VXVCLS"],
            "formula": "VIXCLS / VXVCLS on latest common observation date",
            "meaning": "ratio above 1 indicates front volatility above three-month volatility"}
    else:
        out["vix_term_structure_proxy"] = {"status": "MISSING", "value": None}
    out["survey_fear_greed"] = {"status": "MISSING", "value": None,
        "reason": "No qualified survey/composite adapter; VIX and momentum are distinct proxies"}
    out["fed_tax_interpretation"] = "Fed interest rate (tasa Fed), represented by effective DFF"
    return out


def current_volatility_metrics(raw: dict[str, bytes], cutoff: datetime,
                               histories: dict, errors: dict | None = None) -> dict:
    """Build a same-session VIX/VIX3M panel only from entitled index snapshots."""
    points = {}
    reasons = {}
    for label, ticker in MASSIVE_VOLATILITY_TICKERS.items():
        identity = f"current-volatility-{label}"
        if identity not in raw:
            reasons[label] = (errors or {}).get(identity, "NOT_CAPTURED")
            continue
        try:
            points[label] = parse_massive_index_snapshot(raw[identity], ticker, cutoff)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            reasons[label] = type(exc).__name__
    if "VIX" in points:
        history = [value for day, value in histories.get("VIXCLS", [])
                   if day <= cutoff.date()][-756:]
        if len(history) >= 60:
            value = points["VIX"]["value"]
            points["VIX"]["fear_proxy_percentile"] = 100 * (
                sum(item < value for item in history) + .5 * sum(item == value for item in history)
            ) / len(history)
            points["VIX"]["percentile_observations"] = len(history)
    if set(points) != {"VIX", "VIX3M"}:
        return {"status": "MISSING_INTRADAY", "provider": "Massive Indices Snapshot",
                "values": points, "missing": sorted(set(MASSIVE_VOLATILITY_TICKERS) - set(points)),
                "reasons": reasons,
                "fallback": "FRED latest completed daily VIXCLS/VXVCLS remains separate"}
    timestamps = [_instant(points[label]["observed_at"]) for label in ("VIX", "VIX3M")]
    skew = abs(round((timestamps[0] - timestamps[1]).total_seconds()))
    leg_statuses = {points[label]["status"] for label in points}
    if "STALE" in leg_statuses or skew > 300:
        status = "STALE"
    elif "DELAYED" in leg_statuses:
        status = "DELAYED"
    else:
        status = "LIVE_INTRADAY"
    ratio = points["VIX"]["value"] / points["VIX3M"]["value"]
    return {
        "status": status, "provider": "Massive Indices Snapshot",
        "provider_timeframes": sorted({points[label]["provider_timeframe"] for label in points}),
        "observed_at": max(timestamps).isoformat(), "leg_timestamp_skew_seconds": skew,
        "values": points, "vix_vix3m_ratio": ratio,
        "spread_points": points["VIX"]["value"] - points["VIX3M"]["value"],
        "source_ids": ["current-volatility-VIX", "current-volatility-VIX3M"],
        "meaning": "Timestamped licensed index snapshots; provider timeframe and age govern use",
    }


def global_market_metrics(histories: dict, cutoff: datetime) -> dict:
    """Derived panels use only same-date observations and expose absent families."""
    def common_panel(keys: tuple[str, ...], maximum_age_days: int) -> dict:
        maps = {key: dict(histories.get(key, [])) for key in keys}
        common = set.intersection(*(set(values) for values in maps.values())) if maps else set()
        eligible = sorted(day for day in common if day <= cutoff.date())
        if not eligible:
            return {"status": "MISSING", "values": {}, "source_ids": list(keys),
                    "reason": "NO_COMMON_OBSERVATION_DATE"}
        day = eligible[-1]
        age = (cutoff.date() - day).days
        return {"status": "FRESH" if age <= maximum_age_days else "STALE",
                "observed_date": day.isoformat(), "age_days": age,
                "values": {key: maps[key][day] for key in keys}, "source_ids": list(keys)}

    curve = common_panel(("DGS2", "DGS5", "DGS10", "DGS30"), 7)
    if curve["status"] != "MISSING":
        values = curve["values"]
        curve["slopes_percentage_points"] = {
            "10y_minus_2y": values["DGS10"] - values["DGS2"],
            "30y_minus_5y": values["DGS30"] - values["DGS5"],
        }
    rates = common_panel(("DGS10", "DFII10", "T10YIE"), 7)
    if rates["status"] != "MISSING":
        values = rates["values"]
        rates["nominal_minus_real_minus_breakeven_pp"] = (
            values["DGS10"] - values["DFII10"] - values["T10YIE"])
        rates["interpretation"] = (
            "Same-date Treasury nominal, real-yield and breakeven observations; the residual is a consistency check, not alpha.")
    available = {key for key in GLOBAL_SERIES if histories.get(key)}
    coverage = {
        "treasury_curve": "AVAILABLE" if {"DGS2", "DGS5", "DGS10", "DGS30", "T10Y3M"} <= available else "PARTIAL",
        "policy_and_funding": "AVAILABLE" if {"DFF", "SOFR"} <= set(histories) and histories.get("SOFR") else "PARTIAL",
        "real_rates_and_inflation_expectations": "AVAILABLE" if {"DFII10", "T10YIE"} <= available else "PARTIAL",
        "financial_conditions_and_credit": "AVAILABLE" if {"NFCI", "NFCICREDIT", "STLFSI4"} <= set(histories) and histories.get("NFCICREDIT") else "PARTIAL",
        "dollar_and_oil": "AVAILABLE" if {"DTWEXBGS", "DCOILWTICO"} <= available else "PARTIAL",
        "foreign_central_banks": "MISSING",
        "global_equity_indices": "MISSING",
        "metals_and_agriculture": "MISSING",
    }
    return {
        "yield_curve": curve,
        "nominal_real_breakeven": rates,
        "coverage": coverage,
        "limitations": [
            "FRED observations have heterogeneous publication schedules and are not guaranteed tick-real-time.",
            "Foreign central-bank, global equity-index, metals and agriculture adapters are not implemented.",
            "This is a bounded cross-market context panel, not exhaustive whole-world coverage.",
        ],
    }


def transparent_risk_appetite(market: dict, prices: dict) -> dict:
    fresh = [value for value in prices.values() if value.get("status") == "FRESH"]
    has_current_panel = "current_volatility" in market
    current = market.get("current_volatility", {})
    current_vix = current.get("values", {}).get("VIX", {})
    use_current = current.get("status") in {"LIVE_INTRADAY", "DELAYED"}
    # Once the current panel is part of the packet contract, do not silently
    # substitute a completed-close value for a missing same-session value. Older
    # packets without the panel retain their historical fallback behavior.
    vix_percentile = (current_vix.get("fear_proxy_percentile") if use_current else
                      None if has_current_panel else
                      market.get("VIXCLS", {}).get("fear_proxy_percentile"))
    components = {
        "inverse_vix_percentile": 100-vix_percentile if vix_percentile is not None else None,
        "mean_watchlist_rsi14": (sum(value["rsi14_simple"] for value in fresh)/len(fresh)
                                  if fresh else None),
        "watchlist_above_sma200_pct": (100*sum(value["price_to_sma200"] > 1 for value in fresh)/len(fresh)
                                        if fresh else None),
    }
    present = [value for value in components.values() if value is not None]
    return {"status": "COMPLETE" if len(present) == len(components) else "PARTIAL",
            "value": sum(present)/len(present) if present else None,
            "scale": "0=fear/risk-off;100=greed/risk-on",
            "components": components,
            "volatility_observation": ({"source": current.get("provider"),
                                         "status": current.get("status"),
                                         "observed_at": current.get("observed_at"),
                                         "missing": current.get("missing", [])}
                                        if has_current_panel else
                                       {"source": "FRED_VIXCLS_COMPLETED_CLOSE_FALLBACK",
                                        "status": "LATEST_COMPLETED_CLOSE",
                                        "observed_at": market.get("VIXCLS", {}).get("observed_date")}),
            "formula": "equal mean of inverse VIX percentile, mean watchlist RSI14, and selected-watchlist breadth",
            "limitations": ["transparent research proxy, not the CNN Fear & Greed Index",
                            "breadth is only the requested watchlist", "not empirically calibrated"]}


def postclose_preflight(targets: list[str], forecast_root: Path,
                        now: datetime | None = None) -> dict:
    """Resolve the only current XNYS origin that can still be issued prospectively."""
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cal = xcals.get_calendar("XNYS")
    sessions = cal.sessions_in_range((instant.date()-timedelta(days=10)).isoformat(),
                                     instant.date().isoformat())
    eligible = [session for session in sessions
                if cal.session_close(session).to_pydatetime()+timedelta(minutes=20) <= instant]
    if not eligible:
        return {"status": "OUTSIDE_POST_CLOSE_WINDOW", "as_of": instant.isoformat(),
                "reason": "No XNYS session has completed the 20-minute data buffer"}
    origin = eligible[-1].date().isoformat()
    next_open = cal.session_open(cal.next_session(origin)).to_pydatetime()
    if instant >= next_open:
        return {"status": "OUTSIDE_POST_CLOSE_WINDOW", "as_of": instant.isoformat(),
                "origin_session": origin, "next_open": next_open.isoformat(),
                "reason": "The next XNYS session has already opened"}
    duplicates = []
    if forecast_root.exists():
        from spy_predictor_quant.meta_outcomes import load_forecast
        for path in sorted(forecast_root.glob("*.json")):
            forecast = load_forecast(path)
            for symbol in targets:
                issued = forecast.get("symbols", {}).get(symbol, {})
                if issued.get("status") == "ISSUED" and issued.get("origin_session") == origin:
                    duplicates.append({"symbol": symbol, "forecast_hash": forecast["forecast_hash"],
                                       "path": str(path.resolve())})
    return {"status": "DUPLICATE_ORIGIN" if duplicates else "READY",
            "as_of": instant.isoformat(), "origin_session": origin,
            "next_open": next_open.isoformat(), "duplicates": duplicates}


def validate_postclose_packet(packet_path: Path, expected_symbols: list[str],
                              etfs: list[str], origin_session: str,
                              require_delayed: bool = False,
                              required_holdings: set[str] | None = None) -> dict:
    from spy_predictor_quant.meta_observation import _verified
    packet = _verified(packet_path, "packet_hash")
    errors = []
    if packet.get("symbols") != expected_symbols:
        errors.append("symbol order/identity mismatch")
    if packet.get("acquisition_errors"):
        errors.append("one or more configured acquisitions failed")
    for symbol in expected_symbols:
        instrument = packet.get("instruments", {}).get(symbol, {})
        if instrument.get("status") != "FRESH" or instrument.get("price_date") != origin_session:
            errors.append(f"{symbol} lacks the completed {origin_session} close")
        if {row.get("trading_days") for row in instrument.get("reference_scenarios", [])} != set(HORIZONS):
            errors.append(f"{symbol} lacks all reference horizons")
        if symbol not in etfs and symbol not in packet.get("company_fundamentals", {}):
            errors.append(f"{symbol} lacks normalized SEC evidence")
    for series in CORE_SERIES:
        if packet.get("market", {}).get(series, {}).get("status") != "FRESH":
            errors.append(f"{series} is missing or stale")
    if require_delayed and packet.get("delayed_ibkr_context", {}).get("status") not in {"OK", "PARTIAL"}:
        errors.append("requested IBKR delayed context is unavailable")
    for symbol in required_holdings or set():
        if packet.get("etf_holdings", {}).get(symbol, {}).get("status") != "CURRENT":
            errors.append(f"{symbol} supplied holdings are missing or older than seven days")
    if errors:
        raise ValueError("Post-close packet validation failed: " + "; ".join(errors))
    missing_holdings = [symbol for symbol in etfs if symbol not in packet.get("etf_holdings", {})]
    return {"status": "VALID", "origin_session": origin_session,
            "symbols": expected_symbols, "missing_optional_etf_holdings": missing_holdings,
            "delayed_context": packet.get("delayed_ibkr_context", {}).get("status", "MISSING")}


def postclose(targets: list[str], etfs: list[str], *, capture_root: Path,
              analysis_root: Path, forecast_root: Path,
              holdings_files: dict[str, Path] | None = None,
              etf_profile_files: dict[str, Path] | None = None,
              evidence_file: Path | None = None,
              delayed_context_file: Path | None = None,
              primary_sources_file: Path | None = DEFAULT_PRIMARY_SOURCES,
              runner_config: Path | None = None,
              forecast_policy: Path = DEFAULT_FORECAST_POLICY,
              operations_policy: Path = DEFAULT_OPERATIONS_POLICY,
              operation_callback=None) -> dict:
    preflight = postclose_preflight(targets, forecast_root)
    if preflight["status"] != "READY":
        raise ValueError(f"META post-close preflight: {preflight['status']}")
    if operation_callback:
        operation_callback("ACQUIRING", {"origin_session": preflight["origin_session"]})
    snapshot_path = capture(capture_root, targets, etfs, None, evidence_file,
                            holdings_files, False, delayed_context_file,
                            primary_sources_file, etf_profile_files,
                            operations_policy_path=operations_policy)
    analysis = build(snapshot_path, analysis_root, lane="PROSPECTIVE_EVALUATION")
    packet_path = analysis / "packet.json"
    if operation_callback:
        operation_callback("VALIDATING", {"packet_path": str(packet_path.resolve())})
    validation = validate_postclose_packet(
        packet_path, targets, etfs, preflight["origin_session"], delayed_context_file is not None,
        set((holdings_files or {}).keys()))
    agent_run = None
    meta_report_path = None
    structured_path = None
    if runner_config:
        from spy_predictor_quant.meta_agents import run_agents
        from spy_predictor_quant.meta_forecast import create_structured_forecast
        if operation_callback:
            operation_callback("AGENTS", {})
        agent_run = run_agents(packet_path, runner_config, analysis_root,
                               operations_policy_path=operations_policy,
                               forecast_policy_path=forecast_policy)
        meta_report_path = agent_run / "meta-report.json"
        if operation_callback:
            operation_callback("FORECASTING", {"agent_run": str(agent_run.resolve())})
        structured_path = create_structured_forecast(
            packet_path, meta_report_path, agent_run / "structured-forecast.json", forecast_policy)
    from spy_predictor_quant.meta_observation import register
    if operation_callback:
        operation_callback("REGISTERING", {})
    forecast_path = register(packet_path, forecast_root, meta_report_path,
                             structured_forecast_path=structured_path)
    from spy_predictor_quant.meta_product import write_product_bundle
    if operation_callback:
        operation_callback("RENDERING", {"forecast_path": str(forecast_path.resolve())})
    product_bundle = write_product_bundle(
        packet_path, analysis / "product", structured_path=structured_path,
        report_path=meta_report_path, mode="PROSPECTIVE", forecast_root=forecast_root)
    packet = json.loads(packet_path.read_text())
    forecast = json.loads(forecast_path.read_text())
    receipt = {"schemaVersion": "meta-postclose-receipt-v1",
               "status": ("REGISTERED_STRUCTURED_META_EXPERIMENTAL" if structured_path
                          else "REGISTERED_QUANT_ONLY"),
               "origin_session": preflight["origin_session"], "snapshot_path": str(snapshot_path.resolve()),
               "snapshot_hash": packet["snapshot_hash"], "analysis_path": str(analysis.resolve()),
               "packet_path": str(packet_path.resolve()), "packet_hash": packet["packet_hash"],
               "forecast_path": str(forecast_path.resolve()), "forecast_hash": forecast["forecast_hash"],
               "agent_run": str(agent_run.resolve()) if agent_run else None,
               "agent_report_hash": file_sha256(meta_report_path) if meta_report_path else None,
               "structured_forecast_hash": (json.loads(structured_path.read_text())["artifact_hash"]
                                            if structured_path else None),
               "product_bundle": str(product_bundle.resolve()),
               "validation": validation}
    receipt["receipt_hash"] = digest(receipt)
    receipt_path = analysis / "postclose-receipt.json"
    write_json_exclusive(receipt_path, receipt)
    return {**receipt, "receipt_path": str(receipt_path.resolve())}


def daily_metrics(payload: dict, source: dict, cutoff: datetime) -> dict:
    cal = xcals.get_calendar("XNYS")
    # A bar captured intraday cannot become a final close merely because a
    # later build runs after the bell. Require completion at capture time too.
    available = min(cutoff, _instant(source.get("retrieved_at", cutoff.isoformat())))
    available = min(available, _instant(source.get("data_end", available.isoformat())))
    rows = []
    for bar in payload.get("bars") or []:
        if source["kind"] == "ibkr_daily":
            day = datetime.strptime(bar["date"], "%Y%m%d").date()
            names = ("open", "high", "low", "close", "volume")
        else:
            day = _instant(bar["t"]).astimezone(ZoneInfo("America/New_York")).date()
            names = ("o", "h", "l", "c", "v")
        if not cal.is_session(day.isoformat()):
            raise ValueError("Non-session price bar")
        if cal.session_close(day.isoformat()).to_pydatetime() > available:
            continue
        op, high, low, close, volume = (float(bar[n]) for n in names)
        if (not all(math.isfinite(v) for v in (op, high, low, close, volume))
                or min(op, high, low, close) <= 0 or volume < 0
                or low > min(op, close) or high < max(op, close) or high < low):
            raise ValueError("Invalid OHLCV")
        rows.append((day, op, high, low, close, volume))
    if len(rows) < 200 or [r[0] for r in rows] != sorted({r[0] for r in rows}):
        raise ValueError("Need at least 200 distinct ordered sessions")
    rows = rows[-252:]
    expected = [d.date() for d in cal.sessions_in_range(rows[0][0].isoformat(), rows[-1][0].isoformat())]
    if [r[0] for r in rows] != expected:
        raise ValueError("Incomplete daily session window")
    eligible = [d for d in cal.sessions_in_range((cutoff.date()-timedelta(days=14)).isoformat(), cutoff.date().isoformat())
                if cal.session_close(d).to_pydatetime() <= cutoff]
    status = "FRESH" if eligible and rows[-1][0] == eligible[-1].date() else "STALE"
    prices = np.array([r[4] for r in rows])
    returns = np.diff(np.log(prices))
    changes = np.diff(prices[-15:])
    gains, losses = np.maximum(changes, 0).mean(), np.maximum(-changes, 0).mean()
    rsi = 50.0 if gains == losses == 0 else 100.0 if losses == 0 else 100-100/(1+gains/losses)
    tr = [max(rows[i][2]-rows[i][3], abs(rows[i][2]-rows[i-1][4]), abs(rows[i][3]-rows[i-1][4]))
          for i in range(len(rows)-14, len(rows))]
    result = {"status": status, "price_date": rows[-1][0].isoformat(), "latest_close": float(prices[-1]),
              "source_ids": [source["id"]], "available_at": source.get("retrieved_at"),
              "currency": "USD", "sessions": len(rows),
              "adjustment": source["adjustment"], "feed": source["feed"],
              "rsi14_simple": float(rsi), "atr14_simple": float(np.mean(tr)),
              "drawdown_from_window_high_pct": float(100*(prices[-1]/prices.max()-1)),
              "drawdown_window_sessions": len(rows),
              "greed_proxy": {"momentum_rsi14": float(rsi), "meaning": "Momentum only; not observed investor greed"}}
    for window in (20, 50, 200):
        result[f"sma{window}"] = float(prices[-window:].mean())
        result[f"price_to_sma{window}"] = float(prices[-1]/prices[-window:].mean())
    for window in (5, 21, 63):
        result[f"realized_vol{window}_pct"] = float(100*returns[-window:].std(ddof=1)*math.sqrt(252))
        result[f"return{window}_pct"] = float(100*(prices[-1]/prices[-window-1]-1))
    result["support_resistance_candidates"] = {
        f"{window}_session": {
            "support_close": float(prices[-window:].min()),
            "resistance_close": float(prices[-window:].max()),
            "method": "lowest/highest completed daily close; descriptive, not predictive",
        } for window in (20, 63)
    }
    weekly_rows = []
    for row in rows:
        week = row[0].isocalendar()[:2]
        if weekly_rows and weekly_rows[-1][0] == week:
            weekly_rows[-1] = (week, row[0], row[4])
        else:
            weekly_rows.append((week, row[0], row[4]))
    weekly_closes = np.array([row[2] for row in weekly_rows])
    result["weekly_view"] = {
        "observations": len(weekly_rows),
        "latest_week_ending_session": weekly_rows[-1][1].isoformat(),
        **{f"sma{window}_weeks": float(weekly_closes[-window:].mean())
           for window in (4, 13, 40) if len(weekly_closes) >= window},
        "return13_weeks_pct": (float(100*(weekly_closes[-1]/weekly_closes[-14]-1))
                               if len(weekly_closes) >= 14 else None),
        "method": "last completed session close in each ISO week",
    }
    result["reference_scenarios"] = (reference_scenarios(result["latest_close"], result["realized_vol63_pct"])
                                     if status == "FRESH" else [])
    return result


def intraday_metrics(bars_payload: dict, latest_payload: dict, bars_source: dict,
                     latest_source: dict, cutoff: datetime) -> dict:
    """Validate and summarize one-minute Alpaca evidence without overstating coverage."""
    if bars_source.get("symbol") != latest_source.get("symbol"):
        raise ValueError("Intraday bars and snapshot symbols differ")
    if (bars_source.get("evidence_state") != latest_source.get("evidence_state")
            or bars_source.get("exchange_coverage") != latest_source.get("exchange_coverage")):
        raise ValueError("Intraday source semantics differ")
    effective_end = min(cutoff, _instant(bars_source["data_end"]))
    rows = []
    for bar in bars_payload.get("bars", []):
        timestamp = _instant(bar["t"])
        if timestamp + timedelta(minutes=1) > effective_end:
            continue
        values = [float(bar[key]) for key in ("o", "h", "l", "c", "v")]
        op, high, low, close, volume = values
        vwap = float(bar["vw"]) if bar.get("vw") is not None else None
        if (not all(math.isfinite(value) for value in values)
                or min(op, high, low, close) <= 0 or volume < 0
                or low > min(op, close) or high < max(op, close)
                or (vwap is not None and (not math.isfinite(vwap) or vwap <= 0))):
            raise ValueError("Invalid intraday OHLCV")
        rows.append((timestamp, op, high, low, close, volume, vwap))
    if not rows or [row[0] for row in rows] != sorted({row[0] for row in rows}):
        raise ValueError("Intraday bars must be nonempty, ordered and unique")

    def latest_point(name: str, price_keys: tuple[str, ...]) -> dict | None:
        item = latest_payload.get(name)
        if not isinstance(item, dict) or not item.get("t"):
            return None
        timestamp = _instant(item["t"])
        if timestamp > cutoff + timedelta(seconds=5):
            raise ValueError("Intraday snapshot timestamp follows packet cutoff")
        prices = {}
        for key in price_keys:
            if item.get(key) is not None:
                value = float(item[key])
                if not math.isfinite(value) or value <= 0:
                    raise ValueError("Invalid intraday snapshot price")
                prices[key] = value
        return {"timestamp": timestamp.isoformat(),
                "available_at": latest_source.get("retrieved_at"), **prices} if prices else None

    trade = latest_point("latestTrade", ("p",))
    quote = latest_point("latestQuote", ("bp", "ap"))
    if quote and quote.get("bp") and quote.get("ap"):
        if quote["bp"] > quote["ap"]:
            raise ValueError("Intraday quote is crossed")
        quote["mid"] = (quote["bp"] + quote["ap"]) / 2
        quote["spread_bps"] = 10_000 * (quote["ap"] - quote["bp"]) / quote["mid"]

    cal = xcals.get_calendar("XNYS")
    latest_day = rows[-1][0].astimezone(ZoneInfo("America/New_York")).date()
    regular = []
    if cal.is_session(latest_day.isoformat()):
        session_open = cal.session_open(latest_day.isoformat()).to_pydatetime()
        session_close = cal.session_close(latest_day.isoformat()).to_pydatetime()
        regular = [row for row in rows if session_open <= row[0] < session_close]
    session = regular or [row for row in rows
                          if row[0].astimezone(ZoneInfo("America/New_York")).date() == latest_day]
    if not session:
        raise ValueError("Intraday source has no usable latest session")
    total_volume = sum(row[5] for row in session)
    weighted_vwap = (sum((row[6] if row[6] is not None else row[4]) * row[5] for row in session)
                     / total_volume if total_volume > 0 else None)
    gaps = sum(1 for left, right in zip(session, session[1:])
               if right[0] - left[0] != timedelta(minutes=1))

    timeframe = {}
    for minutes in (1, 5, 15, 60):
        if len(session) < minutes:
            timeframe[str(minutes)] = {"status": "INSUFFICIENT_BARS"}
            continue
        group = session[-minutes:]
        group_volume = sum(row[5] for row in group)
        timeframe[str(minutes)] = {
            "status": "COMPLETE" if all(
                right[0] - left[0] == timedelta(minutes=1)
                for left, right in zip(group, group[1:])) else "GAPPED",
            "start": group[0][0].isoformat(),
            "end": (group[-1][0] + timedelta(minutes=1)).isoformat(),
            "open": group[0][1], "high": max(row[2] for row in group),
            "low": min(row[3] for row in group), "close": group[-1][4],
            "volume": group_volume,
            "vwap": (sum((row[6] if row[6] is not None else row[4]) * row[5] for row in group)
                     / group_volume if group_volume > 0 else None),
        }
    latest_observation_timestamp = max([rows[-1][0]] + [
        _instant(item["timestamp"]) for item in (trade, quote) if item])
    session_last_observed_at = session[-1][0] + timedelta(minutes=1)
    latest_day_rows = [row for row in rows
                       if row[0].astimezone(ZoneInfo("America/New_York")).date() == latest_day]
    extended = [row for row in latest_day_rows if row not in regular]
    extended_summary = {"status": "MISSING", "bars": 0}
    if extended:
        extended_summary = {
            "status": "AVAILABLE", "bars": len(extended), "open": extended[0][1],
            "high": max(row[2] for row in extended), "low": min(row[3] for row in extended),
            "last": extended[-1][4], "volume": sum(row[5] for row in extended),
            "first_timestamp": extended[0][0].isoformat(),
            "last_timestamp": extended[-1][0].isoformat(),
        }
    return {
        "status": "AVAILABLE" if gaps == 0 else "PARTIAL_GAPS",
        "symbol": bars_source["symbol"],
        "evidence_state": bars_source["evidence_state"],
        "exchange_coverage": bars_source["exchange_coverage"],
        "feed": bars_source["feed"],
        "expected_delay_minutes": bars_source["expected_delay_minutes"],
        "market_period_at_cutoff": market_period_at(cutoff),
        "latest_timestamp": latest_observation_timestamp.isoformat(),
        "latest_observation_timestamp": latest_observation_timestamp.isoformat(),
        "session_last_observed_at": session_last_observed_at.isoformat(),
        "value_timestamps": {
            "session_last": session_last_observed_at.isoformat(),
            "latest_trade": (trade or {}).get("timestamp"),
            "latest_quote": (quote or {}).get("timestamp"),
        },
        "age_at_cutoff_seconds": max(0, round((cutoff - session_last_observed_at).total_seconds())),
        "latest_trade": trade, "latest_quote": quote,
        "session_date": latest_day.isoformat(), "session_segment": "REGULAR" if regular else "EXTENDED_OR_CLOSED",
        "session_open": session[0][1], "session_high": max(row[2] for row in session),
        "session_low": min(row[3] for row in session), "session_last": session[-1][4],
        "session_volume": total_volume, "session_vwap": weighted_vwap,
        "minute_bars": len(session), "minute_gaps": gaps,
        "timeframes_minutes": timeframe,
        "extended_hours": extended_summary,
        "halt_status": "UNKNOWN_NO_QUALIFIED_HALT_FEED",
        "limitations": [
            "IEX_ONLY is real-time limited-venue evidence, not consolidated US market coverage"
            if bars_source["exchange_coverage"] == "IEX_ONLY"
            else "consolidated SIP evidence is delayed and not an executable real-time quote",
            "intraday bars are split-adjusted; the latest quote/trade is a separate timestamped observation",
        ],
    }


def reference_scenarios(price: float, annual_vol_pct: float) -> list[dict]:
    """Uncalibrated zero-log-drift Normal reference; never an agent forecast."""
    if not math.isfinite(price) or price <= 0 or not math.isfinite(annual_vol_pct) or annual_vol_pct <= 0:
        return []
    normal = NormalDist()
    output = []
    for horizon, threshold in zip(HORIZONS, (.02, .05, .10), strict=True):
        scale = annual_vol_pct/100*math.sqrt(horizon/252)
        bear = normal.cdf(math.log1p(-threshold)/scale)
        bull = 1-normal.cdf(math.log1p(threshold)/scale)
        output.append({"trading_days": horizon, "return_threshold_pct": threshold*100,
            "probabilities": {"bear": bear, "neutral": 1-bear-bull, "bull": bull},
            "probability_price_up": .5,
            "price_quantiles": {str(q): price*math.exp(normal.inv_cdf(q)*scale)
                                for q in (.05, .10, .25, .50, .75, .90, .95)},
            "status": "ASSUMPTION_BASED_UNCALIBRATED_REFERENCE",
            "formula": "log(P_h/P_0) ~ Normal(0, (RV63/100)^2*h/252)",
            "target": "terminal split-adjusted price; dividends excluded; not path highs/lows",
            "assumptions": "constant volatility, zero median log return, no jumps; no cycle/LLM adjustment"})
    return output


def load_snapshot(path: Path) -> tuple[dict, dict]:
    snapshot = json.loads(path.read_text())
    identity = snapshot.pop("snapshot_hash")
    if digest(snapshot) != identity or snapshot["version"] != VERSION:
        raise ValueError("Snapshot hash/version mismatch")
    snapshot["snapshot_hash"] = identity
    targets = symbols(snapshot["symbols"])
    if not set(snapshot["etfs"]).issubset(targets):
        raise ValueError("ETF identities must belong to the watchlist")
    cutoff = _instant(snapshot["as_of"])
    if cutoff > datetime.now(timezone.utc):
        raise ValueError("Snapshot cutoff is in the future")
    raw = {}
    root = path.resolve().parent
    for key, source in snapshot["sources"].items():
        local = (root/source["path"]).resolve()
        if not local.is_relative_to(root) or file_sha256(local) != source["sha256"]:
            raise ValueError("Source path or hash mismatch")
        if source["id"] != key or _instant(source["retrieved_at"]) > cutoff:
            raise ValueError("Source identity/receipt violates snapshot cutoff")
        raw[key] = local.read_bytes()
    return snapshot, raw


def build(snapshot_path: Path, output_root: Path, *,
          product_config: Path = DEFAULT_PRODUCT_CONFIG,
          lane: str = "RESEARCH_PACKET") -> Path:
    if lane not in {"RESEARCH_PACKET", "ON_DEMAND_ANALYSIS", "PROSPECTIVE_EVALUATION"}:
        raise ValueError("Unsupported META operating lane")
    snapshot, raw = load_snapshot(snapshot_path)
    cutoff = _instant(snapshot["as_of"])
    histories = {key: parse_fred(value, key) for key, value in raw.items() if key in SERIES}
    prices, intraday = {}, {}
    fundamentals, etf_profiles, etf_sponsor_profiles = {}, {}, {}
    evidence = {key: {**source, "availability_policy": "conservative-retrieval-time",
                      "historical_first_seen_established": False}
                for key, source in snapshot["sources"].items()}
    for symbol in snapshot["symbols"]:
        key = f"price-{symbol}"
        if key not in raw:
            prices[symbol] = {"status": "MISSING", "reason": snapshot["acquisition_errors"].get(key, "NOT_CAPTURED")}
        else:
            try:
                prices[symbol] = daily_metrics(json.loads(raw[key]), snapshot["sources"][key], cutoff)
            except (KeyError, ValueError, TypeError) as exc:
                prices[symbol] = {"status": "INVALID", "reason": str(exc)}
        bars_key, latest_key = f"intraday-bars-{symbol}", f"intraday-latest-{symbol}"
        if bars_key in raw and latest_key in raw:
            try:
                intraday[symbol] = intraday_metrics(
                    json.loads(raw[bars_key]), json.loads(raw[latest_key]),
                    snapshot["sources"][bars_key], snapshot["sources"][latest_key], cutoff)
            except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
                intraday[symbol] = {"status": "INVALID", "reason": str(exc)}
        elif snapshot.get("market_data_request", {}).get("mode") == "intraday":
            reasons = [snapshot["acquisition_errors"].get(key, "NOT_CAPTURED")
                       for key in (bars_key, latest_key) if key not in raw]
            intraday[symbol] = {"status": "MISSING", "reason": ";".join(reasons)}
    for symbol in snapshot["symbols"]:
        if symbol in snapshot["etfs"]:
            key = f"holdings-{symbol}"
            if key in raw:
                profile = parse_holdings_csv(raw[key], symbol, cutoff)
                etf_profiles[symbol] = profile
                evidence[key] = {"id": key, "kind": "etf_holdings", "symbols": [symbol],
                    "url": snapshot["sources"][key]["url"], "published_at": snapshot["sources"][key]["retrieved_at"],
                    "retrieved_at": snapshot["sources"][key]["retrieved_at"],
                    "text": json.dumps(profile, sort_keys=True), "parent_source": key,
                    "verification": "STRUCTURE_TIMING_WEIGHT_SUM_AND_TICKER_UNIQUENESS"}
            profile_key = f"etf-profile-{symbol}"
            if profile_key in raw:
                sponsor_profile = parse_etf_profile(json.loads(raw[profile_key]), symbol, cutoff)
                etf_sponsor_profiles[symbol] = sponsor_profile
                evidence[profile_key] = {"id": profile_key, "kind": "etf_profile", "symbols": [symbol],
                    "url": snapshot["sources"][profile_key]["url"],
                    "published_at": sponsor_profile["as_of"] + "T00:00:00+00:00",
                    "retrieved_at": snapshot["sources"][profile_key]["retrieved_at"],
                    "text": json.dumps(sponsor_profile, sort_keys=True), "parent_source": profile_key,
                    "verification": "STRUCTURE_TIMING_NUMERIC_BOUNDS;SPONSOR_REPORTED_NOT_RECALCULATED"}
            continue
        submissions_key, facts_key = f"sec-submissions-{symbol}", f"sec-facts-{symbol}"
        if submissions_key in raw and facts_key in raw:
            filings = recent_filings(json.loads(raw[submissions_key]), symbol, cutoff)
            profile = company_fundamentals(json.loads(raw[facts_key]), symbol, cutoff, filings)
            fundamentals[symbol] = profile
            accepted = [row["accepted_at"] for row in filings["periodic"] + filings["recent_events"]]
            identity = f"fundamentals-{symbol}"
            evidence[identity] = {"id": identity, "kind": "filing", "symbols": [symbol],
                "url": filings["periodic"][0]["url"] if filings["periodic"] else snapshot["sources"][submissions_key]["url"],
                "published_at": max(accepted) if accepted else snapshot["sources"][submissions_key]["retrieved_at"],
                "retrieved_at": max(snapshot["sources"][submissions_key]["retrieved_at"], snapshot["sources"][facts_key]["retrieved_at"]),
                "text": json.dumps(profile, sort_keys=True), "parent_source_ids": [submissions_key, facts_key],
                "verification": "SEC_CIK_TICKER_RESOLUTION;FILED_AT_CUTOFF;STANDARD_US_GAAP_FACTS_ONLY"}
    if "external" in raw:
        for item in validate_external(json.loads(raw["external"]), cutoff):
            evidence[item["id"]] = {**item, "parent_source": "external",
                                    "verification": "SUPPLIED_CONTENT;NOT_INDEPENDENTLY_FACT_CHECKED"}
    primary_definitions = {}
    if "primary-source-config" in raw:
        primary_definitions = {row["id"]: row for row in validate_primary_source_config(
            json.loads(raw["primary-source-config"]))}
    primary_counts = {"issuer_event": 0, "issuer_release": 0, "sector_release": 0,
                      "policy_event": 0, "policy_release": 0}
    for key, source_receipt in snapshot["sources"].items():
        if source_receipt.get("kind") != "primary_source_feed":
            continue
        definition = primary_definitions.get(source_receipt.get("source_id"))
        if not definition:
            raise ValueError("Primary feed receipt lacks its archived configuration")
        rows = primary_source_evidence(raw[key], definition, cutoff, snapshot["symbols"],
                                       source_receipt["retrieved_at"])
        primary_counts[definition["kind"]] += len(rows)
        for item in rows:
            if item["id"] in evidence:
                raise ValueError("Duplicate normalized primary evidence identity")
            evidence[item["id"]] = {**item, "parent_source": key}
    if "news" in raw:
        exposure_map = snapshot["sources"]["news"].get("etf_exposure_map", {})
        for article in json.loads(raw["news"]).get("news", []):
            if max(_instant(article["created_at"]), _instant(article["updated_at"])) > cutoff:
                continue
            identity = f"news-{article['id']}"
            article_symbols = article.get("symbols")
            if not isinstance(article_symbols, list) or any(not isinstance(value, str) for value in article_symbols):
                continue
            indirect = {}
            for ticker in article_symbols:
                for fund, weight in exposure_map.get(ticker, {}).items():
                    indirect.setdefault(fund, []).append({"holding": ticker, "weight_pct": weight})
            evidence[identity] = {"id": identity, "url": article["url"], "kind": "news",
                "published_at": article["created_at"], "updated_at": article["updated_at"],
                "retrieved_at": snapshot["sources"]["news"]["retrieved_at"],
                "symbols": article_symbols, "text": article["headline"] + "\n" + article.get("summary", ""),
                "indirect_etf_exposure_weight_pct": indirect, "parent_source": "news"}
    context_prices = {}
    for symbol, family in snapshot.get("context_symbols", MARKET_CONTEXT).items():
        if symbol in prices:
            context_prices[symbol] = {**prices[symbol], "context_family": family,
                                      "source_role": "REQUESTED_INSTRUMENT_AND_CONTEXT_PROXY"}
            continue
        key = f"context-price-{symbol}"
        if key not in raw:
            context_prices[symbol] = {"status": "MISSING", "context_family": family,
                                      "reason": snapshot.get("supplemental_acquisition_errors", {}).get(
                                          key, "NOT_CAPTURED")}
            continue
        try:
            context_prices[symbol] = {
                **daily_metrics(json.loads(raw[key]), snapshot["sources"][key], cutoff),
                "context_family": family, "source_role": "MARKET_PROXY"}
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            context_prices[symbol] = {"status": "INVALID", "context_family": family,
                                      "reason": str(exc)}
    for symbol, metrics in context_prices.items():
        if metrics.get("status") not in {"FRESH", "STALE"} or not metrics.get("source_ids"):
            continue
        parent = metrics["source_ids"][0]
        identity = f"market-context-{symbol}"
        receipt = snapshot["sources"][parent]
        evidence[identity] = {
            "id": identity, "kind": "market_context", "symbols": snapshot["symbols"],
            "url": receipt["url"], "published_at": receipt["retrieved_at"],
            "retrieved_at": receipt["retrieved_at"], "parent_source": parent,
            "text": json.dumps({"symbol": symbol, "context_family": metrics["context_family"],
                                "price_date": metrics.get("price_date"),
                                "return5_pct": metrics.get("return5_pct"),
                                "return21_pct": metrics.get("return21_pct"),
                                "return63_pct": metrics.get("return63_pct"),
                                "price_to_sma200": metrics.get("price_to_sma200")}, sort_keys=True),
            "verification": "CALCULATED_DAILY_MARKET_PROXY;RELEVANT_AS_SHARED_MARKET_CONTEXT",
        }
        metrics["source_ids"] = [identity]
    fresh = [p for p in prices.values() if p["status"] == "FRESH"]
    benchmark = context_prices.get("SPY")
    for symbol, instrument in prices.items():
        if instrument.get("status") != "FRESH" or not benchmark or benchmark.get("status") != "FRESH":
            instrument["relative_strength_vs_spy"] = {"status": "MISSING"}
            continue
        instrument["relative_strength_vs_spy"] = {
            "status": "BENCHMARK_RELATIVE_RETURN_DIFFERENCE",
            "benchmark": "SPY",
            **{f"{window}_sessions_percentage_points":
               instrument[f"return{window}_pct"] - benchmark[f"return{window}_pct"]
               for window in (5, 21, 63)},
            "meaning": "asset total price return minus SPY price return; not regression alpha",
        }
    market = macro_metrics(histories, cutoff)
    market["current_volatility"] = current_volatility_metrics(
        raw, cutoff, histories, snapshot.get("supplemental_acquisition_errors", {}))
    global_context = global_market_metrics(histories, cutoff)
    fresh_context = [value for value in context_prices.values() if value.get("status") == "FRESH"]
    sector_symbols = ["XLK", "XLF", "XLE", "XLV"]
    fresh_sectors = [context_prices[symbol] for symbol in sector_symbols
                     if context_prices.get(symbol, {}).get("status") == "FRESH"]
    global_context["market_proxies"] = context_prices
    global_context["market_proxy_coverage"] = {
        "fresh": len(fresh_context), "requested": len(context_prices),
        "status": "COMPLETE" if len(fresh_context) == len(context_prices) else "PARTIAL",
        "sector_proxy_above_sma200_pct": (100 * sum(value["price_to_sma200"] > 1
                                                     for value in fresh_sectors) / len(fresh_sectors)
                                          if fresh_sectors else None),
        "sector_proxy_fresh": len(fresh_sectors), "sector_proxy_requested": len(sector_symbols),
        "credit_risk_price_momentum_21d_percentage_points": (
            context_prices["HYG"]["return21_pct"] - context_prices["LQD"]["return21_pct"]
            if all(context_prices.get(symbol, {}).get("status") == "FRESH"
                   for symbol in ("HYG", "LQD")) else None),
        "limitations": ["ETF prices are liquid-market proxies, not underlying index levels or credit spreads",
                        "sector breadth covers four representative US sector ETFs, not all listed equities"],
    }
    delayed_context = (validate_delayed_context(json.loads(raw["ibkr-delayed-context"]), cutoff)
                       if "ibkr-delayed-context" in raw else
                       {"status": "MISSING", "reason": "NO_DELAYED_CAPTURE_ATTACHED"})
    if delayed_context.get("instruments"):
        for symbol, quote in delayed_context["instruments"].items():
            instrument = prices.get(symbol)
            delayed_last = quote.get("delayed_last")
            if instrument and instrument.get("latest_close") and delayed_last:
                quote["delayed_last_vs_completed_close_pct"] = 100*(
                    delayed_last/instrument["latest_close"]-1)
                quote["comparison_warning"] = (
                    "different timestamps; this is context, not a provider-close discrepancy test")
    product_contract = load_product_contract(product_config)
    instrument_profiles = {symbol: instrument_evidence_profile(
        symbol, symbol in snapshot["etfs"], fundamentals=fundamentals.get(symbol),
        holdings=etf_profiles.get(symbol), sponsor_profile=etf_sponsor_profiles.get(symbol),
        instrument=prices.get(symbol)) for symbol in snapshot["symbols"]}
    geopolitical = geopolitical_transmission_coverage(evidence, snapshot["symbols"])
    packet = {"version": VERSION, "snapshot_hash": snapshot["snapshot_hash"], "as_of": snapshot["as_of"],
        "symbols": snapshot["symbols"], "etfs": snapshot["etfs"], "horizons": list(HORIZONS),
        "product_contract": {"schema_version": product_contract["schema_version"],
                             "config_sha256": file_sha256(product_config)},
        "operating_context": {"lane": lane,
                              "market_period": market_period_at(cutoff),
                              "market_data_mode": snapshot.get("market_data_request", {}).get(
                                  "mode", "completed-close"),
                              "intraday_feed": snapshot.get("market_data_request", {}).get("intraday_feed"),
                              "price_basis": ("LATEST_COMPLETED_CLOSE_PLUS_TIMESTAMPED_INTRADAY_CONTEXT"
                                              if any(value.get("status") in {"AVAILABLE", "PARTIAL_GAPS"}
                                                     for value in intraday.values())
                                              else "LATEST_COMPLETED_CLOSE"),
                              "prospective_registration": False},
        "market": market, "global_market_context": global_context,
        "instruments": prices, "intraday": intraday, "evidence": evidence,
        "transparent_risk_appetite": transparent_risk_appetite(market, prices),
        "delayed_ibkr_context": delayed_context,
        "company_fundamentals": fundamentals, "etf_holdings": etf_profiles,
        "instrument_evidence_profiles": instrument_profiles,
        "etf_sponsor_profiles": etf_sponsor_profiles,
        "etf_quality_valuation": {symbol: etf_quality_valuation(
            etf_profiles.get(symbol), etf_sponsor_profiles.get(symbol)) for symbol in snapshot["etfs"]},
        "primary_event_coverage": {"counts": primary_counts,
            "status": "AVAILABLE" if sum(primary_counts.values()) else "MISSING",
            "supplemental_errors": snapshot.get("supplemental_acquisition_errors", {})},
        "etf_overlap": [etf_overlap(etf_profiles[a], etf_profiles[b])
                        for index, a in enumerate(sorted(etf_profiles)) for b in sorted(etf_profiles)[index+1:]],
        "watchlist_above_sma200_pct": 100*sum(p["price_to_sma200"] > 1 for p in fresh)/len(fresh) if fresh else None,
        "breadth_coverage": {"fresh": len(fresh), "requested": len(prices), "meaning": "Selected watchlist only; not whole-market breadth"},
        "fundamental_coverage": {s: "NORMALIZED_EVIDENCE_REQUIRES_ANALYSIS" if any(
            e.get("kind") in {"filing", "etf_holdings", "etf_profile"} and s in e.get("symbols", []) for e in evidence.values())
            else "MISSING" for s in prices},
        "geopolitical_coverage": geopolitical,
        "calibrated_forecast": None, "quantitative_forecast_status": "NO_QUALIFIED_META_FORECAST",
        "notice": "Independent cycle proxies. Reference probabilities are uncalibrated assumptions. Agent views are qualitative.",
        "implementation_sha256": file_sha256(Path(__file__)), "acquisition_errors": snapshot["acquisition_errors"],
        "supplemental_acquisition_errors": snapshot.get("supplemental_acquisition_errors", {}),
        "operational_acquisition": snapshot.get("operational_acquisition")}
    from spy_predictor_quant.meta_events import cluster_news
    packet["event_context"] = cluster_news(evidence, packet["as_of"])
    packet["packet_hash"] = digest(packet)
    run = create_immutable_run_directory(output_root, "analysis")
    write_json_exclusive(run/"packet.json", packet)
    from spy_predictor_quant.meta_agents import write_prompts
    write_prompts(run, packet)
    lines = ["# META analysis research packet", "", f"Cutoff: {packet['as_of']}", "", packet["notice"], "",
             "| Symbol | Price date | Close | RV63 | Price / SMA200 | Status |", "|---|---|---:|---:|---:|---|"]
    def display(value, places=2):
        return f"{value:.{places}f}" if isinstance(value, (int, float)) else "—"
    for symbol, p in prices.items():
        lines.append(f"| {symbol} | {p.get('price_date', '—')} | {display(p.get('latest_close'))} | "
                     f"{display(p.get('realized_vol63_pct'))}% | {display(p.get('price_to_sma200'), 4)} | {p['status']} |")
    lines += ["", "## Fundamental and ETF evidence", "",
              "| Symbol | Evidence type | Coverage | Latest period/as-of |",
              "|---|---|---|---|"]
    for symbol in snapshot["symbols"]:
        if symbol in fundamentals:
            profile = fundamentals[symbol]
            ends = [value["end"] for value in profile["metrics"].values()]
            lines.append(f"| {symbol} | SEC company facts | {len(profile['metrics'])} standardized metrics | {max(ends) if ends else '—'} |")
        elif symbol in etf_profiles:
            profile = etf_profiles[symbol]
            lines.append(f"| {symbol} | Sponsor holdings table/export | {profile['holdings_count']} holdings / {profile['reported_weight_pct']:.2f}% weight | {profile['as_of']} |")
        else:
            lines.append(f"| {symbol} | {'ETF holdings' if symbol in snapshot['etfs'] else 'SEC company facts'} | MISSING | — |")
    lines += ["", "## Primary issuer, sector and policy evidence", "",
              f"Normalized records: {sum(primary_counts.values())}. Supplemental acquisition failures remain visible and do not weaken the quant-only close guard.", "",
              "| Family | Records |", "|---|---:|"]
    for family, count in primary_counts.items():
        lines.append(f"| {family} | {count} |")
    lines += ["", "## Cycle and market evidence", "",
              "Values have different observation dates. FRESH uses explicit age limits; it does not mean a same-day release.", "",
              "| Indicator | Observation date | Value | Unit | Status |",
              "|---|---|---:|---|---|"]
    for key, value in packet["market"].items():
        if isinstance(value, dict):
            lines.append(f"| {key} | {value.get('observed_date', '—')} | {display(value.get('value'), 4)} | "
                         f"{value.get('unit', '—')} | {value['status']} |")
    lines += ["", "## Assumption-based terminal-price reference", "",
              "Central 80% model interval (10th–90th percentiles), not empirically calibrated coverage. "
              "Zero log drift: probability of finishing above the reference close is 50% by construction. "
              "These numbers do not incorporate cycle or agent directional views.", "",
              "| Symbol | Sessions | Bear/bull return boundary | 10th–90th price | Bear / neutral / bull |",
              "|---|---:|---:|---|---|"]
    for symbol, p in prices.items():
        for scenario in p.get("reference_scenarios", []):
            q, prob = scenario["price_quantiles"], scenario["probabilities"]
            lines.append(f"| {symbol} | {scenario['trading_days']} | ±{scenario['return_threshold_pct']:.0f}% | "
                         f"{q['0.1']:.2f}–{q['0.9']:.2f} | "
                         f"{100*prob['bear']:.1f}% / {100*prob['neutral']:.1f}% / {100*prob['bull']:.1f}% |")
    lines += ["", "Fundamentals, political exposure and material news require the specialist evidence review.",
              "See packet.json for source timestamps, macro/credit values and conditional terminal-price ranges.",
              "Specialist execution is separate; generated prompts are not completed agent analyses."]
    write_bytes_exclusive(run/"report.md", ("\n".join(lines)+"\n").encode())
    return run


def _write_on_demand_report(packet_path: Path, agent_run: Path) -> Path:
    packet = json.loads(packet_path.read_text())
    report = json.loads((agent_run / "meta-report.json").read_text())
    synthesis = report.get("results", {}).get("synthesis", {}).get("assessments", [])
    golden = report.get("results", {}).get("synthesis", {}).get("golden_conclusions")
    by_symbol = {row["symbol"]: row for row in synthesis}
    structured_path = agent_run / "structured-forecast.json"
    structured = json.loads(structured_path.read_text()) if structured_path.is_file() else None
    lines = [
        "# On-demand META analysis", "",
        f"Information cutoff: {packet['as_of']}",
        f"Market period: {packet['operating_context']['market_period']}",
        f"Price basis: {packet['operating_context']['price_basis']}",
        f"Agent status: {report['status']}", "",
        "META probabilities and research actions are deterministic experimental policy outputs. "
        "They are not prospectively calibrated and are not trading instructions.", "",
    ]
    lines += ["## GOLDEN RECOMMENDATIONS / GOLDEN CONCLUSIONS", ""]
    if golden:
        lines += ["### Astra META executive assessment", "", golden["overall_conclusion"], "",
                  "### Market regime", "", golden["market_regime"], "", "### Critical conclusions", ""]
        lines.extend(f"- {value}" for value in golden["critical_findings"])
        lines += ["", "### Decision rows", "",
                  "| Symbol | Sessions | Action | New / existing | P(terminal gain) | What changes it |",
                  "|---|---:|---|---|---:|---|"]
        for row in sorted(golden["decision_rows"], key=lambda value: (value["symbol"], value["trading_days"])):
            lines.append(f"| {row['symbol']} | {row['trading_days']} | {row['action_now']} | "
                         f"{row['new_position_action']} / {row['existing_position_action']} | "
                         f"{100*row['probability_price_up']:.1f}% | {row['what_changes_action']} |")
        lines += ["", "### Immediate review triggers", ""]
        lines.extend(f"- {value}" for value in golden["immediate_review_triggers"])
        lines += ["", "### Decisive evidence limitations", ""]
        lines.extend(f"- {value}" for value in golden["evidence_limitations"])
        lines.append("")
    else:
        lines += ["A validated Astra META synthesis is unavailable for this run.", ""]
    for symbol in packet["symbols"]:
        instrument = packet["instruments"].get(symbol, {})
        assessment = by_symbol.get(symbol)
        lines += [f"## {symbol}", "",
                  f"Latest completed close: {instrument.get('latest_close', '—')} "
                  f"({instrument.get('price_date', '—')}); status: {instrument.get('status', 'MISSING')}", ""]
        intraday = packet.get("intraday", {}).get(symbol)
        if intraday:
            lines += [f"Intraday context: {intraday.get('status', 'MISSING')}; "
                      f"state `{intraday.get('evidence_state', '—')}`; coverage "
                      f"`{intraday.get('exchange_coverage', '—')}`; latest timestamp "
                      f"{intraday.get('latest_timestamp', '—')}", ""]
        if not assessment:
            lines += ["Final synthesis unavailable.", ""]
            continue
        lines += [f"View: `{assessment['view']}`; evidence status: `{assessment['status']}`", "",
                  assessment["thesis"], ""]
        scenarios = instrument.get("reference_scenarios", [])
        if scenarios:
            lines += ["Assumption-based uncalibrated reference:", ""]
            for scenario in scenarios:
                probabilities = scenario["probabilities"]
                lines.append(
                    f"- {scenario['trading_days']} sessions: bear {100*probabilities['bear']:.1f}%, "
                    f"neutral {100*probabilities['neutral']:.1f}%, bull {100*probabilities['bull']:.1f}%")
            lines.append("")
        if assessment["claims"]:
            lines += ["Claims:", ""]
            for claim in assessment["claims"]:
                lines.append(f"- **{claim['classification']}** — {claim['statement']} "
                             f"(evidence: {', '.join(claim['evidence_ids'])}; "
                             f"horizons: {', '.join(str(v) for v in claim['horizons'])})")
            lines.append("")
        if assessment["missing"]:
            lines += ["Missing: " + "; ".join(assessment["missing"]), ""]
        if assessment["invalidation"]:
            lines += ["Invalidation: " + "; ".join(assessment["invalidation"]), ""]
        structured_symbol = (structured or {}).get("symbols", {}).get(symbol, {})
        if structured_symbol.get("horizons"):
            lines += ["Experimental structured forecast:", "",
                      "| Sessions | P(up) | Bear / neutral / bull | Expected return | Research action |",
                      "|---:|---:|---|---:|---|"]
            for horizon in structured_symbol["horizons"]:
                if horizon.get("status") != "EXPERIMENTAL_UNCALIBRATED":
                    continue
                distribution = horizon["distribution"]
                probabilities = distribution["probabilities"]
                lines.append(
                    f"| {horizon['trading_days']} | {100*distribution['probability_price_up']:.1f}% | "
                    f"{100*probabilities['bear']:.1f}% / {100*probabilities['neutral']:.1f}% / "
                    f"{100*probabilities['bull']:.1f}% | "
                    f"{distribution['expected_simple_return_pct']:.2f}% | "
                    f"`{horizon['recommendation'].get('action_now', horizon['recommendation'].get('action'))}` |")
            lines.append("")
    lines += ["## Run identity", "", f"Packet: `{packet['packet_hash']}`",
              f"Agent run: `{agent_run.name}`", "",
              "This on-demand report was not entered into the prospective ledger.", ""]
    path = agent_run / "on-demand-report.md"
    write_bytes_exclusive(path, "\n".join(lines).encode())
    return path


def analyze(targets: list[str], etfs: list[str], *, runner_config: Path,
            capture_root: Path = ROOT/"datasets/workbench/meta",
            analysis_root: Path = ROOT/"reports/meta-analysis",
            holdings_files: dict[str, Path] | None = None,
            etf_profile_files: dict[str, Path] | None = None,
            evidence_file: Path | None = None,
            delayed_context_file: Path | None = None,
            primary_sources_file: Path | None = DEFAULT_PRIMARY_SOURCES,
            product_config: Path = DEFAULT_PRODUCT_CONFIG,
            forecast_policy: Path = DEFAULT_FORECAST_POLICY,
            operations_policy: Path = DEFAULT_OPERATIONS_POLICY,
            market_data_mode: str = "completed-close",
            intraday_feed: str = "iex") -> dict:
    """Run the non-registering on-demand lane over one newly frozen packet."""
    load_product_contract(product_config)
    if market_data_mode not in {"completed-close", "intraday"}:
        raise ValueError("market_data_mode must be completed-close or intraday")
    if intraday_feed not in {"iex", "sip-delayed"}:
        raise ValueError("intraday_feed must be iex or sip-delayed")
    snapshot_path = capture(capture_root, targets, etfs, None, evidence_file,
                            holdings_files, False, delayed_context_file,
                            primary_sources_file, etf_profile_files,
                            market_data_mode, intraday_feed,
                            operations_policy_path=operations_policy)
    analysis_run = build(snapshot_path, analysis_root, product_config=product_config,
                         lane="ON_DEMAND_ANALYSIS")
    packet_path = analysis_run / "packet.json"
    from spy_predictor_quant.meta_agents import run_agents
    agent_run = run_agents(packet_path, runner_config, analysis_root,
                           operations_policy_path=operations_policy,
                           forecast_policy_path=forecast_policy)
    from spy_predictor_quant.meta_forecast import create_structured_forecast
    structured_path = create_structured_forecast(
        packet_path, agent_run / "meta-report.json", agent_run / "structured-forecast.json",
        forecast_policy)
    report_path = _write_on_demand_report(packet_path, agent_run)
    packet = json.loads(packet_path.read_text())
    agent_report = json.loads((agent_run / "meta-report.json").read_text())
    structured = json.loads(structured_path.read_text())
    from spy_predictor_quant.meta_product import write_product_bundle
    product_bundle = write_product_bundle(
        packet_path, agent_run / "product", structured_path=structured_path,
        report_path=agent_run / "meta-report.json", mode="ON_DEMAND",
        forecast_root=ROOT/"datasets/meta-observation/forecasts")
    core = {
        "schema_version": "meta-on-demand-receipt-v1",
        "status": "COMPLETED" if not agent_report["failures"] else "PARTIAL",
        "lane": "ON_DEMAND_ANALYSIS",
        "prospective_registration": False,
        "symbols": targets,
        "etfs": etfs,
        "information_cutoff": packet["as_of"],
        "market_period": packet["operating_context"]["market_period"],
        "market_data_mode": market_data_mode,
        "intraday_feed": intraday_feed if market_data_mode == "intraday" else None,
        "price_basis": packet["operating_context"]["price_basis"],
        "product_contract_hash": file_sha256(product_config),
        "probability_status": structured["probability_status"],
        "calibration_status": structured["calibration_status"],
        "forecast_policy_hash": structured["governance"]["policy_hash"],
        "governance_cohort_id": structured["governance"]["cohort_id"],
        "snapshot_path": str(snapshot_path.resolve()),
        "packet_path": str(packet_path.resolve()),
        "packet_hash": packet["packet_hash"],
        "agent_run": str(agent_run.resolve()),
        "agent_report_hash": file_sha256(agent_run / "meta-report.json"),
        "structured_forecast_path": str(structured_path.resolve()),
        "structured_forecast_hash": structured["artifact_hash"],
        "report_path": str(report_path.resolve()),
        "product_bundle": str(product_bundle.resolve()),
        "notice": "On-demand research output; not a prospective forecast or trading instruction.",
    }
    core["receipt_hash"] = digest(core)
    write_json_exclusive(agent_run / "on-demand-receipt.json", core)
    return core


def _cli_exit_status(action: str, output) -> int:
    """Make partial agent chains visible to shells and daily automation."""
    if action == "analyze" and isinstance(output, dict) and output.get("status") == "PARTIAL":
        return 1
    if action == "agents" and isinstance(output, Path):
        report_path = output / "meta-report.json"
        if report_path.is_file() and json.loads(report_path.read_text()).get("status") == "PARTIAL":
            return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    acquire = sub.add_parser("capture")
    acquire.add_argument("--symbols", nargs="+", required=True)
    acquire.add_argument("--etfs", nargs="+", default=[])
    acquire.add_argument("--root", type=Path, default=ROOT/"datasets/workbench/meta")
    acquire.add_argument("--local-prices", type=Path)
    acquire.add_argument("--evidence", type=Path)
    acquire.add_argument("--etf-holdings", action="append", default=[], metavar="SYMBOL=CSV")
    acquire.add_argument("--etf-profile", action="append", default=[], metavar="SYMBOL=JSON")
    acquire.add_argument("--primary-sources", type=Path, default=DEFAULT_PRIMARY_SOURCES)
    acquire.add_argument("--ibkr-delayed-context", type=Path)
    acquire.add_argument("--macro-only", action="store_true")
    acquire.add_argument("--market-data-mode", choices=("completed-close", "intraday"),
                         default="completed-close")
    acquire.add_argument("--intraday-feed", choices=("iex", "sip-delayed"), default="iex")
    acquire.add_argument("--operations-policy", type=Path)
    acquire.add_argument("--cache-root", type=Path, default=ROOT/"datasets/meta-cache")
    calculate = sub.add_parser("build")
    calculate.add_argument("--snapshot", type=Path, required=True)
    calculate.add_argument("--output", type=Path, default=ROOT/"reports/meta-analysis")
    agents = sub.add_parser("agents")
    agents.add_argument("--packet", type=Path)
    agents.add_argument("--runner-config", type=Path)
    agents.add_argument("--resume", type=Path)
    agents.add_argument("--output", type=Path, default=ROOT/"reports/meta-analysis")
    agents.add_argument("--operations-policy", type=Path, default=DEFAULT_OPERATIONS_POLICY)
    agents.add_argument("--forecast-policy", type=Path, default=DEFAULT_FORECAST_POLICY)
    ondemand = sub.add_parser("analyze")
    ondemand.add_argument("--symbols", nargs="+", required=True)
    ondemand.add_argument("--etfs", nargs="+", default=[])
    ondemand.add_argument("--etf-holdings", action="append", default=[], metavar="SYMBOL=CSV")
    ondemand.add_argument("--etf-profile", action="append", default=[], metavar="SYMBOL=JSON")
    ondemand.add_argument("--primary-sources", type=Path, default=DEFAULT_PRIMARY_SOURCES)
    ondemand.add_argument("--evidence", type=Path)
    ondemand.add_argument("--ibkr-delayed-context", type=Path)
    ondemand.add_argument("--runner-config", type=Path, required=True)
    ondemand.add_argument("--product-config", type=Path, default=DEFAULT_PRODUCT_CONFIG)
    ondemand.add_argument("--forecast-policy", type=Path, default=DEFAULT_FORECAST_POLICY)
    ondemand.add_argument("--operations-policy", type=Path, default=DEFAULT_OPERATIONS_POLICY)
    ondemand.add_argument("--market-data-mode", choices=("completed-close", "intraday"),
                          default="completed-close")
    ondemand.add_argument("--intraday-feed", choices=("iex", "sip-delayed"), default="iex")
    ondemand.add_argument("--capture-root", type=Path, default=ROOT/"datasets/workbench/meta")
    ondemand.add_argument("--analysis-root", type=Path, default=ROOT/"reports/meta-analysis")
    observe = sub.add_parser("observe")
    observe.add_argument("--packet", type=Path, required=True)
    observe.add_argument("--meta-report", type=Path)
    observe.add_argument("--structured-forecast", type=Path)
    observe.add_argument("--output", type=Path, default=ROOT/"datasets/meta-observation/forecasts")
    post = sub.add_parser("postclose")
    post.add_argument("--symbols", nargs="+", required=True)
    post.add_argument("--etfs", nargs="+", default=[])
    post.add_argument("--etf-holdings", action="append", default=[], metavar="SYMBOL=CSV")
    post.add_argument("--etf-profile", action="append", default=[], metavar="SYMBOL=JSON")
    post.add_argument("--primary-sources", type=Path, default=DEFAULT_PRIMARY_SOURCES)
    post.add_argument("--evidence", type=Path)
    post.add_argument("--ibkr-delayed-context", type=Path)
    post.add_argument("--capture-root", type=Path, default=ROOT/"datasets/workbench/meta")
    post.add_argument("--analysis-root", type=Path, default=ROOT/"reports/meta-analysis")
    post.add_argument("--forecast-root", type=Path, default=ROOT/"datasets/meta-observation/forecasts")
    post.add_argument("--preflight-only", action="store_true")
    post.add_argument("--runner-config", type=Path)
    post.add_argument("--forecast-policy", type=Path, default=DEFAULT_FORECAST_POLICY)
    post.add_argument("--operations-policy", type=Path, default=DEFAULT_OPERATIONS_POLICY)
    args = parser.parse_args()
    if args.action in {"capture", "postclose", "analyze"}:
        targets = symbols(args.symbols)
        etfs = [s.upper() for s in args.etfs]
        if not set(etfs).issubset(targets):
            parser.error("--etfs must be a subset of --symbols")
        holdings_files = {}
        for value in args.etf_holdings:
            if "=" not in value:
                parser.error("--etf-holdings requires SYMBOL=CSV")
            symbol, path = value.split("=", 1)
            symbol = symbol.upper()
            if symbol not in etfs or symbol in holdings_files:
                parser.error("ETF holdings identity must be a unique member of --etfs")
            holdings_files[symbol] = Path(path)
        etf_profile_files = {}
        for value in args.etf_profile:
            if "=" not in value:
                parser.error("--etf-profile requires SYMBOL=JSON")
            symbol, path = value.split("=", 1)
            symbol = symbol.upper()
            if symbol not in etfs or symbol in etf_profile_files:
                parser.error("ETF profile identity must be a unique member of --etfs")
            etf_profile_files[symbol] = Path(path)
        if args.action == "capture":
            output = capture(args.root, targets, etfs, args.local_prices, args.evidence,
                             holdings_files, args.macro_only, args.ibkr_delayed_context,
                             args.primary_sources, etf_profile_files,
                             args.market_data_mode, args.intraday_feed,
                             args.operations_policy, args.cache_root)
        elif args.action == "analyze":
            output = analyze(targets, etfs, runner_config=args.runner_config,
                             capture_root=args.capture_root, analysis_root=args.analysis_root,
                             holdings_files=holdings_files, etf_profile_files=etf_profile_files,
                             evidence_file=args.evidence,
                             delayed_context_file=args.ibkr_delayed_context,
                             primary_sources_file=args.primary_sources,
                             product_config=args.product_config,
                             forecast_policy=args.forecast_policy,
                             operations_policy=args.operations_policy,
                             market_data_mode=args.market_data_mode,
                             intraday_feed=args.intraday_feed)
        elif args.preflight_only:
            output = postclose_preflight(targets, args.forecast_root)
        else:
            output = postclose(targets, etfs, capture_root=args.capture_root,
                               analysis_root=args.analysis_root, forecast_root=args.forecast_root,
                               holdings_files=holdings_files, etf_profile_files=etf_profile_files,
                               evidence_file=args.evidence, delayed_context_file=args.ibkr_delayed_context,
                               primary_sources_file=args.primary_sources,
                               runner_config=args.runner_config,
                               forecast_policy=args.forecast_policy,
                               operations_policy=args.operations_policy)
    elif args.action == "build":
        output = build(args.snapshot, args.output)
    elif args.action == "agents":
        from spy_predictor_quant.meta_agents import resume_inputs, run_agents
        packet_path, config_path = args.packet, args.runner_config
        if args.resume:
            resumed_packet, resumed_config = resume_inputs(args.resume)
            packet_path = packet_path or resumed_packet
            config_path = config_path or resumed_config
        if not packet_path or not config_path:
            parser.error("agents requires --packet and --runner-config, or --resume")
        output = run_agents(packet_path, config_path, args.output, args.resume,
                            args.operations_policy, args.forecast_policy)
    elif args.action == "observe":
        from spy_predictor_quant.meta_observation import register
        output = register(args.packet, args.output, args.meta_report,
                          structured_forecast_path=args.structured_forecast)
    print(json.dumps(output if isinstance(output, dict) else {"output": str(output)},
                     indent=2, sort_keys=True, allow_nan=False))
    return _cli_exit_status(args.action, output)


if __name__ == "__main__":
    raise SystemExit(main())
