"""Live report clocks, market observations and completeness checks."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from spy_predictor_quant.market_archive import utc_now


def enabled(state):
    return state['mandate'].get('schema_version') == 'investment-research-mandate-v7'


def normalize_snapshot(payload, source, *, now=None):
    now = now or datetime.now(timezone.utc)
    symbol = source['symbols'][0]
    if payload.get('symbol') != symbol:
        raise ValueError('Snapshot symbol mismatch')
    feed = source['feed']
    if feed not in {'iex', 'sip'}:
        raise ValueError('Unsupported snapshot feed')
    def observation(item, fields):
        if not item:
            return None
        stamp = datetime.fromisoformat(item['t'].replace('Z', '+00:00'))
        if stamp.tzinfo is None or stamp > now:
            raise ValueError('Snapshot has a future or timezone-free market time')
        values = {}
        for name, key in fields.items():
            try:
                value = Decimal(str(item[key]))
            except (InvalidOperation, KeyError):
                raise ValueError('Invalid snapshot value') from None
            if not value.is_finite() or value <= 0:
                return None  # No valid two-sided market; never treat zero as a quote.
            values[name] = str(value)
        return {'observed_at': stamp.isoformat(), **values}
    quote = observation(payload.get('latestQuote'), {'bid': 'bp', 'ask': 'ap'})
    if quote and Decimal(quote['ask']) < Decimal(quote['bid']):
        raise ValueError('Crossed snapshot quote')
    return {'symbol': symbol, 'feed': feed, 'coverage': 'consolidated' if feed == 'sip' else 'single_venue',
            'latest_trade': observation(payload.get('latestTrade'), {'price': 'p'}), 'latest_quote': quote,
            'minute_bar': observation(payload.get('minuteBar'), {'close': 'c'}),
            'qualification': ('IEX venue observations do not represent all exchanges or an executable consolidated quote.'
                              if feed == 'iex' else 'Consolidated feed observation; age and market state still govern freshness.')}


def as_of_record(store, state, *, now=None):
    from .publication import market_status
    now = now or datetime.now(timezone.utc)
    policy = state['mandate']['analysis_policy']
    market = market_status(now)
    stocks = []
    for watch in state['mandate']['watchlist']:
        symbol = watch['symbol']
        identity = state['source_cache'].get('snapshot-'+symbol)
        evidence = store.get('evidence', identity) if identity else {}
        data = evidence.get('data') or {}
        quote = data.get('latest_quote')
        age = (now-datetime.fromisoformat(quote['observed_at'])).total_seconds() if quote else None
        status = ('unavailable' if not quote else 'market_closed' if market['status'] != 'OPEN' else
                  'stale' if age > policy['maximum_quote_age_seconds'] else
                  'partial_coverage' if data['coverage'] != 'consolidated' else 'fresh_consolidated')
        price_id = state['source_cache'].get('price-'+symbol)
        price = store.get('evidence', price_id).get('data') if price_id else None
        stocks.append({'symbol': symbol, 'snapshot_evidence_id': identity, 'captured_at': evidence.get('retrieved_at'),
                       'quote_status': status, 'quote_age_seconds': age, 'snapshot': data or None,
                       'completed_close': {'price': price['latest_close'], 'date': price['price_date'], 'evidence_id': price_id} if price else None})
    return {'requested_at': policy['requested_at'], 'assessed_at': now.isoformat(), 'market': market,
            'stocks': stocks, 'news_changes_since_specialists': state.get('live_news_changes', []),
            'qualification': 'Assessment time is the report clock. Every price, quote, filing and macro observation keeps its own source time; they are not simultaneous. No executable order recommendation is implied.'}


def refresh_snapshots(store, state, stage):
    from .broker import Broker
    if not enabled(state):
        return
    broker = Broker(store, state)
    result = {'stage': stage, 'started_at': utc_now(), 'sources': {}}
    source_ids = ['snapshot-'+w['symbol'] for w in state['mandate']['watchlist']]
    if stage == 'before_final':
        source_ids += [s['source_id'] for s in state['mandate']['sources']
                       if s['source_id'].startswith('sec-submissions-') or s['source_id'].endswith('-feed')]
    for source_id in source_ids:
        old_id = state['source_cache'].get(source_id)
        state['source_cache'].pop(source_id, None)
        state['source_failures'].pop(source_id, None)
        fetched = broker.call('read_source', {'source_id': source_id})
        result['sources'][source_id] = {'status': fetched['status'], 'evidence_id': fetched.get('evidence_id')}
        if old_id and not source_id.startswith('snapshot-') and fetched['status'] == 'OK':
            old = store.get('evidence', old_id)
            if old.get('content_sha256') != fetched.get('content_sha256'):
                state.setdefault('live_news_changes', []).append({'source_id': source_id, 'evidence_ids': [old_id, fetched['evidence_id']],
                    'qualification': 'Registered event source changed since specialist analysis; final synthesis must review relevance or keep the affected view provisional.'})
        elif not source_id.startswith('snapshot-') and fetched['status'] != 'OK':
            state.setdefault('live_news_changes', []).append({'source_id': source_id, 'evidence_ids': [old_id] if old_id else [],
                'qualification': 'Final event refresh unavailable; source freshness cannot be confirmed. Keep affected present-time conclusions qualified.'})
    result['completed_at'] = utc_now()
    state.setdefault('live_refreshes', []).append(result)
    store.event(state, 'LIVE_SNAPSHOT_REFRESHED', stage=stage)


def validate_report(state, task, findings):
    if not enabled(state):
        return
    if task['stage'] not in {'draft', 'final'}:
        return
    visible = set(task['visible_evidence_ids'])
    for row in findings['instruments']:
        analysis = row['global_analysis']
        outcomes = analysis['conditional_outcomes']
        if {r['case'] for r in outcomes} != {'bear', 'base', 'bull'}:
            raise ValueError('Global assessment requires distinct bear/base/bull outcomes')
        for item in analysis['global_forces'] + outcomes:
            if not set(item['evidence_ids']) <= visible:
                raise ValueError('Global assessment references unknown or unread evidence')
        if not row['review_conditions']:
            raise ValueError('Global assessment requires concrete view-change conditions')
    if task['stage'] == 'final':
        completed = {t['role'] for t in state['tasks'] if t['status'] == 'COMPLETE'}
        if not {'company', 'macro', 'technical', 'geopolitics', 'commodities', 'challenger'} <= completed:
            raise ValueError('Live assessment requires accepted findings from every specialist and Challenger')
        validate_final_citations(state, findings)


def validate_final_citations(state, findings):
    """Keep final global citations within reviewed content and scoped corrections.

    This checks review coverage, not whether prose correctly interprets a source.
    Same-source news refreshes remain usable with the existing freshness limits.
    """
    drafts = [t for t in state['tasks'] if t['role'] == 'director'
              and t['stage'] == 'draft' and t['status'] == 'COMPLETE' and t.get('result')]
    reviews = [t for t in state['tasks'] if t['role'] == 'challenger'
               and t['stage'] == 'review' and t['status'] == 'COMPLETE' and t.get('result')]
    if not drafts or not reviews:
        raise ValueError('Final global assessment requires a completed draft and Challenger review')
    draft, review = drafts[-1]['result'], reviews[-1]['result']
    changed = {d['objection_id'] for d in findings['dispositions'] if d['decision'] == 'changed'}
    corrected_symbols = {symbol for objection in review['objections']
                         if objection['objection_id'] in changed for symbol in objection['symbols']}
    for row in findings['instruments']:
        symbol = row['symbol']
        prior = next((r for r in draft['instruments'] if r['symbol'] == symbol), None)
        if prior is None:
            raise ValueError('Final stock is absent from reviewed draft: ' + symbol)
        analysis = prior['global_analysis']
        allowed = {identity for item in analysis['global_forces'] + analysis['conditional_outcomes']
                   for identity in item['evidence_ids']}
        allowed.update(identity for claim in draft['claims'] if symbol in claim['symbols']
                       for identity in claim['evidence_ids'])
        if symbol in corrected_symbols:
            allowed.update(identity for claim in review['claims'] if symbol in claim['symbols']
                           for identity in claim['evidence_ids'])
        for change in state.get('live_news_changes', []):
            identities = change['evidence_ids']
            if len(identities) == 2 and identities[0] in allowed:
                allowed.add(identities[1])
        for item in row['global_analysis']['global_forces'] + row['global_analysis']['conditional_outcomes']:
            added = set(item['evidence_ids']) - allowed
            if added:
                raise ValueError('Final global citation was not covered by the reviewed draft or a scoped '
                                 'Challenger correction: ' + symbol + ': ' + ', '.join(sorted(added))
                                 + '. Preserve reviewed content; include new analysis in a reviewed draft.')


def global_lines(row):
    analysis = row.get('global_analysis')
    if not analysis:
        return []
    lines = ['', '### Overall assessment', '', analysis['overall_assessment'], '', '### Global forces', '']
    lines += [f"- {r['force']}: {r['mechanism']} Consequence: {r['consequence']} (evidence: {', '.join(r['evidence_ids'])})" for r in analysis['global_forces']]
    lines += ['', '### Conditional outcomes', '']
    lines += [f"- {r['case']}: If {r['condition']} → {r['consequence']} Plausibility: {r['plausibility_basis']} (evidence: {', '.join(r['evidence_ids'])})" for r in analysis['conditional_outcomes']]
    return lines + ['', '### What to consider', '', analysis['recommend_considering'], '', '### Short summary', '', analysis['short_summary']]
