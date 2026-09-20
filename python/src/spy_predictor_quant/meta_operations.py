"""Local operational controls for META caching, budgets, scheduling, and alerts."""
from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
from threading import Lock
import time
import uuid

import exchange_calendars as xcals
from jsonschema import Draft202012Validator

from spy_predictor_quant.market_archive import file_sha256, write_bytes_exclusive, write_json_exclusive
from spy_predictor_quant.meta_analysis import digest, postclose_preflight
from spy_predictor_quant.request_pacing import PacingController


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY = ROOT / "config/meta-operations-v1.json"
POLICY_SCHEMA = ROOT / "schemas/meta-operations-policy-v1.schema.json"
TERMINAL_STATES = {"COMPLETE", "DEGRADED", "BLOCKED"}
PIPELINE_STATES = (
    "PLANNED", "PREFLIGHT", "ACQUIRING", "VALIDATING", "AGENTS",
    "FORECASTING", "REGISTERING", "RENDERING", "COMPLETE", "DEGRADED", "BLOCKED",
)
ALLOWED_TRANSITIONS = {
    None: {"PLANNED"},
    "PLANNED": {"PREFLIGHT", "BLOCKED"},
    "PREFLIGHT": {"ACQUIRING", "BLOCKED"},
    "ACQUIRING": {"VALIDATING", "COMPLETE", "DEGRADED", "BLOCKED"},
    "VALIDATING": {"AGENTS", "REGISTERING", "RENDERING", "BLOCKED"},
    "AGENTS": {"FORECASTING", "BLOCKED"},
    "FORECASTING": {"REGISTERING", "RENDERING", "BLOCKED"},
    "REGISTERING": {"RENDERING", "BLOCKED"},
    "RENDERING": {"COMPLETE", "DEGRADED", "BLOCKED"},
}


def _validate_artifact(value: dict, schema_name: str) -> None:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text())
    Draft202012Validator(schema).validate(value)


def _instant(value: datetime | None = None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None:
        raise ValueError("Operational timestamps must include a timezone")
    return result.astimezone(timezone.utc)


def load_operations_policy(path: Path = DEFAULT_POLICY) -> dict:
    value = json.loads(path.read_text())
    Draft202012Validator(json.loads(POLICY_SCHEMA.read_text())).validate(value)
    for name, policy in value["cache_policies"].items():
        if policy["mode"] == "ttl" and "ttl_seconds" not in policy:
            raise ValueError(f"TTL cache policy {name} lacks ttl_seconds")
        if policy["mode"] == "manual_as_of" and "maximum_age_seconds" not in policy:
            raise ValueError(f"Manual cache policy {name} lacks maximum_age_seconds")
    return value


class BudgetExceeded(RuntimeError):
    """Raised before work that would exceed a frozen operational budget."""


class BudgetLedger:
    FIELDS = {
        "source_requests": "maximum_source_requests",
        "download_bytes": "maximum_download_bytes",
        "agent_calls": "maximum_agent_calls",
        "input_tokens": "maximum_input_tokens",
        "output_tokens": "maximum_output_tokens",
        "catalog_cost_estimate_usd": "maximum_catalog_cost_estimate_usd",
        "wall_seconds": "maximum_wall_seconds",
    }

    def __init__(self, policy: dict, started_at: float | None = None) -> None:
        self.policy = policy["budgets"] if "budgets" in policy else policy
        self.used = {name: 0.0 for name in self.FIELDS}
        self.started_at = time.monotonic() if started_at is None else started_at

    def consume(self, name: str, amount: float = 1) -> None:
        if name not in self.FIELDS or amount < 0:
            raise ValueError("Unknown budget metric or negative amount")
        limit = float(self.policy[self.FIELDS[name]])
        proposed = self.used[name] + amount
        if proposed > limit:
            raise BudgetExceeded(f"{name} budget exceeded: {proposed:g}>{limit:g}")
        self.used[name] = proposed

    def account_receipt(self, receipt: dict) -> None:
        self.consume("agent_calls")
        self.consume("input_tokens", float(receipt.get("input_tokens", 0)))
        self.consume("output_tokens", float(receipt.get("output_tokens", 0)))
        self.consume("catalog_cost_estimate_usd",
                     float(receipt.get("catalog_cost_estimate_usd", 0)))

    def snapshot(self, now_monotonic: float | None = None) -> dict:
        elapsed = (time.monotonic() if now_monotonic is None else now_monotonic) - self.started_at
        self.used["wall_seconds"] = max(self.used["wall_seconds"], elapsed)
        warning = float(self.policy["warning_fraction"])
        rows = {}
        for name, field in self.FIELDS.items():
            limit = float(self.policy[field])
            used = self.used[name]
            rows[name] = {"used": used, "limit": limit,
                          "fraction": used / limit,
                          "status": "EXHAUSTED" if used >= limit else
                                    "WARNING" if used / limit >= warning else "OK"}
        return {"metrics": rows, "warning_fraction": warning}


class ReleaseCache:
    """Content-addressed cache whose caller supplies the source release identity."""

    def __init__(self, root: Path, operations_policy: dict, budget: BudgetLedger | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 sleeper: Callable[[float], None] = time.sleep) -> None:
        self.root = root
        self.policy = operations_policy
        self.budget = budget or BudgetLedger(operations_policy)
        self.clock = clock
        self.sleeper = sleeper
        self._pacers: dict[str, PacingController] = {}
        self._locks: dict[str, Lock] = {}
        self._locks_guard = Lock()

    def _policy(self, category: str) -> dict:
        try:
            return self.policy["cache_policies"][category]
        except KeyError as error:
            raise ValueError(f"Unknown cache category: {category}") from error

    @staticmethod
    def key(category: str, source: str, release_identity: str) -> str:
        if not all(isinstance(value, str) and value for value in (category, source, release_identity)):
            raise ValueError("Cache identity fields must be nonempty strings")
        return digest({"category": category, "source": source,
                       "release_identity": release_identity})

    def lookup(self, category: str, source: str, release_identity: str,
               now: datetime | None = None) -> dict | None:
        policy = self._policy(category)
        path = self.root / self.key(category, source, release_identity)
        manifest_path, payload_path = path / "manifest.json", path / "payload.bin"
        if not manifest_path.exists() or not payload_path.exists():
            return None
        manifest = json.loads(manifest_path.read_text())
        _validate_artifact(manifest, "meta-cache-entry-v1.schema.json")
        if file_sha256(payload_path) != manifest.get("sha256"):
            raise ValueError(f"Cache payload integrity mismatch: {path}")
        age = (_instant(now) - datetime.fromisoformat(manifest["stored_at"]).astimezone(timezone.utc)).total_seconds()
        if policy["mode"] == "ttl" and age > policy["ttl_seconds"]:
            return None
        return {"status": "HIT", "path": str(payload_path.resolve()),
                "payload": payload_path.read_bytes(), "manifest": manifest}

    def store(self, category: str, source: str, release_identity: str, payload: bytes,
              now: datetime | None = None) -> dict:
        self._policy(category)
        instant = _instant(now)
        key = self.key(category, source, release_identity)
        path = self.root / key
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            path.mkdir()
        except FileExistsError:
            existing = self.lookup(category, source, release_identity, instant)
            if existing is None:
                raise ValueError("Expired TTL identities must include a time bucket")
            return existing
        payload_path = path / "payload.bin"
        sha = write_bytes_exclusive(payload_path, payload)
        manifest = {"schema_version": "meta-cache-entry-v1", "key": key,
                    "category": category, "source": source,
                    "release_identity": release_identity, "stored_at": instant.isoformat(),
                    "bytes": len(payload), "sha256": sha}
        _validate_artifact(manifest, "meta-cache-entry-v1.schema.json")
        write_json_exclusive(path / "manifest.json", manifest)
        return {"status": "STORED", "path": str(payload_path.resolve()),
                "payload": payload, "manifest": manifest}

    def fetch(self, category: str, source: str, release_identity: str,
              fetcher: Callable[[], bytes], now: datetime | None = None) -> dict:
        with self._locks_guard:
            lock = self._locks.setdefault(category, Lock())
        with lock:
            cached = self.lookup(category, source, release_identity, now)
            if cached:
                return cached
            policy = self._policy(category)
            pacer = self._pacers.setdefault(category, PacingController(
                policy["minimum_request_spacing_seconds"],
                policy["maximum_requests_per_window"], policy["window_seconds"],
                self.clock, self.sleeper))
            self.budget.consume("source_requests")
            pacer.wait()
            payload = fetcher()
            if not isinstance(payload, bytes):
                raise TypeError("Acquisition fetcher must return bytes")
            self.budget.consume("download_bytes", len(payload))
            return self.store(category, source, release_identity, payload, now)


class AlertLedger:
    """Append-only, deduplicated local alert events."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def events(self) -> list[dict]:
        if not self.root.exists():
            return []
        events = [json.loads(path.read_text()) for path in sorted(self.root.glob("*.json"))]
        for event in events:
            _validate_artifact(event, "meta-alert-event-v1.schema.json")
            identity = event.pop("event_hash")
            if digest(event) != identity:
                raise ValueError("Alert event integrity mismatch")
            event["event_hash"] = identity
        return events

    def open_conditions(self) -> dict[str, dict]:
        result = {}
        for event in self.events():
            if event["event"] == "OPENED":
                result[event["condition_key"]] = event
            elif event["event"] == "RESOLVED":
                result.pop(event["condition_key"], None)
        return result

    def emit(self, condition_key: str, severity: str, message: str,
             now: datetime | None = None, details: dict | None = None) -> dict:
        if severity not in {"INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Unknown alert severity")
        existing = self.open_conditions().get(condition_key)
        if existing:
            return {"status": "DEDUPLICATED", "event": existing}
        event = {"schema_version": "meta-alert-event-v1", "event": "OPENED",
                 "condition_key": condition_key, "severity": severity,
                 "message": message, "occurred_at": _instant(now).isoformat(),
                 "details": details or {}}
        event["event_hash"] = digest(event)
        _validate_artifact(event, "meta-alert-event-v1.schema.json")
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{event['occurred_at'].replace(':', '')}-{uuid.uuid4().hex[:8]}.json"
        write_json_exclusive(path, event)
        return {"status": "OPENED", "path": str(path.resolve()), "event": event}

    def resolve(self, condition_key: str, now: datetime | None = None) -> dict:
        existing = self.open_conditions().get(condition_key)
        if not existing:
            return {"status": "NOT_OPEN"}
        event = {"schema_version": "meta-alert-event-v1", "event": "RESOLVED",
                 "condition_key": condition_key, "severity": existing["severity"],
                 "message": existing["message"], "occurred_at": _instant(now).isoformat(),
                 "details": {"opened_event_hash": existing["event_hash"]}}
        event["event_hash"] = digest(event)
        _validate_artifact(event, "meta-alert-event-v1.schema.json")
        path = self.root / f"{event['occurred_at'].replace(':', '')}-{uuid.uuid4().hex[:8]}.json"
        write_json_exclusive(path, event)
        return {"status": "RESOLVED", "path": str(path.resolve()), "event": event}


class OperationLedger:
    """Immutable attempt identities with exclusive, ordered state receipts."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def identity(mode: str, origin_session: str, symbols: list[str], policy_hash: str) -> str:
        return digest({"mode": mode, "origin_session": origin_session,
                       "symbols": symbols, "policy_hash": policy_hash})

    def create(self, mode: str, origin_session: str, symbols: list[str], policy_hash: str,
               now: datetime | None = None) -> dict:
        key = self.identity(mode, origin_session, symbols, policy_hash)
        path = self.root / f"attempt-{key}"
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            path.mkdir()
        except FileExistsError:
            attempt = json.loads((path / "attempt.json").read_text())
            _validate_artifact(attempt, "meta-operation-attempt-v1.schema.json")
            identity = attempt.pop("attempt_hash")
            if digest(attempt) != identity:
                raise ValueError("Operation attempt integrity mismatch")
            attempt["attempt_hash"] = identity
            return {"status": "EXISTING", "path": path, "attempt": attempt}
        else:
            core = {"schema_version": "meta-operation-attempt-v1", "attempt_id": key,
                    "mode": mode, "origin_session": origin_session, "symbols": symbols,
                    "policy_hash": policy_hash, "created_at": _instant(now).isoformat()}
            core["attempt_hash"] = digest(core)
            _validate_artifact(core, "meta-operation-attempt-v1.schema.json")
            write_json_exclusive(path / "attempt.json", core)
            self.transition(path, "PLANNED", now, {"reason": "ATTEMPT_CREATED"})
            return {"status": "CREATED", "path": path, "attempt": core}

    @staticmethod
    def states(path: Path) -> list[dict]:
        rows = [json.loads(item.read_text()) for item in sorted((path / "states").glob("*.json"))]
        for index, row in enumerate(rows):
            _validate_artifact(row, "meta-operation-state-v1.schema.json")
            identity = row.pop("state_hash")
            if digest(row) != identity or row["sequence"] != index:
                raise ValueError("Operation state integrity or sequence mismatch")
            row["state_hash"] = identity
        return rows

    def transition(self, path: Path, state: str, now: datetime | None = None,
                   details: dict | None = None) -> Path:
        if state not in PIPELINE_STATES:
            raise ValueError("Unknown operation state")
        states = self.states(path)
        prior = states[-1]["state"] if states else None
        if prior in TERMINAL_STATES:
            raise ValueError("Cannot transition a terminal operation")
        if state not in ALLOWED_TRANSITIONS.get(prior, {"BLOCKED"}):
            raise ValueError(f"Invalid operation transition: {prior}->{state}")
        state_dir = path / "states"
        state_dir.mkdir(exist_ok=True)
        record = {"schema_version": "meta-operation-state-v1", "sequence": len(states),
                  "state": state, "prior_state": prior,
                  "occurred_at": _instant(now).isoformat(), "details": details or {}}
        record["state_hash"] = digest(record)
        _validate_artifact(record, "meta-operation-state-v1.schema.json")
        output = state_dir / f"{len(states):03d}-{state.lower()}.json"
        write_json_exclusive(output, record)
        return output


def schedule_decision(symbols: list[str], forecast_root: Path, operations_policy: dict,
                      now: datetime | None = None, mode: str = "PROSPECTIVE") -> dict:
    instant = _instant(now)
    if mode == "ON_DEMAND":
        return {"status": "READY", "mode": mode, "as_of": instant.isoformat(),
                "registration": False, "symbols": symbols}
    if mode != "PROSPECTIVE":
        raise ValueError("mode must be ON_DEMAND or PROSPECTIVE")
    preflight = postclose_preflight(symbols, forecast_root, instant)
    if preflight["status"] != "READY":
        return {**preflight, "mode": mode, "registration": True}
    cal = xcals.get_calendar("XNYS")
    close = cal.session_close(preflight["origin_session"]).to_pydatetime()
    scheduled = close + timedelta(minutes=operations_policy["scheduler"]["prospective_start_minutes_after_close"])
    if instant < scheduled:
        return {**preflight, "status": "WAIT_UNTIL_SCHEDULED", "mode": mode,
                "registration": True, "scheduled_at": scheduled.isoformat()}
    return {**preflight, "mode": mode, "registration": True,
            "scheduled_at": scheduled.isoformat()}


def doctor(policy_path: Path = DEFAULT_POLICY, root: Path = ROOT,
           forecast_root: Path | None = None) -> dict:
    policy = load_operations_policy(policy_path)
    checks = {
        "operations_policy": "OK",
        "node": "OK" if shutil.which("node") else "MISSING",
        "python": "OK" if shutil.which("python3") else "MISSING",
        "repository": "OK" if (root / "package.json").exists() else "MISSING",
        "forecast_root": "OK" if (forecast_root or root / "datasets/meta-observation/forecasts").exists()
                         else "EMPTY_NOT_ERROR",
        "dashboard_local_only": "OK" if policy["dashboard"]["bind_host"] == "127.0.0.1" else "ERROR",
        "prospective_model_attempts": "OK" if policy["budgets"]["prospective_attempts_per_role"] == 1 else "ERROR",
    }
    return {"schema_version": "meta-operations-health-v1",
            "status": "OK" if all(value in {"OK", "EMPTY_NOT_ERROR"} for value in checks.values()) else "ERROR",
            "checks": checks, "policy_hash": digest(policy)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("doctor", "plan", "attempt", "alert", "resolve-alert"))
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--symbols", nargs="+", default=["SPY", "QQQ", "AAPL", "MSFT", "NVDA"])
    parser.add_argument("--forecasts", type=Path, default=ROOT / "datasets/meta-observation/forecasts")
    parser.add_argument("--ledger", type=Path, default=ROOT / "datasets/meta-operations/attempts")
    parser.add_argument("--alerts", type=Path, default=ROOT / "datasets/meta-operations/alerts")
    parser.add_argument("--mode", choices=("ON_DEMAND", "PROSPECTIVE"), default="PROSPECTIVE")
    parser.add_argument("--now", type=datetime.fromisoformat)
    parser.add_argument("--condition")
    parser.add_argument("--severity", choices=("INFO", "WARNING", "ERROR", "CRITICAL"))
    parser.add_argument("--message")
    args = parser.parse_args()
    policy = load_operations_policy(args.policy)
    if args.action == "doctor":
        result = doctor(args.policy, forecast_root=args.forecasts)
    elif args.action == "plan":
        result = schedule_decision(args.symbols, args.forecasts, policy, args.now, args.mode)
    elif args.action == "attempt":
        decision = schedule_decision(args.symbols, args.forecasts, policy, args.now, args.mode)
        if decision["status"] != "READY":
            result = {"status": "ABSTAINED", "decision": decision}
        else:
            created = OperationLedger(args.ledger).create(
                args.mode, decision.get("origin_session", _instant(args.now).date().isoformat()),
                args.symbols, digest(policy), args.now)
            result = {**created, "path": str(created["path"].resolve()), "decision": decision}
    elif args.action == "alert":
        if not args.condition or not args.severity or not args.message:
            parser.error("alert requires --condition, --severity and --message")
        result = AlertLedger(args.alerts).emit(args.condition, args.severity, args.message, args.now)
    else:
        if not args.condition:
            parser.error("resolve-alert requires --condition")
        result = AlertLedger(args.alerts).resolve(args.condition, args.now)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
