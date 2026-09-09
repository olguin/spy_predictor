"""Proposed successor equations, evaluated only on explicitly supplied fixtures.

No RNG, stream opener, archived-input loader or experiment registration exists
here. This executable candidate does NOT establish the required annual null law.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
import math
from typing import Any

from spy_predictor_quant.cycle1_calendar import _xnys, xnys_session_close
from spy_predictor_quant.cycle1_successor_calendar import month_end as xnys_month_end
from spy_predictor_quant.cycle1_successor_features import SuccessorFeatureState
from spy_predictor_quant.cycle1_targets import TotalReturnPoint
from spy_predictor_quant.cycle1_successor_inputs import SyntheticVintage, select_vintages, monthly_cash_accrual
from spy_predictor_quant.market_archive import content_hash


# Chosen before equation-fixture output. This is a candidate equation contract,
# not a frozen replacement for v1 or authority to consume the redesign slot.
EQUATION_SPEC = {
    'version': 'cycle1-successor-equations-proposal-v1',
    'status': 'DETERMINISTIC_FIXTURES_ONLY_ANNUAL_NULL_UNPROVEN',
    'initialRawPrice': 100.0, 'initialCpi': 100.0, 'initialIndustrialProduction': 100.0,
    'annualBaseExcessLogDrift': 0.04, 'annualBaseVolatility': 0.15,
    'overnightVarianceFraction': 0.25, 'qqqMultiplier': 1.2,
    'qqqSharedShockWeight': 0.8, 'qqqIndependentShockWeight': 0.6,
    'cpiAnnualLogDrift': 0.02, 'cpiMonthlyInnovationScale': 0.002,
    'ipAnnualLogDrift': 0.02, 'ipMonthlyInnovationScale': 0.005,
    'treasuryAnnualPercentBase': 3.0, 'primeSpreadAnnualPercentBase': 2.0,
    'rateLogStateLoading': 0.15, 'firstReleaseLogNoise': 0.001,
    'revisionLogNoise': 0.0005, 'firstReleaseLagDays': 15, 'revisionLagDays': 45,
    'releaseUtcHour': 13, 'releaseUtcMinute': 30,
    'firstReleaseMissingProbability': 0.01, 'revisionTombstoneProbability': 0.005,
    'quarterlyDividendFractionOfPreviousPostSplitClose': 0.0025,
    'dividendMonths': [3, 6, 9, 12], 'splitEveryCalendarYears': 10,
    'splitMonth': 1, 'splitNewSharesPerOldShare': 2.0,
    'cashDayCount': 'calendar-date-actual/365',
    'dividendUnits': 'cash-per-post-split-share;ex-date-entitlement-before-open;reinvest-at-close',
    'dailyBridge': 'weighted-zero-sum-Gaussian-bridge;all-month-shocks-fixed-at-month-start',
    'featureSemantics': 'legacy-nine-formulas-with-successor-inclusive-tombstone-vintages;own-market-history',
    'realDataApproval': False, 'randomDrawsAllowed': False,
}
EQUATION_HASH = content_hash(EQUATION_SPEC)


def _finite(values) -> None:
    if any(isinstance(x, bool) or not math.isfinite(x) for x in values):
        raise ValueError('Equation inputs must be finite real numbers')


@dataclass(frozen=True)
class MonthInnovations:
    """Raw Student-t values, unit Gaussian values, and U[0,1) values, supplied by caller.

    Their probability laws are a future generator obligation, not inferred from
    fixture values. No random sampling takes place in this module.
    """
    month: date
    spy_student: float = 0.0
    qqq_student: float = 0.0
    volatility_normal: float = 0.0
    macro_normals: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0)
    release_normals: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0)
    revision_normals: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0)
    release_uniforms: tuple[float, ...] = (0.5, 0.5, 0.5, 0.5)
    revision_uniforms: tuple[float, ...] = (0.5, 0.5, 0.5, 0.5)
    crash_uniform: float = 0.5
    crash_timing_uniform: float = 0.5
    missing_uniform: float = 0.5
    baseline_uniform: float = 0.5

    def __post_init__(self):
        if self.month.day != 1:
            raise ValueError('Innovation month must be its calendar first day')
        groups = (self.macro_normals, self.release_normals, self.revision_normals,
                  self.release_uniforms, self.revision_uniforms)
        if any(len(group) != 4 for group in groups):
            raise ValueError('Macro innovations require CPI, IP, treasury and spread entries')
        _finite((self.spy_student, self.qqq_student, self.volatility_normal,
                 self.crash_uniform, self.crash_timing_uniform, self.missing_uniform, self.baseline_uniform,
                 *(value for group in groups for value in group)))
        if any(not 0 <= value < 1 for value in (*self.release_uniforms, *self.revision_uniforms,
                                               self.crash_uniform, self.crash_timing_uniform,
                                               self.missing_uniform, self.baseline_uniform)):
            raise ValueError('Uniform innovations must lie in [0,1)')


@dataclass(frozen=True)
class SessionInnovations:
    session: date
    spy_overnight: float = 0.0
    spy_intraday: float = 0.0
    qqq_overnight: float = 0.0
    qqq_intraday: float = 0.0

    def __post_init__(self):
        _finite((self.spy_overnight, self.spy_intraday, self.qqq_overnight, self.qqq_intraday))


@dataclass(frozen=True)
class RawSession:
    instrument: str
    session: date
    open_time: datetime
    close_time: datetime
    raw_open: float
    raw_close: float
    split_factor: float
    dividend_per_post_split_share: float
    close_total_return_level: float
    action_available_at: datetime
    evidence_tier: str = 'SYNTHETIC_ONLY'

    def __post_init__(self):
        if self.instrument not in ('SPY', 'QQQ') or self.evidence_tier != 'SYNTHETIC_ONLY':
            raise ValueError('Only synthetic SPY/QQQ equation paths are accepted')
        _finite((self.raw_open, self.raw_close, self.split_factor,
                 self.dividend_per_post_split_share, self.close_total_return_level))
        if min(self.raw_open, self.raw_close, self.split_factor, self.close_total_return_level) <= 0:
            raise ValueError('Price, split and total-return levels must be positive')
        if self.dividend_per_post_split_share < 0:
            raise ValueError('Cash distributions cannot be negative')
        calendar = _xnys()
        if (self.open_time != calendar.session_open(self.session.isoformat()).to_pydatetime()
                or self.close_time != xnys_session_close(self.session)):
            raise ValueError('Prices require actual scheduled XNYS open/close timestamps')
        if self.action_available_at.tzinfo is None or self.action_available_at >= self.open_time:
            raise ValueError('Action terms must be known strictly before the ex-date open')


def _months(start: date, end: date) -> tuple[date, ...]:
    a, b = start.year * 12 + start.month - 1, end.year * 12 + end.month - 1
    return tuple(date(index // 12, index % 12 + 1, 1) for index in range(a, b + 1))


def macro_path(months: tuple[MonthInnovations, ...], persistence: float) -> tuple[SyntheticVintage, ...]:
    """Positive monthly macro equations with independently timestamped revisions."""
    if not months or tuple(row.month for row in months) != _months(months[0].month, months[-1].month):
        raise ValueError('Macro months must be complete and chronological')
    if not 0 <= persistence < 1:
        raise ValueError('Macro persistence must lie in [0,1)')
    s = EQUATION_SPEC
    state = [0.0] * 4
    cpi, ip = s['initialCpi'], s['initialIndustrialProduction']
    records = []
    for row in months:
        state = [persistence * old + math.sqrt(1 - persistence ** 2) * shock
                 for old, shock in zip(state, row.macro_normals, strict=True)]
        cpi *= math.exp(s['cpiAnnualLogDrift'] / 12 + s['cpiMonthlyInnovationScale'] * state[0])
        ip *= math.exp(s['ipAnnualLogDrift'] / 12 + s['ipMonthlyInnovationScale'] * state[1])
        rate = s['treasuryAnnualPercentBase'] * math.exp(s['rateLogStateLoading'] * state[2])
        spread = s['primeSpreadAnnualPercentBase'] * math.exp(s['rateLogStateLoading'] * state[3])
        observation_end = date(row.month.year + (row.month.month == 12), row.month.month % 12 + 1, 1) - timedelta(days=1)
        for revision, lag, noise, normals, uniforms, missing_probability in (
                (0, s['firstReleaseLagDays'], s['firstReleaseLogNoise'], row.release_normals,
                 row.release_uniforms, s['firstReleaseMissingProbability']),
                (1, s['revisionLagDays'], s['revisionLogNoise'], row.revision_normals,
                 row.revision_uniforms, s['revisionTombstoneProbability'])):
            published = datetime.combine(observation_end + timedelta(days=lag),
                                         time(s['releaseUtcHour'], s['releaseUtcMinute']), timezone.utc)
            for index, (series, value) in enumerate(zip(('CPIAUCSL', 'INDPRO', 'GS3M', 'MPRIME'),
                                                        (cpi, ip, rate, rate + spread), strict=True)):
                revised = None if uniforms[index] < missing_probability else value * math.exp(noise * normals[index])
                records.append(SyntheticVintage(series, row.month, published, revision, revised))
    return tuple(records)


def _cash_interval(start: datetime, end: datetime, records: tuple[SyntheticVintage, ...]) -> dict:
    selected = select_vintages(records, 'GS3M', start, strict=True)
    valid = [record for record in selected.values() if record.value is not None]
    if not valid:
        raise ValueError('No strict-start cash publication; supply macro warmup months')
    rate = max(valid, key=lambda record: record.observation)
    days = (end.date() - start.date()).days
    growth = 1 + rate.value / 100 * days / 365
    if days <= 0 or growth <= 0 or not math.isfinite(growth):
        raise ValueError('Invalid actual/365 holding interval')
    return {'simpleReturn': growth - 1, 'logReturn': math.log(growth), 'actualDays': days,
            'annualPercent': rate.value, 'published': rate.published.isoformat()}


def _feature_state(instrument: str, bars: list[RawSession], records: tuple[SyntheticVintage, ...],
                   feature_state: SuccessorFeatureState) -> dict:
    points = [TotalReturnPoint(row.session, row.close_time, row.raw_close, row.close_total_return_level) for row in bars]
    computed = feature_state.advance(instrument, points, records)
    base = {'cutoff': points[-1].event_time.isoformat(), 'origin': points[-1].session_date.isoformat(),
            'marketHistoryRows': len(points), 'evidenceTier': 'SYNTHETIC_ONLY'}
    if computed is None:
        return {**base, 'status': 'UNAVAILABLE', 'reasons': feature_state.last_unavailable[instrument],
                'dimensionScores': None}
    return {**computed, **base, 'status': 'AVAILABLE'}


def _signal(state: dict, kind: str) -> float:
    d = state['dimensionScores']
    if d is None or state['status'] != 'AVAILABLE' or kind == 'none':
        return 0.0
    return {'cycle': sum(d.values()) / 3, 'stress': d['stress'],
            'position-direction': (d['valuation'] + d['direction']) / 2}[kind]


def _bridge(total: float, sigma: float, innovations: tuple[float, ...]) -> tuple[float, ...]:
    n = len(innovations) // 2
    f = EQUATION_SPEC['overnightVarianceFraction']
    weights = tuple(value for _ in range(n) for value in (f / n, (1 - f) / n))
    deviations = [sigma * math.sqrt(weight) * shock for weight, shock in zip(weights, innovations, strict=True)]
    summed = math.fsum(deviations)
    increments = [weight * total + dev - weight * summed for weight, dev in zip(weights, deviations, strict=True)]
    # Fix floating-point summation residue at the final close, never alter total.
    increments[-1] += total - math.fsum(increments)
    return tuple(increments)


def run_equations(*, start: date, end: date, monthly: tuple[MonthInnovations, ...],
                  daily: tuple[SessionInnovations, ...], scenario: dict, config: dict,
                  repaired: bool = False) -> dict[str, Any]:
    """Run explicit innovations from an anchor month close through a month close.

    `monthly` includes at least two pre-start macro observation months. Full nine
    feature warmup still needs the actual multi-year market path. An unavailable
    state gives zero skill loading and remains unavailable, never a zero feature.
    """
    s = EQUATION_SPEC
    from spy_predictor_quant.cycle1_successor_laws import (
        REPAIR_HASH, NULL_IDS, validate_repair_scenario, reserve_distribution,
        compensate_distribution, iid_null_log_scale, next_baseline_regime, baseline_cpi_records,
    )
    partial_null = repaired and scenario['id'] == 'partial-null-strong-baseline'
    certified_null = repaired and scenario['id'] in NULL_IDS
    if repaired:
        validate_repair_scenario(scenario)
    if start >= end or start != xnys_month_end(start.year, start.month) or end != xnys_month_end(end.year, end.month):
        raise ValueError('Equation bounds must be increasing scheduled month ends')
    calendar = _xnys()
    sessions = tuple(row.date() for row in calendar.sessions_in_range(start.isoformat(), end.isoformat()))
    if tuple(row.session for row in daily) != sessions[1:]:
        raise ValueError('Every following scheduled session requires explicit innovations')
    required_months = _months(start, end)[1:]
    macro_monthly = tuple(replace(row, release_uniforms=(.5,) * 4, revision_uniforms=(.5,) * 4)
                          for row in monthly) if partial_null else monthly
    macro = macro_path(macro_monthly, scenario['predictorPersistence'])
    if partial_null:
        macro = tuple(row for row in macro if row.series != 'CPIAUCSL')
    monthly_lookup = {row.month: row for row in monthly}
    if any(month not in monthly_lookup for month in required_months):
        raise ValueError('Missing monthly equation innovations')
    if scenario['signal'] not in ('none', 'cycle', 'stress', 'position-direction') or scenario['studentDegreesOfFreedom'] <= 2:
        raise ValueError('Unsupported signal or Student-t variance')
    _finite(scenario[key] for key in ('annualLocationAmplitude', 'logScaleLoading', 'volatilityPersistence',
                                    'volatilityInnovationSd', 'afterBreakMultiplier', 'missingProbability',
                                    'crashProbability', 'crashLogReturn'))
    if not 0 <= scenario['volatilityPersistence'] < 1 or scenario['volatilityInnovationSd'] < 0:
        raise ValueError('Invalid volatility process')
    if any(not 0 <= scenario[key] <= 1 for key in ('missingProbability', 'crashProbability')):
        raise ValueError('Invalid scenario probability')
    bars, features = {}, {}
    feature_state = SuccessorFeatureState(config)
    baseline_regime = 1
    for instrument in ('SPY', 'QQQ'):
        bars[instrument] = [RawSession(instrument, start, calendar.session_open(start.isoformat()).to_pydatetime(),
                                      xnys_session_close(start), s['initialRawPrice'], s['initialRawPrice'],
                                      1.0, 0.0, 1.0, calendar.session_open(start.isoformat()).to_pydatetime() - timedelta(seconds=1))]
        if partial_null and instrument == 'SPY':
            macro += baseline_cpi_records(bars[instrument][-1], None, ordinal=0,
                regime=baseline_regime, valuation_sign=feature_state.signs['real-price-trend-deviation'])
        features[instrument] = [_feature_state(instrument, bars[instrument], macro, feature_state)]
    h = 0.0
    parameters = []
    for month_ordinal, month in enumerate(required_months, 1):
        innovation = monthly_lookup[month]
        shocks = tuple(row for row in daily if (row.session.year, row.session.month) == (month.year, month.month))
        month_end = xnys_month_end(month.year, month.month)
        prior = bars['SPY'][-1]
        cash = _cash_interval(prior.close_time, xnys_session_close(month_end), macro)
        eps = innovation.spy_student / math.sqrt(scenario['studentDegreesOfFreedom'] / (scenario['studentDegreesOfFreedom'] - 2))
        other = innovation.qqq_student / math.sqrt(scenario['studentDegreesOfFreedom'] / (scenario['studentDegreesOfFreedom'] - 2))
        crash = scenario['crashLogReturn'] if innovation.crash_uniform < scenario['crashProbability'] else 0.0
        crash_session = min(len(shocks) - 1, int(innovation.crash_timing_uniform * len(shocks)))
        for instrument, shock, multiplier in (('SPY', eps, 1.0), ('QQQ', .8 * eps + .6 * other, 1.2)):
            state = features[instrument][-1]
            signal = _signal(state, scenario['signal'])
            if partial_null and state['status'] == 'AVAILABLE':
                # Decode from the actual computed feature, never substitute R.
                value = state['dimensionScores']['valuation']
                if value == 0:
                    raise ValueError('Partial null requires a nonzero observable valuation state')
                signal = math.copysign(1., value)
                if instrument == 'SPY' and signal != baseline_regime:
                    raise ValueError('Actual SPY valuation does not reveal the certified baseline regime')
            # The inherited break is defined at the forecast origin, not in
            # the month whose return is subsequently realized.
            regime = scenario['afterBreakMultiplier'] if prior.session.isoformat()[:7] >= scenario['breakMonth'] else 1
            mu = s['annualBaseExcessLogDrift'] / 12 + scenario['annualLocationAmplitude'] / 12 * signal * regime
            return_h = iid_null_log_scale(scenario, innovation.volatility_normal) if certified_null else h
            sigma = s['annualBaseVolatility'] / math.sqrt(12) * math.exp(return_h + scenario['logScaleLoading'] * signal)
            bridge_sigma = s['annualBaseVolatility'] / math.sqrt(12) * math.exp(h + scenario['logScaleLoading'] * signal)
            monthly_excess = multiplier * (mu + sigma * shock) + crash
            normals = tuple(value for row in shocks for value in (
                (row.spy_overnight, row.spy_intraday) if instrument == 'SPY' else
                (.8 * row.spy_overnight + .6 * row.qqq_overnight, .8 * row.spy_intraday + .6 * row.qqq_intraday)))
            increments = list(_bridge(multiplier * (mu + sigma * shock) + cash['logReturn'],
                                      multiplier * bridge_sigma, normals))
            increments[2 * crash_session] += crash  # Shared crash at one explicit overnight.
            for index, row in enumerate(shocks):
                previous = bars[instrument][-1]
                split = s['splitNewSharesPerOldShare'] if (index == 0 and month.month == s['splitMonth']
                          and month.year % s['splitEveryCalendarYears'] == 0) else 1.0
                q = s['quarterlyDividendFractionOfPreviousPostSplitClose'] if index == 0 and month.month in s['dividendMonths'] else 0.0
                base = previous.raw_close / split
                dividend = base * q
                if repaired:
                    raw_open, raw_close, dividend, adjustment = reserve_distribution(
                        base, q, increments[2 * index], increments[2 * index + 1])
                    if q:
                        compensate_distribution(increments, 2 * index + 2, adjustment)
                else:
                    raw_open = base * math.exp(increments[2 * index]) - dividend
                    raw_close = base * math.exp(increments[2 * index] + increments[2 * index + 1]) - dividend
                close_level = previous.close_total_return_level * split * (raw_close + dividend) / previous.raw_close
                bars[instrument].append(RawSession(instrument, row.session,
                    calendar.session_open(row.session.isoformat()).to_pydatetime(), xnys_session_close(row.session),
                    raw_open, raw_close, split, dividend, close_level, previous.close_time))
            if partial_null and instrument == 'SPY':
                # R changes only after generating this month's return. Its new
                # public CPI marker can affect the NEXT month's return.
                baseline_regime = next_baseline_regime(baseline_regime, innovation.baseline_uniform,
                                                      scenario['predictorPersistence'])
                macro += baseline_cpi_records(bars[instrument][-1], prior, ordinal=month_ordinal,
                    regime=baseline_regime, valuation_sign=feature_state.signs['real-price-trend-deviation'])
            current = _feature_state(instrument, bars[instrument], macro, feature_state)
            if partial_null and instrument == 'SPY' and state['status'] == 'AVAILABLE' and current['status'] != 'AVAILABLE':
                raise ValueError('Partial-null future loading availability must remain deterministic after warmup')
            if innovation.missing_uniform < scenario['missingProbability']:
                current = {**current, 'status': 'MISSING_ORIGIN', 'reasons': ['scenario-origin-missingness'],
                           'dimensionScores': None}
            features[instrument].append(current)
            parameters.append({'month': month.isoformat(), 'instrument': instrument,
                               'featureCutoff': state['cutoff'], 'featureStatus': state['status'],
                               'signal': signal, 'logVolatilityState': h, 'monthlyMean': mu,
                               'returnLogVolatilityState': return_h, 'bridgeSigma': bridge_sigma,
                               'regimeMultiplier': regime,
                               'monthlySigma': sigma, 'monthlyExcessLogReturn': monthly_excess,
                               'monthlyCashLogReturn': cash['logReturn'], 'crashSession': shocks[crash_session].session.isoformat() if crash else None})
        h = scenario['volatilityPersistence'] * h + scenario['volatilityInnovationSd'] * innovation.volatility_normal
    return {'bars': {name: tuple(rows) for name, rows in bars.items()}, 'features': features,
            'macroVintages': macro, 'parameters': parameters,
            'equationHash': content_hash({'base': EQUATION_HASH, 'repair': REPAIR_HASH}) if repaired else EQUATION_HASH,
            'repairHash': REPAIR_HASH if repaired else None,
            'annualNullCertificate': 'SPY-post-warmup-information-null' if certified_null else None,
            'evidenceTier': 'SYNTHETIC_ONLY', 'randomDraws': 0, 'annualNullProven': certified_null,
            'fullProcedureQualified': False, 'realDataApproval': False}


def execution_equity_return(bars: tuple[RawSession, ...], entry: date, exit: date) -> float:
    """Buy at entry open, close-reinvest entitled dividends, liquidate at exit open.

    Entry-day dividends belong to yesterday's holder; the new purchase receives
    none. Exit-day dividends belong to this holder, even when selling at open.
    A ratio of generic close-reinvested TRI open marks does not implement this.
    """
    lookup = {row.session: index for index, row in enumerate(bars)}
    if entry not in lookup or exit not in lookup or entry >= exit:
        raise ValueError('Missing or unordered execution endpoints')
    selected = bars[lookup[entry]:lookup[exit] + 1]
    expected = tuple(row.date() for row in _xnys().sessions_in_range(entry.isoformat(), exit.isoformat()))
    if tuple(row.session for row in selected) != expected or len({row.instrument for row in selected}) != 1:
        raise ValueError('Execution needs one complete chronological instrument path')
    shares = 1 / selected[0].raw_open
    for row in selected[1:]:
        shares *= row.split_factor
        entitled_cash = shares * row.dividend_per_post_split_share
        if row.session == exit:
            return shares * row.raw_open + entitled_cash - 1
        shares += entitled_cash / row.raw_close
    raise ValueError('Execution interval has no ending session')


def derive_successor_targets(result: dict, origins: tuple[date, ...]) -> list[dict]:
    """Derive complete nominal-minus-cash labels and shareholder execution tapes.

    CPI is not read here. This proves arithmetic on supplied paths, not source
    qualification, downstream statistical qualification, or real-data approval.
    """
    from spy_predictor_quant.cycle1_successor_laws import REPAIR_HASH
    accepted_hashes = (EQUATION_HASH, content_hash({'base': EQUATION_HASH, 'repair': REPAIR_HASH}))
    if result.get('evidenceTier') != 'SYNTHETIC_ONLY' or result.get('equationHash') not in accepted_hashes:
        raise ValueError('Target derivation requires this synthetic equation identity')
    if not origins or tuple(sorted(set(origins))) != origins:
        raise ValueError('Origin calendar must be explicit and chronological')
    output = []
    for instrument, bars in result['bars'].items():
        lookup = {row.session: row for row in bars}
        for origin in origins:
            if origin != xnys_month_end(origin.year, origin.month):
                raise ValueError('Origin must be scheduled month end')
            end = xnys_month_end(origin.year + 1, origin.month)
            boundaries = tuple(xnys_month_end(month.year, month.month) for month in _months(origin, end))
            if any(point not in lookup for point in boundaries):
                raise ValueError('Target requires all thirteen monthly boundaries')
            cash = monthly_cash_accrual(boundaries, result['macroVintages'])
            selected = [row for row in bars if origin <= row.session <= end]
            expected = tuple(x.date() for x in _xnys().sessions_in_range(origin.isoformat(), end.isoformat()))
            if tuple(row.session for row in selected) != expected:
                raise ValueError('Target contains an internal daily session gap')
            for before, after in zip(selected, selected[1:]):
                expected_level = before.close_total_return_level * after.split_factor * (after.raw_close + after.dividend_per_post_split_share) / before.raw_close
                if not math.isclose(after.close_total_return_level, expected_level, rel_tol=1e-12, abs_tol=0):
                    raise ValueError('Total-return levels disagree with raw corporate-action units')
            closes = [row.close_total_return_level for row in selected]
            peak, worst = closes[0], 0.0
            for value in closes:
                peak = max(peak, value)
                worst = min(worst, value / peak - 1)
            entry = _xnys().next_session(origin.isoformat()).date()
            exit = _xnys().next_session(boundaries[1].isoformat()).date()
            if entry not in lookup or exit not in lookup:
                raise ValueError('Missing next-open execution endpoints')
            execution_cash = _cash_interval(lookup[entry].open_time, lookup[exit].open_time, result['macroVintages'])
            equity = math.log(closes[-1] / closes[0])
            output.append({'instrument': instrument, 'origin': origin.isoformat(), 'targetEnd': end.isoformat(),
                'annualEquityLogReturn': equity, 'annualCashLogReturn': cash['cashLogReturn'],
                'annualExcessLogReturn': equity - cash['cashLogReturn'], 'maximumDailyCloseDrawdown': worst,
                'drawdownEvent': worst <= -.2, 'labelAvailableAt': lookup[end].close_time.isoformat(),
                'executionStart': lookup[entry].open_time.isoformat(), 'executionEnd': lookup[exit].open_time.isoformat(),
                'monthlyExecutionEquityReturn': execution_equity_return(bars, entry, exit),
                'monthlyExecutionCashReturn': execution_cash['simpleReturn'], 'cpiRequired': False,
                'evidenceTier': 'SYNTHETIC_ONLY', 'realDataApproval': False})
    return output


def main() -> int:
    """Publish a bounded, zero-innovation equation fixture, never a power run."""
    import argparse
    from dataclasses import asdict
    import json
    from pathlib import Path
    from spy_predictor_quant.cycle1_power_gate import _publish_once
    from spy_predictor_quant.market_archive import file_sha256

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path('.'))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    config = json.loads((root / 'config/cycle1-v5-draft.json').read_text())
    scenario = json.loads((root / 'config/cycle1-simulation-v1.json').read_text())['scenarios'][0]
    start, end = date(2019, 12, 31), date(2020, 12, 31)
    monthly = tuple(MonthInnovations(month) for month in _months(date(2019, 10, 1), end))
    daily = tuple(SessionInnovations(row.date()) for row in _xnys().sessions_in_range(start.isoformat(), end.isoformat())[1:])
    result = run_equations(start=start, end=end, monthly=monthly, daily=daily, scenario=scenario, config=config)
    paths = {}
    for instrument, bars in result['bars'].items():
        serial = [{key: value.isoformat() if isinstance(value, (date, datetime)) else value
                   for key, value in asdict(row).items()} for row in bars]
        paths[instrument] = {'sessions': len(bars), 'pathHash': content_hash(serial)}
    report = {
        'schemaVersion': 'cycle1-equation-fixture-v1', 'status': 'EQUATIONS_EXECUTED_NOT_POWER_QUALIFIED',
        'equationHash': EQUATION_HASH, 'configHash': content_hash(config), 'scenarioHash': content_hash(scenario),
        'implementationHashes': {name: file_sha256(Path(__file__).with_name(name)) for name in (
            'cycle1_successor_equations.py', 'cycle1_successor_features.py', 'cycle1_successor_inputs.py',
            'cycle1_successor_calendar.py', 'cycle1_features.py', 'cycle1_calendar.py')},
        'fixture': 'explicit-zero-innovations-no-random-sampling', 'paths': paths,
        'targets': derive_successor_targets(result, (start,)), 'randomDraws': 0,
        'annualNullProven': False, 'fullProcedureQualified': False, 'realDataApproval': False,
    }
    report['reportHash'] = content_hash(report)
    path = root / 'reports' / ('cycle1-equation-fixture-' + report['reportHash'][:16]) / 'report.json'
    _publish_once(path, report)
    print(json.dumps({'status': report['status'], 'reportPath': str(path), 'reportHash': report['reportHash'],
                      'randomDraws': 0, 'realDataApproval': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
