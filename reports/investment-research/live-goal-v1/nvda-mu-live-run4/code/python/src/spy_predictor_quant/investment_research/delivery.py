"""Minimum analytical delivery checks, separate from recommendation eligibility.

These detect missing work, not truth or usefulness. A fully qualified conditional
analysis may pass with every directional assessment still insufficient_evidence.
"""


def enabled(state):
    return state['mandate'].get('schema_version') in {'investment-research-mandate-v5', 'investment-research-mandate-v6', 'investment-research-mandate-v7'}


def coverage(store, state, findings=None):
    evidence = {i: store.get('evidence', i) for i in state['evidence_ids']}
    rows = []
    for instrument in state['mandate']['watchlist']:
        symbol = instrument['symbol']
        if instrument['kind'] != 'company':
            continue
        annual = [i for i, e in evidence.items() if symbol in e.get('symbols', [])
                  and e.get('adapter') == 'sec_companyfacts'
                  and (e.get('data') or {}).get('earnings_periods', {}).get('annual')]
        prices = [i for i, e in evidence.items() if e.get('adapter') == 'alpaca_daily'
                  and (e.get('data') or {}).get('symbol') == symbol
                  and (e.get('data') or {}).get('latest_close', 0) > 0
                  and (e.get('data') or {}).get('status') == 'FRESH']
        grids = [i for i, e in evidence.items() if e.get('kind') == 'scenario_grid'
                 and e.get('symbol') == symbol]
        methods = [i for i, e in evidence.items() if e.get('kind') == 'three_method_valuation'
                   and e.get('symbol') == symbol and len(e.get('methods', [])) == 3]
        linked = None
        if findings is not None:
            row = next((r for r in findings['instruments'] if r['symbol'] == symbol), {})
            cited = {i for c in findings['claims'] if c['claim_id'] in row.get('claim_ids', [])
                     and symbol in c['symbols'] and c['classification'] == 'scenario' for i in c['evidence_ids']}
            linked = bool(set(grids) & cited)
        rows.append({'symbol': symbol, 'annual_anchor_ids': annual, 'price_ids': prices,
                     'scenario_grid_ids': grids, 'valuation_method_ids': methods,
                     'scenario_linked_in_report': linked})
    return {'version': 'research-delivery-v1', 'companies': rows,
            'qualification': 'Mechanical coverage only. Assumption suitability, sources, comparison and usefulness require review.'}


def require_coverage(store, state, stage, findings=None):
    if not enabled(state):
        return
    result = coverage(store, state, findings)
    missing = []
    for row in result['companies']:
        fields = ('annual_anchor_ids', 'price_ids') if stage == 'seed' else ('scenario_grid_ids',)
        objective = state['mandate']['objective'].lower()
        if stage != 'seed' and len(result['companies']) == 1 and all(term in objective for term in ('forward p/e', 'ev/revenue', 'dcf')):
            fields += ('valuation_method_ids',)
        for field in fields:
            if not row[field]:
                missing.append(f"{row['symbol']}: {field}")
        if findings is not None and not row['scenario_linked_in_report']:
            missing.append(f"{row['symbol']}: scenario not linked to report")
    result.update(stage=stage, status='BLOCKED' if missing else 'PASS', missing=missing)
    state['delivery_check'] = result
    store.event(state, 'DELIVERY_CHECK', **result)
    if missing:
        raise ValueError('Research delivery incomplete at ' + stage + ': ' + '; '.join(missing)
                         + '. Preserve partial findings; repair inputs or analytical work before a new run.')
