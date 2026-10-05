"""Three-method company valuation with explicit, deterministic assumptions."""

from decimal import Decimal, InvalidOperation, localcontext

from spy_predictor_quant.market_archive import utc_now


def _number(value, name, *, positive=False):
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f'Invalid {name}') from None
    if not result.is_finite() or (positive and result <= 0):
        raise ValueError(f'{name} must be finite' + (' and positive' if positive else ''))
    return result


def calculate(broker, args):
    symbol = args['symbol']
    companies = {row['symbol'] for row in broker.state['mandate']['watchlist'] if row['kind'] == 'company'}
    if symbol not in companies:
        raise ValueError('Three-method valuation requires a registered company')
    evidence_ids = args['evidence_ids']
    if not set(evidence_ids) <= set(broker.state['evidence_ids']):
        raise ValueError('Unknown valuation evidence')
    evidence = [broker.store.get('evidence', identity) for identity in evidence_ids]
    if not any(symbol in item.get('symbols', []) and item.get('adapter') == 'sec_companyfacts' for item in evidence):
        raise ValueError('Three-method valuation requires matching SEC company facts')
    price = broker.store.get('evidence', args['price_evidence_id'])
    price_data = price.get('data') or {}
    if (args['price_evidence_id'] not in evidence_ids or price.get('adapter') != 'alpaca_daily'
            or price_data.get('symbol') != symbol or price_data.get('status') != 'FRESH'):
        raise ValueError('Three-method valuation requires a matching fresh completed close')

    pe = args['pe_method']
    sales = args['ev_sales_method']
    dcf = args['dcf_method']
    with localcontext() as context:
        context.prec = 40
        close = _number(price_data['latest_close'], 'completed close', positive=True)
        pe_value = _number(pe['earnings_per_share'], 'EPS', positive=True) * _number(pe['pe_multiple'], 'P/E', positive=True)

        revenue = _number(sales['revenue'], 'revenue', positive=True)
        sales_multiple = _number(sales['ev_to_sales_multiple'], 'EV/sales multiple', positive=True)
        sales_net_cash = _number(sales['net_cash'], 'EV/sales net cash')
        sales_shares = _number(sales['diluted_shares'], 'EV/sales diluted shares', positive=True)
        enterprise_value = revenue * sales_multiple
        sales_equity_value = enterprise_value + sales_net_cash
        sales_value = sales_equity_value / sales_shares

        fcf = _number(dcf['starting_free_cash_flow'], 'starting free cash flow', positive=True)
        growth = _number(dcf['annual_growth_pct'], 'DCF growth') / 100
        discount = _number(dcf['discount_rate_pct'], 'DCF discount rate', positive=True) / 100
        terminal_growth = _number(dcf['terminal_growth_pct'], 'DCF terminal growth') / 100
        if not Decimal('-0.50') <= growth <= Decimal('1.00'):
            raise ValueError('DCF annual growth must be between -50% and 100%')
        if not Decimal('0.01') <= discount <= Decimal('0.50') or not Decimal('-0.10') <= terminal_growth <= Decimal('0.10'):
            raise ValueError('DCF discount or terminal-growth assumption is outside bounds')
        if discount <= terminal_growth:
            raise ValueError('DCF discount rate must exceed terminal growth')
        present_value = Decimal(0)
        projected = []
        for year in range(1, 6):
            fcf *= 1 + growth
            discounted = fcf / ((1 + discount) ** year)
            present_value += discounted
            projected.append({'year': year, 'free_cash_flow': str(fcf), 'present_value': str(discounted)})
        terminal_value = fcf * (1 + terminal_growth) / (discount-terminal_growth)
        discounted_terminal = terminal_value / ((1 + discount) ** 5)
        dcf_equity_value = present_value + discounted_terminal + _number(dcf['net_cash'], 'DCF net cash')
        dcf_shares = _number(dcf['diluted_shares'], 'DCF diluted shares', positive=True)
        dcf_value = dcf_equity_value / dcf_shares

        def row(method, value, rationale):
            return {'method': method, 'value_per_share_decimal': str(value),
                    'change_from_close_pct_decimal': str((value / close - 1) * 100),
                    'rationale': rationale}

        methods = [
            row('forward_pe', pe_value, pe['rationale']),
            row('ev_to_sales', sales_value, sales['rationale']),
            row('discounted_cash_flow', dcf_value, dcf['rationale']),
        ]
        ordered = sorted((item['value_per_share_decimal'] for item in methods), key=Decimal)

    return broker.record({
        'kind': 'three_method_valuation', 'adapter': 'three_method_valuation_v1',
        'symbol': symbol, 'symbols': [symbol], 'price_evidence_id': args['price_evidence_id'],
        'observed_close_decimal': str(close), 'price_date': price_data['price_date'],
        'methods': methods,
        'range': {'low_value_per_share_decimal': ordered[0], 'median_value_per_share_decimal': ordered[1],
                  'high_value_per_share_decimal': ordered[2]},
        'inputs': {'pe_method': pe, 'ev_sales_method': sales,
                   'dcf_method': dcf | {'projected_cash_flows': projected,
                                       'discounted_terminal_value': str(discounted_terminal)}},
        'input_evidence_ids': evidence_ids,
        'assumptions': args['assumptions'],
        'qualification': ('All forward financial inputs and valuation multiples are explicit analyst/model assumptions unless a cited source states otherwise. '
                          'The three methods are correlated and do not form a statistical confidence interval. Values are conditional sensitivities, not targets or guarantees.'),
        'retrieved_at': utc_now(),
    })
