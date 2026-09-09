"""Pre-output repairs: positive corporate actions and annual information nulls.

These laws amend the UNFROZEN candidate. The stopped v1, numeric acceptance
gates, design effects, origin calendars and scenario acceptance roles stand.
No sampler or experiment release is implemented here.
"""
import math

from spy_predictor_quant.cycle1_successor_inputs import SyntheticVintage
from spy_predictor_quant.market_archive import content_hash


REPAIR_SPEC = {
    'version': 'cycle1-successor-laws-v2',
    'status': 'REPAIRED_LAWS_NOT_REGISTERED',
    'actions': 'reserve-announced-cash-before-shocking-residual-equity;reinvest-at-close;compensate-total-return-log-difference-equally-over-remaining-month-increments',
    'nullMonthlyScale': 'iid-lognormal-with-old-stationary-log-scale-variance;independent-of-origin-history',
    'nullDailyScale': 'retain-original-persistent-log-volatility-for-zero-sum-bridge',
    'partialNull': 'SPY-Markov-regime-observed-through-actual-valuation-percentile-sign',
    'partialNullTransition': 'R_next=-R-if-independent-U<(1-predictorPersistence)/2;otherwise-R',
    'partialNullSignal': 'sign(actual-own-valuation-score);same-annual-amplitude',
    'partialNullCpi': 'synthetic-control-only;current-close-release-encodes-regime;next-close-revision-removes-previous-marker',
    'partialNullMarkerLogStep': 0.0001,
    'partialNullMacroMissingness': 'disabled-to-prevent-history-dependent-future-loading-availability',
    'partialNullInitialRegime': 1,
    'innovationIndependence': 'future-month-Student-values,volatility-normals,baseline-uniforms,macro-shocks-and-missingness-uniforms-independent-across-months-and-streams;shared-SPY-QQQ-shocks-explicit',
    'additionalRequiredSubstreams': ['spy-monthly-student', 'qqq-monthly-student', 'baseline-regime'],
    'nullProofScope': 'SPY-primary-annual-excess-labels-at-available-post-warmup-origins;not-QQQ-transfer-or-downside-or-policy',
    'numerics': 'unrepresentable-arithmetic-invalidates-run;never-clip-or-redraw',
    'unchanged': ['acceptance-thresholds', 'scenario-roles', 'design-and-boundary-amplitudes',
                  'calendars', 'models', 'feature-formulas', 'replication-and-compute-budgets'],
    'randomDrawsAllowed': False, 'realDataApproval': False,
}
REPAIR_HASH = content_hash(REPAIR_SPEC)
NULL_IDS = frozenset(('null-no-skill', 'null-persistent-heavy-tails',
                     'partial-null-strong-baseline', 'rare-downside', 'missingness'))


def validate_repair_scenario(scenario: dict) -> None:
    """Fail closed if a claimed-null scenario changes the proof assumptions."""
    if scenario['id'] not in NULL_IDS:
        if scenario['requirement'] == 'false-qualification-upper-bound':
            raise ValueError('Unknown null scenario has no annual-law certificate')
        return
    partial = scenario['id'] == 'partial-null-strong-baseline'
    if (scenario['requirement'] != 'false-qualification-upper-bound'
            or scenario['signal'] != ('position-direction' if partial else 'none')
            or scenario['annualLocationAmplitude'] != (.08 if partial else 0)
            or scenario['logScaleLoading'] != 0 or scenario['afterBreakMultiplier'] != 1
            or scenario['studentDegreesOfFreedom'] <= 2
            or not 0 <= scenario['predictorPersistence'] < 1
            or not 0 <= scenario['volatilityPersistence'] < 1
            or not math.isfinite(scenario['volatilityInnovationSd'])
            or scenario['volatilityInnovationSd'] < 0
            or (partial and (scenario['crashProbability'] != 0 or scenario['missingProbability'] != 0))):
        raise ValueError('Scenario violates the repaired annual-null assumptions')


def reserve_distribution(base: float, fraction: float, overnight: float,
                         intraday: float) -> tuple[float, float, float, float]:
    """Return positive open/close, predetermined cash, and log-TR adjustment.

    base=P_previous/split. D=q*base is reserved before trading; only (1-q)*base
    bears the return shock. log((1-q)*exp(o+i)+q) is the holder's close return.
    Difference from o+i is compensated AFTER this close, with no changed
    monthly target or future-origin information used to choose the payment.
    """
    if (not all(math.isfinite(v) for v in (base, fraction, overnight, intraday))
            or base <= 0 or not 0 <= fraction < 1):
        raise ValueError('Invalid distribution reserve parameters')
    remaining = base * (1 - fraction)
    opened = remaining * math.exp(overnight)
    closed = remaining * math.exp(overnight + intraday)
    dividend = base * fraction
    adjustment = 0.0
    if fraction:
        a, b = math.log1p(-fraction) + overnight + intraday, math.log(fraction)
        high, low = max(a, b), min(a, b)
        holder_log_return = high + math.log1p(math.exp(low - high))
        adjustment = holder_log_return - overnight - intraday
    if not all(math.isfinite(v) and v > 0 for v in (opened, closed)):
        raise ArithmeticError('Unrepresentable positive equity path; invalidate, never redraw')
    return opened, closed, dividend, adjustment


def compensate_distribution(increments: list[float], after_index: int, adjustment: float) -> None:
    count = len(increments) - after_index
    if count <= 0:
        raise ValueError('Distribution compensation requires later sessions in the month')
    for index in range(after_index, len(increments)):
        increments[index] -= adjustment / count


def iid_null_log_scale(scenario: dict, current_normal: float) -> float:
    return scenario['volatilityInnovationSd'] / math.sqrt(1 - scenario['volatilityPersistence'] ** 2) * current_normal


def next_baseline_regime(previous: int, uniform: float, persistence: float) -> int:
    if previous not in (-1, 1) or not 0 <= uniform < 1 or not 0 <= persistence < 1:
        raise ValueError('Invalid baseline regime transition')
    return -previous if uniform < (1 - persistence) / 2 else previous


def baseline_cpi_records(current, previous, *, ordinal: int, regime: int,
                         valuation_sign: int) -> tuple[SyntheticVintage, ...]:
    """A deliberately artificial CPI control, never an observed CPI source.

    At cutoff: all old SPY real month-end levels equal 1; today's equals exp(m).
    With 59 zero log levels, Theil-Sen slope/intercept/MAD are zero. The raw
    deviation is m/madFloor. Increasing |m| makes today's normalized valuation
    a new signed extreme, so its sign reveals R using the UNCHANGED extractor.
    """
    if ordinal < 0 or regime not in (-1, 1) or valuation_sign not in (-1, 1):
        raise ValueError('Invalid observable baseline marker')
    marker = valuation_sign * regime * REPAIR_SPEC['partialNullMarkerLogStep'] * (ordinal + 1)
    records = []
    if previous is not None:
        records.append(SyntheticVintage('CPIAUCSL', previous.session.replace(day=1),
            current.close_time, 1, previous.close_total_return_level))
    records.append(SyntheticVintage('CPIAUCSL', current.session.replace(day=1),
        current.close_time, 0, current.close_total_return_level * math.exp(-marker)))
    return tuple(records)


def partial_null_mean(regime: int, scenario: dict, horizon: int = 12) -> float:
    """Exact conditional annual mean for the repaired SPY partial null."""
    validate_repair_scenario(scenario)
    if scenario['id'] != 'partial-null-strong-baseline' or regime not in (-1, 1) or horizon < 1:
        raise ValueError('Expected a partial-null regime and positive horizon')
    rho = scenario['predictorPersistence']
    return horizon * .04 / 12 + scenario['annualLocationAmplitude'] / 12 * regime * sum(rho ** j for j in range(horizon))
