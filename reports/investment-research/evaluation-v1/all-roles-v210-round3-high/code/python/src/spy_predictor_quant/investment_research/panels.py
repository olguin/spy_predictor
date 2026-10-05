"""Read-only, deterministic comparisons over admitted normalized source evidence."""
from decimal import Decimal, localcontext


def seed_panels(broker):
    state = broker.state
    records = [(i, broker.store.get('evidence', i)) for i in state['source_cache'].values()]
    prices = {e['data']['symbol']: (i, e['data']) for i, e in records if e.get('adapter') == 'alpaca_daily'}
    comparisons, gaps, lineage = [], [], []
    with localcontext() as ctx:
        ctx.prec = 40
        for item in state['mandate']['watchlist']:
            for benchmark in dict.fromkeys([item['benchmark'], item['sector_benchmark']]):
                left, right = prices.get(item['symbol']), prices.get(benchmark)
                if not left or not right:
                    gaps.append({'symbol': item['symbol'], 'benchmark': benchmark, 'reason': 'MISSING_PRICE_SERIES'})
                    continue
                comparable = all(left[1].get(k) == right[1].get(k) for k in ('price_date', 'feed', 'adjustment', 'return_basis'))
                if not comparable:
                    gaps.append({'symbol': item['symbol'], 'benchmark': benchmark, 'reason': 'INCOMPATIBLE_DATE_FEED_OR_BASIS'})
                    continue
                lineage += [left[0], right[0]]
                comparisons.append({'symbol': item['symbol'], 'benchmark': benchmark, 'price_date': left[1]['price_date'],
                    'status': 'FRESH' if left[1]['status'] == right[1]['status'] == 'FRESH' else 'STALE',
                    'input_evidence_ids': [left[0], right[0]],
                    'excess_price_return_percentage_points': {str(h): str(Decimal(str(left[1][f'return{h}_pct'])) - Decimal(str(right[1][f'return{h}_pct']))) for h in (5, 21, 63)}})
    selected = {i['symbol'] for i in state['mandate']['watchlist']}
    overlaps = []
    for identity, evidence in records:
        if evidence.get('adapter') != 'etf_holdings':
            continue
        data = evidence['data']
        overlaps.append({'fund': data['symbol'], 'as_of': data['as_of'], 'status': data['status'],
            'reported_weight_pct': data['reported_weight_pct'], 'input_evidence_id': identity,
            'selected_company_weights': {h['ticker']: h['weight_pct'] for h in data['holdings'] if h['ticker'] in selected},
            'qualification': 'Dated fund composition, not portfolio exposure; missing holdings are not zero exposure.'})
        lineage.append(identity)
    broker.record({'kind': 'comparison_panel', 'adapter': 'research_comparisons_v1',
        'data': {'relative_strength': comparisons, 'gaps': gaps, 'etf_lookthrough': overlaps},
        'input_evidence_ids': sorted(set(lineage)), 'formula': 'excess = instrument price return minus benchmark price return (percentage points)',
        'qualification': 'Inputs retain existing validated numeric precision; no causal attribution or predictive probability'})
    # Include explicit gaps for each declared context symbol without substituting a candidate.
    state['market_context']['missing_symbols'] = [s for s in state['mandate']['market_context_symbols'] if s not in state['market_context']['inputs']]
    broker.store.save(state)
