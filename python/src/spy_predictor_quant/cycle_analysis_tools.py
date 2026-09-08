"""Cutoff-safe exploratory tools for structural and nested cycle analysis.

These utilities are an independent quantitative formalization of public cycle
concepts.  They are not Maru Cape's proprietary method and are deliberately
separate from the frozen CYCLE-ASYMMETRY-001 candidate set.  In particular,
the latent-state filter in this module is diagnostic only and is not a Cycle 1
model.

Every time-series function is causal: output at index ``t`` only uses inputs at
indices ``<= t``.  Callers remain responsible for supplying point-in-time-safe
observations (for example, macro vintages released by the observation cutoff).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from statistics import median
from typing import Mapping, Sequence

import numpy as np

from spy_predictor_quant.cycle1_states import assign_cycle_states


EXPLORATORY_NOTICE = (
    "EXPLORATORY_DIAGNOSTIC_NOT_PART_OF_FROZEN_CYCLE1_AND_NOT_INVESTMENT_ADVICE"
)
IDENTIFIABILITY_NOTICE = (
    "EXPECTED_FUNDAMENTALS_ARE_AN_INPUT_PROXY; THE_RESIDUAL_IS_NOT_IDENTIFIED_SENTIMENT"
)
STATE_LABELS = (
    "CRISIS",
    "EARLY_RECOVERY",
    "NORMAL",
    "GREED",
    "EUPHORIA",
    "CORRECTION",
)

__all__ = [
    "EXPLORATORY_NOTICE",
    "IDENTIFIABILITY_NOTICE",
    "STATE_LABELS",
    "CreditAmplifierMetrics",
    "CreditInputs",
    "CycleArchitecture",
    "CycleStateObservation",
    "CycleTopScore",
    "DimensionScore",
    "ExpectationsDecomposition",
    "ExpectationsSurprise",
    "ExposureMapping",
    "ExposurePolicy",
    "ExploratoryStateResult",
    "ExploratoryStateThresholds",
    "LatentStateEstimate",
    "LatentStateSpec",
    "LevelObservation",
    "NestedCycleConfig",
    "NestedCycleDiagnostic",
    "NestedCycleObservation",
    "RobustScalePoint",
    "SignedComponent",
    "StructuralTrendPoint",
    "TopScoreConfig",
    "calculate_credit_amplifier",
    "calculate_cycle_architecture",
    "calculate_cycle_top_score",
    "calculate_dimension",
    "calculate_fundamental_quality_valuation",
    "calculate_macro_cycle_location",
    "calculate_psychology_credit_risk_temperature",
    "calculate_technical_timing",
    "classify_exploratory_states",
    "compute_trailing_structural_trend",
    "compute_trailing_robust_scores",
    "decompose_embedded_expectations",
    "diagnose_nested_cycles",
    "evaluate_expectations_surprise",
    "filter_latent_states",
    "map_state_probabilities_to_exposure",
]


def _finite(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("Cannot average an empty collection")
    return sum(values) / len(values)


def _clip_unit(value: float) -> float:
    return min(1.0, max(-1.0, value))


@dataclass(frozen=True)
class LevelObservation:
    """A positive level known at ``as_of``; use a real level when appropriate."""

    as_of: date | datetime
    level: float


@dataclass(frozen=True)
class StructuralTrendPoint:
    """Trailing structural log-trend result for one observation cutoff."""

    as_of: date | datetime
    log_level: float
    component_log_trends: Mapping[int, float]
    average_log_trend: float | None
    deviation: float | None
    trailing_deviation_center: float | None
    trailing_deviation_scale: float | None
    robust_deviation: float | None
    history_end_index: int
    notice: str = EXPLORATORY_NOTICE


def compute_trailing_structural_trend(
    observations: Sequence[LevelObservation],
    *,
    windows: Sequence[int],
    scale_window: int | None = None,
    minimum_scale_history: int = 12,
    mad_consistency_factor: float = 1.4826,
    mad_floor: float = 1e-9,
) -> list[StructuralTrendPoint]:
    """Estimate causal Theil-Sen log trends and their explicit-window average.

    For each configured window, the fitted value at ``t`` uses only that
    trailing window ending at ``t``. ``average_log_trend`` is the arithmetic
    mean of all configured component trends; it is unavailable until every
    window is available. The deviation is exactly ``log(level) - average``.
    Its robust score uses only deviations that were themselves available at
    their historical cutoffs.

    ``windows`` is required so research code cannot silently choose a favorable
    trend horizon.  Supply observations in strict chronological order.
    """

    if not observations:
        return []
    chosen_windows = tuple(int(value) for value in windows)
    if not chosen_windows or len(set(chosen_windows)) != len(chosen_windows):
        raise ValueError("windows must contain unique explicit values")
    if any(value < 2 for value in chosen_windows):
        raise ValueError("Every structural trend window must be at least two")
    chosen_scale_window = int(scale_window) if scale_window is not None else None
    if chosen_scale_window is not None and chosen_scale_window < 2:
        raise ValueError("scale_window must be at least two or None")
    if minimum_scale_history < 2:
        raise ValueError("minimum_scale_history must be at least two")
    if chosen_scale_window is not None and chosen_scale_window < minimum_scale_history:
        raise ValueError("scale_window cannot be shorter than minimum_scale_history")
    consistency = _finite(mad_consistency_factor, "mad_consistency_factor")
    floor = _finite(mad_floor, "mad_floor")
    if consistency <= 0 or floor <= 0:
        raise ValueError("MAD consistency and floor must be positive")

    previous: date | datetime | None = None
    log_levels: list[float] = []
    for observation in observations:
        level = _finite(observation.level, "level")
        if level <= 0:
            raise ValueError("Structural trend levels must be positive")
        if previous is not None and observation.as_of <= previous:
            raise ValueError("observations must be in strict chronological order")
        previous = observation.as_of
        log_levels.append(math.log(level))

    deviations: list[float] = []
    result: list[StructuralTrendPoint] = []
    for index, observation in enumerate(observations):
        components: dict[int, float] = {}
        for window in chosen_windows:
            if index + 1 >= window:
                components[window] = _theil_sen_endpoint(log_levels[index - window + 1 : index + 1])
        average = _mean(tuple(components.values())) if len(components) == len(chosen_windows) else None
        deviation = log_levels[index] - average if average is not None else None
        center: float | None = None
        scale: float | None = None
        score: float | None = None
        if deviation is not None:
            deviations.append(deviation)
            scaling_history = deviations[-chosen_scale_window:] if chosen_scale_window is not None else deviations
            if len(scaling_history) >= minimum_scale_history:
                center = median(scaling_history)
                scale = max(
                    floor,
                    consistency * median(abs(value - center) for value in scaling_history),
                )
                score = (deviation - center) / scale
        result.append(
            StructuralTrendPoint(
                as_of=observation.as_of,
                log_level=log_levels[index],
                component_log_trends=components,
                average_log_trend=average,
                deviation=deviation,
                trailing_deviation_center=center,
                trailing_deviation_scale=scale,
                robust_deviation=score,
                history_end_index=index,
            )
        )
    return result


def _theil_sen_endpoint(log_values: Sequence[float]) -> float:
    slopes = [
        (log_values[right] - log_values[left]) / (right - left)
        for left in range(len(log_values))
        for right in range(left + 1, len(log_values))
    ]
    slope = median(slopes)
    intercept = median(value - slope * index for index, value in enumerate(log_values))
    return intercept + slope * (len(log_values) - 1)


@dataclass(frozen=True)
class RobustScalePoint:
    """A causal median/MAD score aligned to one input index."""

    index: int
    value: float | None
    trailing_center: float | None
    trailing_scale: float | None
    robust_score: float | None


def compute_trailing_robust_scores(
    values: Sequence[float | None],
    *,
    window: int | None = None,
    minimum_history: int = 12,
    mad_consistency_factor: float = 1.4826,
    mad_floor: float = 1e-9,
) -> list[RobustScalePoint]:
    """Robustly normalize a series using only values observed through ``t``.

    ``None`` is preserved as unavailable and is not added to history. ``window``
    counts available observations rather than calendar periods. Callers needing
    a calendar window should first create the corresponding cutoff-safe slice.
    """

    chosen_window = int(window) if window is not None else None
    if minimum_history < 2:
        raise ValueError("minimum_history must be at least two")
    if chosen_window is not None and chosen_window < minimum_history:
        raise ValueError("window cannot be shorter than minimum_history")
    consistency = _finite(mad_consistency_factor, "mad_consistency_factor")
    floor = _finite(mad_floor, "mad_floor")
    if consistency <= 0 or floor <= 0:
        raise ValueError("MAD consistency and floor must be positive")
    history: list[float] = []
    output: list[RobustScalePoint] = []
    for index, raw_value in enumerate(values):
        if raw_value is None:
            output.append(RobustScalePoint(index, None, None, None, None))
            continue
        value = _finite(raw_value, f"values[{index}]")
        history.append(value)
        active = history[-chosen_window:] if chosen_window is not None else history
        center: float | None = None
        scale: float | None = None
        score: float | None = None
        if len(active) >= minimum_history:
            center = median(active)
            scale = max(floor, consistency * median(abs(item - center) for item in active))
            score = (value - center) / scale
        output.append(RobustScalePoint(index, value, center, scale, score))
    return output


@dataclass(frozen=True)
class ExpectationsDecomposition:
    """Accounting decomposition whose residual is only a sentiment proxy."""

    price: float
    expected_fundamentals_proxy: float
    sentiment_premium_proxy: float
    reconstructed_price: float
    space: str
    relative_premium: float
    identifiability: str = IDENTIFIABILITY_NOTICE
    notice: str = EXPLORATORY_NOTICE


def decompose_embedded_expectations(
    price: float,
    expected_fundamentals_proxy: float,
    *,
    space: str = "log",
) -> ExpectationsDecomposition:
    """Decompose price into an expected-fundamentals proxy and a residual.

    In ``log`` space the identity is ``log(P) = log(F_proxy) + residual``;
    ``relative_premium`` is ``P/F_proxy - 1``. In ``level`` space it is
    ``P = F_proxy + residual``. Neither identity observes expectations or
    identifies causal sentiment: the fundamentals term must be supplied by the
    caller and the residual can include misspecification and omitted risks.
    """

    price_value = _finite(price, "price")
    fundamentals = _finite(expected_fundamentals_proxy, "expected_fundamentals_proxy")
    if price_value <= 0 or fundamentals <= 0:
        raise ValueError("price and expected_fundamentals_proxy must be positive")
    if space not in {"log", "level"}:
        raise ValueError("space must be 'log' or 'level'")
    if space == "log":
        transformed_price = math.log(price_value)
        transformed_fundamentals = math.log(fundamentals)
        premium = transformed_price - transformed_fundamentals
        reconstructed = math.exp(transformed_fundamentals + premium)
    else:
        premium = price_value - fundamentals
        reconstructed = fundamentals + premium
    return ExpectationsDecomposition(
        price=price_value,
        expected_fundamentals_proxy=fundamentals,
        sentiment_premium_proxy=premium,
        reconstructed_price=reconstructed,
        space=space,
        relative_premium=price_value / fundamentals - 1.0,
    )


@dataclass(frozen=True)
class ExpectationsSurprise:
    actual_result: float
    embedded_expectation_proxy: float
    signed_gap: float
    outcome: str
    identifiability: str = IDENTIFIABILITY_NOTICE


def evaluate_expectations_surprise(
    actual_result: float,
    embedded_expectation_proxy: float,
    *,
    higher_is_better: bool = True,
    equality_tolerance: float = 0.0,
) -> ExpectationsSurprise:
    """Compare an actual result with a caller-supplied expectation proxy."""

    actual = _finite(actual_result, "actual_result")
    expected = _finite(embedded_expectation_proxy, "embedded_expectation_proxy")
    tolerance = _finite(equality_tolerance, "equality_tolerance")
    if tolerance < 0:
        raise ValueError("equality_tolerance cannot be negative")
    gap = (actual - expected) * (1 if higher_is_better else -1)
    outcome = "IN_LINE" if abs(gap) <= tolerance else ("POSITIVE_SURPRISE" if gap > 0 else "NEGATIVE_SURPRISE")
    return ExpectationsSurprise(actual, expected, gap, outcome)


@dataclass(frozen=True)
class SignedComponent:
    """A normalized input with an explicit, separate economic direction."""

    name: str
    value: float
    economic_sign: int
    weight: float = 1.0


@dataclass(frozen=True)
class DimensionScore:
    name: str
    score: float
    score_meaning: str
    contributions: Mapping[str, float]
    total_weight: float
    notice: str = EXPLORATORY_NOTICE


def calculate_dimension(
    name: str,
    components: Sequence[SignedComponent],
    *,
    score_meaning: str,
    clip_to_unit: bool = True,
) -> DimensionScore:
    """Calculate a weighted dimension with positive weights and explicit signs.

    Input values should already be cutoff-safe normalized scores. Negative
    weights are forbidden: direction belongs solely in ``economic_sign`` and
    must be exactly ``-1`` or ``1``. This prevents accidental double-negation.
    """

    if not name.strip() or not score_meaning.strip() or not components:
        raise ValueError("name, score_meaning, and components are required")
    names = [component.name for component in components]
    if len(set(names)) != len(names) or any(not value.strip() for value in names):
        raise ValueError("Component names must be nonempty and unique")
    contributions: dict[str, float] = {}
    total_weight = 0.0
    for component in components:
        value = _finite(component.value, f"{component.name}.value")
        weight = _finite(component.weight, f"{component.name}.weight")
        if component.economic_sign not in {-1, 1}:
            raise ValueError(f"{component.name}.economic_sign must be -1 or 1")
        if weight <= 0:
            raise ValueError(f"{component.name}.weight must be positive")
        contributions[component.name] = value * component.economic_sign * weight
        total_weight += weight
    score = sum(contributions.values()) / total_weight
    return DimensionScore(
        name=name,
        score=_clip_unit(score) if clip_to_unit else score,
        score_meaning=score_meaning,
        contributions=contributions,
        total_weight=total_weight,
    )


def calculate_macro_cycle_location(components: Sequence[SignedComponent]) -> DimensionScore:
    """Higher values mean more favorable/improving macro cycle evidence."""

    return calculate_dimension(
        "macro_cycle_location",
        components,
        score_meaning="higher=favorable_or_improving_macro_evidence",
    )


def calculate_fundamental_quality_valuation(components: Sequence[SignedComponent]) -> DimensionScore:
    """Higher values mean stronger quality and/or more attractive valuation."""

    return calculate_dimension(
        "fundamental_asset_quality_valuation",
        components,
        score_meaning="higher=stronger_quality_or_more_attractive_valuation",
    )


def calculate_technical_timing(components: Sequence[SignedComponent]) -> DimensionScore:
    """Higher values mean stronger positive technical confirmation."""

    return calculate_dimension(
        "technical_timing",
        components,
        score_meaning="higher=stronger_positive_direction_confirmation",
    )


def calculate_psychology_credit_risk_temperature(components: Sequence[SignedComponent]) -> DimensionScore:
    """Higher values mean hotter risk tolerance/easier-credit evidence."""

    return calculate_dimension(
        "psychology_credit_risk_temperature",
        components,
        score_meaning="higher=hotter_risk_tolerance_and_easier_credit",
    )


@dataclass(frozen=True)
class CycleArchitecture:
    macro_cycle_location: DimensionScore
    fundamental_asset_quality_valuation: DimensionScore
    technical_timing: DimensionScore
    psychology_credit_risk_temperature: DimensionScore
    notice: str = EXPLORATORY_NOTICE


def calculate_cycle_architecture(
    *,
    macro: Sequence[SignedComponent],
    fundamental: Sequence[SignedComponent],
    technical: Sequence[SignedComponent],
    psychology_credit: Sequence[SignedComponent],
) -> CycleArchitecture:
    """Calculate the four explicitly separated conceptual dimensions."""

    return CycleArchitecture(
        macro_cycle_location=calculate_macro_cycle_location(macro),
        fundamental_asset_quality_valuation=calculate_fundamental_quality_valuation(fundamental),
        technical_timing=calculate_technical_timing(technical),
        psychology_credit_risk_temperature=calculate_psychology_credit_risk_temperature(psychology_credit),
    )


@dataclass(frozen=True)
class CreditInputs:
    """Historically standardized credit proxies; positive meanings are explicit."""

    spread_level: float
    spread_change: float
    lending_standards_tightness: float
    leverage_growth: float
    underwriting_ease: float
    default_rate: float


@dataclass(frozen=True)
class CreditAmplifierMetrics:
    credit_ease: float
    risk_tolerance: float
    current_stress: float
    latent_fragility: float
    risk_temperature: float
    semantics: Mapping[str, str]
    notice: str = EXPLORATORY_NOTICE


def calculate_credit_amplifier(inputs: CreditInputs, *, clip_to_unit: bool = True) -> CreditAmplifierMetrics:
    """Summarize credit ease, current stress, and boom-created fragility.

    Every input is assumed to be a cutoff-safe standardized value where the
    field-name direction applies.  The metrics are descriptive proxies, not a
    claim that credit variables causally determine later defaults or returns.
    """

    values = {
        name: _finite(getattr(inputs, name), name)
        for name in inputs.__dataclass_fields__
    }
    ease = _mean((-values["spread_level"], -values["spread_change"], -values["lending_standards_tightness"]))
    tolerance = _mean((ease, values["leverage_growth"], values["underwriting_ease"]))
    stress = _mean((values["spread_level"], values["spread_change"], values["lending_standards_tightness"], values["default_rate"]))
    fragility = _mean((ease, values["leverage_growth"], values["underwriting_ease"], -values["default_rate"]))
    temperature = _mean((tolerance, fragility, -stress))
    transform = _clip_unit if clip_to_unit else lambda value: value
    return CreditAmplifierMetrics(
        credit_ease=transform(ease),
        risk_tolerance=transform(tolerance),
        current_stress=transform(stress),
        latent_fragility=transform(fragility),
        risk_temperature=transform(temperature),
        semantics={
            "credit_ease": "higher=easier_credit",
            "risk_tolerance": "higher=greater_risk_tolerance",
            "current_stress": "higher=greater_current_credit_stress",
            "latent_fragility": "higher=more_boom_created_fragility",
            "risk_temperature": "higher=hotter_credit_risk_taking_environment",
        },
    )


@dataclass(frozen=True)
class TopScoreConfig:
    """Explicit top-score weights; signs carry direction, weights magnitude."""

    weights: Mapping[str, float]
    signs: Mapping[str, int]
    intercept: float = 0.0
    normalize_by_weight: bool = True


@dataclass(frozen=True)
class CycleTopScore:
    score: float
    contributions: Mapping[str, float]
    configured_signs: Mapping[str, int]
    total_weight: float
    interpretation: str = "higher=more_late_cycle_or_top_like_evidence"
    notice: str = EXPLORATORY_NOTICE


def calculate_cycle_top_score(values: Mapping[str, float], config: TopScoreConfig) -> CycleTopScore:
    """Calculate an experimental top score with no implicit/default weights."""

    if not values or set(values) != set(config.weights) or set(values) != set(config.signs):
        raise ValueError("values, weights, and signs must have the same nonempty keys")
    contributions: dict[str, float] = {}
    total_weight = 0.0
    for name, raw_value in values.items():
        value = _finite(raw_value, f"{name}.value")
        weight = _finite(config.weights[name], f"{name}.weight")
        sign = config.signs[name]
        if weight <= 0:
            raise ValueError(f"{name}.weight must be positive; encode direction in signs")
        if sign not in {-1, 1}:
            raise ValueError(f"{name}.sign must be -1 or 1")
        contributions[name] = value * weight * sign
        total_weight += weight
    weighted_score = sum(contributions.values())
    if config.normalize_by_weight:
        weighted_score /= total_weight
    score = _finite(config.intercept, "intercept") + weighted_score
    return CycleTopScore(score, contributions, dict(config.signs), total_weight)


@dataclass(frozen=True)
class ExploratoryStateThresholds:
    cheap_valuation_minimum: float = 0.5
    expensive_valuation_maximum: float = -0.5
    high_stress_minimum: float = 0.5
    easy_stress_maximum: float = -0.5
    positive_direction_minimum: float = 0.25
    weak_direction_maximum: float = -0.25
    stress_change_magnitude: float = 0.25
    formerly_expensive_lookback_months: int = 12


@dataclass(frozen=True)
class CycleStateObservation:
    as_of: date | datetime
    valuation_attractiveness: float
    stress: float
    direction: float


@dataclass(frozen=True)
class ExploratoryStateResult:
    as_of: date | datetime
    state: str
    flags: Mapping[str, bool]
    stress_change: float
    notice: str = EXPLORATORY_NOTICE


def classify_exploratory_states(
    observations: Sequence[CycleStateObservation],
    *,
    thresholds: ExploratoryStateThresholds = ExploratoryStateThresholds(),
) -> list[ExploratoryStateResult]:
    """Apply the transparent six-state vocabulary to ordered observations.

    Valuation is signed as attractiveness (positive is cheap), stress is
    positive when stressed, and direction is positive when improving. State
    precedence matches the frozen transparent Cycle 1 engine, but these results
    remain exploratory when fed non-Cycle-1 dimensions.
    """

    if thresholds.formerly_expensive_lookback_months < 1:
        raise ValueError("formerly_expensive_lookback_months must be positive")
    if thresholds.stress_change_magnitude < 0:
        raise ValueError("stress_change_magnitude cannot be negative")
    if thresholds.cheap_valuation_minimum <= thresholds.expensive_valuation_maximum:
        raise ValueError("cheap valuation threshold must exceed expensive threshold")
    if thresholds.high_stress_minimum <= thresholds.easy_stress_maximum:
        raise ValueError("high stress threshold must exceed easy stress threshold")
    if thresholds.positive_direction_minimum <= thresholds.weak_direction_maximum:
        raise ValueError("positive direction threshold must exceed weak threshold")
    rows: list[dict[str, object]] = []
    previous: date | datetime | None = None
    original_as_of: dict[str, date | datetime] = {}
    for observation in observations:
        if previous is not None and observation.as_of <= previous:
            raise ValueError("observations must be in strict chronological order")
        previous = observation.as_of
        valuation = _finite(observation.valuation_attractiveness, "valuation_attractiveness")
        stress = _finite(observation.stress, "stress")
        direction = _finite(observation.direction, "direction")
        day = observation.as_of.date() if isinstance(observation.as_of, datetime) else observation.as_of
        snapshot = day.isoformat()
        if snapshot in original_as_of:
            raise ValueError("Only one state observation per calendar date is allowed")
        original_as_of[snapshot] = observation.as_of
        rows.append(
            {
                "snapshotDate": snapshot,
                "dimensionScores": {
                    "valuation": valuation,
                    "stress": stress,
                    "direction": direction,
                },
            }
        )
    config = {
        "states": {
            "thresholds": {
                "cheapValuationMinimum": _finite(thresholds.cheap_valuation_minimum, "cheap_valuation_minimum"),
                "expensiveValuationMaximum": _finite(thresholds.expensive_valuation_maximum, "expensive_valuation_maximum"),
                "highStressMinimum": _finite(thresholds.high_stress_minimum, "high_stress_minimum"),
                "easyStressMaximum": _finite(thresholds.easy_stress_maximum, "easy_stress_maximum"),
                "positiveDirectionMinimum": _finite(thresholds.positive_direction_minimum, "positive_direction_minimum"),
                "weakDirectionMaximum": _finite(thresholds.weak_direction_maximum, "weak_direction_maximum"),
                "stressChangeMagnitude": _finite(thresholds.stress_change_magnitude, "stress_change_magnitude"),
                "formerlyExpensiveLookbackMonths": thresholds.formerly_expensive_lookback_months,
            },
            "precedence": ["EUPHORIA", "EARLY_RECOVERY", "CRISIS", "CORRECTION", "GREED", "NORMAL"],
        }
    }
    assigned = assign_cycle_states(rows, config)
    return [
        ExploratoryStateResult(
            as_of=original_as_of[str(row["snapshotDate"])],
            state=str(row["state"]),
            flags=dict(row["stateFlags"]),
            stress_change=float(row["stressScoreChange3m"]),
        )
        for row in assigned
    ]


@dataclass(frozen=True)
class LatentStateSpec:
    """Fixed diagonal-Gaussian emission parameters for one diagnostic state."""

    name: str
    means: Sequence[float]
    scales: Sequence[float]


@dataclass(frozen=True)
class LatentStateEstimate:
    index: int
    probabilities: Mapping[str, float]
    most_likely_state: str
    confidence: float
    notice: str = EXPLORATORY_NOTICE


def filter_latent_states(
    observations: Sequence[Mapping[str, float]],
    *,
    feature_names: Sequence[str],
    states: Sequence[LatentStateSpec],
    transition_matrix: Sequence[Sequence[float]],
    initial_probabilities: Sequence[float] | None = None,
) -> list[LatentStateEstimate]:
    """Run a fixed-parameter, forward-only HMM-style probability filter.

    This function does not fit state centers, transitions, labels, or feature
    choices. All are explicit inputs. It performs filtering ``P(Z_t|X_1:t)``,
    never backward smoothing, so a future observation cannot modify an earlier
    estimate. It is diagnostic only and not registered for Cycle 1.
    """

    features = tuple(feature_names)
    if not features or len(set(features)) != len(features) or not states:
        raise ValueError("Unique feature_names and at least one state are required")
    state_names = tuple(state.name for state in states)
    if len(set(state_names)) != len(state_names):
        raise ValueError("Latent state names must be unique")
    count = len(states)
    transition = np.asarray(transition_matrix, dtype=float)
    if transition.shape != (count, count) or not np.all(np.isfinite(transition)) or np.any(transition < 0):
        raise ValueError("transition_matrix must be finite, nonnegative, and square by state")
    if not np.allclose(transition.sum(axis=1), 1.0, atol=1e-10):
        raise ValueError("Every transition_matrix row must sum to one")
    prior = np.asarray(
        initial_probabilities if initial_probabilities is not None else [1.0 / count] * count,
        dtype=float,
    )
    if prior.shape != (count,) or not np.all(np.isfinite(prior)) or np.any(prior < 0) or not math.isclose(float(prior.sum()), 1.0, abs_tol=1e-10):
        raise ValueError("initial_probabilities must be nonnegative and sum to one")
    means: list[np.ndarray] = []
    scales: list[np.ndarray] = []
    for state in states:
        mean = np.asarray(state.means, dtype=float)
        scale = np.asarray(state.scales, dtype=float)
        if mean.shape != (len(features),) or scale.shape != (len(features),):
            raise ValueError("Every state mean and scale must match feature_names")
        if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(scale)) or np.any(scale <= 0):
            raise ValueError("State parameters must be finite and scales positive")
        means.append(mean)
        scales.append(scale)

    output: list[LatentStateEstimate] = []
    posterior = prior
    for index, observation in enumerate(observations):
        if set(observation) != set(features):
            raise ValueError("Every observation must contain exactly feature_names")
        vector = np.asarray([_finite(observation[name], name) for name in features])
        predicted = posterior @ transition if index > 0 else posterior
        log_emissions = np.asarray(
            [
                -0.5 * float(np.sum(((vector - mean) / scale) ** 2 + np.log(2 * math.pi * scale**2)))
                for mean, scale in zip(means, scales, strict=True)
            ]
        )
        log_joint = np.log(np.maximum(predicted, np.finfo(float).tiny)) + log_emissions
        log_joint -= float(np.max(log_joint))
        posterior = np.exp(log_joint)
        posterior /= posterior.sum()
        probabilities = {name: float(value) for name, value in zip(state_names, posterior, strict=True)}
        best = int(np.argmax(posterior))
        output.append(LatentStateEstimate(index, probabilities, state_names[best], float(posterior[best])))
    return output


@dataclass(frozen=True)
class NestedCycleObservation:
    as_of: date | datetime
    level: float
    structural_deviation: float
    direction_score: float


@dataclass(frozen=True)
class NestedCycleConfig:
    structural_extreme: float = 1.0
    correction_drawdown: float = 0.1
    correction_direction: float = -0.25
    recovery_direction: float = 0.25
    rally_max_drawdown: float = 0.05


@dataclass(frozen=True)
class NestedCycleDiagnostic:
    as_of: date | datetime
    megacycle_zone: str
    minor_phase: str
    minor_cycle_number: int
    drawdown_from_running_high: float
    late_cycle_major_reversal_risk: bool
    notice: str = EXPLORATORY_NOTICE


def diagnose_nested_cycles(
    observations: Sequence[NestedCycleObservation],
    *,
    config: NestedCycleConfig = NestedCycleConfig(),
) -> list[NestedCycleDiagnostic]:
    """Diagnose a structural zone plus causal rally/correction/recovery phases.

    This deliberately does not assert that a correction ends a megacycle or
    that an overvalued zone predicts a reversal date. A new numbered minor
    cycle begins only on a transition from correction to recovery.
    """

    if config.structural_extreme <= 0 or config.correction_drawdown <= 0 or config.rally_max_drawdown < 0:
        raise ValueError("Nested-cycle magnitudes must be valid positive thresholds")
    if config.rally_max_drawdown >= config.correction_drawdown:
        raise ValueError("rally_max_drawdown must be below correction_drawdown")
    if config.recovery_direction <= config.correction_direction:
        raise ValueError("recovery_direction must exceed correction_direction")
    previous: date | datetime | None = None
    peak = -math.inf
    prior_phase = "NEUTRAL"
    cycle_number = 0
    result: list[NestedCycleDiagnostic] = []
    for observation in observations:
        if previous is not None and observation.as_of <= previous:
            raise ValueError("observations must be in strict chronological order")
        previous = observation.as_of
        level = _finite(observation.level, "level")
        structural = _finite(observation.structural_deviation, "structural_deviation")
        direction = _finite(observation.direction_score, "direction_score")
        if level <= 0:
            raise ValueError("Nested-cycle levels must be positive")
        peak = max(peak, level)
        drawdown = 1.0 - level / peak
        zone = "OVERVALUED" if structural >= config.structural_extreme else (
            "UNDERVALUED" if structural <= -config.structural_extreme else "NORMAL"
        )
        if direction <= config.correction_direction or drawdown >= config.correction_drawdown:
            phase = "CORRECTION"
        elif prior_phase == "CORRECTION" and direction >= config.recovery_direction:
            phase = "RECOVERY"
            cycle_number += 1
        elif prior_phase == "RECOVERY" and drawdown > config.rally_max_drawdown:
            phase = "RECOVERY"
        elif direction >= config.recovery_direction and drawdown <= config.rally_max_drawdown:
            phase = "RALLY"
            if cycle_number == 0:
                cycle_number = 1
        else:
            phase = "NEUTRAL"
        reversal_risk = zone == "OVERVALUED" and phase == "CORRECTION"
        result.append(
            NestedCycleDiagnostic(
                observation.as_of,
                zone,
                phase,
                cycle_number,
                drawdown,
                reversal_risk,
            )
        )
        prior_phase = phase
    return result


@dataclass(frozen=True)
class ExposurePolicy:
    """Research-only aggressive/defensive budgets for every state."""

    state_budgets: Mapping[str, float]
    fallback_budget: float = 0.5
    minimum_confidence: float = 0.0
    maximum_change: float | None = None


@dataclass(frozen=True)
class ExposureMapping:
    risk_budget: float
    posture: str
    most_likely_state: str
    confidence: float
    used_fallback: bool
    unconstrained_budget: float
    notice: str = EXPLORATORY_NOTICE


def map_state_probabilities_to_exposure(
    probabilities: Mapping[str, float],
    policy: ExposurePolicy,
    *,
    previous_budget: float | None = None,
) -> ExposureMapping:
    """Map state probabilities to a bounded research risk budget in ``[0, 1]``.

    The unconstrained budget is probability-weighted rather than an all-in/out
    rule. Low-confidence estimates use the explicit fallback. If configured,
    ``maximum_change`` limits movement from a supplied previous budget.
    """

    if set(probabilities) != set(STATE_LABELS) or set(policy.state_budgets) != set(STATE_LABELS):
        raise ValueError("probabilities and state_budgets must contain exactly the six state labels")
    checked_probabilities = {name: _finite(value, f"{name}.probability") for name, value in probabilities.items()}
    if any(value < 0 for value in checked_probabilities.values()) or not math.isclose(sum(checked_probabilities.values()), 1.0, abs_tol=1e-9):
        raise ValueError("State probabilities must be nonnegative and sum to one")
    budgets = {name: _finite(value, f"{name}.budget") for name, value in policy.state_budgets.items()}
    if any(not 0 <= value <= 1 for value in budgets.values()):
        raise ValueError("Every state budget must be in [0, 1]")
    fallback = _finite(policy.fallback_budget, "fallback_budget")
    confidence_floor = _finite(policy.minimum_confidence, "minimum_confidence")
    if not 0 <= fallback <= 1 or not 0 <= confidence_floor <= 1:
        raise ValueError("fallback_budget and minimum_confidence must be in [0, 1]")
    state = max(checked_probabilities, key=checked_probabilities.__getitem__)
    confidence = checked_probabilities[state]
    weighted = sum(checked_probabilities[name] * budgets[name] for name in STATE_LABELS)
    used_fallback = confidence < confidence_floor
    unconstrained = fallback if used_fallback else weighted
    budget = unconstrained
    if policy.maximum_change is not None:
        max_change = _finite(policy.maximum_change, "maximum_change")
        if not 0 <= max_change <= 1 or previous_budget is None:
            raise ValueError("maximum_change in [0, 1] requires previous_budget")
        previous_value = _finite(previous_budget, "previous_budget")
        if not 0 <= previous_value <= 1:
            raise ValueError("previous_budget must be in [0, 1]")
        budget = min(previous_value + max_change, max(previous_value - max_change, budget))
    posture = (
        "VERY_DEFENSIVE" if budget < 0.2 else
        "DEFENSIVE" if budget < 0.4 else
        "NEUTRAL" if budget < 0.6 else
        "AGGRESSIVE" if budget < 0.8 else
        "VERY_AGGRESSIVE"
    )
    return ExposureMapping(budget, posture, state, confidence, used_fallback, unconstrained)
