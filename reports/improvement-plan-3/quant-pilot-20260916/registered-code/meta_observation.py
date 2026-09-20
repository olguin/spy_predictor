"""Immutable prospective records for META quantitative and context forecasts."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path

import exchange_calendars as xcals

from spy_predictor_quant.cycle_workbench import _instant
from spy_predictor_quant.meta_analysis import HORIZONS, digest
from spy_predictor_quant.market_archive import file_sha256, write_json_exclusive

VERSION = "meta-observation-v1"


def _verified(path: Path, hash_field: str) -> dict:
    value = json.loads(path.read_text())
    identity = value.pop(hash_field)
    if digest(value) != identity:
        raise ValueError(f"{hash_field} integrity mismatch")
    value[hash_field] = identity
    return value


def target_sessions(origin: str) -> dict[str, str]:
    day = date.fromisoformat(origin)
    cal = xcals.get_calendar("XNYS")
    if not cal.is_session(day.isoformat()):
        raise ValueError("Forecast origin must be an XNYS session")
    future = cal.sessions_in_range((day+timedelta(days=1)).isoformat(),
                                   (day+timedelta(days=160)).isoformat())
    if len(future) < max(HORIZONS):
        raise ValueError("Unable to resolve forecast target sessions")
    return {str(horizon): future[horizon-1].date().isoformat() for horizon in HORIZONS}


def register(packet_path: Path, output_root: Path, meta_report_path: Path | None = None,
             now: datetime | None = None,
             structured_forecast_path: Path | None = None) -> Path:
    packet = _verified(packet_path, "packet_hash")
    issued_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    report = json.loads(meta_report_path.read_text()) if meta_report_path else None
    if report and report.get("packet_hash") != packet["packet_hash"]:
        raise ValueError("Agent report belongs to a different packet")
    accepted_validations = {
        "SCHEMA_AND_CITATION_MEMBERSHIP_ONLY;SEMANTIC_CLAIMS_REQUIRE_REVIEW",
        "SCHEMA_CLAIM_CITATION_AND_NUMERIC_PATHS;SEMANTIC_CLAIMS_REQUIRE_REVIEW",
        "META_AGENT_V3_HORIZON_DECISIONS_AND_CRITIC_CLAIM_GATES",
        "META_AGENT_V4_OBSERVATIONS_AND_HYPOTHESIS_EDGES",
    }
    if report and report.get("validation") not in accepted_validations:
        raise ValueError("Agent report lacks the runner validation identity")
    structured = _verified(structured_forecast_path, "artifact_hash") if structured_forecast_path else None
    if structured:
        if structured.get("schema_version") not in {"meta-structured-forecast-v1",
                                                     "meta-structured-forecast-v2", "meta-structured-forecast-v3"}:
            raise ValueError("Structured META forecast version mismatch")
        if structured.get("packet_hash") != packet["packet_hash"]:
            raise ValueError("Structured META forecast belongs to a different packet")
        if (not report
                or report.get("validation") not in {
                    "SCHEMA_CLAIM_CITATION_AND_NUMERIC_PATHS;SEMANTIC_CLAIMS_REQUIRE_REVIEW",
                    "META_AGENT_V3_HORIZON_DECISIONS_AND_CRITIC_CLAIM_GATES",
                    "META_AGENT_V4_OBSERVATIONS_AND_HYPOTHESIS_EDGES"}
                or structured.get("agent_report_sha256") != file_sha256(meta_report_path)):
            raise ValueError("Structured META forecast requires its exact agent report")
    symbols = {}
    for symbol in packet["symbols"]:
        instrument = packet["instruments"][symbol]
        scenarios = instrument.get("reference_scenarios", [])
        if instrument.get("status") != "FRESH" or {row.get("trading_days") for row in scenarios} != set(HORIZONS):
            symbols[symbol] = {"status": "NO_FORECAST", "reason": "FRESH_COMPLETE_REFERENCE_REQUIRED"}
            continue
        origin = instrument["price_date"]
        _require_issue_window(origin, _instant(packet["as_of"]), issued_at)
        structured_symbol = structured.get("symbols", {}).get(symbol) if structured else None
        structured_horizons = (structured_symbol.get("horizons", [])
                               if structured_symbol and structured_symbol.get("status") == "EXPERIMENTAL_UNCALIBRATED"
                               else [])
        if structured_horizons and {row.get("trading_days") for row in structured_horizons} != set(HORIZONS):
            raise ValueError("Structured META forecast lacks exact horizon coverage")
        for row in structured_horizons:
            reference = row.get("reference", {})
            if reference and (reference.get("reference_price_basis") != "LATEST_COMPLETED_SESSION_CLOSE"
                    or reference.get("reference_price") != instrument["latest_close"]
                    or reference.get("target_trading_session") != target_sessions(origin)[str(row["trading_days"])]
                    or reference.get("origin_session", origin) != origin):
                raise ValueError("Structured target is incompatible with the completed-close registration lane")
        symbols[symbol] = {"status": "ISSUED", "origin_session": origin,
                           "origin_close": instrument["latest_close"],
                           "target_sessions": target_sessions(origin),
                           "quantitative_reference": scenarios,
                           "structured_meta_forecast": structured_horizons,
                           "context_synthesis": _context_for(report, symbol),
                           "context_status": "RECORDED" if report and _context_for(report, symbol) else "NOT_AVAILABLE"}
    core = {"version": VERSION, "packet_hash": packet["packet_hash"],
            "packet_path": str(packet_path.resolve()), "registered_at": issued_at.isoformat(),
            "information_cutoff": packet["as_of"], "symbols": symbols,
            "agent_report_hash": file_sha256(meta_report_path) if meta_report_path else None,
            "forecast_status": ("QUANT_CONTEXT_AND_STRUCTURED_EXPERIMENTAL" if structured else
                                "QUANT_AND_CONTEXT" if report else "QUANT_ONLY"),
            "calibrated_meta_forecast": None,
            "structured_meta_probability_status": (structured.get("probability_status") if structured else "UNAVAILABLE"),
            "governance": structured.get("governance") if structured else None,
            "evaluation_plan": {"event_scores": ["brier", "log_loss"],
                                "distribution_scores": ["crps", "pinball", "interval_coverage"],
                                "comparison": "common eligible symbol-origin-horizon records",
                                "overlap": "time-block uncertainty required"},
            "notice": "Prospective record of an uncalibrated reference; registration does not qualify predictive skill."}
    core["forecast_hash"] = digest(core)
    output_root.mkdir(parents=True, exist_ok=True)
    origins = [row["origin_session"] for row in symbols.values() if row["status"] == "ISSUED"]
    origin_key = max(origins) if origins else "no-forecast"
    path = output_root/f"{origin_key}-{packet['packet_hash'][:16]}.json"
    write_json_exclusive(path, core)
    return path


def _require_issue_window(origin: str, cutoff: datetime, issued_at: datetime) -> None:
    cal = xcals.get_calendar("XNYS")
    close = cal.session_close(origin).to_pydatetime()
    next_session = cal.next_session(origin)
    next_open = cal.session_open(next_session).to_pydatetime()
    if cutoff < close or not cutoff <= issued_at < next_open:
        raise ValueError("Prospective issue must occur after packet cutoff and before the next XNYS open")


def _context_for(report: dict | None, symbol: str) -> dict | None:
    if not report:
        return None
    synthesis = report.get("results", {}).get("synthesis", {})
    rows = [row for row in synthesis.get("assessments", []) if row.get("symbol") == symbol]
    return rows[0] if len(rows) == 1 else None
