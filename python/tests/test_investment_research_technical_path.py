"""Archived OHLCV must stop at the recorded completed-session cutoff."""

from datetime import date, timedelta
import json

import pytest

from spy_predictor_quant.investment_research.technical_path import completed_bars, metrics


def price_fixture():
    start = date(2026, 5, 1)
    bars = []
    for i in range(70):
        close = 100 + i
        bars.append({'t': (start+timedelta(days=i)).isoformat()+'T04:00:00Z',
                     'o': close, 'h': close+1, 'l': close-1,
                     'c': close, 'v': 1000+i})
    completed = bars[:69]
    evidence = {'adapter': 'alpaca_daily', 'document_id': 'document',
                'data': {'price_date': completed[-1]['t'][:10], 'latest_close': completed[-1]['c'],
                         'adjustment': 'split_adjusted', 'return_basis': 'price_return',
                         **{f'return{n}_pct': (completed[-1]['c']/completed[-n-1]['c']-1)*100 for n in (5, 21, 63)}}}
    return bars, evidence


def test_derived_path_excludes_later_bar_and_reconciles_returns():
    bars, evidence = price_fixture()

    class Store:
        def get(self, kind, identity):
            assert (kind, identity) == ('documents', 'document')
            return {'text': json.dumps({'bars': bars})}

    completed, excluded = completed_bars(Store(), evidence)
    assert excluded == 1 and completed[-1]['c'] == 168
    panel = metrics(completed, excluded)
    assert panel['later_or_incomplete_bars_excluded'] == 1
    assert float(panel['sma20_change_over_5_sessions_pct']) > 0
    assert float(panel['close_vs_prior_21_close_high_pct']) > 0
    evidence['data']['latest_close'] = 169
    with pytest.raises(ValueError, match='Archived close differs'):
        completed_bars(Store(), evidence)
