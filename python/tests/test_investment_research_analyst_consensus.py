from spy_predictor_quant.investment_research.analyst_consensus import extract
from spy_predictor_quant.investment_research.controller import Controller


HTML = """
<main>Last Updated: Sep 22, 2026, 3:59 PM EDT
Snapshot Average Recommendation BUY Average Target Price 249.966
Number of Ratings 34 Current Quarters Estimate 1.077
Current Year's Estimate 4.108 Next Fiscal Year Estimate 5.228
Earnings Per Share This Quarter Next Quarter This Fiscal Next Fiscal
# of Estimates 26 25 29 29 Mean Estimate 1.08 1.15 4.11 5.23
High Estimates 1.11 1.24 4.24 6.53 Low Estimate 1.0571 1.09 3.94 4.66
Analysts Recommendations Current 1 Month Ago 3 Months Ago
BUY 31 31 29 OVERWEIGHT 2 3 2 HOLD 1 0 1 UNDERWEIGHT 0 0 0 SELL 0 0 0
</main>
"""


def test_extracts_labelled_consensus_without_inferring_accounting_basis():
    result = extract(HTML)
    assert result['average_target_price'] == '249.966'
    assert result['eps_table']['this_fiscal'] == {
        'estimate_count': 29, 'mean': '4.11', 'high': '4.24', 'low': '3.94'}
    assert result['current_recommendations'] == {
        'buy': 31, 'overweight': 2, 'hold': 1, 'underweight': 0, 'sell': 0}


def test_missing_required_label_returns_none():
    assert extract(HTML.replace('Average Target Price', 'Target')) is None


def test_review_and_final_receive_only_synthesis_dependencies():
    complete = lambda task_id, role, stage: {
        'task_id': task_id, 'role': role, 'stage': stage, 'status': 'COMPLETE', 'result': {}}
    state = {'tasks': [complete('i', 'challenger', 'independent'),
        complete('c', 'company', 'research'), complete('d', 'director', 'draft'),
        complete('r', 'challenger', 'review')]}
    review = {'stage': 'review', 'round': 0}
    final = {'stage': 'final', 'round': 0}
    assert [row['task_id'] for row in Controller.prior_results(state, review)] == ['i', 'd']
    assert [row['task_id'] for row in Controller.prior_results(state, final)] == ['d', 'r']
