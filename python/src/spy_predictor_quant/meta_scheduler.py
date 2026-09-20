"""Calendar-aware, idempotent scheduler entry points for META operations."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from spy_predictor_quant.meta_analysis import (
    DEFAULT_FORECAST_POLICY, DEFAULT_OPERATIONS_POLICY, DEFAULT_PRIMARY_SOURCES,
    digest, postclose, symbols as normalize_symbols,
)
from spy_predictor_quant.meta_operations import (
    AlertLedger, BudgetExceeded, OperationLedger,
    load_operations_policy, schedule_decision,
)
from spy_predictor_quant.meta_outcomes import update


ROOT = Path(__file__).resolve().parents[3]


def _mapping(values: list[str], allowed: set[str], label: str) -> dict[str, Path]:
    result = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"{label} requires SYMBOL=PATH")
        symbol, raw_path = value.split("=", 1)
        symbol = symbol.upper()
        if symbol not in allowed or symbol in result:
            raise ValueError(f"{label} symbol must be a unique configured ETF")
        result[symbol] = Path(raw_path)
    return result


def run_prospective(*, targets: list[str], etfs: list[str], capture_root: Path,
                    analysis_root: Path, forecast_root: Path, ledger_root: Path,
                    alert_root: Path, operations_policy_path: Path,
                    holdings_files: dict[str, Path] | None = None,
                    etf_profile_files: dict[str, Path] | None = None,
                    evidence_file: Path | None = None,
                    delayed_context_file: Path | None = None,
                    primary_sources_file: Path | None = DEFAULT_PRIMARY_SOURCES,
                    runner_config: Path | None = None,
                    forecast_policy: Path = DEFAULT_FORECAST_POLICY,
                    now: datetime | None = None, execute: bool = False,
                    runner=postclose, decision_fn=schedule_decision,
                    product_loader=None) -> dict:
    if execute and now is not None:
        raise ValueError("Executing with an operator-supplied clock is prohibited")
    policy = load_operations_policy(operations_policy_path)
    decision = decision_fn(targets, forecast_root, policy, now, "PROSPECTIVE")
    if not execute:
        return {"status": "DRY_RUN", "would_execute": decision["status"] == "READY",
                "decision": decision, "writes": False}
    if decision["status"] != "READY":
        return {"status": "ABSTAINED", "decision": decision, "writes": False}
    ledger = OperationLedger(ledger_root)
    attempt_result = ledger.create("PROSPECTIVE", decision["origin_session"], targets,
                                   digest(policy))
    attempt_path = attempt_result["path"]
    if attempt_result["status"] == "EXISTING":
        states = ledger.states(attempt_path)
        final = states[-1]["state"] if states else "UNKNOWN"
        return {"status": "ALREADY_TERMINAL" if final in {"COMPLETE", "DEGRADED", "BLOCKED"}
                          else "EXISTING_NONTERMINAL_REQUIRES_RESUME",
                "attempt": str(attempt_path.resolve()), "last_state": final,
                "writes": False}
    ledger.transition(attempt_path, "PREFLIGHT", details={"decision": decision})

    def transition(state: str, details: dict) -> None:
        ledger.transition(attempt_path, state, details=details)

    started = time.monotonic()
    alerts = AlertLedger(alert_root)
    try:
        receipt = runner(
            targets, etfs, capture_root=capture_root, analysis_root=analysis_root,
            forecast_root=forecast_root, holdings_files=holdings_files,
            etf_profile_files=etf_profile_files, evidence_file=evidence_file,
            delayed_context_file=delayed_context_file,
            primary_sources_file=primary_sources_file, runner_config=runner_config,
            forecast_policy=forecast_policy, operations_policy=operations_policy_path,
            operation_callback=transition)
        elapsed = time.monotonic() - started
        if elapsed > policy["budgets"]["maximum_wall_seconds"]:
            raise BudgetExceeded("Prospective pipeline exceeded its wall-clock budget")
        if product_loader is None:
            from spy_predictor_quant.meta_product import load_product_view
            product_loader = load_product_view
        product = product_loader(Path(receipt["product_bundle"]) / "summary.json")
        terminal = "DEGRADED" if product["run_status"] == "DEGRADED" else "COMPLETE"
        ledger.transition(attempt_path, terminal,
                          details={"receipt_path": receipt["receipt_path"],
                                   "product_bundle": receipt["product_bundle"],
                                   "elapsed_seconds": elapsed})
        severity = "WARNING" if terminal == "DEGRADED" else "INFO"
        alerts.emit(f"prospective:{decision['origin_session']}:{terminal.lower()}", severity,
                    f"Prospective META run {terminal.lower()} for {decision['origin_session']}",
                    details={"attempt": str(attempt_path.resolve())})
        return {"status": terminal, "attempt": str(attempt_path.resolve()),
                "receipt": receipt, "elapsed_seconds": elapsed, "writes": True}
    except BaseException as error:
        ledger.transition(attempt_path, "BLOCKED",
                          details={"error_type": type(error).__name__, "message": str(error)})
        alerts.emit(f"prospective:{decision['origin_session']}:blocked", "ERROR",
                    f"Prospective META run blocked: {type(error).__name__}",
                    details={"attempt": str(attempt_path.resolve()), "message": str(error)})
        raise


def run_outcomes(*, forecast_root: Path, outcome_root: Path, score_root: Path,
                 capture_root: Path, report_root: Path, ledger_root: Path,
                 alert_root: Path, operations_policy_path: Path,
                 now: datetime | None = None, execute: bool = False,
                 updater=update) -> dict:
    if execute and now is not None:
        raise ValueError("Executing with an operator-supplied clock is prohibited")
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not execute:
        return {"status": "DRY_RUN", "would_execute": True,
                "as_of": instant.isoformat(), "writes": False}
    policy = load_operations_policy(operations_policy_path)
    ledger = OperationLedger(ledger_root)
    attempt = ledger.create("OUTCOMES", instant.date().isoformat(), [], digest(policy), instant)
    path = attempt["path"]
    if attempt["status"] == "EXISTING":
        last = ledger.states(path)[-1]["state"]
        return {"status": "ALREADY_TERMINAL" if last in {"COMPLETE", "DEGRADED", "BLOCKED"}
                          else "EXISTING_NONTERMINAL_REQUIRES_RESUME",
                "attempt": str(path.resolve()), "last_state": last, "writes": False}
    ledger.transition(path, "PREFLIGHT", instant)
    try:
        ledger.transition(path, "ACQUIRING", instant, {"kind": "outcomes"})
        result = updater(forecast_root, outcome_root, score_root, capture_root, report_root)
        ledger.transition(path, "COMPLETE", details={"result": result})
        AlertLedger(alert_root).emit(f"outcomes:{instant.date().isoformat()}:complete", "INFO",
                                     "META outcome update completed", details=result)
        return {"status": "COMPLETE", "attempt": str(path.resolve()),
                "result": result, "writes": True}
    except BaseException as error:
        ledger.transition(path, "BLOCKED", details={"error_type": type(error).__name__,
                                                     "message": str(error)})
        AlertLedger(alert_root).emit(f"outcomes:{instant.date().isoformat()}:blocked", "ERROR",
                                     f"META outcome update blocked: {type(error).__name__}")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prospective = sub.add_parser("prospective")
    prospective.add_argument("--symbols", nargs="+", required=True)
    prospective.add_argument("--etfs", nargs="+", default=[])
    prospective.add_argument("--etf-holdings", action="append", default=[])
    prospective.add_argument("--etf-profile", action="append", default=[])
    prospective.add_argument("--evidence", type=Path)
    prospective.add_argument("--ibkr-delayed-context", type=Path)
    prospective.add_argument("--primary-sources", type=Path, default=DEFAULT_PRIMARY_SOURCES)
    prospective.add_argument("--runner-config", type=Path)
    prospective.add_argument("--forecast-policy", type=Path, default=DEFAULT_FORECAST_POLICY)
    prospective.add_argument("--operations-policy", type=Path, default=DEFAULT_OPERATIONS_POLICY)
    prospective.add_argument("--capture-root", type=Path, default=ROOT / "datasets/workbench/meta")
    prospective.add_argument("--analysis-root", type=Path, default=ROOT / "reports/meta-analysis")
    prospective.add_argument("--forecast-root", type=Path, default=ROOT / "datasets/meta-observation/forecasts")
    prospective.add_argument("--ledger-root", type=Path, default=ROOT / "datasets/meta-operations/attempts")
    prospective.add_argument("--alert-root", type=Path, default=ROOT / "datasets/meta-operations/alerts")
    prospective.add_argument("--now", type=datetime.fromisoformat)
    prospective.add_argument("--execute", action="store_true")
    outcomes = sub.add_parser("outcomes")
    outcomes.add_argument("--forecasts", type=Path, default=ROOT / "datasets/meta-observation/forecasts")
    outcomes.add_argument("--outcomes", type=Path, default=ROOT / "datasets/meta-observation/outcomes")
    outcomes.add_argument("--scores", type=Path, default=ROOT / "datasets/meta-observation/scores")
    outcomes.add_argument("--captures", type=Path, default=ROOT / "datasets/meta-observation/outcome-captures")
    outcomes.add_argument("--reports", type=Path, default=ROOT / "reports/meta-observation")
    outcomes.add_argument("--operations-policy", type=Path, default=DEFAULT_OPERATIONS_POLICY)
    outcomes.add_argument("--ledger-root", type=Path, default=ROOT / "datasets/meta-operations/outcome-attempts")
    outcomes.add_argument("--alert-root", type=Path, default=ROOT / "datasets/meta-operations/alerts")
    outcomes.add_argument("--now", type=datetime.fromisoformat)
    outcomes.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.action == "prospective":
        targets = normalize_symbols(args.symbols)
        etfs = [value.upper() for value in args.etfs]
        if not set(etfs) <= set(targets):
            parser.error("--etfs must be a subset of --symbols")
        try:
            result = run_prospective(
                targets=targets, etfs=etfs, capture_root=args.capture_root,
                analysis_root=args.analysis_root, forecast_root=args.forecast_root,
                ledger_root=args.ledger_root, alert_root=args.alert_root,
                operations_policy_path=args.operations_policy,
                holdings_files=_mapping(args.etf_holdings, set(etfs), "--etf-holdings"),
                etf_profile_files=_mapping(args.etf_profile, set(etfs), "--etf-profile"),
                evidence_file=args.evidence, delayed_context_file=args.ibkr_delayed_context,
                primary_sources_file=args.primary_sources, runner_config=args.runner_config,
                forecast_policy=args.forecast_policy, now=args.now, execute=args.execute)
        except ValueError as error:
            parser.error(str(error))
    else:
        result = run_outcomes(
            forecast_root=args.forecasts, outcome_root=args.outcomes,
            score_root=args.scores, capture_root=args.captures, report_root=args.reports,
            ledger_root=args.ledger_root, alert_root=args.alert_root,
            operations_policy_path=args.operations_policy, now=args.now, execute=args.execute)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
