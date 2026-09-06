"""Validation and immutable catalog helpers for resolved IBKR contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from spy_predictor_quant.ibkr_config import ContractQuery


CATALOG_IDENTITY_FIELDS = (
    "schemaVersion",
    "source",
    "mode",
    "querySchemaVersion",
    "queries",
    "contracts",
    "ibapiVersion",
    "serverVersion",
)


def validate_resolved_contracts(
    query: ContractQuery,
    records: Iterable[dict[str, object]],
) -> list[dict[str, object]]:
    matching: list[dict[str, object]] = []
    for record in records:
        if (
            record.get("symbol") == query.symbol
            and record.get("securityType") == query.security_type
            and record.get("currency") == query.currency
            and record.get("exchange") == query.exchange
            and (
                query.primary_exchange is None
                or record.get("primaryExchange") == query.primary_exchange
            )
        ):
            matching.append(record)

    unique_by_contract_id: dict[int, dict[str, object]] = {}
    for record in matching:
        contract_id = record.get("conId")
        if not isinstance(contract_id, int) or contract_id <= 0:
            raise ValueError(
                f"IBKR returned an invalid conId for {query.instrument}"
            )
        unique_by_contract_id[contract_id] = record

    validated = sorted(
        unique_by_contract_id.values(),
        key=lambda record: (
            str(record.get("expiration", "")),
            int(record["conId"]),
        ),
    )
    if not validated:
        raise ValueError(f"IBKR returned no matching contract for {query.instrument}")
    if query.security_type == "STK" and len(validated) != 1:
        raise ValueError(
            f"IBKR returned {len(validated)} matching stock contracts for "
            f"{query.instrument}; expected exactly one"
        )
    if query.security_type == "FUT":
        for record in validated:
            if not record.get("expiration"):
                raise ValueError(
                    f"IBKR returned a futures contract without an expiration for "
                    f"{query.instrument}"
                )
            if not record.get("localSymbol"):
                raise ValueError(
                    f"IBKR returned a futures contract without a local symbol for "
                    f"{query.instrument}"
                )
    return validated


def build_catalog(
    *,
    query_schema_version: str,
    queries: list[ContractQuery],
    contracts: dict[str, list[dict[str, object]]],
    ibapi_version: str,
    server_version: int,
    gateway_connection_time: str,
    warnings: list[dict[str, object]],
    captured_at: str | None = None,
) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "schemaVersion": "ibkr-contract-catalog-v1",
        "source": "ibkr-tws-api",
        "mode": "paper",
        "querySchemaVersion": query_schema_version,
        "queries": [query.as_manifest_entry() for query in queries],
        "contracts": contracts,
        "ibapiVersion": ibapi_version,
        "serverVersion": server_version,
    }
    catalog_hash = hashlib.sha256(_canonical_json(identity)).hexdigest()
    return {
        **identity,
        "gatewayConnectionTime": gateway_connection_time,
        "capturedAt": captured_at or datetime.now(timezone.utc).isoformat(),
        "warnings": warnings,
        "catalogHash": catalog_hash,
    }


def write_immutable_catalog(catalog: dict[str, Any], output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    catalog_hash = str(catalog["catalogHash"])
    output_path = output_root / f"catalog-{timestamp}-{catalog_hash[:16]}.json"
    with output_path.open("x", encoding="utf-8") as output:
        json.dump(catalog, output, indent=2, sort_keys=True)
        output.write("\n")
    return output_path


def verify_catalog_hash(catalog: dict[str, Any]) -> None:
    expected = catalog.get("catalogHash")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("IBKR contract catalog has no valid catalogHash")
    try:
        identity = {key: catalog[key] for key in CATALOG_IDENTITY_FIELDS}
    except KeyError as error:
        raise ValueError(f"IBKR contract catalog is missing {error.args[0]}") from error
    actual = hashlib.sha256(_canonical_json(identity)).hexdigest()
    if actual != expected:
        raise ValueError(
            f"IBKR contract catalog hash mismatch: expected {expected}, got {actual}"
        )


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
