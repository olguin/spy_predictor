"""Bounded adapters over existing primary-feed and SEC parsers.

These describe retrieved current sources, not a qualified historical replay.
Feed metadata grants only same-publisher document discovery, never instructions.
"""
from datetime import datetime, timezone
import json
from urllib.parse import urlsplit

from spy_predictor_quant.market_archive import content_hash, utc_now
from spy_predictor_quant.meta_evidence import primary_source_evidence, recent_filings, company_fundamentals


def adapter_kind(source: dict) -> str:
    url = source.get("url") or ""
    if "/submissions/CIK" in url and urlsplit(url).hostname == "data.sec.gov":
        return "sec_submissions"
    if "/companyfacts/CIK" in url and urlsplit(url).hostname == "data.sec.gov":
        return "sec_companyfacts"
    if url.endswith((".xml", ".rss", ".atom")) or source["source_id"].endswith("-feed"):
        return "primary_feed"
    return "document"


def discovered_documents(raw: bytes, source: dict, symbol: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    kind = adapter_kind(source)
    if kind == "primary_feed":
        config = {"id": source["source_id"], "format": "rss_atom", "maximum_items": 12,
                  "publisher_domains": [urlsplit(source["url"]).hostname], "publisher": source["publisher"],
                  "kind": "policy_release" if source["kind"] == "macro" else "issuer_release", "symbols": [symbol]}
        rows = primary_source_evidence(raw, config, now, [symbol], utc_now())
        return [{"url": r["url"], "title": r["title"], "published_at": r["published_at"]} for r in rows]
    if kind == "sec_submissions":
        filings = recent_filings(json.loads(raw), symbol, now)
        return [{"url": row["url"], "title": f"{symbol} {row['form']} filing accepted {row['accepted_at']}",
                 "published_at": row["accepted_at"]} for row in [*filings["periodic"], *filings["recent_events"]]]
    return []


def normalized_data(raw: bytes, source: dict, symbol: str, submissions: dict | None = None) -> dict | None:
    kind = adapter_kind(source)
    if kind == "sec_submissions":
        payload = json.loads(raw)
        if symbol not in payload.get("tickers", []):
            raise ValueError("SEC ticker/mandate identity mismatch")
        return recent_filings(payload, symbol, datetime.now(timezone.utc))
    if kind == "sec_companyfacts":
        if submissions is None:
            raise ValueError("Read matching SEC submissions before companyfacts")
        # Existing parser validates CIK/accession/period alignment; the new wrapper
        # keeps revision and units and does not turn filing dates into retrieval time.
        return company_fundamentals(json.loads(raw), symbol, datetime.now(timezone.utc), submissions)
    return None


def child_source(parent: dict, item: dict, parent_evidence_id: str) -> dict:
    url = urlsplit(item["url"])
    permitted = {urlsplit(parent["url"]).hostname}
    if adapter_kind(parent) == "sec_submissions":
        permitted.add("www.sec.gov")
    if url.scheme != "https" or url.hostname not in permitted or url.username or url.password or url.port not in (None, 443):
        raise ValueError("Discovered document outside publisher boundary")
    return {"source_id": "discovered-" + content_hash(item["url"])[:20],
            "title": item["title"][:200], "url": item["url"], "publisher": parent["publisher"],
            "published_at": item["published_at"], "available_at": None,
            "fixture_text": None, "kind": parent["kind"], "critical": False,
            "parent_evidence_id": parent_evidence_id}


def evidence_number(evidence: dict, pointer: str):
    value = evidence
    if not pointer.startswith("/"):
        raise ValueError("Numeric input requires an absolute JSON pointer")
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Evidence input is not an observed numeric field")
    return str(value)
