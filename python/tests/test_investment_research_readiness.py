"""Source usability and independent conclusion status; all worker outputs synthetic."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from spy_predictor_quant.investment_research.dimensions import DIMENSIONS, validate_dimensions
from spy_predictor_quant.investment_research.holdings import invesco_holdings
from spy_predictor_quant.investment_research.readiness import source_readiness
from spy_predictor_quant.investment_research.readiness_profile import HOLDINGS_URL
from spy_predictor_quant.investment_research.publication import invalidate, withdrawn_valuation_symbols
from test_investment_research_delivery import ready_controller, DeliveryWorker


def test_sponsor_holdings_preserve_dates_exclusions_and_no_renormalization():
    payload = {'cusip': 'QQQ', 'effectiveDate': '2026-09-19', 'effectiveBusinessDate': '2026-09-18',
        'totalNumberOfHoldings': 4, 'holdings': [
            {'ticker': 'NVDA', 'issuerName': 'Nvidia', 'securityTypeCode': 'COM', 'percentageOfTotalNetAssets': 99.5},
            {'ticker': None, 'issuerName': 'Future', 'securityTypeCode': 'IFUT', 'percentageOfTotalNetAssets': 1},
            {'ticker': None, 'issuerName': 'Contra future', 'securityTypeCode': 'SYN', 'percentageOfTotalNetAssets': -.5},
            {'ticker': None, 'issuerName': 'Pending dividends', 'securityTypeCode': 'CURR', 'percentageOfTotalNetAssets': None}]}
    parse = lambda p: invesco_holdings(json.dumps(p).encode(), {'url': HOLDINGS_URL}, 'QQQ', datetime(2026, 9, 21, tzinfo=timezone.utc))
    data = parse(payload)
    assert data['as_of'] == '2026-09-18' and data['reported_weight_pct'] == 99.5
    assert data['sponsor_reported_weight_pct'] == 100 and len(data['excluded_positions']) == 3
    assert data['unknown_weight_positions'] == 1 and data['holdings_count'] == 1
    for patch, match in [({'cusip': 'SPY'}, 'identity'), ({'totalNumberOfHoldings': 3}, 'Incomplete'),
                         ({'effectiveBusinessDate': '2026-10-01'}, 'dates')]:
        with pytest.raises(ValueError, match=match): parse(payload | patch)


def test_readiness_uses_observation_dates_not_refreshed_retrieval(tmp_path):
    c, state = ready_controller(tmp_path, dimensional=True)
    result = source_readiness(c.store, state, at=datetime(2026, 9, 21, tzinfo=timezone.utc))
    assert result['status'] == 'READY'
    state['mandate']['source_requirements'][0]['maximum_age_days'] = 30
    result = source_readiness(c.store, state, at=datetime(2026, 9, 21, tzinfo=timezone.utc))
    assert result['status'] == 'BLOCKED' and result['requirements'][0]['status'] == 'STALE'
    state['source_cache'].clear()
    assert source_readiness(c.store, state)['requirements'][0]['status'] == 'MISSING'


def test_filing_sections_survive_identical_refresh_but_not_changed_submissions(tmp_path):
    from spy_predictor_quant.investment_research.broker import Broker
    c, state = ready_controller(tmp_path, dimensional=True); broker = Broker(c.store, state)
    requirement = state['mandate']['source_requirements'][0]
    requirement.update(check='issuer_sections', query='geographic', required_for_run=False)
    original = broker.record({'source_id': 'NVDA', 'content_sha256': 'same', 'adapter': 'sec_submissions'})
    doc = broker.record({'parent_evidence_id': original['evidence_id'], 'adapter': 'document'})
    broker.record({'parent_evidence_id': doc['evidence_id'], 'adapter': 'document_section', 'symbols': ['NVDA'],
        'query': 'geographic', 'published_at': '2026-08-26T00:00:00+00:00', 'excerpt': 'substantive disclosure '*30})
    for digest, expected in [('same', 'PARTIAL'), ('changed', 'MISSING')]:
        refreshed = broker.record({'source_id': 'NVDA', 'content_sha256': digest, 'adapter': 'sec_submissions', 'refresh': True})
        state['source_cache']['NVDA'] = refreshed['evidence_id']
        actual = source_readiness(c.store, state, at=datetime(2026, 9, 21, tzinfo=timezone.utc))
        assert actual['requirements'][0]['status'] == expected
        assert actual['status'] == 'READY_WITH_GAPS'


def test_undated_optional_input_is_missing_without_blocking_other_work(tmp_path):
    from spy_predictor_quant.investment_research.broker import Broker
    c, state = ready_controller(tmp_path, dimensional=True)
    state['mandate']['source_requirements'][0].update(check='etf_valuation', required_for_run=False)
    metric = Broker(c.store, state).record({'source_id': 'NVDA', 'adapter': 'etf_profile', 'data': {'metrics': {'pe_ratio': 30}}})
    state['source_cache']['NVDA'] = metric['evidence_id']
    actual = source_readiness(c.store, state)
    assert actual['status'] == 'READY_WITH_GAPS' and actual['requirements'][0]['status'] == 'MISSING'


def scoped_result():
    claims = [{'claim_id': d, 'symbols': ['NVDA'], 'dimensions': [d], 'classification': 'inference', 'evidence_ids': []} for d in DIMENSIONS]
    statuses = {'business': 'supported', 'valuation': 'conditional', 'market_behavior': 'supported',
                'policy_exposure': 'insufficient_evidence', 'relative_preference': 'conditional'}
    dimensions = {d: {'status': statuses[d], 'conclusion': 'Synthetic scoped conclusion', 'qualification': 'Synthetic assumptions and limits',
                     'claim_ids': [d] if statuses[d] != 'insufficient_evidence' else [],
                     'depends_on': ['business', 'valuation', 'market_behavior'] if d == 'relative_preference' else []} for d in DIMENSIONS}
    row = {'symbol': 'NVDA', 'assessment': 'conditional_opportunity', 'claim_ids': list(DIMENSIONS), 'dimensions': dimensions}
    return {'claims': claims, 'gaps': [{'symbols': ['NVDA'], 'dimensions': ['policy_exposure'], 'critical': True}],
            'objections': [], 'dispositions': [], 'instruments': [row]}


def test_policy_gap_does_not_erase_unrelated_business_valuation_or_market(tmp_path):
    c, state = ready_controller(tmp_path, dimensional=True)
    value = scoped_result(); task = {'visible_evidence_ids': state['evidence_ids']}
    validate_dimensions(state, task, value)
    value['instruments'][0]['dimensions']['relative_preference']['depends_on'].append('policy_exposure')
    with pytest.raises(ValueError, match='blocks NVDA relative_preference'):
        validate_dimensions(state, task, value)
    value['instruments'][0]['dimensions']['relative_preference']['status'] = 'insufficient_evidence'
    with pytest.raises(ValueError, match='Directional assessment'):
        validate_dimensions(state, task, value)
    value['instruments'][0]['assessment'] = 'insufficient_evidence'
    validate_dimensions(state, task, value)


def test_source_limits_cross_dimension_citations_cycles_and_conditional_dependencies(tmp_path):
    c, state = ready_controller(tmp_path, dimensional=True); task = {'visible_evidence_ids': state['evidence_ids']}
    state['source_readiness'] = {'requirements': [{'symbols': ['NVDA'], 'dimensions': ['business'], 'status': 'MISSING'}]}
    with pytest.raises(ValueError, match='blocks NVDA business'):
        validate_dimensions(state, task, scoped_result())
    state.pop('source_readiness')
    value = scoped_result(); value['instruments'][0]['dimensions']['business']['claim_ids'] = ['valuation']
    with pytest.raises(ValueError, match='dimension scope'): validate_dimensions(state, task, value)
    value = scoped_result(); value['instruments'][0]['dimensions']['business']['depends_on'] = ['relative_preference']
    with pytest.raises(ValueError, match='acyclic'): validate_dimensions(state, task, value)
    value = scoped_result(); value['instruments'][0]['dimensions']['relative_preference']['status'] = 'supported'
    with pytest.raises(ValueError, match='Conditional dependencies'): validate_dimensions(state, task, value)


def test_unresolved_critical_objection_cannot_be_hidden_or_resolved_without_evidence(tmp_path):
    c, state = ready_controller(tmp_path, dimensional=True); task = {'visible_evidence_ids': state['evidence_ids']}
    objection = {'objection_id': 'critical-value', 'symbols': ['NVDA'], 'dimensions': ['valuation'], 'severity': 'critical'}
    state['tasks'].append({'result': {'claims': [], 'objections': [objection]}})
    value = scoped_result()
    with pytest.raises(ValueError, match='blocks NVDA valuation'): validate_dimensions(state, task, value)
    value['dispositions'] = [{'objection_id': 'critical-value', 'decision': 'changed', 'evidence_ids': []}]
    with pytest.raises(ValueError, match='requires cited evidence'): validate_dimensions(state, task, value)


def test_policy_refresh_only_withdraws_linked_dimensions_and_declared_dependents(tmp_path):
    c, state = ready_controller(tmp_path, dimensional=True)
    product = {'evidence_ids': [], 'findings': scoped_result()}
    affected = invalidate(c.store, product, set(), ['NVDA'], changed_dimensions={'NVDA': {'policy_exposure'}})
    assert affected['dimensions'] == {'NVDA': ['policy_exposure']}
    assert withdrawn_valuation_symbols({'invalidation': affected}) == []
    product['findings']['instruments'][0]['dimensions']['relative_preference']['depends_on'].append('policy_exposure')
    affected = invalidate(c.store, product, set(), ['NVDA'], changed_dimensions={'NVDA': {'policy_exposure'}})
    assert affected['dimensions'] == {'NVDA': ['policy_exposure', 'relative_preference']}


class DimensionWorker(DeliveryWorker):
    def __call__(self, request, runtime, timeout):
        answer = super().__call__(request, runtime, timeout)
        if answer['action']['tool'] != 'submit_findings': return answer
        r = answer['action']['arguments']; context = request['context']; task = context['task']
        for claim in r['claims']:
            claim['dimensions'] = ['valuation'] if claim['classification'] == 'scenario' else ['business']
        for gap in r['gaps']:
            gap.update(dimensions=['policy_exposure'], description='Synthetic policy exposure gap')
        for objection in r.get('objections', []):
            objection.update(dimensions=['policy_exposure'], description='Synthetic missing policy exposure')
        dispositions = r['dispositions'].values() if isinstance(r['dispositions'], dict) else r['dispositions']
        for decision in dispositions: decision['evidence_ids'] = []
        rows = r.get('instruments', {})
        rows = rows.items() if isinstance(rows, dict) else [(row['symbol'], row) for row in rows]
        for symbol, row in rows:
            price = next(i for i, e in context['evidence'].items() if e.get('adapter') == 'alpaca_daily' and e['data']['symbol'] == symbol)
            claim_id = task['task_id']+'-market-'+symbol
            r['claims'].append({'claim_id': claim_id, 'symbols': [symbol], 'dimensions': ['market_behavior'], 'classification': 'fact',
                'text': 'Synthetic close 100', 'evidence_ids': [price]})
            row['claim_ids'].append(claim_id)
            dimensions = {}
            for name in DIMENSIONS:
                refs = [c['claim_id'] for c in r['claims'] if c['claim_id'] in row['claim_ids'] and name in c['dimensions']]
                dimensions[name] = {'status': ('conditional' if name == 'valuation' else 'supported') if refs else 'insufficient_evidence',
                    'conclusion': symbol+' synthetic '+name, 'qualification': 'Synthetic test only; no recommendation.', 'claim_ids': refs,
                    'depends_on': ['business', 'valuation', 'market_behavior'] if name == 'relative_preference' else []}
            row['dimensions'] = dimensions
        return answer


def test_v6_controller_schema_transport_and_report_keep_distinct_statuses(tmp_path):
    c, _ = ready_controller(tmp_path, DimensionWorker(), dimensional=True)
    state = c.run()
    assert state['status'] == 'DRAFT', state.get('stop_reason')
    product = c.store.get('products', state['product_id'])
    assert product['schema_version'] == 'investment-research-product-v4'
    row = next(r for r in product['findings']['instruments'] if r['symbol'] == 'NVDA')
    assert row['dimensions']['business']['status'] == 'supported'
    assert row['dimensions']['valuation']['status'] == 'conditional'
    assert row['dimensions']['policy_exposure']['status'] == 'insufficient_evidence'
    assert row['assessment'] == 'insufficient_evidence'
    assert 'Business — supported' in (c.store.root/'draft.md').read_text()


def test_publication_policy_change_preserves_unrelated_conclusions_and_scenarios(tmp_path, monkeypatch):
    from spy_predictor_quant.investment_research.broker import Broker
    from spy_predictor_quant.investment_research.publication import publish, read_publication
    c, state = ready_controller(tmp_path/'run', DimensionWorker(), dimensional=True)
    broker = Broker(c.store, state)
    for identity in state['mandate']['publication_policy']['refresh_source_ids']:
        state['source_cache'].pop(identity, None)
        assert broker.call('read_source', {'source_id': identity})['status'] == 'OK'
    c.store.save(state)
    assert c.run()['status'] == 'DRAFT'
    original = Broker.fetch
    def changed_policy(self, source):
        return b'Changed synthetic policy event' if source['source_id'] == 'm3-events' else original(self, source)
    monkeypatch.setattr(Broker, 'fetch', changed_policy)
    publication = publish(c.store, tmp_path/'ledger')
    product = publication['product']
    assert product['schema_version'] == 'investment-research-publication-product-v2'
    assert all(names == ['policy_exposure'] for names in publication['refresh']['invalidation']['dimensions'].values())
    for row in product['findings']['instruments']:
        assert row['dimensions']['business']['status'] == 'supported'
        assert row['dimensions']['market_behavior']['status'] == 'supported'
        assert row['dimensions']['policy_exposure']['status'] == 'insufficient_evidence'
        if row['symbol'] != 'QQQ': assert row['dimensions']['valuation']['status'] == 'conditional'
    assert withdrawn_valuation_symbols(publication['refresh']) == []
    report = (tmp_path/'ledger/publications'/publication['publication_id']/'report.md').read_text()
    assert 'conditional valuation sensitivity' in report
    assert read_publication(tmp_path/'ledger', publication['publication_id']) == publication


def test_dimension_rejection_reports_all_blocked_conclusions_together(tmp_path):
    c, state = ready_controller(tmp_path, dimensional=True)
    value = scoped_result()
    value['gaps'].append({'critical': True, 'symbols': ['NVDA'], 'dimensions': ['business', 'valuation']})
    with pytest.raises(ValueError) as error:
        validate_dimensions(state, {'visible_evidence_ids': state['evidence_ids']}, value)
    message = str(error.value)
    assert 'blocks NVDA business' in message
    assert 'blocks NVDA valuation' in message
    assert 'blocks NVDA relative_preference' in message
