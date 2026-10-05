"""Deterministic historical forward-return frequencies for the current price regime.

These are descriptive empirical frequencies from the archived daily bars.  They are
not independent observations, calibrated forecasts, or substitutes for valuation.
"""

from decimal import Decimal, ROUND_HALF_UP

from .technical_path import completed_bars


HORIZONS = (5, 21, 63)


def _q(value):
    return str(Decimal(value).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def _percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * Decimal(str(fraction))
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _regime(closes, index):
    close = closes[index]
    sma20 = sum(closes[index-19:index+1]) / 20
    sma50 = sum(closes[index-49:index+1]) / 50
    return {
        'close_above_sma20': close >= sma20,
        'sma20_above_sma50': sma20 >= sma50,
        'return21_positive': close >= closes[index-21],
    }


def _summary(returns):
    positives = sum(value > 0 for value in returns)
    return {
        'sample_size': len(returns),
        'positive_count': positives,
        'positive_return_frequency_pct': _q(Decimal(positives) / len(returns) * 100),
        'median_forward_return_pct': _q(_percentile(returns, Decimal('0.50'))),
        'p10_forward_return_pct': _q(_percentile(returns, Decimal('0.10'))),
        'p90_forward_return_pct': _q(_percentile(returns, Decimal('0.90'))),
    }


def panel(store, evidence):
    bars, excluded = completed_bars(store, evidence)
    closes = [Decimal(str(row['c'])) for row in bars]
    current = _regime(closes, len(closes)-1)
    conditional = {h: [] for h in HORIZONS}
    unconditional = {h: [] for h in HORIZONS}
    first = 50
    last = len(closes) - max(HORIZONS) - 1
    for index in range(first, last + 1):
        same = _regime(closes, index) == current
        for horizon in HORIZONS:
            value = (closes[index+horizon] / closes[index] - 1) * 100
            unconditional[horizon].append(value)
            if same:
                conditional[horizon].append(value)
    if not all(conditional[h] for h in HORIZONS):
        raise ValueError('No historical analogs for current technical regime')
    return {
        'symbol': evidence['data']['symbol'],
        'as_of': evidence['data']['price_date'],
        'regime': current,
        'lookback_start': bars[first]['t'][:10],
        'lookback_end': bars[last]['t'][:10],
        'later_or_incomplete_bars_excluded': excluded,
        'horizons': {str(h): {'conditional_current_regime': _summary(conditional[h]),
                              'unconditional_base_rate': _summary(unconditional[h])}
                     for h in HORIZONS},
    }


def seed(broker):
    watchlist = {row['symbol'] for row in broker.state['mandate']['watchlist']}
    for identity in broker.state['source_cache'].values():
        evidence = broker.store.get('evidence', identity)
        if evidence.get('adapter') != 'alpaca_daily' or evidence.get('data', {}).get('symbol') not in watchlist:
            continue
        broker.record({
            'kind': 'technical_probability_panel',
            'adapter': 'historical_regime_forward_returns_v1',
            'symbols': [evidence['data']['symbol']],
            'data': panel(broker.store, evidence),
            'input_evidence_ids': [identity],
            'qualification': (
                'Historical overlapping forward-return frequencies conditional on three coarse price-regime signs. '
                'Samples are dependent, selected from one finite lookback, and are not calibrated probabilities, '
                'causal estimates, or guarantees. Report sample size and unconditional base rate alongside them.'),
        })
