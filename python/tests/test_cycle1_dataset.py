from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path

import pytest

from spy_predictor_quant.cycle1_config import load_cycle1_plan
from spy_predictor_quant.cycle1_calendar import xnys_month_end, xnys_session_close
from spy_predictor_quant.cycle1_dataset import (
    Cycle1Acquisition,
    acquire_cycle1_sources,
    build_cycle1_dataset,
    _resolve_partitions,
)
from spy_predictor_quant.cycle1_alpaca import _action_records, normalize_alpaca_daily
from spy_predictor_quant.cycle1_fred import (
    _changed_observations,
    normalize_fred_observation,
    reconstruct_vintage_intervals,
)
from spy_predictor_quant.cycle1_source_audit import load_cycle1_source_audit
from spy_predictor_quant.cycle1_invesco import (
    import_invesco_qqq_snapshot,
    parse_invesco_qqq_distributions,
)
from spy_predictor_quant.cycle1_ibkr import (
    implied_distribution_diagnostics,
    normalize_ibkr_daily,
)
from spy_predictor_quant.cycle1_ssga import parse_ssga_spy_distributions
from spy_predictor_quant.historical_http import RequestLimiter, capture_resource
from spy_predictor_quant.market_archive import content_hash


REPO_ROOT = Path(__file__).resolve().parents[2]


def _plans():
    plan = load_cycle1_plan(REPO_ROOT / "config" / "cycle1.json")
    audit = load_cycle1_source_audit(
        REPO_ROOT / "config" / "cycle1-source-audit-v3.json", plan=plan
    )
    return plan, audit


def _acquirer(plan, audit, repo_root, raw_root, offline):
    del plan, audit, repo_root, raw_root, offline
    receipt = "2026-09-06T12:00:00+00:00"
    shiller = []
    daily = {"SPY": [], "QQQ": []}
    macro = []
    for index in range(336):
        year = 2000 + index // 12
        month = index % 12 + 1
        day = f"{year:04d}-{month:02d}-01"
        market_day = xnys_month_end(year, month)
        shiller_core = {
            "schemaVersion": "cycle1-shiller-month-v1", "provider": "shiller-yale",
            "provenanceTier": "RECONSTRUCTED_RESEARCH_ONLY", "observationMonth": day,
            "endpointSemantics": "monthly-average-not-month-end", "fields": {"cape": 20 + index / 100},
            "ingestedAt": receipt,
        }
        shiller.append({**shiller_core, "hash": content_hash(shiller_core)})
        for symbol in ("SPY", "QQQ"):
            price = 100 + index
            daily_core = {
                "schemaVersion": "cycle1-daily-market-v1", "provider": "fixture",
                "provenanceTier": "RECONSTRUCTED_RESEARCH_ONLY", "instrument": symbol,
                "sessionDate": market_day.isoformat(),
                "eventTime": xnys_session_close(market_day).isoformat(),
                "open": price, "high": price + 1, "low": price - 1, "close": price + 0.5,
                "volume": 1_000_000.0, "tradeCount": 1000,
                "weightedAveragePrice": price + 0.25, "ingestedAt": receipt,
            }
            daily[symbol].append({**daily_core, "hash": content_hash(daily_core)})
        for series_id in ("DGS3MO", "CPIAUCSL", "INDPRO", "MPRIME", "GS3M"):
            macro.append(normalize_fred_observation(series_id, {
                "date": day, "realtime_start": day, "realtime_end": "9999-12-31",
                "value": str(1 + index / 100),
            }, receipt))
    resources = {
        "shiller": [_raw("shiller", "shiller.xls")],
        "fred": [_raw("fred", f"{series}.json") for series in ("DGS3MO", "CPIAUCSL", "INDPRO", "MPRIME", "GS3M")],
        "alpaca-SPY": [_raw("alpaca", "SPY.json")],
        "alpaca-QQQ": [_raw("alpaca", "QQQ.json")],
    }
    return Cycle1Acquisition(resources, shiller, macro, daily, {"SPY": [], "QQQ": []})


def _raw(provider: str, path: str) -> dict:
    return {
        "provider": provider, "path": path, "sha256": "a" * 64,
        "requestUrl": f"https://example.test/{path}",
        "receivedAt": "2026-09-06T12:00:00+00:00", "records": 336,
    }


def test_builds_three_separate_immutable_track_manifests(tmp_path: Path) -> None:
    plan, audit = _plans()
    path, manifest = build_cycle1_dataset(
        plan=plan, audit=audit, repo_root=tmp_path, offline=True, acquirer=_acquirer,
        schema_root=REPO_ROOT,
    )
    assert path.exists()
    assert [track["trackId"] for track in manifest["tracks"]] == [
        "discovery-sp500", "validation-spy", "validation-qqq"
    ]
    for track in manifest["tracks"]:
        track_path = tmp_path / track["manifestPath"]
        assert track_path.exists()
        assert hashlib.sha256(track_path.read_bytes()).hexdigest() == track["manifestSha256"]
        track_manifest = json.loads(track_path.read_text(encoding="utf-8"))
        if track["role"] == "ACTUAL_ETF_VALIDATION":
            partitions = track_manifest["resolvedPartitions"]
            assert partitions["selection"]["labeledMonths"] >= 120
            assert partitions["embargo"]["labeledMonths"] == 12
            assert partitions["confirmation"]["labeledMonths"] == 96
            assert [half["labeledMonths"] for half in partitions["confirmation"]["halves"]] == [48, 48]


def test_same_inputs_reproduce_dataset_and_manifest_identity(tmp_path: Path) -> None:
    plan, audit = _plans()
    first_path, first = build_cycle1_dataset(
        plan=plan, audit=audit, repo_root=tmp_path, acquirer=_acquirer,
        schema_root=REPO_ROOT,
    )
    second_path, second = build_cycle1_dataset(
        plan=plan, audit=audit, repo_root=tmp_path, offline=True, acquirer=_acquirer,
        schema_root=REPO_ROOT,
    )
    assert first_path == second_path
    assert first["datasetIdentityHash"] == second["datasetIdentityHash"]


def test_macro_vintage_uses_conservative_release_timestamp() -> None:
    record = normalize_fred_observation("INDPRO", {
        "date": "2020-01-01", "realtime_start": "2020-02-14",
        "realtime_end": "2020-03-16", "value": "101.25",
    }, "2026-09-06T00:00:00+00:00")
    assert record["availableAt"] == "2020-02-14T23:59:59.999999+00:00"
    assert record["value"] == 101.25


def test_fred_change_events_reconstruct_nonoverlapping_vintage_intervals() -> None:
    changes = _changed_observations(
        {
            "observations": [
                {"date": "2020-01-01", "INDPRO_20200214": "101.0"},
                {"date": "2020-01-01", "INDPRO_20200316": "101.25"},
                {"date": "2020-02-01", "INDPRO_20200316": "102.0"},
                {"date": "2019-12-01"},
            ]
        },
        "INDPRO",
    )
    rows = reconstruct_vintage_intervals(
        [
            {**change, "_received_at": "2026-09-06T00:00:00+00:00"}
            for change in changes
        ]
    )
    assert rows[0]["realtime_start"] == "2020-02-14"
    assert rows[0]["realtime_end"] == "2020-03-15"
    assert rows[1]["realtime_start"] == "2020-03-16"
    assert rows[1]["realtime_end"] == "9999-12-31"
    assert rows[2]["date"] == "2020-02-01"


def test_alpaca_nested_corporate_actions_preserve_group_type() -> None:
    records = _action_records(
        {
            "corporate_actions": {
                "cash_dividends": [
                    {"id": "div-1", "symbol": "SPY", "ex_date": "2020-03-20"}
                ]
            },
            "next_page_token": None,
        }
    )
    assert records == [
        {
            "id": "div-1",
            "symbol": "SPY",
            "ex_date": "2020-03-20",
            "ca_type": "cash_dividend",
        }
    ]


def test_daily_cutoff_is_exact_scheduled_close_including_early_close() -> None:
    row = normalize_alpaca_daily(
        "SPY",
        {
            "t": "2024-11-29T05:00:00Z",
            "o": 100,
            "h": 102,
            "l": 99,
            "c": 101,
            "v": 1_000_000,
            "n": 1000,
            "vw": 100.5,
        },
        "2024-11-30T00:00:00+00:00",
    )
    assert row["eventTime"] == "2024-11-29T18:00:00+00:00"


def test_generic_resource_reuse_verifies_request_hash_and_count(tmp_path: Path) -> None:
    raw = b"one\ntwo\n"
    raw_path = tmp_path / "resource.bin"
    raw_path.write_bytes(raw)
    metadata = {
        "schemaVersion": "archived-http-resource-v1", "provider": "fixture",
        "requestUrl": "https://example.test/data", "httpStatus": 200,
        "receivedAt": "2026-09-06T00:00:00+00:00", "records": 2,
        "contentType": "application/octet-stream", "sha256": hashlib.sha256(raw).hexdigest(),
    }
    (tmp_path / "resource.bin.meta.json").write_text(json.dumps(metadata), encoding="utf-8")
    resource, value = capture_resource(
        provider="fixture", request_url="https://example.test/data", raw_path=raw_path,
        headers={}, limiter=RequestLimiter(60), content_type="application/octet-stream",
        count_records=lambda content: len(content.splitlines()), allow_network=False,
    )
    assert value == raw
    assert resource.records == 2
    raw_path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        capture_resource(
            provider="fixture", request_url="https://example.test/data", raw_path=raw_path,
            headers={}, limiter=RequestLimiter(60), content_type="application/octet-stream",
            count_records=lambda content: len(content.splitlines()), allow_network=False,
        )


def test_dataset_fails_when_frozen_model_coverage_is_impossible(tmp_path: Path) -> None:
    plan, audit = _plans()

    def short_acquirer(*args):
        data = _acquirer(*args)
        return Cycle1Acquisition(
            data.raw_resources,
            data.shiller[:200],
            data.macro,
            {symbol: rows[:200] for symbol, rows in data.daily.items()},
            data.actions,
        )

    with pytest.raises(ValueError, match="frozen protocol requires"):
        build_cycle1_dataset(
            plan=plan, audit=audit, repo_root=tmp_path, offline=True,
            acquirer=short_acquirer, schema_root=REPO_ROOT,
        )


def test_dataset_rejects_enough_rows_but_no_matured_selection_forecasts(tmp_path: Path) -> None:
    plan, audit = _plans()

    def infeasible_acquirer(*args):
        data = _acquirer(*args)
        return Cycle1Acquisition(
            data.raw_resources, data.shiller, data.macro,
            {symbol: rows[:-8] for symbol, rows in data.daily.items()}, data.actions,
        )

    with pytest.raises(ValueError, match="no selection forecasts with mature training labels"):
        build_cycle1_dataset(
            plan=plan, audit=audit, repo_root=tmp_path, offline=True,
            acquirer=infeasible_acquirer, schema_root=REPO_ROOT,
        )
    assert not list((tmp_path / "datasets" / "cycle1").glob("cycle1-monthly-*"))


def test_calendar_gap_cannot_be_disguised_as_a_twelve_row_embargo() -> None:
    plan, _ = _plans()
    dates = [xnys_month_end(2000 + index // 12, index % 12 + 1).isoformat() for index in range(240)]
    del dates[125]
    with pytest.raises(ValueError, match="consecutive calendar months"):
        _resolve_partitions(dates, plan.raw["partitions"])


def test_state_street_workbook_parser_preserves_exact_spy_cash_fields() -> None:
    headers = [
        "FUND NAME", "TICKER", "CUSIP", "EX-DATE", "RECORD DATE",
        "PAYABLE DATE", "DIVIDEND ($)", "SHORT TERM CAPITAL GAIN ($)",
        "LONG TERM CAPITAL GAIN ($)", "FREQUENCY",
    ]
    values = headers + [
        "State Street SPDR S&P 500 ETF Trust", "SPY", "78462F103",
        "03/19/1993", "03/25/1993", "04/30/1993", "0.213191", "", "", "Quarterly",
    ]
    shared = "".join(f"<si><t>{escape(value)}</t></si>" for value in values)
    rows = []
    for row_number, offset in ((1, 0), (2, 10)):
        cells = "".join(
            f'<c r="{chr(65 + column)}{row_number}" t="s"><v>{offset + column}</v></c>'
            for column in range(10)
        )
        rows.append(f'<row r="{row_number}">{cells}</row>')
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as workbook:
        workbook.writestr(
            "xl/sharedStrings.xml",
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            + shared
            + "</sst>",
        )
        workbook.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{''.join(rows)}</sheetData></worksheet>",
        )
    parsed = parse_ssga_spy_distributions(buffer.getvalue())
    assert parsed == [
        {
            "fundName": "State Street SPDR S&P 500 ETF Trust",
            "ticker": "SPY",
            "cusip": "78462F103",
            "exDate": "1993-03-19",
            "recordDate": "1993-03-25",
            "payableDate": "1993-04-30",
            "dividend": "0.213191",
            "shortTermCapitalGain": "0",
            "longTermCapitalGain": "0",
            "frequency": "Quarterly",
        }
    ]


def test_invesco_manual_snapshot_is_hash_verified_and_reusable(tmp_path: Path) -> None:
    source = tmp_path / "download.csv"
    source.write_text(
        "Ex-Date,Record Date,Pay Date,$/Share,Ordinary Income,Short Term Gains,Long Term Gains,Return of Capital,Liquidation Distribution\n"
        "12/17/2004,12/21/2004,12/31/2004,0.37858,0.37858,--,--,--,--\n",
        encoding="utf-8",
    )
    parsed = parse_invesco_qqq_distributions(source.read_bytes())
    assert parsed[0]["exDate"] == "2004-12-17"
    assert parsed[0]["distributionPerShare"] == "0.37858"
    archive = tmp_path / "archive"
    first, actions = import_invesco_qqq_snapshot(
        source_path=source, raw_directory=archive
    )
    second, repeated = import_invesco_qqq_snapshot(
        source_path=source, raw_directory=archive
    )
    assert first.sha256 == second.sha256
    assert actions == repeated
    assert actions[0]["raw"]["cash"] == 0.37858
    offline, offline_actions = import_invesco_qqq_snapshot(
        source_path=None, raw_directory=archive
    )
    assert offline.sha256 == first.sha256
    assert offline_actions == actions
    source.write_text(source.read_text().replace("0.37858", "0.4"), encoding="utf-8")
    with pytest.raises(ValueError, match="Immutable Invesco snapshot mismatch"):
        import_invesco_qqq_snapshot(source_path=source, raw_directory=archive)


def test_ibkr_daily_normalization_and_adjustment_diagnostic_are_separate() -> None:
    raw = [
        {
            "date": "20241127", "open": "99", "high": "101", "low": "98",
            "close": "100", "volume": "1000", "tradeCount": 10,
            "weightedAveragePrice": "99.5",
        },
        {
            "date": "20241129", "open": "98", "high": "100", "low": "97",
            "close": "99", "volume": "900", "tradeCount": 9,
            "weightedAveragePrice": "98.5",
        },
    ]
    trades = normalize_ibkr_daily(
        symbol="QQQ", kind="TRADES", bars=raw,
        received_at="2024-11-30T00:00:00+00:00", as_of=date(2024, 11, 29),
    )
    adjusted_raw = [dict(row) for row in raw]
    adjusted_raw[1]["close"] = "99.5"
    adjusted = normalize_ibkr_daily(
        symbol="QQQ", kind="ADJUSTED_LAST", bars=adjusted_raw,
        received_at="2024-11-30T00:00:00+00:00", as_of=date(2024, 11, 29),
    )
    diagnostic = implied_distribution_diagnostics(trades, adjusted)
    assert trades[1]["eventTime"] == "2024-11-29T18:00:00+00:00"
    assert diagnostic[0]["diagnosticOnly"] is True
    assert diagnostic[0]["sessionDate"] == "2024-11-29"


def test_ibkr_daily_drops_only_zero_activity_non_session_placeholders() -> None:
    placeholder = {
        "date": "20050221", "open": "37.33", "high": "37.33",
        "low": "37.33", "close": "37.33", "volume": "0",
        "tradeCount": 0, "weightedAveragePrice": "37.33",
    }
    valid = {
        "date": "20050222", "open": "37.03", "high": "37.55",
        "low": "36.79", "close": "36.89", "volume": "112781000",
        "tradeCount": 97795, "weightedAveragePrice": "37.109",
    }
    rows = normalize_ibkr_daily(
        symbol="QQQ", kind="TRADES", bars=[placeholder, valid],
        received_at="2026-09-05T00:00:00+00:00", as_of=date(2026, 9, 5),
    )
    assert [row["sessionDate"] for row in rows] == ["2005-02-22"]

    active_non_session = {**placeholder, "volume": "1", "tradeCount": 1}
    with pytest.raises(ValueError, match="activity on non-session 2005-02-21"):
        normalize_ibkr_daily(
            symbol="QQQ", kind="TRADES", bars=[active_non_session],
            received_at="2026-09-05T00:00:00+00:00", as_of=date(2026, 9, 5),
        )


def test_xnys_month_end_handles_first_etf_history_month() -> None:
    assert xnys_month_end(1993, 1) == date(1993, 1, 29)


def test_source_audit_v3_fails_before_network_without_manual_qqq_snapshot(
    tmp_path: Path,
) -> None:
    plan = load_cycle1_plan(REPO_ROOT / "config" / "cycle1.json")
    audit = load_cycle1_source_audit(
        REPO_ROOT / "config" / "cycle1-source-audit-v3.json", plan=plan
    )
    with pytest.raises(FileNotFoundError, match="browser-saved Invesco QQQ"):
        acquire_cycle1_sources(
            plan, audit, tmp_path, tmp_path / "raw", False
        )
