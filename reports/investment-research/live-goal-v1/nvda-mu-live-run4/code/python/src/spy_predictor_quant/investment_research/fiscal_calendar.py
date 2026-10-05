"""Derive current annual boundaries from disclosed 52/53 weeks, never guessed dates."""
from datetime import date, timedelta
import re


def derive(text, periods):
    annuals = periods.get('annual', [])
    if not annuals:
        return None
    annual = max(annuals, key=lambda r: r['end'])
    start = date.fromisoformat(annual['end']) + timedelta(days=1)
    if not any(r['start'] == start.isoformat() for r in periods.get('interim', [])):
        return None  # A reported current-period start must corroborate continuity.
    normalized = ' '.join(text.split())
    pattern = r'Fiscal year (\d{4}) (?:is a|contains) (52|53)(?:-week| weeks)'
    candidates = []
    for match in re.finditer(pattern, normalized, re.I):
        year, weeks = map(int, match.groups())
        end = start + timedelta(days=7*weeks-1)
        if end.year == year:
            candidates.append({'fiscal_year': year, 'weeks': weeks, 'start': start.isoformat(),
                'end': end.isoformat(), 'statement': match.group(0), 'prior_annual_end': annual['end']})
    unique = {(r['fiscal_year'], r['weeks'], r['start'], r['end']): r for r in candidates}
    return next(iter(unique.values())) if len(unique) == 1 else None


def seed(broker):
    records = {i: broker.store.get('evidence', i) for i in broker.state['evidence_ids']}
    companies = [r['symbol'] for r in broker.state['mandate']['watchlist'] if r['kind'] == 'company']
    for symbol in companies:
        filings = [(i, e) for i, e in records.items() if e.get('document_id') and e.get('data') is None
                   and e.get('adapter') != 'document_section' and symbol in e.get('symbols', [])
                   and '/Archives/edgar/data/' in e.get('url', '')]
        facts = [(i, e) for i, e in records.items() if e.get('adapter') == 'sec_companyfacts' and symbol in e.get('symbols', [])]
        if not filings or not facts:
            continue
        identity, filing = max(filings, key=lambda pair: pair[1].get('published_at', ''))
        section = None
        for query in ('53-week', '53 weeks', '52-week', '52 weeks'):
            candidate = broker.call('inspect_evidence', {'evidence_id': identity, 'query': query, 'occurrence': 0})
            if candidate['status'] == 'OK':
                section = candidate
                break
        if section is None:
            continue
        facts_id, fact = facts[0]
        calendar = derive(section['excerpt'], (fact.get('data') or {}).get('earnings_periods', {}))
        if calendar:
            broker.record({'kind': 'fiscal_calendar', 'symbols': [symbol], 'symbol': symbol, **calendar,
                'input_evidence_ids': [facts_id, section['evidence_id']], 'source_published_at': filing['published_at'],
                'qualification': 'Current annual period derived from disclosed week count plus prior annual end, corroborated by reported interim start. No extrapolation to later fiscal years.'})
