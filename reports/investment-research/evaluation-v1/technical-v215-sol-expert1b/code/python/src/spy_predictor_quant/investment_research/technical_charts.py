"""Deterministic SVG charts from admitted completed-session technical evidence."""

from decimal import Decimal, ROUND_HALF_UP
from html import escape


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
    width, height = 1100, 790
    zero, scale = 560, 24
    body = [_text(42, 46, 'Relative price performance', size=26, weight=700),
            _text(42, 73, f'Completed session ending {date} · instrument minus benchmark · percentage points', size=14, color='#62748a')]
    for tick in (-10, -5, 0, 5, 10):
        x = zero + tick * scale
        body += [f'<line x1="{x}" y1="106" x2="{x}" y2="728" stroke="{("#8290a2" if tick == 0 else "#e4e9ef")}" stroke-width="{(2 if tick == 0 else 1)}"/>',
                 _text(x, 96, f'{tick:+d}', size=12, color='#62748a', anchor='middle')]
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
            body += [_text(263, y + 12, horizon+' sessions', size=12, color='#62748a'),
                     f'<rect x="{left:.1f}" y="{y}" width="{width_bar:.1f}" height="16" rx="3" fill="{color}"/>',
                     _text(end + (8 if value >= 0 else -8), y + 13, _signed(value), size=12,
                           color=color, weight=700, anchor=('start' if value >= 0 else 'end'))]
        body.append(f'<line x1="42" y1="{top+92}" x2="1058" y2="{top+92}" stroke="#eef1f5"/>')
    body.append(_text(42, 763, 'Historical price-return comparisons only; no forecast, total return or causal attribution.', size=13, color='#62748a'))
    return _svg(width, height, body)


def _risk_chart(prices, date):
    width, height = 1100, 455
    metrics = [('return63_pct', '63-session return', -20, 20, True),
               ('realized_vol63_pct', '63-session vol.', 0, 100, False),
               ('drawdown_from_window_high_pct', '252-session drawdown', -30, 0, True),
               ('price_to_sma50', 'Close vs 50-day SMA', -10, 10, True)]
    body = [_text(42, 46, 'Trend and path risk snapshot', size=26, weight=700),
            _text(42, 73, f'Completed session ending {date} · split-adjusted price basis', size=14, color='#62748a')]
    for col, (_, label, low, high, _) in enumerate(metrics):
        x = 174 + col * 224
        body += [_text(x, 112, label, size=13, weight=700),
                 _text(x, 134, f'{low:+d} to {high:+d}%', size=11, color='#62748a')]
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
    body += [_text(42, 420, 'Volatility is annualized from the supplied 63-session window; drawdown uses the supplied 252-session high.', size=13, color='#62748a'),
             _text(42, 440, 'Different windows are shown separately. Historical variation and moving-average distance do not predict returns.', size=13, color='#62748a')]
    return _svg(width, height, body)


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
    lines += ['Charts use saved completed-session summary fields. The packet has no raw daily path or volume series, so these are snapshot charts rather than price, volume, or breakout-confirmation charts.', '']
    return lines
