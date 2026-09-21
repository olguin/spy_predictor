"""One bounded refresh, conservative dependency withdrawal, immutable publication."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import html
import json
from pathlib import Path
import shutil
import uuid

from spy_predictor_quant.market_archive import content_hash, utc_now
from .broker import Broker, LimitReached, remaining_seconds
from .controller import source_identity
from .observations import calendar, positive, schedule, timestamp
from .rendering import condition_line, numerical_lines
from .store import Store


def market_status(at):
    cal = calendar(at)
    opened = [s for s in cal.sessions if cal.session_open(s).to_pydatetime() <= at]
    session = opened[-1]
    closed = [s for s in cal.sessions if cal.session_close(s).to_pydatetime() <= at]
    return {'status': 'OPEN' if at < cal.session_close(session).to_pydatetime() else 'CLOSED',
            'latest_completed_session': closed[-1].date().isoformat()}


def condition_state(condition, evidence, at):
    if condition['kind'] == 'human_review':
        return {'status': 'HUMAN_REVIEW', 'condition': condition}
    if timestamp(condition['expires_at']) <= at:
        return {'status': 'EXPIRED', 'condition': condition}
    data = (evidence or {}).get('data') or {}
    if (data.get('price_date') != market_status(at)['latest_completed_session'] or
            data.get('adjustment') != condition['price_basis'] or data.get('latest_close') is None):
        return {'status': 'UNAVAILABLE', 'reason': 'Stale close, missing price or incompatible share basis', 'condition': condition}
    price, threshold = positive(data['latest_close']), positive(condition['threshold_decimal'])
    operations = {'above': price > threshold, 'below': price < threshold,
        'at_or_above': price >= threshold, 'at_or_below': price <= threshold,
        'gt': price > threshold, 'gte': price >= threshold, 'lt': price < threshold, 'lte': price <= threshold}
    if condition['operator'] not in operations:
        raise ValueError('Unsupported condition comparator')
    return {'status': 'MET' if operations[condition['operator']] else 'NOT_MET', 'condition': condition,
            'price_decimal': str(price), 'price_date': data['price_date'], 'qualification': 'Completed-close review only; no intraday trigger or fill asserted'}


def qualify_quote(quote, at, maximum_age_seconds):
    """A dated daily close can never qualify as a contemporaneous quote."""
    if not quote or quote.get('kind') != 'quote':
        return {'status': 'UNAVAILABLE', 'reason': 'No contemporaneous quote; daily closes are not executable quotes'}
    age = (at-timestamp(quote['observed_at'])).total_seconds()
    if age < 0 or age > maximum_age_seconds:
        return {'status': 'STALE', 'reason': 'Quote timestamp outside freshness window', 'age_seconds': age}
    if market_status(at)['status'] != 'OPEN':
        return {'status': 'MARKET_CLOSED', 'reason': 'Regular session is closed'}
    if quote.get('delayed') is not False or quote.get('coverage') != 'consolidated':
        return {'status': 'UNAVAILABLE', 'reason': 'Delayed or partial-venue coverage'}
    if positive(quote['ask_decimal']) < positive(quote['bid_decimal']):
        raise ValueError('Crossed quote')
    return {'status': 'FRESH_REFERENCE', 'observed_at': quote['observed_at'], 'age_seconds': age,
            'qualification': 'Reference quote only; no order or fill assertion'}


def invalidate(store, product, changed_ids, changed_symbols):
    """Propagate through calculations, claims and scoped thesis dependencies."""
    affected = set(changed_ids)
    while True:
        previous = set(affected)
        for identity in product['evidence_ids']:
            evidence = store.get('evidence', identity)
            refs = set(evidence.get('evidence_ids', [])) | set(evidence.get('input_evidence_ids', []))
            refs.add(evidence.get('parent_evidence_id'))
            refs.update(r.get('evidence_id') for r in evidence.get('input_refs', []) if isinstance(r, dict))
            if refs & affected:
                affected.add(identity)
        if previous == affected:
            break
    claims = [c['claim_id'] for c in product['findings']['claims'] if set(c['evidence_ids']) & affected]
    symbols = set(changed_symbols)
    for row in product['findings']['instruments']:
        if set(row['claim_ids']) & set(claims):
            symbols.add(row['symbol'])
    return {'evidence_ids': sorted(affected), 'claim_ids': claims, 'symbols': sorted(symbols)}


def refresh(store, state):
    policy = state['mandate']['publication_policy']
    if state.get('publication_refresh'):
        raise ValueError('Final refresh already attempted; no automatic second cycle')
    state['publication_refresh'] = {'started_at': utc_now(), 'policy': policy, 'results': {}, 'status': 'STARTED'}
    state.update(phase='publication', status='RUNNING')
    state.pop('completed_at', None)
    store.event(state, 'PUBLICATION_REFRESH_STARTED')
    broker = Broker(store, state)
    old_cache = dict(state['source_cache'])
    changed, symbols, latest_prices = set(), set(), {}
    coverage = []
    product = store.get('products', state['product_id'])
    for source_id in policy['refresh_source_ids']:
        state['source_cache'].pop(source_id, None)
        state['source_failures'].pop(source_id, None)
        result = broker.call('read_source', {'source_id': source_id})
        state['publication_refresh']['results'][source_id] = result.get('evidence_id')
        source = next(s for s in state['mandate']['sources'] if s['source_id'] == source_id)
        scope = source['symbols'] or product['symbols']
        old_id = old_cache.get(source_id)
        old = store.get('evidence', old_id) if old_id else None
        material = result['status'] != 'OK' or old is None
        reason = 'Missing refresh coverage' if result['status'] != 'OK' else 'Previously unavailable evidence'
        if result['status'] == 'OK':
            if source['adapter'] == 'alpaca_daily':
                latest_prices.update({s: result for s in scope})
                previous_price = (old or {}).get('data', {}).get('latest_close')
                new_price = (result.get('data') or {}).get('latest_close')
                if previous_price is not None and new_price is not None:
                    move = abs((positive(new_price)/positive(previous_price)-1)*100)
                    material |= move >= Decimal(str(policy['material_price_move_pct']))
                    material |= old['data'].get('adjustment') != result['data'].get('adjustment')
                    reason = f'Price move {move}% or changed share basis'
            else:
                material |= old is not None and old['content_sha256'] != result['content_sha256']
                reason = 'Changed event/source content; relevance requires review'
        if material:
            if old_id:
                changed.add(old_id)
            symbols.update(scope)
            symbols.update(row['symbol'] for row in state['mandate']['watchlist']
                           if row['benchmark'] in scope or row['sector_benchmark'] in scope)
        coverage.append({'source_id': source_id, 'symbols': scope, 'status': result['status'],
                         'old_evidence_id': old_id, 'new_evidence_id': result.get('evidence_id'),
                         'material_change': material, 'reason': reason if material else 'No policy-material change detected'})
        store.event(state, 'PUBLICATION_SOURCE_REFRESHED', source_id=source_id, status=result['status'], material_change=material)
    at = datetime.now(timezone.utc)
    # Recompute the deterministic comparison panel over refreshed caches. Other
    # dependent calculations are explicitly invalidated, never LLM-repaired.
    from .panels import seed_panels
    seed_panels(broker)
    conditions = {}
    for row in product['findings']['instruments']:
        symbol = row['symbol']
        conditions[symbol] = [condition_state(c, latest_prices.get(symbol), at) for c in row['review_conditions']]
        for current in conditions[symbol]:
            c = current['condition']
            prior_price = next((store.get('evidence', i) for i in c.get('evidence_ids', []) if (store.get('evidence', i).get('data') or {}).get('symbol') == symbol), None)
            prior = condition_state(c, prior_price, at)
            if current['status'] in {'EXPIRED', 'UNAVAILABLE'} or prior['status'] != current['status']:
                symbols.add(symbol)
    affected = invalidate(store, product, changed, symbols)
    state['publication_refresh'].update(status='COMPLETE', completed_at=utc_now(), coverage=coverage,
        conditions=conditions, invalidation=affected, latest_prices={s: e['evidence_id'] for s, e in latest_prices.items()})
    store.event(state, 'PUBLICATION_DEPENDENCIES_INVALIDATED', **affected)
    return state['publication_refresh']


def report(store, product, refresh_record, published_at):
    lines = ['# Investment research', '', f'Published: {published_at}', '',
        'SYNTHETIC ENGINEERING FIXTURE — not live research' if product['mode'] == 'fixture' else 'Dated investment research; no execution instructions.', '',
        '| Instrument | Published assessment | Refresh |', '|---|---|---|']
    affected = set(refresh_record['invalidation']['symbols'])
    for row in product['findings']['instruments']:
        lines.append(f"| {row['symbol']} | {row['assessment']} | {'Affected guidance withdrawn' if row['symbol'] in affected else 'No material change detected within coverage'} |")
    for row in product['findings']['instruments']:
        lines += ['', f"## {row['symbol']} — {row['assessment']}", '', row['thesis'], '',
                  'Counter-case: ' + row['counter_thesis'], '', 'Valuation: ' + row['valuation'], '', 'Assumptions:']
        lines += ['- ' + a for a in row['assumptions']]
        lines += ['', 'Review conditions:'] + [condition_line(store, c) for c in row['review_conditions']]
        for condition in refresh_record['conditions'][row['symbol']]:
            lines.append('- Refresh condition state: ' + condition['status'])
        lines += ['', 'Immediate-entry quote: unavailable. Daily closes are dated trend evidence, never executable quotes.']
        for claim in product['findings']['claims']:
            if claim['claim_id'] in row['claim_ids']:
                lines.append(f"- {claim['classification']}: {claim['text']} ({', '.join(claim['evidence_ids'])})")
    lines += ['', '## Coverage', '', json.dumps(refresh_record['coverage'], indent=2), '', '## Limitations', '']
    lines += ['- ' + text for text in product['limitations']]
    lines += numerical_lines(store, product['evidence_ids'])
    return '\n'.join(lines) + '\n'


def publish(store, ledger_root, *, parent_publication_id=None):
    """Manual command. No caller-supplied publication time and no retry after failure."""
    ledger = Store(ledger_root)
    with store.lock(), ledger.lock():
        state = store.load()
        if state.get('publication_id'):
            return read_publication(ledger_root, state['publication_id'])
        if state['status'] != 'DRAFT' or not state['mandate'].get('publication_policy'):
            raise ValueError('Requires an unpublished draft with a pre-registered M3 publication policy')
        if content_hash(state['mandate']) != state['mandate_hash'] or source_identity() != state['source_identity']:
            raise ValueError('Mandate/runtime identity changed; create a new research run')
        if state['usage_unknown']:
            raise ValueError('Unknown usage blocks publication admission')
        parent = read_publication(ledger_root, parent_publication_id) if parent_publication_id else None
        product = deepcopy(store.get('products', state['product_id']))
        if parent and parent['product']['symbols'] != product['symbols']:
            raise ValueError('Review version must preserve instrument identities')
        try:
            remaining_seconds(state)
            refresh_record = refresh(store, state)
            remaining_seconds(state)
            affected = set(refresh_record['invalidation']['symbols'])
            product['invalidated_original_findings'] = deepcopy(product['findings']) if affected else None
            invalid_claims = set(refresh_record['invalidation']['claim_ids'])
            product['findings']['claims'] = [c for c in product['findings']['claims'] if c['claim_id'] not in invalid_claims]
            for row in product['findings']['instruments']:
                if row['symbol'] in affected:
                    row.update(assessment='insufficient_evidence', thesis='Affected guidance withdrawn after final refresh; a new research review is required.',
                               valuation='Prior valuation conclusions require review against refreshed evidence.', claim_ids=[])
            product.update(schema_version='investment-research-publication-product-v1', publication_status='PUBLISHED', status='PUBLISHED',
                mode=state['mandate']['mode'], evidence_ids=state['evidence_ids'][:],
                evidence_cutoff=refresh_record['completed_at'], parent_publication_id=parent_publication_id)
            product['market_context'] = deepcopy(state['market_context'])
            product['limitations'] = [s for s in product['limitations'] if not s.startswith('Unpublished research;')]
            product['limitations'] += ['Final refresh is limited to registered sources; it does not certify all world news.',
                'One refresh cycle only; materially affected guidance is withdrawn, never silently repaired.',
                'Unconditional delayed research observations are separate from conditional opportunity performance.']
            # Assemble the bundle before stamping publication. Staging is never served as a publication.
            publication_id = str(uuid.uuid4())
            staging = ledger_root / ('.pending-' + publication_id)
            staging.mkdir()
            for kind in ('evidence', 'documents', 'manifests', 'requests', 'responses', 'products', 'code'):
                if (store.root / kind).exists():
                    shutil.copytree(store.root / kind, staging / kind, copy_function=shutil.copyfile)
            # Hash the large archived files before publication time, not after it.
            hashes = {str(p.relative_to(staging)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(staging.rglob('*')) if p.is_file()}
            at = datetime.now(timezone.utc)
            if (at-timestamp(refresh_record['completed_at'])).total_seconds() > state['mandate']['publication_policy']['maximum_refresh_age_seconds']:
                raise ValueError('Refresh expired before publication')
            for rows in refresh_record['conditions'].values():
                if any(c['condition'].get('expires_at') and timestamp(c['condition']['expires_at']) <= at and c['status'] != 'EXPIRED' for c in rows):
                    raise ValueError('Condition expired while freezing publication')
            remaining_seconds(state)
            published_at = at.isoformat()
            contract = schedule(published_at, state['mandate']['watchlist'], state['mandate']['horizon_sessions'])
            cal = calendar(at)
            product.update(published_at=published_at, observation_contract=contract,
                price_observed_at={s: cal.session_close(store.get('evidence', i)['data']['price_date']).isoformat() for s, i in refresh_record['latest_prices'].items()},
                price_freshness={s: {'status': store.get('evidence', i)['data']['status'], 'feed': store.get('evidence', i)['data']['feed'],
                    'share_basis': store.get('evidence', i)['data']['adjustment'], 'kind': 'completed_daily_close', 'executable': False} for s, i in refresh_record['latest_prices'].items()},
                market_status=market_status(at), immediate_entry_quote='UNAVAILABLE: daily-close sources only')
            product['quote_freshness'] = qualify_quote(None, at, state['mandate']['publication_policy']['maximum_quote_age_seconds'])
            text = report(store, product, refresh_record, published_at)
            (staging / 'report.md').write_text(text)
            (staging / 'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Published research</title><body><pre>' + html.escape(text) + '</pre></body></html>')
            record = {'schema_version': 'investment-research-publication-v1', 'publication_id': publication_id,
                'published_at': published_at, 'parent_publication_id': parent_publication_id, 'run_id': state['run_id'],
                'draft_product_id': state['product_id'], 'product': product, 'refresh': refresh_record,
                'usage': deepcopy(state['usage']), 'usage_unknown': state['usage_unknown'],
                'observation_contract': contract, 'runtime_identity': state['source_identity']}
            (staging / 'publication.json').write_text(json.dumps(record, indent=2, allow_nan=False)+'\n')
            state.update(status='PUBLISHED', completed_at=published_at, publication_id=publication_id)
            # Freeze the same totals/tasks/attempts visible in the monitor.
            state['events'].append({'at': published_at, 'kind': 'PUBLICATION_COMPLETED', 'publication_id': publication_id,
                                    'sequence': len(state['events'])+1})
            state['event_sequence'] = len(state['events'])
            state['updated_at'] = published_at
            (staging / 'state.json').write_text(json.dumps(state, indent=2, allow_nan=False)+'\n')
            for filename in ('publication.json', 'report.md', 'report.html', 'state.json'):
                hashes[filename] = hashlib.sha256((staging / filename).read_bytes()).hexdigest()
            (staging / 'bundle-manifest.json').write_text(json.dumps(hashes, indent=2)+'\n')
            bundles = ledger_root / 'publications'
            bundles.mkdir(exist_ok=True)
            staging.rename(bundles / publication_id)
            # Registration is content-addressed; linked reviews cannot replace prior versions.
            ledger.put('journal', {'kind': 'publication', 'publication_id': publication_id, 'published_at': published_at,
                'parent_publication_id': parent_publication_id, 'bundle_manifest_hash': content_hash(hashes),
                'theses': [{'symbol': r['symbol'], 'assessment': r['assessment'], 'thesis_id': content_hash({'publication_id': publication_id, 'symbol': r['symbol']})} for r in product['findings']['instruments']]})
            store.save(state)
            return record
        except (LimitReached, ValueError, OSError, KeyError, KeyboardInterrupt) as error:
            state.update(status='INCOMPLETE', completed_at=utc_now(), stop_reason='Publication stopped: '+type(error).__name__)
            store.event(state, 'PUBLICATION_STOPPED', reason=state['stop_reason'])
            raise


def read_publication(root, identity):
    if str(uuid.UUID(identity)) != identity:
        raise ValueError('Invalid publication identity')
    directory = root / 'publications' / identity
    hashes = json.loads((directory / 'bundle-manifest.json').read_text())
    ledger = Store(root)
    registrations = [ledger.get('journal', p.stem) for p in (root / 'journal').glob('*.json')]
    if not any(r.get('kind') == 'publication' and r.get('publication_id') == identity and
               r.get('bundle_manifest_hash') == content_hash(hashes) for r in registrations):
        raise ValueError('Publication bundle registration integrity mismatch')
    if not {'publication.json', 'state.json', 'report.md', 'report.html'} <= hashes.keys():
        raise ValueError('Publication manifest missing required artifacts')
    for path, digest in hashes.items():
        target = (directory / path).resolve()
        if not target.is_relative_to(directory.resolve()) or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError('Publication bundle integrity mismatch')
    return json.loads((directory / 'publication.json').read_text())


def feedback(root, publication_id, value):
    record = read_publication(root, publication_id)
    if value.get('category') not in {'claim', 'omission', 'confusing_explanation', 'changed_user_need', 'usefulness'}:
        raise ValueError('Unknown feedback category')
    if not isinstance(value.get('text'), str) or not value['text'].strip():
        raise ValueError('Feedback text required')
    if value.get('claim_id') and value['claim_id'] not in {c['claim_id'] for c in record['product']['findings']['claims']}:
        raise ValueError('Unknown published claim')
    if value.get('category') == 'claim' and not value.get('claim_id'):
        raise ValueError('Claim feedback requires a claim identity')
    if value.get('symbol') and value['symbol'] not in record['product']['symbols']:
        raise ValueError('Unknown feedback instrument')
    entry = {'schema_version': 'investment-research-feedback-v1', 'publication_id': publication_id,
             'recorded_at': utc_now(), 'feedback': value}
    identity = Store(root).put('feedback', entry)
    return {'feedback_id': identity, **entry}


def review(root, publication_id, value):
    record = read_publication(root, publication_id)
    if value.get('decision') not in {'retain', 'needs_research', 'withdraw'} or not value.get('reason'):
        raise ValueError('Review requires a decision and reason')
    if value.get('symbol') not in record['product']['symbols']:
        raise ValueError('Review requires a published instrument')
    entry = {'schema_version': 'investment-research-manual-review-v1', 'publication_id': publication_id,
             'review_id': str(uuid.uuid4()), 'recorded_at': utc_now(), 'review': value,
             'qualification': 'Linked review; original assessment and observation contract remain frozen. New research publishes a child version.'}
    return {'journal_id': Store(root).put('journal', entry), **entry}
