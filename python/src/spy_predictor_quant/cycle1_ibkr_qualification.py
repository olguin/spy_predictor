"""Read-only, non-persisting IBKR coverage probe for Cycle 1 source audit."""

from __future__ import annotations

import argparse
import json
import math
import os
import threading
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spy_predictor_quant.ibkr_config import GatewayConfig
from spy_predictor_quant.ibkr_contract_catalog import verify_catalog_hash
from spy_predictor_quant.ibkr_history import _ibkr_end_time, _make_exact_contract
from spy_predictor_quant.ibkr_history_config import find_latest_catalog
from spy_predictor_quant.ibkr_session import IbkrSession


class CoverageProbeClient(IbkrSession):
    """Collect only dates and closes in memory; write no provider data."""

    def __init__(self, config: GatewayConfig) -> None:
        super().__init__(config)
        self._contexts: dict[int, tuple[str, str]] = {}
        self._bars: dict[tuple[str, str], list[tuple[str, float]]] = {}
        self._lock = threading.Lock()

    def register_probe(self, request_id: int, symbol: str, kind: str) -> None:
        self._contexts[request_id] = (symbol, kind)
        self._bars[(symbol, kind)] = []

    def historicalData(self, reqId: int, bar: object) -> None:  # noqa: N802
        key = self._contexts[reqId]
        close = float(getattr(bar, "close"))
        with self._lock:
            self._bars[key].append((str(getattr(bar, "date")), close))

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:  # noqa: N802
        del start, end
        self.complete_request(reqId)

    def bars(self, symbol: str, kind: str) -> list[tuple[str, float]]:
        with self._lock:
            return list(self._bars[(symbol, kind)])


def run_probe(
    *,
    catalog_path: Path,
    as_of: datetime,
    duration: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    verify_catalog_hash(catalog)
    contracts = catalog.get("contracts")
    if not isinstance(contracts, dict):
        raise ValueError("IBKR catalog is missing contracts")
    selected: dict[str, dict[str, object]] = {}
    for symbol in ("SPY", "QQQ"):
        matches = contracts.get(symbol)
        if not isinstance(matches, list) or len(matches) != 1:
            raise ValueError(f"IBKR catalog must contain one exact {symbol} contract")
        selected[symbol] = matches[0]

    base_config = GatewayConfig.from_environment(os.environ)
    config = replace(base_config, client_id=base_config.client_id + 1)
    results: list[dict[str, Any]] = []
    with CoverageProbeClient(config) as client:
        for symbol in ("SPY", "QQQ"):
            for kind in ("TRADES", "ADJUSTED_LAST"):
                request_id = client.begin_request()
                client.register_probe(request_id, symbol, kind)
                client.reqHistoricalData(
                    request_id,
                    _make_exact_contract(selected[symbol]),
                    "" if kind == "ADJUSTED_LAST" else _ibkr_end_time(as_of),
                    duration,
                    "1 day",
                    kind,
                    1,
                    1,
                    False,
                    [],
                )
                client.wait_for_request(
                    request_id,
                    f"Cycle 1 {symbol} {kind} coverage probe",
                    timeout_seconds,
                )
                bars = client.bars(symbol, kind)
                if not bars:
                    raise ValueError(f"IBKR returned no {symbol} {kind} daily bars")
                results.append(
                    {
                        "instrument": symbol,
                        "whatToShow": kind,
                        "records": len(bars),
                        "first": bars[0][0],
                        "last": bars[-1][0],
                        "positiveFiniteCloses": all(
                            close > 0 and close not in {float("inf"), float("-inf")}
                            for _, close in bars
                        ),
                    }
                )
        implied_distributions = [
            _implied_distribution_summary(
                symbol,
                client.bars(symbol, "TRADES"),
                client.bars(symbol, "ADJUSTED_LAST"),
            )
            for symbol in ("SPY", "QQQ")
        ]
    return {
        "status": "ok",
        "mode": config.mode,
        "readOnly": config.read_only,
        "catalogHash": catalog["catalogHash"],
        "asOf": as_of.isoformat(),
        "duration": duration,
        "results": results,
        "impliedDistributions": implied_distributions,
        "providerRowsPersisted": 0,
    }


def _implied_distribution_summary(
    symbol: str,
    trades: list[tuple[str, float]],
    adjusted: list[tuple[str, float]],
) -> dict[str, Any]:
    trade_by_date = dict(trades)
    adjusted_by_date = dict(adjusted)
    dates = sorted(set(trade_by_date) & set(adjusted_by_date))
    if len(dates) < 2:
        raise ValueError(f"IBKR {symbol} series do not overlap")
    implied: list[tuple[str, float]] = []
    return_residuals: list[float] = []
    for previous_date, current_date in zip(dates, dates[1:], strict=False):
        previous_trade = trade_by_date[previous_date]
        current_trade = trade_by_date[current_date]
        previous_adjusted = adjusted_by_date[previous_date]
        current_adjusted = adjusted_by_date[current_date]
        adjusted_growth = current_adjusted / previous_adjusted
        cash = previous_trade * adjusted_growth - current_trade
        implied.append((current_date, cash))
        return_residuals.append(abs(math.log(adjusted_growth / (current_trade / previous_trade))))
    material = [(day, cash) for day, cash in implied if cash > 0.0001]
    negative = [(day, cash) for day, cash in implied if cash < -0.0001]
    counts_by_year: dict[str, int] = {}
    for day, _ in material:
        counts_by_year[day[:4]] = counts_by_year.get(day[:4], 0) + 1
    return {
        "instrument": symbol,
        "sharedSessions": len(dates),
        "positiveEventsAbove0001": len(material),
        "negativeEventsBelowMinus0001": len(negative),
        "maximumPositiveCash": max((cash for _, cash in material), default=0.0),
        "minimumNegativeCash": min((cash for _, cash in negative), default=0.0),
        "maximumNonEventReturnDifferenceBps": max(
            (
                residual * 10_000
                for (_, cash), residual in zip(implied, return_residuals, strict=True)
                if abs(cash) <= 0.0001
            ),
            default=0.0,
        ),
        "firstMaterialEvent": material[0][0] if material else None,
        "lastMaterialEvent": material[-1][0] if material else None,
        "materialEventsByYear": counts_by_year,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--catalog-root", type=Path, default=Path("datasets/ibkr/contracts"))
    parser.add_argument("--as-of", default="2026-09-05T00:00:00+00:00")
    parser.add_argument("--duration", default="40 Y")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    args = parser.parse_args()
    catalog_path = args.catalog or find_latest_catalog(args.catalog_root)
    result = run_probe(
        catalog_path=catalog_path,
        as_of=datetime.fromisoformat(args.as_of).astimezone(timezone.utc),
        duration=args.duration,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
