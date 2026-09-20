"""Validated current fundamentals and ETF exposure evidence for META analysis."""
from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import html
import io
import json
import math
import re
from typing import Any
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from spy_predictor_quant.cycle_workbench import _instant

SEC_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "8-K/A"}
CONCEPTS = {
    "revenue": (("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"), "USD", "duration"),
    "net_income": (("NetIncomeLoss", "ProfitLoss"), "USD", "duration"),
    "operating_income": (("OperatingIncomeLoss",), "USD", "duration"),
    "operating_cash_flow": (("NetCashProvidedByUsedInOperatingActivities",), "USD", "duration"),
    "capital_expenditure": (("PaymentsToAcquirePropertyPlantAndEquipment",), "USD", "duration"),
    "assets": (("Assets",), "USD", "instant"),
    "liabilities": (("Liabilities",), "USD", "instant"),
    "equity": (("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"), "USD", "instant"),
    "cash": (("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"), "USD", "instant"),
    "long_term_debt": (("LongTermDebtAndFinanceLeaseObligationsCurrent", "LongTermDebtCurrent", "LongTermDebtNoncurrent"), "USD", "instant"),
    "diluted_eps": (("EarningsPerShareDiluted",), "USD/shares", "duration"),
    "shares_outstanding": (("EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding"), "shares", "instant"),
}
PRIMARY_KINDS = {"issuer_event", "issuer_release", "sector_release", "policy_event", "policy_release"}
PRIMARY_FORMATS = {"rss_atom", "federal_register_json", "fomc_calendar_html"}


def sec_ticker_map(payload: object) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("SEC ticker map must be an object")
    result = {}
    for item in payload.values():
        if not isinstance(item, dict):
            raise ValueError("Malformed SEC ticker entry")
        ticker = str(item.get("ticker", "")).upper()
        cik = item.get("cik_str")
        title = str(item.get("title", "")).strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker) or not isinstance(cik, int) or cik <= 0 or not title:
            raise ValueError("Invalid SEC ticker identity")
        if ticker in result:
            raise ValueError("Duplicate SEC ticker identity")
        result[ticker] = {"cik": f"{cik:010d}", "entity_name": title}
    if not result:
        raise ValueError("SEC ticker map is empty")
    return result


def recent_filings(payload: object, symbol: str, cutoff: datetime) -> dict:
    if not isinstance(payload, dict) or str(payload.get("cik", "")).zfill(10) == "0000000000":
        raise ValueError("Malformed SEC submissions payload")
    recent = payload.get("filings", {}).get("recent", {})
    required = ("accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "primaryDocument")
    if not all(isinstance(recent.get(key), list) for key in required):
        raise ValueError("SEC submissions recent arrays are missing")
    sizes = {len(recent[key]) for key in required}
    if len(sizes) != 1:
        raise ValueError("SEC submissions arrays have unequal lengths")
    rows = []
    for values in zip(*(recent[key] for key in required), strict=True):
        row = dict(zip(required, values, strict=True))
        if row["form"] not in SEC_FORMS:
            continue
        accepted = _sec_acceptance(row["acceptanceDateTime"])
        if accepted > cutoff:
            continue
        accession = str(row["accessionNumber"])
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
            raise ValueError("Invalid SEC accession")
        cik = str(payload["cik"]).lstrip("0")
        document = str(row["primaryDocument"])
        if not re.fullmatch(r"[A-Za-z0-9._-]+", document):
            raise ValueError("Invalid SEC primary document path")
        rows.append({**row, "accepted_at": accepted.isoformat(),
                     "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{document}"})
    rows.sort(key=lambda row: row["accepted_at"], reverse=True)
    periodic = []
    seen = set()
    for row in rows:
        family = "10-K" if row["form"].startswith("10-K") else "10-Q" if row["form"].startswith("10-Q") else None
        if family and family not in seen:
            periodic.append(row)
            seen.add(family)
    events = [row for row in rows if row["form"].startswith("8-K")][:5]
    return {"symbol": symbol, "cik": str(payload["cik"]).zfill(10),
            "entity_name": payload.get("name"), "sic": payload.get("sic"),
            "sic_description": payload.get("sicDescription"),
            "periodic": periodic, "recent_events": events,
            "coverage": "latest 10-K, latest 10-Q, and up to five recent 8-K filings"}


def company_fundamentals(payload: object, symbol: str, cutoff: datetime, filings: dict) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("facts", {}).get("us-gaap"), dict):
        raise ValueError("Malformed SEC companyfacts payload")
    facts = payload["facts"]["us-gaap"]
    cik = str(payload.get("cik", "")).zfill(10)
    if cik != filings.get("cik") or symbol != filings.get("symbol"):
        raise ValueError("SEC submissions/companyfacts identity mismatch")
    admitted_accessions = {row["accessionNumber"] for row in filings["periodic"]}
    metrics = {}
    for name, (candidates, unit, period_kind) in CONCEPTS.items():
        selected = None
        for priority, concept in enumerate(candidates):
            item = facts.get(concept)
            if not item:
                continue
            units = item.get("units", {}).get(unit, [])
            for observation in units:
                if observation.get("form") not in {"10-K", "10-K/A", "10-Q", "10-Q/A"}:
                    continue
                if observation.get("accn") not in admitted_accessions:
                    continue
                filed = _end_of_day(observation.get("filed"))
                if filed > cutoff:
                    continue
                start = observation.get("start")
                end = observation.get("end")
                value = observation.get("val")
                if (period_kind == "duration" and not start) or not end or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    continue
                key = (filed, date.fromisoformat(end), -priority)
                candidate = {"concept": concept, "label": item.get("label"), "unit": unit,
                             "value": value, "start": start, "end": end,
                             "filed": observation["filed"], "form": observation["form"],
                             "fiscal_year": observation.get("fy"), "fiscal_period": observation.get("fp"),
                             "accession": observation.get("accn"), "frame": observation.get("frame"),
                             "selection_key": key}
                if selected is None or key > selected["selection_key"]:
                    selected = candidate
        if selected:
            selected.pop("selection_key")
            metrics[name] = selected
    # Selected values can refer to periods of different length; compute ratios
    # only for same-period values and preserve raw facts otherwise.
    derived = {}
    revenue, operating, income = metrics.get("revenue"), metrics.get("operating_income"), metrics.get("net_income")
    if revenue and revenue["value"] > 0:
        if operating and (operating["start"], operating["end"]) == (revenue["start"], revenue["end"]):
            derived["operating_margin_pct"] = 100*operating["value"]/revenue["value"]
        if income and (income["start"], income["end"]) == (revenue["start"], revenue["end"]):
            derived["net_margin_pct"] = 100*income["value"]/revenue["value"]
    return {"symbol": symbol, "entity_name": payload.get("entityName"),
            "cik": cik, "metrics": metrics,
            "derived": derived, "filings": filings,
            "limitations": ["latest retrieved SEC company facts only", "custom taxonomy facts excluded",
                            "no market-derived valuation multiple", "period lengths may differ by issuer"]}


def parse_holdings_csv(raw: bytes, fund_symbol: str, cutoff: datetime) -> dict:
    try:
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    except UnicodeDecodeError as error:
        raise ValueError("ETF holdings must be UTF-8 CSV") from error
    required = {"as_of", "source_url", "ticker", "name", "weight_pct"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("ETF holdings need as_of,ticker,name,weight_pct columns")
    holdings, dates, source_urls, seen = [], set(), set(), set()
    for row in rows:
        as_of = date.fromisoformat(row["as_of"])
        ticker = row["ticker"].upper().strip()
        name = row["name"].strip()
        weight = float(row["weight_pct"])
        source_url = row["source_url"].strip()
        if as_of > cutoff.date() or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker) or not name:
            raise ValueError("ETF holding has invalid/future identity")
        if not source_url.startswith("https://"):
            raise ValueError("ETF holdings require an HTTPS sponsor source URL")
        if not math.isfinite(weight) or not 0 < weight <= 100 or ticker in seen:
            raise ValueError("ETF weights must be finite, positive, and unique by ticker")
        dates.add(as_of)
        source_urls.add(source_url)
        seen.add(ticker)
        holdings.append({"ticker": ticker, "name": name, "weight_pct": weight,
                         "sector": row.get("sector", "").strip() or None})
    if len(dates) != 1 or len(source_urls) != 1 or sum(item["weight_pct"] for item in holdings) > 100.5:
        raise ValueError("ETF holdings require one as-of date/source URL and total weight <= 100.5%")
    holdings.sort(key=lambda item: item["weight_pct"], reverse=True)
    sectors = {}
    for item in holdings:
        if item["sector"]:
            sectors[item["sector"]] = sectors.get(item["sector"], 0)+item["weight_pct"]
    holdings_date = dates.pop()
    age_days = (cutoff.date()-holdings_date).days
    return {"symbol": fund_symbol, "as_of": holdings_date.isoformat(), "status": "CURRENT" if age_days <= 7 else "STALE",
            "age_days": age_days, "maximum_age_days": 7, "source_url": source_urls.pop(), "holdings": holdings,
            "holdings_count": len(holdings), "reported_weight_pct": sum(i["weight_pct"] for i in holdings),
            "top10_weight_pct": sum(i["weight_pct"] for i in holdings[:10]),
            "sector_weights_pct": dict(sorted(sectors.items(), key=lambda item: item[1], reverse=True)),
            "limitations": "Current supplied sponsor table/export; historical composition and first-seen time not established"}


def exposure_news_symbols(profiles: dict[str, dict], limit: int = 20) -> tuple[list[str], dict[str, dict[str, float]]]:
    exposures: dict[str, dict[str, float]] = {}
    for fund, profile in profiles.items():
        for item in profile["holdings"]:
            exposures.setdefault(item["ticker"], {})[fund] = item["weight_pct"]
    ranked = sorted(exposures, key=lambda ticker: max(exposures[ticker].values()), reverse=True)
    return ranked[:limit], exposures


def etf_overlap(left: dict, right: dict) -> dict:
    a = {item["ticker"]: item["weight_pct"] for item in left["holdings"]}
    b = {item["ticker"]: item["weight_pct"] for item in right["holdings"]}
    common = sorted(a.keys() & b.keys(), key=lambda ticker: min(a[ticker], b[ticker]), reverse=True)
    return {"symbols": [left["symbol"], right["symbol"]],
            "overlap_min_weight_pct": sum(min(a[t], b[t]) for t in common),
            "common_holdings": [{"ticker": t, left["symbol"]: a[t], right["symbol"]: b[t]} for t in common[:20]],
            "coverage_note": "Minimum-weight overlap over supplied holdings only"}


def etf_quality_valuation(holdings: dict | None, sponsor_profile: dict | None) -> dict:
    """Join transparent holdings-derived quality with separately sourced fund metrics."""
    result = {
        "status": "MISSING", "holdings_coverage_pct": None, "top10_weight_pct": None,
        "sector_hhi": None, "sponsor_metrics": {}, "source_dates": {},
        "limitations": ["no constituent fundamentals are imputed from fund-level values",
                        "sponsor metrics are descriptive and not a calibrated return signal"],
    }
    if holdings:
        result.update(status="PARTIAL", holdings_coverage_pct=holdings["reported_weight_pct"],
                      top10_weight_pct=holdings["top10_weight_pct"])
        sectors = list(holdings.get("sector_weights_pct", {}).values())
        result["sector_hhi"] = sum((weight / 100) ** 2 for weight in sectors) if sectors else None
        result["source_dates"]["holdings"] = holdings["as_of"]
    if sponsor_profile:
        result["sponsor_metrics"] = sponsor_profile["metrics"]
        result["source_dates"]["sponsor_profile"] = sponsor_profile["as_of"]
        result["status"] = "COMPLETE_CURRENT_INPUTS" if holdings and holdings["status"] == "CURRENT" and sponsor_profile["status"] == "CURRENT" else "PARTIAL"
    return result


def company_market_valuation(fundamentals: dict | None, instrument: dict | None) -> dict:
    """Compute only transparent price/fact ratios; never synthesize earnings multiples."""
    if not fundamentals or not instrument or instrument.get("status") != "FRESH":
        return {"status": "MISSING", "metrics": {},
                "reason": "FRESH_PRICE_AND_SEC_FACTS_REQUIRED"}
    facts = fundamentals.get("metrics", {})
    shares = facts.get("shares_outstanding")
    price = instrument.get("latest_close")
    if not shares or not isinstance(price, (int, float)) or price <= 0 or shares["value"] <= 0:
        return {"status": "MISSING", "metrics": {},
                "reason": "SHARES_OUTSTANDING_OR_PRICE_UNAVAILABLE"}
    market_cap = price * shares["value"]
    metrics = {"market_cap_proxy_usd": market_cap}
    equity = facts.get("equity")
    if equity and equity["end"] == shares["end"] and equity["value"] > 0:
        metrics["price_to_book_proxy"] = market_cap / equity["value"]
    return {
        "status": "AVAILABLE" if "price_to_book_proxy" in metrics else "PARTIAL",
        "metrics": metrics,
        "price_date": instrument["price_date"], "shares_fact_end": shares["end"],
        "source_accessions": sorted({shares["accession"]} | ({equity["accession"]} if equity else set())),
        "formulae": {"market_cap_proxy_usd": "latest completed split-adjusted close * SEC shares outstanding",
                     "price_to_book_proxy": "market-cap proxy / SEC equity; only when shares and equity dates match"},
        "limitations": ["market and filing dates differ", "not a vendor-normalized valuation",
                        "no P/E, EV/EBITDA or forward multiple without qualified denominator evidence"],
    }


def instrument_evidence_profile(symbol: str, is_etf: bool, *, fundamentals: dict | None,
                                holdings: dict | None, sponsor_profile: dict | None,
                                instrument: dict | None) -> dict:
    if is_etf:
        families = {
            "holdings": holdings.get("status") if holdings else "MISSING",
            "sector_allocation": "AVAILABLE" if holdings and holdings.get("sector_weights_pct") else "MISSING",
            "country_allocation": "MISSING",
            "sponsor_metrics": sponsor_profile.get("status") if sponsor_profile else "MISSING",
        }
        return {"symbol": symbol, "instrument_type": "ETF", "families": families,
                "status": "COMPLETE_CURRENT_INPUTS" if all(value in {"CURRENT", "AVAILABLE"} for value in families.values()) else "PARTIAL",
                "missing": [key for key, value in families.items() if value == "MISSING"],
                "limitations": ["ETF evidence requires dated sponsor inputs; no automated sponsor-page scraping"]}
    filings = fundamentals.get("filings", {}) if fundamentals else {}
    forms = {row["form"].split("/")[0] for row in filings.get("periodic", [])}
    valuation = company_market_valuation(fundamentals, instrument)
    families = {
        "issuer_identity": "AVAILABLE" if fundamentals and fundamentals.get("cik") else "MISSING",
        "latest_10k": "AVAILABLE" if "10-K" in forms else "MISSING",
        "latest_10q": "AVAILABLE" if "10-Q" in forms else "MISSING",
        "recent_8k_events": "AVAILABLE" if filings.get("recent_events") else "MISSING",
        "standardized_sec_metrics": "AVAILABLE" if fundamentals and fundamentals.get("metrics") else "MISSING",
        "market_valuation": valuation["status"],
        "country_revenue_and_supply_chain": "MISSING",
    }
    return {"symbol": symbol, "instrument_type": "COMPANY", "families": families,
            "status": "AVAILABLE_WITH_GAPS" if fundamentals else "MISSING",
            "valuation": valuation,
            "missing": [key for key, value in families.items() if value == "MISSING"],
            "limitations": ["SEC facts do not establish geographic revenue or supply-chain exposure"]}


def geopolitical_transmission_coverage(evidence: dict[str, dict], symbols: list[str]) -> dict:
    result = {}
    for symbol in symbols:
        relevant = [item for item in evidence.values()
                    if item.get("kind") in {"policy", "news"} and symbol in item.get("symbols", [])]
        explicit = [item for item in relevant if item.get("transmission")]
        statuses = {}
        for item in relevant:
            status = item.get("event_status", "REPORTED")
            statuses[status] = statuses.get(status, 0) + 1
        result[symbol] = {
            "status": "TRACEABLE_TRANSMISSIONS" if explicit else (
                "SOURCE_ITEMS_REQUIRE_SPECIALIST_MAPPING" if relevant else "MISSING"),
            "source_item_count": len(relevant), "explicit_transmission_count": len(explicit),
            "event_status_counts": statuses,
            "missing": [] if explicit else ["sourced asset-specific transmission mechanism"],
        }
    return {"by_symbol": result,
            "taxonomy": {"event_status": ["ENACTED", "PROPOSED", "SCHEDULED", "REPORTED", "SCENARIO"],
                         "channels": ["REVENUE", "COST", "SUPPLY_CHAIN", "COUNTRY", "CURRENCY",
                                      "REGULATION", "SANCTIONS", "TARIFF", "RATES"]},
            "notice": "A policy/news mention is not itself an established asset-price transmission."}


def parse_etf_profile(payload: object, fund_symbol: str, cutoff: datetime) -> dict:
    """Validate dated, sponsor-reported ETF quality and valuation fields."""
    if not isinstance(payload, dict) or payload.get("symbol", "").upper() != fund_symbol:
        raise ValueError("ETF profile symbol mismatch")
    as_of = date.fromisoformat(str(payload.get("as_of", "")))
    source_url = str(payload.get("source_url", ""))
    if as_of > cutoff.date() or urlparse(source_url).scheme != "https":
        raise ValueError("ETF profile requires a nonfuture date and HTTPS sponsor URL")
    fields = {}
    allowed = {
        "expense_ratio_pct": (0, 10), "pe_ratio": (0.01, 1000),
        "price_to_book_ratio": (0.01, 100), "roe_pct": (-1000, 1000),
        "earnings_growth_pct": (-1000, 1000), "distribution_yield_pct": (0, 100),
        "tracking_difference_pct": (-100, 100), "holdings_count": (1, 100000),
    }
    supplied = payload.get("metrics")
    if not isinstance(supplied, dict) or not supplied:
        raise ValueError("ETF profile needs at least one sponsor-reported metric")
    for key, value in supplied.items():
        if key not in allowed or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Unsupported or nonnumeric ETF profile metric")
        low, high = allowed[key]
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError("ETF profile metric outside conservative bounds")
        if key == "holdings_count" and not isinstance(value, int):
            raise ValueError("ETF holdings_count must be an integer")
        fields[key] = value
    age_days = (cutoff.date() - as_of).days
    return {"symbol": fund_symbol, "as_of": as_of.isoformat(),
            "status": "CURRENT" if age_days <= 31 else "STALE", "age_days": age_days,
            "maximum_age_days": 31, "source_url": source_url, "metrics": fields,
            "methodology_note": str(payload.get("methodology_note", "")).strip() or None,
            "limitations": ["current sponsor-reported aggregate; no historical point-in-time series",
                            "metric methodology may differ across sponsors; no silent cross-fund comparison"]}


def validate_primary_source_config(payload: object) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("version") != "meta-primary-sources-v1":
        raise ValueError("Primary-source config version mismatch")
    rows = payload.get("sources")
    if not isinstance(rows, list) or not rows or len(rows) > 20:
        raise ValueError("Primary-source config needs 1-20 sources")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or not re.fullmatch(r"[a-z][a-z0-9-]{2,63}", row.get("id", ""))
                or row["id"] in seen or row.get("kind") not in PRIMARY_KINDS
                or row.get("format") not in PRIMARY_FORMATS):
            raise ValueError("Invalid primary-source identity, kind, or format")
        parsed = urlparse(str(row.get("url", "")))
        domains = row.get("publisher_domains")
        if (parsed.scheme != "https" or not isinstance(domains, list) or not domains
                or parsed.hostname not in domains or any(not isinstance(d, str) for d in domains)):
            raise ValueError("Primary source URL must match an explicit publisher domain")
        scope = row.get("symbols")
        if not isinstance(scope, list) or not scope or any(
                s != "*" and not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", s) for s in scope):
            raise ValueError("Primary source needs ticker symbols or wildcard scope")
        if "*" in scope and scope != ["*"]:
            raise ValueError("Primary-source wildcard scope cannot be mixed with tickers")
        if not isinstance(row.get("maximum_items", 20), int) or not 1 <= row.get("maximum_items", 20) <= 50:
            raise ValueError("Primary source maximum_items must be 1-50")
        seen.add(row["id"])
    return rows


def primary_source_evidence(raw: bytes, source: dict, cutoff: datetime,
                            watchlist: list[str], retrieved_at: str) -> list[dict]:
    if source["format"] == "federal_register_json":
        return _federal_register_evidence(raw, source, cutoff, watchlist, retrieved_at)
    if source["format"] == "fomc_calendar_html":
        return _fomc_calendar_evidence(raw, source, cutoff, watchlist, retrieved_at)
    return _feed_evidence(raw, source, cutoff, watchlist, retrieved_at)


def _scope(source: dict, watchlist: list[str]) -> list[str]:
    return watchlist if source["symbols"] == ["*"] else [s for s in source["symbols"] if s in watchlist]


def _feed_evidence(raw: bytes, source: dict, cutoff: datetime,
                   watchlist: list[str], retrieved_at: str) -> list[dict]:
    if len(raw) > 20_000_000:
        raise ValueError("Primary feed exceeds bounded response size")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("Malformed primary XML feed") from exc
    entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] in {"item", "entry"}]
    output = []
    for node in entries[:source.get("maximum_items", 20)]:
        values: dict[str, list[str]] = {}
        links = []
        for child in node.iter():
            name = child.tag.rsplit("}", 1)[-1].lower()
            text = " ".join((child.text or "").split())
            if text:
                values.setdefault(name, []).append(text)
            if name == "link" and child.attrib.get("href"):
                links.append(child.attrib["href"])
        title = next(iter(values.get("title", [])), "")
        url = next(iter(values.get("link", [])), links[0] if links else "")
        timestamp = next((v[0] for key in ("pubdate", "published", "updated", "date")
                          if (v := values.get(key))), None)
        if (not title or not url.startswith("https://") or not timestamp
                or urlparse(url).hostname not in source["publisher_domains"]):
            continue
        try:
            published = parsedate_to_datetime(timestamp) if "," in timestamp else _instant(timestamp)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            published = published.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue
        if published > cutoff:
            continue
        summary = next(iter(values.get("description", []) or values.get("summary", []) or values.get("content", [])), "")
        identity = hashlib.sha256(f"{source['id']}\0{url}\0{published.isoformat()}".encode()).hexdigest()[:20]
        output.append(_primary_item(source, identity, title, summary, url, published,
                                    retrieved_at, _scope(source, watchlist)))
    return output


def _federal_register_evidence(raw: bytes, source: dict, cutoff: datetime,
                               watchlist: list[str], retrieved_at: str) -> list[dict]:
    payload = json.loads(raw)
    rows = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Malformed Federal Register response")
    output = []
    for row in rows[:source.get("maximum_items", 20)]:
        try:
            published = datetime.combine(date.fromisoformat(row["publication_date"]), time.min, timezone.utc)
        except (KeyError, TypeError, ValueError):
            continue
        url = str(row.get("html_url", ""))
        title = str(row.get("title", "")).strip()
        if published > cutoff or not title or urlparse(url).hostname != "www.federalregister.gov":
            continue
        agencies = ", ".join(str(a.get("name")) for a in row.get("agencies", []) if isinstance(a, dict) and a.get("name"))
        summary = "\n".join(filter(None, [str(row.get("abstract") or "").strip(), agencies]))
        identity = str(row.get("document_number") or hashlib.sha256(url.encode()).hexdigest()[:20])
        output.append(_primary_item(source, identity, title, summary, url, published,
                                    retrieved_at, _scope(source, watchlist)))
    return output


def _fomc_calendar_evidence(raw: bytes, source: dict, cutoff: datetime,
                            watchlist: list[str], retrieved_at: str) -> list[dict]:
    try:
        page = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("FOMC calendar must be UTF-8 HTML") from exc
    updated_match = re.search(r"Last Update:\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", page)
    if not updated_match:
        raise ValueError("FOMC calendar lacks a publisher update date")
    published = datetime.strptime(updated_match.group(1), "%B %d, %Y").replace(tzinfo=timezone.utc)
    if published > cutoff:
        raise ValueError("FOMC calendar update follows packet cutoff")
    # The Board page marks meeting years and each month/date in named elements.
    # Keep date-only semantics because it does not publish a meeting time here.
    years = list(re.finditer(r"(20\d{2})\s+FOMC Meetings", page))
    output = []
    for index, year_match in enumerate(years):
        year = int(year_match.group(1))
        segment = page[year_match.end(): years[index + 1].start() if index + 1 < len(years) else len(page)]
        pairs = re.findall(
            r'fomc-meeting__month[^>]*>(.*?)</div>.*?fomc-meeting__date[^>]*>(.*?)</div>',
            segment, flags=re.IGNORECASE | re.DOTALL)
        for month_text, date_text in pairs:
            month_name = html.unescape(re.sub(r"<[^>]+>", "", month_text)).strip().split("/")[-1]
            cleaned = re.sub(r"[^0-9-]", "", html.unescape(re.sub(r"<[^>]+>", "", date_text)))
            if not cleaned:
                continue
            try:
                end_day = int(cleaned.split("-")[-1])
                scheduled = date(year, datetime.strptime(month_name, "%B").month, end_day)
            except ValueError:
                continue
            if scheduled < cutoff.date() - timedelta(days=31):
                continue
            title = f"FOMC scheduled meeting ending {scheduled.isoformat()}"
            item = _primary_item(source, scheduled.isoformat(), title,
                                 "Official scheduled FOMC meeting; date is tentative until confirmed by the Committee.",
                                 source["url"], published, retrieved_at, _scope(source, watchlist))
            item["scheduled_for"] = scheduled.isoformat()
            item["event_status"] = "SCHEDULED"
            item["temporal_role"] = "ANNOUNCED_FUTURE_OR_RECENT_EVENT_DATE;TIME_UNSPECIFIED"
            output.append(item)
    return output[:source.get("maximum_items", 20)]


def _primary_item(source: dict, identity: str, title: str, summary: str, url: str,
                  published: datetime, retrieved_at: str, symbols: list[str]) -> dict:
    evidence_kind = "policy" if source["kind"] in {"policy_event", "policy_release", "sector_release"} else "news"
    return {"id": f"primary-{source['id']}-{identity}", "kind": evidence_kind,
            "primary_kind": source["kind"], "publisher": source.get("publisher"),
            "symbols": symbols, "url": url, "published_at": published.isoformat(),
            "retrieved_at": retrieved_at, "title": title, "text": (title + "\n" + summary)[:16000],
            "event_status": "REPORTED",
            "temporal_role": "PUBLISHED_RELEASE_OR_ANNOUNCEMENT",
            "verification": "PUBLISHER_FEED_OR_GOVERNMENT_API;TIMESTAMP_CUTOFF;CONTENT_HASH_PARENT"}


def _sec_acceptance(value: str) -> datetime:
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        try:
            parsed = datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as error:
            raise ValueError("Invalid SEC acceptance timestamp") from error
    return parsed.replace(tzinfo=timezone.utc)


def _end_of_day(value: str) -> datetime:
    try:
        return datetime.combine(date.fromisoformat(str(value)), time.max, timezone.utc)
    except ValueError as error:
        raise ValueError("Invalid SEC filing date") from error
