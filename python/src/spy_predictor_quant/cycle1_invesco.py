"""Hash-verified manual Invesco QQQ distribution snapshot import.

Invesco's site prohibits repeated automated extraction and currently returns
HTTP 406 to the archive client.  This module therefore imports a single
user-saved sponsor table without making a network request.
"""

from __future__ import annotations

import csv
import json
import math
import re
from datetime import datetime
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Any

from spy_predictor_quant.historical_http import ArchivedResource
from spy_predictor_quant.market_archive import (
    content_hash,
    file_sha256,
    utc_now,
    write_bytes_exclusive,
    write_json_exclusive,
)


INVESCO_QQQ_PRODUCT_URL = (
    "https://www.invesco.com/us/en/financial-products/etfs/"
    "invesco-qqq-trust-series-1.html"
)
_COLUMN_ALIASES = {
    "exdate": "exDate",
    "recorddate": "recordDate",
    "paydate": "payDate",
    "payabledate": "payDate",
    "share": "distributionPerShare",
    "pershare": "distributionPerShare",
    "distributionpershare": "distributionPerShare",
    "ordinaryincome": "ordinaryIncome",
    "shorttermgains": "shortTermGains",
    "longtermgains": "longTermGains",
    "returnofcapital": "returnOfCapital",
    "liquidationdistribution": "liquidationDistribution",
}
_REQUIRED_FIELDS = {"exDate", "recordDate", "payDate", "distributionPerShare"}


def import_invesco_qqq_snapshot(
    *, source_path: Path | None, raw_directory: Path
) -> tuple[ArchivedResource, list[dict[str, Any]]]:
    """Copy one browser-saved sponsor snapshot into the immutable raw archive."""
    existing = [
        path
        for path in (
            raw_directory / "qqq-distributions.csv",
            raw_directory / "qqq-distributions.html",
        )
        if path.exists()
    ]
    if len(existing) > 1:
        raise ValueError("Multiple immutable Invesco QQQ snapshots exist")
    if source_path is None:
        if not existing:
            raise FileNotFoundError("Offline run is missing the Invesco QQQ snapshot")
        raw_path = existing[0]
        raw = raw_path.read_bytes()
    else:
        if not source_path.is_file():
            raise FileNotFoundError(f"Invesco QQQ sponsor snapshot is missing: {source_path}")
        raw = source_path.read_bytes()
        suffix = ".html" if _looks_like_html(raw) else ".csv"
        raw_path = raw_directory / f"qqq-distributions{suffix}"
        if existing and existing[0] != raw_path:
            raise ValueError("Invesco snapshot format differs from the immutable archive")
    rows = parse_invesco_qqq_distributions(raw)
    raw_directory.mkdir(parents=True, exist_ok=True)
    metadata_path = raw_path.with_name(raw_path.name + ".meta.json")
    received_at = utc_now()
    if raw_path.exists():
        if raw_path.read_bytes() != raw:
            raise ValueError(f"Immutable Invesco snapshot mismatch at {raw_path}")
        if not metadata_path.exists():
            raise ValueError(f"Immutable Invesco metadata is missing at {metadata_path}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        received_at = str(metadata.get("receivedAt", ""))
    else:
        digest = write_bytes_exclusive(raw_path, raw)
        metadata = {
            "schemaVersion": "archived-manual-resource-v1",
            "provider": "invesco-qqq",
            "requestUrl": INVESCO_QQQ_PRODUCT_URL,
            "acquisitionMethod": "single-browser-saved-sponsor-snapshot",
            "receivedAt": received_at,
            "records": len(rows),
            "contentType": "text/html" if raw_path.suffix == ".html" else "text/csv",
            "sha256": digest,
        }
        write_json_exclusive(metadata_path, metadata)
    _verify_metadata(metadata, raw_path, len(rows))
    resource = ArchivedResource(
        provider="invesco-qqq",
        path=raw_path,
        sha256=file_sha256(raw_path),
        received_at=received_at,
        request_url=INVESCO_QQQ_PRODUCT_URL,
        records=len(rows),
        content_type=str(metadata["contentType"]),
    )
    return resource, normalize_invesco_qqq_distributions(rows, received_at)


def parse_invesco_qqq_distributions(raw: bytes) -> list[dict[str, str]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Invesco snapshot must be UTF-8 HTML or CSV") from error
    table = _html_table(text) if _looks_like_html(raw) else _csv_table(text)
    if not table:
        raise ValueError("Invesco snapshot contains no distribution rows")
    header = [_canonical_header(value) for value in table[0]]
    if not _REQUIRED_FIELDS.issubset(set(header)):
        raise ValueError(
            "Invesco snapshot lacks Ex-Date, Record Date, Pay Date, or $/Share"
        )
    output: list[dict[str, str]] = []
    for values in table[1:]:
        if not any(value.strip() for value in values):
            continue
        padded = values + [""] * (len(header) - len(values))
        row = {key: value.strip() for key, value in zip(header, padded, strict=False) if key}
        ex_date = _us_date(row.get("exDate", ""), "ex-date")
        amount = _money(row.get("distributionPerShare", ""), "distribution per share")
        if amount <= 0:
            raise ValueError(f"Invesco QQQ row {ex_date} has no positive distribution")
        normalized = {
            "exDate": ex_date,
            "recordDate": _us_date(row.get("recordDate", ""), "record date"),
            "payDate": _us_date(row.get("payDate", ""), "pay date"),
            "distributionPerShare": _decimal_text(amount),
        }
        for key in (
            "ordinaryIncome",
            "shortTermGains",
            "longTermGains",
            "returnOfCapital",
            "liquidationDistribution",
        ):
            normalized[key] = _decimal_text(_money(row.get(key, ""), key))
        output.append(normalized)
    output.sort(key=lambda row: row["exDate"])
    dates = [row["exDate"] for row in output]
    if len(dates) != len(set(dates)):
        raise ValueError("Invesco QQQ distributions contain duplicate ex-dates")
    return output


def normalize_invesco_qqq_distributions(
    rows: list[dict[str, str]], received_at: str
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        core: dict[str, Any] = {
            "schemaVersion": "cycle1-corporate-action-v1",
            "provider": "invesco-qqq",
            "provenanceTier": "RECONSTRUCTED_RESEARCH_ONLY",
            "instrument": "QQQ",
            "actionId": f"invesco-qqq-{row['exDate']}",
            "actionType": "cash_dividend",
            "effectiveDate": row["exDate"],
            "raw": {**row, "cash": float(row["distributionPerShare"])},
            "ingestedAt": received_at,
        }
        output.append({**core, "hash": content_hash(core)})
    return output


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def _html_table(text: str) -> list[list[str]]:
    parser = _TableParser()
    parser.feed(text)
    for table in parser.tables:
        if table and _REQUIRED_FIELDS.issubset(
            {_canonical_header(value) for value in table[0]}
        ):
            return table
    return []


def _csv_table(text: str) -> list[list[str]]:
    return [list(row) for row in csv.reader(StringIO(text))]


def _canonical_header(value: str) -> str:
    compact = re.sub(r"[^a-z]", "", value.lower())
    return _COLUMN_ALIASES.get(compact, "")


def _looks_like_html(raw: bytes) -> bool:
    return raw.lstrip().lower().startswith((b"<!doctype html", b"<html"))


def _us_date(value: str, field: str) -> str:
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Invalid Invesco {field}: {value}")


def _money(value: str, field: str) -> float:
    stripped = value.strip().replace("$", "").replace(",", "")
    if stripped in {"", "-", "--", "—", "–"}:
        return 0.0
    try:
        result = float(stripped)
    except ValueError as error:
        raise ValueError(f"Invalid Invesco {field}: {value}") from error
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Invesco {field} must be nonnegative and finite")
    return result


def _decimal_text(value: float) -> str:
    return f"{value:.12f}".rstrip("0").rstrip(".") or "0"


def _verify_metadata(metadata: dict[str, Any], path: Path, records: int) -> None:
    if metadata.get("schemaVersion") != "archived-manual-resource-v1":
        raise ValueError(f"Invalid Invesco snapshot metadata at {path}")
    if metadata.get("requestUrl") != INVESCO_QQQ_PRODUCT_URL:
        raise ValueError(f"Invesco snapshot request identity mismatch at {path}")
    if metadata.get("sha256") != file_sha256(path):
        raise ValueError(f"Invesco snapshot hash mismatch at {path}")
    if metadata.get("records") != records:
        raise ValueError(f"Invesco snapshot record count mismatch at {path}")
    if not str(metadata.get("receivedAt", "")):
        raise ValueError(f"Invesco snapshot receipt timestamp is missing at {path}")
