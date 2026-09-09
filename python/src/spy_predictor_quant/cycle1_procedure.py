"""Conditional synthetic procedure with explicit evidence availability.

Monthly simulated returns are never relabeled as daily-close drawdown evidence
or next-session-open executable returns. Missing supplemental evidence yields
an unavailable downstream result, without changing primary qualification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from spy_predictor_quant.cycle1_evaluator import (
    FoldScores, assess_partition, score_partition, training_indices,
)
from spy_predictor_quant.cycle1_models import (
    MODEL_IDS, UnavailableFold, distribution_scores, fit_distribution, tertile_boundaries, tertile_index,
)
from spy_predictor_quant.cycle1_synthetic import SyntheticPath


def ordering_diagnostic(scores: FoldScores) -> list[dict]:
    result = []
    for mode in range(2):
        counts, means = [], []
        for group in range(3):
            mask = (scores.score_groups[:, mode] == group) & np.isfinite(scores.outcomes)
            counts.append(int(mask.sum()))
            means.append(float(scores.outcomes[mask].mean()) if mask.any() else None)
        supported = min(counts) >= 12
        result.append({'mode': ('expanding', 'rolling')[mode], 'role': 'DIAGNOSTIC_ONLY',
                       'counts': counts, 'meanReturns': means,
                       'strictlyIncreasing': bool(supported and means[0] < means[1] < means[2]),
                       'sufficientSupport': supported, 'affectsPrimaryQualification': False})
    return result


def transfer_report(qqq: SyntheticPath, spy_scores: FoldScores, config: dict,
                    qualified: tuple[bool, bool]) -> dict:
    if qqq.evidence_tier != 'SYNTHETIC_ONLY' or qqq.instrument != 'QQQ':
        raise ValueError('Transfer requires synthetic QQQ evidence')
    if spy_scores.fitted is None:
        raise ValueError('Transfer requires the retained SPY fits')
    forecasts = np.full((len(spy_scores.months), 2, 3), np.nan)
    errors, coverage, widths = (np.full_like(forecasts, np.nan) for _ in range(3))
    actual_outcomes = np.full(len(spy_scores.months), np.nan)
    lookup = {month: i for i, month in enumerate(qqq.months)}
    if any(qualified):
        for row, month in enumerate(spy_scores.months):
            index = lookup.get(month)
            if index is None or qqq.missing[index] or not np.isfinite(qqq.outcomes[index]):
                continue
            actual_outcomes[row] = qqq.outcomes[index]
            for mode_idx, mode in enumerate(config['partitions']['modes']):
                cache = spy_scores.fitted.get((row, mode_idx))
                if cache is None:
                    continue
                train = training_indices(qqq, index, mode, config)
                try:
                    reference = fit_distribution('unconditional-history', qqq.dimensions[train],
                                                 qqq.volatility[train], qqq.outcomes[train])
                    sample = reference.predict(qqq.dimensions[index], qqq.volatility[index])
                    values = distribution_scores(sample, qqq.outcomes[index])
                    for array, value in zip((forecasts,errors,coverage,widths),values,strict=True):
                        array[row,mode_idx,0] = value
                except UnavailableFold:
                    continue
                for claim, active in enumerate(qualified):
                    if not active:
                        continue
                    fitted = cache['models'][MODEL_IDS[5+claim]]
                    if fitted is None:
                        continue
                    try:
                        sample = fitted.predict(qqq.dimensions[index], qqq.volatility[index])
                        values = distribution_scores(sample, qqq.outcomes[index])
                        for array, value in zip((forecasts,errors,coverage,widths),values,strict=True):
                            array[row,mode_idx,claim+1] = value
                    except UnavailableFold:
                        pass
    assessed = assess_partition(FoldScores(spy_scores.months,forecasts,errors,coverage,widths,
                                          np.zeros((len(forecasts),2),int),
                                          np.full((len(forecasts),2),-1,int),actual_outcomes),
                                 config,'confirmation',eligible_claims=qualified,transfer_only=True)
    entries = []
    for claim, active in enumerate(qualified):
        if not active:
            entries.append({'entryId': 'QQQ:'+MODEL_IDS[5+claim], 'status': 'SKIPPED_SPY_NOT_QUALIFIED'})
            continue
        mask = np.isfinite(forecasts[:, :, [0, claim+1]]).all(axis=(1, 2))
        count = int(mask.sum())
        delta = forecasts[mask, :, 0] - forecasts[mask, :, claim+1]
        claim_result = assessed['claims'][claim]
        status = ('TRANSFER_SUPPORTS' if claim_result['qualified'] else
                  'TRANSFER_DOES_NOT_SUPPORT' if claim_result['status']=='EVALUATED' else 'TRANSFER_INSUFFICIENT')
        entries.append({'entryId': 'QQQ:'+MODEL_IDS[5+claim],
                        'status': status, 'claim': claim_result,
                        'pairedMonths': count,
                        'meanCrpsImprovement': delta.mean(axis=0).tolist() if count else None,
                        'parametersRefittedOnQqq': False})
    return {'entries': entries, 'referenceStatus': 'EVALUATED' if any(qualified) else 'SKIPPED_NO_SPY_SURVIVOR',
            'affectsSpyQualification': False, 'comparator':'QQQ:unconditional-history',
            'rule':'unchanged-SPY-numeric-gates-and-two-conditional-claim-family-against-registered-QQQ-reference'}


def distinct_event_episodes(origin_months: np.ndarray, positive: np.ndarray,
                            horizon_months: int = 12) -> int:
    """Connected components of overlapping positive target holding intervals."""
    starts = np.sort(origin_months[positive.astype(bool)].astype('datetime64[M]').astype(int))
    count, end = 0, None
    for start in starts:
        if end is None or start > end:
            count += 1
        end = max(start+horizon_months, end if end is not None else start)
    return count


def daily_drawdown_labels(dates: np.ndarray, levels: np.ndarray, starts: np.ndarray,
                          ends: np.ndarray, threshold: float = -.2) -> np.ndarray:
    if len(dates) != len(levels) or not np.isfinite(levels).all() or (levels <= 0).any():
        raise ValueError('Invalid daily total-return index')
    if np.any(np.diff(dates.astype('datetime64[D]').astype(int)) <= 0):
        raise ValueError('Daily close dates must be unique and ordered')
    result = np.full(len(starts), np.nan)
    for i, (start, end) in enumerate(zip(starts, ends, strict=True)):
        mask = (dates >= start) & (dates <= end)
        selected = dates[mask]
        if not len(selected) or selected[0] != start or selected[-1] != end:
            continue
        path = levels[mask]
        drawdown = np.min(path / np.maximum.accumulate(path) - 1)
        result[i] = drawdown <= threshold
    return result


def downside_support(origin_months: np.ndarray, events: np.ndarray | None, config: dict) -> dict:
    if events is None:
        return {'status': 'INSUFFICIENT_SUPPORT', 'reason': 'NO_PREREGISTERED_DAILY_CLOSE_PATH',
                'affectsPrimaryQualification': False, 'policyUseAllowed': False}
    available = np.isfinite(events)
    episodes = distinct_event_episodes(origin_months[available], events[available] > 0)
    required = config['evaluationContract']['drawdown']['minimumDistinctEventEpisodes']
    if episodes < required:
        return {'status': 'INSUFFICIENT_SUPPORT', 'distinctEpisodes': episodes,
                'requiredEpisodes': required, 'policyUseAllowed': False,
                'affectsPrimaryQualification': False}
    return {'status': 'SUPPORT_ADEQUATE_FOR_SECONDARY_TEST',
            'distinctEpisodes': episodes, 'policyUseAllowed': False,
            'affectsPrimaryQualification': False}


def policy_weights(scores: FoldScores, path: SyntheticPath, model_id: str, mode: int,
                   config: dict) -> np.ndarray:
    if scores.fitted is None:
        raise ValueError('Policy mapping requires retained fitted models')
    result=np.full(len(scores.months),np.nan)
    for row in range(len(scores.months)):
        cache=scores.fitted.get((row,mode))
        if cache is None:continue
        model=cache['models'][model_id]
        if model is None:continue
        train=cache['trainingIndices'];index=cache['originIndex']
        try:
            # The same fitted distribution defines both training and current
            # predictive means; no outcome quantiles or confirmation tuning.
            means=np.array([model.predict(path.dimensions[i],path.volatility[i]).mean() for i in train])
            bounds=tertile_boundaries(means)
            current=model.predict(path.dimensions[index],path.volatility[index]).mean()
            result[row]=config['promotionGates']['economicPolicy']['equityWeightsByForecastTertile'][int(tertile_index(current,bounds))]
        except UnavailableFold:
            pass
    return result


@dataclass(frozen=True)
class PolicyTape:
    """Verified next-session-open total returns, supplied independently of labels."""
    equity_returns: np.ndarray
    cash_returns: np.ndarray
    return_convention: str = 'NEXT_SESSION_OPEN_TO_NEXT_SESSION_OPEN_TOTAL_RETURN'


def policy_path(weights: np.ndarray, tape: PolicyTape, one_way_bps: float,
                *, terminal_liquidation: bool = True) -> dict:
    if tape.return_convention != 'NEXT_SESSION_OPEN_TO_NEXT_SESSION_OPEN_TOTAL_RETURN':
        raise ValueError('Policy requires executable monthly intervals, not annual labels')
    equity, cash = tape.equity_returns, tape.cash_returns
    if not (weights.shape == equity.shape == cash.shape) or len(weights) < 2:
        raise ValueError('Policy interval shapes do not match')
    if not all(np.isfinite(x).all() for x in (weights, equity, cash)):
        raise ValueError('Missing policy intervals cannot be imputed')
    if (weights < 0).any() or (weights > 1).any() or (equity <= -1).any() or (cash <= -1).any():
        raise ValueError('Invalid unlevered policy inputs')
    cost = one_way_bps / 10000
    returns, turnover = [], []
    drifted = 0.0
    for weight, er, cr in zip(weights, equity, cash, strict=True):
        traded = abs(weight-drifted)
        gross = weight*(1+er)+(1-weight)*(1+cr)
        returns.append((1-cost*traded)*gross-1)
        turnover.append(traded)
        drifted = weight*(1+er)/gross
    if terminal_liquidation:
        returns[-1] = (1+returns[-1])*(1-cost*drifted)-1
        turnover[-1] += drifted
    returns = np.array(returns)
    excess = returns-cash
    std = float(excess.std(ddof=1))
    wealth = np.concatenate([[1.0], np.cumprod(1+returns)])
    risk_ratio = float(np.sqrt(12)*excess.mean()/std) if std > 0 else None
    return {'monthlyReturns': returns, 'wealth': wealth,
            'annualReturn': float(wealth[-1]**(12/len(returns))-1),
            'maximumDrawdown': float(1-np.min(wealth/np.maximum.accumulate(wealth))),
            'riskRatio': risk_ratio, 'meanExcessReturn': float(excess.mean()),
            'annualTurnover': float(sum(turnover)*12/len(returns)),
            'monthlyVolatility': float(returns.std(ddof=1))}


def policy_report(selection_weights: np.ndarray, confirmation_weights: np.ndarray,
                  selection_tape: PolicyTape, confirmation_tape: PolicyTape, config: dict) -> dict:
    gates = config['promotionGates']['economicPolicy']
    base_cost = gates['oneWayTransactionCostBps']
    selection = policy_path(selection_weights, selection_tape, base_cost)
    grid = np.arange(101)/100
    differences = [abs(policy_path(np.full(len(selection_weights), w), selection_tape, base_cost)['monthlyVolatility']
                       - selection['monthlyVolatility']) for w in grid]
    weight = float(grid[int(np.argmin(differences))])  # First minimum selects the lowest weight.
    reports = []
    for multiplier in (1, gates['stressCostMultiplier']):
        cost = base_cost*multiplier
        policy = policy_path(confirmation_weights, confirmation_tape, cost)
        static = policy_path(np.full(len(confirmation_weights), weight), confirmation_tape, cost)
        cash = policy_path(np.zeros(len(confirmation_weights)), confirmation_tape, cost)
        buy_hold = policy_path(np.ones(len(confirmation_weights)), confirmation_tape, cost)
        checks = {'riskTradeoff': policy['riskRatio'] is not None and static['riskRatio'] is not None
                  and policy['riskRatio']-static['riskRatio'] >= gates['minimumRiskAdjustedTradeoffImprovement'],
                  'returnShortfall': policy['annualReturn'] >= static['annualReturn']-gates['maximumAnnualizedReturnShortfall'],
                  'drawdownImprovement': static['maximumDrawdown']-policy['maximumDrawdown'] >= gates['minimumMaximumDrawdownImprovement'],
                  'turnover': policy['annualTurnover'] <= gates['maximumAnnualTurnover'],
                  'excessOverCash': policy['meanExcessReturn'] > 0}
        def summary(result):
            return {k:v for k,v in result.items() if k not in ('wealth','monthlyReturns')}
        reports.append({'costMultiplier':multiplier, 'checks':{k:bool(v) for k,v in checks.items()},
                        'policy':summary(policy), 'static':summary(static),
                        'cash':summary(cash), 'buyAndHold':summary(buy_hold)})
    return {'status':'QUALIFIED_FOR_FURTHER_TESTING' if all(all(r['checks'].values()) for r in reports) else 'FAILED',
            'staticSelectionWeight':weight, 'costCases':reports, 'affectsPrimaryQualification':False}


def evaluate_procedure(paths: dict[str, SyntheticPath], config: dict,
                       *, exercise_confirmation: bool = False,
                       supplemental: dict | None = None) -> dict[str, Any]:
    from spy_predictor_quant.cycle1_downside import assess_downside
    spy, qqq = paths['SPY'], paths['QQQ']
    selection_scores = score_partition(spy, config, 'selection', retain_fits=True)
    selection = assess_partition(selection_scores, config, 'selection')
    survivors = tuple(c['qualified'] for c in selection['claims'])
    confirmation_scores = None
    if any(survivors) or exercise_confirmation:
        confirmation_scores = score_partition(spy, config, 'confirmation', retain_fits=True)
    if any(survivors):
        confirmation = assess_partition(confirmation_scores, config, 'confirmation', eligible_claims=survivors)
    else:
        confirmation = {'partition':'confirmation', 'status':'NOT_OPENED_NO_SELECTION_SURVIVOR',
                        'claims':[{'modelId':name,'qualified':False,'pValue':1.0,
                                   'status':'SKIPPED_SELECTION_FAILED'} for name in MODEL_IDS[5:]]}
    qualified = tuple(c['qualified'] for c in confirmation['claims'])
    primary = {'evidenceTier':'SYNTHETIC_ONLY','selection':selection,'confirmation':confirmation,
               'qualified':any(qualified),'realDataApproval':False}
    if confirmation_scores is not None:
        transfer = transfer_report(qqq, confirmation_scores, config, qualified)
    else:
        transfer = {'entries':[{'entryId':'QQQ:'+name,'status':'SKIPPED_SPY_NOT_QUALIFIED'} for name in MODEL_IDS[5:]],
                    'referenceStatus':'SKIPPED_NO_SPY_SURVIVOR','affectsSpyQualification':False}
    ledger = [{'entryId': row['entryId'],
               'status': ('EVALUATED_SELECTION' if row['instrument']=='SPY' else
                          'SKIPPED_NO_SPY_SURVIVOR' if not any(qualified) else 'CONDITIONAL_TRANSFER')}
              for row in config['evaluationLedger']]
    extra=supplemental or {}
    downside=assess_downside(confirmation_scores if confirmation_scores is not None else selection_scores,
                             spy,extra.get('drawdownEvents'),config,qualified)
    policy={'status':'NOT_EVALUATED','reason':'NO_PREREGISTERED_EXECUTION_PRICE_PATH',
            'affectsPrimaryQualification':False}
    if 'selectionTape' in extra and 'confirmationTape' in extra:
        analyses=[]
        for claim,active in enumerate(qualified):
            if not active:continue
            for mode in range(2):
                selection_weights=policy_weights(selection_scores,spy,MODEL_IDS[5+claim],mode,config)
                confirmation_weights=policy_weights(confirmation_scores,spy,MODEL_IDS[5+claim],mode,config)
                if not np.isfinite(selection_weights).all() or not np.isfinite(confirmation_weights).all():
                    analyses.append({'modelId':MODEL_IDS[5+claim],'mode':mode,'status':'NOT_EVALUATED_UNAVAILABLE_FORECAST'})
                else:
                    analyses.append({'modelId':MODEL_IDS[5+claim],'mode':mode,
                                     **policy_report(selection_weights,confirmation_weights,
                                                     extra['selectionTape'],extra['confirmationTape'],config)})
        policy={'status':'EVALUATED' if analyses else 'NOT_EVALUATED_PRIMARY_FAILED',
                'analyses':analyses,'affectsPrimaryQualification':False}
    result = {'primary':primary, 'ledger':ledger, 'transfer':transfer,
              'selectionScoreOrdering':ordering_diagnostic(selection_scores),
              'downside': downside, 'policy':policy,
              'scopeCompleteForRealApproval':False,
              'scopeLimitations':['CONDITIONAL_FEATURE_SURROGATES','NO_DAILY_CLOSE_GENERATOR',
                                  'NO_EXECUTION_OPEN_GENERATOR'],
              'realDataApproval':False}
    if exercise_confirmation:
        result['confirmationBranchExerciseOnly'] = assess_partition(confirmation_scores,config,'confirmation')
        result['transferBranchExerciseOnly'] = transfer_report(qqq,confirmation_scores,config,(True,True))
    return result
