"""M2 scoped contracts and deterministic publication of unpublished research."""
from datetime import datetime
from decimal import Decimal

from spy_predictor_quant.market_archive import utc_now
from .contracts import M2_ROLES, validate

SPECIALISTS = tuple(r for r in M2_ROLES if r not in {"director", "challenger"})


def validate_mandate(mandate):
    symbols = [i['symbol'] for i in mandate['watchlist']]
    if len(symbols) != len(set(symbols)):
        raise ValueError('Duplicate instrument identity')
    allowed = set(symbols) | set(mandate['market_context_symbols'])
    allowed |= {i[k] for i in mandate['watchlist'] for k in ('benchmark', 'sector_benchmark')}
    sources = {s['source_id']: s for s in mandate['sources']}
    if not set(mandate['seed_source_ids']) <= sources.keys():
        raise ValueError('Unknown seed source')
    for source in sources.values():
        if not set(source['symbols']) <= allowed:
            raise ValueError('Source scope outside declared instruments/benchmarks')
        if source['adapter'] not in {'document', 'fred_csv'} and len(source['symbols']) != 1:
            raise ValueError('Numeric source requires one symbol')
        if bool(source['local_path']) != bool(source['sha256']):
            raise ValueError('Local source requires frozen SHA256')
        if source['local_path'] and (source['fixture_text'] is not None or source['captured_at'] is None):
            raise ValueError('Local source requires capture time and cannot be a fixture')
        if source['adapter'] == 'fred_csv' and (not source['series_id'] or not source['units']):
            raise ValueError('FRED source requires series identity and units')
        if source['adapter'] == 'alpaca_daily' and not source['feed']:
            raise ValueError('Market series requires feed identity')
        if source['adapter'] == 'alpaca_daily' and source['share_basis'] != 'split_adjusted':
            raise ValueError('Daily comparison requires captured, split-adjusted bars')
    if mandate['budgets']['task_attempts'] < 9 or mandate['budgets']['model_calls'] < 20:
        raise ValueError('M2 requires capacity for the full team and synthesis')


def validate_conditions(conditions, symbols, evidence_ids):
    for condition in conditions:
        if not set(condition['evidence_ids']) <= evidence_ids:
            raise ValueError('Unknown condition evidence')
        if condition['kind'] == 'human_review':
            if any(condition[k] is not None for k in ('operator', 'threshold_decimal', 'price_basis', 'expires_at')):
                raise ValueError('Human review cannot impersonate a machine price condition')
            if condition['symbol'] is not None and condition['symbol'] not in symbols:
                raise ValueError('Unknown review symbol')
        elif (condition['symbol'] not in symbols or condition['operator'] is None or
              condition['threshold_decimal'] is None or Decimal(condition['threshold_decimal']) <= 0 or
              condition['price_basis'] is None or condition['expires_at'] is None or not condition['evidence_ids']):
            raise ValueError('Completed-close condition requires symbol, comparator, positive price, basis, expiry and evidence')


def validate_scoped(state, task, result):
    symbols = {i['symbol'] for i in state['mandate']['watchlist']}
    visible = set(task['visible_evidence_ids'])
    for collection in ('claims', 'gaps', 'objections'):
        for item in result[collection]:
            if not set(item['symbols']) <= symbols:
                raise ValueError('Unknown finding scope')
    validate_conditions(result['review_conditions'], symbols, visible)
    rows = result['instruments']
    if len({i['symbol'] for i in rows}) != len(rows) or not {i['symbol'] for i in rows} <= symbols:
        raise ValueError('Duplicate or unknown instrument result')
    if task['stage'] in {'draft', 'final'} and {i['symbol'] for i in rows} != symbols:
        raise ValueError('Director must return exactly one thesis per watchlist instrument')
    own_claims = {c['claim_id']: c for c in result['claims']}
    for row in rows:
        if not set(row['claim_ids']) <= own_claims.keys():
            raise ValueError('Instrument must cite claims in this submission')
        if any(row['symbol'] not in own_claims[c]['symbols'] for c in row['claim_ids']):
            raise ValueError('Instrument claim has incompatible scope')
        if row['assessment'] != 'insufficient_evidence' and not row['claim_ids']:
            raise ValueError('Supported assessment requires linked claims')
        if any(g['critical'] and row['symbol'] in g['symbols'] for g in result['gaps']) and row['assessment'] != 'insufficient_evidence':
            raise ValueError('Critical gap blocks only the affected instrument')
        instrument = next(i for i in state['mandate']['watchlist'] if i['symbol'] == row['symbol'])
        if instrument['kind'] == 'etf' and not row['etf_lookthrough']:
            raise ValueError('ETF requires dated holdings/concentration/cost discussion or explicit missingness')
        validate_conditions(row['review_conditions'], {row['symbol']}, visible)
    for exposure in result['shared_exposures']:
        if not set(exposure['symbols']) <= symbols or not set(exposure['evidence_ids']) <= visible:
            raise ValueError('Unknown exposure scope or evidence')
    coverage = result['role_coverage']
    if len({r['role'] for r in coverage}) != len(coverage):
        raise ValueError('Duplicate role coverage')
    if task['stage'] == 'final':
        if {r['role'] for r in coverage} != set(SPECIALISTS):
            raise ValueError('Every specialist requires completion or an explicit omission reason')
        for row in coverage:
            completed = any(t['role'] == row['role'] and t['stage'] == 'research' and t['status'] == 'COMPLETE' for t in state['tasks'])
            if (row['status'] == 'completed') != completed:
                raise ValueError('Role coverage disagrees with controller task records')


def finish(controller, state):
    final_task = next(t for t in reversed(state['tasks']) if t['stage'] == 'final')
    final = final_task['result']
    validate_scoped(state, final_task, final)
    all_objections = [o for t in state['tasks'] if t['result'] for o in t['result']['objections']]
    objections = {o['objection_id']: o for o in all_objections}
    if len(objections) != len(all_objections):
        raise ValueError('Duplicate objection identity')
    dispositions = {d['objection_id']: d for d in final['dispositions']}
    if len(dispositions) != len(final['dispositions']) or dispositions.keys() != objections.keys():
        raise ValueError('Every objection requires exactly one disposition')
    effects = [q['question_id'] for q in final['question_effects']]
    if len(effects) != len(set(effects)) or set(effects) != {q['question_id'] for q in state['questions']}:
        raise ValueError('Every question requires exactly one effect')
    for row in final['instruments']:
        blocked = any(o['severity'] == 'critical' and row['symbol'] in o['symbols'] and
                      dispositions[key]['decision'] == 'unresolved' for key, o in objections.items())
        blocked |= any(s['critical'] and (not s['symbols'] or row['symbol'] in s['symbols']) and
                       s['source_id'] not in state['source_cache'] for s in state['mandate']['sources'])
        if blocked and row['assessment'] != 'insufficient_evidence':
            raise ValueError('Unresolved critical dependency blocks the affected instrument')
    now = utc_now()
    product = {'schema_version': 'investment-research-product-v3', 'run_id': state['run_id'],
        'status': 'DRAFT', 'publication_status': 'NOT_PUBLISHED', 'research_started_at': state['started_at'],
        'research_completed_at': now, 'published_at': None, 'observation_contract': None,
        'symbols': [i['symbol'] for i in state['mandate']['watchlist']], 'horizon_sessions': state['mandate']['horizon_sessions'],
        'evidence_ids': state['evidence_ids'], 'task_ids': [t['task_id'] for t in state['tasks']],
        'findings': final, 'market_context': state['market_context'], 'role_coverage': final['role_coverage'],
        'limitations': ['Unpublished research; publication refresh, conditions evaluation and outcome scoring belong to M3.',
            'Market context uses only the frozen benchmark list; watchlist diagnostics are not market breadth.',
            'Source dates and missingness remain explicit. Scenario valuations are assumptions, not price targets or calibrated forecasts.',
            'Catalog cost is estimated; provider output-token and cost ceilings may be enforced after a response.']}
    validate('product', product)
    identity = controller.store.put('products', product)
    state.update(status='DRAFT', completed_at=now, product_id=identity)
    controller.store.event(state, 'DRAFT_COMPLETED', product_id=identity)
    lines = ['# Five-symbol research' if len(product['symbols']) == 5 else '# Watchlist research', '',
             'NOT PUBLISHED · no observation issued', '', final['summary']]
    for row in final['instruments']:
        lines += ['', f"## {row['symbol']} — {row['assessment']}", '', row['thesis'], '',
                  'Counter-case: ' + row['counter_thesis'], '', 'Valuation: ' + row['valuation']]
        if row['etf_lookthrough']:
            lines += ['', 'ETF look-through: ' + row['etf_lookthrough']]
        lines += ['', 'Assumptions:'] + [f'- {a}' for a in row['assumptions']]
        lines += ['', 'Review conditions:'] + [f"- `{c['kind']}`: {c['description']}" for c in row['review_conditions']]
        lines += ['', 'Claims:']
        for claim in final['claims']:
            if claim['claim_id'] in row['claim_ids']:
                refs = ', '.join(f'[{i[:12]}](evidence/{i}.json)' for i in claim['evidence_ids'])
                lines += [f"- {claim['classification']}: {claim['text']} ({refs or 'scenario/inference'})"]
    for title, rows in [('Shared exposures', [e['mechanism'] + ' — ' + e['qualification'] for e in final['shared_exposures']]),
                        ('Role coverage', [f"{r['role']}: {r['status']} — {r['reason']}" for r in final['role_coverage']]),
                        ('Evidence gaps', [f"{','.join(g['symbols'])}: {g['description']}" for g in final['gaps']]),
                        ('Question effects', [f"{q['question_id']} / {q['effect']}: {q['reason']}" for q in final['question_effects']]),
                        ('Challenge dispositions', [f"{d['objection_id']} / {d['decision']}: {d['reason']}" for d in final['dispositions']]),
                        ('Limitations', product['limitations'])]:
        lines += ['', '## ' + title, ''] + ['- ' + row for row in rows]
    from .rendering import numerical_lines
    lines += numerical_lines(controller.store, state['evidence_ids'])
    (controller.store.root / 'draft.md').write_text('\n'.join(lines) + '\n')
