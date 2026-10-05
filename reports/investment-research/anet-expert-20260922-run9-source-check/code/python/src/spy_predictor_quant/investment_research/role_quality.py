"""Predeclared per-role development ratings, distinct from human acceptance."""
from pathlib import Path

ROLE_RUBRIC = {
    'version': 'specialist-quality-v1',
    'dimensions': {
        'evidence_accuracy': 'Dated facts, numerical comparisons, fiscal/share basis and citations are correct.',
        'analytical_depth': 'Explains competing causal mechanisms, interprets calculations and tests important assumptions.',
        'decision_usefulness': 'Answers the role question with differentiated implications and observable change conditions.',
        'uncertainty': 'Scopes missingness and counter-cases honestly without hiding supported conclusions or forcing preference.',
        'coherence': 'Conclusions follow the cited evidence and calculations; structured claims match the prose.'},
    'scale': {'0': 'Absent or misleading', '1': 'Major deficiencies', '2': 'Useful but material improvements needed',
              '3': 'Strong, specific and supported; only minor improvements', '4': 'Exceptional depth and precision'},
    'very_good_total': 16, 'excellent_total': 19, 'minimum_each': 3,
    'critical_gate': 'Any unresolved material error fails regardless of points.',
    'qualification': 'Provisional development quality, not human acceptance, release acceptance or investment performance.'}


def rate(store, state, review):
    registration = store.get('registrations', state['evaluation']['registration_id'])
    rubric = registration['role_rubric']
    if review.get('registration_id') != state['evaluation']['registration_id'] or not review.get('reviewer'):
        raise ValueError('Named, registered review required')
    if review.get('reviewer_kind') not in {'assistant', 'human'}:
        raise ValueError('Reviewer kind required')
    required = set(state['evaluation']['task_ids'])
    if set(review.get('tasks', {})) != required:
        raise ValueError('Review every registered task; no selection of passing tasks')
    results = {}
    for task in state['tasks']:
        if task['task_id'] not in required:
            continue
        row = review['tasks'][task['task_id']]
        if set(row.get('dimensions', {})) != set(rubric['dimensions']):
            raise ValueError('Review every role quality dimension')
        for item in [*row['dimensions'].values(), *row['critical_defects']]:
            if not item.get('reason') or not item.get('artifact_refs'):
                raise ValueError('Evidence-linked rationale required')
            for ref in item['artifact_refs']:
                path = (store.root / ref).resolve()
                if not path.is_relative_to(store.root.resolve()) or not path.is_file():
                    raise ValueError('Review evidence must exist inside this evaluation')
        scores = [d.get('score') for d in row['dimensions'].values()]
        if any(type(n) is not int or not 0 <= n <= 4 for n in scores):
            raise ValueError('Integer scores zero through four required')
        total = sum(scores)
        eligible = task['status'] == 'COMPLETE' and not state['usage_unknown'] and not row['critical_defects']
        if task['role'] == 'challenger' and registration.get('challenge'):
            from .evaluation_challenge import check
            challenge = check(state)
            eligible = eligible and bool(challenge and challenge['caught_all_planted_material_errors']
                                         and challenge['sound_control_not_critically_flagged'])
        rating = 'NEEDS_IMPROVEMENT'
        if eligible and min(scores) >= rubric['minimum_each']:
            if total >= rubric['excellent_total']:
                rating = 'EXCELLENT'
            elif total >= rubric['very_good_total']:
                rating = 'VERY_GOOD'
        results[task['task_id']] = {'role': task['role'], 'stage': task['stage'], 'total': total, 'rating': rating}
    return {'registration_id': review['registration_id'], 'tasks': results,
            'all_very_good': all(r['rating'] in {'VERY_GOOD', 'EXCELLENT'} for r in results.values()),
            'review_id': store.put('role_reviews', review), 'qualification': rubric['qualification']}
