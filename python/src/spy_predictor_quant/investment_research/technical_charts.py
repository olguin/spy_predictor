"""Deterministic SVG charts from admitted completed-session technical evidence."""

from decimal import Decimal, ROUND_HALF_UP
from html import escape

from .technical_path import completed_bars


def _text(x, y, value, *, size=14, color='#26364a', weight=400, anchor='start'):
    return (f'<text x="{x}" y="{y}" fill="{color}" font-family="Arial,sans-serif" '
            f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>')


def _signed(value):
    number = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return f'{number:+.2f}'


def _svg(width, height, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" role="img" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#ffffff"/>'
            + ''.join(body) + '</svg>\n')


def _relative_chart(rows, date):
    width, height = 1100, 145 + len(rows) * 101
    zero = 665
    maximum = max((abs(float(v)) for r in rows for v in r['excess_price_return_percentage_points'].values()), default=1)
    extent = max(1, maximum * 1.18)
    scale = 335 / extent
    body = [_text(42, 46, 'Relative price performance', size=26, weight=700),
            _text(42, 73, f'Completed session ending {date} · instrument minus benchmark · percentage points', size=14, color='#62748a')]
    for tick in (-extent, -extent/2, 0, extent/2, extent):
        x = zero + tick * scale
        body += [f'<line x1="{x}" y1="106" x2="{x}" y2="{height-42}" stroke="{("#8290a2" if tick == 0 else "#e4e9ef")}" stroke-width="{(2 if tick == 0 else 1)}"/>',
                 _text(x, 96, f'{tick:+.1f}', size=12, color='#62748a', anchor='middle')]
    for index, row in enumerate(rows):
        top = 119 + index * 101
        pair = f"{row['symbol']} / {row['benchmark']}"
        body.append(_text(42, top + 21, pair, size=16, weight=700))
        for offset, horizon in enumerate(('5', '21', '63')):
            y = top + 7 + offset * 25
            value = Decimal(row['excess_price_return_percentage_points'][horizon])
            end = zero + float(value) * scale
            left, width_bar = min(zero, end), max(1, abs(end-zero))
            color = '#147d72' if value >= 0 else '#c34e55'
            body += [_text(240, y + 12, horizon+' sessions', size=12, color='#62748a'),
                     f'<rect x="{left:.1f}" y="{y}" width="{width_bar:.1f}" height="16" rx="3" fill="{color}"/>',
                     _text(end + (8 if value >= 0 else -8), y + 13, _signed(value), size=12,
                           color=color, weight=700, anchor=('start' if value >= 0 else 'end'))]
        body.append(f'<line x1="42" y1="{top+92}" x2="1058" y2="{top+92}" stroke="#eef1f5"/>')
    body.append(_text(42, height-16, 'Historical price-return comparisons only; no forecast, total return or causal attribution.', size=13, color='#62748a'))
    return _svg(width, height, body)


def _risk_chart(prices, date):
    width, height = 1100, 190 + len(prices)*73
    metrics = [('return63_pct', '63-session return', -20, 20, True),
               ('realized_vol63_pct', '63-session vol.', 0, 100, False),
               ('drawdown_from_window_high_pct', '252-session drawdown', -30, 0, True),
               ('price_to_sma50', 'Close vs 50-day SMA', -10, 10, True)]
    body = [_text(42, 46, 'Trend and path risk snapshot', size=26, weight=700),
            _text(42, 73, f'Completed session ending {date} · split-adjusted price basis', size=14, color='#62748a')]
    for col, (key, label, low, high, signed) in enumerate(metrics):
        x = 174 + col * 224
        actual = [((float(d[key])-1)*100 if key == 'price_to_sma50' else float(d[key])) for d in prices.values()]
        low, high = min(low, min(actual)*1.1), max(high, max(actual)*1.1)
        metrics[col] = (key, label, low, high, signed)
        body += [_text(x, 112, label, size=13, weight=700),
                 _text(x, 134, f'{low:+.0f} to {high:+.0f}%', size=11, color='#62748a')]
    for row, (symbol, data) in enumerate(prices.items()):
        y = 171 + row * 73
        body += [_text(42, y + 16, symbol, size=17, weight=700),
                 f'<line x1="42" y1="{y+51}" x2="1058" y2="{y+51}" stroke="#eef1f5"/>']
        for col, (key, _, low, high, signed) in enumerate(metrics):
            value = ((float(data[key])-1)*100 if key == 'price_to_sma50' else float(data[key]))
            x = 174 + col * 224
            start = x + (0-low)/(high-low)*150
            end = x + max(0, min(1, (value-low)/(high-low)))*150
            bar_x, bar_width = min(start, end), max(2, abs(end-start))
            color = '#147d72' if value >= 0 else '#c34e55'
            body += [f'<line x1="{x}" y1="{y+32}" x2="{x+150}" y2="{y+32}" stroke="#e4e9ef" stroke-width="8"/>',
                     f'<rect x="{bar_x:.1f}" y="{y+27}" width="{bar_width:.1f}" height="10" rx="3" fill="{color}"/>',
                     _text(x+158, y+37, f'{value:+.1f}%' if signed else f'{value:.1f}%', size=12, color=color, weight=700)]
    body += [_text(42, height-27, 'Volatility is annualized from the supplied 63-session window; drawdown uses the supplied 252-session high.', size=13, color='#62748a'),
             _text(42, height-7, 'Different windows are shown separately. Historical variation and moving-average distance do not predict returns.', size=13, color='#62748a')]
    return _svg(width, height, body)


def _path_chart(symbol, benchmark, sector, paths, excluded, date):
    names = list(dict.fromkeys((symbol, benchmark, sector)))
    recent = {name: paths[name][-64:] for name in names}
    dates = [[bar['t'][:10] for bar in bars] for bars in recent.values()]
    if any(row != dates[0] for row in dates[1:]):
        raise ValueError('Technical chart requires matched completed-session dates')
    indexed = {name: [float(Decimal(str(bar['c'])) / Decimal(str(bars[0]['c'])) * 100)
                      for bar in bars] for name, bars in recent.items()}
    values = [value for row in indexed.values() for value in row]
    low, high = min(values), max(values)
    padding = max(1.0, (high-low)*0.08)
    low, high = low-padding, high+padding
    x0, x1, y0, y1 = 88, 1044, 142, 354
    x_at = lambda index: x0+(x1-x0)*index/63
    y_at = lambda value: y1-(value-low)/(high-low)*(y1-y0)
    colors = {symbol: '#1d4ed8', benchmark: '#64748b', sector: '#bd7519'}
    body = [_text(42, 42, f'{symbol}: completed price and volume path', size=24, weight=700),
            _text(42, 68, f'63 sessions ending {date} · split-adjusted SIP closes · first close = 100', size=13, color='#62748a')]
    for index, name in enumerate(names):
        x = 42 + index*238
        body += [f'<line x1="{x}" y1="91" x2="{x+25}" y2="91" stroke="{colors[name]}" stroke-width="3"/>',
                 _text(x+32, 96, name, size=13, color=colors[name], weight=700)]
    for tick in (round(low), 100, round(high)):
        if not low <= tick <= high:
            continue
        y = y_at(tick)
        body += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="#e4e9ef"/>',
                 _text(77, y+4, f'{tick:.0f}', size=11, color='#62748a', anchor='end')]
    for name, row in indexed.items():
        points = ' '.join(f'{x_at(i):.1f},{y_at(value):.1f}' for i, value in enumerate(row))
        body.append(f'<polyline fill="none" stroke="{colors[name]}" stroke-width="{3 if name == symbol else 2}" points="{points}"/>')
    volumes = [float(bar['v']) for bar in recent[symbol]]
    maximum = max(volumes) or 1
    body.append(_text(42, 392, f'{symbol} volume · millions of shares', size=13, weight=700))
    for i, volume in enumerate(volumes):
        bar_height = volume/maximum*88
        body.append(f'<rect x="{x_at(i)-4:.1f}" y="{492-bar_height:.1f}" width="8" height="{bar_height:.1f}" fill="#9ab8e9"/>')
    for i in (0, 21, 42, 63):
        body.append(_text(x_at(i), 515, dates[0][i], size=11, color='#62748a', anchor='middle'))
    body += [_text(42, 543, f'Source cutoff {date}; {excluded[symbol]} later/unfinished bar(s) excluded. Volume is descriptive, not confirmation by itself.', size=12, color='#62748a')]
    return _svg(1100, 560, body)


def _probability_chart(data):
    body = [_text(42, 44, f"{data['symbol']}: historical positive-return frequencies", size=24, weight=700),
            _text(42, 70, f"Regime analogs through {data['as_of']} · overlapping observations", size=13, color='#62748a')]
    for index, (horizon, row) in enumerate(data['horizons'].items()):
        x = 124 + index * 310
        conditional = float(row['conditional_current_regime']['positive_return_frequency_pct'])
        base = float(row['unconditional_base_rate']['positive_return_frequency_pct'])
        n = row['conditional_current_regime']['sample_size']
        body += [_text(x, 112, horizon+' sessions', size=15, weight=700),
                 f'<rect x="{x}" y="132" width="72" height="{conditional*2.2:.1f}" fill="#147d72"/>',
                 f'<rect x="{x+94}" y="132" width="72" height="{base*2.2:.1f}" fill="#9aa7b8"/>',
                 _text(x+36, 126, f'{conditional:.1f}%', size=12, color='#147d72', weight=700, anchor='middle'),
                 _text(x+130, 126, f'{base:.1f}%', size=12, color='#62748a', weight=700, anchor='middle'),
                 _text(x+36, 374, f'conditional n={n}', size=11, color='#62748a', anchor='middle'),
                 _text(x+130, 394, 'base rate', size=11, color='#62748a', anchor='middle')]
    body += [_text(42, 430, 'Green: current coarse regime. Gray: unconditional history. Frequencies are descriptive and not calibrated forecasts.', size=12, color='#62748a')]
    return _svg(1100, 455, body)


def _valuation_chart(evidence):
    values = [float(row['value_per_share_decimal']) for row in evidence['methods']]
    close = float(evidence['observed_close_decimal'])
    maximum = max(values + [close]) * 1.12
    body = [_text(42, 44, f"{evidence['symbol']}: conditional valuation methods", size=24, weight=700),
            _text(42, 70, f"Compared with completed close {close:.2f} on {evidence['price_date']}", size=13, color='#62748a')]
    for index, row in enumerate(evidence['methods']):
        y = 118 + index * 83
        value = float(row['value_per_share_decimal'])
        width = value / maximum * 820
        body += [_text(42, y+18, row['method'].replace('_', ' '), size=14, weight=700),
                 f'<rect x="220" y="{y}" width="{width:.1f}" height="28" rx="4" fill="#1d4ed8"/>',
                 _text(228+width, y+20, f'{value:.2f}', size=13, color='#1d4ed8', weight=700)]
    close_x = 220 + close / maximum * 820
    body += [f'<line x1="{close_x:.1f}" y1="100" x2="{close_x:.1f}" y2="350" stroke="#c34e55" stroke-width="3"/>',
             _text(close_x, 375, f'close {close:.2f}', size=12, color='#c34e55', weight=700, anchor='middle'),
             _text(42, 416, 'Assumption-driven methods are correlated sensitivities, not independent forecasts or a confidence interval.', size=12, color='#62748a')]
    return _svg(1100, 440, body)


def render(store, state):
    """Write charts inside this run and return Markdown references with lineage."""
    panel = next(((identity, store.get('evidence', identity)) for identity in state['evidence_ids']
                  if store.get('evidence', identity).get('kind') == 'comparison_panel'), None)
    if panel is None:
        return []
    panel_id, evidence = panel
    rows = evidence['data']['relative_strength']
    if not rows:
        return []
    date = rows[0]['price_date']
    prices = {}
    price_ids = {}
    wanted = {item['symbol'] for item in state['mandate']['watchlist']}
    for identity in state['evidence_ids']:
        item = store.get('evidence', identity)
        if item.get('adapter') == 'alpaca_daily' and item.get('data', {}).get('symbol') in wanted:
            symbol = item['data']['symbol']
            prices[symbol] = item['data']
            price_ids[symbol] = identity
    (store.root/'technical-relative-excess.svg').write_text(_relative_chart(rows, date))
    lines = ['', '### Deterministic technical charts', '',
             f'![Signed 5, 21 and 63-session excess price returns](technical-relative-excess.svg)', '',
             f'Comparison panel: [recorded evidence](evidence/{panel_id}.json). Positive is instrument outperformance; negative is underperformance.', '']
    if prices:
        (store.root/'technical-risk-context.svg').write_text(_risk_chart(prices, date))
        lines += ['![Dated return, volatility, drawdown and moving-average distance](technical-risk-context.svg)', '',
                  'Price evidence: '+', '.join(f'[{symbol}](evidence/{identity}.json)' for symbol, identity in price_ids.items())+'.', '']
    probability = next((item for identity in state['evidence_ids']
                        for item in [store.get('evidence', identity)]
                        if item.get('kind') == 'technical_probability_panel'), None)
    if probability:
        (store.root/'technical-forward-frequencies.svg').write_text(_probability_chart(probability['data']))
        lines += ['![Historical conditional and unconditional positive-return frequencies](technical-forward-frequencies.svg)', '',
                  probability['qualification'], '']
    valuation = next((item for identity in state['evidence_ids']
                      for item in [store.get('evidence', identity)]
                      if item.get('kind') == 'three_method_valuation'), None)
    if valuation:
        (store.root/'valuation-three-methods.svg').write_text(_valuation_chart(valuation))
        lines += ['![Three conditional valuation methods versus dated close](valuation-three-methods.svg)', '',
                  valuation['qualification'], '']
    paths, excluded = {}, {}
    for identity in state['source_cache'].values():
        item = store.get('evidence', identity)
        if item.get('adapter') == 'alpaca_daily' and item.get('document_id'):
            paths[item['data']['symbol']], excluded[item['data']['symbol']] = completed_bars(store, item)
    for item in state['mandate']['watchlist']:
        symbol, benchmark, sector = item['symbol'], item['benchmark'], item['sector_benchmark']
        if all(name in paths for name in (symbol, benchmark, sector)):
            filename = f'technical-{symbol}-path.svg'
            (store.root/filename).write_text(_path_chart(symbol, benchmark, sector, paths, excluded, date))
            lines += [f'![{symbol} indexed price path versus {benchmark} and {sector}, with volume]({filename})', '']
    lines += ['The indexed paths use archived OHLCV only through the normalized completed close; later/unfinished bars are excluded. The summary comparison and risk charts use the same admitted cutoff. These are historical observations, not forecasts or executable quotes.', '']
    return lines
