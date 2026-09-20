"""Frozen, restricted ETF pilot panel and pre-outcome feasibility receipt.

The revised-price lane exercises real walk-forward code without certifying
historical availability, a broad universe, or eligibility for promotion.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import numpy as np

from spy_predictor_quant.market_archive import file_sha256, write_json_exclusive
from spy_predictor_quant.meta_analysis import digest
from spy_predictor_quant.meta_contracts import finite, instant
from spy_predictor_quant.meta_experiments import feasibility, validate_protocol
from spy_predictor_quant.meta_forecast import _quant_signals


def source_bars(root: Path, adjustment: str) -> tuple[dict, list[str], str]:
    bars, hashes, captured = {}, [], []
    paths = sorted((root / "raw").glob(f"bars-{adjustment}-*.receipt.json"),
                   key=lambda p: int(p.name.split("-")[-1].split(".")[0]))
    if not paths:
        raise ValueError("Receipted price history required")
    expected_token = None
    for index, path in enumerate(paths):
        if path.name != f"bars-{adjustment}-{index}.receipt.json":
            raise ValueError("Missing price page receipt")
        receipt = json.loads(path.read_text())
        raw = root / "raw" / receipt["raw_file"]
        if file_sha256(raw) != receipt["sha256"]:
            raise ValueError("Raw price integrity mismatch")
        params = receipt["request"]["params"]
        if params["adjustment"] != adjustment or params["feed"] != "sip":
            raise ValueError("Price convention mismatch")
        if params.get("page_token") != expected_token or (index and expected_token is None):
            raise ValueError("Price pagination chain mismatch")
        payload = json.loads(raw.read_text())
        expected_token = payload.get("next_page_token")
        hashes.append(receipt["sha256"])
        captured.append(receipt["captured_at"])
        for symbol, values in payload["bars"].items():
            for row in values:
                session = instant(row["t"]).astimezone(ZoneInfo("America/New_York")).date().isoformat()
                if session in bars.setdefault(symbol, {}):
                    raise ValueError("Duplicate price session")
                if any(not finite(row[k]) or row[k] <= 0 for k in ("o", "h", "l", "c")) or row["v"] < 0:
                    raise ValueError("Invalid OHLCV history")
                if not row["l"] <= min(row["o"], row["c"]) <= max(row["o"], row["c"]) <= row["h"]:
                    raise ValueError("Inconsistent OHLC history")
                bars[symbol][session] = row
    if payload.get("next_page_token"):
        raise ValueError("Incomplete price pagination")
    return bars, hashes, max(captured)


def build_panel(source: Path, output: Path, protocol: dict) -> dict:
    validate_protocol(protocol)
    if protocol.get("research_mode") != "DIAGNOSTIC_REVISED_PRICES":
        raise ValueError("This builder only supports the explicitly unqualified revised-price lane")
    scope = protocol["scope"]
    if scope["history_start"] < "2025-08-01":
        raise ValueError("Protected evaluation period cannot enter this pilot")
    output.mkdir(parents=True, exist_ok=True)
    # Exclusive design freeze precedes loading any numerical price data.
    write_json_exclusive(output / "design.json", {"protocol": protocol, "protocol_hash": digest(protocol),
        "purpose": "ENGINEERING_DIAGNOSTIC_ONLY", "created_before_price_panel_inspection": True})
    adjusted, adjusted_hashes, captured = source_bars(source, "split")
    raw, raw_hashes, _ = source_bars(source, "raw")
    symbols = scope["symbols"]
    if set(adjusted) != set(symbols) or set(raw) != set(symbols):
        raise ValueError("Fixed ETF universe differs from requested symbols")
    calendar = xcals.get_calendar("XNYS")
    sessions = [s.date().isoformat() for s in calendar.sessions_in_range(scope["history_start"], scope["history_end"])]
    missing = {s: [day for day in sessions if day not in adjusted[s] or day not in raw[s]] for s in symbols}
    if any(missing.values()):
        write_json_exclusive(output / "coverage-failure.json", missing)
        raise ValueError("Missing sessions; refusing to collapse a trading horizon across a gap")
    metadata = []
    warmup = scope["warmup_sessions"]
    for i in range(warmup, len(sessions)):
        reference = sessions[i]
        origin = calendar.session_close(reference).to_pydatetime() + timedelta(minutes=20)
        for horizon in protocol["horizons"]:
            if i + horizon >= len(sessions):
                continue
            end = calendar.session_close(sessions[i + horizon]).to_pydatetime()
            for symbol in symbols:
                metadata.append({"symbol": symbol, "origin_at": origin.isoformat(), "horizon_sessions": horizon,
                    "reference_session": reference, "label_end_at": end.isoformat(),
                    "label_available_at": (end + timedelta(minutes=20)).isoformat()})
    readiness = feasibility(metadata, protocol)
    write_json_exclusive(output / "feasibility.json", readiness)
    snapshots = output / "features"
    snapshots.mkdir()
    by_session = {day: i for i, day in enumerate(sessions)}
    prices = {s: np.array([adjusted[s][day]["c"] for day in sessions]) for s in symbols}
    panel = []
    for item in metadata:
        symbol, h = item["symbol"], item["horizon_sessions"]
        i = by_session[item["reference_session"]]
        values = prices[symbol][:i+1]
        vol = float(np.std(np.diff(np.log(values[-64:])), ddof=1) * np.sqrt(252) * 100)
        returns = {str(n): float((values[-1] / values[-1-n] - 1) * 100) for n in (5, 21, 63)}
        market = float((prices["SPY"][i] / prices["SPY"][i-h] - 1) * 100)
        sector = float((prices["XLK"][i] / prices["XLK"][i-h] - 1) * 100)
        instrument = {"status": "FRESH", "realized_vol63_pct": vol,
                      **{f"return{n}_pct": r for n, r in returns.items()},
                      **{f"price_to_sma{n}": float(values[-1] / values[-n:].mean()) for n in (20, 50, 200) if len(values) >= n},
                      "relative_strength_vs_spy": {f"{h}_sessions_percentage_points": returns[str(h)] - market}}
        score = _quant_signals({"instruments": {symbol: instrument}}, symbol, h)["score"]
        features = {"market_return_pct": market, "sector_return_pct": sector,
                    "momentum_pct": returns[str(h)], "annual_volatility_pct": vol, "quant_score": score}
        core = {"schema_version": "meta-feature-snapshot-v2", "cutoff": item["origin_at"],
                "availability_lane": "REVISED_PRICE_DIAGNOSTIC", "source_captured_at": captured,
                "registry_hash": digest(protocol), "source_hashes": adjusted_hashes,
                "horizon_sessions": h, "features": [{"entity": symbol, "name": name, "value": value,
                    "available_at": item["origin_at"], "availability_is_assumed": True,
                    "units": "score" if name == "quant_score" else "percent", "status": "DIAGNOSTIC",
                    "input_hashes": adjusted_hashes} for name, value in features.items()]}
        identity = digest(core)
        write_json_exclusive(snapshots / f"{identity}.json", {**core, "snapshot_hash": identity})
        panel.append({**item, "features": features, "feature_snapshot_hash": identity,
            "feature_available_at": item["origin_at"], "universe_member_available_at": item["origin_at"],
            "simple_return": float(prices[symbol][i+h] / prices[symbol][i] - 1),
            "origin_kind": "PRIOR_COMPLETED_CLOSE", "return_basis": "SPLIT_ADJUSTED_PRICE_RETURN_EX_DIVIDENDS",
            "target_contract": "XNYS_COMPLETED_CLOSE_PLUS_H_SESSIONS", "universe_version": "FIXED_ETF_CASE_STUDY_20260916",
            "availability_status": "REVISED_HISTORY_DIAGNOSTIC", "quality_flags": ["HISTORICAL_PRICE_VINTAGE_UNVERIFIED"]})
    panel_path = output / "panel.json"
    write_json_exclusive(panel_path, panel)
    coverage = {"sessions": len(sessions), "symbols": symbols, "panel_rows": len(panel), "missing_sessions": missing,
        "adjusted_vs_raw_close_differences": {s: sum(adjusted[s][d]["c"] != raw[s][d]["c"] for d in sessions) for s in symbols},
        "raw_source_hashes": raw_hashes, "adjusted_source_hashes": adjusted_hashes,
        "corporate_action_receipts": [str(p.resolve()) for p in sorted((source / "raw").glob("actions-*.receipt.json"))],
        "price_vintage_qualification": "NOT_QUALIFIED", "broad_universe_qualification": "NOT_APPLICABLE_FIXED_CASE_STUDY"}
    write_json_exclusive(output / "coverage.json", coverage)
    manifest = {"schema_version": "meta-research-panel-manifest-v1", "research_track": "IMPROVEMENT_PLAN_3_NEW_COHORT",
        "dataset_kind": "REVISED_PRICE_DIAGNOSTIC", "qualification_status": "NOT_QUALIFIED",
        "panel_sha256": file_sha256(panel_path), "feature_snapshots_root": str(snapshots.resolve()),
        "availability_audited": False, "survivorship_audited": False, "corporate_actions_audited": False,
        "license_audited": False, "feasibility_sha256": file_sha256(output / "feasibility.json"),
        "coverage_sha256": file_sha256(output / "coverage.json"), "audit_restrictions": [
            "Latest revised price history does not certify historical first availability.",
            "Named ETF case study selected now; no historical broad-universe selection claim.",
            "Raw/split differences and action receipts retained; action coverage and historical processing availability unqualified.",
            "Existing authenticated local access; redistribution and broader data license qualification not established.",
            "ALFRED/SEC histories are separate qualified source reconstructions, not prerequisites or features of this quant pilot."]}
    write_json_exclusive(output / "manifest.json", manifest)
    return {"panel": str(panel_path), "manifest": str(output / "manifest.json"), "rows": len(panel), "feasibility": readiness}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_panel(args.source, args.output, json.loads(args.protocol.read_text())), indent=2))


if __name__ == "__main__":
    main()
