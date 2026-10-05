"""Registered development experiments over immutable evidence; never publication.

Reuses the production worker, action validation and accounting. The explicitly
smaller scheduler runs Company then Director, with no acquisition or delegation.
"""
from copy import deepcopy
from datetime import datetime, timedelta
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from jsonschema import ValidationError

from spy_predictor_quant.market_archive import content_hash, utc_now
from .broker import Broker, LimitReached
from .contracts import ROOT, validate
from .controller import Controller, source_identity, subprocess_worker
from .delivery import coverage, require_coverage
from .dimensions import dimension_lines
from .panels import seed_panels
from .readiness import source_readiness
from .rendering import numerical_lines
from .store import Store
from .role_quality import ROLE_RUBRIC


RUBRIC = {
    'version': 'research-usefulness-v1',
    'scale': {'0': 'Missing, misleading or unusable', '1': 'Useful but materially incomplete',
              '2': 'Specific, supported and decision-relevant'},
    'dimensions': {
        'source_support': 'Material factual/numerical claims match dated primary evidence, periods and accounting/share basis.',
        'valuation_rationale': 'EPS and multiple assumptions have defensible anchors and mechanisms; arbitrary sensitivity grids fail.',
        'comparison': 'Explains company versus ETF differences and implied expectations, with comparable dates/methods or explicit limits.',
        'downside': 'Specific counter-case, transmission mechanism and conditional downside, without fabricated probabilities.',
        'change_conditions': 'Observable, instrument-specific evidence or thresholds explain how the assessment would change.',
        'uncertainty_scope': 'Preserves supported observations and scopes missingness correctly; neither forced preference nor blanket abstention.'},
    'minimum_each': 1, 'minimum_total': 10,
    'critical_defects': 'Any unresolved material factual, numerical, timing, attribution or required-analysis error fails independently of total.',
    'review_policy': 'Evidence-linked review required. Assistant/model review is provisional; actual human usefulness acceptance is separate.',
    'market_performance': 'No return, alpha or investment-performance conclusion from these research-quality scores.'}

TOOLS = ['inspect_evidence', 'calculate', 'calculate_scenarios', 'submit_findings']
TERMINAL = {'EVALUATION_COMPLETE', 'EVALUATION_INCOMPLETE', 'EVALUATION_INTERRUPTED'}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def prepare(source_root, output, *, prompt_version='v2.7', omit_sources=(), expectation='report', profile='company_director', challenge=False, reasoning_effort=None, max_output_tokens=None, specialist_role=None):
    """Freeze a new development registration. Never resume or mutate its source."""
    if profile not in {'company_director', 'all_roles', 'specialist'}:
        raise ValueError('Unknown evaluation profile')
    if profile == 'specialist':
        if specialist_role not in {'company', 'macro', 'technical', 'geopolitics', 'commodities'}:
            raise ValueError('Specialist profile requires a supported research role')
    elif specialist_role is not None:
        raise ValueError('Role selection requires the specialist profile')
    if challenge and profile != 'all_roles':
        raise ValueError('Adversarial challenge requires all roles')
    source_root, output = Path(source_root).resolve(), Path(output).resolve()
    if output == source_root or output.is_relative_to(source_root) or source_root.is_relative_to(output):
        raise ValueError('Evaluation must be separate from its source capture')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use an empty evaluation directory; registrations are immutable')
    if not re.fullmatch(r'v\d+\.\d+', prompt_version):
        raise ValueError('Invalid prompt version')
    source_bytes = (source_root/'state.json').read_bytes()
    origin = json.loads(source_bytes)
    if origin['mandate']['schema_version'] != 'investment-research-mandate-v6':
        raise ValueError('Evaluation requires a v6 evidence capture')
    if expectation not in {'report', 'early_stop'}:
        raise ValueError('Unknown expected behavior')
    source = Store(source_root)
    registered = {s['source_id'] for s in origin['mandate']['sources']}
    if not set(omit_sources) <= registered:
        raise ValueError('Unknown omitted source')
    records = {i: source.get('evidence', i) for i in origin['evidence_ids']}
    # A source-only packet prevents prior analyst conclusions leaking into a baseline.
    if any(e.get('kind') != 'source' for e in records.values()):
        raise ValueError('Use a source-only capture without prior calculations or findings')
    excluded = {i for i, e in records.items() if e.get('source_id') in omit_sources}
    while True:
        before = set(excluded)
        excluded.update(i for i, e in records.items() if e.get('parent_evidence_id') in excluded)
        if before == excluded:
            break
    records = {i: e for i, e in records.items() if i not in excluded}
    mandate = deepcopy(origin['mandate'])
    mandate['network']['enabled'] = False
    if reasoning_effort is not None:
        mandate['runtime']['reasoning_effort'] = reasoning_effort
    if max_output_tokens is not None:
        mandate['runtime']['max_output_tokens'] = max_output_tokens
    # Initialize production storage/contracts, then freeze the explicitly smaller
    # evaluation profile. Production's full-team scheduler minimum is inapplicable.
    controller = Controller(output)
    state = controller.create(mandate)
    state['mandate']['budgets'].update(model_calls=8, reserved_final_calls=3,
        input_tokens=350000, output_tokens=48000, catalog_cost_usd=3, wall_seconds=900,
        tool_calls=40, source_requests=1, followup_rounds=0)
    if profile == 'all_roles':
        state['mandate']['budgets'].update(model_calls=28, input_tokens=1000000, output_tokens=100000,
            catalog_cost_usd=10, wall_seconds=1200, tool_calls=100)
    if profile in {'all_roles', 'specialist'}:
        state['context_profile'] = 'role-research-v1'
    validate('mandate', state['mandate'])
    state['mandate_hash'] = content_hash(state['mandate'])
    state['limits'].update(state['mandate']['budgets'], source_requests=0, download_bytes=0)
    state['reservations'].update(input_tokens=100000, output_tokens=18000, tool_calls=3, source_requests=0)
    state['runtime_policy_version'] = 'research-evaluation-'+profile+'-v2'
    state['prompt_version'] = prompt_version
    prompt_root = ROOT/'prompts/investment-research'/prompt_version
    shared = (prompt_root/'shared.md').read_text()
    for role in state['prompts']:
        state['prompts'][role] = shared+'\n'+(prompt_root/(role+'.md')).read_text()
    for task in state['tasks']:
        task.update(status='OMITTED_EVALUATION', completed_at=utc_now())
    for identity, value in records.items():
        assert controller.store.put('evidence', value) == identity
        if value.get('document_id'):
            doc_id = value['document_id']
            assert controller.store.put('documents', source.get('documents', doc_id)) == doc_id
    state['evidence_ids'] = list(records)
    state['manifest_id'] = controller.store.put('manifests', {'parent': None, 'evidence_ids': list(records), 'created_at': utc_now()})
    state['source_cache'] = {s: i for s, i in origin['source_cache'].items() if i in records}
    state['source_failures'] = deepcopy(origin['source_failures'])
    state['source_failures'].update({s: {'status': 'GAP', 'reason': 'REGISTERED_EVALUATION_OMISSION'} for s in omit_sources})
    state['discovered_sources'] = {}  # No discovery/acquisition tool in this profile.
    state['market_context'] = deepcopy(origin['market_context'])
    state['market_context']['inputs'] = {s: e for s, e in state['market_context']['inputs'].items() if e['evidence_id'] in records}
    cutoff = origin.get('completed_at') or origin['started_at']
    state['source_readiness'] = source_readiness(controller.store, state, at=datetime.fromisoformat(cutoff))
    state['seed_complete'] = True
    broker = Broker(controller.store, state)
    seed_panels(broker)
    if profile in {'all_roles', 'specialist'}:
        for identity, evidence in records.items():
            if evidence.get('source_id', '').endswith('quarterly-results') and evidence.get('document_id'):
                broker.call('inspect_evidence', {'evidence_id': identity, 'query': 'outlook', 'occurrence': 0})
        from .fiscal_calendar import seed as seed_fiscal_calendar
        seed_fiscal_calendar(broker)
    prefix = ('Fixed-evidence development evaluation as of '+cutoff+'. This is not current research or a publication. '
        'No source acquisition, delegation or follow-up is available. State missing inputs, then deliver the useful '
        'conditional analysis the supplied evidence permits. Do not invent missing facts. ')
    if profile == 'company_director':
        prefix += 'Only Company and Director are scheduled; other roles are omitted. '
        schedule = [('company', 'research', 5), ('director', 'final', 3)]
    elif profile == 'specialist':
        prefix += 'Only the registered '+specialist_role+' research contribution is evaluated; no synthesis or whole-team pass is implied. '
        schedule = [(specialist_role, 'research', 5 if specialist_role == 'company' else 3)]
    else:
        schedule = [('company', 'research', 5), ('macro', 'research', 3), ('technical', 'research', 3),
                    ('geopolitics', 'research', 3), ('commodities', 'research', 3),
                    ('director', 'draft', 3), ('challenger', 'review', 3), ('director', 'final', 3)]
    tasks = []
    for role, stage, turns in schedule:
        question = prefix+mandate['objective']
        if stage == 'research' and profile in {'all_roles', 'specialist'}:
            scopes = {
                'company': 'Operating-to-earnings bridge, interpreted conditional valuation and ETF overlap.',
                'macro': 'Fixed benchmark context, competing macro transmission channels and discriminating evidence.',
                'technical': 'Matched completed-session behavior, differentiated trend/risk interpretation and one useful review condition per instrument.',
                'geopolitics': 'Dated policy status versus issuer geographic/product/supply exposure, scenarios and change conditions.',
                'commodities': 'Evidence-based materiality of product pricing versus input costs or customer constraints, with a concrete revisit trigger.'}
            question += (' Your assignment is ONLY the '+role+' contribution: '+scopes[role]+
                ' Do not answer the whole mandate, repeat other roles\' work or treat their unassessed inputs as your critical gaps.')
        if stage in {'draft', 'final'}:
            question += ' Synthesize actual specialist results, with linked scenario grids and separate conclusion statuses.'
        elif stage == 'review':
            question += ' Audit the Director draft and underlying sources; return specific, scoped objections with evidence.'
            if challenge:
                question += ' Also review the unverified alternative candidate draft supplied alongside it; preserve sound claims and identify specific material defects.'
        task = controller.add_task(state, role, stage, question)
        task.update(permitted_tools=TOOLS[:], model_turn_limit=turns)
        tasks.append(task)
    state['status'] = 'EVALUATION_PREPARED'
    from .context import compact
    projection = {i: compact(controller.store.get('evidence', i)) for i in state['evidence_ids']}
    role_projection_bytes = {task['role']: len(json.dumps({i: controller.context_evidence(state, task, controller.store.get('evidence', i))
                              for i in state['evidence_ids']}).encode()) for task in tasks}
    registration = {'version': 'research-evaluation-v2', 'profile': profile, 'context_profile': state.get('context_profile'),
        'specialist_role': specialist_role, 'challenge': challenge, 'challenge_recipe': 'reversed_bull_comparison_and_unverified_current_policy_with_sound_close_control' if challenge else None,
        'purpose': 'DEVELOPMENT_ONLY', 'prepared_at': utc_now(),
        'source_root': str(source_root), 'source_state_sha256': hashlib.sha256(source_bytes).hexdigest(),
        'evidence_cutoff': cutoff, 'source_evidence_ids': list(records), 'excluded_evidence_ids': sorted(excluded),
        'omit_sources': sorted(omit_sources), 'expectation': expectation, 'prompt_version': prompt_version,
        'prompt_sha256': {r: content_hash(state['prompts'][r]) for r in {t['role'] for t in tasks}},
        'source_identity': state['source_identity'], 'mandate_hash': state['mandate_hash'],
        'packet': {k: deepcopy(state[k]) for k in ('evidence_ids', 'source_cache', 'source_failures', 'source_readiness', 'market_context')},
        'effective_limits': state['limits'], 'reservations': state['reservations'],
        'tasks': [{k: t[k] for k in ('task_id', 'role', 'stage', 'question', 'model_turn_limit', 'permitted_tools')} for t in tasks],
        'rubric': RUBRIC, 'role_rubric': ROLE_RUBRIC, 'evidence_projection_bytes': len(json.dumps(projection).encode()),
        'role_projection_bytes': role_projection_bytes,
        'projection_qualification': 'Evidence JSON bytes only, not tokens; complete request bytes are measured before each dispatch.',
        'budget_qualification': 'Source requests/downloads are capped at zero. Model usage/cost may exceed a ceiling on the final response; observed usage is retained.',
        'exclusions': ['publication', 'live acquisition', 'frozen release cases', 'investment performance', 'full-team superiority']}
    identity = controller.store.put('registrations', registration)
    state['evaluation'] = {'registration_id': identity, 'task_ids': [t['task_id'] for t in tasks]}
    write_json(output/'registration.json', registration)
    controller.store.save(state)
    write_json(output/'review-template.json', review_template(identity))
    return {'registration_id': identity, 'status': state['status'], 'readiness': state['source_readiness']['status'],
            'effective_limits': state['limits'], 'evidence_projection_bytes': registration['evidence_projection_bytes']}


def review_template(identity):
    return {'registration_id': identity, 'reviewer': '', 'reviewer_kind': 'assistant',
        'dimensions': {k: {'score': None, 'reason': '', 'artifact_refs': []} for k in RUBRIC['dimensions']},
        'critical_defects': [], 'other_defects': [], 'human_usefulness': 'not_collected',
        'qualification': 'Template only; fill every dimension with evidence-linked reasoning. No automatic usefulness acceptance.'}


def integrity(store, state):
    registration = store.get('registrations', state['evaluation']['registration_id'])
    if source_identity() != registration['source_identity'] or state['source_identity'] != registration['source_identity']:
        raise ValueError('Evaluation runtime changed; create a new registration')
    if content_hash(state['mandate']) != registration['mandate_hash'] or state['limits'] != registration['effective_limits']:
        raise ValueError('Evaluation mandate or limits changed')
    if state['reservations'] != registration['reservations']:
        raise ValueError('Evaluation reservations changed')
    for role, digest in registration['prompt_sha256'].items():
        if content_hash(state['prompts'][role]) != digest:
            raise ValueError('Evaluation prompt changed')
    if state.get('context_profile') != registration.get('context_profile'):
        raise ValueError('Evaluation context profile changed')
    actual = [{k: t[k] for k in row} for row in registration['tasks']
              for t in state['tasks'] if t['task_id'] == row['task_id']]
    if actual != registration['tasks']:
        raise ValueError('Evaluation task profile changed')
    if state['evaluation']['task_ids'] != [t['task_id'] for t in registration['tasks']]:
        raise ValueError('Evaluation schedule changed')
    packet = registration['packet']
    if (not set(packet['evidence_ids']) <= set(state['evidence_ids']) or
            any(state[k] != packet[k] for k in ('source_cache', 'source_failures', 'source_readiness', 'market_context'))):
        raise ValueError('Evaluation evidence packet changed')
    if state['status'] == 'EVALUATION_PREPARED' and state['evidence_ids'] != packet['evidence_ids']:
        raise ValueError('Evidence added after registration')
    for identity in state['evidence_ids']:
        evidence = store.get('evidence', identity)
        if evidence.get('document_id'):
            store.get('documents', evidence['document_id'])
    return registration


def run(output, *, worker=subprocess_worker):
    store = Store(Path(output))
    with store.lock():
        state = store.load()
        registration = integrity(store, state)
        if state['status'] in TERMINAL:
            if (store.root/'scorecard.json').exists():
                pointer = json.loads((store.root/'scorecard.json').read_text())
                return store.get('scorecards', pointer['scorecard_id'])
            return scorecard(store, state)
        if state['status'] != 'EVALUATION_PREPARED' or state['attempts']:
            state.update(status='EVALUATION_INTERRUPTED', usage_unknown=True, completed_at=utc_now(),
                         stop_reason='Interrupted evaluation is not retried; create a new registration')
            store.save(state)
            return scorecard(store, state)
        def measured_worker(request, runtime, timeout):
            store.put('request_profiles', {'task_id': request['task_id'], 'request_id': content_hash(request),
                'request_bytes': len(json.dumps(request).encode()), 'evidence_count': len(request['context']['evidence']),
                'evidence_bytes': len(json.dumps(request['context']['evidence']).encode()),
                'prior_findings_bytes': len(json.dumps(request['context']['prior_findings']).encode()),
                'tools_schema_bytes': len(json.dumps(request['tool_schemas']).encode())})
            return worker(request, runtime, timeout)
        controller = Controller(store.root, measured_worker)
        state.update(status='EVALUATION_RUNNING', started_at=utc_now())
        state['run_deadline_at'] = (datetime.fromisoformat(state['started_at'])+timedelta(seconds=state['limits']['wall_seconds'])).isoformat()
        store.event(state, 'EVALUATION_STARTED', registration_id=state['evaluation']['registration_id'])
        try:
            if state['source_readiness']['status'] == 'BLOCKED':
                raise ValueError('Required source readiness blocked at the frozen evidence cutoff')
            require_coverage(store, state, 'seed')
            for task_id in state['evaluation']['task_ids']:
                task = next(t for t in state['tasks'] if t['task_id'] == task_id)
                if registration.get('challenge') and task['role'] == 'challenger':
                    from .evaluation_challenge import plant
                    plant(controller, state)
                state['phase'] = task['stage']
                controller.execute_task(state, task)
                if task['status'] != 'COMPLETE':
                    raise ValueError('Evaluation task did not complete')
                if task['role'] == 'company':
                    require_coverage(store, state, 'company_complete')
            state['status'] = 'EVALUATION_COMPLETE'
        except (LimitReached, ValueError, RuntimeError, TimeoutError, OSError, ValidationError, KeyError, KeyboardInterrupt, SystemExit) as error:
            state['status'] = 'EVALUATION_INTERRUPTED' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'EVALUATION_INCOMPLETE'
            state['stop_reason'] = str(error) if isinstance(error, (LimitReached, ValueError)) else type(error).__name__
            for task in state['tasks']:
                if task['status'] in {'PENDING', 'RUNNING'}:
                    task.update(status=state['status'], completed_at=utc_now())
        state['completed_at'] = utc_now()
        store.event(state, 'EVALUATION_FINISHED', status=state['status'])
        render(store, state, registration)
        return scorecard(store, state)


def render(store, state, registration):
    lines = ['# Registered role development evaluation', '',
        'Fixed archived evidence; unpublished and not current investment research.', '',
        'Evidence cutoff: '+registration['evidence_cutoff'], 'Execution: '+state['status'], '']
    for task in state['tasks']:
        if task['task_id'] not in state['evaluation']['task_ids']:
            continue
        lines += ['## '+task['role'].title(), '', 'Task status: '+task['status']]
        result = task.get('result')
        if not result:
            continue
        lines += ['', result['summary'], '', 'Counter-case: '+result['counter_thesis']]
        for row in result['instruments']:
            lines += ['', '### '+row['symbol'], '', row['thesis'], '', row['valuation'], '', row['counter_thesis']]
            lines += dimension_lines(row)
            lines += ['', 'Review conditions:']+[c['description'] for c in row['review_conditions']]
        lines += ['', 'Claims:']+[f"- {c['claim_id']}: {c['text']} ({', '.join(c['evidence_ids'])})" for c in result['claims']]
        lines += ['', 'Gaps:', json.dumps(result['gaps'], indent=2)]
        lines += ['', 'Objections:', json.dumps(result.get('objections', []), indent=2)]
        lines += ['', 'Dispositions:', json.dumps(result.get('dispositions', []), indent=2)]
    grids = [i for i in state['evidence_ids'] if store.get('evidence', i).get('kind') == 'scenario_grid']
    lines += numerical_lines(store, grids)
    (store.root/'evaluation-report.md').write_text('\n'.join(lines)+'\n')


def scorecard(store, state, review=None):
    registration = store.get('registrations', state['evaluation']['registration_id'])
    rubric = registration['rubric']
    final = next((t['result'] for t in state['tasks'] if t['stage'] == 'final' and t.get('result')), None)
    tasks = []
    for task in state['tasks']:
        if task['task_id'] not in state['evaluation']['task_ids']:
            continue
        attempts = [a for a in state['attempts'] if a['task_id'] == task['task_id']]
        receipts = [store.get('responses', a['response_id']).get('receipt') or {} for a in attempts if a.get('response_id')]
        tasks.append({'role': task['role'], 'stage': task['stage'], 'task_id': task['task_id'], 'status': task['status'], 'model_calls': len(attempts),
            'rejected_submissions': sum(a['status'] == 'REJECTED_VALIDATION' for a in attempts),
            'usage': {k: sum(r.get(k, 0) or 0 for r in receipts if type(r.get(k, 0)) in (int, float) and math.isfinite(r.get(k, 0)) and r.get(k, 0) >= 0)
                      for k in ('input_tokens', 'output_tokens', 'catalog_cost_usd')},
            'tools': [h['action']['tool'] for h in task['history']],
            'claims_delivered': len((task.get('result') or {}).get('claims', []))})
    negative_pass = (registration['expectation'] == 'early_stop' and state['status'] == 'EVALUATION_INCOMPLETE'
                     and state['source_readiness']['status'] == 'BLOCKED' and state['usage']['model_calls'] == 0)
    engineering = 'EXPECTED_EARLY_STOP' if negative_pass else 'PASS' if state['status'] == 'EVALUATION_COMPLETE' and registration['expectation'] == 'report' else 'FAIL'
    result = {'version': 'research-evaluation-scorecard-v1', 'registration_id': state['evaluation']['registration_id'],
        'execution_status': state['status'], 'engineering_status': engineering, 'review_status': 'PENDING',
        'stop_reason': state.get('stop_reason'), 'usage': state['usage'], 'usage_unknown': state['usage_unknown'],
        'elapsed_seconds': (datetime.fromisoformat(state.get('completed_at', utc_now()))-datetime.fromisoformat(state['started_at'])).total_seconds(),
        'tasks': tasks, 'delivery': coverage(store, state, final), 'review': None,
        'qualification': 'Structural completion is separate from usefulness. All failed attempts count. Unknown usage is a lower bound. No release/performance claim.'}
    from .evaluation_challenge import check
    result['challenge'] = check(state)
    if review is not None:
        validate_review(store, state, review)
        total = sum(d['score'] for d in review['dimensions'].values())
        passes = (engineering == 'PASS' and not state['usage_unknown'] and not review['critical_defects']
            and min(d['score'] for d in review['dimensions'].values()) >= rubric['minimum_each'] and total >= rubric['minimum_total']
            and review['human_usefulness'] != 'not_useful')
        result.update(review=review, total_score=total, review_status='PROVISIONAL_PASS' if passes else 'REJECTED')
        if passes and review['reviewer_kind'] == 'human' and review['human_usefulness'] == 'useful':
            result['review_status'] = 'HUMAN_ACCEPTED_DEVELOPMENT_RESULT'
        result['review_id'] = store.put('reviews', review)
    identity = store.put('scorecards', result)
    write_json(store.root/'scorecard.json', result | {'scorecard_id': identity})
    return result


def validate_review(store, state, review):
    rubric = store.get('registrations', state['evaluation']['registration_id'])['rubric']
    if review.get('registration_id') != state['evaluation']['registration_id']:
        raise ValueError('Review registration mismatch')
    if not review.get('reviewer') or review.get('reviewer_kind') not in {'assistant', 'human'}:
        raise ValueError('Named reviewer and reviewer kind required')
    if review.get('human_usefulness') not in {'not_collected', 'useful', 'not_useful'}:
        raise ValueError('Invalid human usefulness value')
    if review['reviewer_kind'] != 'human' and review['human_usefulness'] != 'not_collected':
        raise ValueError('Assistant review cannot supply human acceptance')
    if set(review.get('dimensions', {})) != set(rubric['dimensions']):
        raise ValueError('Every rubric dimension must be reviewed')
    for row in [*review['dimensions'].values(), *review['critical_defects'], *review['other_defects']]:
        if not row.get('reason') or not row.get('artifact_refs'):
            raise ValueError('Review needs reasons and artifact references')
        for ref in row['artifact_refs']:
            path = (store.root/ref).resolve()
            if not path.is_relative_to(store.root.resolve()) or not path.is_file():
                raise ValueError('Review artifact must exist inside the evaluation')
    if any(type(d.get('score')) is not int or not 0 <= d['score'] <= 2 for d in review['dimensions'].values()):
        raise ValueError('Scores must be integers from zero to two')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('--source', type=Path, required=True)
    prepare_parser.add_argument('--output', type=Path, required=True)
    prepare_parser.add_argument('--profile', choices=['company_director', 'all_roles', 'specialist'], default='company_director')
    prepare_parser.add_argument('--role', choices=['company', 'macro', 'technical', 'geopolitics', 'commodities'])
    prepare_parser.add_argument('--challenge', action='store_true')
    prepare_parser.add_argument('--reasoning', choices=['minimal', 'low', 'medium', 'high', 'xhigh', 'max'])
    prepare_parser.add_argument('--max-output-tokens', type=int)
    prepare_parser.add_argument('--prompts', default='v2.7')
    prepare_parser.add_argument('--omit-source', action='append', default=[])
    prepare_parser.add_argument('--expect', choices=['report', 'early_stop'], default='report')
    execute = commands.add_parser('run')
    execute.add_argument('--output', type=Path, required=True)
    execute.add_argument('--execute', action='store_true', help='Dispatch registered paid model calls')
    score = commands.add_parser('score')
    score.add_argument('--output', type=Path, required=True)
    score.add_argument('--review', type=Path, required=True)
    role_score = commands.add_parser('score-roles')
    role_score.add_argument('--output', type=Path, required=True)
    role_score.add_argument('--review', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.source, args.output, prompt_version=args.prompts, omit_sources=args.omit_source, expectation=args.expect, profile=args.profile, challenge=args.challenge, reasoning_effort=args.reasoning, max_output_tokens=args.max_output_tokens, specialist_role=args.role)
    elif args.command == 'run':
        if not args.execute:
            parser.error('Use --execute to dispatch this registered evaluation')
        result = run(args.output)
    else:
        store = Store(args.output)
        with store.lock():
            state = store.load()
            if state['status'] not in TERMINAL:
                raise ValueError('Review requires a terminal evaluation')
            review = json.loads(args.review.read_text())
            if args.command == 'score-roles':
                from .role_quality import rate
                result = rate(store, state, review)
                write_json(store.root/'role-scorecard.json', result)
            else:
                result = scorecard(store, state, review)
    print(json.dumps(result, indent=2))
    return 1 if result.get('engineering_status') == 'FAIL' or result.get('review_status') == 'REJECTED' or result.get('all_very_good') is False else 0


if __name__ == '__main__':
    raise SystemExit(main())
