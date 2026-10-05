"""Readable projections of saved work. Never generates claims or changes research."""
from collections import Counter
import re

ROLES = ('director', 'company', 'macro', 'technical', 'geopolitics', 'commodities', 'challenger')
ROLE_NAMES = {'director': 'Overall assessment', 'company': 'Company & valuation',
              'macro': 'Economy & markets', 'technical': 'Price & market behavior',
              'geopolitics': 'Geopolitics & policy', 'commodities': 'Inputs & commodities',
              'challenger': 'Independent challenge'}


def agent_reports(store, state, *, publication=None):
    """Count recorded actions, distinguish cited evidence from merely visible evidence."""
    reports = []
    for role in ROLES:
        tasks = [t for t in state['tasks'] if t['role'] == role]
        accepted = [t for t in tasks if t.get('result') and t['status'] == 'COMPLETE']
        latest = accepted[-1] if accepted else None
        result = latest['result'] if latest else {}
        actions = Counter()
        inspected, calculated = set(), set()
        for task in tasks:
            for turn in task.get('history', []):
                outcome = turn.get('result') or {}
                if outcome.get('status') == 'REJECTED_VALIDATION':
                    continue
                tool = turn.get('action', {}).get('tool')
                if tool:
                    actions[tool] += 1
                identity = outcome.get('evidence_id')
                if identity and tool in {'read_source', 'inspect_evidence'}:
                    inspected.add(identity)
                if identity and tool and tool.startswith('calculate'):
                    calculated.add(identity)
        cited = sorted({i for claim in result.get('claims', []) for i in claim.get('evidence_ids', [])})
        attempts = [a for a in state.get('attempts', []) if a.get('task_id') in {t['task_id'] for t in tasks}]
        receipts = [store.get('responses', a['response_id']).get('receipt') for a in attempts if a.get('response_id')]
        cost_known = len(receipts) == len(attempts) and all(r and r.get('catalog_cost_usd') is not None for r in receipts)
        cost = sum((r or {}).get('catalog_cost_usd') or 0 for r in receipts)
        coverage = next((r for t in reversed(state['tasks']) for r in (t.get('result') or {}).get('role_coverage', []) if r['role'] == role), None)
        status = ('running' if any(t['status'] == 'RUNNING' for t in tasks) else
                  'pending' if any(t['status'] == 'PENDING' for t in tasks) else
                  'completed' if latest else 'incomplete' if tasks else
                  (coverage or {}).get('status', 'not_assigned'))
        # A failed follow-up must remain visible even when an earlier result exists.
        if latest and tasks[-1]['status'] not in {'COMPLETE', 'RUNNING', 'PENDING'}:
            status = 'partial'
        summary = result.get('summary') or (coverage or {}).get('reason') or 'No accepted conclusions recorded yet.'
        narrative = result.get('agent_report') or {}
        brief = re.split(r'(?<=[.!?])\s+', summary.strip())[0]
        if len(brief) > 360:
            brief = brief[:357].rsplit(' ', 1)[0] + '…'
        sources = []
        for identity in cited:
            evidence = store.get('evidence', identity)
            data = evidence.get('data') or {}
            sources.append({'evidence_id': identity, 'title': evidence.get('title') or evidence.get('source_id') or evidence.get('kind'),
                            'observed_at': data.get('price_date') or data.get('as_of') or evidence.get('published_at'),
                            'retrieved_at': evidence.get('retrieved_at')})
        reports.append({'role': role, 'name': ROLE_NAMES[role], 'status': status,
                        'task_ids': [t['task_id'] for t in tasks], 'latest_task_id': latest['task_id'] if latest else None,
                        'stages': [t['stage'] for t in tasks], 'symbols': sorted({s for t in tasks for s in t['symbols']}),
                        'activity': dict(actions), 'inspected_evidence_count': len(inspected),
                        'calculation_count': len(calculated), 'visible_evidence_count': len(set(i for t in tasks for i in t.get('visible_evidence_ids', []))),
                        'model_calls': len(attempts), 'catalog_cost_usd': cost, 'cost_known': cost_known,
                        'main_conclusions': result.get('claims', []), 'summary': summary,
                        'short_summary': narrative.get('short_summary') or brief, 'narrative': narrative,
                        'instruments': result.get('instruments', []), 'gaps': result.get('gaps', []),
                        'counter_thesis': result.get('counter_thesis'), 'objections': result.get('objections', []),
                        'review_conditions': result.get('review_conditions', []), 'sources': sources,
                        'qualification': ('Saved agent work before publication refresh; consult the published assessment for withdrawn conclusions.'
                                          if publication else 'Accepted research findings; source dates and gaps limit the conclusion.')})
    return reports


def chart_data(store, state, *, withdrawn_symbols=()):
    """Small, lineage-linked chart payload. Do not mix incompatible price cutoffs."""
    from .technical_path import completed_bars
    evidence = [(i, store.get('evidence', i)) for i in state['evidence_ids']]
    charts = []
    panel = next(((i, e) for i, e in reversed(evidence) if e.get('kind') == 'comparison_panel'), None)
    if panel:
        identity, item = panel
        for symbol in [w['symbol'] for w in state['mandate']['watchlist'] if w['symbol'] not in withdrawn_symbols]:
            rows = [r for r in item['data']['relative_strength'] if r['symbol'] == symbol]
            if rows:
                charts.append({'kind': 'relative_returns', 'symbol': symbol, 'title': f'{symbol} vs benchmarks',
                               'as_of': rows[0]['price_date'], 'rows': rows, 'evidence_ids': [identity],
                               'qualification': 'Completed-session price returns, instrument minus benchmark in percentage points. Historical observations, not forecasts.'})
    prices = {e.get('data', {}).get('symbol'): (i, e) for i, e in evidence
              if e.get('adapter') == 'alpaca_daily' and e.get('data') and e.get('document_id')}
    for watch in state['mandate']['watchlist']:
        symbol = watch['symbol']
        if symbol in withdrawn_symbols:
            continue
        names = list(dict.fromkeys((symbol, watch['benchmark'], watch['sector_benchmark'])))
        if not all(name in prices for name in names):
            continue
        try:
            bars = {name: completed_bars(store, prices[name][1])[0][-64:] for name in names}
            dates = [[b['t'][:10] for b in rows] for rows in bars.values()]
            if len(dates[0]) != 64 or any(d != dates[0] for d in dates[1:]):
                continue
            charts.append({'kind': 'price_path', 'symbol': symbol, 'title': f'{symbol}: 63-session price path',
                           'as_of': dates[0][-1], 'dates': dates[0],
                           'series': [{'name': name, 'values': [float(b['c']) / float(rows[0]['c']) * 100 for b in rows]}
                                      for name, rows in bars.items()],
                           'evidence_ids': [prices[name][0] for name in names],
                           'qualification': 'Split-adjusted completed closes, first close = 100. Matched session dates; excludes unfinished bars. Price return, not total return or a forecast.'})
        except (ValueError, KeyError, TypeError, ZeroDivisionError):
            continue  # Missing/incompatible data means no chart, never imputed values.
    return charts
