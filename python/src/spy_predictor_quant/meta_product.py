"""Readable, local-only product projections for immutable META artifacts."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse

import exchange_calendars as xcals

from jsonschema import Draft202012Validator

from spy_predictor_quant.market_archive import file_sha256, write_bytes_exclusive, write_json_exclusive
from spy_predictor_quant.meta_analysis import HORIZONS, digest, market_period_at
from spy_predictor_quant.meta_observation import _verified
from spy_predictor_quant.meta_contracts import instant as parse_instant, price_state
from spy_predictor_quant.meta_operations import DEFAULT_POLICY, load_operations_policy
from spy_predictor_quant.meta_outcomes import _aggregate, evaluation_status


ROOT = Path(__file__).resolve().parents[3]
VIEW_SCHEMA = ROOT / "schemas/meta-product-view-v3.schema.json"


def _instant(value: datetime | None = None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None:
        raise ValueError("Product timestamps must include a timezone")
    return result.astimezone(timezone.utc)


def _load_report(path: Path | None, packet_hash: str) -> dict | None:
    if not path:
        return None
    report = json.loads(path.read_text())
    if report.get("packet_hash") != packet_hash:
        raise ValueError("Agent report belongs to a different packet")
    return report


def _load_structured(path: Path | None, packet_hash: str, report_path: Path | None) -> dict | None:
    if not path:
        return None
    structured = _verified(path, "artifact_hash")
    if structured.get("schema_version") not in {"meta-structured-forecast-v1",
                                                 "meta-structured-forecast-v2", "meta-structured-forecast-v3"}:
        raise ValueError("Unexpected structured forecast version")
    if structured.get("packet_hash") != packet_hash:
        raise ValueError("Structured forecast belongs to a different packet")
    if report_path and structured.get("agent_report_sha256") != file_sha256(report_path):
        raise ValueError("Structured forecast does not bind the supplied agent report")
    return structured


def _freshness(packet: dict, report: dict | None, publication: datetime) -> list[dict]:
    rows = []
    calendar = xcals.get_calendar("XNYS")
    recent = calendar.sessions_in_range((publication - timedelta(days=10)).date().isoformat(), publication.date().isoformat())
    completed = [session for session in recent if calendar.session_close(session).to_pydatetime() <= publication]
    latest_completed = completed[-1].date().isoformat() if completed else None
    for symbol in packet["symbols"]:
        item = packet.get("instruments", {}).get(symbol, {})
        daily_status = item.get("status", "MISSING")
        if daily_status == "FRESH" and item.get("price_date") != latest_completed:
            daily_status = "STALE_AT_PUBLICATION"
        rows.append({"family": "price_completed_close", "scope": symbol,
                     "status": "LATEST_COMPLETED_CLOSE" if daily_status == "FRESH" else daily_status,
                     "observed_at": item.get("price_date"),
                     "retrieved_at": None,
                     "coverage": "COMPLETED_DAILY_BAR",
                     "detail": "Daily technical indicators use the latest completed exchange session; this is not a live quote."})
        intraday = packet.get("intraday", {}).get(symbol, {})
        if packet.get("operating_context", {}).get("market_data_mode") == "intraday" or intraday:
            state = intraday.get("evidence_state")
            raw_status = intraday.get("status", "MISSING")
            if raw_status == "AVAILABLE" and state == "REAL_TIME":
                intraday_status = "LIVE_INTRADAY"
            elif raw_status == "PARTIAL_GAPS" and state == "REAL_TIME":
                intraday_status = "LIVE_INTRADAY_PARTIAL"
            elif raw_status in {"AVAILABLE", "PARTIAL_GAPS"} and state == "DELAYED":
                intraday_status = "DELAYED"
            else:
                intraday_status = "MISSING_INTRADAY" if raw_status == "MISSING" else raw_status
            rows.append({"family": "price_intraday", "scope": symbol,
                         "status": intraday_status,
                         "observed_at": intraday.get("session_last_observed_at",
                                                     intraday.get("latest_timestamp")),
                         "retrieved_at": None,
                         "coverage": intraday.get("exchange_coverage"),
                         "detail": (f"Timestamped {state or 'unknown'} intraday context; "
                                    f"raw coverage status {raw_status}. It does not replace the completed-close technical basis.")})
            for value_name, point_name in (("latest_trade", "trade"), ("latest_quote", "quote")):
                point = intraday.get(value_name)
                if point:
                    rows.append({"family": f"price_intraday_{point_name}", "scope": symbol,
                                 "status": intraday_status,
                                 "observed_at": point.get("timestamp"), "retrieved_at": None,
                                 "coverage": intraday.get("exchange_coverage"),
                                 "detail": f"The displayed {point_name} is bound to its own provider timestamp."})
    for series, item in sorted(packet.get("market", {}).items()):
        if series == "current_volatility" or not isinstance(item, dict) or "status" not in item:
            continue
        raw_status = item.get("status", "MISSING")
        display_status = raw_status
        if raw_status == "FRESH":
            display_status = ("LATEST_COMPLETED_CLOSE" if series in
                              {"VIXCLS", "VXVCLS", "vix_term_structure_proxy"}
                              else "LATEST_OFFICIAL_RELEASE")
        rows.append({"family": "market_macro", "scope": series,
                     "status": display_status,
                     "observed_at": item.get("observed_date"), "retrieved_at": None,
                     "coverage": item.get("unit"),
                     "detail": ("Latest completed daily observation; not same-session intraday."
                                if display_status == "LATEST_COMPLETED_CLOSE" else
                                "Latest published official observation; release schedules differ and this is not tick-real-time.")})
    if ("current_volatility" in packet.get("market", {}) or
            packet.get("operating_context", {}).get("market_data_mode") == "intraday"):
        current = packet.get("market", {}).get("current_volatility", {})
        values = current.get("values", {}) if isinstance(current, dict) else {}
        for label in ("VIX", "VIX3M"):
            point = values.get(label, {})
            rows.append({"family": "volatility_intraday", "scope": label,
                         "status": point.get("status", current.get("status", "MISSING_INTRADAY")),
                         "observed_at": point.get("observed_at"), "retrieved_at": None,
                         "coverage": point.get("provider_timeframe"),
                         "detail": (f"Licensed Massive index snapshot ({point.get('ticker', 'not captured')}); "
                                    f"provider: {current.get('provider', 'Massive Indices Snapshot')}.")})
        rows.append({"family": "volatility_intraday", "scope": "VIX/VIX3M",
                     "status": current.get("status", "MISSING_INTRADAY"),
                     "observed_at": current.get("observed_at"), "retrieved_at": None,
                     "coverage": ", ".join(current.get("provider_timeframes", [])) or None,
                     "detail": ("Same-session ratio requires both timestamped index legs. "
                                f"Missing: {', '.join(current.get('missing', [])) or 'none'}; "
                                f"reasons: {json.dumps(current.get('reasons', {}), sort_keys=True)}")})
    for symbol, item in sorted(packet.get("global_market_context", {}).get("market_proxies", {}).items()):
        raw_status = item.get("status", "MISSING")
        rows.append({"family": "market_proxy_completed_close", "scope": symbol,
                     "status": "LATEST_COMPLETED_CLOSE" if raw_status == "FRESH" else raw_status,
                     "observed_at": item.get("price_date"), "retrieved_at": None,
                     "coverage": item.get("context_family"),
                     "detail": "Cross-market ETF proxy based on a completed daily bar; not a current index quote."})
    if "evidence" in packet:
        news = [item for item in packet.get("evidence", {}).values()
                if isinstance(item, dict) and item.get("kind") == "news" and item.get("published_at")]
        cutoff = datetime.fromisoformat(packet["as_of"])
        eligible_news = []
        for item in news:
            try:
                published = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            if published <= cutoff:
                eligible_news.append((published, item))
        latest_news = max((published for published, _ in eligible_news), default=None)
        same_day = sum(published.date() == cutoff.date() for published, _ in eligible_news)
        age_hours = ((cutoff - latest_news).total_seconds() / 3600) if latest_news else None
        news_status = ("CURRENT_NEWS" if same_day else "RECENT_NEWS"
                       if age_hours is not None and age_hours <= 24 else "STALE"
                       if latest_news else "MISSING")
        rows.append({"family": "news", "scope": "requested watchlist",
                     "status": news_status,
                     "observed_at": latest_news.isoformat() if latest_news else None,
                     "retrieved_at": None,
                     "coverage": f"{len(eligible_news)} items; {same_day} published on cutoff UTC date",
                     "detail": "News was evaluated only through the immutable packet cutoff; publication time is distinct from retrieval time."})
    for symbol in packet.get("etfs", []):
        holdings = packet.get("etf_holdings", {}).get(symbol)
        profile = packet.get("etf_sponsor_profiles", {}).get(symbol)
        rows.append({"family": "etf_holdings", "scope": symbol,
                     "status": holdings.get("status", "MISSING") if holdings else "MISSING",
                     "observed_at": (holdings or {}).get("as_of"), "retrieved_at": None,
                     "coverage": (holdings or {}).get("coverage"),
                     "detail": "sponsor holdings; manual input when required"})
        rows.append({"family": "etf_sponsor_profile", "scope": symbol,
                     "status": profile.get("status", "MISSING") if profile else "MISSING",
                     "observed_at": (profile or {}).get("as_of"), "retrieved_at": None,
                     "coverage": None, "detail": "sponsor valuation and quality metrics"})
    for symbol in packet["symbols"]:
        if symbol in packet.get("etfs", []):
            continue
        fundamentals = packet.get("company_fundamentals", {}).get(symbol)
        rows.append({"family": "fundamentals", "scope": symbol,
                     "status": "AVAILABLE" if fundamentals else "MISSING",
                     "observed_at": (fundamentals or {}).get("latest_period"),
                     "retrieved_at": None,
                     "coverage": packet.get("fundamental_coverage", {}).get(symbol),
                     "detail": "normalized issuer evidence"})
    if report:
        failures = report.get("failures", {})
        for role in ("macro_cycle", "technical", "fundamental", "news", "geopolitical", "critic", "synthesis"):
            rows.append({"family": "agent", "scope": role,
                         "status": "FAILED" if role in failures else
                                   "AVAILABLE" if role in report.get("results", {}) else "MISSING",
                         "observed_at": report.get("completed_at"), "retrieved_at": None,
                         "coverage": None, "detail": failures.get(role, "validated structured output")})
    critical_families = {"price_completed_close", "fundamentals"}
    for row in rows:
        observed = row.get("observed_at")
        age = None
        if isinstance(observed, str) and "T" in observed:
            try:
                observed_instant = parse_instant(observed)
                age = (publication - observed_instant).total_seconds()
            except ValueError:
                pass
        if row["family"] == "price_completed_close" and observed:
            try:
                age = (publication - calendar.session_close(observed).to_pydatetime()).total_seconds()
            except ValueError:
                pass
        row["age_at_publication_seconds"] = age
        row["criticality"] = "CRITICAL" if row["family"] in critical_families else "ADVISORY"
        row["action_gate"] = "OPEN"
        intraday_family = row["family"].startswith("price_intraday") or row["family"] == "volatility_intraday"
        if intraday_family and (age is None or age < 0 or (observed and parse_instant(observed) > parse_instant(packet["as_of"]))):
            row["status"] = "UNKNOWN_OR_INELIGIBLE_TIMESTAMP"
            row["action_gate"] = "ADVISORY_ONLY"
        elif intraday_family and age > 900:
            row["status"] = "STALE_AT_PUBLICATION"
            row["action_gate"] = "WAIT" if row["criticality"] == "CRITICAL" else "ADVISORY_ONLY"
            row["detail"] += " It exceeded the 15-minute publication-age bound."
        elif row["status"] in {"MISSING", "MISSING_INTRADAY", "FAILED", "STALE", "STALE_AT_PUBLICATION", "PARTIAL_GAPS"}:
            row["action_gate"] = "WAIT" if row["criticality"] == "CRITICAL" else "ADVISORY_ONLY"
    return rows


def _agent_views(report: dict | None, symbol: str) -> list[dict]:
    if not report:
        return []
    rows = []
    failures = report.get("failures", {})
    for role in ("macro_cycle", "technical", "fundamental", "news", "geopolitical", "critic", "synthesis"):
        assessments = report.get("results", {}).get(role, {}).get("assessments", [])
        assessment = next((row for row in assessments if row.get("symbol") == symbol), None)
        rows.append({"role": role, "status": "FAILED" if role in failures else
                     (assessment or {}).get("status", "MISSING"),
                     "view": (assessment or {}).get("view", "UNKNOWN"),
                     "thesis": (assessment or {}).get("thesis"),
                     "failure": failures.get(role)})
    return rows


def _symbol_view(packet: dict, structured: dict | None, report: dict | None,
                 symbol: str, publication: datetime | None = None, freshness: list[dict] | None = None) -> dict:
    instrument = packet.get("instruments", {}).get(symbol, {})
    structured_symbol = (structured or {}).get("symbols", {}).get(symbol, {})
    structured_rows = {int(row["trading_days"]): row
                       for row in structured_symbol.get("horizons", [])}
    references = {int(row["trading_days"]): row
                  for row in instrument.get("reference_scenarios", [])}
    horizons = []
    for horizon in HORIZONS:
        row = structured_rows.get(horizon)
        if row and row.get("status") == "EXPERIMENTAL_UNCALIBRATED":
            scenario = row["distribution"]
            recommendation = row["recommendation"]
            action = recommendation.get("action_now", recommendation.get("action"))
            horizons.append({"trading_days": horizon, "status": row["status"],
                             "action": action,
                             "new_position_action": recommendation.get("new_position_action", action),
                             "existing_position_action": recommendation.get("existing_position_action", "REVIEW"),
                             "probability_price_up": scenario["probability_price_up"],
                             "probabilities": scenario["probabilities"],
                             "event_definitions": scenario.get("event_definitions", {}),
                             "expected_return_pct": scenario["expected_simple_return_pct"],
                             "median_return_pct": scenario.get("median_simple_return_pct"),
                             "price_interval_80": [scenario["price_quantiles"]["0.1"],
                                                   scenario["price_quantiles"]["0.9"]],
                             "reference": row.get("reference", {
                                 "reference_price": instrument.get("latest_close"),
                                 "reference_price_basis": "LATEST_COMPLETED_SESSION_CLOSE",
                                 "reference_price_observed_at": instrument.get("price_date"),
                                 "forecast_origin": (structured or {}).get("created_at"),
                                 "target_trading_session": None,
                                 "entry_basis_warning": "Legacy frozen forecast."}),
                             "coverage": row.get("coverage"),
                             "model_usage": row.get("model_usage", "LEGACY_UNKNOWN"),
                             "decision_reason": recommendation.get("decision_reason", "LEGACY_UNSPECIFIED"),
                             "heuristic_inputs": sorted(row.get("quant_signal", {}).get("features", []),
                                                        key=lambda item: abs(item["value"]), reverse=True)[:3],
                             "reason_codes": recommendation.get("reason_codes", []),
                             "disagreement": row["context_signal"]["disagreement_range"],
                             "supported_roles": row["context_signal"].get("accepted_roles",
                                 row["context_signal"].get("supported_roles", 0)),
                             "conditional_trigger": recommendation.get("conditional_trigger"),
                             "invalidation_trigger": recommendation.get("invalidation_trigger"),
                             "wait_for": recommendation.get("wait_for", []),
                             "next_review": recommendation.get("next_review"),
                             "critical_gaps": recommendation.get("critical_gaps", []),
                             "advisory_gaps": recommendation.get("advisory_gaps", []),
                             "catalysts": recommendation.get("catalysts_or_supporting_conditions", []),
                             "counter_case": recommendation.get("counter_case", []),
                             "review_triggers": recommendation.get("review_triggers", []),
                             "missing_inputs": recommendation.get("missing_inputs", []),
                             "ablations": {name: value["probability_price_up"]
                                           for name, value in row.get("ablations", {}).items()}})
        elif horizon in references:
            scenario = references[horizon]
            horizons.append({"trading_days": horizon, "status": scenario.get("status", "UNAVAILABLE"),
                             "action": "UNAVAILABLE", "probability_price_up": scenario["probability_price_up"],
                             "probabilities": scenario["probabilities"],
                             "event_definitions": {},
                             "expected_return_pct": scenario.get("expected_simple_return_pct"),
                             "median_return_pct": None,
                             "price_interval_80": [scenario["price_quantiles"]["0.1"],
                                                   scenario["price_quantiles"]["0.9"]],
                             "reference": {"reference_price": instrument.get("latest_close"),
                                           "reference_price_basis": "LATEST_COMPLETED_SESSION_CLOSE",
                                           "reference_price_observed_at": instrument.get("price_date"),
                                           "forecast_origin": None, "target_trading_session": None,
                                           "entry_basis_warning": "No structured META forecast."},
                             "coverage": None, "new_position_action": "UNAVAILABLE",
                             "existing_position_action": "UNAVAILABLE", "disagreement": None,
                             "supported_roles": 0, "catalysts": [], "counter_case": [],
                             "conditional_trigger": None, "invalidation_trigger": None,
                             "wait_for": ["structured META forecast"], "next_review": None,
                             "critical_gaps": ["structured META forecast"], "advisory_gaps": [],
                             "review_triggers": [], "missing_inputs": ["structured META forecast"],
                             "ablations": {}})
        else:
            horizons.append({"trading_days": horizon, "status": "NO_FORECAST",
                             "action": "WAIT", "new_position_action": "WAIT",
                             "existing_position_action": "REVIEW_RISK", "probability_price_up": None,
                             "probabilities": None, "expected_return_pct": None,
                             "event_definitions": {}, "median_return_pct": None,
                             "price_interval_80": None,
                             "reference": {"reference_price": None, "reference_price_basis": "UNAVAILABLE",
                                           "reference_price_observed_at": None, "forecast_origin": None,
                                           "target_trading_session": None, "entry_basis_warning": "No forecast."},
                             "coverage": None, "disagreement": None, "supported_roles": 0,
                             "conditional_trigger": None, "invalidation_trigger": None,
                             "wait_for": ["fresh price and volatility history"], "next_review": None,
                             "critical_gaps": ["fresh price and volatility history"], "advisory_gaps": [],
                             "catalysts": [], "counter_case": [], "review_triggers": [],
                             "missing_inputs": ["fresh price and volatility history"], "ablations": {}})
    intraday = packet.get("intraday", {}).get(symbol, {})
    published = (publication or datetime.fromisoformat(packet["as_of"])).isoformat()
    values = {}
    values["session_last"] = price_state(intraday.get("session_last"),
        intraday.get("session_last_observed_at", intraday.get("latest_timestamp")),
        packet["as_of"], published, intraday.get("evidence_state"))
    for name in ("latest_trade", "latest_quote"):
        point = intraday.get(name) or {}
        if name == "latest_trade":
            values[name] = price_state(point.get("price", point.get("p")), point.get("timestamp"),
                packet["as_of"], published, intraday.get("evidence_state"))
        else:
            for side in ("bid", "ask"):
                values[f"quote_{side}"] = price_state(point.get(side, point.get({"bid": "bp", "ask": "ap"}[side])), point.get("timestamp"),
                    packet["as_of"], published, intraday.get("evidence_state"))
    current_eligible = values["latest_trade"]["publication_eligible"] and intraday.get("status") == "AVAILABLE"
    daily_state = next((item for item in (freshness if freshness is not None else _freshness(packet, None, publication or datetime.fromisoformat(packet["as_of"])))
                        if item["family"] == "price_completed_close" and item["scope"] == symbol), {})
    current_eligible = current_eligible and daily_state.get("status") == "LATEST_COMPLETED_CLOSE"
    for row in horizons:
        eligible = current_eligible
        reasons = [] if eligible else ["WAIT_DATA", "QUALIFIED_CURRENT_TRADE_REQUIRED"]
        trigger = row.get("conditional_trigger")
        if trigger:
            try:
                if parse_instant(trigger["expiry"]) <= parse_instant(published):
                    eligible = False
                    reasons.append("CONDITION_EXPIRED_AT_PUBLICATION")
            except (KeyError, ValueError, AttributeError, TypeError):
                eligible = False
                reasons.append("UNQUALIFIED_CONDITION_EXPIRY")
        if market_period_at(parse_instant(published)) != "REGULAR":
            eligible = False
            reasons.append("OUTSIDE_REGULAR_SESSION")
        row["action_overlay"] = {
            "evaluated_at": published, "cutoff_action": row["action"],
            "current_entry_eligible": eligible,
            "current_entry_action": row["new_position_action"] if eligible else "WAIT",
            "reason_codes": reasons,
            "notice": "Freshness overlay; original cutoff forecast remains immutable. An eligible observation is not an executable fill.",
        }
    return {"symbol": symbol, "status": structured_symbol.get("status", instrument.get("status", "MISSING")),
            "price": instrument.get("latest_close"), "price_date": instrument.get("price_date"),
            "price_state": daily_state,
            "intraday": {"status": values["session_last"]["status"],
                         "evidence_state": values["session_last"]["status"],
                         "acquisition_status": intraday.get("status", "MISSING"),
                         "value_states": values,
                         "age_at_publication_seconds": values["session_last"]["age_at_publication_seconds"],
                         "publication_eligible": values["session_last"]["publication_eligible"],
                         "coverage": intraday.get("exchange_coverage"),
                         "latest_timestamp": intraday.get("session_last_observed_at",
                                                          intraday.get("latest_timestamp")),
                         "latest_observation_timestamp": intraday.get("latest_observation_timestamp",
                                                                      intraday.get("latest_timestamp")),
                         "latest_trade": intraday.get("latest_trade"),
                         "latest_quote": intraday.get("latest_quote"),
                         "session_last": intraday.get("session_last")},
            "technical": {key: instrument.get(key) for key in
                          ("return5_pct", "return21_pct", "return63_pct", "realized_vol63_pct", "rsi14_simple",
                           "price_to_sma20", "price_to_sma50", "price_to_sma200")},
            "horizons": horizons, "agent_views": _agent_views(report, symbol)}


def _evaluation(forecast_root: Path | None, outcome_root: Path | None,
                score_root: Path | None, now: datetime) -> dict | None:
    if not forecast_root or not forecast_root.exists():
        return None
    outcome_root = outcome_root or ROOT / "datasets/meta-observation/outcomes"
    score_root = score_root or ROOT / "datasets/meta-observation/scores"
    status = evaluation_status(forecast_root, outcome_root, score_root, now)
    aggregate = _aggregate(score_root)
    return {"status": {"as_of": status["asOf"], "counts": status["counts"]},
            "aggregate": aggregate}


def _market_summary(packet: dict) -> list[dict]:
    market = packet.get("market", {})
    current = market.get("current_volatility", {})
    current_values = current.get("values", {})
    definitions = (
        ("current_vix", "Current VIX", "Same-session licensed index snapshot; higher values indicate more priced uncertainty", current_values.get("VIX", {}), "value", "%", current.get("status", "MISSING_INTRADAY")),
        ("current_vix_vix3m", "Current VIX / VIX3M", "Same-session ratio; above 1 means front volatility exceeds three-month volatility", current, "vix_vix3m_ratio", "", current.get("status", "MISSING_INTRADAY")),
        ("VIXCLS", "VIX completed close", "Fallback completed daily observation; not the current intraday index", market.get("VIXCLS", {}), "value", "%", None),
        ("vix_term_structure_proxy", "VIX / VIX3M completed close", "Fallback completed daily ratio on the latest common observation date", market.get("vix_term_structure_proxy", {}), "value", "", None),
        ("DFF", "Fed effective rate", "Effective federal funds rate", "value", "%"),
        ("T10Y2Y", "10Y–2Y curve", "Positive is an upward-sloping Treasury curve", "value", " pp"),
        ("NFCI", "Financial conditions", "Negative values indicate looser-than-average financial conditions", "value", ""),
        ("CPIAUCSL", "CPI year over year", "Trailing year change in the CPI index", "yoy_pct", "%"),
    )
    rows = []
    for definition in definitions:
        if len(definition) == 5:
            key, label, meaning, field, suffix = definition
            source, forced_status = market.get(key, {}), None
        else:
            key, label, meaning, source, field, suffix, forced_status = definition
        value = source.get(field) if isinstance(source, dict) else None
        status = forced_status or (source.get("status", "MISSING") if isinstance(source, dict) else "MISSING")
        if status == "FRESH":
            status = ("LATEST_COMPLETED_CLOSE" if key in {"VIXCLS", "vix_term_structure_proxy"}
                      else "LATEST_OFFICIAL_RELEASE")
        rows.append({"key": key, "label": label, "value": value,
                     "display": "—" if value is None else f"{value:.2f}{suffix}",
                     "status": status,
                     "observed_at": (source.get("observed_at") or source.get("observed_date"))
                                    if isinstance(source, dict) else None,
                     "meaning": meaning})
    return rows


def _deterministic_decision_rows(structured: dict | None, explanation: str) -> list[dict]:
    rows = []
    for symbol, value in (structured or {}).get("symbols", {}).items():
        for index, item in enumerate(value.get("horizons", [])):
            if item.get("status") != "EXPERIMENTAL_UNCALIBRATED":
                continue
            recommendation = item["recommendation"]
            action = recommendation.get("action_now", recommendation.get("action", "WAIT"))
            rows.append({"symbol": symbol, "trading_days": item["trading_days"],
                         "action_now": action,
                         "new_position_action": recommendation.get("new_position_action", action),
                         "existing_position_action": recommendation.get("existing_position_action", "REVIEW_RISK"),
                         "probability_price_up": item["distribution"]["probability_price_up"],
                         "forecast_ref": f"/symbols/{symbol}/horizons/{index if structured.get('schema_version') == 'meta-structured-forecast-v3' else item['trading_days']}",
                         "explanation": explanation,
                         "what_changes_action": "; ".join(recommendation.get("wait_for", [])) or "A new immutable analysis",
                         "what_could_go_wrong": "The distribution is experimental and uncalibrated."})
    return rows


def _golden_view(report: dict | None, structured: dict | None) -> dict:
    golden = ((report or {}).get("results", {}).get("synthesis", {})
              .get("golden_conclusions"))
    if golden:
        if "overall_conclusion" not in golden:  # Frozen v1 report projection.
            priorities = golden.get("cross_symbol_priorities", [])
            golden = {
                "overall_conclusion": golden.get("executive_summary", "Legacy synthesis"),
                "market_regime": golden.get("market_regime", {}).get("summary", "Unknown"),
                "critical_findings": [row.get("conclusion", "") for row in golden.get("critical_conclusions", [])][:5],
                "decision_rows": _deterministic_decision_rows(
                    structured, "Legacy Astra synthesis predates the v2 numerical decision mandate."),
                "research_priorities": [{"symbol": row["symbol"], "priority": row["rank"],
                    "buy_attractiveness": "UNKNOWN", "rationale": row["rationale"]} for row in priorities],
                "immediate_review_triggers": golden.get("immediate_review_triggers", []),
                "evidence_limitations": [*golden.get("evidence_limitations", []),
                                         "Legacy synthesis predates numerical decision rows."],
                "new_material_contradiction": None,
            }
        expected = _deterministic_decision_rows(structured, "Frozen numerical decision")
        keys = ("symbol", "trading_days", "action_now", "new_position_action", "existing_position_action", "probability_price_up", "forecast_ref")
        if structured and ({tuple(row[key] for key in keys) for row in golden["decision_rows"]} !=
                           {tuple(row[key] for key in keys) for row in expected}
                           or len(golden["decision_rows"]) != len(expected)):
            raise ValueError("Report decisions disagree with the frozen numerical forecast")
        projected = {"status": "AVAILABLE", **golden}
        projected["executive_summary"] = golden["overall_conclusion"]
        projected["market_regime_detail"] = {"summary": golden["market_regime"],
                                              "invalidation": "Reassess at the listed triggers."}
        projected["critical_conclusions"] = [
            {"importance": "CRITICAL", "scopes": ["MARKET"], "horizons": [5, 21, 63],
             "conclusion": value, "invalidation": "Reassess at the listed triggers."}
            for value in golden["critical_findings"]]
        projected["cross_symbol_priorities"] = [
            {"rank": row["priority"], "symbol": row["symbol"],
             "stance": row["buy_attractiveness"], "horizons": [5, 21, 63],
             "rationale": row["rationale"], "conditions": [], "invalidation": []}
            for row in golden["research_priorities"]]
        return projected
    rows = _deterministic_decision_rows(
        structured, "Astra synthesis is unavailable; use the deterministic gate only.")
    return {"status": "UNAVAILABLE", "overall_conclusion": "Astra META synthesis is unavailable.",
            "market_regime": "Unavailable", "critical_findings": [], "decision_rows": rows,
            "research_priorities": [], "immediate_review_triggers": [],
            "evidence_limitations": ["No validated Astra final synthesis was attached."],
            "new_material_contradiction": None,
            "executive_summary": "Astra META synthesis is unavailable for this artifact.",
            "market_regime_detail": {"summary": "Unavailable",
                                     "invalidation": "Run a complete Astra synthesis."},
            "critical_conclusions": [], "cross_symbol_priorities": []}


def build_product_view(packet_path: Path, *, structured_path: Path | None = None,
                       report_path: Path | None = None, mode: str = "ON_DEMAND",
                       now: datetime | None = None, forecast_root: Path | None = None,
                       outcome_root: Path | None = None, score_root: Path | None = None) -> dict:
    generated = _instant(now)
    packet = _verified(packet_path, "packet_hash")
    report = _load_report(report_path, packet["packet_hash"])
    structured = _load_structured(structured_path, packet["packet_hash"], report_path)
    freshness = _freshness(packet, report, generated)
    failures = []
    failures.extend({"stage": "acquisition", "name": key, "detail": str(value)}
                    for key, value in sorted(packet.get("acquisition_errors", {}).items()))
    failures.extend({"stage": "supplemental_acquisition", "name": key, "detail": str(value)}
                    for key, value in sorted(packet.get("supplemental_acquisition_errors", {}).items()))
    failures.extend({"stage": "agent", "name": key, "detail": str(value)}
                    for key, value in sorted((report or {}).get("failures", {}).items()))
    healthy = {"FRESH", "CURRENT", "AVAILABLE", "COMPLETE", "OK", "REAL_TIME",
               "LATEST_COMPLETED_CLOSE", "LATEST_OFFICIAL_RELEASE", "LIVE_INTRADAY",
               "CURRENT_NEWS", "RECENT_NEWS", "DELAYED"}
    missing = [row for row in freshness if row["status"] not in healthy]
    run_status = "DEGRADED" if failures or missing else "COMPLETE"
    alerts = ([{"severity": "ERROR", "condition": "partial-failures",
                "message": f"{len(failures)} pipeline failures remain visible"}] if failures else [])
    if missing:
        alerts.append({"severity": "WARNING", "condition": "evidence-gaps",
                       "message": f"{len(missing)} evidence rows are missing, stale, failed or partial"})
    probability = (structured or {}).get("probability_status", "UNAVAILABLE")
    cutoff = datetime.fromisoformat(packet["as_of"])
    publication_lag = max(0.0, (generated - cutoff.astimezone(timezone.utc)).total_seconds())
    market_summary = _market_summary(packet)
    for row in market_summary:
        if row["key"] in {"current_vix", "current_vix_vix3m"}:
            scope = "VIX" if row["key"] == "current_vix" else "VIX/VIX3M"
            state = next((item for item in freshness if item["family"] == "volatility_intraday" and item["scope"] == scope), None)
            if state:
                row["acquisition_status"] = row["status"]
                row["status"] = state["status"]
                row["age_at_publication_seconds"] = state["age_at_publication_seconds"]
                row["publication_eligible"] = state["status"] in {"REAL_TIME", "LIVE_INTRADAY"}
    core = {"schema_version": "meta-product-view-v3", "generated_at": generated.isoformat(),
            "publication_lag_seconds": publication_lag,
            "mode": mode, "run_status": run_status, "probability_status": probability,
            "as_of": packet["as_of"], "market_period": market_period_at(datetime.fromisoformat(packet["as_of"])),
            "golden_conclusions": _golden_view(report, structured),
            "market_summary": market_summary,
            "symbols": [_symbol_view(packet, structured, report, symbol, generated, freshness) for symbol in packet["symbols"]],
            "freshness": freshness,
            "failures": failures, "alerts": alerts,
            "provenance": {"packet_path": str(packet_path.resolve()), "packet_hash": packet["packet_hash"],
                           "structured_path": str(structured_path.resolve()) if structured_path else None,
                           "structured_hash": (structured or {}).get("artifact_hash"),
                           "agent_report_path": str(report_path.resolve()) if report_path else None,
                           "agent_report_sha256": file_sha256(report_path) if report_path else None,
                           "cohort_id": (structured or {}).get("governance", {}).get("cohort_id")},
            "evaluation": _evaluation(forecast_root, outcome_root, score_root, generated),
            "notice": "Research support only. This is an immutable snapshot: browser refreshes do not acquire new market data. Probabilities remain experimental and uncalibrated until the prospective cohort passes its frozen qualification and statistical-review gates."}
    core["view_hash"] = digest(core)
    Draft202012Validator(json.loads(VIEW_SCHEMA.read_text())).validate(core)
    return core


def load_product_view(path: Path) -> dict:
    view = json.loads(path.read_text())
    schema = (ROOT / "schemas/meta-product-view-v2.schema.json"
              if view.get("schema_version") == "meta-product-view-v2" else VIEW_SCHEMA)
    Draft202012Validator(json.loads(schema.read_text())).validate(view)
    identity = view.pop("view_hash")
    if digest(view) != identity:
        raise ValueError("Product view integrity mismatch")
    view["view_hash"] = identity
    return view


def _pct(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{100 * value:.{digits}f}%"


def _num(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def render_markdown(view: dict) -> str:
    golden = view["golden_conclusions"]
    lines = ["# META research cockpit", "",
             f"**{view['mode']} · {view['run_status']} · cutoff {view['as_of']} · {view['market_period']}**", "",
             f"Probability status: **{view['probability_status']}**", "", view["notice"], "",
             "## How to read this report", "",
             *[f"**{label}:** {explanation}\n" for label, explanation in READING_GUIDE],
             "## GOLDEN RECOMMENDATIONS / GOLDEN CONCLUSIONS", "",
             f"**META assessment status: {golden['status']}**", "",
             golden["executive_summary"], "",
             "### Market regime", "", golden["market_regime_detail"]["summary"], "",
             f"Invalidation: {golden['market_regime_detail']['invalidation']}", "",
             "### Critical conclusions", ""]
    if golden["critical_conclusions"]:
        for row in golden["critical_conclusions"]:
            lines.append(f"- **{row['importance']} · {', '.join(row['scopes'])} · "
                         f"{', '.join(str(value) for value in row['horizons'])} sessions:** "
                         f"{row['conclusion']} Invalidation: {row['invalidation']}")
    else:
        lines.append("- No validated critical conclusions are available.")
    lines.extend(["", "### Ranked cross-symbol priorities", "",
                  "| Rank | Symbol | Stance | Horizons | Rationale | Conditions / invalidation |",
                  "|---:|---|---|---|---|---|"])
    if golden["cross_symbol_priorities"]:
        for row in sorted(golden["cross_symbol_priorities"], key=lambda value: value["rank"]):
            conditions = "; ".join(row["conditions"]) or "—"
            invalidation = "; ".join(row["invalidation"]) or "—"
            lines.append(f"| {row['rank']} | {row['symbol']} | {row['stance']} | "
                         f"{', '.join(str(value) for value in row['horizons'])} | {row['rationale']} | "
                         f"{conditions} / {invalidation} |")
    else:
        lines.append("| — | — | UNKNOWN | — | Astra synthesis unavailable | — |")
    lines.extend(["", "### Immediate review triggers", ""])
    lines.extend(f"- {value}" for value in golden["immediate_review_triggers"])
    if not golden["immediate_review_triggers"]:
        lines.append("- None available.")
    lines.extend(["", "### Decisive evidence limitations", ""])
    lines.extend(f"- {value}" for value in golden["evidence_limitations"])
    lines.extend(["", "### Frozen decisions at the information cutoff", "",
                  "| Symbol | Horizon | Cutoff action | New / existing | P(terminal gain) | What changes it | What could go wrong |",
                  "|---|---:|---|---|---:|---|---|"])
    for row in sorted(golden["decision_rows"], key=lambda value: (value["symbol"], value["trading_days"])):
        lines.append(f"| {row['symbol']} | {row['trading_days']} | {row['action_now']} | "
                     f"{row['new_position_action']} / {row['existing_position_action']} | "
                     f"{_pct(row['probability_price_up'])} | {row['what_changes_action']} | "
                     f"{row['what_could_go_wrong']} |")
    lines.extend(["", "### Five-symbol horizon board", "",
             "| Symbol | Price | 5 sessions | 21 sessions | 63 sessions | Context roles (5/21/63) / disagreement |",
             "|---|---:|---|---|---|---|"])
    for symbol in view["symbols"]:
        cells = []
        for row in symbol["horizons"]:
            interval = row["price_interval_80"]
            interval_text = f"{_num(interval[0])}–{_num(interval[1])}" if interval else "unavailable"
            cells.append(f"Cutoff: {row['action']} · P↑ {_pct(row['probability_price_up'])} · "
                         f"{row.get('model_usage', 'REFERENCE_ONLY')} · 80% {interval_text} · "
                         f"current entry: {row['action_overlay']['current_entry_action']} "
                         f"{','.join(row['action_overlay']['reason_codes'])}")
        disagreements = [row["disagreement"] for row in symbol["horizons"] if row["disagreement"] is not None]
        coverages = [row["coverage"]["context_roles"] for row in symbol["horizons"] if row["coverage"]]
        quality = (" · ".join(f"{row['covered']}/{row['total']}" for row in coverages) + " roles"
                   if coverages else "—")
        disagreement = _num(max(disagreements)) if disagreements else "—"
        lines.append(f"| {symbol['symbol']} | {_num(symbol['price'])} | {' | '.join(cells)} | {quality} / {disagreement} |")
    lines.extend(["", "## Whole-market context", "",
                  "| Indicator | Value | Status | Observed | Interpretation |",
                  "|---|---:|---|---|---|"])
    for row in view["market_summary"]:
        lines.append(f"| {row['label']} | {row['display']} | {row['status']} | "
                     f"{row['observed_at'] or '—'} | {row['meaning']} |")
    lines.extend(["", "## Symbol details", ""])
    for symbol in view["symbols"]:
        intraday = symbol["intraday"]
        lines.extend([f"### {symbol['symbol']}", "",
                      f"Completed close: {_num(symbol['price'])} ({symbol['price_date'] or 'unknown date'})", "",
                      f"Intraday context: {_num(intraday['session_last'])} at "
                      f"{intraday['latest_timestamp'] or 'unavailable'}; {intraday['evidence_state'] or 'unknown'}; "
                      f"{intraday['coverage'] or 'unknown coverage'}; {intraday['status']}; "
                      f"age {intraday['age_at_publication_seconds']} seconds; publication eligible {intraday['publication_eligible']}.", ""])
        for row in symbol["horizons"]:
            interval = row["price_interval_80"]
            interval_text = f"{_num(interval[0])}–{_num(interval[1])}" if interval else "—"
            probs = row["probabilities"] or {}
            lines.extend([f"#### {row['trading_days']} sessions — {row['action']}", "",
                          f"P(up) {_pct(row['probability_price_up'])}; bear/neutral/bull "
                          f"{_pct(probs.get('bear'))} / {_pct(probs.get('neutral'))} / {_pct(probs.get('bull'))}; "
                          f"80% price interval {interval_text}; "
                          f"disagreement {_num(row['disagreement'])}.", ""])
            ref = row["reference"]
            lines.extend([f"Reference: {_num(ref['reference_price'])} ({ref['reference_price_basis']}) observed "
                          f"{ref['reference_price_observed_at'] or 'unknown'}; forecast origin "
                          f"{ref['forecast_origin'] or 'unknown'}; target session "
                          f"{ref['target_trading_session'] or 'unresolved'}.", "",
                          ref["entry_basis_warning"], "",
                          f"New position: {row['new_position_action']}; existing holding: "
                          f"{row['existing_position_action']}; next review: {row['next_review'] or 'not specified'}.", ""])
            overlay = row.get("action_overlay", {})
            lines.extend([f"Current entry overlay: {overlay.get('current_entry_action', 'UNAVAILABLE')}; "
                          f"{', '.join(overlay.get('reason_codes', []))}.", "",
                          f"Invalidation: {json.dumps(row.get('invalidation_trigger')) if row.get('invalidation_trigger') else 'UNAVAILABLE'}.", ""])
            if row.get("heuristic_inputs"):
                lines.append("Heuristic inputs (predictive contributions are unmeasured): " + "; ".join(
                    f"{item['name']}={item['value']:.3f}" for item in row["heuristic_inputs"]))
            if row["conditional_trigger"]:
                trigger = row["conditional_trigger"]
                lines.append(f"- Conditional trigger: {trigger['field']} {trigger['comparison']} "
                             f"{trigger['level']} {trigger['units']} for {trigger['confirmation_interval']}; "
                             f"expires {trigger['expiry']}.")
            if row["wait_for"]:
                lines.append("- Wait for: " + "; ".join(row["wait_for"]))
            for heading, key in (("Supporting conditions", "catalysts"), ("Counter-case", "counter_case"),
                                 ("Review triggers", "review_triggers"), ("Missing inputs", "missing_inputs")):
                values = row[key]
                if values:
                    lines.append(f"- {heading}: " + "; ".join(str(value) for value in values))
            lines.append("")
    lines.extend(["## Evidence freshness and coverage", "",
                  "| Family | Scope | Status | Observation | Age at publication | Criticality / gate | Coverage | Detail |",
                  "|---|---|---|---|---:|---|---|---|"])
    for row in view["freshness"]:
        lines.append(f"| {row['family']} | {row['scope']} | {row['status']} | "
                     f"{row['observed_at'] or '—'} | {row['age_at_publication_seconds'] if row['age_at_publication_seconds'] is not None else '—'} | "
                     f"{row['criticality']} / {row['action_gate']} | {row['coverage'] or '—'} | {row['detail']} |")
    lines.extend(["", "## Partial failures", ""])
    if view["failures"]:
        lines.extend(f"- **{row['stage']} / {row['name']}**: {row['detail']}" for row in view["failures"])
    else:
        lines.append("No recorded stage failures.")
    if view["evaluation"]:
        counts = view["evaluation"]["status"]["counts"]
        lines.extend(["", "## Prospective evaluation", "",
                      ", ".join(f"{key}: {value}" for key, value in counts.items()), ""])
    lines.extend(["", "## Provenance", "",
                  f"- Packet: `{view['provenance']['packet_hash']}`",
                  f"- Structured forecast: `{view['provenance']['structured_hash'] or 'UNAVAILABLE'}`",
                  f"- Cohort: `{view['provenance']['cohort_id'] or 'UNAVAILABLE'}`",
                  f"- Product view: `{view['view_hash']}`", ""])
    return "\n".join(lines)


READING_GUIDE = (
    ("Probability", "P(up) concerns the terminal close relative to the displayed reference price. It is not the chance of reaching a price at any time, and it is not a calibrated success rate."),
    ("Horizon", "5, 21 and 63 mean exchange trading sessions. The target session gives the actual evaluation date."),
    ("Price interval", "The 80% interval describes a model distribution for the terminal price. It is neither a guaranteed range nor a stop-loss instruction."),
    ("Action", "The cutoff action uses the frozen evidence. Current entry separately checks whether the evidence and price are still usable. WAIT can coexist with a positive directional estimate."),
    ("Evidence", "Missing coverage means unknown. Agent agreement and accepted facts do not establish predictive accuracy. Existing holdings require position context."),
)


def _horizon_card(row: dict) -> str:
    probs = row["probabilities"] or {"bear": 0, "neutral": 0, "bull": 0}
    interval = row["price_interval_80"]
    interval_text = f"{_num(interval[0])}–{_num(interval[1])}" if interval else "—"
    coverage = row.get("coverage") or {}
    context_coverage = coverage.get("context_roles", {})
    trigger = row.get("conditional_trigger")
    trigger_text = (f"{trigger['field']} {trigger['comparison']} {trigger['level']} {trigger['units']} "
                    f"for {trigger['confirmation_interval']}; expires {trigger['expiry']}"
                    if trigger else "No measurable trigger available")
    reference = row["reference"]
    return f'''<article class="horizon">
      <header><strong>{row['trading_days']} sessions</strong><span class="action">{escape(row['action'])}</span></header>
      <div class="primary">P↑ {_pct(row['probability_price_up'])}</div>
      <div class="prob" aria-label="Bear {_pct(probs.get('bear'))}, neutral {_pct(probs.get('neutral'))}, bull {_pct(probs.get('bull'))}">
        <i class="bear" style="width:{100*probs.get('bear',0):.2f}%"></i><i class="neutral" style="width:{100*probs.get('neutral',0):.2f}%"></i><i class="bull" style="width:{100*probs.get('bull',0):.2f}%"></i>
      </div>
      <dl><dt>Bear / neutral / bull</dt><dd>{_pct(probs.get('bear'))} / {_pct(probs.get('neutral'))} / {_pct(probs.get('bull'))}</dd>
      <dt>Expected return</dt><dd>{_num(row['expected_return_pct'])}%</dd><dt>80% price interval</dt><dd>{interval_text}</dd>
      <dt>Median return</dt><dd>{_num(row['median_return_pct'])}%</dd><dt>Context coverage</dt><dd>{context_coverage.get('covered', '—')}/{context_coverage.get('total', '—')} roles</dd>
      <dt>Disagreement</dt><dd>{_num(row['disagreement'])}</dd><dt>Target session</dt><dd>{escape(str(reference['target_trading_session'] or 'unresolved'))}</dd></dl>
      <p><b>Reference:</b> {_num(reference['reference_price'])} · {escape(reference['reference_price_basis'])} · observed {escape(str(reference['reference_price_observed_at'] or 'unknown'))}. {escape(reference['entry_basis_warning'])}</p>
      <p><b>New position:</b> {escape(row['new_position_action'])} · <b>Existing holding:</b> {escape(row['existing_position_action'])}</p>
      <details><summary>Conditions, counter-case and triggers</summary>
      <p><b>Current entry overlay:</b> {escape(row.get('action_overlay', {}).get('current_entry_action', 'UNAVAILABLE'))} · {escape(', '.join(row.get('action_overlay', {}).get('reason_codes', [])))}</p>
      <p><b>Invalidation:</b> {escape(json.dumps(row.get('invalidation_trigger')) if row.get('invalidation_trigger') else 'UNAVAILABLE')}</p>
      <p><b>Next review:</b> {escape(str(row.get('next_review') or 'UNAVAILABLE'))}</p>
      <p><b>Heuristic inputs (predictive contributions unmeasured):</b> {escape('; '.join(f"{item['name']}={item['value']:.3f}" for item in row.get('heuristic_inputs', [])) or 'Unavailable')}</p>
      <p><b>Conditional trigger:</b> {escape(trigger_text)}</p>
      <p><b>Wait for:</b> {escape('; '.join(map(str,row['wait_for'])) or 'Nothing specified')}</p>
      <p><b>Support:</b> {escape('; '.join(map(str,row['catalysts'])) or 'None recorded')}</p>
      <p><b>Counter-case:</b> {escape('; '.join(map(str,row['counter_case'])) or 'None recorded')}</p>
      <p><b>Review:</b> {escape('; '.join(map(str,row['review_triggers'])) or 'None recorded')}</p>
      <p><b>Missing:</b> {escape('; '.join(map(str,row['critical_gaps'] + row['advisory_gaps'] + row['missing_inputs'])) or 'None')}</p></details></article>'''


def render_html(view: dict, refresh_seconds: int = 30) -> str:
    _ = refresh_seconds  # The generated bundle is immutable; browser reload cannot update evidence.
    symbol_sections = []
    for symbol in view["symbols"]:
        intraday = symbol["intraday"]
        agents = "".join(f"<tr><td>{escape(row['role'])}</td><td>{escape(row['status'])}</td><td>{escape(row['view'])}</td><td>{escape(str(row['thesis'] or row['failure'] or '—'))}</td></tr>"
                         for row in symbol["agent_views"])
        symbol_sections.append(f'''<section id="{escape(symbol['symbol'])}" class="symbol">
          <div class="symbol-head"><h2>{escape(symbol['symbol'])}</h2><span>Completed close {_num(symbol['price'])} · {escape(str(symbol['price_date'] or 'unknown'))}</span></div>
          <p class="muted">Intraday context: {_num(intraday['session_last'])} at {escape(str(intraday['latest_timestamp'] or 'unavailable'))}; {escape(str(intraday['evidence_state'] or 'unknown'))}; {escape(str(intraday['coverage'] or 'unknown coverage'))}; publication status {escape(intraday['status'])}; age {intraday['age_at_publication_seconds']} seconds; publication eligible {intraday['publication_eligible']}.</p>
          <div class="horizons">{''.join(_horizon_card(row) for row in symbol['horizons'])}</div>
          <details><summary>Specialist and synthesis views</summary><div class="scroll"><table><thead><tr><th>Role</th><th>Status</th><th>View</th><th>Thesis/failure</th></tr></thead><tbody>{agents}</tbody></table></div></details>
        </section>''')
    freshness = "".join(
        f'''<tr><td>{escape(row['family'])}</td><td>{escape(row['scope'])}</td>
        <td><span class="badge {escape(row['status'].lower())}">{escape(row['status'])}</span></td>
        <td>{escape(str(row['observed_at'] or '—'))}</td><td>{escape(str(row['age_at_publication_seconds'] if row['age_at_publication_seconds'] is not None else '—'))}</td>
        <td>{escape(row['criticality'])} / {escape(row['action_gate'])}</td><td>{escape(str(row['coverage'] or '—'))}</td>
        <td>{escape(row['detail'])}</td></tr>'''
        for row in view["freshness"])
    failures = "".join(f"<li><b>{escape(row['stage'])} / {escape(row['name'])}</b>: {escape(row['detail'])}</li>" for row in view["failures"]) or "<li>None recorded.</li>"
    market_cards = "".join(
        f'''<article class="horizon"><header><strong>{escape(row['label'])}</strong><span class="badge {escape(row['status'].lower())}">{escape(row['status'])}</span></header>
        <div class="primary">{escape(row['display'])}</div><p class="muted">Observed {escape(str(row['observed_at'] or '—'))}</p><p>{escape(row['meaning'])}</p></article>'''
        for row in view["market_summary"])
    golden = view["golden_conclusions"]
    critical = "".join(
        f'''<li><b>{escape(row['importance'])} · {escape(', '.join(row['scopes']))} · {escape(', '.join(str(value) for value in row['horizons']))} sessions</b><br>
        {escape(row['conclusion'])}<br><span class="muted">Invalidation: {escape(row['invalidation'])}</span></li>'''
        for row in golden["critical_conclusions"]) or "<li>No validated critical conclusions are available.</li>"
    priorities = "".join(
        f'''<tr><td>{row['rank']}</td><td><b>{escape(row['symbol'])}</b></td><td>{escape(row['stance'])}</td>
        <td>{escape(', '.join(str(value) for value in row['horizons']))}</td><td>{escape(row['rationale'])}</td>
        <td>{escape('; '.join(row['conditions']) or '—')}</td><td>{escape('; '.join(row['invalidation']) or '—')}</td></tr>'''
        for row in sorted(golden["cross_symbol_priorities"], key=lambda value: value["rank"]))
    if not priorities:
        priorities = "<tr><td>—</td><td>—</td><td>UNKNOWN</td><td>—</td><td>Astra synthesis unavailable</td><td>—</td><td>—</td></tr>"
    triggers = "".join(f"<li>{escape(value)}</li>" for value in golden["immediate_review_triggers"]) or "<li>None available.</li>"
    limitations = "".join(f"<li>{escape(value)}</li>" for value in golden["evidence_limitations"]) or "<li>None recorded.</li>"
    decision_rows = "".join(
        f"<tr><td><b>{escape(row['symbol'])}</b></td><td>{row['trading_days']}</td>"
        f"<td>{escape(row['action_now'])}</td><td>{escape(row['new_position_action'])} / {escape(row['existing_position_action'])}</td>"
        f"<td>{_pct(row['probability_price_up'])}</td><td>{escape(row['what_changes_action'])}</td>"
        f"<td>{escape(row['what_could_go_wrong'])}</td></tr>"
        for row in sorted(golden["decision_rows"], key=lambda value: (value["symbol"], value["trading_days"])))
    board_rows = []
    for symbol in view["symbols"]:
        cells = "".join(f"<td>Cutoff: {escape(row['action'])}<br><span class=\"muted\">P↑ {_pct(row['probability_price_up'])}<br>"
                        f"{escape(row.get('model_usage', 'REFERENCE_ONLY'))}<br>Current entry: "
                        f"{escape(row['action_overlay']['current_entry_action'])} · "
                        f"{escape(', '.join(row['action_overlay']['reason_codes']))}</span></td>"
                        for row in symbol["horizons"])
        board_rows.append(f"<tr><td><b>{escape(symbol['symbol'])}</b></td><td>{_num(symbol['price'])}</td>{cells}</tr>")
    golden_html = f'''<section id="golden" class="symbol golden"><div class="symbol-head"><h2>GOLDEN RECOMMENDATIONS / GOLDEN CONCLUSIONS</h2><span class="badge">{escape(golden['status'])}</span></div>
      <h3>META executive assessment</h3><p class="executive">{escape(golden['executive_summary'])}</p>
      <h3>Market regime</h3><p>{escape(golden['market_regime_detail']['summary'])}</p><p class="muted">Invalidation: {escape(golden['market_regime_detail']['invalidation'])}</p>
      <h3>Critical conclusions</h3><ol class="critical">{critical}</ol>
      <h3>Ranked cross-symbol priorities</h3><div class="scroll"><table><thead><tr><th>Rank</th><th>Symbol</th><th>Stance</th><th>Sessions</th><th>Rationale</th><th>Conditions</th><th>Invalidation</th></tr></thead><tbody>{priorities}</tbody></table></div>
      <h3>Immediate review triggers</h3><ul>{triggers}</ul><h3>Decisive evidence limitations</h3><ul>{limitations}</ul>
      <h3>Frozen decisions at the information cutoff</h3><div class="scroll"><table><thead><tr><th>Symbol</th><th>Sessions</th><th>Action</th><th>New / existing</th><th>P(terminal gain)</th><th>What changes it</th><th>What could go wrong</th></tr></thead><tbody>{decision_rows}</tbody></table></div>
      <h3>Deterministic horizon board</h3><div class="scroll"><table><thead><tr><th>Symbol</th><th>Completed close</th><th>5 sessions</th><th>21 sessions</th><th>63 sessions</th></tr></thead><tbody>{''.join(board_rows)}</tbody></table></div>
    </section>'''
    evaluation_html = ""
    if view["evaluation"]:
        counts = view["evaluation"]["status"]["counts"]
        count_rows = "".join(f"<tr><td>{escape(str(key))}</td><td>{value}</td></tr>"
                             for key, value in counts.items())
        evaluation_html = f'''<section id="evaluation" class="symbol"><h2>Prospective evaluation</h2>
        <p>As of {escape(view['evaluation']['status']['as_of'])}. These are outcome states, not a claim of predictive skill.</p>
        <table><thead><tr><th>State</th><th>Records</th></tr></thead><tbody>{count_rows}</tbody></table></section>'''
    nav = "".join(f'<a href="#{escape(row["symbol"])}">{escape(row["symbol"])}</a>' for row in view["symbols"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>META research cockpit</title>
    <style>:root{{--bg:#0b1020;--panel:#141b2d;--line:#2b3652;--text:#edf2ff;--muted:#9eabc7;--warn:#f4bd50;--bad:#ef6a78;--good:#54c89a;--neutral:#7692bb;--gold:#ffd76a}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}}main{{max-width:1320px;margin:auto;padding:24px}}a{{color:#9fc4ff}}.top{{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;flex-wrap:wrap}}.eyebrow,.muted{{color:var(--muted)}}h1{{margin:.2rem 0;font-size:clamp(1.7rem,4vw,3rem)}}nav{{display:flex;gap:8px;flex-wrap:wrap}}nav a,.badge,.action{{border:1px solid var(--line);border-radius:999px;padding:4px 9px;text-decoration:none}}.banner{{margin:20px 0;padding:14px 16px;border-left:5px solid var(--warn);background:var(--panel)}}.symbol{{margin:28px 0;padding:18px;background:var(--panel);border:1px solid var(--line);border-radius:16px}}.golden{{border-color:var(--gold);box-shadow:0 0 0 1px #ffd76a30}}.golden h2,.golden h3{{color:var(--gold)}}.executive{{font-size:1.12rem}}.critical li{{margin-bottom:12px}}.symbol-head,.horizon header{{display:flex;justify-content:space-between;gap:12px;align-items:center}}.symbol-head h2{{margin:0}}.horizons{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:16px 0}}.horizon{{border:1px solid var(--line);padding:14px;border-radius:12px}}.primary{{font-size:1.45rem;margin:14px 0 8px}}.prob{{height:9px;display:flex;border-radius:8px;overflow:hidden;background:#333}}.prob i{{display:block}}.bear{{background:var(--bad)}}.neutral{{background:var(--neutral)}}.bull{{background:var(--good)}}dl{{display:grid;grid-template-columns:1fr auto;gap:5px 10px}}dt{{color:var(--muted)}}dd{{margin:0}}details{{margin-top:12px}}summary{{cursor:pointer}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:8px;border-bottom:1px solid var(--line);vertical-align:top}}.scroll{{overflow:auto}}.missing,.missing_intraday,.stale,.failed,.partial,.live_intraday_partial{{color:#111;background:var(--warn)}}footer{{color:var(--muted);margin:35px 0}}@media(max-width:850px){{.horizons{{grid-template-columns:1fr}}}}</style></head>
    <body><main><header class="top"><div><div class="eyebrow">{escape(view['mode'])} · {escape(view['market_period'])}</div><h1>META research cockpit</h1><div>Cutoff {escape(view['as_of'])}</div></div><div><span class="badge">{escape(view['run_status'])}</span> <span class="badge">{escape(view['probability_status'])}</span></div></header>
    <div class="banner"><b>Immutable evidence snapshot.</b> {escape(view['notice'])}</div><nav><a href="#golden">Golden conclusions</a><a href="#market">Market</a>{nav}<a href="#freshness">Evidence</a><a href="#evaluation">Evaluation</a><a href="#operations">Operations</a></nav>
    <section class="symbol" id="reading-guide"><h2>How to read this report</h2><dl>{''.join(f'<dt>{escape(label)}</dt><dd>{escape(explanation)}</dd>' for label, explanation in READING_GUIDE)}</dl></section>
    {golden_html}
    <section id="market" class="symbol"><h2>Whole-market context</h2><div class="horizons">{market_cards}</div></section>
    {''.join(symbol_sections)}
    <section id="freshness" class="symbol"><h2>Evidence freshness and coverage</h2><div class="scroll"><table><thead><tr><th>Family</th><th>Scope</th><th>Status</th><th>Observed</th><th>Age (s)</th><th>Criticality / gate</th><th>Coverage</th><th>Meaning</th></tr></thead><tbody>{freshness}</tbody></table></div></section>
    {evaluation_html}
    <section id="operations" class="symbol"><h2>Partial failures</h2><ul>{failures}</ul><h3>Provenance</h3><p>Packet <code>{escape(view['provenance']['packet_hash'])}</code><br>Structured forecast <code>{escape(str(view['provenance']['structured_hash'] or 'UNAVAILABLE'))}</code><br>Cohort <code>{escape(str(view['provenance']['cohort_id'] or 'UNAVAILABLE'))}</code><br>View <code>{escape(view['view_hash'])}</code></p></section>
    <footer>Generated {escape(view['generated_at'])}. Values are rendered directly from hash-verified local artifacts.</footer></main></body></html>'''


def write_product_bundle(packet_path: Path, output_root: Path, **kwargs) -> Path:
    policy_path = kwargs.pop("operations_policy", DEFAULT_POLICY)
    policy = load_operations_policy(policy_path)
    view = build_product_view(packet_path, **kwargs)
    output_root.mkdir(parents=True, exist_ok=False)
    write_json_exclusive(output_root / "summary.json", view)
    write_bytes_exclusive(output_root / "report.md", render_markdown(view).encode())
    write_bytes_exclusive(output_root / "index.html",
                          render_html(view, policy["dashboard"]["auto_refresh_seconds"]).encode())
    receipt = {"schema_version": "meta-product-bundle-v1", "view_hash": view["view_hash"],
               "files": {name: file_sha256(output_root / name)
                         for name in ("summary.json", "report.md", "index.html")}}
    receipt["bundle_hash"] = digest(receipt)
    write_json_exclusive(output_root / "bundle.json", receipt)
    return output_root


class ProductHandler(BaseHTTPRequestHandler):
    root: Path

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        mapping = {"/": ("index.html", "text/html; charset=utf-8"),
                   "/index.html": ("index.html", "text/html; charset=utf-8"),
                   "/summary.json": ("summary.json", "application/json"),
                   "/api/v1/latest": ("summary.json", "application/json"),
                   "/report.md": ("report.md", "text/markdown; charset=utf-8")}
        if route == "/healthz":
            payload = json.dumps({"status": "OK", "read_only": True}).encode()
            return self._send(200, "application/json", payload)
        if route not in mapping:
            return self._send(404, "text/plain; charset=utf-8", b"Not found\n")
        name, content_type = mapping[route]
        path = self.root / name
        if not path.exists():
            return self._send(404, "text/plain; charset=utf-8", b"Not found\n")
        self._send(200, content_type, path.read_bytes())

    def do_POST(self) -> None:  # noqa: N802
        self._send(405, "application/json", b'{"error":"read-only dashboard"}\n')

    def _send(self, status: int, content_type: str, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:
        return


def serve(bundle: Path, host: str, port: int) -> None:
    if host != "127.0.0.1":
        raise ValueError("The G10 dashboard may bind only to 127.0.0.1")
    handler = type("BoundProductHandler", (ProductHandler,), {"root": bundle.resolve()})
    with ThreadingHTTPServer((host, port), handler) as server:
        print(f"META dashboard: http://{host}:{port}")
        server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    render = sub.add_parser("render")
    render.add_argument("--packet", type=Path, required=True)
    render.add_argument("--structured-forecast", type=Path)
    render.add_argument("--agent-report", type=Path)
    render.add_argument("--output", type=Path, required=True)
    render.add_argument("--mode", choices=("ON_DEMAND", "PROSPECTIVE"), default="ON_DEMAND")
    render.add_argument("--operations-policy", type=Path, default=DEFAULT_POLICY)
    render.add_argument("--forecasts", type=Path, default=ROOT / "datasets/meta-observation/forecasts")
    render.add_argument("--outcomes", type=Path, default=ROOT / "datasets/meta-observation/outcomes")
    render.add_argument("--scores", type=Path, default=ROOT / "datasets/meta-observation/scores")
    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--bundle", type=Path, required=True)
    serve_parser.add_argument("--operations-policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args()
    if args.action == "render":
        output = write_product_bundle(args.packet, args.output,
                                      structured_path=args.structured_forecast,
                                      report_path=args.agent_report, mode=args.mode,
                                      forecast_root=args.forecasts, outcome_root=args.outcomes,
                                      score_root=args.scores, operations_policy=args.operations_policy)
        result = {"status": "RENDERED", "output": str(output.resolve())}
        print(json.dumps(result, indent=2))
    else:
        policy = load_operations_policy(args.operations_policy)
        serve(args.bundle, policy["dashboard"]["bind_host"], policy["dashboard"]["port"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
