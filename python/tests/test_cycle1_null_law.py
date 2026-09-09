from fractions import Fraction

import pytest

from spy_predictor_quant.cycle1_null_law import (
    MarkedKernel, Transition, audit_conditional_law, feedback_counterexample,
    partial_null_fixture,
)


def test_predictable_persistent_baseline_can_have_exact_partial_null():
    result = audit_conditional_law(partial_null_fixture())
    assert result['status'] == 'EXACT_FINITE_STATE_INFORMATION_NULL'
    assert result['sufficientAllHorizonCondition'] is True
    assert result['targetLaws']['low:0'] == result['targetLaws']['low:1']
    assert result['targetLaws']['high:0'] != result['targetLaws']['low:0']
    for law in result['targetLaws'].values():
        assert sum(map(Fraction, law.values())) == 1
    assert result['falseQualificationRateEstimated'] is False


def test_one_step_null_does_not_establish_annual_null_under_feedback():
    short = audit_conditional_law(feedback_counterexample(), 1)
    annual = audit_conditional_law(feedback_counterexample(), 12)
    assert short['status'] == 'EXACT_FINITE_STATE_INFORMATION_NULL'
    assert short['sufficientAllHorizonCondition'] is False
    assert annual['status'] == 'EXTRA_STATE_CONTAINS_TARGET_INFORMATION'
    assert annual['targetLaws']['A'] == {'11': '1'}
    assert annual['targetLaws']['B'] == {'-11': '1'}
    assert annual['statePairs'][0]['annualTotalVariation'] == '1'


def test_equal_means_do_not_establish_equal_return_distributions():
    kernel = MarkedKernel({'A': 'same', 'B': 'same'}, {
        'A': (Transition('A', 1, Fraction(1, 2)), Transition('A', -1, Fraction(1, 2))),
        'B': (Transition('B', 2, Fraction(1, 2)), Transition('B', -2, Fraction(1, 2))),
    })
    result = audit_conditional_law(kernel)
    for law in result['targetLaws'].values():
        assert sum(int(reward) * Fraction(mass) for reward, mass in law.items()) == 0
    assert result['status'] == 'EXTRA_STATE_CONTAINS_TARGET_INFORMATION'


def test_null_law_is_deterministic_without_random_streams(monkeypatch):
    import numpy as np
    def forbidden(*args, **kwargs):
        raise AssertionError('No random draws belong in algebraic fixtures')
    monkeypatch.setattr(np.random, 'default_rng', forbidden)
    assert audit_conditional_law(partial_null_fixture()) == audit_conditional_law(partial_null_fixture())


@pytest.mark.parametrize('bad_row', [
    (Transition('A', 1, Fraction(1, 2)),),
    (Transition('unknown', 1, Fraction(1)),),
    (Transition('A', 1.0, Fraction(1)),),
    (Transition('A', 1, 1.0),),
    (Transition('A', 1, Fraction(2)), Transition('A', 0, Fraction(-1))),
])
def test_invalid_transition_tables_are_rejected(bad_row):
    with pytest.raises(ValueError):
        audit_conditional_law(MarkedKernel({'A': 'same', 'B': 'same'},
                                          {'A': bad_row, 'B': (Transition('B', 0, Fraction(1)),)}))
