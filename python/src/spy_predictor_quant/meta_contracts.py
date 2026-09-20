"""Fail-closed timing, identity and condition contracts shared by META stages."""
from __future__ import annotations

from datetime import datetime, timezone
import math

import exchange_calendars as xcals


def instant(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp requires an explicit timezone")
    return result.astimezone(timezone.utc)


def finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def rejections(report: dict) -> list[dict]:
    value = report.get("deterministic_claim_rejections", [])
    if isinstance(value, dict):
        return [{**row, "role": role} for role, rows in value.items() for row in rows]
    return value


def quarantined(report: dict, role: str, symbol: str, horizon: int,
                claim_id: str | None = None) -> bool:
    for row in rejections(report):
        ref = row.get("claim_ref")
        if ref:
            if claim_id and ref == f"{role}:{claim_id}":
                return True
            continue
        # Old flattened findings lost the role: conservatively quarantine all
        # roles matching the explicit symbol/horizon instead of guessing one.
        if (row.get("role") in (None, role) and row.get("symbol") in (None, symbol)
                and row.get("trading_days") in (None, horizon)):
            return True
    return False


def require_unique_claims(report: dict) -> None:
    for role, result in report.get("results", {}).items():
        identities = [claim["claim_id"] for row in result.get("assessments", [])
                      for claim in row.get("claims", [])]
        if len(identities) != len(set(identities)):
            raise ValueError(f"Ambiguous claim identity in {role}; IDs must be unique across symbols")


def price_state(value: float | None, observed_at: str | None, cutoff: str,
                publication: str, acquisition_state: str | None,
                max_age_seconds: int = 900) -> dict:
    status, age = "MISSING", None
    if finite(value) and value > 0:
        try:
            observed, at, published = instant(observed_at), instant(cutoff), instant(publication)
            age = (published - observed).total_seconds()
            status = ("INELIGIBLE_TIMESTAMP" if observed > at or published < at else
                      "STALE_AT_PUBLICATION" if age > max_age_seconds else
                      "REAL_TIME" if acquisition_state == "REAL_TIME" else
                      "DELAYED" if acquisition_state == "DELAYED" else "UNQUALIFIED_FEED")
        except (ValueError, TypeError, AttributeError):
            status = "UNKNOWN_TIMESTAMP"
    return {"value": value, "observed_at": observed_at,
            "acquisition_state": acquisition_state, "status": status,
            "age_at_publication_seconds": age,
            "publication_eligible": status == "REAL_TIME"}


def reference_contract(packet: dict, symbol: str, horizon: int,
                       origin_kind: str = "PRIOR_COMPLETED_CLOSE") -> dict:
    from spy_predictor_quant.meta_observation import target_sessions

    instrument = packet["instruments"][symbol]
    cutoff = instant(packet["as_of"])
    cal = xcals.get_calendar("XNYS")
    if origin_kind == "PRIOR_COMPLETED_CLOSE":
        origin = instrument["price_date"]
        observed = cal.session_close(origin).to_pydatetime()
        price = instrument.get("latest_close")
        if observed > cutoff:
            raise ValueError("Reference completed close occurs after information cutoff")
        basis, feed = "LATEST_COMPLETED_SESSION_CLOSE", instrument.get("feed", "UNKNOWN")
        available = instrument.get("available_at")
        evidence = [key for key, row in packet.get("evidence", {}).items()
                    if row.get("kind") in {"alpaca_daily", "ibkr_daily"}
                    and symbol in row.get("symbols", [])]
        warning = "This completed-close forecast is not a profitability estimate for an intraday entry price."
    elif origin_kind == "QUALIFIED_CURRENT_TRADE":
        intraday = packet.get("intraday", {}).get(symbol, {})
        trade = intraday.get("latest_trade") or {}
        price = trade.get("price", trade.get("p"))
        state = price_state(price, trade.get("timestamp"), packet["as_of"], packet["as_of"],
                            intraday.get("evidence_state"))
        if not state["publication_eligible"] or intraday.get("status") != "AVAILABLE":
            raise ValueError("Current-origin forecast requires a qualified current trade")
        observed = instant(trade["timestamp"])
        origin = observed.astimezone(cal.tz).date().isoformat()
        if not cal.is_session(origin) or not (
                cal.session_open(origin).to_pydatetime() <= observed <= cal.session_close(origin).to_pydatetime()):
            raise ValueError("Current trade must be inside a regular XNYS session")
        basis, feed = "QUALIFIED_CURRENT_TRADE", intraday.get("exchange_coverage", "UNKNOWN")
        available = trade.get("available_at")
        if not available or instant(available) > cutoff or instant(available) < observed:
            raise ValueError("Current trade requires qualified source availability")
        evidence = [key for key, row in packet.get("evidence", {}).items()
                    if row.get("kind") == "alpaca_intraday_snapshot" and symbol in row.get("symbols", [])]
        if not evidence or feed == "UNKNOWN":
            raise ValueError("Current trade requires feed and source provenance")
        warning = "Observed trade reference; no executable entry price, fill, spread or fee is assumed."
    else:
        raise ValueError("Unsupported forecast origin")
    if not finite(price) or price <= 0:
        raise ValueError("Reference price must be finite and positive")
    if available and (instant(available) > cutoff or instant(available) < observed):
        raise ValueError("Reference source availability is incompatible with cutoff")
    target = target_sessions(origin)[str(horizon)]
    return {"contract_version": "meta-target-v1", "origin_kind": origin_kind,
            "information_cutoff": packet["as_of"], "source_available_at": available,
            "availability_status": "KNOWN" if available else "UNKNOWN_HISTORICAL_AVAILABILITY",
            "reference_price": price, "reference_price_basis": basis,
            "reference_price_observed_at": observed.isoformat(), "reference_feed": feed,
            "reference_evidence_ids": evidence, "forecast_origin": packet["as_of"],
            "origin_session": origin, "target_trading_session": target,
            "target_timestamp": cal.session_close(target).isoformat(), "session_calendar": "XNYS",
            "return_basis": "PRICE_RETURN", "corporate_action_basis": instrument.get("adjustment", "UNQUALIFIED_UNTIL_VERIFIED"),
            "entry_basis_warning": warning}


def audit_trigger(trigger: dict | None, packet: dict, symbol: str,
                  accepted_evidence: set[str], accepted_numeric_values: list[dict] | None = None) -> dict:
    """Only currently auditable completed-close conditions become future setups."""
    reasons = []
    if not trigger or trigger.get("availability") != "AVAILABLE":
        return {"status": "UNAVAILABLE", "reason_codes": ["NO_AVAILABLE_CONDITION"], "trigger": None}
    level = trigger.get("level")
    if not finite(level) or level <= 0:
        reasons.append("INVALID_LEVEL")
    if trigger.get("units") != "USD":
        reasons.append("UNSUPPORTED_UNITS")
    if trigger.get("field") not in {"completed close", "latest_close"}:
        reasons.append("UNSUPPORTED_FIELD")
    if trigger.get("confirmation_interval") not in {"one completed session", "ONE_COMPLETED_SESSION"}:
        reasons.append("UNSUPPORTED_CONFIRMATION_INTERVAL")
    refs = set(trigger.get("evidence_ids", []))
    if not refs or not refs <= accepted_evidence or not refs <= set(packet.get("evidence", {})):
        reasons.append("UNACCEPTED_PROVENANCE")
    grounded = False
    for numeric in accepted_numeric_values or []:
        pointer = numeric.get("packet_path", "")
        prefix = f"/instruments/{symbol}/"
        if not pointer.startswith(prefix):
            continue
        field = pointer[len(prefix):]
        if not (field in {"latest_close", "sma20", "sma50", "sma200"} or
                (field.startswith("support_resistance_candidates/") and
                 field.rsplit("/", 1)[-1] in {"support_close", "resistance_close"})):
            continue
        try:
            actual = packet
            for part in pointer.split("/")[1:]:
                actual = actual[part.replace("~1", "/").replace("~0", "~")]
            if finite(actual) and finite(level) and actual == numeric["value"] == level:
                grounded = True
        except (KeyError, TypeError):
            continue
    if not grounded:
        reasons.append("UNGROUNDED_PRICE_LEVEL")
    try:
        if instant(trigger["expiry"]) <= instant(packet["as_of"]):
            reasons.append("EXPIRED")
    except (KeyError, ValueError, TypeError, AttributeError):
        reasons.append("UNRESOLVED_EXPIRY")
    comparisons = {"ABOVE": lambda a, b: a > b, "AT_OR_ABOVE": lambda a, b: a >= b,
                   "BELOW": lambda a, b: a < b, "AT_OR_BELOW": lambda a, b: a <= b,
                   "EQUALS": lambda a, b: a == b}
    comparator = comparisons.get(trigger.get("comparison"))
    if comparator is None:
        reasons.append("INVALID_COMPARISON")
    observed = packet.get("instruments", {}).get(symbol, {})
    if not finite(observed.get("latest_close")) or observed.get("status") != "FRESH":
        reasons.append("MISSING_CURRENT_COMPARISON")
    if reasons:
        return {"status": "REJECTED", "reason_codes": reasons, "trigger": None}
    satisfied = comparator(observed["latest_close"], level)
    return {"status": "ALREADY_SATISFIED" if satisfied else "AVAILABLE",
            "reason_codes": ["CONDITION_MET_AT_CUTOFF"] if satisfied else [],
            "observed_value": observed["latest_close"], "observed_session": observed.get("price_date"),
            "trigger": trigger}
