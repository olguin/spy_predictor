"""Aggregate all paid attempts and the weakest registered candidate-case rating."""
import argparse
import json
from pathlib import Path

from .role_quality import rate
from .store import Store

ROLES = {'company', 'macro', 'technical', 'geopolitics', 'commodities', 'challenger', 'director'}
ORDER = {'NEEDS_IMPROVEMENT': 0, 'VERY_GOOD': 1, 'EXCELLENT': 2}


def summarize(runs, candidates=()):
    paths = [Path(p).resolve() for p in runs]
    chosen = {Path(p).resolve() for p in candidates}
    if len(paths) != len(set(paths)) or not chosen <= set(paths):
        raise ValueError('Unique runs required; candidate runs must be included in usage ledger')
    ledger, selected = [], []
    totals = dict(model_calls=0, input_tokens=0, output_tokens=0, catalog_cost_usd=0)
    unknown = False
    for path in paths:
        store = Store(path); state = store.load()
        usage = {k: state['usage'][k] for k in totals}
        for k in totals:
            totals[k] += usage[k]
        unknown |= state['usage_unknown']
        row = {'path': str(path), 'status': state['status'], 'usage': usage, 'usage_unknown': state['usage_unknown']}
        if (path/'independent-review.json').exists() and state.get('evaluation'):
            review = json.loads((path/'independent-review.json').read_text())
            row['quality'] = rate(store, state, review)
        ledger.append(row)
        if path in chosen:
            registration = store.get('registrations', state['evaluation']['registration_id'])
            selected.append((registration, state, row))
    ratings = {role: {'rating': 'NEEDS_IMPROVEMENT', 'minimum_total': None} for role in sorted(ROLES)}
    failures = []
    if not selected:
        failures.append('No candidate cohort selected')
    else:
        first = selected[0][0]
        for reg, state, row in selected:
            if (reg['prompt_sha256'] != first['prompt_sha256'] or reg['source_identity'] != first['source_identity']
                    or reg['role_rubric'] != first['role_rubric'] or reg['source_state_sha256'] != first['source_state_sha256']
                    or state['mandate']['runtime'] != selected[0][1]['mandate']['runtime']):
                failures.append('Candidate cases must use the same prompts/runtime/rubric/source capture')
            if reg['profile'] != 'all_roles' or state['status'] != 'EVALUATION_COMPLETE' or not row.get('quality', {}).get('all_very_good'):
                failures.append('Every candidate case must complete with all tasks VERY_GOOD or EXCELLENT')
        if not any(not reg['omit_sources'] and not reg.get('challenge') for reg, _, _ in selected):
            failures.append('Primary unmodified case missing')
        if not any(reg['omit_sources'] and reg.get('challenge') for reg, _, _ in selected):
            failures.append('Missing-evidence plus planted-error stress case missing')
        for role in ROLES:
            rows = [r for _, _, item in selected for r in item.get('quality', {}).get('tasks', {}).values() if r['role'] == role]
            if not rows:
                failures.append('No rating for '+role)
                continue
            ratings[role] = {'rating': min((r['rating'] for r in rows), key=ORDER.get),
                             'minimum_total': min(r['total'] for r in rows)}
    if unknown:
        failures.append('Cumulative usage includes unknown amounts; totals are a lower bound')
    return {'status': 'TARGET_MET' if not failures else 'IN_PROGRESS', 'cumulative_usage': totals,
            'usage_unknown': unknown, 'roles': ratings, 'failures': failures, 'runs': ledger,
            'qualification': 'Provisional development ratings across selected cases; not human usefulness acceptance, release acceptance or investment performance.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='append', required=True, type=Path)
    parser.add_argument('--candidate', action='append', default=[], type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = summarize(args.run, args.candidate)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'runs'}, indent=2))
    return 0 if result['status'] == 'TARGET_MET' else 1


if __name__ == '__main__':
    raise SystemExit(main())
