from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.error import HTTPError

import exchange_calendars as xcals
from jsonschema import Draft202012Validator
import numpy as np
import pytest

from spy_predictor_quant.meta_analysis import (
    _cli_exit_status, analyze, archive, build, daily_metrics, digest, global_market_metrics, intraday_metrics,
    current_volatility_metrics, load_product_contract, load_snapshot, macro_metrics,
    market_period_at, parse_massive_index_snapshot,
    parse_fred, reference_scenarios, SecHttpClient, transparent_risk_appetite,
    postclose_preflight, SERIES, validate_delayed_context, validate_external,
    validate_postclose_packet, VERSION,
)
import spy_predictor_quant.meta_analysis as meta_analysis
from spy_predictor_quant.meta_agents import (
    INDEPENDENT, _normalize_exact_duplicate_assessments, project_packet, request_for,
    run_agents, validate_output,
)

CUTOFF = datetime(2026, 9, 9, 22, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_sec_client_identifies_paces_and_honors_retry_after(monkeypatch):
    clock = FakeClock()
    calls = []

    def fake_get(url, headers=None):
        calls.append((clock.now, headers))
        if len(calls) == 1:
            raise HTTPError(url, 429, "busy", {"Retry-After": "2"}, None)
        return b"ok"

    monkeypatch.setattr(meta_analysis, "get_raw", fake_get)
    client = SecHttpClient("spy-predictor test@example.com", sleeper=clock.sleep,
                           monotonic=clock.monotonic)
    assert client.get("https://data.sec.gov/test") == b"ok"
    assert calls == [(0, {"User-Agent": "spy-predictor test@example.com"}),
                     (2, {"User-Agent": "spy-predictor test@example.com"})]
    assert clock.sleeps == [2]


def test_sec_client_spaces_requests_and_does_not_retry_permanent_error(monkeypatch):
    clock = FakeClock()
    calls = []

    def fake_get(url, headers=None):
        calls.append(clock.now)
        if url.endswith("missing"):
            raise HTTPError(url, 404, "missing", {}, None)
        return b"ok"

    monkeypatch.setattr(meta_analysis, "get_raw", fake_get)
    client = SecHttpClient("spy-predictor test@example.com", requests_per_second=2,
                           sleeper=clock.sleep, monotonic=clock.monotonic)
    assert client.get("https://data.sec.gov/one") == b"ok"
    assert client.get("https://data.sec.gov/two") == b"ok"
    with pytest.raises(HTTPError):
        client.get("https://data.sec.gov/missing")
    assert calls == [0, .5, 1]


@pytest.fixture
def prices():
    days = xcals.get_calendar("XNYS").sessions_in_range("2025-08-01", "2026-09-09")
    rows = []
    for i, day in enumerate(days):
        p = 100*np.exp(.0003*i+.01*np.sin(i))
        rows.append({"date": day.strftime("%Y%m%d"), "open": p, "high": p+1,
                     "low": p-1, "close": p, "volume": 1000})
    return {"symbol": "SPY", "bars": rows, "received_at": CUTOFF.isoformat()}


def source():
    return {"id": "price-SPY", "kind": "ibkr_daily", "adjustment": "split", "feed": "test"}


def test_technical_arithmetic_and_incomplete_session_exclusion(prices):
    cutoff = CUTOFF.replace(hour=12)
    metrics = daily_metrics(prices, source(), cutoff)
    closes = np.array([b["close"] for b in prices["bars"][:-1]])
    assert metrics["price_date"] == "2026-09-08"
    assert metrics["sma200"] == pytest.approx(closes[-200:].mean())
    assert metrics["realized_vol63_pct"] == pytest.approx(np.std(np.diff(np.log(closes[-64:])), ddof=1)*np.sqrt(252)*100)
    assert metrics["weekly_view"]["sma40_weeks"] > 0
    assert metrics["support_resistance_candidates"]["20_session"]["support_close"] == pytest.approx(
        closes[-20:].min())
    changed = deepcopy(prices)
    changed["bars"][-1]["close"] = 1e9
    assert daily_metrics(changed, source(), cutoff) == metrics


@pytest.mark.parametrize("problem", ["gap", "duplicate", "invalid_ohlc", "nonfinite"])
def test_bad_price_inputs_rejected(prices, problem):
    if problem == "gap":
        del prices["bars"][-30]
    elif problem == "duplicate":
        prices["bars"].insert(-30, prices["bars"][-30])
    elif problem == "invalid_ohlc":
        prices["bars"][-1]["high"] = 1
    else:
        prices["bars"][-1]["close"] = float("nan")
    with pytest.raises(ValueError):
        daily_metrics(prices, source(), CUTOFF)


def test_stale_price_cannot_generate_current_ranges(prices):
    prices["bars"] = prices["bars"][:-2]
    result = daily_metrics(prices, source(), CUTOFF)
    assert result["status"] == "STALE"
    assert result["reference_scenarios"] == []


def test_intraday_capture_cannot_become_final_in_later_build(prices):
    receipt = {**source(), "retrieved_at": CUTOFF.replace(hour=12).isoformat()}
    result = daily_metrics(prices, receipt, CUTOFF)
    assert result["price_date"] == "2026-09-08"
    assert result["status"] == "STALE"
    assert result["reference_scenarios"] == []


def test_delayed_request_end_excludes_partial_bar_even_after_bell(prices):
    receipt = {**source(), "retrieved_at": CUTOFF.isoformat(),
               "data_end": CUTOFF.replace(hour=19, minute=50).isoformat()}
    result = daily_metrics(prices, receipt, CUTOFF)
    assert result["price_date"] == "2026-09-08"
    assert result["reference_scenarios"] == []


def test_credit_uses_same_month_and_exact_three_month_change():
    histories = {"MPRIME": [(date(2026, 4, 1), 7), (date(2026, 5, 1), 6.75), (date(2026, 8, 1), 6.5)],
                 "GS3M": [(date(2026, 4, 1), 4), (date(2026, 5, 1), 3.9), (date(2026, 8, 1), 3.5)]}
    credit = macro_metrics(histories, CUTOFF)["lending_rate_proxy"]
    assert credit["value"] == 300
    assert credit["change_exact_3_months_bps"] == pytest.approx(15)
    histories["GS3M"].pop(1)
    assert macro_metrics(histories, CUTOFF)["lending_rate_proxy"]["change_exact_3_months_bps"] is None


def test_vix_term_structure_uses_latest_common_observation():
    histories = {
        "VIXCLS": [(date(2026, 9, 8), 18), (date(2026, 9, 9), 21)],
        "VXVCLS": [(date(2026, 9, 8), 20)],
    }
    result = macro_metrics(histories, CUTOFF)["vix_term_structure_proxy"]
    assert result["observed_date"] == "2026-09-08"
    assert result["value"] == pytest.approx(.9)
    assert result["spread_points"] == -2


def massive_snapshot(ticker="I:VIX", value=18.5, observed=CUTOFF, timeframe="REAL-TIME"):
    return json.dumps({"status": "OK", "results": [{"ticker": ticker, "value": value,
        "last_updated": int(observed.timestamp() * 1_000_000_000),
        "timeframe": timeframe}]}).encode()


def test_massive_current_vix_parser_enforces_identity_timeframe_and_age():
    result = parse_massive_index_snapshot(
        massive_snapshot(observed=CUTOFF-timedelta(seconds=30)), "I:VIX", CUTOFF)
    assert result["status"] == "LIVE_INTRADAY"
    assert result["value"] == 18.5
    delayed = parse_massive_index_snapshot(
        massive_snapshot(observed=CUTOFF-timedelta(minutes=15), timeframe="DELAYED"),
        "I:VIX", CUTOFF)
    assert delayed["status"] == "DELAYED"
    with pytest.raises(ValueError, match="ticker"):
        parse_massive_index_snapshot(massive_snapshot(ticker="I:OTHER"), "I:VIX", CUTOFF)
    with pytest.raises(ValueError, match="cutoff"):
        parse_massive_index_snapshot(
            massive_snapshot(observed=CUTOFF+timedelta(seconds=6)), "I:VIX", CUTOFF)


def test_current_vix_panel_requires_both_legs_and_computes_same_session_ratio():
    histories = {"VIXCLS": [(CUTOFF.date()-timedelta(days=index), 10+index/10)
                              for index in range(100, -1, -1)]}
    missing = current_volatility_metrics({}, CUTOFF, histories,
                                         {"current-volatility-VIX": "HTTP_403"})
    assert missing["status"] == "MISSING_INTRADAY"
    assert missing["reasons"]["VIX"] == "HTTP_403"
    raw = {
        "current-volatility-VIX": massive_snapshot("I:VIX", 18, CUTOFF-timedelta(seconds=15)),
        "current-volatility-VIX3M": massive_snapshot("I:VIX3M", 20, CUTOFF-timedelta(seconds=10)),
    }
    result = current_volatility_metrics(raw, CUTOFF, histories)
    assert result["status"] == "LIVE_INTRADAY"
    assert result["vix_vix3m_ratio"] == pytest.approx(.9)
    assert result["spread_points"] == -2


def test_global_market_panels_require_same_date_and_show_missing_families():
    day = date(2026, 9, 9)
    histories = {key: [(day, value)] for key, value in {
        "DGS2": 3.5, "DGS5": 3.7, "DGS10": 4.0, "DGS30": 4.4,
        "T10Y3M": .4, "DFII10": 1.6, "T10YIE": 2.3,
        "SOFR": 3.2, "NFCICREDIT": -.1, "DTWEXBGS": 120, "DCOILWTICO": 70,
    }.items()}
    result = global_market_metrics(histories, CUTOFF)
    assert result["yield_curve"]["slopes_percentage_points"] == {
        "10y_minus_2y": pytest.approx(.5), "30y_minus_5y": pytest.approx(.7)}
    assert result["nominal_real_breakeven"]["nominal_minus_real_minus_breakeven_pp"] == pytest.approx(.1)
    assert result["coverage"]["treasury_curve"] == "AVAILABLE"
    assert result["coverage"]["foreign_central_banks"] == "MISSING"
    histories["DGS30"] = [(date(2026, 9, 8), 4.4)]
    assert global_market_metrics(histories, CUTOFF)["yield_curve"]["status"] == "MISSING"


def intraday_fixture(*, coverage="IEX_ONLY", state="REAL_TIME"):
    start = datetime(2026, 9, 9, 13, 30, tzinfo=timezone.utc)
    bars = []
    for index in range(62):
        price = 100 + index / 10
        bars.append({"t": (start + timedelta(minutes=index)).isoformat(),
                     "o": price, "h": price + .2, "l": price - .2,
                     "c": price + .1, "v": 100 + index, "vw": price + .05})
    cutoff = start + timedelta(minutes=61)
    common = {"symbol": "SPY", "evidence_state": state,
              "exchange_coverage": coverage, "expected_delay_minutes": 0 if state == "REAL_TIME" else 15}
    bars_source = {**common, "feed": "iex" if state == "REAL_TIME" else "sip",
                   "data_end": cutoff.isoformat()}
    latest_source = {**common, "feed": "iex" if state == "REAL_TIME" else "delayed_sip"}
    latest = {"latestTrade": {"t": (cutoff-timedelta(seconds=20)).isoformat(), "p": 106},
              "latestQuote": {"t": (cutoff-timedelta(seconds=10)).isoformat(), "bp": 105.9, "ap": 106.1}}
    return {"bars": bars}, latest, bars_source, latest_source, cutoff


def test_intraday_metrics_label_coverage_and_exclude_unfinished_minute():
    args = intraday_fixture()
    result = intraday_metrics(*args)
    assert result["evidence_state"] == "REAL_TIME"
    assert result["exchange_coverage"] == "IEX_ONLY"
    assert result["minute_bars"] == 61
    assert result["timeframes_minutes"]["60"]["status"] == "COMPLETE"
    assert result["timeframes_minutes"]["60"]["end"] == args[-1].isoformat()
    assert result["latest_quote"]["spread_bps"] == pytest.approx(18.8679245)
    assert result["halt_status"] == "UNKNOWN_NO_QUALIFIED_HALT_FEED"
    assert "limited-venue" in result["limitations"][0]


def test_fresh_quote_does_not_make_older_displayed_bar_look_fresh():
    bars, latest, bars_source, latest_source, cutoff = intraday_fixture()
    bars_source["data_end"] = (cutoff - timedelta(minutes=5)).isoformat()
    result = intraday_metrics(bars, latest, bars_source, latest_source, cutoff)
    assert result["latest_observation_timestamp"] == latest["latestQuote"]["t"]
    assert result["session_last_observed_at"] == bars_source["data_end"]
    assert result["value_timestamps"]["session_last"] != result["value_timestamps"]["latest_quote"]
    assert result["age_at_cutoff_seconds"] == 300


def test_intraday_metrics_reject_crossed_quote_and_marks_gaps():
    bars, latest, bars_source, latest_source, cutoff = intraday_fixture(
        coverage="ALL_US_EXCHANGES", state="DELAYED")
    latest["latestQuote"]["bp"] = 107
    with pytest.raises(ValueError, match="crossed"):
        intraday_metrics(bars, latest, bars_source, latest_source, cutoff)
    latest["latestQuote"]["bp"] = 105.9
    del bars["bars"][20]
    result = intraday_metrics(bars, latest, bars_source, latest_source, cutoff)
    assert result["status"] == "PARTIAL_GAPS"
    assert "delayed" in result["limitations"][0]


def test_transparent_risk_appetite_keeps_components_and_limitations_visible():
    market = {"VIXCLS": {"fear_proxy_percentile": 80}}
    prices = {
        "SPY": {"status": "FRESH", "rsi14_simple": 60, "price_to_sma200": 1.1},
        "QQQ": {"status": "FRESH", "rsi14_simple": 40, "price_to_sma200": .9},
    }
    result = transparent_risk_appetite(market, prices)
    assert result["components"] == {
        "inverse_vix_percentile": 20,
        "mean_watchlist_rsi14": 50,
        "watchlist_above_sma200_pct": 50,
    }
    assert result["value"] == 40
    assert "not the CNN" in result["limitations"][0]
    market["current_volatility"] = {"status": "MISSING_INTRADAY", "values": {},
                                     "missing": ["VIX", "VIX3M"]}
    current_missing = transparent_risk_appetite(market, prices)
    assert current_missing["status"] == "PARTIAL"
    assert current_missing["components"]["inverse_vix_percentile"] is None
    assert current_missing["volatility_observation"]["status"] == "MISSING_INTRADAY"


def test_product_contract_and_market_periods_are_explicit():
    contract = load_product_contract()
    assert contract["horizons_sessions"] == [5, 21, 63]
    assert contract["operating_modes"]["on_demand"]["registration"] is False
    assert contract["operating_modes"]["prospective"]["registration"] is True
    assert market_period_at(datetime(2026, 9, 12, 16, tzinfo=timezone.utc)) == "CLOSED"
    assert market_period_at(datetime(2026, 9, 14, 12, tzinfo=timezone.utc)) == "PREMARKET"
    assert market_period_at(datetime(2026, 9, 14, 16, tzinfo=timezone.utc)) == "REGULAR"
    assert market_period_at(datetime(2026, 9, 14, 21, tzinfo=timezone.utc)) == "POSTMARKET"


def test_delayed_ibkr_context_is_bounded_and_never_treated_as_live():
    payload = {
        "schemaVersion": "ibkr-delayed-quotes-v1", "status": "ok",
        "observedAt": "2026-09-09T21:59:58+00:00", "quotes": {
            "SPY": {"marketDataType": 3, "lastAsOf": "2026-09-09T21:44:58+00:00",
                    "lastAgeSeconds": 900, "ticks": {
                        "DELAYED_BID": {"value": "-1", "receivedAt": "2026-09-09T21:59:57+00:00"},
                        "DELAYED_LAST": {"value": "101.5", "receivedAt": "2026-09-09T21:59:57+00:00"}}}}}
    result = validate_delayed_context(payload, CUTOFF)
    assert result["market_data_type"] == "DELAYED"
    assert result["instruments"]["SPY"]["delayed_last"] == 101.5
    assert "delayed_bid" not in result["instruments"]["SPY"]
    assert "not executable" in result["limitations"][0]
    with pytest.raises(ValueError, match="too old"):
        validate_delayed_context(payload, CUTOFF + timedelta(days=2))


def test_postclose_preflight_rejects_intraday_and_duplicate_origins(tmp_path):
    intraday = postclose_preflight(["SPY"], tmp_path, datetime(2026, 9, 10, 18, tzinfo=timezone.utc))
    assert intraday["status"] == "OUTSIDE_POST_CLOSE_WINDOW"
    forecast = {"version": "meta-observation-v1", "symbols": {
        "SPY": {"status": "ISSUED", "origin_session": "2026-09-10"}}}
    forecast["forecast_hash"] = digest(forecast)
    (tmp_path / "forecast.json").write_text(json.dumps(forecast))
    duplicate = postclose_preflight(["SPY"], tmp_path, datetime(2026, 9, 10, 21, tzinfo=timezone.utc))
    assert duplicate["status"] == "DUPLICATE_ORIGIN"
    assert duplicate["duplicates"][0]["symbol"] == "SPY"


def test_postclose_packet_requires_prices_macro_and_sec(tmp_path):
    scenario = reference_scenarios(100, 20)
    packet = {
        "symbols": ["SPY", "AAPL"], "acquisition_errors": {},
        "instruments": {symbol: {"status": "FRESH", "price_date": "2026-09-10",
                                 "reference_scenarios": scenario}
                        for symbol in ("SPY", "AAPL")},
        "market": {series: {"status": "FRESH"} for series in SERIES},
        "company_fundamentals": {"AAPL": {}}, "etf_holdings": {},
        "delayed_ibkr_context": {"status": "MISSING"},
    }
    packet["packet_hash"] = digest(packet)
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(packet))
    result = validate_postclose_packet(path, ["SPY", "AAPL"], ["SPY"], "2026-09-10")
    assert result["missing_optional_etf_holdings"] == ["SPY"]
    packet["market"]["VXVCLS"]["status"] = "MISSING"
    packet.pop("packet_hash")
    packet["packet_hash"] = digest(packet)
    path.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="VXVCLS"):
        validate_postclose_packet(path, ["SPY", "AAPL"], ["SPY"], "2026-09-10")


def test_fred_future_values_and_missingness():
    rows = parse_fred(b"observation_date,DFF\n2026-09-08,3.5\n2026-09-09,.\n2026-09-10,9\n", "DFF")
    result = macro_metrics({"DFF": rows}, CUTOFF)
    assert result["DFF"]["value"] == 3.5
    assert result["VIXCLS"]["status"] == "MISSING"
    assert result["survey_fear_greed"]["value"] is None
    with pytest.raises(ValueError):
        parse_fred(b"<html>Forbidden</html>", "DFF")


def test_reference_distribution_has_coherent_events_quantiles_and_labels():
    for row in reference_scenarios(100, 20):
        probabilities = row["probabilities"]
        assert sum(probabilities.values()) == pytest.approx(1)
        assert all(0 <= v <= 1 for v in probabilities.values())
        quantiles = list(row["price_quantiles"].values())
        assert quantiles == sorted(quantiles)
        assert row["price_quantiles"]["0.5"] == 100
        assert row["probability_price_up"] == .5
        assert "UNCALIBRATED" in row["status"]
    assert reference_scenarios(100, 0) == []


def test_snapshot_tamper_and_future_receipt_rejected(tmp_path, prices):
    (tmp_path/"raw").mkdir()
    receipt = archive(tmp_path, "price-SPY", "https://example.com", json.dumps(prices).encode(),
                      kind="ibkr_daily", received_at=CUTOFF.isoformat(), adjustment="split", feed="test")
    snapshot = {"version": VERSION, "as_of": CUTOFF.isoformat(), "symbols": ["SPY"], "etfs": ["SPY"],
                "sources": {"price-SPY": receipt}, "acquisition_errors": {}}
    snapshot["snapshot_hash"] = digest(snapshot)
    path = tmp_path/"snapshot.json"
    path.write_text(json.dumps(snapshot))
    run = build(path, tmp_path/"output")
    packet = json.loads((run/"packet.json").read_text())
    assert packet["instruments"]["SPY"]["status"] == "FRESH"
    assert packet["fundamental_coverage"]["SPY"] == "MISSING"
    assert packet["calibrated_forecast"] is None
    snapshot["sources"]["price-SPY"]["retrieved_at"] = "2026-09-10T00:00:00+00:00"
    snapshot.pop("snapshot_hash")
    snapshot["snapshot_hash"] = digest(snapshot)
    path.write_text(json.dumps(snapshot))
    with pytest.raises(ValueError, match="receipt"):
        load_snapshot(path)
    (tmp_path/receipt["path"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        load_snapshot(path)


def packet_fixture():
    packet = {"symbols": ["SPY", "QQQ"], "as_of": CUTOFF.isoformat(), "evidence": {"DFF": {}},
              "instruments": {"SPY": {}, "QQQ": {}}}
    packet["packet_hash"] = digest(packet)
    return packet


def response(request):
    result = {"role": request["role"], "input_hash": request["input_hash"], "assessments": [
        {"symbol": s, "status": "INSUFFICIENT_EVIDENCE", "view": "UNKNOWN", "thesis": "Missing evidence",
         "counterevidence": [], "invalidation": [], "missing": ["filings"], "claims": []}
        for s in request["packet"]["symbols"]]}
    if request["role"] == "synthesis":
        result["golden_conclusions"] = golden_fixture(request["packet"]["symbols"])
    return result


def golden_fixture(symbols):
    return {"executive_summary": "Evidence is insufficient; retain conditional posture.",
            "market_regime": {"summary": "Unknown regime", "supporting_claim_ids": [],
                              "invalidation": "New evidence changes the regime."},
            "critical_conclusions": [{"conclusion": "Current evidence is incomplete.",
                "importance": "CRITICAL", "scopes": ["MARKET"], "horizons": [5, 21, 63],
                "supporting_claim_ids": [], "invalidation": "Complete evidence arrives."}],
            "cross_symbol_priorities": [{"rank": rank, "symbol": symbol, "stance": "UNKNOWN",
                "horizons": [5, 21, 63], "rationale": "Insufficient evidence",
                "supporting_claim_ids": [], "conditions": ["Acquire sources"],
                "invalidation": ["Validated evidence arrives"]}
                for rank, symbol in enumerate(symbols, 1)],
            "immediate_review_triggers": ["New validated evidence"],
            "evidence_limitations": ["Fixture has no claims"]}


def claim(claim_id, evidence_id, *, statement="Supported fixture", numeric_values=None):
    return {"claim_id": claim_id, "classification": "FACT", "statement": statement,
            "evidence_ids": [evidence_id], "horizons": [5, 21, 63],
            "invalidation": "A newer packet supersedes this claim",
            "numeric_values": numeric_values or []}


def v3_horizons(*, direction="UNKNOWN", claim_id=None, missing=True):
    unavailable_trigger = {"availability": "UNAVAILABLE", "field": "UNAVAILABLE",
        "comparison": "UNAVAILABLE", "level": None, "units": "UNAVAILABLE",
        "confirmation_interval": "UNAVAILABLE", "expiry": "UNAVAILABLE", "evidence_ids": []}
    return [{"trading_days": horizon,
             "status": "INSUFFICIENT_EVIDENCE" if missing else "SUPPORTED",
             "direction": "UNKNOWN" if missing else direction,
             "strongest_support_claim_ids": [claim_id] if claim_id else [],
             "strongest_opposition_claim_ids": [], "action_implication": "Wait for evidence" if missing else "Monitor",
             "confirmation": unavailable_trigger, "invalidation_trigger": unavailable_trigger,
             "missing_evidence": ([{"item": "coverage", "criticality": "CRITICAL"}] if missing else []),
             "review": {"when": "next close", "event": "new evidence"}}
            for horizon in (5, 21, 63)]


def v3_empty_assessment(symbol):
    return {"symbol": symbol, "status": "INSUFFICIENT_EVIDENCE", "view": "UNKNOWN",
            "thesis": "Insufficient evidence", "counterevidence": [], "invalidation": [],
            "missing": ["coverage"], "claims": [], "horizon_assessments": v3_horizons()}


def test_v3_contract_enforces_horizon_claim_decisions_and_frozen_astra_actions():
    from spy_predictor_quant.meta_forecast import build_structured_forecast, load_policy

    packet = packet_fixture()
    packet.update({"version": "meta-analysis-v1",
                   "transparent_risk_appetite": {"value": 50},
                   "evidence": {"spy-price": {"kind": "alpaca_daily", "symbols": ["SPY"]}},
                   "instruments": {"SPY": {"status": "FRESH", "latest_close": 100.0,
                       "price_date": "2026-09-09", "realized_vol63_pct": 20.0,
                       "price_to_sma20": 1.01, "price_to_sma50": 1.01,
                       "price_to_sma200": 1.01, "return21_pct": 1.0, "return63_pct": 2.0},
                       "QQQ": {}}})
    packet.pop("packet_hash")
    packet["packet_hash"] = digest(packet)
    specialist_request = request_for("technical", packet)
    assert specialist_request["agent_contract_version"] == "meta-agent-output-v4"
    specialist_claim = claim("trend", "spy-price") | {"stance": "SUPPORT", "evidence_family": "price_trend"}
    specialist = {"role": "technical", "input_hash": specialist_request["input_hash"],
                  "assessments": [{"symbol": "SPY", "status": "SUPPORTED", "view": "BULLISH",
                      "thesis": "Trend support", "counterevidence": [], "invalidation": ["break"],
                      "missing": [], "claims": [specialist_claim],
                      "horizon_assessments": v3_horizons(direction="BULLISH", claim_id="trend", missing=False)},
                      v3_empty_assessment("QQQ")]}
    validate_output(specialist, specialist_request)
    invalid_specialist = deepcopy(specialist)
    invalid_specialist["assessments"][0]["claims"][0]["numeric_values"] = [
        {"packet_path": "/instruments/SPY/not_a_field", "value": 1.0}]
    findings = validate_output(invalid_specialist, specialist_request,
                               allow_deterministic_claim_rejections=True)
    assert findings == [{"claim_ref": "technical:trend",
                         "reason": "NUMERIC_VALUE_OR_PACKET_PATH_MISMATCH"}]
    with pytest.raises(ValueError):
        validate_output(invalid_specialist, specialist_request)
    previous = {"results": {"technical": specialist}, "failures": {}}
    critic_request = request_for("critic", packet, previous)
    critic = {"role": "critic", "input_hash": critic_request["input_hash"],
              "assessments": [v3_empty_assessment("SPY"), v3_empty_assessment("QQQ")],
              "claim_decisions": [{"claim_ref": "technical:trend", "decision": "ACCEPT",
                                   "materiality": "MATERIAL", "reason": "Matches packet", "correction": None}],
              "audit_summary": {"accepted_claims": 1, "rejected_claims": 0,
                  "needs_verification_claims": 0, "material_restrictions": [],
                  "summary": "All submitted claims were audited."}}
    validate_output(critic, critic_request)
    critic_with_non_signal_horizon_prose = deepcopy(critic)
    critic_with_non_signal_horizon_prose["assessments"][0]["horizon_assessments"] = (
        v3_horizons(direction="BULLISH", missing=False))
    validate_output(critic_with_non_signal_horizon_prose, critic_request)
    critic_schema = critic_request["output_schema"]
    strict_object_defects = []
    def check_strict_objects(value, path="$schema"):
        if isinstance(value, dict):
            if value.get("type") == "object":
                properties = value.get("properties", {})
                if (value.get("additionalProperties") is not False
                        or set(value.get("required", [])) != set(properties)):
                    strict_object_defects.append(path)
            for key, child in value.items():
                check_strict_objects(child, f"{path}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                check_strict_objects(child, f"{path}/{index}")
    check_strict_objects(critic_schema)
    assert strict_object_defects == []
    bad_summary = deepcopy(critic)
    bad_summary["audit_summary"]["accepted_claims"] = 0
    with pytest.raises(ValueError, match="summary counts"):
        validate_output(bad_summary, critic_request)
    forced_request = request_for("critic", packet, previous | {
        "deterministic_claim_rejections": findings})
    forced_critic = deepcopy(critic)
    forced_critic["input_hash"] = forced_request["input_hash"]
    forced_critic["claim_decisions"][0]["decision"] = "ACCEPT"
    with pytest.raises(ValueError, match="must reject"):
        validate_output(forced_critic, forced_request)
    report = {"packet_hash": packet["packet_hash"], "completed_at": packet["as_of"],
              "runtime_config_hash": "runtime", "harness_implementation_sha256": "harness",
              "validation": "META_AGENT_V3_HORIZON_DECISIONS_AND_CRITIC_CLAIM_GATES",
              "results": {"technical": specialist, "critic": critic}, "failures": {}}
    numerical = build_structured_forecast(packet, report, load_policy())
    synthesis_request = request_for("synthesis", packet, {"results": report["results"],
        "failures": {}, "numerical_forecast": numerical, "accepted_claim_refs": ["technical:trend"]})
    decision_rows = []
    for index, row in enumerate(numerical["symbols"]["SPY"]["horizons"]):
        decision_rows.append({"symbol": "SPY", "trading_days": row["trading_days"],
            "action_now": row["recommendation"]["action_now"],
            "new_position_action": row["recommendation"]["new_position_action"],
            "existing_position_action": row["recommendation"]["existing_position_action"],
            "probability_price_up": row["distribution"]["probability_price_up"],
            "forecast_ref": f"/symbols/SPY/horizons/{index}",
            "explanation": "The deterministic gate requires waiting.",
            "what_changes_action": "More accepted evidence", "what_could_go_wrong": "Model error"})
    synthesis = {"role": "synthesis", "input_hash": synthesis_request["input_hash"],
                 "assessments": [v3_empty_assessment("SPY"), v3_empty_assessment("QQQ")],
                 "golden_conclusions": {"overall_conclusion": "Wait for complete coverage.",
                     "market_regime": "Insufficient evidence", "critical_findings": ["Coverage is incomplete"],
                     "decision_rows": decision_rows,
                     "research_priorities": [{"symbol": symbol, "priority": 1,
                         "buy_attractiveness": "UNKNOWN", "rationale": "Incomplete"}
                         for symbol in packet["symbols"]],
                     "immediate_review_triggers": ["New evidence"],
                     "evidence_limitations": ["Only technical evidence"],
                     "new_material_contradiction": None}}
    validate_output(synthesis, synthesis_request)
    changed = deepcopy(synthesis)
    changed["golden_conclusions"]["decision_rows"][0]["probability_price_up"] += .01
    with pytest.raises(Exception):
        validate_output(changed, synthesis_request)


def test_only_exact_duplicate_specialist_assessments_are_normalized():
    row = v3_empty_assessment("SPY")
    result = {"role": "fundamental", "input_hash": "fixture",
              "assessments": [row, deepcopy(row)]}
    normalized, findings = _normalize_exact_duplicate_assessments(result, "fundamental")
    assert normalized["assessments"] == [row]
    assert findings == [{"claim_ref": None, "symbol": "SPY", "trading_days": None,
                         "reason": "EXACT_DUPLICATE_ASSESSMENT_REMOVED"}]
    conflicting = deepcopy(row)
    conflicting["thesis"] = "Different conclusion"
    unchanged, findings = _normalize_exact_duplicate_assessments(
        {**result, "assessments": [row, conflicting]}, "fundamental")
    assert unchanged["assessments"] == [row, conflicting]
    assert findings == []


def test_role_packet_projections_are_deterministic_and_preserve_audit_closure():
    packet = packet_fixture()
    packet.update({
        "market": {"DFF": {"source_ids": ["macro"]}},
        "company_fundamentals": {"SPY": {}},
        "etf_holdings": {"SPY": {}},
        "evidence": {
            "price": {"kind": "alpaca_daily", "symbols": ["SPY"]},
            "macro": {"kind": "fred_csv", "symbols": []},
            "filing": {"kind": "filing", "symbols": ["SPY"]},
            "article": {"kind": "news", "symbols": ["SPY"]},
            "policy": {"kind": "policy", "symbols": ["SPY"]},
        },
    })
    assert project_packet("technical", packet) == project_packet("technical", packet)
    assert set(project_packet("technical", packet)["evidence"]) == {"price"}
    assert set(project_packet("macro_cycle", packet)["evidence"]) == {"macro", "policy"}
    assert set(project_packet("fundamental", packet)["evidence"]) == {"filing"}
    assert set(project_packet("news", packet)["evidence"]) == {"article"}
    assert set(project_packet("geopolitical", packet)["evidence"]) == {"article", "filing", "policy"}
    assert set(project_packet("critic", packet)["evidence"]) == set(packet["evidence"])
    previous = {"results": {"technical": {"assessments": [{"evidence_ids": ["price"]}]},
                            "news": {"assessments": [{"evidence_ids": ["article"]}]}}}
    synthesis = project_packet("synthesis", packet, previous)
    assert set(synthesis["evidence"]) == {"price", "article"}
    assert synthesis["source_packet_hash"] == packet["packet_hash"]


def test_agent_wrong_packet_citations_duplicates_and_false_support_rejected():
    request = request_for("fundamental", packet_fixture())
    result = response(request)
    validate_output(result, request)
    for mutation in ("hash", "citation", "duplicate", "false_support"):
        bad = deepcopy(result)
        if mutation == "hash":
            bad["input_hash"] = "other"
        elif mutation == "citation":
            bad["assessments"][0].update(status="SUPPORTED", view="NEUTRAL", missing=[],
                                          claims=[claim("c1", "invented")])
        elif mutation == "duplicate":
            bad["assessments"][1]["symbol"] = "SPY"
        else:
            bad["assessments"][0]["status"] = "SUPPORTED"
        with pytest.raises(Exception):
            validate_output(bad, request)


def test_agent_schema_exposes_cross_field_abstention_rules():
    request = request_for("technical", packet_fixture())
    result = response(request)
    result["assessments"][0]["missing"] = []
    with pytest.raises(Exception):
        Draft202012Validator(request["output_schema"]).validate(result)


def test_claim_level_evidence_relevance_and_numeric_paths_are_validated():
    packet = packet_fixture()
    packet["evidence"] = {
        "spy-price": {"kind": "alpaca_daily", "symbols": ["SPY"]},
        "qqq-price": {"kind": "alpaca_daily", "symbols": ["QQQ"]},
    }
    packet["instruments"]["SPY"] = {"status": "FRESH", "latest_close": 123.45}
    packet.pop("packet_hash")
    packet["packet_hash"] = digest(packet)
    request = request_for("technical", packet)
    result = response(request)
    result["assessments"][0].update(
        status="SUPPORTED", view="BULLISH", missing=[],
        claims=[claim("spy-close", "spy-price", numeric_values=[
            {"packet_path": "/instruments/SPY/latest_close", "value": 123.45}])],
    )
    validate_output(result, request)
    wrong_value = deepcopy(result)
    wrong_value["assessments"][0]["claims"][0]["numeric_values"][0]["value"] = 999
    with pytest.raises(ValueError, match="numeric value"):
        validate_output(wrong_value, request)
    wrong_symbol = deepcopy(result)
    wrong_symbol["assessments"][0]["claims"][0]["evidence_ids"] = ["qqq-price"]
    with pytest.raises(ValueError, match="not relevant"):
        validate_output(wrong_symbol, request)
    result = response(request)
    result["assessments"][0].update(status="INSUFFICIENT_EVIDENCE", view="NEUTRAL")
    with pytest.raises(Exception):
        Draft202012Validator(request["output_schema"]).validate(result)


def test_synthesis_may_compare_requested_symbol_prices_but_not_unrelated_news():
    packet = packet_fixture()
    packet["evidence"] = {
        "spy-price": {"kind": "alpaca_daily", "symbols": ["SPY"]},
        "qqq-price": {"kind": "alpaca_daily", "symbols": ["QQQ"]},
        "qqq-news": {"kind": "news", "symbols": ["QQQ"]},
    }
    packet.pop("packet_hash")
    packet["packet_hash"] = digest(packet)
    prior = {"results": {"technical": {"assessments": [{"claims": [
        {"evidence_ids": ["spy-price", "qqq-price", "qqq-news"]}]}]}}}
    request = request_for("synthesis", packet, prior)
    result = response(request)
    result["assessments"][0].update(
        status="SUPPORTED", view="MIXED", missing=[],
        claims=[claim("cross-price", "qqq-price")])
    result["golden_conclusions"]["market_regime"]["supporting_claim_ids"] = ["cross-price"]
    validate_output(result, request)
    result["assessments"][0]["claims"][0]["evidence_ids"] = ["qqq-news"]
    with pytest.raises(ValueError, match="not relevant"):
        validate_output(result, request)


def test_external_evidence_later_than_cutoff_rejected():
    item = {"id": "ext-test", "url": "https://example.com", "kind": "filing", "text": "example",
            "symbols": ["SPY"], "published_at": "2026-09-09T20:00:00+00:00",
            "retrieved_at": "2026-09-10T00:00:00+00:00"}
    with pytest.raises(ValueError, match="timing"):
        validate_external([item], CUTOFF)


def test_macro_citation_cannot_qualify_missing_company_fundamentals():
    request = request_for("fundamental", packet_fixture())
    result = response(request)
    result["assessments"][0].update(status="SUPPORTED", view="BULLISH", missing=[],
                                     claims=[claim("macro", "DFF")])
    # Role projection removes macro-only IDs before schema validation.
    with pytest.raises(Exception):
        validate_output(result, request)


def test_news_support_requires_direct_or_holdings_linked_evidence():
    packet = packet_fixture()
    packet["evidence"] = {
        "direct": {"kind": "news", "symbols": ["SPY"]},
        "indirect": {"kind": "news", "symbols": ["NVDA"],
                     "indirect_etf_exposure_weight_pct": {"QQQ": [{"holding": "NVDA", "weight_pct": 8}]}},
    }
    packet.pop("packet_hash")
    packet["packet_hash"] = digest(packet)
    request = request_for("news", packet)
    result = response(request)
    result["assessments"][0].update(status="SUPPORTED", view="NEUTRAL", missing=[],
                                     claims=[claim("direct-claim", "direct")])
    result["assessments"][1].update(status="SUPPORTED", view="MIXED", missing=[],
                                     claims=[claim("indirect-claim", "indirect")])
    validate_output(result, request)
    result["assessments"][1]["claims"][0]["evidence_ids"] = ["direct"]
    with pytest.raises(ValueError, match="relevant"):
        validate_output(result, request)


def test_orchestration_stages_and_failure_visibility(tmp_path):
    # This local fixture exercises process I/O and staging, without any model/network call.
    script = tmp_path/"runner.py"
    script.write_text('''import json, sys
r = json.load(sys.stdin)
if r['role'] == 'news':
    sys.exit(2)
if r['role'] == 'critic':
    assert len(r['prior_results']['results']) == 4
    assert 'news' in r['prior_results']['failures']
if r['role'] == 'synthesis':
    assert 'critic' in r['prior_results']['results']
rows = [dict(symbol=s, status='INSUFFICIENT_EVIDENCE', view='UNKNOWN', thesis='Fixture only',
counterevidence=[], invalidation=[], missing=['sources'], claims=[]) for s in r['packet']['symbols']]
result = dict(role=r['role'], input_hash=r['input_hash'], assessments=rows)
if r['role'] == 'synthesis':
    result['golden_conclusions'] = dict(executive_summary='Fixture', market_regime=dict(summary='Unknown', supporting_claim_ids=[], invalidation='New evidence'), critical_conclusions=[dict(conclusion='Incomplete', importance='CRITICAL', scopes=['MARKET'], horizons=[5,21,63], supporting_claim_ids=[], invalidation='New evidence')], cross_symbol_priorities=[dict(rank=i+1, symbol=s, stance='UNKNOWN', horizons=[5,21,63], rationale='Insufficient evidence', supporting_claim_ids=[], conditions=['Acquire evidence'], invalidation=['New evidence']) for i,s in enumerate(r['packet']['symbols'])], immediate_review_triggers=['New evidence'], evidence_limitations=['Fixture'])
print(json.dumps(result))
''')
    packet_path = tmp_path/"packet.json"
    packet_path.write_text(json.dumps(packet_fixture()))
    config = tmp_path/"runner.json"
    config.write_text(json.dumps({"argv": [sys.executable, str(script)], "model": "TEST_FIXTURE"}))
    output = run_agents(packet_path, config, tmp_path/"output")
    report = json.loads((output/"meta-report.json").read_text())
    assert report["status"] == "PARTIAL"
    assert report["failures"] == {"news": "CalledProcessError"}
    assert len(report["results"]) == 6
    assert report["calibrated_meta_forecast"] is None


def test_orchestration_role_models_and_receipts(tmp_path):
    script = tmp_path/"runner.py"
    script.write_text('''import json, sys
r = json.load(sys.stdin)
expected = 'openai-codex/gpt-5.6-sol' if r['role'] in {'critic', 'synthesis'} else 'openai-codex/gpt-5.6-terra'
assert r['runtime']['model'] == expected
rows = [dict(symbol=s, status='INSUFFICIENT_EVIDENCE', view='UNKNOWN', thesis='Fixture only',
counterevidence=[], invalidation=[], missing=['sources'], claims=[]) for s in r['packet']['symbols']]
result = dict(role=r['role'], input_hash=r['input_hash'], assessments=rows)
if r['role'] == 'synthesis':
    result['golden_conclusions'] = dict(executive_summary='Fixture', market_regime=dict(summary='Unknown', supporting_claim_ids=[], invalidation='New evidence'), critical_conclusions=[dict(conclusion='Incomplete', importance='CRITICAL', scopes=['MARKET'], horizons=[5,21,63], supporting_claim_ids=[], invalidation='New evidence')], cross_symbol_priorities=[dict(rank=i+1, symbol=s, stance='UNKNOWN', horizons=[5,21,63], rationale='Insufficient evidence', supporting_claim_ids=[], conditions=['Acquire evidence'], invalidation=['New evidence']) for i,s in enumerate(r['packet']['symbols'])], immediate_review_triggers=['New evidence'], evidence_limitations=['Fixture'])
receipt = dict(provider='openai-codex', requested_model=expected, input_tokens=10, output_tokens=5)
print(json.dumps(dict(result=result, receipt=receipt)))
''')
    packet_path = tmp_path/"packet.json"
    packet_path.write_text(json.dumps(packet_fixture()))
    config = tmp_path/"runner.json"
    config.write_text(json.dumps({
        "argv": [sys.executable, str(script)],
        "model": "openai-codex/gpt-5.6-terra",
        "models": {"critic": "openai-codex/gpt-5.6-sol", "synthesis": "openai-codex/gpt-5.6-sol"},
        "reasoning_effort": "medium",
    }))
    output = run_agents(packet_path, config, tmp_path/"output")
    report = json.loads((output/"meta-report.json").read_text())
    assert report["status"] == "COMPLETED_UNCALIBRATED_RESEARCH"
    assert json.loads((output/"technical-receipt.json").read_text())["requested_model"].endswith("terra")
    assert json.loads((output/"synthesis-receipt.json").read_text())["requested_model"].endswith("sol")


@pytest.mark.parametrize(
    ("missing_stage", "removed_roles", "expected_reused", "expected_executed"),
    [
        ("independent", {"technical"},
         {"macro_cycle", "fundamental", "news", "geopolitical"},
         {"technical", "critic", "synthesis"}),
        ("critic", {"critic"}, set(INDEPENDENT), {"critic", "synthesis"}),
        ("synthesis", {"synthesis"}, set(INDEPENDENT) | {"critic"}, {"synthesis"}),
    ],
)
def test_agent_resume_reuses_only_verified_dependency_complete_roles(
        tmp_path, missing_stage, removed_roles, expected_reused, expected_executed):
    log = tmp_path / "calls.log"
    script = tmp_path / "runner.py"
    script.write_text('''import json, pathlib, sys
r = json.load(sys.stdin)
with pathlib.Path(sys.argv[1]).open('a') as handle:
    handle.write(r['role'] + '\\n')
rows = [dict(symbol=s, status='INSUFFICIENT_EVIDENCE', view='UNKNOWN', thesis='Fixture only',
counterevidence=[], invalidation=[], missing=['sources'], claims=[]) for s in r['packet']['symbols']]
result = dict(role=r['role'], input_hash=r['input_hash'], assessments=rows)
if r['role'] == 'synthesis':
    result['golden_conclusions'] = dict(executive_summary='Fixture', market_regime=dict(summary='Unknown', supporting_claim_ids=[], invalidation='New evidence'), critical_conclusions=[dict(conclusion='Incomplete', importance='CRITICAL', scopes=['MARKET'], horizons=[5,21,63], supporting_claim_ids=[], invalidation='New evidence')], cross_symbol_priorities=[dict(rank=i+1, symbol=s, stance='UNKNOWN', horizons=[5,21,63], rationale='Insufficient evidence', supporting_claim_ids=[], conditions=['Acquire evidence'], invalidation=['New evidence']) for i,s in enumerate(r['packet']['symbols'])], immediate_review_triggers=['New evidence'], evidence_limitations=['Fixture'])
receipt = dict(provider='openai-codex', requested_model=r['runtime']['model'], input_tokens=1, output_tokens=1)
print(json.dumps(dict(result=result, receipt=receipt)))
''')
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet_fixture()))
    config = tmp_path / "runner.json"
    config.write_text(json.dumps({"argv": [sys.executable, str(script), str(log)],
                                  "model": "TEST_FIXTURE", "max_parallel": 1}))
    source = run_agents(packet_path, config, tmp_path / "output")
    for role in removed_roles:
        for path in source.glob(f"{role}-*"):
            path.unlink()
    (source / "meta-report.json").unlink()
    resumed = run_agents(packet_path, config, tmp_path / "output", source)
    report = json.loads((resumed / "meta-report.json").read_text())
    assert report["status"] == "COMPLETED_UNCALIBRATED_RESEARCH"
    assert set(report["reused_roles"]) == expected_reused
    assert set(report["newly_executed_roles"]) == expected_executed
    assert report["resumed_from"] == str(source.resolve())
    assert len(log.read_text().splitlines()) == 7 + len(expected_executed)
    assert source != resumed


def test_agent_resume_rejects_runtime_identity_change(tmp_path):
    script = tmp_path / "runner.py"
    script.write_text('''import json, sys
r = json.load(sys.stdin)
rows = [dict(symbol=s, status='INSUFFICIENT_EVIDENCE', view='UNKNOWN', thesis='Fixture',
counterevidence=[], invalidation=[], missing=['sources'], claims=[]) for s in r['packet']['symbols']]
result = dict(role=r['role'], input_hash=r['input_hash'], assessments=rows)
print(json.dumps(dict(result=result, receipt=dict(provider='openai-codex', requested_model=r['runtime']['model']))))
''')
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet_fixture()))
    config = tmp_path / "runner.json"
    config.write_text(json.dumps({"argv": [sys.executable, str(script)], "model": "TEST_FIXTURE",
                                  "roles": ["technical"]}))
    source = run_agents(packet_path, config, tmp_path / "output")
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps({"argv": [sys.executable, str(script)], "model": "OTHER_MODEL",
                                   "roles": ["technical"]}))
    with pytest.raises(ValueError, match="runtime configuration mismatch"):
        run_agents(packet_path, changed, tmp_path / "output", source)


@pytest.mark.parametrize("incomplete", ["missing_receipt", "truncated_stdout"])
def test_agent_resume_refuses_incomplete_role_reuse(tmp_path, incomplete):
    log = tmp_path / "calls.log"
    script = tmp_path / "runner.py"
    script.write_text('''import json, pathlib, sys
r = json.load(sys.stdin)
with pathlib.Path(sys.argv[1]).open('a') as handle: handle.write(r['role'] + '\\n')
rows = [dict(symbol=s, status='INSUFFICIENT_EVIDENCE', view='UNKNOWN', thesis='Fixture',
counterevidence=[], invalidation=[], missing=['sources'], claims=[]) for s in r['packet']['symbols']]
result = dict(role=r['role'], input_hash=r['input_hash'], assessments=rows)
receipt = dict(provider='openai-codex', requested_model=r['runtime']['model'])
print(json.dumps(dict(result=result, receipt=receipt)))
''')
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet_fixture()))
    config = tmp_path / "runner.json"
    config.write_text(json.dumps({"argv": [sys.executable, str(script), str(log)],
                                  "model": "TEST_FIXTURE", "roles": ["technical"]}))
    source = run_agents(packet_path, config, tmp_path / "output")
    (source / "meta-report.json").unlink()
    if incomplete == "missing_receipt":
        (source / "technical-receipt.json").unlink()
    else:
        stdout = source / "technical-stdout.txt"
        stdout.write_text(stdout.read_text()[:-2])
    resumed = run_agents(packet_path, config, tmp_path / "output", source)
    report = json.loads((resumed / "meta-report.json").read_text())
    assert report["reused_roles"] == []
    assert report["newly_executed_roles"] == ["technical"]
    assert log.read_text().splitlines() == ["technical", "technical"]


def test_orchestration_can_gate_selected_stages(tmp_path):
    script = tmp_path/"runner.py"
    script.write_text('''import json, sys
r = json.load(sys.stdin)
if r['role'] == 'critic':
    assert set(r['prior_results']['results']) == {'technical'}
rows = [dict(symbol=s, status='INSUFFICIENT_EVIDENCE', view='UNKNOWN', thesis='Gate fixture',
counterevidence=[], invalidation=[], missing=['sources'], claims=[]) for s in r['packet']['symbols']]
print(json.dumps(dict(role=r['role'], input_hash=r['input_hash'], assessments=rows)))
''')
    packet_path = tmp_path/"packet.json"
    packet_path.write_text(json.dumps(packet_fixture()))
    config = tmp_path/"runner.json"
    config.write_text(json.dumps({
        "argv": [sys.executable, str(script)], "model": "TEST_FIXTURE",
        "roles": ["technical", "critic"],
    }))
    output = run_agents(packet_path, config, tmp_path/"output")
    report = json.loads((output/"meta-report.json").read_text())
    assert report["status"] == "COMPLETED_STAGE_GATE"
    assert report["executed_roles"] == ["technical", "critic"]
    assert set(report["results"]) == {"technical", "critic"}


def test_orchestration_stops_dependent_stages_after_failure(tmp_path):
    script = tmp_path/"runner.py"
    script.write_text('''import json, sys
r = json.load(sys.stdin)
if r['role'] == 'news':
    sys.exit(2)
if r['role'] in {'critic', 'synthesis'}:
    raise AssertionError('dependent stage must not run')
rows = [dict(symbol=s, status='INSUFFICIENT_EVIDENCE', view='UNKNOWN', thesis='Fixture only',
counterevidence=[], invalidation=[], missing=['sources'], claims=[]) for s in r['packet']['symbols']]
print(json.dumps(dict(role=r['role'], input_hash=r['input_hash'], assessments=rows)))
''')
    packet_path = tmp_path/"packet.json"
    packet_path.write_text(json.dumps(packet_fixture()))
    config = tmp_path/"runner.json"
    config.write_text(json.dumps({
        "argv": [sys.executable, str(script)], "model": "TEST_FIXTURE",
        "on_stage_failure": "stop",
    }))
    output = run_agents(packet_path, config, tmp_path/"output")
    report = json.loads((output/"meta-report.json").read_text())
    assert report["status"] == "PARTIAL"
    assert report["failures"] == {"news": "CalledProcessError"}
    assert report["skipped_roles"] == ["critic", "synthesis"]
    assert report["executed_roles"] == list(INDEPENDENT)
    assert not (output/"critic-request.json").exists()
    assert not (output/"synthesis-request.json").exists()


def test_agent_timeout_signals_entire_process_group(tmp_path):
    marker = tmp_path/"child-stopped"
    runner = tmp_path/"runner.py"
    runner.write_text('''import json, signal, subprocess, sys, time
json.load(sys.stdin)
child = "import pathlib,signal,sys,time; signal.signal(signal.SIGTERM, lambda *_: (pathlib.Path(sys.argv[1]).write_text('stopped'), sys.exit(0))); time.sleep(60)"
subprocess.Popen([sys.executable, '-c', child, sys.argv[1]])
signal.signal(signal.SIGTERM, signal.SIG_IGN)
time.sleep(60)
''')
    packet_path = tmp_path/"packet.json"
    packet_path.write_text(json.dumps(packet_fixture()))
    config = tmp_path/"runner.json"
    config.write_text(json.dumps({
        "argv": [sys.executable, str(runner), str(marker)], "model": "TEST_FIXTURE",
        "roles": ["technical"], "timeout_seconds": 1,
    }))
    started = time.monotonic()
    output = run_agents(packet_path, config, tmp_path/"output")
    report = json.loads((output/"meta-report.json").read_text())
    assert time.monotonic() - started < 7
    assert marker.read_text() == "stopped"
    assert report["failures"] == {"technical": "TimeoutExpired"}


def test_operator_signal_archives_cancellation_receipt(tmp_path):
    runner = tmp_path/"runner.py"
    runner.write_text("import json,sys,time; from pathlib import Path; json.load(sys.stdin); "
                      "Path(__file__).with_suffix('.started').write_text('ready'); time.sleep(60)")
    packet_path = tmp_path/"packet.json"
    packet_path.write_text(json.dumps(packet_fixture()))
    config = tmp_path/"runner.json"
    config.write_text(json.dumps({
        "argv": [sys.executable, str(runner)], "model": "TEST_FIXTURE",
        "roles": ["technical"],
    }))
    invoke = tmp_path/"invoke.py"
    invoke.write_text('''import sys
from pathlib import Path
from spy_predictor_quant.meta_agents import run_agents
run_agents(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
''')
    output_root = tmp_path/"output"
    process = subprocess.Popen([sys.executable, str(invoke), str(packet_path), str(config), str(output_root)])
    deadline = time.monotonic() + 10
    request_paths = []
    while time.monotonic() < deadline:
        request_paths = list(output_root.glob("agents-*/technical-request.json"))
        # A written request precedes Popen/active-role registration. Wait until
        # the child reads stdin, which occurs after the runner records it active.
        if request_paths and runner.with_suffix('.started').exists():
            break
        time.sleep(.05)
    assert request_paths and runner.with_suffix('.started').exists()
    os.kill(process.pid, signal.SIGTERM)
    assert process.wait(timeout=10) != 0
    run = request_paths[0].parent
    receipt = json.loads((run/"cancellation.json").read_text())
    assert receipt["status"] == "CANCELLED_BY_OPERATOR"
    assert receipt["signal"] == "SIGTERM"
    assert receipt["initiated_roles"] == ["technical"]
    assert receipt["active_roles_at_cancellation"] == ["technical"]
    assert not (run/"meta-report.json").exists()


def test_on_demand_analysis_runs_whole_lane_without_registration(tmp_path, monkeypatch):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text("{}")
    analysis_run = tmp_path / "analysis"
    analysis_run.mkdir()
    packet = {
        "as_of": CUTOFF.isoformat(), "symbols": ["SPY"], "etfs": ["SPY"],
        "operating_context": {"market_period": "REGULAR", "price_basis": "LATEST_COMPLETED_CLOSE"},
        "instruments": {"SPY": {"status": "FRESH", "latest_close": 100, "price_date": "2026-09-08"}},
    }
    packet["packet_hash"] = digest(packet)
    (analysis_run / "packet.json").write_text(json.dumps(packet))
    agent_run = tmp_path / "agents"
    agent_run.mkdir()
    assessment = {"symbol": "SPY", "status": "INSUFFICIENT_EVIDENCE", "view": "UNKNOWN",
                  "thesis": "Fixture", "counterevidence": [], "invalidation": [],
                  "missing": ["sources"], "claims": []}
    agent_report = {"packet_hash": packet["packet_hash"],
                    "completed_at": CUTOFF.isoformat(),
                    "runtime_config_hash": "fixture", "harness_implementation_sha256": "fixture",
                    "validation": "SCHEMA_CLAIM_CITATION_AND_NUMERIC_PATHS;SEMANTIC_CLAIMS_REQUIRE_REVIEW",
                    "status": "COMPLETED_UNCALIBRATED_RESEARCH", "failures": {},
                    "results": {"synthesis": {"assessments": [assessment]}}}
    (agent_run / "meta-report.json").write_text(json.dumps(agent_report))
    calls = []
    monkeypatch.setattr(meta_analysis, "capture", lambda *args, **kwargs: calls.append("capture") or snapshot)
    monkeypatch.setattr(meta_analysis, "build", lambda *args, **kwargs: calls.append("build") or analysis_run)
    import spy_predictor_quant.meta_agents as meta_agents
    monkeypatch.setattr(meta_agents, "run_agents", lambda *args, **kwargs: calls.append("agents") or agent_run)
    import spy_predictor_quant.meta_observation as meta_observation
    monkeypatch.setattr(meta_observation, "register",
                        lambda *args, **kwargs: pytest.fail("on-demand lane must not register"))
    runner_config = tmp_path / "runner.json"
    runner_config.write_text("{}")
    receipt = analyze(["SPY"], ["SPY"], runner_config=runner_config,
                      capture_root=tmp_path, analysis_root=tmp_path)
    assert calls == ["capture", "build", "agents"]
    assert receipt["prospective_registration"] is False
    assert receipt["market_period"] == "REGULAR"
    assert receipt["price_basis"] == "LATEST_COMPLETED_CLOSE"
    assert receipt["probability_status"] == "EXPERIMENTAL_UNCALIBRATED"
    assert (agent_run / "structured-forecast.json").is_file()
    assert (agent_run / "on-demand-report.md").is_file()
    assert (agent_run / "on-demand-receipt.json").is_file()


def test_on_demand_intraday_mode_reaches_capture_with_explicit_free_feed(tmp_path, monkeypatch):
    config = tmp_path / "runner.json"
    config.write_text("{}")
    captured = []
    def stop_after_capture(*args, **kwargs):
        captured.append((args, kwargs))
        raise RuntimeError("stop fixture")
    monkeypatch.setattr(meta_analysis, "capture", stop_after_capture)
    with pytest.raises(RuntimeError, match="stop fixture"):
        analyze(["SPY"], ["SPY"], runner_config=config, market_data_mode="intraday")
    assert captured[0][0][-2:] == ("intraday", "iex")


def test_cli_marks_partial_agent_chains_as_failures(tmp_path):
    assert _cli_exit_status("analyze", {"status": "PARTIAL"}) == 1
    assert _cli_exit_status("analyze", {"status": "COMPLETED"}) == 0
    partial = tmp_path / "partial-agents"
    partial.mkdir()
    (partial / "meta-report.json").write_text(json.dumps({"status": "PARTIAL"}))
    assert _cli_exit_status("agents", partial) == 1
    complete = tmp_path / "complete-agents"
    complete.mkdir()
    (complete / "meta-report.json").write_text(
        json.dumps({"status": "COMPLETED_UNCALIBRATED_RESEARCH"}))
    assert _cli_exit_status("agents", complete) == 0
