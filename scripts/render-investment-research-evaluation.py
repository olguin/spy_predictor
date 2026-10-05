"""Render an accepted evaluation's final response without regenerating analysis."""
import argparse
from pathlib import Path

from spy_predictor_quant.investment_research.rendering import numerical_lines
from spy_predictor_quant.investment_research.store import Store


def render(root):
    store = Store(root)
    state = store.load()
    if state['status'] != 'EVALUATION_COMPLETE':
        raise ValueError('A completed development evaluation is required')
    final = next(t for t in state['tasks'] if t['stage'] == 'final' and t['status'] == 'COMPLETE')
    result = final['result']
    registration = store.get('registrations', state['evaluation']['registration_id'])
    lines = ['# ' + ', '.join(r['symbol'] for r in result['instruments']) + ' — research draft', '',
             'Archived development evaluation; no publication or new source refresh.', '',
             f"Evidence cutoff: {registration['evidence_cutoff']}" if 'evidence_cutoff' in registration else
             'The fixed evidence date is recorded in the [experiment registration](registrations/' + state['evaluation']['registration_id'] + '.json).', '',
             'Quality results: [independent review](independent-review.md). '
             'A completed report does not by itself mean the whole-team quality target passed.', '',
             result['summary'], '']
    for row in result['instruments']:
        lines += ['## ' + row['symbol'], '',
                  '**Overall preference assessment:** ' + row['assessment'].replace('_', ' '), '',
                  '**Thesis and demand drivers**', '', row['thesis'], '',
                  '**Valuation assumptions and interpretation**', '', row['valuation'], '',
                  '**Downside and counter-case**', '', row['counter_thesis'], '',
                  '**What would change the assessment**', '']
        for c in row['review_conditions']:
            prefix = (f"{c['symbol']} completed close {c['operator']} {c['threshold_decimal']} "
                      f"({c['price_basis']}; expires {c['expires_at']}): ") if c['kind'] == 'completed_close' else ''
            lines += ['- ' + prefix + c['description']]
        if row.get('etf_lookthrough'):
            lines += ['', '**Dated fund exposure**', '', row['etf_lookthrough']]
        lines += ['', '| Conclusion | Status | Interpretation |', '|---|---|---|']
        for key, dimension in row.get('dimensions', {}).items():
            value = (dimension['conclusion'] + ' ' + dimension['qualification']).replace('|', '\\|').replace('\n', ' ')
            lines += [f"| {key.replace('_', ' ')} | {dimension['status'].replace('_', ' ')} | {value} |"]
        lines += ['']
    grids = [i for i in state['evidence_ids'] if store.get('evidence', i).get('kind') == 'scenario_grid']
    lines += numerical_lines(store, grids)
    lines += ['', '## Review record', '',
              'Full specialist findings, cited evidence, objections and dispositions are in the '
              '[evaluation report](evaluation-report.md) and [saved state](state.json). '
              'The tables above reproduce recorded calculations; all EPS and multiple assumptions '
              'remain those chosen in this run. No probability, price target or expected return is inferred.', '']
    target = root / 'final-research-draft.md'
    target.write_text('\n'.join(lines))
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='Completed evaluation directory')
    print(render(parser.parse_args().output))
