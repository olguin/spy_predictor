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
from threading import Lock
import time
from statistics import NormalDist
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import numpy as np

from spy_predictor_quant.cycle_workbench import _instant
from spy_predictor_quant.market_archive import (
    create_immutable_run_directory, file_sha256, write_bytes_exclusive,
    write_json_exclusive, utc_now,
)
from spy_predictor_quant.meta_evidence import (
    company_fundamentals, etf_overlap, exposure_news_symbols, parse_holdings_csv,
    recent_filings, sec_ticker_map,
)

VERSION = "meta-analysis-v1"
ROOT = Path(__file__).resolve().parents[3]
# Series-specific observation-age limits, in calendar days. These are explicit
# first-version SLAs, not a release-calendar implementation.
SERIES = {
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
HORIZONS = (5, 21, 63)


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


def get_raw(url: str, headers: dict | None = None) -> bytes:
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


def capture(root: Path, targets: list[str], etfs: list[str], local_prices: Path | None,
            evidence_file: Path | None, holdings_files: dict[str, Path] | None = None,
            macro_only: bool = False, delayed_context_file: Path | None = None) -> Path:
    run = create_immutable_run_directory(root, "capture")
    (run / "raw").mkdir()
    start = max(date(2025, 8, 1), datetime.now(timezone.utc).date() - timedelta(days=420))
    sources, errors = {}, {}

    def fred(series):
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urlencode({
            "id": series, "cosd": (date.today() - timedelta(days=1100)).isoformat()})
        raw = get_raw(url)
        # Validate before marking an HTTP-successful HTML response as usable.
        parse_fred(raw, series)
        return archive(run, series, url, raw, kind="fred_csv")

    def guarded(identity, function):
        try:
            return identity, function(), None
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
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

    stocks = [symbol for symbol in targets if symbol not in etfs]
    sec_user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if stocks and not macro_only and not sec_user_agent:
        for symbol in stocks:
            errors[f"sec-{symbol}"] = "SEC_USER_AGENT_REQUIRED"
    elif stocks and not macro_only:
        sec = SecHttpClient(sec_user_agent)
        ticker_url = "https://www.sec.gov/files/company_tickers.json"
        try:
            ticker_raw = sec.get(ticker_url)
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
                    raw = sec.get(url)
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
            raw = get_raw(url, headers)
            data = json.loads(raw)
            if data.get("symbol") != symbol:
                raise ValueError("Alpaca returned a different instrument identity")
            if data.get("next_page_token"):
                raise ValueError("Unexpected price pagination; refusing a partial price window")
            return archive(run, f"price-{symbol}", url, raw, kind="alpaca_daily",
                           symbol=symbol, adjustment="split;cash-dividends-excluded", feed=feed,
                           data_end=data_end, request_delay_minutes=20)
        identity, source, error = guarded(f"price-{symbol}", price_source)
        if source:
            sources[identity] = source
        else:
            errors[identity] = error

    if headers and not macro_only:
        def news_source():
            holding_symbols, exposures = exposure_news_symbols(holdings_profiles)
            query_symbols = list(dict.fromkeys(targets + holding_symbols))
            url = "https://data.alpaca.markets/v1beta1/news?" + urlencode({
                "symbols": ",".join(query_symbols), "start": (date.today()-timedelta(days=7)).isoformat(),
                "sort": "desc", "limit": 50, "include_content": "false"})
            raw = get_raw(url, headers)
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
               "etfs": etfs, "sources": sources, "acquisition_errors": errors,
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


def transparent_risk_appetite(market: dict, prices: dict) -> dict:
    fresh = [value for value in prices.values() if value.get("status") == "FRESH"]
    vix_percentile = market.get("VIXCLS", {}).get("fear_proxy_percentile")
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
    for series in SERIES:
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
              evidence_file: Path | None = None,
              delayed_context_file: Path | None = None) -> dict:
    preflight = postclose_preflight(targets, forecast_root)
    if preflight["status"] != "READY":
        raise ValueError(f"META post-close preflight: {preflight['status']}")
    snapshot_path = capture(capture_root, targets, etfs, None, evidence_file,
                            holdings_files, False, delayed_context_file)
    analysis = build(snapshot_path, analysis_root)
    packet_path = analysis / "packet.json"
    validation = validate_postclose_packet(
        packet_path, targets, etfs, preflight["origin_session"], delayed_context_file is not None,
        set((holdings_files or {}).keys()))
    from spy_predictor_quant.meta_observation import register
    forecast_path = register(packet_path, forecast_root)
    packet = json.loads(packet_path.read_text())
    forecast = json.loads(forecast_path.read_text())
    receipt = {"schemaVersion": "meta-postclose-receipt-v1", "status": "REGISTERED_QUANT_ONLY",
               "origin_session": preflight["origin_session"], "snapshot_path": str(snapshot_path.resolve()),
               "snapshot_hash": packet["snapshot_hash"], "analysis_path": str(analysis.resolve()),
               "packet_path": str(packet_path.resolve()), "packet_hash": packet["packet_hash"],
               "forecast_path": str(forecast_path.resolve()), "forecast_hash": forecast["forecast_hash"],
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
              "source_ids": [source["id"]], "currency": "USD", "sessions": len(rows),
              "adjustment": source["adjustment"], "feed": source["feed"],
              "rsi14_simple": float(rsi), "atr14_simple": float(np.mean(tr)),
              "drawdown_from_window_high_pct": float(100*(prices[-1]/prices.max()-1)),
              "drawdown_window_sessions": len(rows),
              "greed_proxy": {"momentum_rsi14": float(rsi), "meaning": "Momentum only; not observed investor greed"}}
    for window in (20, 50, 200):
        result[f"sma{window}"] = float(prices[-window:].mean())
        result[f"price_to_sma{window}"] = float(prices[-1]/prices[-window:].mean())
    for window in (21, 63):
        result[f"realized_vol{window}_pct"] = float(100*returns[-window:].std(ddof=1)*math.sqrt(252))
        result[f"return{window}_pct"] = float(100*(prices[-1]/prices[-window-1]-1))
    result["reference_scenarios"] = (reference_scenarios(result["latest_close"], result["realized_vol63_pct"])
                                     if status == "FRESH" else [])
    return result


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


def build(snapshot_path: Path, output_root: Path) -> Path:
    snapshot, raw = load_snapshot(snapshot_path)
    cutoff = _instant(snapshot["as_of"])
    histories = {key: parse_fred(value, key) for key, value in raw.items() if key in SERIES}
    prices = {}
    fundamentals, etf_profiles = {}, {}
    evidence = {key: {**source, "availability_policy": "conservative-retrieval-time",
                      "historical_first_seen_established": False}
                for key, source in snapshot["sources"].items()}
    for symbol in snapshot["symbols"]:
        key = f"price-{symbol}"
        if key not in raw:
            prices[symbol] = {"status": "MISSING", "reason": snapshot["acquisition_errors"].get(key, "NOT_CAPTURED")}
            continue
        try:
            prices[symbol] = daily_metrics(json.loads(raw[key]), snapshot["sources"][key], cutoff)
        except (KeyError, ValueError, TypeError) as exc:
            prices[symbol] = {"status": "INVALID", "reason": str(exc)}
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
    fresh = [p for p in prices.values() if p["status"] == "FRESH"]
    market = macro_metrics(histories, cutoff)
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
    packet = {"version": VERSION, "snapshot_hash": snapshot["snapshot_hash"], "as_of": snapshot["as_of"],
        "symbols": snapshot["symbols"], "etfs": snapshot["etfs"], "horizons": list(HORIZONS),
        "market": market, "instruments": prices, "evidence": evidence,
        "transparent_risk_appetite": transparent_risk_appetite(market, prices),
        "delayed_ibkr_context": delayed_context,
        "company_fundamentals": fundamentals, "etf_holdings": etf_profiles,
        "etf_overlap": [etf_overlap(etf_profiles[a], etf_profiles[b])
                        for index, a in enumerate(sorted(etf_profiles)) for b in sorted(etf_profiles)[index+1:]],
        "watchlist_above_sma200_pct": 100*sum(p["price_to_sma200"] > 1 for p in fresh)/len(fresh) if fresh else None,
        "breadth_coverage": {"fresh": len(fresh), "requested": len(prices), "meaning": "Selected watchlist only; not whole-market breadth"},
        "fundamental_coverage": {s: "NORMALIZED_EVIDENCE_REQUIRES_ANALYSIS" if any(
            e.get("kind") in {"filing", "etf_holdings"} and s in e.get("symbols", []) for e in evidence.values())
            else "MISSING" for s in prices},
        "geopolitical_coverage": "SOURCE_DEPENDENT;NO_EXHAUSTIVE_GLOBAL_NEWS_CLAIM",
        "calibrated_forecast": None, "quantitative_forecast_status": "NO_QUALIFIED_META_FORECAST",
        "notice": "Independent cycle proxies. Reference probabilities are uncalibrated assumptions. Agent views are qualitative.",
        "implementation_sha256": file_sha256(Path(__file__)), "acquisition_errors": snapshot["acquisition_errors"]}
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
    acquire.add_argument("--ibkr-delayed-context", type=Path)
    acquire.add_argument("--macro-only", action="store_true")
    calculate = sub.add_parser("build")
    calculate.add_argument("--snapshot", type=Path, required=True)
    calculate.add_argument("--output", type=Path, default=ROOT/"reports/meta-analysis")
    agents = sub.add_parser("agents")
    agents.add_argument("--packet", type=Path, required=True)
    agents.add_argument("--runner-config", type=Path, required=True)
    agents.add_argument("--output", type=Path, default=ROOT/"reports/meta-analysis")
    observe = sub.add_parser("observe")
    observe.add_argument("--packet", type=Path, required=True)
    observe.add_argument("--meta-report", type=Path)
    observe.add_argument("--output", type=Path, default=ROOT/"datasets/meta-observation/forecasts")
    post = sub.add_parser("postclose")
    post.add_argument("--symbols", nargs="+", required=True)
    post.add_argument("--etfs", nargs="+", default=[])
    post.add_argument("--etf-holdings", action="append", default=[], metavar="SYMBOL=CSV")
    post.add_argument("--evidence", type=Path)
    post.add_argument("--ibkr-delayed-context", type=Path)
    post.add_argument("--capture-root", type=Path, default=ROOT/"datasets/workbench/meta")
    post.add_argument("--analysis-root", type=Path, default=ROOT/"reports/meta-analysis")
    post.add_argument("--forecast-root", type=Path, default=ROOT/"datasets/meta-observation/forecasts")
    post.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.action in {"capture", "postclose"}:
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
        if args.action == "capture":
            output = capture(args.root, targets, etfs, args.local_prices, args.evidence,
                             holdings_files, args.macro_only, args.ibkr_delayed_context)
        elif args.preflight_only:
            output = postclose_preflight(targets, args.forecast_root)
        else:
            output = postclose(targets, etfs, capture_root=args.capture_root,
                               analysis_root=args.analysis_root, forecast_root=args.forecast_root,
                               holdings_files=holdings_files, evidence_file=args.evidence,
                               delayed_context_file=args.ibkr_delayed_context)
    elif args.action == "build":
        output = build(args.snapshot, args.output)
    elif args.action == "agents":
        from spy_predictor_quant.meta_agents import run_agents
        output = run_agents(args.packet, args.runner_config, args.output)
    elif args.action == "observe":
        from spy_predictor_quant.meta_observation import register
        output = register(args.packet, args.output, args.meta_report)
    print(json.dumps(output if isinstance(output, dict) else {"output": str(output)},
                     indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
