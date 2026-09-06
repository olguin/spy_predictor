"""Pure configuration models for the local IB Gateway integration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


SUPPORTED_SECURITY_TYPES = {"STK", "FUT"}
REQUIRED_INSTRUMENTS = {"SPY", "QQQ", "ES", "NQ"}


@dataclass(frozen=True)
class GatewayConfig:
    host: str
    port: int
    client_id: int
    mode: str
    read_only: bool

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> GatewayConfig:
        mode = environment.get("IBKR_MODE", "").strip()
        read_only_value = environment.get("IBKR_READ_ONLY", "").strip().lower()
        if mode != "paper":
            raise ValueError("IBKR_MODE must be paper")
        if read_only_value != "true":
            raise ValueError("IBKR_READ_ONLY must be true")

        host = environment.get("IBKR_HOST", "127.0.0.1").strip()
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError("IBKR_HOST must be localhost")

        port = int(environment.get("IBKR_PORT", "4002"))
        if port != 4002:
            raise ValueError("IBKR_PORT must be the paper IB Gateway port 4002")

        client_id = int(environment.get("IBKR_CLIENT_ID", "71"))
        if client_id < 0:
            raise ValueError("IBKR_CLIENT_ID must be non-negative")

        return cls(
            host=host,
            port=port,
            client_id=client_id,
            mode=mode,
            read_only=True,
        )


@dataclass(frozen=True)
class ContractQuery:
    instrument: str
    symbol: str
    security_type: str
    exchange: str
    currency: str
    primary_exchange: str | None = None

    def as_manifest_entry(self) -> dict[str, object]:
        entry: dict[str, object] = {
            "instrument": self.instrument,
            "symbol": self.symbol,
            "securityType": self.security_type,
            "exchange": self.exchange,
            "currency": self.currency,
        }
        if self.primary_exchange is not None:
            entry["primaryExchange"] = self.primary_exchange
        return entry


def load_contract_queries(path: Path) -> tuple[str, list[ContractQuery]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema_version = payload.get("schemaVersion")
    if schema_version != "ibkr-contract-query-v1":
        raise ValueError(
            "Contract configuration schemaVersion must be "
            "ibkr-contract-query-v1"
        )

    raw_instruments = payload.get("instruments")
    if not isinstance(raw_instruments, list) or not raw_instruments:
        raise ValueError("Contract configuration must contain instruments")

    queries: list[ContractQuery] = []
    for raw in raw_instruments:
        if not isinstance(raw, dict):
            raise ValueError("Every contract query must be an object")
        query = ContractQuery(
            instrument=_required_text(raw, "instrument"),
            symbol=_required_text(raw, "symbol"),
            security_type=_required_text(raw, "securityType"),
            exchange=_required_text(raw, "exchange"),
            currency=_required_text(raw, "currency"),
            primary_exchange=_optional_text(raw, "primaryExchange"),
        )
        if query.security_type not in SUPPORTED_SECURITY_TYPES:
            raise ValueError(
                f"Unsupported security type for {query.instrument}: "
                f"{query.security_type}"
            )
        queries.append(query)

    instruments = [query.instrument for query in queries]
    if len(instruments) != len(set(instruments)):
        raise ValueError("Contract configuration contains duplicate instruments")
    if set(instruments) != REQUIRED_INSTRUMENTS:
        raise ValueError(
            "Contract configuration must define exactly SPY, QQQ, ES, and NQ"
        )
    return schema_version, queries


def _required_text(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Contract query field {key} must be a non-empty string")
    return value.strip()


def _optional_text(raw: dict[str, object], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Contract query field {key} must be a non-empty string")
    return value.strip()
