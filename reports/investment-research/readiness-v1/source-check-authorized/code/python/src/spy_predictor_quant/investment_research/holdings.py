"""Normalize the sponsor's public JSON without hiding non-equity positions."""
import csv
from datetime import date
import io
import json
import math
from urllib.parse import urlsplit

from spy_predictor_quant.meta_evidence import parse_holdings_csv


def invesco_holdings(raw, source, symbol, cutoff):
    url = urlsplit(source['url'])
    if url.hostname != 'dng-api.invesco.com' or f'/shareclasses/{symbol}/holdings/fund' != url.path[-len(f'/shareclasses/{symbol}/holdings/fund'):]:
        raise ValueError('Unverified sponsor holdings endpoint')
    payload = json.loads(raw)
    if payload.get('cusip') != symbol:
        raise ValueError('Sponsor holdings fund identity mismatch')
    as_of = date.fromisoformat(payload['effectiveBusinessDate'])
    effective = date.fromisoformat(payload['effectiveDate'])
    if as_of > cutoff.date() or effective > cutoff.date() or effective < as_of:
        raise ValueError('Invalid sponsor holdings dates')
    rows = payload['holdings']
    if len(rows) != payload['totalNumberOfHoldings']:
        raise ValueError('Incomplete sponsor holdings response')
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['as_of', 'source_url', 'ticker', 'name', 'weight_pct'])
    writer.writeheader()
    excluded, total = [], 0.0
    for row in rows:
        weight = row['percentageOfTotalNetAssets']
        if weight is not None:
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight):
                raise ValueError('Invalid sponsor weight')
            total += weight
        if row['securityTypeCode'] in {'COM', 'ADR', 'DRNY'}:
            if weight is None:
                raise ValueError('Missing equity weight')
            writer.writerow({'as_of': as_of.isoformat(), 'source_url': source['url'],
                'ticker': row['ticker'], 'name': row['issuerName'], 'weight_pct': weight})
        else:
            excluded.append({k: row[k] for k in ('ticker', 'issuerName', 'securityTypeCode', 'percentageOfTotalNetAssets')})
    if not 99 <= total <= 101:
        raise ValueError('Sponsor portfolio weight does not reconcile')
    result = parse_holdings_csv(output.getvalue().encode(), symbol, cutoff)
    result.update(sponsor_effective_date=effective.isoformat(), sponsor_row_count=len(rows),
        sponsor_reported_weight_pct=total, excluded_positions=excluded,
        unknown_weight_positions=sum(r['percentageOfTotalNetAssets'] is None for r in rows),
        limitations='Dated sponsor equity view; cash/derivatives excluded and retained separately. '
            'Weights are not renormalized. Unknown weights remain unknown. No historical membership inference.')
    return result
