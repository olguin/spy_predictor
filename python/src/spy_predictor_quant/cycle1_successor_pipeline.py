"""Repaired daily evidence adapter and complete synthetic procedure.

Explicit innovations only: this entry point cannot open random streams or real
data. The stopped v1 evaluator remains unchanged and supplies shared arithmetic.
"""
from __future__ import annotations

from datetime import date
import math

import numpy as np

from spy_predictor_quant.cycle1_successor_equations import (
    EQUATION_HASH, derive_successor_targets, run_equations,
)
from spy_predictor_quant.cycle1_successor_laws import REPAIR_HASH
from spy_predictor_quant.cycle1_synthetic import SyntheticPath
from spy_predictor_quant.cycle1_procedure import (
    PolicyTape, evaluate_procedure, policy_weights, policy_report,
)
from spy_predictor_quant.cycle1_evaluator import score_partition
from spy_predictor_quant.cycle1_models import MODEL_IDS
from spy_predictor_quant.cycle1_downside import assess_downside
from spy_predictor_quant.market_archive import content_hash


def adapt_evidence(evidence: dict, config: dict) -> tuple[dict, dict]:
    if (evidence.get('evidenceTier') != 'SYNTHETIC_ONLY'
            or evidence.get('equationHash') != content_hash({'base': EQUATION_HASH, 'repair': REPAIR_HASH})):
        raise ValueError('Full pipeline requires repaired synthetic equation evidence')
    features = evidence['features']
    origins = tuple(date.fromisoformat(row['cutoff'][:10]) for row in features['SPY'])
    months = np.array([day.isoformat()[:7] for day in origins], dtype='datetime64[M]')
    if len(months) < 13 or np.any(np.diff(months.astype(int)) != 1):
        raise ValueError('Evidence must retain every monthly origin including warmup')
    targets = derive_successor_targets(evidence, origins[:-12])
    paths, events, execution = {}, {}, {}
    for instrument in ('SPY', 'QQQ'):
        rows = features[instrument]
        if tuple(date.fromisoformat(row['cutoff'][:10]) for row in rows) != origins:
            raise ValueError('Instruments must share the fixed calendar')
        n = len(months)
        dimensions = np.full((n, 3), np.nan)
        volatility, outcomes, monthly, drawdown, equity, cash = (np.full(n, np.nan) for _ in range(6))
        missing = np.ones(n, dtype=bool)
        for i, row in enumerate(rows):
            if row['status'] == 'AVAILABLE':
                dimensions[i] = [row['dimensionScores'][name] for name in ('valuation', 'stress', 'direction')]
                volatility[i] = row['rawFeatures']['realized-volatility-3m']
                missing[i] = False
        lookup = {day.isoformat(): i for i, day in enumerate(origins)}
        for row in targets:
            if row['instrument'] != instrument:
                continue
            i = lookup[row['origin']]
            outcomes[i] = row['annualExcessLogReturn']
            drawdown[i] = float(row['drawdownEvent'])
            equity[i] = row['monthlyExecutionEquityReturn']
            cash[i] = row['monthlyExecutionCashReturn']
        # These are monthly EXCESS close returns, never executable returns.
        for row in evidence['parameters']:
            if row['instrument'] == instrument:
                i = int(np.searchsorted(months, np.datetime64(row['month'][:7], 'M')))
                monthly[i] = row['monthlyExcessLogReturn']
        for i in range(n - 12):
            if not math.isclose(outcomes[i], float(monthly[i+1:i+13].sum()), abs_tol=1e-10):
                raise ValueError('Daily accounting does not preserve monthly endpoint law')
        paths[instrument] = SyntheticPath(months.copy(), dimensions, volatility, outcomes, monthly, missing, instrument)
        events[instrument] = drawdown
        execution[instrument] = (equity, cash)
    supplemental = {'drawdownEvents': events['SPY']}
    cal = config['partitions']['fixedCalendar']
    for partition in ('selection', 'confirmation'):
        start = cal['selectionForecastStart' if partition == 'selection' else 'confirmationStart'][:7]
        mask = (months >= np.datetime64(start, 'M')) & (months <= np.datetime64(cal[partition+'End'][:7], 'M'))
        if mask.sum() != config['partitions']['fixedCalendarCounts'][partition]:
            raise ValueError('Generated path does not cover the fixed evaluation calendar')
        equity, cash = execution['SPY']
        if not np.isfinite(equity[mask]).all() or not np.isfinite(cash[mask]).all():
            raise ValueError('Missing executable interval; never compress or impute')
        supplemental[partition+'Tape'] = PolicyTape(equity[mask], cash[mask])
    return paths, supplemental


def evaluate_evidence(evidence: dict, config: dict, *, exercise_branches: bool = False) -> dict:
    paths, supplemental = adapt_evidence(evidence, config)
    result = evaluate_procedure(paths, config, supplemental=supplemental,
                                exercise_confirmation=exercise_branches)
    result['scopeLimitations'] = ['NOT_REGISTERED_OR_POWER_QUALIFIED', 'REAL_DATA_PARITY_AND_QUALIFICATION_PENDING']
    result['evidencePath'] = {
        'equationHash': evidence['equationHash'], 'features': 'actual-nine-feature-extractor',
        'targets': 'shared-daily-close-path-minus-publication-admissible-cash',
        'policy': 'shareholder-next-open-accounting-with-base-and-stress-costs',
        'monthlyOrigins': len(paths['SPY'].months),
        'dailySessions': {name: len(rows) for name, rows in evidence['bars'].items()},
    }
    if exercise_branches:
        # Eligibility is forced ONLY in separately labeled fixture diagnostics.
        # The counted primary and conditional downstream results above stand.
        spy = paths['SPY']
        selection = score_partition(spy, config, 'selection', retain_fits=True)
        confirmation = score_partition(spy, config, 'confirmation', retain_fits=True)
        result['downsideBranchExerciseOnly'] = assess_downside(
            confirmation, spy, supplemental['drawdownEvents'], config, (True, True))
        policies = []
        for model in MODEL_IDS[5:]:
            for mode in range(2):
                before = policy_weights(selection, spy, model, mode, config)
                after = policy_weights(confirmation, spy, model, mode, config)
                assessment = (policy_report(before, after, supplemental['selectionTape'],
                                            supplemental['confirmationTape'], config)
                              if np.isfinite(before).all() and np.isfinite(after).all()
                              else {'status': 'NOT_EVALUATED_UNAVAILABLE_FORECAST'})
                policies.append({'modelId': model, 'mode': mode, **assessment})
        result['policyBranchExerciseOnly'] = policies
    return result


def run_pipeline(*, start, end, monthly, daily, scenario, config,
                 exercise_branches: bool = False) -> dict:
    evidence = run_equations(start=start, end=end, monthly=monthly, daily=daily,
                             scenario=scenario, config=config, repaired=True)
    return evaluate_evidence(evidence, config, exercise_branches=exercise_branches)
