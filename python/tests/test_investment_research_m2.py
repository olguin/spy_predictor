"""M2 five-instrument engineering cases; synthetic findings are not live acceptance."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest
from jsonschema import ValidationError

from spy_predictor_quant.investment_research.broker import Broker, Excerpt
from spy_predictor_quant.investment_research.contracts import ROOT, validate
from spy_predictor_quant.investment_research.controller import Controller
from spy_predictor_quant.investment_research.multi_instrument import validate_scoped
from spy_predictor_quant.investment_research.panels import seed_panels
from test_investment_research import findings, response

SYMBOLS = ['ANET', 'QQQ', 'MU', 'META', 'NVDA']
ROLES = ['company', 'macro', 'technical', 'geopolitics', 'commodities']


def source(identity, symbols, *, text='Synthetic primary evidence', adapter='document', critical=False):
    return {'source_id': identity, 'symbols': symbols, 'title': identity, 'publisher': 'SYNTHETIC TEST',
        'url': 'https://example.com/' + identity, 'fixture_text': text, 'kind': 'company',
        'published_at': None, 'available_at': None, 'critical': critical, 'adapter': adapter,
        'local_path': None, 'sha256': None, 'captured_at': None, 'share_basis': 'not_applicable',
        'feed': None, 'series_id': None, 'units': None, 'data_end': None}


def mandate():
    m = json.loads((ROOT / 'config/investment-research-m1-live-v4.json').read_text())
    m.update(schema_version='investment-research-mandate-v3', mode='fixture',
        watchlist=[{'symbol': s, 'kind': 'etf' if s == 'QQQ' else 'company', 'benchmark': 'SPY', 'sector_benchmark': 'XLK'} for s in SYMBOLS],
        market_context_symbols=['SPY', 'IWM'], sources=[source(s, [s], text=None if s == 'MU' else f'{s} synthetic business evidence', critical=s == 'MU') for s in SYMBOLS])
    m['sources'] += [source('optional-policy', [], text=None)]
    m['seed_source_ids'] = [s['source_id'] for s in m['sources']]
    m['network']['enabled'] = False
    return m


def condition(symbol=None):
    return {'kind': 'human_review', 'description': 'Review issuer assumptions and exposure', 'symbol': symbol,
        'operator': None, 'threshold_decimal': None, 'price_basis': None, 'expires_at': None, 'evidence_ids': []}


def result(task_id, evidence_ids=()):
    r = findings(task_id)
    r.update(assessment='watch', claims=[], gaps=[], review_conditions=[condition()], instruments=[], role_coverage=[], shared_exposures=[])
    return r


class FiveSymbolWorker:
    def __init__(self):
        self.requests = []

    def __call__(self, request, runtime, timeout):
        self.requests.append(deepcopy(request))
        c = request['context']; t = c['task']; stage = t['stage']; role = t['role']
        tools = [h['action']['tool'] for h in c['history']]
        if stage == 'planning':
            asked = [h['action']['arguments']['recipient'] for h in c['history'] if h['action']['tool'] == 'ask_specialist']
            for specialist in ROLES[:-1]:
                if specialist not in asked:
                    return response('ask_specialist', {'recipient': specialist, 'symbols': SYMBOLS,
                        'question': f'Assess {specialist} material differences', 'decision_impact': 'Could change scoped assessment', 'evidence_ids': []})
        if stage == 'research' and role == 'company' and 'calculate' not in tools:
            return response('calculate', {'operation': 'scenario_price', 'left': '2.50', 'right': '30',
                'units': 'USD/share', 'assumptions': 'Synthetic earnings/share and P/E scenario, not observed expectations', 'evidence_ids': []})
        if stage == 'research' and role == 'company' and 'ask_specialist' not in tools:
            return response('ask_specialist', {'recipient': 'macro', 'symbols': ['NVDA'],
                'question': 'Could discount rates offset NVDA growth?', 'decision_impact': 'Could change the conditional case', 'evidence_ids': []})
        if stage == 'triage':
            q = next((q for q in c['questions'] if q['status'] == 'PROPOSED'), None)
            if q:
                answer = next(p['task_id'] for p in c['prior_findings'] if p['role'] == 'macro')
                return response('route_question', {'question_id': q['question_id'], 'decision': 'approve', 'reason': 'Completed macro research answers this scope', 'answer_task_id': answer})
        r = result(t['task_id'])
        if stage == 'review':
            r['objections'] = [{'objection_id': t['task_id'] + '-mu', 'claim_ids': [], 'symbols': ['MU'],
                                'severity': 'critical', 'description': 'MU source is missing'}]
        if stage in {'draft', 'final'}:
            for index, symbol in enumerate(SYMBOLS):
                e = next((i for i, value in c['evidence'].items() if value.get('symbols') == [symbol]), None)
                claim_ids = []
                if e:
                    claim_id = t['task_id'] + '-' + symbol
                    r['claims'].append({'claim_id': claim_id, 'symbols': [symbol], 'classification': 'fact', 'text': symbol + ' synthetic primary evidence', 'evidence_ids': [e]})
                    claim_ids.append(claim_id)
                assessment = 'insufficient_evidence' if symbol == 'MU' else 'conditional_opportunity' if symbol == 'NVDA' else 'watch'
                r['instruments'].append({'symbol': symbol, 'assessment': assessment,
                    'thesis': symbol + ' differentiated synthetic thesis', 'counter_thesis': symbol + ' concentration counter-case',
                    'assumptions': [symbol + ' growth scenario uncertain'], 'claim_ids': claim_ids,
                    'valuation': 'Named scenario assumptions require comparison with qualified current prices',
                    'etf_lookthrough': 'Synthetic holdings concentration and costs unavailable' if symbol == 'QQQ' else None,
                    'review_conditions': [condition(symbol)]})
            r['gaps'] = [{'symbols': ['MU'], 'critical': True, 'description': 'MU source missing'},
                         {'symbols': SYMBOLS, 'critical': False, 'description': 'Optional policy source unavailable'}]
            r['shared_exposures'] = [{'symbols': ['ANET', 'NVDA'], 'mechanism': 'Synthetic shared demand scenario', 'evidence_ids': [], 'qualification': 'Assumed, no measured portfolio weights'}]
        if stage == 'final':
            r['instruments'] = {row['symbol']: {k: v for k, v in row.items() if k != 'symbol'} for row in r['instruments']}
            r['role_coverage'] = [{'role': role, 'status': 'omitted' if role == 'commodities' else 'completed',
                'reason': 'No material commodity channel in this fixture' if role == 'commodities' else 'Grouped task completed'} for role in ROLES]
            r['question_effects'] = {q['question_id']: {'effect': 'unchanged', 'reason': 'Scoped answer retained'} for q in c['questions']}
            r['dispositions'] = {o['objection_id']: {'decision': 'unresolved', 'reason': 'MU remains insufficient evidence'} for o in c['required_objection_dispositions']}
        if stage not in {'draft', 'final'}:
            del r['instruments']; del r['role_coverage']
        if role != 'challenger':
            del r['objections']
        return response('submit_findings', r)


def test_five_symbol_cooperation_keeps_optional_gaps_scoped_and_exact_numbers(tmp_path):
    worker = FiveSymbolWorker(); controller = Controller(tmp_path, worker)
    controller.create(mandate()); state = controller.run()
    assert state['status'] == 'DRAFT', state.get('stop_reason')
    product = controller.store.get('products', state['product_id'])
    assert product['symbols'] == SYMBOLS and product['published_at'] is None
    assert {r['assessment'] for r in product['findings']['instruments']} == {'watch', 'conditional_opportunity', 'insufficient_evidence'}
    assert len(product['role_coverage']) == 5 and product['role_coverage'][-1]['status'] == 'omitted'
    assert state['usage']['model_calls'] <= 40 and state['usage']['task_attempts'] <= 16
    assert len(state['questions']) == 5 and state['questions'][-1]['answer_reused']
    assert '75.00' in (tmp_path / 'draft.md').read_text()
    for r in worker.requests:
        if r['context']['task']['stage'] == 'independent':
            assert r['context']['prior_findings'] == []
    assert all(t['created_at'] <= t['started_at'] <= t['completed_at'] for t in state['tasks'])
    assert len(worker.requests) == controller.run()['usage']['model_calls']


def test_scoped_claims_conditions_and_coverage_fail_closed(tmp_path):
    controller = Controller(tmp_path); state = controller.create(mandate())
    task = state['tasks'][0]; task['visible_evidence_ids'] = []
    r = result('t')
    r['gaps'] = [{'symbols': ['BOGUS'], 'critical': False, 'description': 'Unknown'}]
    with pytest.raises(ValueError, match='scope'): validate_scoped(state, task, r)
    r['gaps'] = []
    r['review_conditions'] = [{**condition('NVDA'), 'kind': 'completed_close'}]
    with pytest.raises(ValueError, match='requires'): validate_scoped(state, task, r)
    r['review_conditions'] = [condition()]; r['review_conditions'][0]['kind'] = 'latest_close'
    with pytest.raises(ValidationError): validate('findings', r, m2=True)


def test_local_capture_rejects_changed_hash_and_non_dataset_paths(tmp_path):
    m = mandate(); m['mode'] = 'live'
    source_row = m['sources'][0]
    source_row.update(local_path='datasets/workbench/manual-sources/qqq-profile-20260911.json', sha256='0' * 64,
                      captured_at='2026-09-11T22:00:00+00:00', fixture_text=None)
    controller = Controller(tmp_path); state = controller.create(m)
    with pytest.raises(ValueError, match='integrity'): Broker(controller.store, state).fetch(source_row)
    source_row['local_path'] = 'config/investment-research-m1-live-v4.json'
    with pytest.raises(ValueError, match='dataset'): Broker(controller.store, state).fetch(source_row)


def test_sec_hidden_inline_xbrl_is_not_visible_prose():
    parser = Excerpt(); parser.feed('<html><ix:header><ix:hidden><div>secret taxonomy</div></ix:hidden></ix:header><div style="display: none">hidden facts</div><p>Visible revenue <ix:nonFraction>100</ix:nonFraction></p><br/>after</html>')
    assert parser.parts == ['Visible revenue', '100', 'after']


def test_fixed_context_and_comparisons_do_not_follow_watchlist(tmp_path):
    controller = Controller(tmp_path); state = controller.create(mandate()); broker = Broker(controller.store, state)
    for symbol, value in [('SPY', 10.25), ('IWM', 7.0), ('NVDA', 15.75)]:
        data = {'symbol': symbol, 'price_date': '2026-09-18', 'status': 'FRESH', 'feed': 'sip', 'adjustment': 'split_adjusted',
                'return_basis': 'price_return', **{f'return{h}_pct': value for h in (5, 21, 63)}}
        record = broker.record({'kind': 'source', 'adapter': 'alpaca_daily', 'data': data})
        state['source_cache'][symbol] = record['evidence_id']
        if symbol in state['market_context']['symbols']: state['market_context']['inputs'][symbol] = {'evidence_id': record['evidence_id'], 'data': data}
    before = deepcopy(state['market_context']['inputs']); seed_panels(broker)
    panel = broker.store.get('evidence', state['evidence_ids'][-1])['data']
    comparison = next(r for r in panel['relative_strength'] if r['symbol'] == 'NVDA')
    assert comparison['excess_price_return_percentage_points']['21'] == '5.50'
    state['mandate']['watchlist'] = state['mandate']['watchlist'][:1]
    seed_panels(broker)
    assert state['market_context']['inputs'] == before
    assert set(state['market_context']['inputs']) == {'SPY', 'IWM'}


def test_valuation_sensitivity_calculation_references_preserve_decimal(tmp_path):
    controller = Controller(tmp_path); state = controller.create(mandate()); broker = Broker(controller.store, state)
    values = []
    for multiple in ('20', '30', '40'):
        r = broker.call('calculate', {'operation': 'scenario_price', 'left': '2.50', 'right': multiple,
            'units': 'USD/share', 'assumptions': 'Synthetic EPS x assumed multiple', 'evidence_ids': []})
        values.append(r['result_decimal'])
    assert values == ['50.00', '75.00', '100.00']
    growth = broker.call('calculate', {'operation': 'percentage_change', 'left': r['evidence_id'] + '#/result_decimal', 'right': '80',
        'units': 'percent', 'assumptions': 'Compare scenario with assumed baseline', 'evidence_ids': [r['evidence_id']]})
    assert growth['result_decimal'] == '25.00'


def test_sec_facts_use_matching_issuer_submissions(tmp_path, monkeypatch):
    from spy_predictor_quant.investment_research import broker as module
    m = mandate(); m['sources'] = []
    for symbol, cik in [('ANET', '0001596532'), ('MU', '0000723125')]:
        for kind, url in [('submissions', f'https://data.sec.gov/submissions/CIK{cik}.json'),
                          ('facts', f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json')]:
            row = source(kind + '-' + symbol, [symbol], text='{}'); row['url'] = url; m['sources'].append(row)
    m['seed_source_ids'] = [s['source_id'] for s in m['sources']]
    def normalize(raw, src, symbol, submissions):
        if src['source_id'].startswith('facts'):
            assert submissions == {'symbol': symbol}
        return {'symbol': symbol}
    monkeypatch.setattr(module, 'normalized_data', normalize)
    monkeypatch.setattr(module, 'discovered_documents', lambda *a: [])
    c = Controller(tmp_path); state = c.create(m); b = Broker(c.store, state)
    for src in m['sources']:
        e = b.call('read_source', {'source_id': src['source_id']})
        assert e['status'] == 'OK' and e['data']['symbol'] == src['symbols'][0]


def test_market_adapter_preserves_capture_end_and_symbol(tmp_path, monkeypatch):
    from spy_predictor_quant.investment_research.sources import normalized_data
    from spy_predictor_quant import meta_analysis
    src = source('price-NVDA', ['NVDA'], adapter='alpaca_daily')
    src.update(captured_at='2026-09-18T20:10:00+00:00', data_end='2026-09-18T19:50:00+00:00', feed='sip', share_basis='split_adjusted')
    seen = []
    def metrics(payload, metadata, cutoff):
        seen.append(metadata); return {'status': 'STALE'}
    monkeypatch.setattr(meta_analysis, 'daily_metrics', metrics)
    assert normalized_data(b'{"symbol":"NVDA","bars":[]}', src, 'NVDA')['status'] == 'STALE'
    assert seen[0]['data_end'] == '2026-09-18T19:50:00+00:00'
    with pytest.raises(ValueError, match='symbol mismatch'):
        normalized_data(b'{"symbol":"MU","bars":[]}', src, 'NVDA')


def test_final_instrument_identity_map_rejects_missing_symbol(tmp_path):
    from spy_predictor_quant.investment_research.result_transport import tool_schemas, restore_action
    c = Controller(tmp_path); state = c.create(mandate())
    task = c.add_task(state, 'director', 'final', 'Final'); base = json.loads((ROOT / 'prompts/investment-research/v2/tools.json').read_text())
    schemas = tool_schemas(base, task, state, 1)
    assert set(schemas['submit_findings']['properties']['instruments']['required']) == set(SYMBOLS)
    r = result('final'); r.update(instruments={}, dispositions={}, question_effects={})
    with pytest.raises(ValidationError): restore_action({'tool': 'submit_findings', 'arguments': r}, schemas, 'final')


def test_context_projection_keeps_values_and_original_numeric_pointers():
    from spy_predictor_quant.investment_research.context import compact
    from spy_predictor_quant.investment_research.sources import evidence_number
    e = {'kind': 'source', 'adapter': 'etf_holdings', 'data': {'holdings': [
        {'ticker': 'NVDA', 'weight_pct': 8.45, 'name': 'Nvidia', 'sector': None},
        {'ticker': 'MU', 'weight_pct': 4.85, 'name': 'Micron', 'sector': None}]}, 'excerpt': 'duplicate serialized data'}
    projected = compact(e)
    assert 'excerpt' not in projected and 'context_projection' in projected
    assert evidence_number(e, '/data/holdings/1/weight_pct') == evidence_number(projected, '/data/holdings/1/weight_pct') == '4.85'
    assert 'data' not in compact(e, catalog_only=True)
    assert 'name' in e['data']['holdings'][0]  # source artifact is not mutated


def test_optional_followup_preserves_final_input_budget_and_marks_question_unanswered(tmp_path):
    c = Controller(tmp_path, lambda *a: pytest.fail('Reserved capacity must prevent a provider call'))
    state = c.create(mandate())
    q = {'question_id': 'question-1', 'status': 'ACCEPTED'}; state['questions'].append(q)
    task = c.add_task(state, 'company', 'research', 'Optional follow-up', round_number=1, question_id=q['question_id'])
    state['usage']['input_tokens'] = state['limits']['input_tokens'] - state['reservations']['input_tokens']
    c.execute_task(state, task)
    assert task['status'] == 'OMITTED_BUDGET' and q['status'] == 'UNANSWERED'
    assert state['usage']['model_calls'] == 0


def test_specialist_wire_is_scoped_findings_without_premature_director_assessments(tmp_path):
    from spy_predictor_quant.investment_research.result_transport import tool_schemas, restore_action
    c = Controller(tmp_path); state = c.create(mandate()); task = c.add_task(state, 'company', 'research', 'Evidence')
    base = json.loads((ROOT / 'prompts/investment-research/v2.3/tools.json').read_text())
    schemas = tool_schemas(base, task, state, 1)
    assert 'instruments' not in schemas['submit_findings']['properties']
    r = result('company'); del r['instruments']; del r['role_coverage']; del r['objections']
    restored = restore_action({'tool': 'submit_findings', 'arguments': r}, schemas, 'research')
    assert restored['arguments']['instruments'] == []
    assert restored['arguments']['claims'] == r['claims']
    assert restored['arguments']['assessment'] == r['assessment']
    r['instruments'] = []
    with pytest.raises(ValidationError): restore_action({'tool': 'submit_findings', 'arguments': r}, schemas, 'research')


def test_director_cannot_create_challenger_objections_on_wire(tmp_path):
    from spy_predictor_quant.investment_research.result_transport import tool_schemas, restore_action
    c = Controller(tmp_path); state = c.create(mandate())
    task = c.add_task(state, 'director', 'draft', 'Synthesize')
    base = json.loads((ROOT / 'prompts/investment-research/v2.5/tools.json').read_text())
    schemas = tool_schemas(base, task, state, 1)
    assert 'objections' not in schemas['submit_findings']['properties']
    r = result(task['task_id']); del r['objections']
    restored = restore_action({'tool': 'submit_findings', 'arguments': r}, schemas, 'draft')
    assert restored['arguments']['objections'] == []
    assert restored['arguments']['summary'] == r['summary']
    r['objections'] = []
    with pytest.raises(ValidationError):
        restore_action({'tool': 'submit_findings', 'arguments': r}, schemas, 'draft')


def test_saved_task_graph_never_contains_an_uncommitted_question(tmp_path, monkeypatch):
    from spy_predictor_quant.investment_research.store import Store
    original = Store.save
    checkpoints = []
    def checked_save(store, state):
        questions = {q['question_id']: q for q in state['questions']}
        for task in state['tasks']:
            if task['question_id']:
                question = questions[task['question_id']]
                assert question['answer_task_id'] == task['task_id']
                assert question['symbols'] == task['symbols']
        checkpoints.append(state['status'])
        original(store, state)
    monkeypatch.setattr(Store, 'save', checked_save)
    c = Controller(tmp_path, FiveSymbolWorker()); state = c.create(mandate())
    assert len(c.store.load()['tasks']) == 2
    assert c.run()['status'] == 'DRAFT'
    assert checkpoints


def test_short_evidence_transport_constrains_references_and_preserves_prose():
    from spy_predictor_quant.investment_research.evidence_transport import prepare, restore
    from spy_predictor_quant.investment_research.result_transport import restore_action
    identity = 'a' * 64
    state = {'evidence_ids': [identity]}; task = {'visible_evidence_ids': [identity]}
    request = {'context': {'evidence': {identity: {'kind': 'calculation', 'result_decimal': '175.00'}},
        'history': [{'action': {'arguments': {'left': identity + '#/result_decimal'}}, 'result': {'evidence_id': identity}}]},
        'tool_schemas': {'inspect_evidence': {'type': 'object', 'additionalProperties': False, 'required': ['evidence_id'],
            'properties': {'evidence_id': {'type': 'string'}}}}}
    prepare(request, state, task)
    assert request['context']['evidence']['e1']['result_decimal'] == '175.00'
    assert request['context']['history'][0]['action']['arguments']['left'] == 'e1#/result_decimal'
    assert request['tool_schemas']['inspect_evidence']['properties']['evidence_id']['enum'] == ['e1']
    with pytest.raises(ValidationError):
        restore_action({'tool': 'inspect_evidence', 'arguments': {'evidence_id': 'sec-facts-NVDA'}}, request['tool_schemas'], 'research')
    action = {'tool': 'calculate', 'arguments': {'evidence_ids': ['e1'], 'left': 'e1#/result_decimal', 'assumptions': 'e1'}}
    restored = restore(action, request)
    assert restored['arguments']['evidence_ids'] == [identity]
    assert restored['arguments']['left'] == identity + '#/result_decimal'
    assert restored['arguments']['assumptions'] == 'e1'  # never edit semantic prose
