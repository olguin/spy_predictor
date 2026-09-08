"""Immutable State Street SPY distribution acquisition for Cycle 1."""

from __future__ import annotations

import math
import re
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from spy_predictor_quant.historical_http import (
    ArchivedResource,
    RequestLimiter,
    capture_resource,
)
from spy_predictor_quant.market_archive import content_hash


SSGA_DISTRIBUTIONS_URL = (
    "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
    "spdr-etf-historical-distributions.xlsx"
)
_SPREADSHEET_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
}
_EXPECTED_HEADERS = {
    "A": "FUND NAME",
    "B": "TICKER",
    "C": "CUSIP",
    "D": "EX-DATE",
    "E": "RECORD DATE",
    "F": "PAYABLE DATE",
    "G": "DIVIDEND ($)",
    "H": "SHORT TERM CAPITAL GAIN ($)",
    "I": "LONG TERM CAPITAL GAIN ($)",
    "J": "FREQUENCY",
}


def capture_ssga_spy_distributions(
    *, raw_directory: Path, offline: bool
) -> tuple[ArchivedResource, list[dict[str, Any]]]:
    resource, raw = capture_resource(
        provider="state-street-spdr-distributions",
        request_url=SSGA_DISTRIBUTIONS_URL,
        raw_path=raw_directory / "spdr-etf-historical-distributions.xlsx",
        headers={
            "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "User-Agent": "spy-predictor-cycle1/1.0",
        }
        if not offline
        else {},
        limiter=RequestLimiter(30),
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        count_records=lambda value: len(parse_ssga_spy_distributions(value)),
        allow_network=not offline,
    )
    return resource, normalize_ssga_spy_distributions(
        parse_ssga_spy_distributions(raw), resource.received_at
    )


def parse_ssga_spy_distributions(raw: bytes) -> list[dict[str, str]]:
    """Parse only the SPY rows from State Street's single-sheet OOXML file."""
    try:
        with zipfile.ZipFile(BytesIO(raw)) as workbook:
            shared = _shared_strings(workbook)
            sheet = ElementTree.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        raise ValueError("Invalid State Street distribution workbook") from error

    rows = sheet.findall(".//m:sheetData/m:row", _SPREADSHEET_NS)
    if not rows:
        raise ValueError("State Street distribution workbook has no rows")
    header = _xlsx_row(rows[0], shared)
    if header != _EXPECTED_HEADERS:
        raise ValueError("Unexpected State Street distribution workbook headers")

    parsed: list[dict[str, str]] = []
    for element in rows[1:]:
        values = _xlsx_row(element, shared)
        if values.get("B") != "SPY":
            continue
        if values.get("C") != "78462F103":
            raise ValueError("State Street SPY row has an unexpected CUSIP")
        ex_date = _us_date(values.get("D", ""), "ex-date")
        record_date = _us_date(values.get("E", ""), "record date")
        payable_date = _us_date(values.get("F", ""), "payable date")
        dividend = _nonnegative(values.get("G", ""), "dividend")
        short_gain = _nonnegative(values.get("H", ""), "short-term gain")
        long_gain = _nonnegative(values.get("I", ""), "long-term gain")
        if dividend + short_gain + long_gain <= 0:
            raise ValueError(f"State Street SPY row {ex_date} has no distribution")
        parsed.append(
            {
                "fundName": values.get("A", ""),
                "ticker": "SPY",
                "cusip": values["C"],
                "exDate": ex_date,
                "recordDate": record_date,
                "payableDate": payable_date,
                "dividend": _decimal_text(dividend),
                "shortTermCapitalGain": _decimal_text(short_gain),
                "longTermCapitalGain": _decimal_text(long_gain),
                "frequency": values.get("J", ""),
            }
        )
    parsed.sort(key=lambda row: row["exDate"])
    if len({row["exDate"] for row in parsed}) != len(parsed):
        raise ValueError("State Street SPY distributions contain duplicate ex-dates")
    return parsed


def normalize_ssga_spy_distributions(
    rows: list[dict[str, str]], received_at: str
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        cash = sum(
            float(row[key])
            for key in (
                "dividend",
                "shortTermCapitalGain",
                "longTermCapitalGain",
            )
        )
        core: dict[str, Any] = {
            "schemaVersion": "cycle1-corporate-action-v1",
            "provider": "state-street-spdr",
            "provenanceTier": "RECONSTRUCTED_RESEARCH_ONLY",
            "instrument": "SPY",
            "actionId": f"ssga-spy-{row['exDate']}",
            "actionType": "cash_dividend",
            "effectiveDate": row["exDate"],
            "raw": {**row, "cash": cash},
            "ingestedAt": received_at,
        }
        output.append({**core, "hash": content_hash(core)})
    return output


def _shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in item.findall(".//m:t", _SPREADSHEET_NS))
        for item in root.findall("m:si", _SPREADSHEET_NS)
    ]


def _xlsx_row(element: ElementTree.Element, shared: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for cell in element.findall("m:c", _SPREADSHEET_NS):
        reference = str(cell.get("r", ""))
        match = re.match(r"([A-Z]+)", reference)
        if match is None:
            raise ValueError(f"Invalid spreadsheet cell reference {reference}")
        column = match.group(1)
        value_node = cell.find("m:v", _SPREADSHEET_NS)
        value = "" if value_node is None else (value_node.text or "")
        if cell.get("t") == "s" and value:
            try:
                value = shared[int(value)]
            except (IndexError, ValueError) as error:
                raise ValueError(f"Invalid shared-string index at {reference}") from error
        values[column] = value.strip()
    return values


def _us_date(value: str, field: str) -> str:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise ValueError(f"Invalid State Street {field}: {value}") from error


def _nonnegative(value: str, field: str) -> float:
    if not value:
        return 0.0
    try:
        result = float(value)
    except ValueError as error:
        raise ValueError(f"Invalid State Street {field}: {value}") from error
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"State Street {field} must be nonnegative and finite")
    return result


def _decimal_text(value: float) -> str:
    return f"{value:.12f}".rstrip("0").rstrip(".") or "0"
