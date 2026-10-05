"""Regression tests for the real pilot's lost evidence and missing analytical work."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from spy_predictor_quant.investment_research.broker import Broker
from spy_predictor_quant.investment_research.context import compact
from spy_predictor_quant.investment_research.controller import Controller
from spy_predictor_quant.investment_research.delivery import coverage, require_coverage
from spy_predictor_quant.investment_research.earnings import earnings_periods
from spy_predictor_quant.investment_research.publication import publish
from spy_predictor_quant.investment_research.rendering import numerical_lines
from test_investment_research import response
from test_investment_research_m2 import FiveSymbolWorker, result, source
from test_investment_research_m3 import m3_mandate


def eps_payload():
    base = {'accn': 'annual', 'form': '10-K', 'filed': '2026-02-25', 'start': '2025-01-27', 'end': '2026-01-25', 'val': 4.9}
    rows = [base, base | {'accn': 'quarter', 'form': '10-Q', 'filed': '2026-08-26', 'start': '2026-01-26', 'end': '2026-07-26', 'val': 4.85}]
    return {'cik': 1, 'facts': {'us-gaap': {'EarningsPerShareDiluted': {'units': {'USD/shares': rows}}}}}


def test_annual_and_interim_survive_latest_quarter_and_context_projection():
    payload = eps_payload()
    filings = {'cik': '0000000001', 'periodic': [{'accessionNumber': x} for x in ('annual', 'quarter')]}
    periods = earnings_periods(payload, filings, datetime(2026, 9, 21, tzinfo=timezone.utc))
    assert periods['annual'][0]['value'] == 4.9
    assert periods['interim'][0]['value'] == 4.85
    assert periods['annual'][0]['share_basis'] == 'diluted_as_reported_in_accession'
    e = compact({'adapter': 'sec_companyfacts', 'data': {'earnings_periods': periods}})
    assert e['data']['earnings_periods'] == periods
    rows = payload['facts']['us-gaap']['EarningsPerShareDiluted']['units']['USD/shares']
    rows += [rows[0] | {'accn': 'unadmitted', 'val': 999}, rows[0] | {'filed': '2026-12-01', 'val': 888}, rows[0] | {'val': True}]
    assert earnings_periods(payload, filings, datetime(2026, 9, 21, tzinfo=timezone.utc)) == periods
    with pytest.raises(ValueError, match='issuer mismatch'):
        earnings_periods(payload | {'cik': 2}, filings, datetime.now(timezone.utc))


def ready_controller(path, worker=None, *, dimensional=False):
    m = m3_mandate(); m['schema_version'] = 'investment-research-mandate-v6' if dimensional else 'investment-research-mandate-v5'
    if dimensional:
        for source in m['sources']:
            source['supports_dimensions'] = ['market_behavior', 'valuation'] if source['adapter'] == 'alpaca_daily' else ['policy_exposure']
        m['source_requirements'] = [{'requirement_id': 'NVDA-annual', 'symbols': ['NVDA'], 'dimensions': ['valuation'],
            'source_ids': ['NVDA'], 'check': 'annual_eps', 'query': None, 'maximum_age_days': 450, 'required_for_run': True}]
    c = Controller(path, worker or FiveSymbolWorker()); s = c.create(m)
    broker = Broker(c.store, s)
    for instrument in m['watchlist']:
        symbol = instrument['symbol']
        price = broker.record({'kind': 'source', 'source_id': 'price-'+symbol, 'adapter': 'alpaca_daily', 'symbols': [symbol],
            'data': {'symbol': symbol, 'status': 'FRESH', 'latest_close': 100, 'price_date': '2026-09-18', 'adjustment': 'split_adjusted',
                     'feed': 'synthetic', **{k: 0 for k in ('sma20', 'sma50', 'sma200', 'rsi14_simple', 'return5_pct', 'return21_pct', 'return63_pct', 'realized_vol63_pct')}}})
        if instrument['kind'] == 'company':
            facts = broker.record({'kind': 'source', 'source_id': symbol, 'adapter': 'sec_companyfacts', 'symbols': [symbol],
                'data': {'earnings_periods': {'annual': [{'value': 4.0, 'unit': 'USD/shares', 'filed': '2026-02-25', 'start': '2025-01-01', 'end': '2025-12-31'}]}}})
            if dimensional:
                s['source_cache'][symbol] = facts['evidence_id']
    s['seed_complete'] = True
    c.store.save(s)
    return c, s


def grid_args(evidence, symbol='NVDA'):
    ids = [i for i, e in evidence.items() if e.get('symbols') == [symbol]]
    price = next(i for i in ids if evidence[i].get('adapter') == 'alpaca_daily')
    return {'symbol': symbol, 'price_evidence_id': price, 'evidence_ids': ids,
        'earnings_period_start': '2026-01-01', 'earnings_period_end': '2026-12-31',
        'accounting_basis': 'US_GAAP', 'share_basis': 'split_adjusted',
        'assumptions': 'Synthetic fixture only; assume unchanged share basis, varied annual earnings and valuation at the research horizon.',
        'cases': [{'case': name, 'earnings_per_share': eps, 'pe_multiple': '20', 'rationale': 'Synthetic margin/growth sensitivity, not consensus.'}
                  for name, eps in [('bear', '3'), ('base', '5'), ('bull', '7')]]}


def test_batch_math_lineage_and_wrong_company_or_partial_period_refused(tmp_path):
    c, state = ready_controller(tmp_path)
    evidence = {i: c.store.get('evidence', i) for i in state['evidence_ids']}
    args = grid_args(evidence)
    b = Broker(c.store, state)
    grid = b.call('calculate_scenarios', args)
    assert [r['scenario_price_decimal'] for r in grid['cases']] == ['60', '100', '140']
    assert [r['change_from_close_pct_decimal'] for r in grid['cases']] == ['-40.0', '0', '40.0']
    assert grid['input_evidence_ids'] == args['evidence_ids']
    assert state['usage']['tool_calls'] == 1
    for replacement, match in [({'symbol': 'QQQ'}, 'registered company'),
            ({'symbol': 'MU'}, 'annual earnings anchor'),
            ({'earnings_period_end': '2026-06-30'}, 'annual period')]:
        with pytest.raises(ValueError, match=match):
            b.call('calculate_scenarios', args | replacement)
    bad = deepcopy(args); bad['cases'][0]['earnings_per_share'] = 'NaN'
    with pytest.raises(ValueError, match='finite and positive'):
        b.call('calculate_scenarios', bad)
    lines = '\n'.join(numerical_lines(c.store, [grid['evidence_id']]))
    assert '| bear | 3 | 20 | 60 | -40.0 |' in lines
    assert 'conditional valuation' not in '\n'.join(numerical_lines(c.store, [grid['evidence_id']], withdrawn_symbols=['NVDA']))


def test_archived_filing_section_beyond_16000_and_contents_match(tmp_path):
    m = m3_mandate()
    src = source('long-filing', ['NVDA'], text='<main>Geographic revenue contents\n' + 'Opening material. '*1500 + '\nGeographic revenue actual disclosure 42%</main>')
    m['sources'].append(src)
    c = Controller(tmp_path); state = c.create(m); broker = Broker(c.store, state)
    original = broker.call('read_source', {'source_id': 'long-filing'})
    assert 'actual disclosure' not in original['excerpt']
    requests = state['usage']['source_requests']
    section = broker.call('inspect_evidence', {'evidence_id': original['evidence_id'], 'query': 'Geographic revenue', 'occurrence': 1})
    assert 'actual disclosure 42%' in section['excerpt']
    assert section['parent_evidence_id'] == original['evidence_id']
    assert section['content_sha256'] == original['content_sha256'] and section['matches'] == 2
    assert state['usage']['source_requests'] == requests
    assert broker.call('inspect_evidence', {'evidence_id': original['evidence_id'], 'query': 'nonexistent'})['status'] == 'GAP'


def test_missing_seed_inputs_stop_before_any_model_call(tmp_path):
    worker = FiveSymbolWorker(); c = Controller(tmp_path, worker)
    m = m3_mandate(); m['schema_version'] = 'investment-research-mandate-v5'; c.create(m)
    s = c.run()
    assert s['status'] == 'INCOMPLETE' and s['usage']['model_calls'] == 0
    assert s['delivery_check']['stage'] == 'seed' and not worker.requests
    assert any('annual_anchor_ids' in gap for gap in s['delivery_check']['missing'])


def test_company_omission_stops_before_macro_or_synthesis(tmp_path):
    worker = FiveSymbolWorker(); c, _ = ready_controller(tmp_path, worker)
    state = c.run()
    assert state['status'] == 'INCOMPLETE' and state['delivery_check']['stage'] == 'company_complete'
    assert not any(r['context']['task']['role'] == 'macro' for r in worker.requests)
    assert not any(r['context']['task']['stage'] == 'draft' for r in worker.requests)
    assert c.run()['usage'] == state['usage']


class DeliveryWorker(FiveSymbolWorker):
    def __call__(self, request, runtime, timeout):
        context = request['context']; task = context['task']
        if task['role'] == 'company' and task['stage'] == 'research':
            for company in context['mandate']['watchlist']:
                symbol = company['symbol']
                if company['kind'] == 'company' and not any(e.get('kind') == 'scenario_grid' and e['symbol'] == symbol for e in context['evidence'].values()):
                    return response('calculate_scenarios', grid_args(context['evidence'], symbol))
            findings = result(task['task_id']); del findings['instruments']; del findings['role_coverage']; del findings['objections']
            return response('submit_findings', findings)
        answer = super().__call__(request, runtime, timeout)
        if task['stage'] in {'draft', 'final'}:
            r = answer['action']['arguments']
            rows = r['instruments'].items() if isinstance(r['instruments'], dict) else [(r['symbol'], r) for r in r['instruments']]
            for symbol, row in rows:
                row['assessment'] = 'insufficient_evidence'  # Useful scenarios must not force directional eligibility.
                grid = next((i for i, e in context['evidence'].items() if e.get('kind') == 'scenario_grid' and e['symbol'] == symbol), None)
                if grid:
                    claim = {'claim_id': task['task_id']+'-scenario-'+symbol, 'symbols': [symbol], 'classification': 'scenario',
                             'text': 'Synthetic conditional sensitivity, not consensus.', 'evidence_ids': [grid]}
                    r['claims'].append(claim); row['claim_ids'].append(claim['claim_id'])
        return answer


def test_delivery_accepts_conditional_analysis_without_forcing_a_recommendation(tmp_path):
    c, _ = ready_controller(tmp_path/'run', DeliveryWorker())
    state = c.run()
    assert state['status'] == 'DRAFT', state.get('stop_reason')
    product = c.store.get('products', state['product_id'])
    assert all(r['assessment'] == 'insufficient_evidence' for r in product['findings']['instruments'])
    check = coverage(c.store, state, product['findings'])
    assert all(row['scenario_linked_in_report'] for row in check['companies'])
    assert state['delivery_check']['status'] == 'PASS'
    assert 'conditional valuation sensitivity' in (c.store.root/'draft.md').read_text()
    product['findings']['claims'] = [r for r in product['findings']['claims'] if r['classification'] != 'scenario']
    state['product_id'] = c.store.put('products', product); c.store.save(state)
    before = state['usage'].copy()
    with pytest.raises(ValueError, match='scenario not linked'):
        publish(c.store, tmp_path/'ledger')
    assert c.store.load()['usage'] == before
    assert not c.store.load().get('publication_refresh')


def test_refresh_withdrawal_hides_scenario_guidance_in_markdown_and_api(tmp_path):
    import uuid
    from spy_predictor_quant.investment_research.workspace import Workspace, QUESTION
    workspace = Workspace(tmp_path/'workspace', tmp_path/'ledger', launch=lambda *args: None)
    identity = str(uuid.uuid4()); workspace.start(identity, QUESTION)
    c, _ = ready_controller(workspace.directory(identity)/'run', DeliveryWorker())
    assert c.run()['status'] == 'DRAFT'
    assert len(workspace.report(identity)['scenario_grids']) == 4
    publication = publish(c.store, workspace.ledger)
    assert publication['refresh']['invalidation']['symbols']
    assert workspace.report(identity)['scenario_grids'] == []
    text = (workspace.ledger/'publications'/publication['publication_id']/'report.md').read_text()
    assert 'conditional valuation sensitivity' not in text


def test_reverse_expectations_and_residual_preserve_period_and_share_caveat(tmp_path):
    c, state = ready_controller(tmp_path)
    b = Broker(c.store, state)
    facts = b.record({'kind': 'source', 'adapter': 'sec_companyfacts', 'symbols': ['NVDA'],
        'data': {'earnings_periods': {'annual': [{'value': 4}], 'interim': [
            {'start': '2026-01-01', 'end': '2026-03-31', 'value': 1},
            {'start': '2026-01-01', 'end': '2026-06-30', 'value': 4},
            {'start': '2025-01-01', 'end': '2025-09-30', 'value': 99}]}}})
    evidence = {i: c.store.get('evidence', i) for i in state['evidence_ids']}
    args = grid_args(evidence)
    grid = b.call('calculate_scenarios', args)
    base = grid['cases'][1]
    assert base['break_even_pe_decimal'] == '20'
    assert base['break_even_eps_decimal'] == '5'
    assert base['constant_share_residual']['eps_decimal'] == '1'
    assert grid['cases'][0]['constant_share_residual']['eps_decimal'] == '-1'  # Must expose a loss implication, not clip it.
    assert 'not an exact annual EPS reconciliation' in base['constant_share_residual']['qualification']
    next_year = b.call('calculate_scenarios', args | {'earnings_period_start': '2027-01-01', 'earnings_period_end': '2027-12-31'})
    assert all('constant_share_residual' not in r for r in next_year['cases'])


def test_scenario_asymmetry_compares_absolute_loss_not_signed_downside(tmp_path):
    c, state = ready_controller(tmp_path)
    args = grid_args({i: c.store.get('evidence', i) for i in state['evidence_ids']})
    args['cases'][0]['earnings_per_share'] = '3.2'
    args['cases'][2]['earnings_per_share'] = '6.9'
    grid = Broker(c.store, state).call('calculate_scenarios', args)
    assert grid['asymmetry']['bear_loss_magnitude_pct_decimal'] == '36.00'
    assert grid['asymmetry']['bull_gain_pct_decimal'] == '38.00'
    assert grid['asymmetry']['bull_gain_minus_bear_loss_pp_decimal'] == '2.00'
    assert grid['asymmetry']['comparison'] == 'bull_gain_exceeds_bear_loss'


def test_disclosed_53_week_calendars_prevent_anniversary_date_guesses(tmp_path):
    from spy_predictor_quant.investment_research.fiscal_calendar import derive
    nvda = derive('Fiscal year 2027 is a 53-week year, and fiscal year 2026 was a 52-week year.',
                  {'annual': [{'end': '2026-01-25'}], 'interim': [{'start': '2026-01-26'}]})
    mu = derive('Fiscal year 2026 contains 53 weeks and fiscal year 2025 contains 52 weeks.',
                {'annual': [{'end': '2025-08-28'}], 'interim': [{'start': '2025-08-29'}]})
    assert nvda['end'] == '2027-01-31' and mu['end'] == '2026-09-03'
    assert derive('Fiscal year 2027 is a 53-week year.', {'annual': [{'end': '2026-01-25'}], 'interim': []}) is None
    assert derive('Fiscal year 2027 is a 53-week year. Fiscal year 2027 contains 52 weeks.',
                  {'annual': [{'end': '2026-01-25'}], 'interim': [{'start': '2026-01-26'}]}) is None
    c, state = ready_controller(tmp_path); b = Broker(c.store, state)
    calendar = b.record({'kind': 'fiscal_calendar', 'symbol': 'NVDA', **nvda})
    args = grid_args({i: c.store.get('evidence', i) for i in state['evidence_ids']})
    args.update(earnings_period_start='2026-01-26', earnings_period_end='2027-01-25')
    with pytest.raises(ValueError, match='disclosed fiscal calendar'):
        b.call('calculate_scenarios', args)
    args['earnings_period_end'] = '2027-01-31'
    assert calendar['evidence_id'] in b.call('calculate_scenarios', args)['input_evidence_ids']
