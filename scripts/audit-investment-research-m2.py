#!/usr/bin/env python3
"""Read-only M2 structural audit. Semantic source/claim review is a separate gate."""
import argparse
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from spy_predictor_quant.investment_research.contracts import validate
from spy_predictor_quant.investment_research.store import Store


def audit(root):
    if not (root / 'state.json').is_file():
        raise ValueError('Existing run state required; audit does not create runs')
    store = Store(root); state = store.load(); checks = {}
    product = store.get('products', state['product_id']) if state.get('product_id') else None
    checks['unpublished_five_symbol_draft'] = bool(product and state['status'] == 'DRAFT' and len(product['symbols']) == 5 and
        product['published_at'] is None and product['observation_contract'] is None)
    if product:
        validate('product', product)
        rows = product['findings']['instruments']
        checks['all_instruments_and_distinct_thesis_texts'] = ({r['symbol'] for r in rows} == set(product['symbols']) and
            len({r['thesis'] for r in rows}) == len(rows))
        roles = product['role_coverage']
        checks['all_specialists_accounted'] = {r['role'] for r in roles} == {'company', 'macro', 'technical', 'geopolitics', 'commodities'} and all(r['reason'].strip() for r in roles)
        checks['all_question_effects'] = {q['question_id'] for q in state['questions']} == {q['question_id'] for q in product['findings']['question_effects']}
        objections = {o['objection_id'] for t in state['tasks'] if t['result'] for o in t['result']['objections']}
        checks['all_objection_dispositions'] = objections == {d['objection_id'] for d in product['findings']['dispositions']}
    attempts = state['attempts']
    receipts, requests = [], []
    for attempt in attempts:
        requests.append(store.get('requests', attempt['request_id']))
        if attempt.get('response_id'):
            receipts.append(store.get('responses', attempt['response_id']).get('receipt', {}))
    checks['known_real_provider_receipts'] = bool(receipts) and len(receipts) == len(attempts) and not state['usage_unknown'] and all(r.get('model') == state['mandate']['runtime']['model'] and r.get('model_calls') == 1 and r.get('pi_version') for r in receipts)
    checks['within_global_budgets'] = all(state['usage'][k] <= v for k, v in state['limits'].items() if k in state['usage'])
    checks['completed_within_wall_budget'] = bool(state.get('completed_at') and
        0 <= (datetime.fromisoformat(state['completed_at']) - datetime.fromisoformat(state['started_at'])).total_seconds() <= state['limits']['wall_seconds'])
    checks['model_call_attempt_count'] = state['usage']['model_calls'] == len(attempts)
    checks['usage_reconciles_to_receipts'] = bool(receipts) and all(
        all(r.get(key) is not None for r in receipts) and
        abs(sum((Decimal(str(r[key])) for r in receipts), Decimal(0)) - Decimal(str(state['usage'][key]))) <= Decimal('0.000000001')
        for key in ('input_tokens', 'output_tokens', 'catalog_cost_usd'))
    checks['task_visibility_matches_manifest'] = all({r.get('evidence_aliases', {}).get(i, i) for i in r['context']['evidence']} == set(store.get('manifests', r['context']['manifest_id'])['evidence_ids']) for r in requests)
    independent = [r for r in requests if r['context']['task']['stage'] == 'independent']
    checks['challenger_independent_first_pass'] = bool(independent) and all(not r['context']['prior_findings'] and not r['context']['questions'] for r in independent)
    checks['archived_runtime_matches_registration'] = all(hashlib.sha256((root / 'code' / name).read_bytes()).hexdigest() == expected for name, expected in state['source_identity'].items())
    registration_path = root.with_name(root.name + '-registration.json')
    registration = json.loads(registration_path.read_text()) if registration_path.is_file() else None
    checks['preregistered_runtime_and_budgets'] = bool(registration and
        registration['source_identity'] == state['source_identity'] and
        registration['budgets'] == state['mandate']['budgets'] and
        datetime.fromisoformat(registration['registered_at']) <= datetime.fromisoformat(state['started_at']))
    checks['fixed_market_universe'] = set(state['market_context']['inputs']) <= set(state['mandate']['market_context_symbols'])
    for identity in state['evidence_ids']:
        store.get('evidence', identity)
    checks['content_addressed_evidence_integrity'] = True
    return {'schema_version': 'investment-research-m2-structural-audit-v1', 'run_id': state['run_id'],
        'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'usage': state['usage'],
        'semantic_review': 'REQUIRED: source support, numerical qualifications, differentiated investment judgment and scoped missingness are not proven by structural checks.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('run', type=Path); args = parser.parse_args()
    report = audit(args.run)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['status'] == 'PASS' else 1)
