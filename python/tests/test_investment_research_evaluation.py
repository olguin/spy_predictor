"""No provider calls: evaluation boundaries and scorecard failure semantics."""
from copy import deepcopy
import json

import pytest

from spy_predictor_quant.investment_research.controller import Controller
from spy_predictor_quant.investment_research.evaluation import prepare, run, scorecard, review_template
from spy_predictor_quant.investment_research.store import Store
from test_investment_research import response
from test_investment_research_readiness import DimensionWorker, ready_controller


class ProbeWorker(DimensionWorker):
    def __call__(self, request, runtime, timeout):
        assert set(request['tool_schemas']) <= {'inspect_evidence', 'calculate', 'calculate_scenarios', 'submit_findings'}
        answer = super().__call__(request, runtime, timeout)
        if request['context']['task']['stage'] == 'final' and answer['action']['tool'] == 'submit_findings':
            for row in answer['action']['arguments']['role_coverage']:
                row.update(status='completed' if row['role'] == 'company' else 'omitted', reason='Registered two-role evaluation')
        return answer


def prepared(tmp_path, **kwargs):
    c, _ = ready_controller(tmp_path/'source', dimensional=True)
    source_bytes = (c.store.root/'state.json').read_bytes()
    output = tmp_path/'evaluation'
    receipt = prepare(c.store.root, output, **kwargs)
    assert (c.store.root/'state.json').read_bytes() == source_bytes
    return output, receipt


def test_fixed_packet_runs_bounded_company_director_and_never_implicitly_repeats(tmp_path):
    output, receipt = prepared(tmp_path)
    assert receipt['effective_limits']['model_calls'] == 8
    assert receipt['effective_limits']['source_requests'] == 0
    result = run(output, worker=ProbeWorker())
    assert result['engineering_status'] == 'PASS', result['stop_reason']
    assert result['review_status'] == 'PENDING'
    assert result['usage']['model_calls'] == 6 and result['usage']['source_requests'] == 0
    assert result['usage']['download_bytes'] == 0
    assert [t['role'] for t in result['tasks']] == ['company', 'director']
    assert all(r['scenario_linked_in_report'] for r in result['delivery']['companies'])
    assert len(list((output/'request_profiles').glob('*.json'))) == 6
    assert run(output, worker=lambda *a: pytest.fail('No paid replay')) == result
    with pytest.raises(ValueError, match='evaluation runner'):
        Controller(output).run()
    with pytest.raises(ValueError, match='empty evaluation'):
        prepare(tmp_path/'source', output)


def test_missing_mandatory_source_stops_without_model_work(tmp_path):
    output, _ = prepared(tmp_path, omit_sources=['NVDA'], expectation='early_stop')
    result = run(output, worker=lambda *a: pytest.fail('No model call allowed'))
    assert result['engineering_status'] == 'EXPECTED_EARLY_STOP'
    assert result['usage']['model_calls'] == 0


def test_focused_specialist_replay_cannot_dispatch_the_rest_of_the_team(tmp_path):
    output, _ = prepared(tmp_path, profile='specialist', specialist_role='technical', prompt_version='v2.13', model='openai-codex/gpt-5.6-sol')
    store = Store(output)
    state = store.load()
    registration = store.get('registrations', state['evaluation']['registration_id'])
    assert registration['profile'] == 'specialist'
    assert registration['specialist_role'] == 'technical'
    assert state['mandate']['runtime']['model'] == 'openai-codex/gpt-5.6-sol'
    assert state['limits']['model_calls'] == 6
    assert state['limits']['catalog_cost_usd'] == 1
    assert [(t['role'], t['stage'], t['model_turn_limit']) for t in registration['tasks']] == [('technical', 'research', 3)]
    assert state['context_profile'] == 'role-research-v1'
    worker = ProbeWorker()
    result = run(output, worker=worker)
    assert result['engineering_status'] == 'PASS'
    assert result['review_status'] == 'PENDING'
    assert result['usage']['model_calls'] == 1 and result['usage']['source_requests'] == 0
    assert [r['context']['task']['role'] for r in worker.requests] == ['technical']
    assert worker.requests[0]['context']['prior_findings'] == []
    assert not any(t['stage'] == 'final' for t in result['tasks'])


@pytest.mark.parametrize('role', [None, 'director', 'challenger'])
def test_focused_replay_rejects_roles_requiring_upstream_synthesis(tmp_path, role):
    with pytest.raises(ValueError, match='supported research role'):
        prepared(tmp_path, profile='specialist', specialist_role=role)


@pytest.mark.parametrize('mutation', ['limits', 'packet', 'prompt', 'schedule'])
def test_registration_tampering_blocks_dispatch(tmp_path, mutation):
    output, _ = prepared(tmp_path); store = Store(output); state = store.load()
    if mutation == 'limits': state['limits']['model_calls'] += 1
    if mutation == 'packet': state['evidence_ids'].pop()
    if mutation == 'prompt': state['prompts']['company'] += 'Changed'
    if mutation == 'schedule': state['evaluation']['task_ids'].pop()
    store.save(state)
    with pytest.raises(ValueError, match='changed'):
        run(output, worker=lambda *a: pytest.fail('No model call allowed'))


def test_missing_grids_and_unknown_usage_stop_without_director(tmp_path):
    output, _ = prepared(tmp_path)
    worker = ProbeWorker()
    def no_grids(request, runtime, timeout):
        # Capture a valid Company submission from the fixture after simulating its grids.
        fake = deepcopy(request)
        for instrument in fake['context']['mandate']['watchlist']:
            fake['context']['evidence']['fake-'+instrument['symbol']] = {'kind': 'scenario_grid', 'symbol': instrument['symbol']}
        return worker(fake, runtime, timeout)
    result = run(output, worker=no_grids)
    assert result['engineering_status'] == 'FAIL' and result['usage']['model_calls'] == 1
    assert result['tasks'][1]['model_calls'] == 0
    other, _ = prepared(tmp_path/'unknown')
    result = run(other, worker=lambda *a: {'schema_version': 'pi-research-worker-v2', 'action': None})
    assert result['usage_unknown'] and result['usage']['model_calls'] == 1
    assert result['tasks'][1]['model_calls'] == 0
    assert run(other, worker=lambda *a: pytest.fail('Unknown usage must not retry')) == result


def test_reviews_cannot_average_away_missing_work_or_claim_human_acceptance(tmp_path):
    output, _ = prepared(tmp_path); run(output, worker=ProbeWorker())
    store = Store(output); state = store.load()
    review = review_template(state['evaluation']['registration_id']); review['reviewer'] = 'Synthetic reviewer'
    for row in review['dimensions'].values():
        row.update(score=2, reason='Synthetic test, not actual financial judgment', artifact_refs=['evaluation-report.md'])
    assert scorecard(store, state, review)['review_status'] == 'PROVISIONAL_PASS'
    review['dimensions']['valuation_rationale']['score'] = 0
    result = scorecard(store, state, review)
    assert result['total_score'] == 10 and result['review_status'] == 'REJECTED'
    review['dimensions']['valuation_rationale']['score'] = 2
    review['critical_defects'] = [{'reason': 'Synthetic material unsupported claim', 'artifact_refs': ['evaluation-report.md']}]
    assert scorecard(store, state, review)['review_status'] == 'REJECTED'
    review['human_usefulness'] = 'useful'
    with pytest.raises(ValueError, match='human acceptance'): scorecard(store, state, review)
    review['human_usefulness'] = 'not_collected'; review['critical_defects'] = []
    review['dimensions']['source_support']['artifact_refs'] = ['../source/state.json']
    with pytest.raises(ValueError, match='inside the evaluation'): scorecard(store, state, review)


def test_later_rubric_changes_do_not_rescore_old_registration_under_new_thresholds(tmp_path, monkeypatch):
    from spy_predictor_quant.investment_research import evaluation
    output, _ = prepared(tmp_path); run(output, worker=ProbeWorker())
    store = Store(output); state = store.load()
    review = review_template(state['evaluation']['registration_id']); review['reviewer'] = 'Synthetic reviewer'
    for row in review['dimensions'].values():
        row.update(score=1, reason='Synthetic partial work', artifact_refs=['evaluation-report.md'])
    monkeypatch.setattr(evaluation, 'RUBRIC', evaluation.RUBRIC | {'minimum_total': 0, 'minimum_each': 0})
    assert scorecard(store, state, review)['review_status'] == 'REJECTED'


def test_all_roles_registration_and_role_ratings_do_not_average_away_defects(tmp_path):
    from spy_predictor_quant.investment_research.role_quality import rate, ROLE_RUBRIC
    output, _ = prepared(tmp_path, profile='all_roles', prompt_version='v2.8')
    store = Store(output); state = store.load()
    registration = store.get('registrations', state['evaluation']['registration_id'])
    assert len(registration['tasks']) == 8
    assert set(registration['prompt_sha256']) == {'company', 'macro', 'technical', 'geopolitics', 'commodities', 'director', 'challenger'}
    assert state['context_profile'] == 'role-research-v1'
    assert state['limits']['source_requests'] == 0
    review = {'registration_id': state['evaluation']['registration_id'], 'reviewer': 'Synthetic test', 'reviewer_kind': 'assistant', 'tasks': {}}
    for task in state['tasks']:
        if task['task_id'] in state['evaluation']['task_ids']:
            task['status'] = 'COMPLETE'
            review['tasks'][task['task_id']] = {'dimensions': {k: {'score': 4, 'reason': 'Synthetic test only', 'artifact_refs': ['registration.json']} for k in ROLE_RUBRIC['dimensions']}, 'critical_defects': []}
    assert rate(store, state, review)['all_very_good']
    row = next(iter(review['tasks'].values()))
    row['dimensions']['evidence_accuracy']['score'] = 2
    assert not rate(store, state, review)['all_very_good']  # 18/20 cannot hide a weak dimension.
    row['dimensions']['evidence_accuracy']['score'] = 4
    row['critical_defects'].append({'reason': 'Synthetic critical error', 'artifact_refs': ['registration.json']})
    assert not rate(store, state, review)['all_very_good']
    row['critical_defects'] = []
    state['usage_unknown'] = True
    assert not rate(store, state, review)['all_very_good']
    state['usage_unknown'] = False
    state['context_profile'] = 'tampered'
    store.save(state)
    with pytest.raises(ValueError, match='context profile'):
        run(output, worker=lambda *a: pytest.fail('No dispatch'))


def test_role_projection_retains_numbers_and_makes_omitted_text_explicit():
    from spy_predictor_quant.investment_research.role_context import project
    value = {'adapter': 'document_section', 'symbols': ['X'], 'query': 'outlook', 'published_at': '2026-01-01', 'occurrence': 0, 'data': None, 'excerpt': 'x'*3100+'EPS 9.25'}
    selected = {(('X',), 'outlook'): ('2026-01-01', 0)}
    assert 'EPS 9.25' in project(value, 'company', selected)['excerpt']
    assert 'excerpt' not in project(value, 'technical', selected)
    assert 'Catalog only' in project(value, 'technical', selected)['context_projection']
    facts = {'adapter': 'sec_companyfacts', 'data': {'earnings_periods': {'annual': [{'value': 9.25}]}}}
    assert project(facts, 'company', {})['data'] == facts['data']


def test_adversarial_fixture_preserves_real_draft_and_has_negative_control(tmp_path):
    from types import SimpleNamespace
    from spy_predictor_quant.investment_research.evaluation_challenge import plant, check
    store = Store(tmp_path)
    ids = []
    for symbol, upside in [('X', '50'), ('Y', '30')]:
        ids.append(store.put('evidence', {'kind': 'scenario_grid', 'symbol': symbol, 'cases': [{}, {}, {'change_from_close_pct_decimal': upside}]}))
        ids.append(store.put('evidence', {'adapter': 'alpaca_daily', 'symbols': [symbol], 'data': {'price_date': '2026-09-18', 'latest_close': 100}}))
    ids.append(store.put('evidence', {'source_id': 'advanced-computing-rule-test'}))
    original = {'claims': [{'claim_id': 'draft-c', 'text': 'Sound original'}], 'instruments': [
        {'symbol': x, 'claim_ids': ['draft-c'], 'dimensions': {'valuation': {'claim_ids': ['draft-c']}, 'policy_exposure': {'claim_ids': []}, 'market_behavior': {'claim_ids': []}}} for x in ('X', 'Y')]}
    before = deepcopy(original)
    state = {'tasks': [{'task_id': 'draft', 'stage': 'draft', 'role': 'director', 'status': 'COMPLETE', 'result': original}], 'evidence_ids': ids, 'events': []}
    def add_task(state, role, stage, question):
        task = {'task_id': 'fixture', 'role': role, 'stage': stage}; state['tasks'].append(task); return task
    plant(SimpleNamespace(store=store, add_task=add_task), state)
    assert original == before
    fixture = state['tasks'][-1]
    assert fixture['evaluation_fixture'] and fixture['model_turn_limit'] == 0
    assert 'Y has greater' in fixture['result']['claims'][-3]['text']
    assert fixture['result']['instruments'][0]['dimensions']['valuation']['claim_ids'] == ['fixture-0', 'fixture-comparison']
    state['tasks'].append({'role': 'challenger', 'result': {'objections': [{'severity': 'critical', 'claim_ids': ['fixture-comparison', 'fixture-policy']}]}})
    assert check(state)['caught_all_planted_material_errors']
    assert check(state)['sound_control_not_critically_flagged']
    state['tasks'][-1]['result']['objections'][0]['claim_ids'].append('fixture-close')
    assert not check(state)['sound_control_not_critically_flagged']


def test_draft_identity_map_requires_each_instrument_and_restores_without_repair(tmp_path):
    from jsonschema import Draft202012Validator, ValidationError
    from spy_predictor_quant.investment_research.result_transport import tool_schemas, restore_action
    from spy_predictor_quant.investment_research.contracts import ROOT
    output, _ = prepared(tmp_path, profile='all_roles', prompt_version='v2.9')
    state = Store(output).load()
    task = next(t for t in state['tasks'] if t['stage'] == 'draft')
    base = json.loads((ROOT/'prompts/investment-research/v2.9/tools.json').read_text())
    definitions = tool_schemas(base, task, state, 1)
    schema = definitions['submit_findings']['properties']['instruments']
    assert schema['type'] == 'object'
    assert set(schema['required']) == {i['symbol'] for i in state['mandate']['watchlist']}
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate({})
    # Identity conversion itself must preserve text, rather than repair meaning.
    minimal = {'submit_findings': {'type': 'object', 'properties': {'objections': {}, 'instruments': schema | {'properties': {s: {'type': 'object'} for s in schema['required']}}}}}
    action = {'tool': 'submit_findings', 'arguments': {'instruments': {s: {'thesis': 'verbatim'} for s in schema['required']}}}
    restored = restore_action(action, minimal, 'draft')
    assert restored['arguments']['instruments'] == [{'symbol': s, 'thesis': 'verbatim'} for s in schema['required']]


def test_campaign_requires_consistent_primary_and_stress_without_erasing_unknown_history(tmp_path, monkeypatch):
    from spy_predictor_quant.investment_research import evaluation_campaign as campaign
    roots = [tmp_path/x for x in ('failed', 'primary', 'stress')]
    for root in roots:
        root.mkdir()
    for root in roots[1:]:
        (root/'independent-review.json').write_text('{}')
    base = {'prompt_sha256': {'company': 'fixed'}, 'source_identity': {'runtime': 'fixed'},
            'role_rubric': {'fixed': True}, 'source_state_sha256': 'fixed', 'profile': 'all_roles', 'omit_sources': [], 'challenge': False}
    registrations = {roots[1]: deepcopy(base), roots[2]: base | {'omit_sources': ['qqq-profile'], 'challenge': True}}
    class FakeStore:
        def __init__(self, path): self.root = path
        def load(self):
            return {'status': 'EVALUATION_INCOMPLETE' if self.root == roots[0] else 'EVALUATION_COMPLETE',
                    'usage_unknown': self.root == roots[0], 'usage': {'model_calls': 1, 'input_tokens': 100, 'output_tokens': 20, 'catalog_cost_usd': 0.1},
                    'evaluation': {'registration_id': 'test'}, 'mandate': {'runtime': {'model': 'same'}}}
        def get(self, kind, identity): return registrations[self.root]
    monkeypatch.setattr(campaign, 'Store', FakeStore)
    monkeypatch.setattr(campaign, 'rate', lambda *a: {'all_very_good': True, 'tasks': {r: {'role': r, 'total': 16, 'rating': 'VERY_GOOD'} for r in campaign.ROLES}})
    result = campaign.summarize(roots, roots[1:])
    assert result['status'] == 'TARGET_MET'
    assert result['usage_unknown'] and result['accounting_status'] == 'LOWER_BOUND_WITH_UNKNOWN_ATTEMPT'
    assert result['cumulative_usage']['model_calls'] == 3
    assert campaign.summarize(roots, roots[1:2])['status'] == 'IN_PROGRESS'
    registrations[roots[2]]['prompt_sha256'] = {'company': 'different'}
    assert campaign.summarize(roots, roots[1:])['status'] == 'IN_PROGRESS'
