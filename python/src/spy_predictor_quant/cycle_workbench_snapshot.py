"""Separately archived current workbench inputs: Fed release and IBKR daily bars.

No Cycle 1 archive is read. Metrics describe a snapshot acquired now, never a
historical point-in-time panel. ETF fundamentals remain explicitly unavailable.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re

import numpy as np

from spy_predictor_quant.market_archive import file_sha256, write_json_exclusive
from spy_predictor_quant.cycle_workbench_inputs import load_workbench_inputs
from spy_predictor_quant.cycle_workbench import assess, export_report

G17_BASE = 'https://www.federalreserve.gov/releases/g17/20260818/'
REQUIRED = ['growth', 'credit', 'psychology', 'stress', 'quality', 'valuation', 'timing']


def _now():
    return datetime.now(timezone.utc).isoformat()


class _Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None
    def handle_starttag(self, tag, attrs):
        if tag == 'tr': self.row = []
        if tag in ('td', 'th') and self.row is not None: self.cell = []
    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row, self.cell = None, None


def verify_growth(release: str, table: str) -> dict:
    dates = [re.search(r'Release Date:\s*([A-Za-z]+ \d+, \d{4})', text) for text in (release, table)]
    if not all(dates) or dates[0][1] != dates[1][1]:
        raise ValueError('Fed release and table dates disagree')
    published = datetime.strptime(dates[0][1], '%B %d, %Y').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    narrative = re.search(r'total IP in (\w+) was ([\d.]+) percent (above|below) its year-earlier level', release)
    if not narrative:
        raise ValueError('Missing explicit year-on-year total IP statement')
    value = float(narrative[2]) * (1 if narrative[3] == 'above' else -1)
    parser = _Rows()
    parser.feed(table)
    rows = [row for row in parser.rows if row and row[0] == 'Total IP']
    if len(rows) != 1 or float(rows[0][-1]) != value:
        raise ValueError('Narrative and independently extracted Total IP table cell disagree')
    month = datetime.strptime(narrative[1], '%B').month
    # Require the matching year-on-year column header, not just any last number.
    normalized = re.sub('<[^>]+>', '', table).replace('&nbsp;', ' ')
    year_suffix = str(published.year)[-2:]
    if not re.search(narrative[1] + r"\s*'" + year_suffix, normalized):
        raise ValueError('Table does not identify the expected current observation year')
    import calendar
    observed = published.replace(month=month, day=calendar.monthrange(published.year, month)[1])
    if observed >= published:
        raise ValueError('Observation must precede publication')
    return {'value': value, 'observed_at': observed.isoformat(), 'published_at': published.isoformat(),
            'verification': 'release-narrative-equals-table1-Total-IP-year-on-year-cell;same-publisher-two-extractions'}


def price_metrics(capture: dict, as_of: str) -> dict:
    import exchange_calendars as xcals
    cutoff = datetime.fromisoformat(as_of)
    received = datetime.fromisoformat(capture['received_at'])
    if received > cutoff or capture['symbol'] not in ('SPY', 'QQQ'):
        raise ValueError('Price snapshot not available at cutoff or wrong instrument')
    if capture['whatToShow'] != 'TRADES' or capture['barSize'] != '1 day' or capture['useRTH'] != 1:
        raise ValueError('Unsupported market-price convention')
    cal = xcals.get_calendar('XNYS')
    rows = []
    for bar in capture['bars']:
        day = datetime.strptime(bar['date'], '%Y%m%d').date()
        if not cal.is_session(day.isoformat()):
            raise ValueError('Unexpected non-session bar')
        close = cal.session_close(day.isoformat()).to_pydatetime()
        if close > cutoff:
            continue  # incomplete current session is never a finalized close
        values = [float(bar[k]) for k in ('open', 'high', 'low', 'close')]
        op, hi, lo, cl = values
        if not all(math.isfinite(v) and v > 0 for v in values) or lo > min(op, cl) or hi < max(op, cl) or lo > hi:
            raise ValueError('Invalid daily OHLC')
        rows.append((day, cl, close))
    if len(rows) < 200 or [r[0] for r in rows] != sorted(set(r[0] for r in rows)):
        raise ValueError('Need at least 200 distinct ordered daily closes')
    window = rows[-200:]
    expected = [x.date() for x in cal.sessions_in_range(window[0][0].isoformat(), window[-1][0].isoformat())]
    if [r[0] for r in window] != expected:
        raise ValueError('Internal daily session gap in moving-average window')
    # Do not call old bars a current price snapshot.
    eligible = [x for x in cal.sessions_in_range((cutoff.date()-timedelta(days=14)).isoformat(), cutoff.date().isoformat())
                if cal.session_close(x).to_pydatetime() <= cutoff]
    if not eligible or window[-1][0] != eligible[-1].date():
        raise ValueError('Price capture does not reach the latest completed trading session')
    prices = np.array([r[1] for r in window])
    ratio = float(prices[-1] / prices.mean())
    log_returns = np.diff(np.log(prices[-64:]))
    vol = float(log_returns.std(ddof=1) * math.sqrt(252) * 100)
    # Independently compute the two metrics with scalar arithmetic.
    independent_ratio = window[-1][1] * 200 / math.fsum(r[1] for r in window)
    scalar_returns = [math.log(window[i][1] / window[i-1][1]) for i in range(len(window)-63, len(window))]
    mean = math.fsum(scalar_returns) / 63
    independent_vol = math.sqrt(math.fsum((r-mean)**2 for r in scalar_returns) / 62 * 252) * 100
    if not math.isclose(ratio, independent_ratio, rel_tol=1e-12) or not math.isclose(vol, independent_vol, rel_tol=1e-10):
        raise ValueError('Independent metric recomputation failed')
    return {'price_to_ma200_ratio': ratio, 'realized_vol_pct': vol,
            'observed_at': window[-1][2].isoformat(), 'latest_close': window[-1][1],
            'window_start': window[0][0].isoformat(), 'sessions': len(window),
            'verification': 'complete-XNYS-window;NumPy-versus-independent-scalar-recomputation',
            'convention': 'IBKR-TRADES-split-adjusted-price-closes;cash-dividends-excluded;200-session-SMA;63-log-return-sample-volatility-annualized-sqrt252'}


def build_snapshot(root: Path) -> dict:
    root = root.resolve()
    as_of = _now()
    release_path, table_path = root / 'raw/g17-release.html', root / 'raw/g17-table1.html'
    growth = verify_growth(release_path.read_text(), table_path.read_text())
    def observation(metric, value, unit, identity, observed, published, first_seen, source, publisher, reference, max_age):
        return {'metric': metric, 'value': value, 'unit': unit, 'instrument_id': identity,
                'observed_at': observed, 'published_at': published, 'first_seen_at': first_seen,
                'retrieved_at': as_of, 'source_url': source, 'publisher': publisher,
                'source_reference': reference, 'revision': 'captured-' + as_of,
                'status': 'AVAILABLE', 'max_age_days': max_age, 'evidence': 'OBSERVED_AS_OF'}
    base = observation('growth_yoy_pct', growth['value'], 'percent', 'US_EQUITY', growth['observed_at'],
        growth['published_at'], as_of, G17_BASE + 'table1.htm', 'Board of Governors of the Federal Reserve System',
        'Total industrial production, seasonally adjusted, July 2026 over July 2025; preliminary; release narrative/table1 cross-check', 75)
    verification = {'as_of': as_of, 'scope': 'CURRENT_DESCRIPTIVE_SNAPSHOT_ONLY',
        'growth': growth, 'sources': [
            {'path': str(path.relative_to(root)), 'sha256': file_sha256(path), 'url': G17_BASE + name,
             'verified_at': as_of, 'first_seen_policy': 'conservative-verification-instant-no-historical-first-seen-claim'}
            for path, name in ((release_path, 'default.htm'), (table_path, 'table1.htm'))],
        'prices': {}, 'missing': ['credit', 'psychology', 'quality', 'valuation'],
        'realDatasetQualification': False, 'predictionPerformanceEstablished': False}
    captures = {}
    for symbol in ('SPY', 'QQQ'):
        path = root / 'raw' / (symbol + '-daily.json')
        if path.exists():
            capture = json.loads(path.read_text())
            metrics = price_metrics(capture, as_of)
            captures[symbol] = (capture, metrics)
            verification['prices'][symbol] = {'sha256': file_sha256(path), **metrics}
    # Broad US-equity realized volatility is represented by SPY, consistently
    # across both instrument panels. QQQ volatility remains a separate diagnostic.
    outputs = {}
    for symbol in ('SPY', 'QQQ'):
        observations = [base.copy()]
        for source_symbol, metric, unit, identity in (
                (symbol, 'price_to_ma200_ratio', 'ratio', symbol),
                ('SPY', 'realized_vol_pct', 'percent', 'US_EQUITY')):
            if source_symbol not in captures:
                continue
            capture, metrics = captures[source_symbol]
            observations.append(observation(metric, metrics[metric], unit, identity,
                metrics['observed_at'], capture['received_at'], capture['received_at'],
                'https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/', 'Interactive Brokers',
                source_symbol + ': ' + metrics['convention'] + '; publication conservatively bounded by API receipt', 7))
        snapshot = {'schema_version': 'cycle-workbench-observations-v1', 'observations': observations}
        snapshot_path = root / (symbol + '-observations.json')
        write_json_exclusive(snapshot_path, snapshot)
        manifest = {'schema_version': 'cycle-workbench-inputs-v1', 'transformation_version': 'illustrative-raw-metrics-v1',
                    'instrument_id': symbol, 'instrument_type': 'etf', 'market_id': 'US_EQUITY',
                    'evidence': 'OBSERVED_AS_OF', 'required_components': REQUIRED,
                    'snapshot': {'path': snapshot_path.name, 'sha256': file_sha256(snapshot_path)}}
        manifest_path = root / (symbol + '-manifest.json')
        write_json_exclusive(manifest_path, manifest)
        loaded = load_workbench_inputs(manifest_path, as_of=as_of, allowed_root=root)
        report = assess(loaded.observations, as_of=as_of, symbol=symbol, input_metadata=loaded.metadata)
        outputs[symbol] = export_report(report, root / 'assessments' / symbol, input_audit=loaded.audit)
    verification['outputs'] = outputs
    if 'SPY' not in captures: verification['missing'].append('stress')
    if len(captures) != 2: verification['missing'].append('timing-for-unavailable-price-captures')
    write_json_exclusive(root / 'verification.json', verification)
    return verification


def capture_prices(root: Path):
    """Two read-only contract resolutions and two bounded historical requests."""
    import os
    from dataclasses import replace
    from ibapi.contract import Contract
    from spy_predictor_quant.ibkr_config import GatewayConfig
    from spy_predictor_quant.ibkr_session import IbkrSession
    class Client(IbkrSession):
        def __init__(self, config):
            super().__init__(config)
            self.contracts, self.bars = {}, {}
        def contractDetails(self, reqId, details):
            self.contracts.setdefault(reqId, []).append(details.contract)
        def contractDetailsEnd(self, reqId):
            self.complete_request(reqId)
        def historicalData(self, reqId, bar):
            self.bars.setdefault(reqId, []).append({k: str(getattr(bar, k)) for k in ('date', 'open', 'high', 'low', 'close', 'volume')})
        def historicalDataEnd(self, reqId, start, end):
            self.complete_request(reqId)
    config = replace(GatewayConfig.from_environment(os.environ), client_id=83)
    (root / 'raw').mkdir(parents=True, exist_ok=True)
    with Client(config) as client:
        for symbol, exchange in (('SPY', 'ARCA'), ('QQQ', 'NASDAQ')):
            path = root / 'raw' / (symbol + '-daily.json')
            if path.exists():
                raise ValueError('Use a fresh capture directory; refusing to replace archived prices')
            query = Contract()
            query.symbol, query.secType, query.currency = symbol, 'STK', 'USD'
            query.exchange, query.primaryExchange = 'SMART', exchange
            request = client.begin_request()
            client.reqContractDetails(request, query)
            client.wait_for_request(request, symbol + ' contract identity', 30)
            contracts = client.contracts.get(request, [])
            if len(contracts) != 1:
                raise ValueError('Ambiguous IBKR contract identity')
            contract = contracts[0]
            if contract.symbol != symbol or contract.secType != 'STK' or contract.currency != 'USD' or contract.primaryExchange != exchange:
                raise ValueError('Unexpected IBKR resolved contract')
            contract.exchange = 'SMART'
            request = client.begin_request()
            client.reqHistoricalData(request, contract, '', '1 Y', '1 day', 'TRADES', 1, 1, False, [])
            client.wait_for_request(request, symbol + ' current daily price history', 45)
            payload = {'symbol': symbol, 'conId': contract.conId, 'primaryExchange': exchange,
                       'received_at': _now(), 'barSize': '1 day', 'whatToShow': 'TRADES', 'useRTH': 1,
                       'duration': '1 Y', 'bars': client.bars.get(request, []),
                       'evidence': 'CURRENT_RETRIEVAL_OF_RETROSPECTIVE_PRICE_HISTORY', 'read_only': True}
            write_json_exclusive(path, payload)
    return {'status': 'CAPTURED', 'symbols': ['SPY', 'QQQ'], 'root': str(root)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('capture-prices', 'build'))
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    result = capture_prices(args.root) if args.action == 'capture-prices' else build_snapshot(args.root)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
