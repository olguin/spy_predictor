import pytest

from spy_predictor_quant.development_diagnostics import summarize, validate_calendar


def test_coverage_bias_and_probability_hand_calculation():
    result = summarize([{'status': 'SCORED', 'samples': [-1, 0, 1, 2], 'outcome': 1,
                         'crps': .5, 'squaredError': .25}, {'status': 'UNAVAILABLE'}])
    assert result['scheduled'] == 2 and result['scored'] == 1
    assert result['meanForecastMinusOutcome'] == -.5
    assert result['coverage50'] == result['coverage90'] == 1
    assert result['meanWidth90'] == 3
    assert result['positiveExcessReturnBrier'] == .25
    assert result['pitHistogramFiveBins'] == [0, 0, 0, 1, 0]


def test_all_missing_remains_unavailable():
    assert summarize([{'status': 'UNAVAILABLE'}]) == {'scheduled': 1, 'scored': 0}


def test_final_period_cannot_be_used_as_development():
    with pytest.raises(ValueError, match='development-only'):
        validate_calendar([{'date': '2017-07-31', 'mode': 'expanding', 'modelId': 'unconditional-history'}])
