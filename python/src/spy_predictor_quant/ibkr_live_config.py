"""Configuration for locally timestamped IBKR real-time bar capture."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from spy_predictor_quant.ibkr_history_config import ContractSelection


@dataclass(frozen=True)
class LiveCaptureSettings:
    bar_size_seconds: int
    what_to_show: str
    use_regular_trading_hours: bool
    duration_seconds: float
    maximum_reconnect_attempts: int
    reconnect_delay_seconds: float
    connection_timeout_seconds: float


@dataclass(frozen=True)
class LiveCapturePlan:
    schema_version: str
    settings: LiveCaptureSettings
    selections: tuple[ContractSelection, ...]


def load_live_capture_plan(
    path: Path,
    duration_override: float | None = None,
) -> LiveCapturePlan:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "ibkr-live-capture-v1":
        raise ValueError("Live schemaVersion must be ibkr-live-capture-v1")
    raw_settings = payload.get("settings")
    if not isinstance(raw_settings, dict):
        raise ValueError("Live configuration must contain settings")
    duration = (
        duration_override
        if duration_override is not None
        else _nonnegative_number(raw_settings, "durationSeconds")
    )
    if duration < 0:
        raise ValueError("Live capture duration must be non-negative")
    settings = LiveCaptureSettings(
        bar_size_seconds=_positive_int(raw_settings, "barSizeSeconds"),
        what_to_show=_required_text(raw_settings, "whatToShow"),
        use_regular_trading_hours=_required_bool(
            raw_settings, "useRegularTradingHours"
        ),
        duration_seconds=duration,
        maximum_reconnect_attempts=_nonnegative_int(
            raw_settings, "maximumReconnectAttempts"
        ),
        reconnect_delay_seconds=_nonnegative_number(
            raw_settings, "reconnectDelaySeconds"
        ),
        connection_timeout_seconds=_positive_number(
            raw_settings, "connectionTimeoutSeconds"
        ),
    )
    if settings.bar_size_seconds != 5:
        raise ValueError("IBKR real-time bars require a five-second bar size")
    if settings.what_to_show != "TRADES":
        raise ValueError("Initial live capture requires TRADES data")

    raw_contracts = payload.get("contracts")
    if not isinstance(raw_contracts, list):
        raise ValueError("Live configuration must contain contracts")
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
        raise ValueError("Every live contract selection must be an object")
    instruments = [selection.instrument for selection in selections]
    if set(instruments) != {"SPY", "QQQ", "ES", "NQ"}:
        raise ValueError("Live plan must select exactly SPY, QQQ, ES, and NQ")
    if len(instruments) != len(set(instruments)):
        raise ValueError("Live plan contains duplicate instruments")
    return LiveCapturePlan("ibkr-live-capture-v1", settings, selections)


def _required_text(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Live field {key} must be a non-empty string")
    return value.strip()


def _required_bool(raw: dict[str, object], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"Live field {key} must be boolean")
    return value


def _positive_int(raw: dict[str, object], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"Live field {key} must be a positive integer")
    return value


def _nonnegative_int(raw: dict[str, object], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"Live field {key} must be a non-negative integer")
    return value


def _positive_number(raw: dict[str, object], key: str) -> float:
    value = _nonnegative_number(raw, key)
    if value <= 0:
        raise ValueError(f"Live field {key} must be positive")
    return value


def _nonnegative_number(raw: dict[str, object], key: str) -> float:
    value = raw.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValueError(f"Live field {key} must be non-negative")
    return float(value)
