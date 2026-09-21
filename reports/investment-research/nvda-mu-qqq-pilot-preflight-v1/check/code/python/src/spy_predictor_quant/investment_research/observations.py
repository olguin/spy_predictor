"""Separate publication-origin lane; no legacy forecast/outcome ledger access."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import importlib.metadata

import exchange_calendars as xcals

from spy_predictor_quant.market_archive import content_hash, utc_now


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('Timezone-aware timestamp required')
    return result.astimezone(timezone.utc)


def positive(value):
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Invalid decimal') from None
    if not number.is_finite() or number <= 0:
        raise ValueError('Positive finite decimal required')
    return number


def calendar(at):
    return xcals.get_calendar('XNYS', start=(at-timedelta(days=30)).date().isoformat(),
                              end=(at+timedelta(days=400)).date().isoformat())


def schedule(published_at, watchlist, horizons):
    """Origin session is 1; publication at the open goes to the next open."""
    published = timestamp(published_at)
    if not horizons or any(type(h) is not int or h < 1 or h > 63 for h in horizons):
        raise ValueError('Horizons must be registered in 1..63 sessions')
    cal = calendar(published)
    sessions = [s for s in cal.sessions if cal.session_open(s).to_pydatetime() > published]
    origin = sessions[0]
    origin_at = cal.session_open(origin).isoformat()
    return {'schema_version': 'investment-research-observation-contract-v1',
        'lane': 'investment-research-v1', 'published_at': published_at,
        'rule': 'first_regular_open_strictly_after_publication;origin_session_is_1;target_session_h_close',
        'calendar': 'XNYS', 'calendar_version': importlib.metadata.version('exchange-calendars'),
        'origin_session': origin.date().isoformat(), 'origin_at': origin_at, 'origin_price': None,
        'publication_to_origin_seconds': (timestamp(origin_at)-published).total_seconds(),
        'targets': {str(h): {'session': sessions[h-1].date().isoformat(), 'at': cal.session_close(sessions[h-1]).isoformat()} for h in horizons},
        'pairs': [{'symbol': row['symbol'], 'benchmarks': list(dict.fromkeys([row['benchmark'], row['sector_benchmark']]))} for row in watchlist],
        'currency': 'USD', 'return_basis': 'price_return', 'cash_dividends': 'excluded',
        'conditional_lane': 'separate_unscored; requires registered trigger, subsequent price, expiry and cost rule',
        'qualification': 'Delayed research-return observation; not an order fill, portfolio return or net strategy return'}


def _return(contract, symbol, horizon, data, now):
    target = contract['targets'][str(horizon)]['at']
    origin = contract['origin_at']
    if data['symbol'] != symbol or data['currency'] != 'USD' or data['return_basis'] != 'price_return':
        raise ValueError('Incompatible symbol, currency or return basis')
    if data['share_basis'] != 'raw' or data.get('cash_dividends') != 'excluded':
        raise ValueError('Requires raw prices and explicit dividend exclusion')
    coverage = data['corporate_actions']
    if (coverage['status'] != 'complete' or timestamp(coverage['from']) > timestamp(origin) or
            timestamp(coverage['through']) < timestamp(target) or not coverage['source_hash']):
        raise ValueError('Insufficient corporate-action coverage')
    for key, at in [('origin', origin), ('target', target)]:
        row = data[key]
        if timestamp(row['at']) != timestamp(at):
            raise ValueError('Price timestamp differs from frozen session convention')
        if timestamp(row['available_at']) < timestamp(at) or timestamp(row['available_at']) > now:
            raise ValueError('Price availability is invalid or still pending')
        if not row['source_hash'] or not row['feed'] or row['session'] != 'regular':
            raise ValueError('Price provenance and regular session required')
    if data['origin']['feed'] != data['target']['feed']:
        raise ValueError('Inconsistent origin/target feed')
    factor = Decimal(1)
    seen = set()
    for event in coverage['events']:
        if event['event_id'] in seen:
            raise ValueError('Duplicate corporate action')
        seen.add(event['event_id'])
        if event['kind'] != 'split':
            raise ValueError('Unsupported corporate action; outcome unscorable')
        if timestamp(origin) < timestamp(event['effective_at']) <= timestamp(target):
            factor *= positive(event['new_shares_per_old_share'])
    normalized_origin = positive(data['origin']['price_decimal']) / factor
    target_price = positive(data['target']['price_decimal'])
    result = (target_price/normalized_origin - 1)*100
    return {'return_pct_decimal': str(result), 'origin_on_target_share_basis_decimal': str(normalized_origin),
            'split_factor_decimal': str(factor), 'target_decimal': str(target_price),
            'input_hash': content_hash(data), 'feed': data['origin']['feed']}


def observe(contract, symbol, horizon, instrument, benchmarks, *, now=None):
    """Retain pending/unscorable cases; never select a substitute origin."""
    now = now or datetime.now(timezone.utc)
    record = {'schema_version': 'investment-research-outcome-v1', 'contract_id': content_hash(contract),
        'lane': 'unconditional_thesis', 'symbol': symbol, 'horizon': horizon, 'recorded_at': now.isoformat(),
        'status': 'UNSCORABLE', 'inputs': {'instrument': instrument, 'benchmarks': benchmarks}}
    try:
        pair = next(p for p in contract['pairs'] if p['symbol'] == symbol)
        target = timestamp(contract['targets'][str(horizon)]['at'])
        if now < target:
            return {**record, 'status': 'PENDING', 'reason': 'Registered target has not closed'}
        if timestamp(contract['origin_at']) <= timestamp(contract['published_at']):
            raise ValueError('Origin must be strictly after publication')
        if set(benchmarks) != set(pair['benchmarks']):
            raise ValueError('Benchmark mapping differs from issued contract')
        result = _return(contract, symbol, horizon, instrument, now)
        paired = {b: _return(contract, b, horizon, benchmarks[b], now) for b in pair['benchmarks']}
        if any(p['feed'] != result['feed'] for p in paired.values()):
            raise ValueError('Instrument and benchmark feed mismatch')
        return {**record, 'status': 'OBSERVED', 'instrument': result, 'benchmarks': paired,
            'excess_percentage_points': {b: str(Decimal(result['return_pct_decimal'])-Decimal(p['return_pct_decimal'])) for b, p in paired.items()},
            'origin_at': contract['origin_at'], 'target_at': contract['targets'][str(horizon)]['at'],
            'return_basis': 'price_return;cash_dividends_excluded', 'qualification': contract['qualification']}
    except (ValueError, KeyError, StopIteration, TypeError) as error:
        return {**record, 'reason': str(error) or type(error).__name__}
