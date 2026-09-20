"""Render recorded numeric values and source periods without model regeneration."""
import json


def numerical_lines(store, identities):
    lines = ['', '## Validated numerical evidence', '',
        'Values below come directly from stored evidence. Open each source for full lineage and fields.', '']
    for identity in identities:
        e = store.get('evidence', identity); d = e.get('data'); adapter = e.get('adapter')
        if d is None and e['kind'] != 'calculation':
            continue
        lines += [f"### [{e.get('source_id', identity[:12])}](evidence/{identity}.json)", '']
        if e['kind'] == 'calculation':
            lines += [f"`{e['formula']}` = **{e['result_decimal']}** {e['units']}", '', e['assumptions'], '', e['qualification'], '']
        elif adapter == 'alpaca_daily':
            lines += [f"{d['symbol']} · {d['price_date']} · {d['status']} · {d['feed']} · {d['adjustment']} · price return", '',
                '| Metric | Recorded value |', '|---|---:|']
            for key in ('latest_close', 'sma20', 'sma50', 'sma200', 'rsi14_simple', 'return5_pct', 'return21_pct', 'return63_pct', 'realized_vol63_pct'):
                lines.append(f'| {key} | {d[key]} |')
        elif adapter == 'sec_companyfacts':
            lines += ['| Metric | Value | Unit | Period start | Period end | Filed |', '|---|---:|---|---|---|---|']
            for key, m in d.get('metrics', {}).items():
                lines.append(f"| {key} ({m['concept']}) | {m['value']} | {m['unit']} | {m.get('start') or 'instant'} | {m['end']} | {m['filed']} |")
            lines += ['', 'Fiscal durations are not silently annualized; debt concepts may cover only current maturities.']
        elif adapter == 'etf_profile':
            lines += [f"As of {d['as_of']} · {d['status']}", '', '| Sponsor metric | Value | Metric date |', '|---|---:|---|']
            for key, value in d['metrics'].items():
                lines.append(f"| {key} | {value} | {d.get('metric_as_of', {}).get(key, d['as_of'])} |")
        elif adapter == 'etf_holdings':
            lines += [f"As of {d['as_of']} · {d['status']} · {d['holdings_count']} supplied holdings", '',
                f"Reported coverage: {d['reported_weight_pct']}%; top ten: {d['top10_weight_pct']}%.", '', d['limitations']]
        elif adapter == 'research_comparisons_v1':
            lines += ['| Symbol | Benchmark | Date | Status | Excess 5 / 21 / 63 sessions (pp) |', '|---|---|---|---|---:|']
            for row in d['relative_strength']:
                values = row['excess_price_return_percentage_points']
                lines.append(f"| {row['symbol']} | {row['benchmark']} | {row['price_date']} | {row['status']} | {values['5']} / {values['21']} / {values['63']} |")
            for row in d['etf_lookthrough']:
                lines += ['', f"{row['fund']} selected-company weights at {row['as_of']} ({row['status']}): `{json.dumps(row['selected_company_weights'])}`", '', row['qualification']]
            lines += ['', 'Comparison gaps: `' + json.dumps(d['gaps']) + '`']
        else:
            lines += ['Full normalized fields are available through the evidence link.']
        lines.append('')
    return lines
