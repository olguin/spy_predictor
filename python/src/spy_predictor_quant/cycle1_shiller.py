"""Immutable Shiller workbook acquisition for reconstructed discovery only."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from spy_predictor_quant.historical_http import ArchivedResource, RequestLimiter, capture_resource
from spy_predictor_quant.market_archive import content_hash


SHILLER_URL = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"


def capture_shiller(
    *, raw_directory: Path, offline: bool, limiter: RequestLimiter | None = None
) -> tuple[ArchivedResource, list[dict[str, Any]]]:
    resource, raw = capture_resource(
        provider="shiller-yale",
        request_url=SHILLER_URL,
        raw_path=raw_directory / "ie_data.xls",
        headers={"Accept": "application/vnd.ms-excel,application/octet-stream"},
        limiter=limiter or RequestLimiter(12),
        content_type="application/vnd.ms-excel",
        count_records=lambda value: len(parse_shiller_workbook(value)),
        allow_network=not offline,
    )
    return resource, normalize_shiller_rows(parse_shiller_workbook(raw), resource.received_at)


def parse_shiller_workbook(raw: bytes) -> list[dict[str, Any]]:
    try:
        import xlrd
    except ImportError as error:  # pragma: no cover - dependency failure path
        raise RuntimeError("xlrd is required to parse the pinned Shiller .xls workbook") from error
    workbook = xlrd.open_workbook(file_contents=raw)
    sheet = workbook.sheet_by_name("Data") if "Data" in workbook.sheet_names() else workbook.sheet_by_index(0)
    header_row = next(
        (index for index in range(min(sheet.nrows, 30)) if str(sheet.cell_value(index, 0)).strip().lower() == "date"),
        None,
    )
    if header_row is None:
        raise ValueError("Shiller workbook Data sheet has no Date header")
    headers = [_header(sheet.cell_value(header_row, column), column) for column in range(sheet.ncols)]
    rows: list[dict[str, Any]] = []
    for row_index in range(header_row + 1, sheet.nrows):
        date_value = sheet.cell_value(row_index, 0)
        if not isinstance(date_value, (int, float)) or isinstance(date_value, bool):
            continue
        month = _shiller_month(float(date_value))
        values = {headers[column]: _cell(sheet.cell_value(row_index, column)) for column in range(sheet.ncols)}
        rows.append({"month": month, "fields": values})
    if not rows:
        raise ValueError("Shiller workbook contains no monthly observations")
    return rows


def normalize_shiller_rows(rows: list[dict[str, Any]], received_at: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    previous = ""
    for row in rows:
        month = str(row["month"])
        if month <= previous:
            raise ValueError("Shiller months must be strictly increasing")
        previous = month
        core: dict[str, Any] = {
            "schemaVersion": "cycle1-shiller-month-v1",
            "provider": "shiller-yale",
            "provenanceTier": "RECONSTRUCTED_RESEARCH_ONLY",
            "observationMonth": month,
            "endpointSemantics": "monthly-average-not-month-end",
            "fields": row["fields"],
            "ingestedAt": received_at,
        }
        normalized.append({**core, "hash": content_hash(core)})
    return normalized


def _header(value: Any, column: int) -> str:
    text = str(value).strip().lower().replace(" ", "_").replace("/", "_")
    return text or f"column_{column}"


def _shiller_month(value: float) -> str:
    year = int(value)
    month = int(round((value - year) * 100))
    if year < 1800 or not 1 <= month <= 12:
        raise ValueError(f"Invalid Shiller month encoding {value}")
    return f"{year:04d}-{month:02d}-01"


def _cell(value: Any) -> Any:
    if value in {"", "NA", "N/A", "."}:
        return None
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        return value
    return str(value)
