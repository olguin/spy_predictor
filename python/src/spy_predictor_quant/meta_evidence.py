"""Validated current fundamentals and ETF exposure evidence for META analysis."""
from __future__ import annotations

import csv
from datetime import date, datetime, time, timezone
import io
import json
import math
import re
from typing import Any

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
