"""Prepare and run current research collection in a separate append-only lane."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

import exchange_calendars as xcals

from spy_predictor_quant.market_archive import create_immutable_run_directory, file_sha256, write_json_exclusive
from spy_predictor_quant.meta_analysis import build, capture, digest
from spy_predictor_quant.meta_operations import load_operations_policy
from spy_predictor_quant.meta_research_data import coverage_audit, ingest_packet

ROOT = Path(__file__).resolve().parents[3]


def validate_config(config: dict) -> None:
    if config.get("schema_version") != "meta-research-collection-v1":
        raise ValueError("Unsupported collection configuration")
    symbols = config["symbols"]
    if not symbols or len(set(symbols)) != len(symbols) or not set(config["etfs"]) <= set(symbols):
        raise ValueError("Collection requires unique symbols and matching ETF identities")
    for name in ("capture_root", "store_root", "receipt_root"):
        path = (ROOT / config[name]).resolve()
        if not path.is_relative_to(ROOT / "datasets/meta-research"):
            raise ValueError("Research collection cannot write to an existing forecast or closed-cohort lane")
    if not (ROOT / config["analysis_root"]).resolve().is_relative_to(ROOT / "reports/improvement-plan-3"):
        raise ValueError("Research reports must remain in the Improvement Plan 3 lane")
    for group in ("etf_profiles", "etf_holdings"):
        if not set(config[group]) <= set(config["etfs"]):
            raise ValueError("ETF source mapping differs from configured ETFs")
        for path in config[group].values():
            if not (ROOT / path).is_file():
                raise ValueError("Configured ETF source file missing")
    load_operations_policy(ROOT / config["operations_policy"])


def prepare(config: dict, now: datetime | None = None) -> dict:
    validate_config(config)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Collection clock must include timezone")
    cal = xcals.get_calendar("XNYS")
    sessions = cal.sessions_in_range(now.date().isoformat(), (now + timedelta(days=7)).date().isoformat())
    next_close = next(cal.session_close(s).to_pydatetime() + timedelta(minutes=20) for s in sessions
                      if cal.session_close(s).to_pydatetime() + timedelta(minutes=20) > now)
    return {"schema_version": "meta-collection-readiness-v1", "as_of": now.isoformat(),
        "configuration_hash": digest(config), "status": "PREPARED",
        "credentials_present": {k: bool(os.environ.get(k)) for k in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "SEC_USER_AGENT")},
        "source_hashes": {path: file_sha256(ROOT / path) for group in ("etf_profiles", "etf_holdings") for path in config[group].values()},
        "next_completed_close_collection_at": next_close.isoformat(), "forecast_registration": False,
        "scheduler_installed": False, "orders_enabled": False, "writes": False,
        "coverage": coverage_audit(ROOT / config["store_root"]),
        "notice": "Preparation validates local configuration; acquisition may report missing or stale sources. Manual ETF files retain their own dates."}


def collect(config: dict, packet_path: Path | None = None) -> dict:
    validate_config(config)
    run = create_immutable_run_directory(ROOT / config["receipt_root"], "collection")
    write_json_exclusive(run / "started.json", {"configuration": config, "configuration_hash": digest(config),
                                               "started_at": datetime.now(timezone.utc).isoformat()})
    try:
        if packet_path is None:
            snapshot = capture(ROOT / config["capture_root"], config["symbols"], config["etfs"], None, None,
                {s: ROOT / p for s, p in config["etf_holdings"].items()},
                primary_sources_file=ROOT / config["primary_sources"],
                etf_profile_files={s: ROOT / p for s, p in config["etf_profiles"].items()},
                market_data_mode=config["market_data_mode"], intraday_feed=config["intraday_feed"],
                operations_policy_path=ROOT / config["operations_policy"],
                cache_root=ROOT / "datasets/meta-cache")
            packet_path = build(snapshot, ROOT / config["analysis_root"]) / "packet.json"
        packet = json.loads(packet_path.read_text())
        if set(packet["symbols"]) != set(config["symbols"]) or set(packet.get("etfs", [])) != set(config["etfs"]):
            raise ValueError("Collection packet identity differs from configuration")
        paths = ingest_packet(ROOT / config["store_root"], packet_path)
        status = ("COLLECTED_WITH_SOURCE_GAPS" if packet.get("acquisition_errors") else "COLLECTED") if paths else "NO_QUALIFIED_NUMERIC_OBSERVATIONS"
        receipt = {"status": status,
            "packet": str(packet_path.resolve()), "packet_sha256": file_sha256(packet_path),
            "observations": len(paths), "observation_hashes": [p.stem for p in paths],
            "source_cutoff": packet["as_of"], "completed_at": datetime.now(timezone.utc).isoformat(),
            "availability": "ACTUAL_INGESTION_TIME_NOT_BACKDATED", "forecast_registration": False,
            "acquisition_errors": packet.get("acquisition_errors", {}),
            "coverage": coverage_audit(ROOT / config["store_root"])}
        write_json_exclusive(run / "completed.json", receipt)
        return {"path": str(run / "completed.json"), **receipt}
    except Exception as exc:
        write_json_exclusive(run / "failed.json", {"error_type": type(exc).__name__, "reason": str(exc)})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "collect"])
    parser.add_argument("--config", type=Path, default=Path("config/meta-research-collection-v1.json"))
    parser.add_argument("--packet", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    result = prepare(config) if args.command == "prepare" else collect(config, args.packet)
    print(json.dumps(result, indent=2))
    return 2 if result["status"] == "NO_QUALIFIED_NUMERIC_OBSERVATIONS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
