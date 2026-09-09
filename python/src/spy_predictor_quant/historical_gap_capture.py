"""Two bounded read-only IBKR TRADES requests for missing development sessions."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from spy_predictor_quant.historical_development import encode, load_contract, verify, write_once
from spy_predictor_quant.market_archive import file_sha256

REQUESTS = [('2004-07-12', '20040717 00:00:00 UTC'),
            ('2007-07-02', '20070707 00:00:00 UTC')]


def capture(root: Path, *, variants: bool = False, venues: bool = False, hourly: bool = False, all_hours: bool = False, minimal: bool = False):
    from spy_predictor_quant.ibkr_config import GatewayConfig
    from spy_predictor_quant.ibkr_history import _make_exact_contract
    from spy_predictor_quant.ibkr_session import IbkrSession

    c, _ = load_contract(root)
    manifest = json.loads((root / c['sourceManifestPath']).read_text())
    entry = next(r for r in manifest['rawResources'] if r['path'] == 'ibkr/SPY/trades.json')
    original_path = root / 'datasets/cycle1/raw' / manifest['sourceAuditHash'][:16] / entry['path']
    verify(root, {str(original_path.relative_to(root)): entry['sha256']})
    original = json.loads(original_path.read_text())
    suffix = '-minimal' if minimal else '-all-hours' if all_hours else '-hourly' if hourly else '-venues' if venues else '-variants' if variants else ''
    folder = root / f'datasets/historical-development/gap-capture{suffix}-20260909'
    contract = original['contract']
    requests = ([('2004-07-12', '20040713 00:00:00 UTC', '1 D', exchange),
                 ('2007-07-02', '20070703 00:00:00 UTC', '1 D', exchange)]
                for exchange in ('SMART', 'ARCA')) if variants else [[(d, end, '10 D', 'SMART') for d, end in REQUESTS]]
    requests = [r for group in requests for r in group]
    if venues:
        requests = [('2004-07-12', '20040717 00:00:00 UTC', '10 D', 'AMEX'),
                    ('2007-07-02', '20070707 00:00:00 UTC', '10 D', 'ARCA')]
    if hourly:
        requests = [('2004-07-12', '20040713 00:00:00 UTC', '3 D', 'SMART'),
                    ('2007-07-02', '20070703 00:00:00 UTC', '3 D', 'SMART')]
    if minimal:
        requests = [(d, end.replace(' 00:00:00 UTC', '-00:00:00'), duration, exchange)
                    for d, end, duration, exchange in requests]
    bar_size = '1 hour' if hourly else '1 day'
    use_rth = 0 if all_hours else 1
    plan = {'instrument': 'SPY', 'conId': 756733, 'whatToShow': 'TRADES',
            'barSize': bar_size, 'duration': '3 D' if hourly else '10 D', 'useRTH': use_rth,
            'requests': requests if variants or venues or hourly or minimal else REQUESTS, 'sourceSha256': entry['sha256'],
            'finalEvaluationAccess': False, 'ordersAllowed': False}
    write_once(folder / 'plan.json', encode(plan))

    class Client(IbkrSession):
        def __init__(self):
            super().__init__(GatewayConfig('127.0.0.1', 4002, 89, 'paper', True))
            self.bars = {}

        def historicalData(self, reqId, bar):
            self.bars[reqId].append({'date': str(bar.date),
                **{k: repr(float(getattr(bar, k))) for k in ('open', 'high', 'low', 'close')},
                'volume': str(bar.volume), 'tradeCount': int(bar.barCount),
                'weightedAveragePrice': str(bar.wap)})

        def historicalDataEnd(self, reqId, start, end):
            self.complete_request(reqId)

    def filename(target, exchange):
        return f'{target}-{exchange}.json' if variants or venues else f'{target}.json'
    pending = [(d, end, duration, exchange) for d, end, duration, exchange in requests
               if not (folder / filename(d, exchange)).exists()]
    if pending:
        with Client() as client:
            for target, end, duration, exchange in pending:
                req = client.begin_request()
                client.bars[req] = []
                request_contract = {**contract, 'exchange': exchange}
                if minimal:
                    from ibapi.contract import Contract
                    request_contract = {'conId': 756733, 'exchange': 'SMART', 'currency': 'USD'}
                    sdk_contract = Contract()
                    sdk_contract.conId = 756733
                    sdk_contract.exchange = 'SMART'
                    sdk_contract.currency = 'USD'
                else:
                    sdk_contract = _make_exact_contract(request_contract)
                client.reqHistoricalData(req, sdk_contract, end,
                    duration, bar_size, 'TRADES', use_rth, 2 if hourly else 1, False, [])
                try:
                    client.wait_for_request(req, f'SPY gap {target}', 45)
                except Exception as exc:
                    client.cancelHistoricalData(req)
                    if not (variants or venues or hourly):
                        raise
                    failure = {'status': 'REQUEST_FAILED', 'targetSession': target, 'exchange': exchange,
                               'requestedEnd': end, 'duration': duration, 'error': str(exc),
                               'receivedAt': datetime.now(timezone.utc).isoformat()}
                    write_once(folder / filename(target, exchange), encode(failure))
                    print(json.dumps(failure), flush=True)
                    continue
                payload = {'schemaVersion': 'historical-development-gap-capture-v1',
                           'instrument': 'SPY', 'contract': request_contract, 'whatToShow': 'TRADES',
                           'targetSession': target, 'requestedEnd': end, 'duration': duration,
                           'barSize': bar_size, 'useRTH': use_rth,
                           'receivedAt': datetime.now(timezone.utc).isoformat(), 'bars': client.bars[req]}
                write_once(folder / filename(target, exchange), encode(payload))
                print(json.dumps({'targetSession': target, 'exchange': exchange, 'barSize': bar_size, 'bars': len(client.bars[req]),
                    'targetPresent': any((datetime.fromtimestamp(int(b['date']), timezone.utc).date().isoformat() == target
                                         if hourly else b['date'] == target.replace('-', '')) for b in client.bars[req])}), flush=True)
    receipt = {'planSha256': file_sha256(folder / 'plan.json'),
               'captures': {str((folder/filename(d, exchange)).relative_to(root)): file_sha256(folder/filename(d, exchange))
                            for d, _, _, exchange in requests}}
    write_once(folder / 'receipt.json', encode(receipt))
    return folder / 'receipt.json'


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--variants', action='store_true')
    group.add_argument('--venues', action='store_true')
    group.add_argument('--hourly', action='store_true')
    group.add_argument('--all-hours', action='store_true')
    group.add_argument('--minimal', action='store_true')
    args = parser.parse_args()
    print(capture(Path('.').resolve(), variants=args.variants, venues=args.venues, hourly=args.hourly, all_hours=args.all_hours, minimal=args.minimal))
