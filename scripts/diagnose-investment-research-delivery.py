"""Read-only diagnosis of a saved run; no model calls, acquisitions or resume."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path

from spy_predictor_quant.investment_research.earnings import earnings_periods
from spy_predictor_quant.investment_research.store import Store


def diagnose(path):
    store = Store(path); state = store.load()
    tasks = []
    for task in state['tasks']:
        receipts = [store.get('responses', a['response_id']).get('receipt', {}) for a in state['attempts']
                    if a['task_id'] == task['task_id'] and a.get('response_id')]
        tasks.append({'task_id': task['task_id'], 'role': task['role'], 'stage': task['stage'],
            'turns_used': len(task['history']), 'turn_limit': task['model_turn_limit'],
            'tools': dict(Counter(h['action']['tool'] for h in task['history'])),
            'input_tokens': sum(r.get('input_tokens', 0) for r in receipts),
            'output_tokens': sum(r.get('output_tokens', 0) for r in receipts),
            'gaps': (task.get('result') or {}).get('gaps', [])})
    recovered = []
    for identity in state['evidence_ids']:
        e = store.get('evidence', identity)
        if e.get('adapter') != 'sec_companyfacts':
            continue
        document = store.get('documents', e['document_id'])
        periods = earnings_periods(json.loads(document['text']), e['data']['filings'], datetime.fromisoformat(e['retrieved_at']))
        recovered.append({'source_id': e['source_id'], 'evidence_id': identity,
            'raw_document_id': e['document_id'], 'content_sha256': e['content_sha256'],
            'original_selected_eps': e['data']['metrics'].get('diluted_eps'),
            'annual_observations_in_original_download': periods['annual'],
            'qualification': periods['qualification']})
    final = next(t['result'] for t in reversed(state['tasks']) if t['stage'] == 'final')
    return {'kind': 'RETROSPECTIVE_DELIVERY_DIAGNOSIS', 'run_id': state['run_id'],
        'original_state_sha256': hashlib.sha256((path/'state.json').read_bytes()).hexdigest(),
        'user_usefulness_verdict': 'REJECTED: requested relative valuation analysis not delivered',
        'usage': state['usage'], 'unused_model_calls': state['limits']['model_calls']-state['usage']['model_calls'],
        'scenario_calculations': sum(t['tools'].get('calculate', 0)+t['tools'].get('calculate_scenarios', 0) for t in tasks),
        'assessments': {r['symbol']: r['assessment'] for r in final['instruments']},
        'source_failures': state['source_failures'], 'tasks': tasks, 'recovered_earnings': recovered,
        'followups': [{'recipient': q['recipient'], 'question': q['question'], 'status': q['status'],
                      'answer_reused': q.get('answer_reused', False)} for q in state['questions'] if q['round'] > 0],
        'interpretation': 'Annual EPS existed in downloaded source bytes but was omitted from normalized evidence. '
            'This is a retrospective parser diagnosis, not a new company valuation, current data capture or release evaluation.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    print(json.dumps(diagnose(args.run), indent=2))
