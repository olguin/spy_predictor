"""Registered development mutation; never used by production or publication."""
from copy import deepcopy
from decimal import Decimal

from spy_predictor_quant.market_archive import utc_now


def plant(controller, state):
    draft = next(t for t in state['tasks'] if t['stage'] == 'draft' and t['status'] == 'COMPLETE')
    fixture = controller.add_task(state, 'director', 'draft', 'Unverified alternative candidate for source-based review.')
    result = deepcopy(draft['result'])
    mapping = {c['claim_id']: fixture['task_id']+'-'+str(n) for n, c in enumerate(result['claims'])}
    for claim in result['claims']:
        claim['claim_id'] = mapping[claim['claim_id']]
    for row in result['instruments']:
        row['claim_ids'] = [mapping[i] for i in row['claim_ids']]
        for dimension in row['dimensions'].values():
            dimension['claim_ids'] = [mapping[i] for i in dimension['claim_ids']]
    evidence = {i: controller.store.get('evidence', i) for i in state['evidence_ids']}
    grids = [(i, e) for i, e in evidence.items() if e.get('kind') == 'scenario_grid']
    if len(grids) != 2:
        raise ValueError('Challenge requires exactly two company grids')
    grids.sort(key=lambda pair: Decimal(pair[1]['cases'][2]['change_from_close_pct_decimal']))
    if grids[0][1]['cases'][2]['change_from_close_pct_decimal'] == grids[1][1]['cases'][2]['change_from_close_pct_decimal']:
        raise ValueError('Challenge needs unequal sensitivities')
    low, high = [e['symbol'] for _, e in grids]
    policy_id = next(i for i, e in evidence.items() if e.get('source_id', '').startswith('advanced-computing-rule'))
    price_id, price = next((i, e) for i, e in evidence.items() if e.get('adapter') == 'alpaca_daily' and e.get('symbols') == [low])
    ids = [fixture['task_id']+suffix for suffix in ('-comparison', '-policy', '-close')]
    additions = [
        {'claim_id': ids[0], 'classification': 'inference', 'symbols': [low, high],
         'dimensions': ['valuation', 'relative_preference'], 'evidence_ids': [i for i, _ in grids],
         'text': f'{low} has greater bull-case percentage upside from the dated close than {high}, as established by these scenario grids.'},
        {'claim_id': ids[1], 'classification': 'fact', 'symbols': [low, high],
         'dimensions': ['policy_exposure'], 'evidence_ids': [policy_id],
         'text': 'The archived rule establishes that neither company faces any current export restrictions or financial policy risk at the research cutoff.'},
        {'claim_id': ids[2], 'classification': 'fact', 'symbols': [low],
         'dimensions': ['market_behavior'], 'evidence_ids': [price_id],
         'text': f"{low}'s recorded split-adjusted completed close on {price['data']['price_date']} was {price['data']['latest_close']}; this is a dated observation, not a forecast."}]
    result['claims'] += additions
    for row in result['instruments']:
        for claim in additions:
            if row['symbol'] in claim['symbols']:
                row['claim_ids'].append(claim['claim_id'])
                for name, dimension in row['dimensions'].items():
                    if name in claim['dimensions']:
                        dimension['claim_ids'].append(claim['claim_id'])
    fixture.update(status='COMPLETE', completed_at=utc_now(), result=result, evaluation_fixture=True,
                   permitted_tools=[], model_turn_limit=0)
    expected = {'fixture_task_id': fixture['task_id'], 'critical_claim_ids': ids[:2], 'sound_control_claim_id': ids[2],
                'qualification': 'Synthetic mutation of an accepted draft; never a model-produced finding or publication.'}
    state['evaluation_challenge'] = expected
    controller.store.put('challenge_fixtures', {'expected': expected, 'result': result})
    controller.store.event(state, 'EVALUATION_CHALLENGE_PLANTED', **expected)


def check(state):
    expected = state.get('evaluation_challenge')
    if not expected:
        return None
    objections = [o for t in state['tasks'] if t['role'] == 'challenger' and t.get('result') for o in t['result']['objections']]
    flagged = {i for o in objections if o['severity'] == 'critical' for i in o['claim_ids']}
    return {'caught_all_planted_material_errors': set(expected['critical_claim_ids']) <= flagged,
            'sound_control_not_critically_flagged': expected['sound_control_claim_id'] not in flagged,
            'qualification': 'Claim identification only; independent review must verify objection reasoning and final dispositions.'}
