"""Period-qualified SEC EPS observations for research, without annualization.

Keep this separate from the legacy single-value fundamentals selector. An annual
observation is a historical anchor, not forward consensus or a verified price
share-basis match. Do not manufacture TTM EPS by adding per-share observations.
"""
from datetime import date, datetime, time, timezone
import math


def earnings_periods(payload, filings, cutoff):
    if str(payload.get('cik', '')).zfill(10) != filings['cik']:
        raise ValueError('SEC earnings issuer mismatch')
    accessions = {r['accessionNumber'] for r in filings['periodic']}
    observations = payload.get('facts', {}).get('us-gaap', {}).get(
        'EarningsPerShareDiluted', {}).get('units', {}).get('USD/shares', [])
    selected = {}
    for row in observations:
        if row.get('accn') not in accessions or row.get('form') not in {'10-K', '10-K/A', '10-Q', '10-Q/A'}:
            continue
        try:
            start, end, filed = (date.fromisoformat(row[k]) for k in ('start', 'end', 'filed'))
        except (KeyError, TypeError, ValueError):
            continue
        value = row.get('val')
        if (datetime.combine(filed, time.max, timezone.utc) > cutoff or end > cutoff.date()
                or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
            continue
        days = (end-start).days+1
        if not 60 <= days <= 380:
            continue
        annual = 350 <= days <= 380 and row['form'] in {'10-K', '10-K/A'}
        key = (row['start'], row['end'])
        candidate = {'value': value, 'unit': 'USD/shares', 'concept': 'EarningsPerShareDiluted',
            'start': row['start'], 'end': row['end'], 'duration_days': days,
            'period_kind': 'annual' if annual else 'interim', 'accounting_basis': 'US_GAAP',
            'share_basis': 'diluted_as_reported_in_accession', 'filed': row['filed'],
            'accession': row['accn'], 'form': row['form']}
        if key not in selected or (candidate['filed'], candidate['accession']) > (selected[key]['filed'], selected[key]['accession']):
            selected[key] = candidate
    rows = sorted(selected.values(), key=lambda r: (r['end'], r['duration_days']), reverse=True)
    return {'annual': [r for r in rows if r['period_kind'] == 'annual'][:3],
            'interim': [r for r in rows if r['period_kind'] == 'interim'][:8],
            'qualification': 'Historical reported EPS; no consensus, annualization or TTM construction. '
                'Verify corporate actions/share basis before combining with a market price.'}
