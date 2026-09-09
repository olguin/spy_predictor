"""Deterministic scientific review of the candidate, never a simulation release."""
from dataclasses import replace
from datetime import date
import json
import math
from pathlib import Path

from spy_predictor_quant.cycle1_calendar import _xnys
from spy_predictor_quant.cycle1_power_gate import _publish_once
from spy_predictor_quant.cycle1_redesign import load_proposal
from spy_predictor_quant.cycle1_successor_equations import (
    EQUATION_HASH, EQUATION_SPEC, MonthInnovations, SessionInnovations, run_equations,
)
from spy_predictor_quant.market_archive import content_hash, file_sha256


def annual_variance(last_completed_log_volatility: float, scenario: dict) -> float:
    """SPY latent excess variance conditional on the last month's scale state.

    Assumes the proposed independent standardized Student and Gaussian laws.
    The engine updates h AFTER each month: future states start at phi*g+omega*z.
    This is NOT variance conditional on the actual nine observed features and
    does not by itself disprove their conditional independence null.
    """
    if (scenario['signal'] != 'none' or scenario['annualLocationAmplitude'] != 0
            or scenario['logScaleLoading'] != 0 or scenario['crashProbability'] != 0
            or scenario['studentDegreesOfFreedom'] <= 2):
        raise ValueError('Analytic variance requires the no-loading, no-crash scenario')
    phi, omega = scenario['volatilityPersistence'], scenario['volatilityInnovationSd']
    if not math.isfinite(last_completed_log_volatility) or not 0 <= phi < 1 or omega < 0:
        raise ValueError('Invalid volatility state or parameters')
    noise_variance = 0.0
    terms = []
    for horizon in range(1, 13):
        noise_variance = phi ** 2 * noise_variance + omega ** 2
        terms.append(math.exp(2 * phi ** horizon * last_completed_log_volatility + 2 * noise_variance))
    return EQUATION_SPEC['annualBaseVolatility'] ** 2 / 12 * math.fsum(terms)


def dividend_support_witness(config: dict, scenario: dict) -> dict:
    """A finite supplied Gaussian shock breaks positivity on an ex-date.

    A strict inequality persists on an open neighborhood, hence has positive
    probability under Gaussian support. No tail probability is estimated.
    """
    start, end = date(2019, 12, 31), date(2020, 3, 31)
    months = (date(2019, 10, 1), date(2019, 11, 1), date(2019, 12, 1),
              date(2020, 1, 1), date(2020, 2, 1), date(2020, 3, 1))
    monthly = tuple(MonthInnovations(month) for month in months)
    daily = tuple(SessionInnovations(row.date()) for row in
                  _xnys().sessions_in_range(start.isoformat(), end.isoformat())[1:])
    # Verify the ordinary fixture succeeds before isolating the ex-date shock.
    run_equations(start=start, end=end, monthly=monthly, daily=daily, scenario=scenario, config=config)
    ex_date = date(2020, 3, 2)
    shock = -2000.0
    stressed = tuple(replace(row, spy_overnight=shock) if row.session == ex_date else row for row in daily)
    try:
        run_equations(start=start, end=end, monthly=monthly, daily=stressed, scenario=scenario, config=config)
    except ValueError as error:
        if str(error) != 'Price, split and total-return levels must be positive':
            raise
        return {'status': 'POSITIVE_PRICE_SUPPORT_FAILURE', 'exDate': ex_date.isoformat(),
                'suppliedSpyOvernightNormal': shock, 'otherInnovations': 'dataclass defaults',
                'condition': 'overnight_log_increment < log(dividend_fraction)',
                'threshold': math.log(EQUATION_SPEC['quarterlyDividendFractionOfPreviousPostSplitClose']),
                'error': str(error), 'tailProbabilityEstimated': False}
    raise AssertionError('Candidate changed: re-review support instead of retaining a stale failure')


def review_readiness(root: Path) -> dict:
    proposal = load_proposal(root)
    config = json.loads((root / 'config/cycle1-v5-draft.json').read_text())
    scenario = proposal['preserved']['scenarios'][0]
    witness = dividend_support_witness(config, scenario)
    report = {
        'schemaVersion': 'cycle1-successor-readiness-v1', 'status': 'NOT_READY_TO_FREEZE',
        'proposalHash': proposal['proposalHash'], 'equationHash': EQUATION_HASH,
        'configHash': content_hash(config), 'scenarioHash': content_hash(scenario),
        'implementationHashes': {name: file_sha256(Path(__file__).with_name(name)) for name in (
            'cycle1_successor_readiness.py', 'cycle1_successor_equations.py',
            'cycle1_successor_features.py', 'cycle1_successor_inputs.py',
            'cycle1_successor_calendar.py', 'cycle1_features.py', 'cycle1_calendar.py')},
        'dividendSupport': witness,
        'annualNull': {
            'status': 'UNPROVEN_FOR_ACTUAL_FEATURES',
            'conditionalLatentAnnualVariances': {str(g): annual_variance(g, scenario) for g in (-.5, 0., .5)},
            'conditioning': 'log volatility used in the last completed month; independent proposed innovations',
            'formula': '0.15^2/12 * sum(j=1..12, exp(2*phi^j*g + 2*omega^2*sum(i=0..j-1, phi^(2*i))))',
            'limitation': 'Latent-state dependence is not a proof of incremental predictability from the supplied features.',
            'requiredProof': 'Annual return-law equality conditional on each declared baseline versus added cycle features, including the strong-baseline null.',
        },
        'nextSteps': [
            'Specify coherent positive-price dividend/return support without silent clipping or rejected-draw replacement.',
            'Establish the actual annual conditional null; reconcile any scenario changes explicitly before freeze.',
            'Bind final equations, laws, feature parity and authority hashes; atomically register the single redesign.',
            'Only then run development full-procedure profiling and the gated locked power audit.',
        ],
        'runtimeProfile': {'status': 'NOT_RUN', 'reason': 'Scientific prerequisites for successor release are unmet.'},
        'randomDraws': 0, 'redesignSlotsConsumedByReview': 0,
        'annualNullProven': False, 'fullProcedureQualified': False, 'realDataApproval': False,
    }
    report['reportHash'] = content_hash(report)
    return report


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path('.'))
    root = parser.parse_args().repo_root.resolve()
    report = review_readiness(root)
    path = root / 'reports' / ('cycle1-successor-readiness-' + report['reportHash'][:16]) / 'report.json'
    _publish_once(path, report)
    print(json.dumps({'status': report['status'], 'reportPath': str(path), 'reportHash': report['reportHash']}))
    return 2  # Completed review with unmet gates, not an execution error.


if __name__ == '__main__':
    raise SystemExit(main())
