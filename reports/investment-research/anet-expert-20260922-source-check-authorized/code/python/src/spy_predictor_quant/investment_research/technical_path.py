"""Point-in-time OHLCV summaries from archived daily-bar source documents."""

from decimal import Decimal
import json
from statistics import median


def completed_bars(store, evidence):
    """Exclude any bar later than the normalized completed-session cutoff."""
    data = evidence['data']
    if evidence.get('adapter') != 'alpaca_daily' or data.get('adjustment') != 'split_adjusted' or data.get('return_basis') != 'price_return':
        raise ValueError('Technical path requires split-adjusted daily price-return evidence')
    document = store.get('documents', evidence['document_id'])
    raw = json.loads(document['text'])
    bars = raw.get('bars')
    if not isinstance(bars, list):
        raise ValueError('Daily bar document has no bar series')
    dates = set()
    completed = []
    for bar in bars:
        date = bar['t'][:10]
        if date > data['price_date']:
            continue
        if date in dates or (completed and date <= completed[-1]['t'][:10]):
            raise ValueError('Daily bars have duplicate or unordered sessions')
        dates.add(date)
        high, low = Decimal(str(bar['h'])), Decimal(str(bar['l']))
        opened, close = Decimal(str(bar['o'])), Decimal(str(bar['c']))
        volume = Decimal(str(bar['v']))
        if low <= 0 or volume < 0 or high < max(opened, close) or low > min(opened, close):
            raise ValueError('Daily bar violates OHLCV bounds')
        completed.append(bar)
    if len(completed) < 64 or completed[-1]['t'][:10] != data['price_date']:
        raise ValueError('Daily bars do not cover the normalized completed session')
    if Decimal(str(completed[-1]['c'])) != Decimal(str(data['latest_close'])):
        raise ValueError('Archived close differs from normalized completed close')
    for horizon in (5, 21, 63):
        calculated = (Decimal(str(completed[-1]['c'])) / Decimal(str(completed[-horizon-1]['c'])) - 1) * 100
        if abs(calculated - Decimal(str(data[f'return{horizon}_pct']))) > Decimal('0.00001'):
            raise ValueError(f'Archived bars disagree with normalized {horizon}-session return')
    return completed, len(bars)-len(completed)


def _percent(value):
    return str(value.quantize(Decimal('0.0001')))


def metrics(bars, excluded):
    closes = [Decimal(str(bar['c'])) for bar in bars]
    volumes = [Decimal(str(bar['v'])) for bar in bars]
    last = closes[-1]
    sma20 = sum(closes[-20:]) / 20
    earlier_sma20 = sum(closes[-25:-5]) / 20
    prior21_high = max(closes[-22:-1])
    recent5_volume = sum(volumes[-5:]) / 5
    prior20_volume = Decimal(str(median(volumes[-25:-5])))
    prior20_latest = Decimal(str(median(volumes[-21:-1])))
    peak = closes[-64]
    max_drawdown = Decimal(0)
    for close in closes[-64:]:
        peak = max(peak, close)
        max_drawdown = min(max_drawdown, (close/peak-1)*100)
    return {'completed_sessions': len(bars), 'later_or_incomplete_bars_excluded': excluded,
            'sma20_change_over_5_sessions_pct': _percent((sma20/earlier_sma20-1)*100),
            'close_vs_prior_21_close_high_pct': _percent((last/prior21_high-1)*100),
            'last_volume_to_prior_20_median': _percent(volumes[-1]/prior20_latest) if prior20_latest else None,
            'recent_5_average_volume_to_preceding_20_median': _percent(recent5_volume/prior20_volume) if prior20_volume else None,
            'max_close_drawdown_63_pct': _percent(max_drawdown),
            'last_completed_date': bars[-1]['t'][:10]}


def seed(broker):
    rows, lineage = [], []
    for identity in broker.state['source_cache'].values():
        evidence = broker.store.get('evidence', identity)
        if evidence.get('adapter') != 'alpaca_daily':
            continue
        bars, excluded = completed_bars(broker.store, evidence)
        rows.append({'symbol': evidence['data']['symbol'], 'source_evidence_id': identity,
                     'feed': evidence['data']['feed'], 'adjustment': evidence['data']['adjustment'],
                     'return_basis': evidence['data']['return_basis'], **metrics(bars, excluded)})
        lineage.append(identity)
    if rows:
        broker.record({'kind': 'technical_path_panel', 'adapter': 'technical_path_v1',
            'data': {'instruments': rows}, 'input_evidence_ids': lineage,
            'qualification': 'Derived from archived source OHLCV only through each normalized completed-session date; later bars excluded. Volume ratios and levels are descriptive, not signals or execution estimates.'})
