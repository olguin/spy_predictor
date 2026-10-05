"""Deterministic acceptance checks for technical comparison statements."""

from copy import deepcopy

import pytest

from spy_predictor_quant.investment_research.technical_signs import validate_technical_signs
from spy_predictor_quant.investment_research.technical_charts import render as render_charts


class EvidenceStore:
    def get(self, kind, identity):
        assert (kind, identity) == ('evidence', 'panel')
        return {'kind': 'comparison_panel', 'adapter': 'research_comparisons_v1',
                'data': {'relative_strength': [{
                    'symbol': 'QQQ', 'benchmark': 'SPY',
                    'excess_price_return_percentage_points': {
                        '5': '1.25922037088669336',
                        '21': '1.7082289559087527',
                        '63': '-4.5904074189895726'}}]}}


def findings():
    return {'summary': 'QQQ led SPY at five and 21 sessions but lagged at 63.',
            'counter_thesis': 'A short rebound does not establish 63-session leadership.',
            'claims': [{'text': 'PAIR QQQ/SPY 5=+1.2592 21=+1.7082 63=-4.5904',
                        'evidence_ids': ['panel'], 'symbols': ['QQQ']}],
            'review_conditions': []}


def task(version='investment-research/v2.15'):
    return {'role': 'technical', 'prompt_version': version, 'visible_evidence_ids': ['panel']}


def test_signed_pair_values_are_checked_against_calculated_panel():
    validate_technical_signs(EvidenceStore(), task(), findings())
    wrong = findings()
    wrong['claims'][0]['text'] = 'PAIR QQQ/SPY 5=-1.2592 21=+1.7082 63=-4.5904'
    with pytest.raises(ValueError, match='sign/value contradicts panel'):
        validate_technical_signs(EvidenceStore(), task(), wrong)


def test_original_all_window_contradiction_is_rejected_even_for_older_prompt():
    wrong = findings()
    wrong['summary'] = 'QQQ lagged SPY at all matched windows, including 63 sessions.'
    with pytest.raises(ValueError, match='All-window technical direction contradicts panel'):
        validate_technical_signs(EvidenceStore(), task('investment-research/v2.13'), wrong)


def test_other_benchmark_lag_does_not_poison_correct_all_window_pair():
    class MixedStore(EvidenceStore):
        def get(self, kind, identity):
            panel = super().get(kind, identity)
            panel['data']['relative_strength'].append({
                'symbol': 'NVDA', 'benchmark': 'QQQ',
                'excess_price_return_percentage_points': {
                    '5': '0.9042272696998310', '21': '1.4150038115835928',
                    '63': '8.0845985883738256'}})
            return panel

    correct = findings()
    correct['claims'][0]['text'] += '; PAIR NVDA/QQQ 5=+0.9042 21=+1.4150 63=+8.0846; NVDA led QQQ at all three measured windows, but lagged XLK at 21 sessions.'
    correct['claims'][0]['symbols'].append('NVDA')
    validate_technical_signs(MixedStore(), task(), correct)


def test_new_prompt_requires_source_linked_pair_rows():
    missing = findings()
    missing['claims'] = []
    with pytest.raises(ValueError, match='need exact signed PAIR rows'):
        validate_technical_signs(EvidenceStore(), task(), missing)
    unlinked = deepcopy(findings())
    unlinked['claims'][0]['evidence_ids'] = []
    with pytest.raises(ValueError, match='lacks comparison evidence'):
        validate_technical_signs(EvidenceStore(), task(), unlinked)


def test_charts_render_saved_comparisons_without_inventing_a_price_path(tmp_path):
    class ChartStore(EvidenceStore):
        root = tmp_path

        def get(self, kind, identity):
            if identity == 'panel':
                panel = super().get(kind, identity)
                panel['data']['relative_strength'][0]['price_date'] = '2026-09-18'
                return panel
            assert identity == 'qqq-price'
            return {'adapter': 'alpaca_daily', 'data': {'symbol': 'QQQ',
                    'return63_pct': -2.5884, 'realized_vol63_pct': 20.8494,
                    'drawdown_from_window_high_pct': -3.3116, 'price_to_sma50': 1.0162}}

    state = {'evidence_ids': ['panel', 'qqq-price'], 'source_cache': {},
             'mandate': {'watchlist': [{'symbol': 'QQQ', 'benchmark': 'SPY', 'sector_benchmark': 'XLK'}]}}
    lines = render_charts(ChartStore(), state)
    chart = (tmp_path/'technical-relative-excess.svg').read_text()
    risk = (tmp_path/'technical-risk-context.svg').read_text()
    assert '+1.26' in chart and '+1.71' in chart and '-4.59' in chart
    assert 'QQQ / SPY' in chart and '-2.6%' in risk and '20.8%' in risk
    assert any('summary comparison and risk charts' in line for line in lines)
