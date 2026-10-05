"""Conclusion-specific eligibility, with explicit dependency propagation."""

DIMENSIONS = ('business', 'valuation', 'market_behavior', 'policy_exposure', 'relative_preference')


def enabled(state):
    return state['mandate']['schema_version'] in {'investment-research-mandate-v6', 'investment-research-mandate-v7'}


def validate_dimensions(state, task, result):
    claims = {c['claim_id']: c for c in result['claims']}
    prior_claims = {c['claim_id']: c for t in state['tasks'] if t.get('result') for c in t['result']['claims']}
    for objection in result['objections']:
        affected = {d for identity in objection['claim_ids'] for d in (claims | prior_claims)[identity]['dimensions']}
        if not affected <= set(objection['dimensions']):
            raise ValueError('Objection scope must include the dimensions of its referenced claims: '+
                             objection['objection_id']+' missing '+', '.join(sorted(affected-set(objection['dimensions']))))
    original = {o['objection_id']: o for t in state['tasks'] if t.get('result') for o in t['result']['objections']}
    decisions = {d['objection_id']: d for d in result['dispositions']}
    for identity, decision in decisions.items():
        if not set(decision['evidence_ids']) <= set(task['visible_evidence_ids']):
            raise ValueError('Unknown disposition evidence')
        if identity in original and original[identity]['severity'] == 'critical' and decision['decision'] != 'unresolved' and not decision['evidence_ids']:
            raise ValueError('Resolving a critical objection requires cited evidence')
    issues = []
    for row in result['instruments']:
        symbol = row['symbol']; dimensions = row['dimensions']
        blocked = {d for g in result['gaps'] if g['critical'] and symbol in g['symbols'] for d in g['dimensions']}
        for identity, objection in original.items():
            if (objection['severity'] == 'critical' and symbol in objection['symbols'] and
                    decisions.get(identity, {}).get('decision', 'unresolved') == 'unresolved'):
                blocked.update(objection['dimensions'])
        for source in state['mandate']['sources']:
            if source['critical'] and (not source['symbols'] or symbol in source['symbols']) and source['source_id'] not in state['source_cache']:
                blocked.update(source['supports_dimensions'])
        partial = set()
        for requirement in state.get('source_readiness', {}).get('requirements', []):
            if symbol in requirement['symbols']:
                if requirement['status'] in {'MISSING', 'STALE'}:
                    blocked.update(requirement['dimensions'])
                elif requirement['status'] == 'PARTIAL':
                    partial.update(requirement['dimensions'])
        visited, active = set(), set()
        def visit(name):
            if name in active:
                raise ValueError('Conclusion dependencies must be acyclic')
            if name in visited:
                return
            active.add(name)
            for dependency in dimensions[name]['depends_on']:
                visit(dependency)
                if dependency in blocked:
                    blocked.add(name)
                if dependency in partial:
                    partial.add(name)
            active.remove(name); visited.add(name)
        for name in DIMENSIONS:
            visit(name)
        for name, assessment in dimensions.items():
            ids = set(assessment['claim_ids'])
            if not ids <= set(row['claim_ids']) or any(name not in claims[i]['dimensions'] for i in ids):
                missing = sorted(ids-set(row['claim_ids']))
                mismatched = sorted(i for i in ids if i in claims and name not in claims[i]['dimensions'])
                issues.append(f'Conclusion claims require matching instrument and dimension scope: {symbol}/{name}; missing instrument claim_ids={missing}; incompatible dimension claim_ids={mismatched}')
            status = assessment['status']
            if status != 'insufficient_evidence' and not ids:
                issues.append('Supported or conditional conclusion requires claims')
            if name in blocked and status != 'insufficient_evidence':
                issues.append(f'Unresolved dependency blocks {symbol} {name}, not unrelated conclusions')
            if name in partial and status == 'supported':
                issues.append(f'Partial source coverage permits only conditional {symbol} {name}')
            for dependency in assessment['depends_on']:
                dependency_status = dimensions[dependency]['status']
                if dependency_status == 'insufficient_evidence' and status != 'insufficient_evidence':
                    issues.append(f'Unsupported conclusion dependency cannot support another conclusion: {symbol}/{name} depends on {dependency}')
                if dependency_status == 'conditional' and status == 'supported':
                    issues.append(f'Conditional dependencies cannot become unconditional conclusions: {symbol}/{name} depends on {dependency}')
        preference = dimensions['relative_preference']
        if not {'business', 'valuation', 'market_behavior'} <= set(preference['depends_on']):
            issues.append('Relative preference requires business, valuation and market dependencies')
        if preference['status'] == 'insufficient_evidence' and row['assessment'] != 'insufficient_evidence':
            issues.append(f'Directional assessment requires an eligible relative preference: {symbol}')
    if issues:
        raise ValueError('; '.join(dict.fromkeys(issues)))


def dimension_lines(row):
    lines = []
    for name, value in row.get('dimensions', {}).items():
        lines += ['', f"{name.replace('_', ' ').title()} — {value['status']}", value['conclusion'],
                  'Qualification: ' + value['qualification']]
    return lines
