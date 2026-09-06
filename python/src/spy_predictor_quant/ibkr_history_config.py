"""Configuration and exact-contract selection for IBKR history downloads."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from spy_predictor_quant.ibkr_contract_catalog import verify_catalog_hash


@dataclass(frozen=True)
class HistorySettings:
    bar_size: str
    what_to_show: str
    use_regular_trading_hours: bool
    format_date: int
    chunk_duration: str
    chunk_count: int
    end_lag_minutes: int
    request_timeout_seconds: float
    max_retries: int
    retry_base_seconds: float
    minimum_request_spacing_seconds: float
    maximum_requests_per_window: int
    pacing_window_seconds: float


@dataclass(frozen=True)
class ContractSelection:
    instrument: str
    contract_id: int
    local_symbol: str


@dataclass(frozen=True)
class HistoryPlan:
    schema_version: str
    settings: HistorySettings
    selections: tuple[ContractSelection, ...]


def load_history_plan(path: Path, chunk_override: int | None = None) -> HistoryPlan:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "ibkr-history-request-v1":
        raise ValueError("History schemaVersion must be ibkr-history-request-v1")

    raw_settings = payload.get("settings")
    if not isinstance(raw_settings, dict):
        raise ValueError("History configuration must contain settings")
    chunk_count = (
        chunk_override
        if chunk_override is not None
        else _positive_int(raw_settings, "chunkCount")
    )
    if chunk_count <= 0:
        raise ValueError("History chunk count must be positive")

    settings = HistorySettings(
        bar_size=_required_text(raw_settings, "barSize"),
        what_to_show=_required_text(raw_settings, "whatToShow"),
        use_regular_trading_hours=_required_bool(
            raw_settings, "useRegularTradingHours"
        ),
        format_date=_positive_int(raw_settings, "formatDate"),
        chunk_duration=_required_text(raw_settings, "chunkDuration"),
        chunk_count=chunk_count,
        end_lag_minutes=_nonnegative_int(raw_settings, "endLagMinutes"),
        request_timeout_seconds=_positive_float(
            raw_settings, "requestTimeoutSeconds"
        ),
        max_retries=_nonnegative_int(raw_settings, "maxRetries"),
        retry_base_seconds=_nonnegative_float(
            raw_settings, "retryBaseSeconds"
        ),
        minimum_request_spacing_seconds=_nonnegative_float(
            raw_settings, "minimumRequestSpacingSeconds"
        ),
        maximum_requests_per_window=_positive_int(
            raw_settings, "maximumRequestsPerWindow"
        ),
        pacing_window_seconds=_positive_float(
            raw_settings, "pacingWindowSeconds"
        ),
    )
    if settings.bar_size != "1 min":
        raise ValueError("Initial IBKR history adapter requires one-minute bars")
    if settings.what_to_show != "TRADES":
        raise ValueError("Initial IBKR history adapter requires TRADES data")
    if settings.format_date != 2:
        raise ValueError("IBKR history formatDate must be 2 for UTC epoch values")
    if settings.chunk_duration != "1 D":
        raise ValueError("One-minute downloads must use 1 D chunks")

    raw_contracts = payload.get("contracts")
    if not isinstance(raw_contracts, list):
        raise ValueError("History configuration must contain contracts")
    selections = tuple(
        ContractSelection(
            instrument=_required_text(raw, "instrument"),
            contract_id=_positive_int(raw, "conId"),
            local_symbol=_required_text(raw, "localSymbol"),
        )
        for raw in raw_contracts
        if isinstance(raw, dict)
    )
    if len(selections) != len(raw_contracts):
        raise ValueError("Every history contract selection must be an object")
    instruments = [selection.instrument for selection in selections]
    if set(instruments) != {"SPY", "QQQ", "ES", "NQ"}:
        raise ValueError("History plan must select exactly SPY, QQQ, ES, and NQ")
    if len(instruments) != len(set(instruments)):
        raise ValueError("History plan contains duplicate instruments")
    return HistoryPlan("ibkr-history-request-v1", settings, selections)


def select_catalog_contracts(
    catalog: dict[str, Any],
    plan: HistoryPlan,
) -> dict[str, dict[str, object]]:
    return select_contract_records(catalog, plan.selections)


def select_contract_records(
    catalog: dict[str, Any],
    selections: tuple[ContractSelection, ...],
) -> dict[str, dict[str, object]]:
    verify_catalog_hash(catalog)
    if catalog.get("schemaVersion") != "ibkr-contract-catalog-v1":
        raise ValueError("Unsupported IBKR contract catalog")
    raw_contracts = catalog.get("contracts")
    if not isinstance(raw_contracts, dict):
        raise ValueError("Contract catalog is missing contracts")

    selected: dict[str, dict[str, object]] = {}
    for selection in selections:
        candidates = raw_contracts.get(selection.instrument)
        if not isinstance(candidates, list):
            raise ValueError(
                f"Catalog is missing instrument {selection.instrument}"
            )
        matches = [
            candidate
            for candidate in candidates
            if isinstance(candidate, dict)
            and candidate.get("conId") == selection.contract_id
            and candidate.get("localSymbol") == selection.local_symbol
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Catalog does not contain exactly one {selection.instrument} "
                f"contract matching conId {selection.contract_id} and "
                f"localSymbol {selection.local_symbol}"
            )
        selected[selection.instrument] = dict(matches[0])
    return selected


def is_transient_history_error(errors: list[dict[str, object]]) -> bool:
    for error in errors:
        code = int(error.get("code", 0))
        message = str(error.get("message", "")).lower()
        if code in {1100, 1101, 2103, 2105}:
            return True
        if code in {162, 420} and "pacing" in message:
            return True
    return False


def trading_weekday_endpoints(end: datetime, count: int) -> list[datetime]:
    if end.tzinfo is None:
        raise ValueError("History endpoint must contain an explicit timezone")
    if count <= 0:
        raise ValueError("History endpoint count must be positive")
    eastern = ZoneInfo("America/New_York")
    endpoints: list[datetime] = []
    candidate = end
    while len(endpoints) < count:
        if candidate.astimezone(eastern).weekday() < 5:
            endpoints.append(candidate)
        candidate -= timedelta(days=1)
    return endpoints


def find_latest_catalog(root: Path) -> Path:
    candidates = sorted(root.glob("catalog-*.json"))
    if not candidates:
        raise FileNotFoundError(f"No IBKR contract catalog found under {root}")
    return candidates[-1]


def _required_text(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"History field {key} must be a non-empty string")
    return value.strip()


def _required_bool(raw: dict[str, object], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"History field {key} must be boolean")
    return value


def _positive_int(raw: dict[str, object], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"History field {key} must be a positive integer")
    return value


def _nonnegative_int(raw: dict[str, object], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"History field {key} must be a non-negative integer")
    return value


def _positive_float(raw: dict[str, object], key: str) -> float:
    value = raw.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"History field {key} must be positive")
    return float(value)


def _nonnegative_float(raw: dict[str, object], key: str) -> float:
    value = raw.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValueError(f"History field {key} must be non-negative")
    return float(value)
