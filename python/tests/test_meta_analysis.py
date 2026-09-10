from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from urllib.error import HTTPError

import exchange_calendars as xcals
import numpy as np
import pytest

from spy_predictor_quant.meta_analysis import (
    archive, build, daily_metrics, digest, load_snapshot, macro_metrics,
    parse_fred, reference_scenarios, SecHttpClient, transparent_risk_appetite,
    postclose_preflight, SERIES, validate_delayed_context, validate_external,
    validate_postclose_packet, VERSION,
)
import spy_predictor_quant.meta_analysis as meta_analysis
from spy_predictor_quant.meta_agents import request_for, run_agents, validate_output

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
    return {"role": request["role"], "input_hash": request["input_hash"], "assessments": [
        {"symbol": s, "status": "INSUFFICIENT_EVIDENCE", "view": "UNKNOWN", "thesis": "Missing evidence",
         "counterevidence": [], "invalidation": [], "missing": ["filings"], "evidence_ids": []}
        for s in request["packet"]["symbols"]]}


def test_agent_wrong_packet_citations_duplicates_and_false_support_rejected():
    request = request_for("fundamental", packet_fixture())
    result = response(request)
    validate_output(result, request)
    for mutation in ("hash", "citation", "duplicate", "false_support"):
        bad = deepcopy(result)
        if mutation == "hash":
            bad["input_hash"] = "other"
        elif mutation == "citation":
            bad["assessments"][0]["evidence_ids"] = ["invented"]
        elif mutation == "duplicate":
            bad["assessments"][1]["symbol"] = "SPY"
        else:
            bad["assessments"][0]["status"] = "SUPPORTED"
        with pytest.raises(Exception):
            validate_output(bad, request)


def test_external_evidence_later_than_cutoff_rejected():
    item = {"id": "ext-test", "url": "https://example.com", "kind": "filing", "text": "example",
            "symbols": ["SPY"], "published_at": "2026-09-09T20:00:00+00:00",
            "retrieved_at": "2026-09-10T00:00:00+00:00"}
    with pytest.raises(ValueError, match="timing"):
        validate_external([item], CUTOFF)


def test_macro_citation_cannot_qualify_missing_company_fundamentals():
    request = request_for("fundamental", packet_fixture())
    result = response(request)
    result["assessments"][0].update(status="SUPPORTED", view="BULLISH", evidence_ids=["DFF"])
    with pytest.raises(ValueError, match="instrument-specific"):
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
    result["assessments"][0].update(status="SUPPORTED", view="NEUTRAL", evidence_ids=["direct"])
    result["assessments"][1].update(status="SUPPORTED", view="MIXED", evidence_ids=["indirect"])
    validate_output(result, request)
    result["assessments"][1]["evidence_ids"] = ["direct"]
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
counterevidence=[], invalidation=[], missing=['sources'], evidence_ids=[]) for s in r['packet']['symbols']]
print(json.dumps(dict(role=r['role'], input_hash=r['input_hash'], assessments=rows)))
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
