"""Source-only input readiness; a fetched document is never semantic approval."""
from datetime import date, datetime, timezone
import json

from .dimensions import enabled


def acquire_sections(broker):
    state = broker.state
    if not enabled(state) or state.get('section_acquisition_complete'):
        return
    requirements = [r for r in state['mandate']['source_requirements'] if r['check'] == 'issuer_sections']
    for symbol in sorted({s for r in requirements for s in r['symbols']}):
        parents = {state['source_cache'].get(s) for r in requirements if symbol in r['symbols'] for s in r['source_ids']}
        sources = [s for s in state['discovered_sources'].values() if s.get('parent_evidence_id') in parents
                   and (' 10-Q ' in s['title'] or ' 10-K ' in s['title'])]
        for source in sorted(sources, key=lambda s: s.get('published_at') or '', reverse=True)[:2]:
            doc = broker.call('read_source', {'source_id': source['source_id']})
            if doc['status'] != 'OK':
                continue
            for requirement in requirements:
                if symbol not in requirement['symbols']:
                    continue
                # Take first and last occurrence: a contents listing cannot be the only view.
                first = broker.call('inspect_evidence', {'evidence_id': doc['evidence_id'], 'query': requirement['query']})
                if first['status'] == 'OK' and first['matches'] > 1:
                    broker.call('inspect_evidence', {'evidence_id': doc['evidence_id'], 'query': requirement['query'],
                                                   'occurrence': min(first['matches']-1, 1000)})
    state['section_acquisition_complete'] = True
    broker.store.save(state)


def source_readiness(store, state, *, at=None):
    at = at or datetime.now(timezone.utc)
    evidence = {i: store.get('evidence', i) for i in state['evidence_ids']}
    requirements = []
    for requirement in state['mandate'].get('source_requirements', []):
        candidates = {i: e for i, e in evidence.items() if i in
            {state['source_cache'].get(s) for s in requirement['source_ids']}}
        if requirement['check'] == 'issuer_sections':
            parent_ids = set(candidates)
            # Refresh creates a new evidence identity even when the submissions
            # bytes are unchanged. Preserve sections only for that same source
            # and content, never for an older, changed filing index.
            current = {(e.get('source_id'), e.get('content_sha256')) for e in candidates.values()
                       if e.get('content_sha256')}
            parent_ids.update(i for i, e in evidence.items()
                              if (e.get('source_id'), e.get('content_sha256')) in current)
            document_ids = {i for i, e in evidence.items() if e.get('parent_evidence_id') in parent_ids}
            candidates = {i: e for i, e in evidence.items() if e.get('adapter') == 'document_section'
                          and e.get('query') == requirement['query'] and e.get('parent_evidence_id') in document_ids
                          and set(requirement['symbols']) <= set(e.get('symbols', []))}
        status, explanation, ids, observed_dates = 'MISSING', 'Required usable fields not retrieved.', [], []
        for identity, e in candidates.items():
            data = e.get('data') or {}; method = requirement['check']; observed = None
            candidate_status, note = 'MISSING', 'Required usable fields not retrieved.'
            if method == 'annual_eps' and e.get('adapter') == 'sec_companyfacts':
                annual = data.get('earnings_periods', {}).get('annual', [])
                if annual:
                    observed = annual[0]['end']; candidate_status = 'READY'
                    note = 'Dated annual diluted EPS anchor; no forward consensus or automatic share-basis match.'
            elif method == 'completed_price' and e.get('adapter') == 'alpaca_daily' and data.get('latest_close', 0) > 0:
                observed = data.get('price_date'); candidate_status = 'READY' if data.get('status') == 'FRESH' else 'STALE'
                note = 'Completed-session close and descriptive metrics; not an executable quote.'
            elif method == 'operating_data' and e.get('adapter') == 'sec_companyfacts':
                metric = data.get('metrics', {}).get('revenue')
                if metric:
                    observed = metric['end']; candidate_status = 'READY'
                    note = 'Period-qualified issuer revenue available; demand attribution requires cited disclosure.'
            elif method == 'holdings' and e.get('adapter') == 'etf_holdings':
                observed = data.get('as_of')
                candidate_status = 'READY' if data.get('holdings_count', 0) >= 90 and data.get('reported_weight_pct', 0) >= 95 else 'PARTIAL'
                note = 'Dated equity weights, measured coverage and excluded positions; no renormalization or portfolio-weight inference.'
            elif method == 'etf_valuation' and e.get('adapter') == 'etf_profile':
                if data.get('metrics', {}).get('pe_ratio') is not None:
                    observed = data.get('metric_as_of', {}).get('pe_ratio', data.get('as_of'))
                    candidate_status = 'READY'; note = 'Dated sponsor aggregate P/E only; corporate versus fund methodology must be qualified.'
            elif method == 'issuer_sections' and len(e.get('excerpt', '')) >= 500:
                observed = (e.get('published_at') or '')[:10] or None
                candidate_status = 'PARTIAL'; note = 'Located filing excerpt for substantive review; keyword presence does not verify a quantified exposure.'
            elif method == 'policy_document' and e.get('adapter') == 'document' and len(e.get('excerpt', '')) >= 1000:
                observed = (e.get('published_at') or '')[:10] or None
                candidate_status = 'PARTIAL'; note = 'Dated primary policy text retrieved; subsequent amendments and company applicability not certified.'
            if candidate_status != 'MISSING' and not observed:
                candidate_status = 'MISSING'; note = 'Observation date missing; retrieval time cannot substitute.'
            if observed:
                age = (at.date()-date.fromisoformat(observed)).days
                if age < 0 or age > requirement['maximum_age_days']:
                    candidate_status = 'STALE'; note = 'Observation outside the registered age window; retrieval does not refresh its date.'
            if candidate_status != 'MISSING':
                ids.append(identity)
                if observed:
                    observed_dates.append(observed)
            if {'MISSING': 0, 'STALE': 1, 'PARTIAL': 2, 'READY': 3}[candidate_status] > {'MISSING': 0, 'STALE': 1, 'PARTIAL': 2, 'READY': 3}[status]:
                status, explanation = candidate_status, note
        requirements.append({**requirement, 'status': status, 'evidence_ids': ids,
            'observed_dates': sorted(set(observed_dates)), 'explanation': explanation})
    blocked = [r['requirement_id'] for r in requirements if r['required_for_run'] and r['status'] != 'READY']
    return {'version': 'source-readiness-v1', 'checked_at': at.isoformat(),
        'status': 'BLOCKED' if blocked else 'READY_WITH_GAPS' if any(r['status'] != 'READY' for r in requirements) else 'READY',
        'blocked_requirements': blocked, 'requirements': requirements,
        'qualification': 'Checks input usability, dates and coverage. Semantic source interpretation and investment usefulness remain separate.'}


def checkpoint(store, state):
    if not enabled(state):
        return
    result = source_readiness(store, state)
    state['source_readiness'] = result
    store.event(state, 'SOURCE_READINESS_CHECK', status=result['status'], blocked_requirements=result['blocked_requirements'])
    (store.root/'source-readiness.json').write_text(json.dumps(result, indent=2)+'\n')
    lines = ['# Source readiness', '', result['status'], '', result['qualification'], '',
             '| Requirement | Symbols | Conclusions | Status | Observed dates |', '|---|---|---|---|---|']
    for r in result['requirements']:
        lines.append(f"| {r['requirement_id']} | {', '.join(r['symbols'])} | {', '.join(r['dimensions'])} | {r['status']} | {', '.join(r['observed_dates']) or 'unknown'} |")
    for r in result['requirements']:
        lines += ['', f"## {r['requirement_id']}", r['explanation'], 'Evidence: '+', '.join(r['evidence_ids'])]
    (store.root/'source-readiness.md').write_text('\n'.join(lines)+'\n')
    if result['blocked_requirements']:
        raise ValueError('Source readiness blocked: '+', '.join(result['blocked_requirements']))
