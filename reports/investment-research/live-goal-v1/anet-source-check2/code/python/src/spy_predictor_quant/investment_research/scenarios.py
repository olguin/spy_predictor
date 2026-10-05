"""One bounded bear/base/bull calculation per company; every input is explicit."""
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext

from spy_predictor_quant.market_archive import utc_now


def positive(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Invalid scenario decimal') from None
    if not result.is_finite() or result <= 0:
        raise ValueError('Scenario EPS, multiple and price must be finite and positive')
    return result


def calculate_grid(broker, args):
    symbol = args['symbol']
    companies = {r['symbol'] for r in broker.state['mandate']['watchlist'] if r['kind'] == 'company'}
    if symbol not in companies:
        raise ValueError('Scenario grid requires a registered company, never ETF EPS')
    if not set(args['evidence_ids']) <= set(broker.state['evidence_ids']):
        raise ValueError('Unknown scenario anchor evidence')
    anchors = [broker.store.get('evidence', i) for i in args['evidence_ids']]
    if not any(symbol in e.get('symbols', []) and e.get('adapter') == 'sec_companyfacts'
               and (e.get('data') or {}).get('earnings_periods', {}).get('annual') for e in anchors):
        raise ValueError('Scenario requires this company annual earnings anchor')
    if args['price_evidence_id'] not in args['evidence_ids']:
        raise ValueError('Scenario price must be listed in input evidence')
    price = broker.store.get('evidence', args['price_evidence_id'])
    data = price.get('data') or {}
    if (price.get('adapter') != 'alpaca_daily' or data.get('symbol') != symbol
            or data.get('status') != 'FRESH' or data.get('adjustment') != 'split_adjusted'):
        raise ValueError('Scenario requires matching fresh completed-close evidence and split-adjusted share basis')
    start, end = date.fromisoformat(args['earnings_period_start']), date.fromisoformat(args['earnings_period_end'])
    if not 350 <= (end-start).days+1 <= 380:
        raise ValueError('Scenario earnings must describe an explicit annual period')
    calendars = [(i, broker.store.get('evidence', i)) for i in broker.state['evidence_ids']]
    calendars = [(i, e) for i, e in calendars if e.get('kind') == 'fiscal_calendar'
                 and e.get('symbol') == symbol and e['start'] == args['earnings_period_start']]
    if any(e['end'] != args['earnings_period_end'] for _, e in calendars):
        raise ValueError('Scenario period conflicts with disclosed fiscal calendar: '+
                         '; '.join(f"{e['start']} through {e['end']} ({e['weeks']} weeks)" for _, e in calendars))
    if args['share_basis'] != data['adjustment']:
        raise ValueError('Scenario earnings and price share basis mismatch')
    if [r['case'] for r in args['cases']] != ['bear', 'base', 'bull']:
        raise ValueError('Exactly ordered bear/base/bull scenarios required')
    rows = []
    with localcontext() as context:
        context.prec = 40
        close = positive(data['latest_close'])
        for row in args['cases']:
            eps, multiple = positive(row['earnings_per_share']), positive(row['pe_multiple'])
            target = eps * multiple
            rows.append({**row, 'scenario_price_decimal': str(target),
                'break_even_pe_decimal': str(close / eps),
                'break_even_eps_decimal': str(close / multiple),
                'change_from_close_pct_decimal': str((target / close-1)*100)})
            interim = [r for e in anchors if e.get('adapter') == 'sec_companyfacts' and symbol in e.get('symbols', [])
                       for r in (e.get('data') or {}).get('earnings_periods', {}).get('interim', [])
                       if r['start'] == args['earnings_period_start'] and r['end'] < args['earnings_period_end']]
            if interim:
                anchor = max(interim, key=lambda r: r['end'])
                rows[-1]['constant_share_residual'] = {
                    'eps_decimal': str(eps - Decimal(str(anchor['value']))),
                    'interim_start': anchor['start'], 'interim_end': anchor['end'],
                    'qualification': 'Annual assumed EPS minus reported interim EPS under a constant diluted-share approximation only; not an exact annual EPS reconciliation.'}
        if not Decimal(rows[0]['scenario_price_decimal']) <= Decimal(rows[1]['scenario_price_decimal']) <= Decimal(rows[2]['scenario_price_decimal']):
            raise ValueError('Scenario prices must be ordered bear <= base <= bull')
        loss = max(Decimal(0), -Decimal(rows[0]['change_from_close_pct_decimal']))
        gain = max(Decimal(0), Decimal(rows[2]['change_from_close_pct_decimal']))
        asymmetry = {'bear_loss_magnitude_pct_decimal': str(loss), 'bull_gain_pct_decimal': str(gain),
                     'bull_gain_minus_bear_loss_pp_decimal': str(gain-loss),
                     'comparison': 'bull_gain_exceeds_bear_loss' if gain > loss else 'bear_loss_exceeds_bull_gain' if loss > gain else 'equal_magnitudes',
                     'qualification': 'Compares positive bull gain with absolute negative bear loss only; no probabilities or expected return.'}
    return broker.record({'kind': 'scenario_grid', 'symbol': symbol, 'symbols': [symbol],
        'cases': rows, 'asymmetry': asymmetry, 'earnings_period_start': args['earnings_period_start'],
        'earnings_period_end': args['earnings_period_end'], 'accounting_basis': args['accounting_basis'],
        'share_basis': args['share_basis'], 'assumptions': args['assumptions'],
        'input_evidence_ids': list(dict.fromkeys([*args['evidence_ids'], *(i for i, _ in calendars)])), 'price_evidence_id': args['price_evidence_id'],
        'observed_close_decimal': str(close), 'price_date': data['price_date'],
        'horizon_sessions': broker.state['mandate']['horizon_sessions'],
        'qualification': 'All EPS and P/E inputs are analyst assumptions, not observed multiples or consensus. '
            'Prices are conditional sensitivities, not forecasts, probabilities or executable quotes. '
            'The earnings period differs from the research horizon; assumption and share-basis suitability require review.',
        'retrieved_at': utc_now()})
