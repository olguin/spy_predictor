"""Read-only structural audit of a workspace pilot. Never a usefulness score."""
import argparse
from datetime import datetime
from decimal import Decimal
import hashlib
import json

from spy_predictor_quant.investment_research.contracts import validate
from spy_predictor_quant.investment_research.controller import source_identity
from spy_predictor_quant.investment_research.publication import read_publication
from spy_predictor_quant.investment_research.workspace import Workspace
from spy_predictor_quant.market_archive import content_hash
from spy_predictor_quant.investment_research.store import Store


def audit(identity):
    workspace = Workspace()
    job = workspace.job(identity)
    directory = workspace.directory(identity)
    mandate = json.loads((directory/'mandate.json').read_text())
    store = Store(directory/'run')
    state = store.load()
    product = store.get('products', state['product_id']) if state.get('product_id') else None
    checks = {}
    checks['frozen_mandate'] = content_hash(mandate) == state['mandate_hash'] == content_hash(state['mandate'])
    checks['question_registered_before_execution'] = (job['question'] in mandate['objective'] and
        datetime.fromisoformat(job['created_at']) <= datetime.fromisoformat(state['started_at']))
    checks['archived_runtime_matches_registration'] = all(
        hashlib.sha256((store.root/'code'/p).read_bytes()).hexdigest() == h for p,h in state['source_identity'].items())
    attempts = state['attempts']
    receipts = [store.get('responses', a['response_id']).get('receipt', {}) for a in attempts if a.get('response_id')]
    checks['known_real_usage'] = bool(receipts) and len(receipts) == len(attempts) and not state['usage_unknown'] and all(
        r.get('model') == mandate['runtime']['model'] and r.get('model_calls') == 1 and r.get('pi_version') for r in receipts)
    checks['receipt_totals'] = bool(receipts) and state['usage']['model_calls'] == len(attempts) and all(
        all(r.get(k) is not None for r in receipts) and
        abs(sum((Decimal(str(r[k])) for r in receipts), Decimal(0))-Decimal(str(state['usage'][k]))) < Decimal('0.000000001')
        for k in ('input_tokens', 'output_tokens', 'catalog_cost_usd'))
    checks['within_budget'] = all(state['usage'][k] <= v for k,v in state['limits'].items() if k in state['usage'])
    checks['terminal_within_wall_budget'] = bool(state.get('completed_at') and
        0 <= (datetime.fromisoformat(state['completed_at'])-datetime.fromisoformat(state['started_at'])).total_seconds() <= state['limits']['wall_seconds'])
    checks['draft_available'] = bool(product)
    if product:
        validate('product', product)
        checks['complete_instrument_identities'] = {r['symbol'] for r in product['findings']['instruments']} == set(job['scope'])
        checks['differentiated_thesis_texts'] = len({r['thesis'] for r in product['findings']['instruments']}) == len(job['scope'])
        checks['question_dispositions'] = {q['question_id'] for q in state['questions']} == {q['question_id'] for q in product['findings']['question_effects']}
        objections = {o['objection_id'] for t in state['tasks'] if t['result'] for o in t['result']['objections']}
        checks['objection_dispositions'] = objections == {d['objection_id'] for d in product['findings']['dispositions']}
    for identity in state['evidence_ids']:
        store.get('evidence', identity)
    checks['evidence_integrity'] = True
    if state.get('publication_id'):
        record = read_publication(workspace.ledger, state['publication_id'])
        checks['verified_publication_bundle'] = record['run_id'] == state['run_id'] and record['usage'] == state['usage']
    return {'kind': 'WORKSPACE_PILOT_STRUCTURAL_AUDIT', 'status': 'PASS' if all(checks.values()) else 'FAIL',
            'checks': checks, 'run_id': state['run_id'], 'run_status': state['status'], 'usage': state['usage'],
            'current_runtime_matches_frozen_run': source_identity() == state['source_identity'],
            'runtime_note': 'Read-only replay can use newer presentation code. Execution still requires the frozen runtime identity.',
            'stop_reason': state.get('stop_reason'), 'm4_release_evaluation': False,
            'semantic_claim_review': 'Required separately; structural checks do not establish financial usefulness.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace_job_id')
    args = parser.parse_args()
    result = audit(args.workspace_job_id)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
