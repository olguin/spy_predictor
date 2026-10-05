"""Check technical return directions against the deterministic comparison panel."""

from decimal import Decimal, ROUND_HALF_UP
import re


PAIR_ROW = re.compile(
    r'PAIR\s+([A-Z][A-Z0-9.]*)/([A-Z][A-Z0-9.]*)\s+'
    r'5=([+-]\d+\.\d{4})\s+21=([+-]\d+\.\d{4})\s+'
    r'63=([+-]\d+\.\d{4})\b'
)
NEGATIVE = re.compile(r'\b(?:lagged|lags|lag|underperformed|underperforms|underperform|trailed|trails|trail)\b', re.I)
POSITIVE = re.compile(r'\b(?:led|leads|lead|outperformed|outperforms|outperform|beat|beats)\b', re.I)
ALL_WINDOWS = re.compile(r'\b(?:all|every)\b.{0,65}\b(?:window|horizon|session|period)s?\b|\b(?:window|horizon|session|period)s?\b.{0,65}\b(?:all|every)\b', re.I)


def _version_at_least(prompt_version, minor):
    match = re.search(r'/v(\d+)\.(\d+)$', prompt_version or '')
    return bool(match and (int(match[1]), int(match[2])) >= (2, minor))


def _panel(store, task):
    matches = [(identity, store.get('evidence', identity)) for identity in task['visible_evidence_ids']]
    matches = [(identity, item) for identity, item in matches
               if item.get('kind') == 'comparison_panel' and item.get('adapter') == 'research_comparisons_v1']
    if len(matches) > 1:
        raise ValueError('Technical sign audit requires one unambiguous comparison panel')
    return matches[0] if matches else (None, None)


def validate_technical_signs(store, task, result):
    """Reject contradictory all-window prose and require checked rows from v2.15.

    PAIR rows are constrained data, not an attempt to understand arbitrary prose.
    Other narrative claims still require semantic review.
    """
    if task['role'] != 'technical':
        return
    panel_id, panel = _panel(store, task)
    if panel is None:
        return
    pairs = {(row['symbol'], row['benchmark']): row['excess_price_return_percentage_points']
             for row in panel['data']['relative_strength']}
    narratives = [result['summary'], result['counter_thesis']]
    narratives += [claim['text'] for claim in result['claims']]
    narratives += [condition['description'] for condition in result['review_conditions']]
    signed_rows = {}
    for claim in result['claims']:
        for match in PAIR_ROW.finditer(claim['text']):
            pair = (match[1], match[2])
            if pair not in pairs or pair in signed_rows:
                raise ValueError(f'Unknown or repeated technical PAIR row: {pair[0]}/{pair[1]}')
            if panel_id not in claim['evidence_ids'] or pair[0] not in claim['symbols']:
                raise ValueError(f'Technical PAIR row lacks comparison evidence or symbol: {pair[0]}/{pair[1]}')
            expected = pairs[pair]
            for horizon, supplied in zip(('5', '21', '63'), match.groups()[2:]):
                actual = Decimal(supplied)
                correct = Decimal(expected[horizon]).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
                if actual != correct or (correct > 0 and not supplied.startswith('+')):
                    raise ValueError(f'Technical sign/value contradicts panel: {pair[0]}/{pair[1]} {horizon} sessions')
            signed_rows[pair] = True
    if _version_at_least(task.get('prompt_version'), 15) and set(signed_rows) != set(pairs):
        missing = ', '.join(f'{a}/{b}' for a, b in pairs if (a, b) not in signed_rows)
        raise ValueError(f'Technical findings need exact signed PAIR rows: {missing}')
    for narrative in narratives:
        for sentence in re.split(r'\.(?!\d)|[;!?]\s+', narrative):
            if not ALL_WINDOWS.search(sentence):
                continue
            for (symbol, benchmark), values in pairs.items():
                if not re.search(rf'\b{re.escape(symbol)}\b', sentence) or not re.search(rf'\b{re.escape(benchmark)}\b', sentence):
                    continue
                directions = {Decimal(value).compare(Decimal(0)) for value in values.values()}
                if ((NEGATIVE.search(sentence) and any(direction >= 0 for direction in directions)) or
                        (POSITIVE.search(sentence) and any(direction <= 0 for direction in directions))):
                    raise ValueError(f'All-window technical direction contradicts panel: {symbol}/{benchmark}')
