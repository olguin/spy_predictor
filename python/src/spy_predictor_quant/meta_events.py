"""Dated event identity and verified exposure paths, without sentiment votes."""
from __future__ import annotations

from difflib import SequenceMatcher
import re

from spy_predictor_quant.meta_analysis import digest
from spy_predictor_quant.meta_contracts import finite, instant


def cluster_news(evidence: dict, cutoff: str) -> dict:
    at = instant(cutoff)
    eligible, excluded = [], []
    for identity, item in evidence.items():
        if item.get("kind") != "news":
            continue
        try:
            published, seen = instant(item["published_at"]), instant(item["retrieved_at"])
            updated = instant(item.get("updated_at", item["published_at"]))
            if not published <= seen <= at or updated > at or updated < published:
                raise ValueError("ineligible event timing")
        except (KeyError, ValueError, AttributeError, TypeError):
            excluded.append({"evidence_id": identity, "reason": "UNKNOWN_OR_INELIGIBLE_AVAILABILITY"})
            continue
        normalized = re.sub(r"\W+", " ", item.get("text", "").lower()).strip()
        if not normalized or not item.get("symbols"):
            excluded.append({"evidence_id": identity, "reason": "MISSING_ENTITY_OR_TEXT"})
            continue
        eligible.append((published, identity, item, normalized))
    clusters = []
    for published, identity, item, normalized in sorted(eligible):
        match = None
        for cluster in clusters:
            if cluster["entities"] != sorted(set(item["symbols"])):
                continue
            within_window = abs((published - instant(cluster["first_published_at"])).total_seconds()) <= 172800
            explicit = item.get("event_key") and item.get("event_key") == cluster["event_key"]
            similar = SequenceMatcher(None, normalized, cluster["normalized_text"]).ratio() >= .9
            if explicit or (within_window and similar):
                match = cluster
                break
        if match is None:
            match = {"event_id": "event-" + digest({"first_evidence_id": identity})[:24],
                     "event_key": item.get("event_key"), "entities": sorted(set(item["symbols"])),
                     "normalized_text": normalized, "first_published_at": item["published_at"],
                     "first_available_at": item["retrieved_at"], "evidence_ids": [],
                     "versions": [], "independent_source_ids": [],
                     "extraction_status": "CLUSTERED_SOURCE_TEXT_REQUIRES_FACTUAL_REVIEW",
                     "surprise": None, "surprise_status": "QUALIFIED_EXPECTATION_NOT_SUPPLIED",
                     "transmission": "UNKNOWN_UNTIL_VERIFIED_EXPOSURE_PATH",
                     "predictive_status": "UNTESTED"}
            clusters.append(match)
        match["evidence_ids"].append(identity)
        match["versions"].append({"evidence_id": identity, "published_at": item["published_at"],
                                  "updated_at": item.get("updated_at"), "available_at": item["retrieved_at"]})
        if instant(item["retrieved_at"]) < instant(match["first_available_at"]):
            match["first_available_at"] = item["retrieved_at"]
        # A publisher/domain is not proof of independence from a wire source.
        source = item.get("verified_independent_source_id")
        if source and source not in match["independent_source_ids"]:
            match["independent_source_ids"].append(source)
    for cluster in clusters:
        cluster.pop("normalized_text")
        cluster["independent_source_count"] = len(cluster["independent_source_ids"]) or None
    return {"schema_version": "meta-event-clusters-v1", "cutoff": cutoff,
            "clusters": clusters, "excluded": excluded,
            "method": "explicit entity/event key or 0.9 text similarity inside 48 hours; review required",
            "notice": "Event identity reduces duplicate evidence; it does not establish factual validity or return predictiveness."}


def verified_exposure_paths(edges: list[dict], source: str, target: str, cutoff: str,
                            evidence: dict, max_hops: int = 3) -> dict:
    at = instant(cutoff)
    qualified = []
    for edge in edges:
        try:
            if (edge.get("status") != "VERIFIED" or not edge.get("evidence_ids")
                    or not set(edge["evidence_ids"]) <= evidence.keys()
                    or not instant(edge["available_at"]) <= at
                    or not instant(edge["valid_from"]) <= at
                    or (edge.get("valid_until") and at >= instant(edge["valid_until"]))):
                continue
            if not finite(edge.get("confidence")) or not 0 <= edge["confidence"] <= 1:
                continue
            for key in edge["evidence_ids"]:
                item = evidence[key]
                if not instant(item["published_at"]) <= instant(item["retrieved_at"]) <= at:
                    raise ValueError("Exposure provenance is unavailable")
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        qualified.append(edge)
    paths = []

    def visit(entity, path, visited):
        if entity == target and path:
            paths.append(path)
        if len(path) >= max_hops:
            return
        for edge in qualified:
            if edge["from"] == entity and edge["to"] not in visited:
                visit(edge["to"], path + [edge], visited | {edge["to"]})

    visit(source, [], {source})
    return {"status": "VERIFIED_PATH" if paths else "UNKNOWN_EXPOSURE", "paths": paths,
            "notice": "Missing exposure is unknown, not zero. Confidence is an evidence annotation, not a return probability."}


def reaction_feature(before: dict, after: dict, benchmark_before: dict, benchmark_after: dict,
                     prediction_origin: str) -> dict:
    points = (before, after, benchmark_before, benchmark_after)
    if any(not finite(row.get("price")) or row["price"] <= 0 for row in points):
        raise ValueError("Reaction requires positive qualified prices")
    if (before["timestamp"] != benchmark_before["timestamp"] or after["timestamp"] != benchmark_after["timestamp"]
            or instant(before["timestamp"]) >= instant(after["timestamp"])
            or any(not instant(row["timestamp"]) <= instant(row["available_at"]) <= instant(prediction_origin)
                   for row in points)):
        raise ValueError("Reaction window must finish and be available before the prediction origin")
    value = (after["price"] / before["price"] - 1) - (benchmark_after["price"] / benchmark_before["price"] - 1)
    return {"status": "OBSERVED_ASSOCIATION", "market_adjusted_return": value,
            "window_start": before["timestamp"], "window_end": after["timestamp"],
            "prediction_origin": prediction_origin, "priced_in_degree": "UNKNOWN",
            "notice": "Observed reaction is not evidence that information is fully priced in."}
