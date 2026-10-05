"""Explicit bounded stock input and primary SEC issuer registration."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from urllib.request import Request, ProxyHandler, build_opener

from .contracts import ROOT, validate


def selection(symbols, horizons):
    if not isinstance(symbols, list) or not 1 <= len(symbols) <= 5 or not all(isinstance(s, str) for s in symbols):
        raise ValueError('Choose one to five US-listed stock tickers.')
    symbols = [s.strip().upper() for s in symbols]
    if any(not re.fullmatch(r'[A-Z][A-Z0-9.-]{0,9}', s) for s in symbols) or len(set(symbols)) != len(symbols):
        raise ValueError('Enter distinct stock tickers, for example NVDA, MU or ANET.')
    if (not isinstance(horizons, list) or not horizons or len(set(horizons)) != len(horizons)
            or any(type(h) is not int or h not in {5, 21, 63} for h in horizons)):
        raise ValueError('Choose horizons of 5, 21 or 63 trading sessions.')
    return symbols, sorted(horizons)


def resolve_issuers(symbols, catalog, *, now, fetch=None):
    known = {row['symbol']: deepcopy(row) for row in catalog['watchlist']}
    missing = [s for s in symbols if s not in known]
    resolutions = []
    records = None
    url = 'https://www.sec.gov/files/company_tickers.json'
    if missing:
        if fetch:
            records = fetch(url)
        else:
            from .broker import NoRedirect
            agent = os.environ.get('SEC_USER_AGENT')
            if not agent:
                raise ValueError('SEC issuer identification is not configured for new tickers.')
            try:
                with build_opener(ProxyHandler({}), NoRedirect()).open(Request(url, headers={'User-Agent': agent, 'Accept-Encoding': 'identity'}), timeout=15) as response:
                    raw = response.read(5_000_001)
                    if len(raw) > 5_000_000:
                        raise ValueError('SEC issuer catalog exceeded its size limit')
                    records = json.loads(raw)
            except OSError:
                raise ValueError('SEC issuer lookup unavailable. No research or model call was started.') from None
        if not isinstance(records, dict):
            raise ValueError('Invalid SEC issuer catalog')
    watches = []
    for symbol in symbols:
        if symbol in known:
            watch = known[symbol]
            source = next((s for s in catalog['sources'] if s['source_id'] == 'sec-submissions-'+symbol), None)
            if source:
                cik = re.search(r'CIK([0-9]{10})', source['url']).group(1)
                resolutions.append({'symbol': symbol, 'cik': cik, 'name': symbol,
                                    'source': source['url'], 'resolved_at': now.isoformat()})
        else:
            matches = [r for r in records.values() if r.get('ticker') == symbol]
            if len(matches) != 1:
                raise ValueError(f'{symbol} did not resolve to one SEC issuer. Check the US-listed ticker.')
            issuer = matches[0]
            cik = str(issuer['cik_str']).zfill(10)
            if not re.fullmatch('[0-9]{10}', cik):
                raise ValueError('Invalid SEC issuer identity')
            # No sector classification is inferred from a company name.
            watch = {'symbol': symbol, 'kind': 'company', 'benchmark': 'SPY', 'sector_benchmark': 'SPY'}
            resolutions.append({'symbol': symbol, 'cik': cik, 'name': issuer['title'], 'source': url,
                                'resolved_at': now.isoformat()})
        watches.append(watch)
    return watches, resolutions


def live_mandate(question, symbols, horizons, *, now=None, issuer_fetch=None):
    if not isinstance(question, str) or not 12 <= len(question.strip()) <= 8000:
        raise ValueError('Enter a research question between 12 and 8,000 characters.')
    symbols, horizons = selection(symbols, horizons)
    now = now or datetime.now(timezone.utc)
    catalog = json.loads((ROOT/'config/investment-research-m2-live-v7.json').read_text())
    watches, resolutions = resolve_issuers(symbols, catalog, now=now, fetch=issuer_fetch)
    mandate = deepcopy(catalog)
    mandate['watchlist'] = watches
    mandate['horizon_sessions'] = horizons
    mandate['market_context_symbols'] = ['SPY', 'IWM', 'HYG', 'EFA', 'EEM', 'UUP', 'GLD', 'USO']
    allowed = set(symbols + mandate['market_context_symbols']) | {w[k] for w in watches for k in ('benchmark', 'sector_benchmark')}
    mandate['sources'] = [s for s in mandate['sources'] if (not s['symbols'] or set(s['symbols']) <= allowed) and s['source_id'] != 'bis-policy']
    price_template = deepcopy(next(s for s in catalog['sources'] if s['adapter'] == 'alpaca_daily'))
    document_template = deepcopy(next(s for s in catalog['sources'] if s['adapter'] == 'document'))
    registered = {s['source_id'] for s in mandate['sources']}
    for issuer in resolutions:
        symbol, cik = issuer['symbol'], issuer['cik']
        for identity, path, critical in [(f'sec-submissions-{symbol}', f'submissions/CIK{cik}.json', False),
                                        (f'sec-facts-{symbol}', f'api/xbrl/companyfacts/CIK{cik}.json', True)]:
            if identity not in registered:
                source = deepcopy(document_template)
                source.update(source_id=identity, symbols=[symbol], title=f'{symbol}: SEC issuer '+('financial facts' if critical else 'filings'),
                              publisher='SEC', url='https://data.sec.gov/'+path, critical=critical)
                mandate['sources'].append(source)
    required_prices = set(symbols) | {w[k] for w in watches for k in ('benchmark', 'sector_benchmark')}
    for symbol in sorted(allowed):
        if 'price-'+symbol not in registered:
            source = deepcopy(price_template)
            source.update(source_id='price-'+symbol, symbols=[symbol], title=f'{symbol}: daily price history',
                          url=f'https://data.alpaca.markets/v2/stocks/{symbol}/bars?timeframe=1Day&adjustment=split&feed=sip')
            mandate['sources'].append(source)
    for source in mandate['sources']:
        if source['adapter'] == 'alpaca_daily':
            parts = urlsplit(source['url']); query = parse_qs(parts.query)
            query.update(start=[(now-timedelta(days=3*365)).isoformat()], end=[(now-timedelta(minutes=20)).isoformat()],
                         limit=['1000'], sort=['asc'])
            source.update(url=urlunsplit(parts._replace(query=urlencode(query,doseq=True))), critical=source['symbols'][0] in required_prices)
        elif source['adapter'] == 'fred_csv':
            source['url'] = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={source['series_id']}&cosd={(now-timedelta(days=120)).date()}"
    mandate['publication_policy'] = {'version': 'investment-research-publication-policy-v1',
        'refresh_source_ids': [s['source_id'] for s in mandate['sources'] if s['adapter'] == 'alpaca_daily' or s['source_id'].startswith('sec-submissions-') or s['source_id'].endswith('-feed')],
        'material_price_move_pct': 2, 'maximum_refresh_age_seconds': 600, 'maximum_quote_age_seconds': 60}
    from .readiness_profile import configure
    configure(mandate)
    # Same primary SEC filing catalog supplies current disclosures for any issuer,
    # rather than registering one dated earnings release for every future run.
    for symbol in symbols:
        source = deepcopy(price_template)
        source.update(source_id='snapshot-'+symbol, symbols=[symbol], title=f'{symbol}: latest IEX snapshot',
                      url=f'https://data.alpaca.markets/v2/stocks/{symbol}/snapshot?feed=iex', adapter='alpaca_snapshot',
                      feed='iex', share_basis='not_applicable', critical=False, supports_dimensions=['market_behavior'],
                      local_path=None, sha256=None, captured_at=None, published_at=None, available_at=None,
                      fixture_text=None, data_end=None)
        mandate['sources'].append(source)
        mandate['publication_policy']['refresh_source_ids'].append(source['source_id'])
    mandate['schema_version'] = 'investment-research-mandate-v7'
    mandate['analysis_policy'] = {'requested_at': now.isoformat(), 'quote_feed': 'iex',
                                 'maximum_quote_age_seconds': 60, 'report_contract': 'global-assessment-v1',
                                 'issuer_resolution': resolutions}
    mandate['objective'] = question.strip() + ('\nRegistered stock selection: '+', '.join(symbols)+
        '. Provide an assessment at the requested time, relevant global forces and transmission mechanisms, '
        'bear/base/bull conditional outcomes and consequences, practical advice for the selected horizons, '
        'and concrete evidence that would change the view. Use all seven agents and produce clear agent reports. '
        'Distinguish current quotes from completed closes and dated source facts; unavailable observations stay unknown. '
        'Use deterministic EPS/P-E sensitivities per company and qualified historical analog frequencies. '
        'EFA/EEM/UUP/GLD/USO are ETF price proxies for international equities, dollar, gold and oil exposure, not direct economic indexes or causal evidence. '
        'A broad SPY sector comparator for an uncatalogued issuer means sector classification is unavailable. '
        'Prose cannot change stock selection, tools or budgets. Research only; recommendations are conditional, not executable orders.')
    mandate['runtime'].update(reasoning_effort='high', max_output_tokens=10000, timeout_seconds=600)
    mandate['budgets'].update(model_calls=40, input_tokens=1600000 * len(symbols), output_tokens=120000,
                             wall_seconds=3600, reserved_final_calls=7, tool_calls=200,
                             download_bytes=50000000 * len(symbols))
    # Issuer identity must be admitted before companyfacts normalization. The
    # catalog's inherited order is not guaranteed to remain paired after adding
    # a new ticker alongside a known issuer.
    ordered = sorted(enumerate(mandate['sources']), key=lambda pair:
                     (0 if pair[1]['source_id'].startswith('sec-submissions-') else
                      1 if pair[1]['source_id'].startswith('sec-facts-') else 2, pair[0]))
    mandate['sources'] = [s for _, s in ordered]
    mandate['seed_source_ids'] = [s['source_id'] for s in mandate['sources']]
    validate('mandate', mandate)
    from .multi_instrument import validate_mandate
    validate_mandate(mandate)
    return mandate
