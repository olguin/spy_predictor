"""Bounded, receipted source acquisition and source-specific vintage adapters.

No purchases, trading, inferred release times, or silent feed substitution.
Historical prices remain revised-price diagnostics until vintage evidence exists.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from spy_predictor_quant.market_archive import file_sha256, write_json_exclusive, write_bytes_exclusive
from spy_predictor_quant.meta_analysis import digest
from spy_predictor_quant.meta_contracts import finite, instant
from spy_predictor_quant.meta_research_data import append_observation, validate_observation


def next_day(day: str) -> str:
    """A date-only vintage is usable after that whole US Eastern calendar day."""
    return datetime.combine(date.fromisoformat(day) + timedelta(days=1), datetime.min.time(),
                            ZoneInfo("America/New_York")).astimezone(timezone.utc).isoformat()


def reconstructed(*, entity: str, metric: str, value: float, units: str, effective: str,
                  published: str, available: str, captured: str, source_hash: str,
                  kind: str, locator: str, revision: str, start=None, end=None) -> dict:
    row = {"schema_version": "meta-pit-observation-v2", "availability_lane": "HISTORICAL_RECONSTRUCTION",
           "entity": entity, "metric": metric, "value": value, "units": units,
           "effective_at": effective, "published_at": published, "available_at": available,
           "first_seen_at": captured, "captured_at": captured, "source_hash": source_hash,
           "source_version": kind + "-v1", "revision_id": revision, "quality_flags": [],
           "period_start": start, "period_end": end,
           "availability_evidence": {"kind": kind, "source_hash": source_hash, "locator": locator,
                                     "available_at": available, "precision": "DAY_CONSERVATIVE_NEXT_DAY"}}
    validate_observation(row)
    return row


def alfred_observations(payload: dict, series: str, units: str, captured: str, source_hash: str) -> list[dict]:
    if int(payload.get("output_type", 0)) != 1 or payload.get("units") != "lin":
        raise ValueError("ALFRED requires untransformed real-time-period observations (output_type=1)")
    rows = []
    for item in payload["observations"]:
        if item["value"] == ".":
            continue
        value = float(item["value"])
        if not finite(value):
            raise ValueError("Invalid ALFRED value")
        vintage = item["realtime_start"]
        available = next_day(vintage)
        if instant(available) > instant(captured):
            continue
        rows.append(reconstructed(entity=series, metric="level", value=value, units=units,
            effective=item["date"] + "T00:00:00Z", published=available,
            available=available, captured=captured, source_hash=source_hash, kind="ALFRED_VINTAGE",
            locator=f"observations/date={item['date']}/realtime_start={vintage}", revision=vintage))
    return rows


def sec_observations(bundle: dict, symbol: str, captured: str, source_hash: str,
                     start: str = "2025-08-01") -> tuple[list[dict], dict]:
    """Join accession, never fiscal period, to filing acceptance; preserve amendments.

    Availability is conservatively next Eastern day after acceptance. Historical
    financial facts and publication timestamps share a hashed source bundle.
    """
    facts, submissions = bundle["companyfacts"], bundle["submissions"]
    if int(facts["cik"]) != int(submissions["cik"]):
        raise ValueError("SEC bundle CIK mismatch")
    accepted = {}
    tables = [submissions["filings"]["recent"], *bundle.get("older_submissions", [])]
    for table in tables:
        count = len(table["accessionNumber"])
        if any(len(table.get(k, [])) != count for k in ("acceptanceDateTime", "filingDate", "form")):
            raise ValueError("SEC submission column length mismatch")
        for i, accession in enumerate(table["accessionNumber"]):
            item = {k: table[k][i] for k in ("acceptanceDateTime", "filingDate", "form")}
            if accession in accepted and accepted[accession] != item:
                raise ValueError("Conflicting SEC accession metadata")
            accepted[accession] = item
    rows, missing, conflicts = {}, 0, set()
    for metric, concept in facts.get("facts", {}).get("us-gaap", {}).items():
        if metric not in {"Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "NetIncomeLoss",
                          "OperatingIncomeLoss", "NetCashProvidedByUsedInOperatingActivities", "Assets", "Liabilities"}:
            continue
        for units, items in concept["units"].items():
            for fact in items:
                if fact.get("filed", "") < start:
                    continue
                filing = accepted.get(fact["accn"])
                if not filing or not filing["acceptanceDateTime"]:
                    missing += 1
                    continue
                if filing["filingDate"] != fact["filed"] or filing["form"] != fact["form"]:
                    raise ValueError("SEC fact/filing identity mismatch")
                published = instant(filing["acceptanceDateTime"])
                available = next_day(published.astimezone(ZoneInfo("America/New_York")).date().isoformat())
                if instant(available) > instant(captured):
                    continue
                row = reconstructed(entity=symbol, metric=metric, value=fact["val"], units=units,
                    effective=fact["end"] + "T00:00:00Z", published=published.isoformat(), available=available,
                    captured=captured, source_hash=source_hash, kind="SEC_ACCEPTANCE",
                    locator=f"us-gaap/{metric}/{units}/accn={fact['accn']}/end={fact['end']}", revision=fact["accn"],
                    start=fact.get("start"), end=fact["end"] if fact.get("start") else None)
                row.update(share_basis="AS_FILED_USD" if units == "USD" else "UNQUALIFIED_SHARE_BASIS",
                           filing_form=fact["form"], fiscal_year=fact.get("fy"), fiscal_period=fact.get("fp"))
                if units != "USD":
                    row["quality_flags"].append("UNQUALIFIED_SHARE_BASIS")
                key = (metric, units, fact["accn"], fact.get("start"), fact["end"])
                if key in rows and rows[key]["value"] != row["value"]:
                    conflicts.add(key)
                rows[key] = row
    for key in conflicts:
        rows[key]["quality_flags"].append("CONFLICTING_SAME_ACCESSION_FACT")
    return list(rows.values()), {"unmatched_accession_facts": missing, "conflicting_facts": len(conflicts)}


def fetch(root: Path, name: str, endpoint: str, params: dict, headers: dict | None = None) -> dict:
    """Idempotent receipt; secrets excluded from URLs, errors and persisted metadata."""
    safe = {k: v for k, v in params.items() if k != "api_key"}
    request = {"endpoint": endpoint, "params": safe}
    receipt_path = root / f"{name}.receipt.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt["request"] != request or file_sha256(root / receipt["raw_file"]) != receipt["sha256"]:
            raise ValueError("Source receipt integrity or request mismatch")
        return receipt
    root.mkdir(parents=True, exist_ok=True)
    url = endpoint + ("?" + urlencode(params) if params else "")
    try:
        with urlopen(Request(url, headers=headers or {}), timeout=40) as response:
            raw = response.read()
    except (HTTPError, URLError) as exc:
        # Exception text can contain a FRED API key. Never propagate it.
        raise RuntimeError(f"{name}: source request failed ({getattr(exc, 'code', type(exc).__name__)})") from None
    json.loads(raw)  # Refuse HTML/invalid responses before committing a receipt.
    raw_file = root / f"{name}.json"
    if raw_file.exists():
        if raw_file.read_bytes() != raw:
            raise ValueError("Unreceipted raw source exists; preserve it and use a new capture root")
    else:
        write_bytes_exclusive(raw_file, raw)
    receipt = {"request": request, "raw_file": raw_file.name, "sha256": file_sha256(raw_file),
               "captured_at": datetime.now(timezone.utc).isoformat()}
    write_json_exclusive(receipt_path, receipt)
    return receipt


def capture_sources(root: Path, start: str, end: str) -> dict:
    if date.fromisoformat(start) < date(2025, 8, 1) or date.fromisoformat(start) > date.fromisoformat(end):
        raise ValueError("New pilot is restricted to the post-July-2025 window")
    raw_root = root / "raw"
    results = {}
    def bounded(name, action):
        try:
            results[name] = action()
        except RuntimeError as exc:
            results[name] = {"status": "SOURCE_UNAVAILABLE", "reason": str(exc)}
    key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if key and secret:
        headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        for adjustment in ("raw", "split"):
            def bars(adjustment=adjustment):
                receipts, token = [], None
                for page in range(20):
                    params = {"symbols": "SPY,QQQ,XLK", "timeframe": "1Day", "start": start + "T00:00:00Z",
                              "end": end + "T23:59:59Z", "adjustment": adjustment, "feed": "sip", "limit": 10000, "sort": "asc"}
                    if token:
                        params["page_token"] = token
                    receipt = fetch(raw_root, f"bars-{adjustment}-{page}", "https://data.alpaca.markets/v2/stocks/bars", params, headers)
                    receipts.append(receipt)
                    token = json.loads((raw_root / receipt["raw_file"]).read_text()).get("next_page_token")
                    if not token:
                        return {"status": "CAPTURED_REVISED_HISTORY", "receipts": receipts}
                raise RuntimeError("Daily bars pagination exceeds bounded request budget")
            bounded("bars-" + adjustment, bars)
        def actions():
            receipts, token = [], None
            for page in range(20):
                params = {"symbols": "SPY,QQQ,XLK", "start": start, "end": end, "limit": 1000, "sort": "asc", "data_quality": "all"}
                if token:
                    params["page_token"] = token
                receipt = fetch(raw_root, f"actions-{page}", "https://data.alpaca.markets/v1/corporate-actions", params, headers)
                receipts.append(receipt)
                token = json.loads((raw_root / receipt["raw_file"]).read_text()).get("next_page_token")
                if not token:
                    return {"status": "CAPTURED_AVAILABILITY_NOT_GUARANTEED", "receipts": receipts}
            raise RuntimeError("Corporate actions pagination exceeds bounded request budget")
        bounded("corporate_actions", actions)
    else:
        results["prices"] = {"status": "MISSING_CREDENTIALS"}
    fred_key = os.environ.get("FRED_API_KEY")
    for series, units in (("CPIAUCSL", "index"), ("UNRATE", "percent")):
        def macro(series=series, units=units):
            if not fred_key:
                return {"status": "MISSING_CREDENTIALS"}
            receipt = fetch(raw_root, f"alfred-{series}", "https://api.stlouisfed.org/fred/series/observations",
                {"api_key": fred_key, "series_id": series, "file_type": "json", "output_type": 1,
                 "units": "lin", "observation_start": start, "observation_end": end,
                 "realtime_start": start, "realtime_end": end, "limit": 100000})
            payload = json.loads((raw_root / receipt["raw_file"]).read_text())
            if int(payload["count"]) != len(payload["observations"]):
                raise RuntimeError("ALFRED pagination required; refusing partial history")
            rows = alfred_observations(payload, series, units, receipt["captured_at"], receipt["sha256"])
            for row in rows:
                append_observation(root, row)
            return {"status": "RECONSTRUCTED_WITH_VINTAGE_DATES", "records": len(rows), "receipt": receipt}
        bounded(series, macro)
    user_agent = os.environ.get("SEC_USER_AGENT")
    def sec():
        if not user_agent:
            return {"status": "MISSING_SEC_USER_AGENT"}
        receipts, payloads = [], {}
        for name, endpoint in (("submissions", "https://data.sec.gov/submissions/CIK0000320193.json"),
                               ("companyfacts", "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json")):
            receipt = fetch(raw_root, "sec-AAPL-" + name, endpoint, {}, {"User-Agent": user_agent})
            receipts.append(receipt)
            payloads[name] = json.loads((raw_root / receipt["raw_file"]).read_text())
            time.sleep(.15)
        payloads["older_submissions"] = []
        relevant = [item for item in payloads["submissions"]["filings"].get("files", []) if item["filingTo"] >= start and item["filingFrom"] <= end]
        if len(relevant) > 10:
            raise RuntimeError("SEC submission history exceeds bounded request budget")
        for item in relevant:
            filename = item["name"]
            if "/" in filename or not filename.startswith("CIK0000320193-submissions-"):
                raise ValueError("Invalid SEC history filename")
            receipt = fetch(raw_root, "sec-AAPL-" + filename[:-5], "https://data.sec.gov/submissions/" + filename,
                            {}, {"User-Agent": user_agent})
            receipts.append(receipt)
            payloads["older_submissions"].append(json.loads((raw_root / receipt["raw_file"]).read_text()))
            time.sleep(.15)
        bundle_path = raw_root / "sec-AAPL-bundle.json"
        if not bundle_path.exists():
            write_json_exclusive(bundle_path, payloads)
        elif json.loads(bundle_path.read_text()) != payloads:
            raise ValueError("SEC bundle integrity mismatch")
        captured = max(r["captured_at"] for r in receipts)
        rows, audit = sec_observations(payloads, "AAPL", captured, file_sha256(bundle_path), start)
        for row in rows:
            append_observation(root, row)
        return {"status": "RECONSTRUCTED_WITH_ACCESSION_ACCEPTANCE", "records": len(rows), **audit,
                "source_hash": file_sha256(bundle_path), "captured_at": captured}
    bounded("SEC-AAPL", sec)
    results["optional_sources"] = {name: {"status": "NOT_REQUIRED_BY_QUANT_PILOT", "history_qualification": "MISSING",
        "reason": reason} for name, reason in {
            "news": "Current news is available to live capture; historical first-seen and correction histories are not certified.",
            "consensus": "No timestamped historical expectation dataset configured; surprise features remain missing.",
            "etf_holdings": "Current manual holdings cannot reconstruct historical index membership or exposures.",
            "broad_stock_universe": "Fixed ETF case study cannot qualify historically defined stocks and delistings."}.items()}
    report = {"schema_version": "meta-source-qualification-v1", "start": start, "end": end, "sources": results,
              "license_status": "LOCAL_RESEARCH_ACCESS_ONLY_REDISTRIBUTION_NOT_QUALIFIED",
              "price_availability": "REVISED_HISTORY_NOT_CERTIFIED_POINT_IN_TIME"}
    report_path = root / ("qualification-" + digest(report)[:16] + ".json")
    if not report_path.exists():
        write_json_exclusive(report_path, report)
    return {"path": str(report_path), "sources": {name: row.get("status") for name, row in results.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--start", default="2025-08-01")
    parser.add_argument("--end", default="2026-09-15")
    args = parser.parse_args()
    print(json.dumps(capture_sources(args.root, args.start, args.end), indent=2))


if __name__ == "__main__":
    main()
