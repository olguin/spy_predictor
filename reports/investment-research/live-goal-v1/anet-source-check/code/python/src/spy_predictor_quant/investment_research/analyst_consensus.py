"""Extract a dated analyst snapshot from an archived registered quote page."""

from html import unescape
import re


def _visible_text(value):
    value = re.sub(r'<(?:script|style)\b[^>]*>.*?</(?:script|style)>', ' ', value,
                   flags=re.I | re.S)
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', value)).split())


def _number(text, label):
    match = re.search(re.escape(label) + r'\s+(-?[0-9]+(?:\.[0-9]+)?)', text, re.I)
    return match.group(1) if match else None


def extract(text):
    """Return only explicitly labelled values; never infer a missing table field."""
    visible = _visible_text(text)
    updated = re.search(r'Last Updated:\s+([A-Z][a-z]{2} \d{1,2}, \d{4}, \d{1,2}:\d{2} [AP]M [A-Z]{3})', visible)
    recommendation = re.search(r'Average Recommendation\s+([A-Z]+)', visible, re.I)
    eps = re.search(
        r'Earnings Per Share\s+This Quarter\s+Next Quarter\s+This Fiscal\s+Next Fiscal\s+'
        r'# of Estimates\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+'
        r'Mean Estimate\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+'
        r'High Estimates\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+'
        r'Low Estimate\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)', visible, re.I)
    ratings = re.search(
        r'Analysts Recommendations\s+Current\s+1 Month Ago\s+3 Months Ago\s+'
        r'BUY\s+(\d+)\s+\d+\s+\d+\s+OVERWEIGHT\s+(\d+)\s+\d+\s+\d+\s+'
        r'HOLD\s+(\d+)\s+\d+\s+\d+\s+UNDERWEIGHT\s+(\d+)\s+\d+\s+\d+\s+'
        r'SELL\s+(\d+)\s+\d+\s+\d+', visible, re.I)
    required = {
        'average_target_price': _number(visible, 'Average Target Price'),
        'ratings_count': _number(visible, 'Number of Ratings'),
        'current_quarter_estimate': _number(visible, 'Current Quarters Estimate'),
        'current_fiscal_year_estimate': _number(visible, "Current Year's Estimate"),
        'next_fiscal_year_estimate': _number(visible, 'Next Fiscal Year Estimate'),
    }
    if not updated or not recommendation or not eps or not ratings or any(v is None for v in required.values()):
        return None
    counts = list(map(int, eps.groups()[:4])); values = eps.groups()[4:]
    columns = ('this_quarter', 'next_quarter', 'this_fiscal', 'next_fiscal')
    return {
        'page_last_updated': updated.group(1),
        'average_recommendation': recommendation.group(1).upper(),
        **required,
        'eps_table': {column: {'estimate_count': counts[i], 'mean': values[i],
            'high': values[i+4], 'low': values[i+8]} for i, column in enumerate(columns)},
        'current_recommendations': dict(zip(('buy', 'overweight', 'hold', 'underweight', 'sell'),
                                             map(int, ratings.groups()))),
    }


def seed(broker):
    for identity in broker.state['source_cache'].values():
        evidence = broker.store.get('evidence', identity)
        if evidence.get('source_id') != 'anet-analyst-consensus' or not evidence.get('document_id'):
            continue
        document = broker.store.get('documents', evidence['document_id'])
        data = extract(document['text'])
        if data:
            broker.record({'kind': 'analyst_consensus_snapshot', 'adapter': 'archived_quote_consensus_v1',
                'symbols': evidence['symbols'], 'data': data, 'input_evidence_ids': [identity],
                'retrieved_at': evidence.get('retrieved_at'),
                'qualification': ('Third-party FactSet data displayed by Fox Business. The archived table does not '
                    'identify GAAP versus non-GAAP EPS, individual analysts, methodology, or target dispersion. '
                    'Treat the snapshot as dated consensus context, not issuer guidance or a valuation conclusion.')})
        return
