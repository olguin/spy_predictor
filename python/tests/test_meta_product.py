from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from spy_predictor_quant.market_archive import file_sha256
from spy_predictor_quant.meta_analysis import digest, reference_scenarios
from spy_predictor_quant.meta_product import (
    ProductHandler, build_product_view, render_html, render_markdown, serve,
    write_product_bundle,
)


NOW = datetime(2026, 9, 14, 20, 26, tzinfo=timezone.utc)


def artifacts(tmp_path, *, failed=False):
    packet = {"version": "meta-analysis-v1", "as_of": "2026-09-14T20:25:00+00:00",
              "symbols": ["SPY"], "etfs": [], "acquisition_errors": {},
              "supplemental_acquisition_errors": {},
              "instruments": {"SPY": {"status": "FRESH", "price_date": "2026-09-14",
                  "latest_close": 100.0, "realized_vol63_pct": 20,
                  "return21_pct": 2, "return63_pct": 5, "price_to_sma200": 1.02,
                  "reference_scenarios": reference_scenarios(100, 20)}},
              "market": {"DFF": {"status": "FRESH", "observed_date": "2026-09-13",
                                    "value": 3.5, "unit": "percent"}},
              "company_fundamentals": {"SPY": {"latest_period": "2026-Q2"}},
              "fundamental_coverage": {"SPY": "AVAILABLE"}}
    packet["packet_hash"] = digest(packet)
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet))
    assessment = {"symbol": "SPY", "status": "SUPPORTED", "view": "BULLISH",
                  "thesis": "<script>not executable</script>", "counterevidence": [],
                  "invalidation": [], "missing": [], "claims": []}
    results = {role: {"assessments": [assessment]} for role in
               ("macro_cycle", "technical", "fundamental", "news", "geopolitical", "critic", "synthesis")}
    results["synthesis"]["golden_conclusions"] = {
        "executive_summary": "Astra summary <script>blocked</script>",
        "market_regime": {"summary": "Constructive but conditional",
                          "supporting_claim_ids": [], "invalidation": "Breadth fails"},
        "critical_conclusions": [{"conclusion": "Protect against volatility",
                                  "importance": "CRITICAL", "scopes": ["MARKET", "SPY"],
                                  "horizons": [5, 21], "supporting_claim_ids": [],
                                  "invalidation": "Volatility normalizes"}],
        "cross_symbol_priorities": [{"rank": 1, "symbol": "SPY", "stance": "BULLISH",
                                     "horizons": [5, 21, 63], "rationale": "Test rationale",
                                     "supporting_claim_ids": [], "conditions": ["Breadth holds"],
                                     "invalidation": ["Breadth fails"]}],
        "immediate_review_triggers": ["Volatility spike"],
        "evidence_limitations": ["Fixture evidence"],
    }
    report = {"packet_hash": packet["packet_hash"], "completed_at": NOW.isoformat(),
              "results": results, "failures": {"news": "fixture"} if failed else {}}
    report_path = tmp_path / "meta-report.json"
    report_path.write_text(json.dumps(report))
    horizons = []
    for scenario in reference_scenarios(100, 20):
        distribution = {**scenario, "expected_simple_return_pct": 1.0,
                        "status": "EXPERIMENTAL_UNCALIBRATED"}
        horizons.append({"trading_days": scenario["trading_days"],
                         "status": "EXPERIMENTAL_UNCALIBRATED", "distribution": distribution,
                         "evidence_quality": .8,
                         "context_signal": {"disagreement_range": .5, "supported_roles": 5},
                         "recommendation": {"action": "ACCUMULATE_CONDITIONALLY",
                            "catalysts_or_supporting_conditions": ["condition"],
                            "counter_case": ["counter"], "review_triggers": ["trigger"],
                            "missing_inputs": [], "portfolio_sizing": "OUT_OF_SCOPE"},
                         "ablations": {"without_news": distribution}})
    structured = {"schema_version": "meta-structured-forecast-v1",
                  "created_at": NOW.isoformat(), "packet_hash": packet["packet_hash"],
                  "probability_status": "EXPERIMENTAL_UNCALIBRATED",
                  "symbols": {"SPY": {"status": "EXPERIMENTAL_UNCALIBRATED", "horizons": horizons}},
                  "governance": {"cohort_id": "cohort"},
                  "agent_report_sha256": file_sha256(report_path)}
    structured["artifact_hash"] = digest(structured)
    structured_path = tmp_path / "structured.json"
    structured_path.write_text(json.dumps(structured))
    return packet_path, report_path, structured_path


def test_product_view_exposes_horizons_freshness_disagreement_and_provenance(tmp_path):
    packet, report, structured = artifacts(tmp_path)
    view = build_product_view(packet, structured_path=structured, report_path=report,
                              now=NOW, forecast_root=tmp_path / "none")
    assert view["run_status"] == "COMPLETE"
    assert view["probability_status"] == "EXPERIMENTAL_UNCALIBRATED"
    assert [row["trading_days"] for row in view["symbols"][0]["horizons"]] == [5, 21, 63]
    assert view["symbols"][0]["horizons"][0]["disagreement"] == .5
    assert view["symbols"][0]["horizons"][0]["ablations"] == {"without_news": .5}
    assert [row["key"] for row in view["market_summary"]] == [
        "current_vix", "current_vix_vix3m", "VIXCLS", "vix_term_structure_proxy",
        "DFF", "T10Y2Y", "NFCI", "CPIAUCSL"]
    assert next(row for row in view["market_summary"] if row["key"] == "DFF")["display"] == "3.50%"
    assert view["provenance"]["cohort_id"] == "cohort"
    assert view["golden_conclusions"]["status"] == "AVAILABLE"
    assert view["view_hash"] == digest({key: value for key, value in view.items() if key != "view_hash"})


def test_partial_agent_failure_is_visible_and_not_rendered_as_success(tmp_path):
    packet, report, structured = artifacts(tmp_path, failed=True)
    view = build_product_view(packet, structured_path=structured, report_path=report,
                              now=NOW, forecast_root=tmp_path / "none")
    assert view["run_status"] == "DEGRADED"
    assert view["failures"] == [{"stage": "agent", "name": "news", "detail": "fixture"}]
    news = next(row for row in view["freshness"] if row["family"] == "agent" and row["scope"] == "news")
    assert news["status"] == "FAILED"


def test_markdown_and_html_are_readable_escape_agent_text_and_label_uncalibrated(tmp_path):
    packet, report, structured = artifacts(tmp_path)
    view = build_product_view(packet, structured_path=structured, report_path=report,
                              now=NOW, forecast_root=tmp_path / "none")
    markdown = render_markdown(view)
    html = render_html(view)
    assert "5 sessions" in markdown and "Whole-market context" in markdown
    assert "GOLDEN RECOMMENDATIONS / GOLDEN CONCLUSIONS" in markdown
    assert "Evidence freshness and coverage" in markdown
    assert "EXPERIMENTAL_UNCALIBRATED" in html
    assert "Fed effective rate" in html
    assert "META executive assessment" in html
    assert "Astra META executive assessment" not in html
    assert "How to read this report" in html and "How to read this report" in markdown
    assert "terminal close" in html and "Current entry separately checks" in markdown
    assert "<script>not executable</script>" not in html
    assert "&lt;script&gt;not executable&lt;/script&gt;" in html
    assert "<script>blocked</script>" not in html
    assert "Content-Security-Policy" not in html  # Supplied by the local server, not misleading markup.


def test_product_bundle_is_hashed_and_cannot_overwrite(tmp_path):
    packet, report, structured = artifacts(tmp_path)
    output = write_product_bundle(packet, tmp_path / "product", structured_path=structured,
                                  report_path=report, now=NOW, forecast_root=tmp_path / "none")
    assert {path.name for path in output.iterdir()} == {
        "summary.json", "report.md", "index.html", "bundle.json"}
    receipt = json.loads((output / "bundle.json").read_text())
    assert receipt["files"]["index.html"] == file_sha256(output / "index.html")
    with pytest.raises(FileExistsError):
        write_product_bundle(packet, output, structured_path=structured,
                             report_path=report, now=NOW, forecast_root=tmp_path / "none")


def test_product_rejects_cross_packet_or_tampered_structured_artifact(tmp_path):
    packet, report, structured = artifacts(tmp_path)
    value = json.loads(structured.read_text())
    value["symbols"]["SPY"]["horizons"][0]["evidence_quality"] = 1
    structured.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="integrity"):
        build_product_view(packet, structured_path=structured, report_path=report,
                           now=NOW, forecast_root=tmp_path / "none")


def test_dashboard_refuses_nonlocal_binding(tmp_path):
    with pytest.raises(ValueError, match="127.0.0.1"):
        serve(tmp_path, "0.0.0.0", 8765)


def test_dashboard_serves_only_allowlisted_reads_and_rejects_post(tmp_path):
    packet, report, structured = artifacts(tmp_path)
    bundle = write_product_bundle(packet, tmp_path / "product", structured_path=structured,
                                  report_path=report, now=NOW, forecast_root=tmp_path / "none")
    class FakeHandler:
        root = bundle

        def __init__(self, path):
            self.path = path
            self.sent = None

        def _send(self, status, content_type, payload):
            self.sent = (status, content_type, payload)

    latest = FakeHandler("/api/v1/latest")
    ProductHandler.do_GET(latest)
    assert latest.sent[0] == 200
    assert json.loads(latest.sent[2])["view_hash"]
    traversal = FakeHandler("/../packet.json")
    ProductHandler.do_GET(traversal)
    assert traversal.sent[0] == 404
    rejected = FakeHandler("/api/v1/latest")
    ProductHandler.do_POST(rejected)
    assert rejected.sent[0] == 405


def test_publication_age_stales_old_intraday_value_and_renderers_keep_decision_semantics(tmp_path):
    packet_path, report_path, structured_path = artifacts(tmp_path)
    packet = json.loads(packet_path.read_text())
    packet["operating_context"] = {"market_data_mode": "intraday"}
    packet["intraday"] = {"SPY": {"status": "AVAILABLE", "evidence_state": "REAL_TIME",
        "exchange_coverage": "IEX_ONLY", "latest_timestamp": "2026-09-14T20:00:00+00:00",
        "session_last": 101.0}}
    packet.pop("packet_hash")
    packet["packet_hash"] = digest(packet)
    packet_path.write_text(json.dumps(packet))
    report = json.loads(report_path.read_text())
    report["packet_hash"] = packet["packet_hash"]
    report_path.write_text(json.dumps(report))
    structured = json.loads(structured_path.read_text())
    structured.pop("artifact_hash")
    structured["packet_hash"] = packet["packet_hash"]
    structured["agent_report_sha256"] = file_sha256(report_path)
    structured["artifact_hash"] = digest(structured)
    structured_path.write_text(json.dumps(structured))
    view = build_product_view(packet_path, structured_path=structured_path,
                              report_path=report_path, now=NOW,
                              forecast_root=tmp_path / "none")
    row = next(item for item in view["freshness"]
               if item["family"] == "price_intraday" and item["scope"] == "SPY")
    assert row["status"] == "STALE_AT_PUBLICATION"
    assert row["age_at_publication_seconds"] == 1560
    assert row["criticality"] == "ADVISORY"
    assert view["publication_lag_seconds"] == 60
    markdown, html = render_markdown(view), render_html(view)
    action = view["symbols"][0]["horizons"][0]["action"]
    assert action in markdown and action in html
    assert "LATEST_COMPLETED_SESSION_CLOSE" in markdown
    assert "Age (s)" in html
