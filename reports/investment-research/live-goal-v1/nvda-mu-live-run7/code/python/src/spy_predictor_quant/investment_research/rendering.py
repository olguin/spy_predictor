"""Render recorded numeric values and source periods without model regeneration."""
import json


def condition_line(store, condition):
    if condition['kind'] == 'human_review':
        return '- Human review: ' + condition['description']
    dates = []
    for identity in condition.get('evidence_ids', []):
        evidence = store.get('evidence', identity)
        dates.append(str((evidence.get('data') or {}).get('price_date') or evidence.get('published_at') or 'unknown') + ' / retrieved ' + str(evidence.get('retrieved_at') or 'unknown'))
    return (f"- Completed-close review: {condition['symbol']} {condition['operator']} "
            f"{condition['threshold_decimal']} ({condition['price_basis']}); expires {condition['expires_at']}; "
            f"evidence dates: {', '.join(dates) or 'unknown'}. {condition['description']} — not an executable order.")


def numerical_lines(store, identities, *, withdrawn_symbols=()):
    lines = ['', '## Validated numerical evidence', '',
        'Values below come directly from stored evidence. Open each source for full lineage and fields.', '']
    for identity in identities:
        e = store.get('evidence', identity); d = e.get('data'); adapter = e.get('adapter')
        if e['kind'] == 'scenario_grid':
            if e['symbol'] in withdrawn_symbols:
                continue
            lines += [f"### {e['symbol']} conditional valuation sensitivity", '',
                f"Assumed earnings period: {e['earnings_period_start']} to {e['earnings_period_end']} · {e['accounting_basis']} · {e['share_basis']}", '',
                f"Reference close: {e['observed_close_decimal']} on {e['price_date']}", '',
                '| Case | Assumed EPS | Assumed P/E | Scenario price | Change from dated close (%) |',
                '|---|---:|---:|---:|---:|']
            for row in e['cases']:
                lines.append(f"| {row['case']} | {row['earnings_per_share']} | {row['pe_multiple']} | {row['scenario_price_decimal']} | {row['change_from_close_pct_decimal']} |")
            lines += ['', e['assumptions'], '', e['qualification'], '']
            lines += [f"- {r['case']}: {r['rationale']}" for r in e['cases']]
            continue
        if e['kind'] == 'three_method_valuation':
            lines += [f"### {e['symbol']} three-method valuation", '',
                f"Reference close: {e['observed_close_decimal']} on {e['price_date']}", '',
                '| Method | Conditional value/share | Change from dated close (%) |',
                '|---|---:|---:|']
            for row in e['methods']:
                lines.append(f"| {row['method']} | {row['value_per_share_decimal']} | {row['change_from_close_pct_decimal']} |")
            lines += ['', (f"Range: {e['range']['low_value_per_share_decimal']} to "
                           f"{e['range']['high_value_per_share_decimal']}; median "
                           f"{e['range']['median_value_per_share_decimal']}."), '',
                      e['assumptions'], '', e['qualification'], '']
            continue
        if e['kind'] == 'technical_probability_panel':
            lines += [f"### {e['data']['symbol']} historical forward-return frequencies", '',
                f"As of {e['data']['as_of']} · analog window {e['data']['lookback_start']} to {e['data']['lookback_end']}", '',
                f"Current regime: `{json.dumps(e['data']['regime'], sort_keys=True)}`", '',
                '| Horizon | Conditional n | Positive frequency | Median | 10th / 90th pct | Unconditional positive frequency |',
                '|---:|---:|---:|---:|---:|---:|']
            for horizon, row in e['data']['horizons'].items():
                conditional = row['conditional_current_regime']; base = row['unconditional_base_rate']
                lines.append(f"| {horizon} | {conditional['sample_size']} | {conditional['positive_return_frequency_pct']}% | "
                    f"{conditional['median_forward_return_pct']}% | {conditional['p10_forward_return_pct']}% / "
                    f"{conditional['p90_forward_return_pct']}% | {base['positive_return_frequency_pct']}% (n={base['sample_size']}) |")
            lines += ['', e['qualification'], '']
            continue
        if e['kind'] == 'analyst_consensus_snapshot':
            lines += [f"### {e['symbols'][0]} analyst consensus snapshot", '',
                f"Page last updated: {d['page_last_updated']} · retrieved {e.get('retrieved_at')}", '',
                '| Item | Value |', '|---|---:|',
                f"| Average recommendation | {d['average_recommendation']} |",
                f"| Ratings | {d['ratings_count']} |",
                f"| Average target price | {d['average_target_price']} |",
                f"| Current-quarter EPS estimate | {d['current_quarter_estimate']} |",
                f"| Current-fiscal EPS estimate | {d['current_fiscal_year_estimate']} |",
                f"| Next-fiscal EPS estimate | {d['next_fiscal_year_estimate']} |", '',
                e['qualification'], '']
            continue
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
            for m in d.get('earnings_periods', {}).get('annual', []):
                lines.append(f"| annual diluted EPS anchor | {m['value']} | {m['unit']} | {m['start']} | {m['end']} | {m['filed']} |")
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
