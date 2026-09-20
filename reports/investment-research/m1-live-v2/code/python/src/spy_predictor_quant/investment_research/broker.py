"""No arbitrary URLs, shell, trading, or filesystem tools are exposed to workers."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
import os
import socket
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from spy_predictor_quant.market_archive import utc_now
from .sources import adapter_kind, child_source, discovered_documents, evidence_number, normalized_data


class LimitReached(RuntimeError):
    pass


def consume(state: dict, metric: str, amount: int | float = 1) -> None:
    value = state["usage"][metric] + amount
    if value > state["limits"][metric]:
        raise LimitReached(f"{metric} budget exhausted")
    state["usage"][metric] = value


def remaining_seconds(state: dict) -> float:
    elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(state["started_at"])).total_seconds()
    remaining = state["mandate"]["budgets"]["wall_seconds"] - elapsed
    if remaining <= 0:
        raise LimitReached("wall_seconds budget exhausted")
    return remaining


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirects are not permitted; register the destination as a source")


class Excerpt(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


class Broker:
    def __init__(self, store, state):
        self.store, self.state = store, state

    def record(self, value: dict) -> dict:
        identity = self.store.put("evidence", value)
        if identity not in self.state["evidence_ids"]:
            parent = self.state["manifest_id"]
            self.state["evidence_ids"].append(identity)
            self.state["manifest_id"] = self.store.put("manifests", {
                "parent": parent, "evidence_ids": self.state["evidence_ids"][:], "created_at": utc_now()})
        self.store.save(self.state)
        return {"status": "OK", "evidence_id": identity, **value}

    def call(self, name: str, args: dict) -> dict:
        remaining_seconds(self.state)
        consume(self.state, "tool_calls")
        self.store.save(self.state)
        if name == "discover_sources":
            query = args["query"].lower().split()
            failures = []
            for source in self.state["mandate"]["sources"]:
                if adapter_kind(source) in {"primary_feed", "sec_submissions"}:
                    result = self.read_source(source["source_id"])
                    if result["status"] == "GAP":
                        failures.append({"source_id": source["source_id"], "reason": result["reason"]})
            sources = [*self.state["mandate"]["sources"], *self.state["discovered_sources"].values()]
            ranked = sorted(sources, key=lambda s: -sum(w in (s["title"] + " " + s["kind"]).lower() for w in query))
            return {"status": "OK" if ranked else "GAP", "coverage": "Configured feeds/SEC indexes and discovered same-publisher documents; no general web search",
                    "gaps": failures, "sources": [{**{k: s[k] for k in ("source_id", "title", "publisher", "url", "kind", "published_at")},
                        "read": s["source_id"] in self.state["source_cache"]} for s in ranked[:16]]}
        if name == "inspect_evidence":
            identity = args["evidence_id"]
            if identity not in self.state["evidence_ids"]:
                return {"status": "GAP", "reason": "UNKNOWN_EVIDENCE"}
            return {"status": "OK", "evidence_id": identity, **self.store.get("evidence", identity)}
        if name == "calculate":
            return self.calculate(args)
        if name != "read_source":
            raise ValueError("Tool is not available through this broker")
        return self.read_source(args["source_id"])

    def read_source(self, source_id: str) -> dict:
        sources = [*self.state["mandate"]["sources"], *self.state["discovered_sources"].values()]
        source = next((s for s in sources if s["source_id"] == source_id), None)
        if source is None:
            return {"status": "GAP", "reason": "UNREGISTERED_SOURCE"}
        cached = self.state["source_cache"].get(source["source_id"])
        if cached:
            return {"status": "OK", "evidence_id": cached, **self.store.get("evidence", cached), "cache_hit": True}
        if source_id in self.state["source_failures"]:
            return self.state["source_failures"][source_id]
        consume(self.state, "source_requests")
        self.store.save(self.state)
        try:
            payload = self.fetch(source)
            submissions = next((self.store.get("evidence", identity).get("data")
                for key, identity in self.state["source_cache"].items()
                if any(s["source_id"] == key and adapter_kind(s) == "sec_submissions" for s in sources)), None)
            data = normalized_data(payload, source, self.state["mandate"]["watchlist"][0]["symbol"], submissions)
            text = payload.decode("utf-8", errors="replace")
            parser = Excerpt()
            parser.feed(text if data is None else json.dumps(data))
            excerpt = "\n".join(parser.parts)[:16000]
            if not excerpt.strip():
                return {"status": "GAP", "reason": "EMPTY_DOCUMENT"}
            raw_id = self.store.put("documents", {"source_id": source["source_id"], "text": text})
            result = self.record({"kind": "source", "source_id": source["source_id"], "data": data,
                "parent_evidence_id": source.get("parent_evidence_id"), "adapter": adapter_kind(source),
                "publisher": source["publisher"], "url": source["url"],
                "published_at": source["published_at"], "available_at": source["available_at"],
                "retrieved_at": utc_now(), "content_sha256": hashlib.sha256(payload).hexdigest(),
                "document_id": raw_id, "locator": "normalized text characters 0:16000",
                "excerpt": excerpt, "truncated": len("\n".join(parser.parts)) > 16000,
                "trust": "UNTRUSTED_SOURCE_DATA", "mode": self.state["mandate"]["mode"]})
            self.state["source_cache"][source["source_id"]] = result["evidence_id"]
            for item in discovered_documents(payload, source, self.state["mandate"]["watchlist"][0]["symbol"]):
                child = child_source(source, item, result["evidence_id"])
                if len(self.state["discovered_sources"]) < 60:
                    self.state["discovered_sources"].setdefault(child["source_id"], child)
            self.store.save(self.state)
            return result
        except LimitReached:
            raise
        except (OSError, ValueError) as error:
            # Do not persist exception text: network errors may contain credentials.
            failure = {"status": "GAP", "reason": "SOURCE_UNAVAILABLE", "error_type": type(error).__name__}
            self.state["source_failures"][source_id] = failure
            self.store.save(self.state)
            return failure

    def fetch(self, source: dict) -> bytes:
        mandate = self.state["mandate"]
        maximum = mandate["budgets"]["document_bytes"]
        if mandate["mode"] == "fixture":
            if source["fixture_text"] is None:
                raise ValueError("Fixture source missing")
            data = source["fixture_text"].encode()
            if len(data) > maximum:
                raise ValueError("Document byte budget exhausted")
            consume(self.state, "download_bytes", len(data))
            return data
        if not mandate["network"]["enabled"] or source["fixture_text"] is not None:
            raise ValueError("Live network disabled or fixture contamination")
        url = urlsplit(source["url"] or "")
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.port not in (None, 443):
            raise ValueError("Only registered public HTTPS sources are allowed")
        addresses = socket.getaddrinfo(url.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Nonpublic address refused")
        spacing = mandate["network"]["minimum_spacing_seconds"]
        delay = max(0, spacing - (time.time() - self.state.get("last_request_at", 0)))
        if delay >= remaining_seconds(self.state):
            raise LimitReached("wall_seconds budget exhausted before source request")
        time.sleep(delay)
        self.state["last_request_at"] = time.time()
        self.store.save(self.state)
        user_agent = mandate["network"]["user_agent"]
        if url.hostname in {"data.sec.gov", "www.sec.gov"}:
            user_agent = os.environ.get("SEC_USER_AGENT")
            if not user_agent:
                raise ValueError("SEC identification is not configured")
        request = Request(source["url"], headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=min(15, remaining_seconds(self.state))) as response:
            kind = response.headers.get_content_type()
            if kind not in {"text/html", "text/plain", "application/json", "application/xml", "text/xml", "application/rss+xml", "application/atom+xml"}:
                raise ValueError("Unsupported document type")
            chunks = []
            size = 0
            while size <= maximum:
                # read1 returns after at most one socket read, so a slowly
                # streaming document cannot reset the run deadline indefinitely.
                remaining_seconds(self.state)
                chunk = response.read1(min(8192, maximum + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                consume(self.state, "download_bytes", len(chunk))
                self.store.save(self.state)
            data = b"".join(chunks)
            remaining_seconds(self.state)
        if len(data) > maximum:
            raise ValueError("Document byte budget exhausted")
        return data

    def calculate(self, args: dict) -> dict:
        if not set(args["evidence_ids"]) <= set(self.state["evidence_ids"]):
            raise ValueError("Unknown calculation input evidence")
        references = []
        resolved = {}
        for side in ("left", "right"):
            value = args[side]
            if "#/" in value:
                identity, pointer = value.split("#", 1)
                if identity not in args["evidence_ids"]:
                    raise ValueError("Numeric reference must be listed in input evidence_ids")
                value = evidence_number(self.store.get("evidence", identity), pointer)
                references.append({"side": side, "evidence_id": identity, "pointer": pointer})
            resolved[side] = value
        try:
            with localcontext() as context:
                context.prec = 40
                left, right = Decimal(resolved["left"]), Decimal(resolved["right"])
                if not left.is_finite() or not right.is_finite() or right == 0:
                    raise ValueError("Nonfinite input or zero denominator")
                result = (left / right - 1) * 100 if args["operation"] == "percentage_change" else left / right
        except InvalidOperation:
            raise ValueError("Invalid decimal inputs") from None
        return self.record({"kind": "calculation", "operation": args["operation"],
            "formula": "(left/right-1)*100" if args["operation"] == "percentage_change" else "left/right",
            "inputs": resolved, "input_references": references, "result_decimal": str(result),
            "units": args["units"], "assumptions": args["assumptions"], "input_evidence_ids": args["evidence_ids"],
            "qualification": "Deterministically resolved source fields; formula suitability still requires review" if len(references) == 2 else
                "User/model supplied scenario inputs; source lineage is not a verified numeric extraction",
            "retrieved_at": utc_now()})
