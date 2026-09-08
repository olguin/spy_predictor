from __future__ import annotations

import math
from datetime import date

import pytest

from spy_predictor_quant.cycle_analysis_tools import (
    IDENTIFIABILITY_NOTICE,
    STATE_LABELS,
    CreditInputs,
    CycleStateObservation,
    ExposurePolicy,
    ExploratoryStateThresholds,
    LatentStateSpec,
    LevelObservation,
    NestedCycleConfig,
    NestedCycleObservation,
    SignedComponent,
    TopScoreConfig,
    calculate_credit_amplifier,
    calculate_cycle_architecture,
    calculate_cycle_top_score,
    calculate_dimension,
    classify_exploratory_states,
    compute_trailing_robust_scores,
    compute_trailing_structural_trend,
    decompose_embedded_expectations,
    diagnose_nested_cycles,
    evaluate_expectations_surprise,
    filter_latent_states,
    map_state_probabilities_to_exposure,
)


def _levels(count: int, *, bump_last: float = 0.0) -> list[LevelObservation]:
    values = []
    for index in range(count):
        level = math.exp(2.0 + 0.02 * index + (bump_last if index == count - 1 else 0.0))
        values.append(LevelObservation(date(2000 + index // 12, index % 12 + 1, 1), level))
    return values


def test_structural_trend_is_exact_for_log_linear_levels_and_averages_windows() -> None:
    result = compute_trailing_structural_trend(
        _levels(30), windows=(6, 12), minimum_scale_history=4
    )
    point = result[-1]
    assert set(point.component_log_trends) == {6, 12}
    assert math.isclose(point.average_log_trend or 0, point.log_level, abs_tol=1e-12)
    assert math.isclose(point.deviation or 0, 0.0, abs_tol=1e-12)
    assert point.robust_deviation is not None
    assert math.isclose(point.robust_deviation, 0.0, abs_tol=1e-7)
    assert point.history_end_index == 29
    assert result[10].average_log_trend is None


def test_structural_trend_outputs_are_cutoff_safe() -> None:
    prefix = compute_trailing_structural_trend(
        _levels(24), windows=(6, 12), scale_window=8, minimum_scale_history=4
    )
    extended = compute_trailing_structural_trend(
        _levels(36, bump_last=3.0), windows=(6, 12), scale_window=8, minimum_scale_history=4
    )
    assert prefix == extended[:24]


def test_structural_trend_rejects_implicit_or_invalid_horizons() -> None:
    with pytest.raises(ValueError, match="windows"):
        compute_trailing_structural_trend(_levels(5), windows=())
    with pytest.raises(ValueError, match="positive"):
        compute_trailing_structural_trend(
            [LevelObservation(date(2020, 1, 1), 0)], windows=(2,)
        )


def test_generic_robust_scaling_is_causal_and_preserves_unavailable_rows() -> None:
    prefix = compute_trailing_robust_scores(
        [None, 1.0, 2.0, 3.0, 4.0], window=3, minimum_history=3
    )
    extended = compute_trailing_robust_scores(
        [None, 1.0, 2.0, 3.0, 4.0, 1000.0], window=3, minimum_history=3
    )
    assert prefix == extended[: len(prefix)]
    assert prefix[0].robust_score is None
    assert prefix[2].robust_score is None
    assert math.isclose(prefix[3].trailing_center or 0, 2.0)
    assert prefix[4].robust_score is not None


def test_expectations_decomposition_is_an_identity_but_not_identified_sentiment() -> None:
    result = decompose_embedded_expectations(150, 100, space="log")
    assert math.isclose(result.sentiment_premium_proxy, math.log(1.5))
    assert math.isclose(result.relative_premium, 0.5)
    assert math.isclose(result.reconstructed_price, 150)
    assert result.identifiability == IDENTIFIABILITY_NOTICE
    level = decompose_embedded_expectations(150, 100, space="level")
    assert level.sentiment_premium_proxy == 50
    assert evaluate_expectations_surprise(98, 100).outcome == "NEGATIVE_SURPRISE"
    assert evaluate_expectations_surprise(2.0, 3.0, higher_is_better=False).outcome == "POSITIVE_SURPRISE"


def test_dimension_calculators_keep_weight_magnitude_separate_from_sign() -> None:
    score = calculate_dimension(
        "stress",
        (
            SignedComponent("spread", 0.8, 1, 2.0),
            SignedComponent("momentum", 0.4, -1, 1.0),
        ),
        score_meaning="higher=more_stress",
    )
    assert math.isclose(score.score, 0.4)
    assert score.contributions == {"spread": 1.6, "momentum": -0.4}
    with pytest.raises(ValueError, match="positive"):
        calculate_dimension(
            "bad", (SignedComponent("x", 1, 1, -1),), score_meaning="invalid"
        )


def test_four_part_cycle_architecture_keeps_dimensions_separate() -> None:
    architecture = calculate_cycle_architecture(
        macro=(SignedComponent("growth", 0.5, 1),),
        fundamental=(SignedComponent("valuation", 0.7, 1),),
        technical=(SignedComponent("momentum", 0.4, 1),),
        psychology_credit=(SignedComponent("spread", -0.6, -1),),
    )
    assert architecture.macro_cycle_location.score == 0.5
    assert architecture.fundamental_asset_quality_valuation.score == 0.7
    assert architecture.technical_timing.score == 0.4
    assert architecture.psychology_credit_risk_temperature.score == 0.6


def test_credit_amplifier_distinguishes_current_stress_from_latent_fragility() -> None:
    easy_boom = calculate_credit_amplifier(
        CreditInputs(
            spread_level=-0.8,
            spread_change=-0.4,
            lending_standards_tightness=-0.6,
            leverage_growth=0.9,
            underwriting_ease=0.8,
            default_rate=-0.7,
        )
    )
    assert easy_boom.credit_ease > 0
    assert easy_boom.current_stress < 0
    assert easy_boom.latent_fragility > 0
    assert easy_boom.risk_temperature > 0


def test_cycle_top_score_requires_exact_keys_positive_weights_and_explicit_signs() -> None:
    config = TopScoreConfig(
        weights={"price": 2.0, "country_risk": 1.0},
        signs={"price": 1, "country_risk": -1},
    )
    result = calculate_cycle_top_score({"price": 0.9, "country_risk": -0.6}, config)
    assert math.isclose(result.score, 0.8)
    assert result.interpretation.startswith("higher=")
    with pytest.raises(ValueError, match="same nonempty keys"):
        calculate_cycle_top_score({"price": 0.9}, config)
    with pytest.raises(ValueError, match="positive"):
        calculate_cycle_top_score(
            {"price": 0.9}, TopScoreConfig({"price": -1}, {"price": 1})
        )


def test_deterministic_exploratory_states_follow_frozen_precedence() -> None:
    observations = [
        CycleStateObservation(date(2020, 1, 1), -0.8, -0.8, 0.6),  # euphoria
        CycleStateObservation(date(2020, 2, 1), 0.0, 0.0, 0.0),  # normal
        CycleStateObservation(date(2020, 3, 1), -0.8, 0.0, 0.6),  # greed
        CycleStateObservation(date(2020, 4, 1), 0.8, 0.8, -0.6),  # crisis precedence
        CycleStateObservation(date(2020, 5, 1), -0.2, 0.1, -0.6),  # correction
        CycleStateObservation(date(2020, 6, 1), 0.0, 0.8, 0.0),
        CycleStateObservation(date(2020, 7, 1), 0.8, 0.5, 0.6),  # recovery vs Apr
    ]
    states = classify_exploratory_states(observations)
    assert [states[index].state for index in (0, 1, 2, 3, 4, 6)] == [
        "EUPHORIA", "NORMAL", "GREED", "CRISIS", "CORRECTION", "EARLY_RECOVERY"
    ]
    assert states[3].flags["formerlyExpensive"] is True
    assert states[6].flags["stressDeclining"] is True


def test_latent_state_filter_is_forward_only_and_probabilistic() -> None:
    states = (
        LatentStateSpec("CRISIS", (-1.0,), (0.4,)),
        LatentStateSpec("EUPHORIA", (1.0,), (0.4,)),
    )
    transition = ((0.9, 0.1), (0.1, 0.9))
    history = [{"temperature": -1.0}, {"temperature": -0.8}, {"temperature": 0.9}]
    prefix = filter_latent_states(
        history, feature_names=("temperature",), states=states, transition_matrix=transition
    )
    extended = filter_latent_states(
        history + [{"temperature": 10.0}],
        feature_names=("temperature",), states=states, transition_matrix=transition,
    )
    assert prefix == extended[: len(prefix)]
    assert prefix[0].most_likely_state == "CRISIS"
    assert prefix[-1].most_likely_state == "EUPHORIA"
    assert math.isclose(sum(prefix[-1].probabilities.values()), 1.0)
    with pytest.raises(ValueError, match="sum to one"):
        filter_latent_states(
            history, feature_names=("temperature",), states=states,
            transition_matrix=((0.8, 0.8), (0.1, 0.9)),
        )


def test_nested_cycle_diagnostics_are_causal_and_do_not_equate_correction_with_mega_end() -> None:
    observations = [
        NestedCycleObservation(date(2020, 1, 1), 100, 1.2, 0.5),
        NestedCycleObservation(date(2020, 2, 1), 110, 1.3, 0.5),
        NestedCycleObservation(date(2020, 3, 1), 95, 1.1, -0.5),
        NestedCycleObservation(date(2020, 4, 1), 104, 0.8, 0.6),
        NestedCycleObservation(date(2020, 5, 1), 111, 0.7, 0.5),
    ]
    prefix = diagnose_nested_cycles(observations)
    extended = diagnose_nested_cycles(
        observations + [NestedCycleObservation(date(2020, 6, 1), 80, -2, -1)]
    )
    assert prefix == extended[: len(prefix)]
    assert [point.minor_phase for point in prefix] == [
        "RALLY", "RALLY", "CORRECTION", "RECOVERY", "RALLY"
    ]
    assert prefix[2].megacycle_zone == "OVERVALUED"
    assert prefix[2].late_cycle_major_reversal_risk is True
    assert prefix[3].minor_cycle_number == 2


def test_exposure_mapping_is_probability_weighted_bounded_and_rate_limited() -> None:
    budgets = {
        "CRISIS": 0.9,
        "EARLY_RECOVERY": 0.8,
        "NORMAL": 0.5,
        "GREED": 0.3,
        "EUPHORIA": 0.1,
        "CORRECTION": 0.2,
    }
    probabilities = {name: 0.0 for name in STATE_LABELS}
    probabilities.update({"CRISIS": 0.7, "EARLY_RECOVERY": 0.3})
    mapped = map_state_probabilities_to_exposure(
        probabilities,
        ExposurePolicy(budgets, maximum_change=0.1),
        previous_budget=0.4,
    )
    assert math.isclose(mapped.unconstrained_budget, 0.87)
    assert math.isclose(mapped.risk_budget, 0.5)
    assert mapped.posture == "NEUTRAL"
    diffuse = {name: 1 / len(STATE_LABELS) for name in STATE_LABELS}
    fallback = map_state_probabilities_to_exposure(
        diffuse, ExposurePolicy(budgets, fallback_budget=0.45, minimum_confidence=0.6)
    )
    assert fallback.used_fallback is True
    assert fallback.risk_budget == 0.45


def test_custom_state_thresholds_are_accepted_but_explicit() -> None:
    thresholds = ExploratoryStateThresholds(expensive_valuation_maximum=-0.9)
    state = classify_exploratory_states(
        [CycleStateObservation(date(2020, 1, 1), -0.8, -0.8, 0.6)],
        thresholds=thresholds,
    )[0]
    assert state.state == "NORMAL"


def test_nested_cycle_config_rejects_nonpositive_structural_threshold() -> None:
    with pytest.raises(ValueError, match="valid positive"):
        diagnose_nested_cycles([], config=NestedCycleConfig(structural_extreme=0))
