"""Verified source locations and frozen input requirements for the workspace."""
from copy import deepcopy

HOLDINGS_URL = 'https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/QQQ/holdings/fund?idType=ticker&productType=ETF'
POLICY_URL = 'https://www.govinfo.gov/content/pkg/FR-2026-01-15/html/2026-00789.htm'


def configure(mandate):
    mandate['schema_version'] = 'investment-research-mandate-v6'
    mandate['sources'] = [s for s in mandate['sources'] if s['source_id'] != 'bis-policy']
    for source in mandate['sources']:
        adapter = source['adapter']
        source['supports_dimensions'] = (['valuation', 'market_behavior'] if adapter == 'alpaca_daily' else
            ['business'] if adapter == 'etf_holdings' else ['valuation'] if adapter == 'etf_profile' else
            ['policy_exposure'] if source['kind'] in {'policy', 'macro'} else ['business', 'valuation', 'policy_exposure'])
        if source['source_id'] == 'qqq-holdings':
            source.update(url=HOLDINGS_URL, local_path=None, sha256=None, captured_at=None,
                          published_at=None, available_at=None, title='QQQ sponsor holdings with effective business date')
    template = deepcopy(next(s for s in mandate['sources'] if s['adapter'] == 'document'))
    symbols = [row['symbol'] for row in mandate['watchlist']]
    companies = [row['symbol'] for row in mandate['watchlist'] if row['kind'] == 'company']
    etfs = [row['symbol'] for row in mandate['watchlist'] if row['kind'] == 'etf']
    policy = template
    policy.update(source_id='advanced-computing-rule-20260115', title='Dated advanced computing license review rule, January 15 2026',
        url=POLICY_URL, publisher='U.S. Government Publishing Office / Bureau of Industry and Security',
        kind='policy', symbols=symbols, published_at='2026-01-15T23:59:59+00:00',
        available_at=None, fixture_text=None, local_path=None, sha256=None, captured_at=None,
        supports_dimensions=['policy_exposure'])
    mandate['sources'].append(policy)
    mandate['seed_source_ids'] = [s['source_id'] for s in mandate['sources']]
    if any(s['source_id'] == 'qqq-holdings' for s in mandate['sources']):
        mandate['publication_policy']['refresh_source_ids'].append('qqq-holdings')
    mandate['publication_policy']['refresh_source_ids'].append(policy['source_id'])
    requirements = []
    def add(identity, symbols, dimensions, sources, check, days, required=False, query=None):
        requirements.append({'requirement_id': identity, 'symbols': symbols, 'dimensions': dimensions,
            'source_ids': sources, 'check': check, 'maximum_age_days': days, 'required_for_run': required, 'query': query})
    for symbol in companies:
        add(symbol+'-annual', [symbol], ['valuation'], ['sec-facts-'+symbol], 'annual_eps', 450, True)
        add(symbol+'-operations', [symbol], ['business'], ['sec-facts-'+symbol], 'operating_data', 150)
        for query in ['geographic', 'customer', 'supply']:
            add(symbol+'-'+query, [symbol], ['policy_exposure'], ['sec-submissions-'+symbol], 'issuer_sections', 450, query=query)
    price_symbols = list(dict.fromkeys(symbols + [row['benchmark'] for row in mandate['watchlist']] +
        [row['sector_benchmark'] for row in mandate['watchlist']] + mandate['market_context_symbols']))
    required_prices = set(symbols + [row['benchmark'] for row in mandate['watchlist']] +
        [row['sector_benchmark'] for row in mandate['watchlist']])
    for symbol in price_symbols:
        add(symbol+'-price', [symbol], ['market_behavior'], ['price-'+symbol], 'completed_price', 4,
            symbol in required_prices)
    for symbol in etfs:
        if symbol == 'QQQ':
            add('QQQ-composition', ['QQQ'], ['business'], ['qqq-holdings'], 'holdings', 4)
            add('QQQ-valuation', ['QQQ'], ['valuation'], ['qqq-profile'], 'etf_valuation', 31)
    add('dated-policy', symbols, ['policy_exposure'], [policy['source_id']], 'policy_document', 365)
    mandate['source_requirements'] = requirements
    return mandate
