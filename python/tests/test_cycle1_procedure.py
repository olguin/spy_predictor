from __future__ import annotations
from pathlib import Path
import numpy as np
import pytest
from spy_predictor_quant.cycle1_config import load_cycle1_plan
from spy_predictor_quant.cycle1_evaluator import score_partition
from spy_predictor_quant.cycle1_simulation_design import load_design
from spy_predictor_quant.cycle1_synthetic import generate_paths
from spy_predictor_quant.cycle1_procedure import (
    PolicyTape,daily_drawdown_labels,distinct_event_episodes,downside_support,
    policy_path,policy_report,transfer_report,evaluate_procedure,
)
ROOT=Path(__file__).resolve().parents[2]

@pytest.fixture(scope='module')
def config():return load_cycle1_plan(ROOT/'config/cycle1-v5-draft.json').raw

@pytest.fixture(scope='module')
def paths():
    d=load_design(ROOT/'config/cycle1-simulation-v1.json',repo_root=ROOT)
    return generate_paths(d,0,0)


def test_policy_costs_weight_drift_and_terminal_liquidation():
    tape=PolicyTape(np.array([.1,-.1]),np.zeros(2))
    weights=np.array([.5,.5])
    result=policy_path(weights,tape,5)
    cost=.0005
    first=(1-cost*.5)*1.05
    drift=.55/1.05
    second=(1-cost*abs(.5-drift))*.95
    terminal=.45/.95
    assert result['wealth'][-1]==pytest.approx(first*second*(1-cost*terminal))
    assert result['annualTurnover']==pytest.approx((.5+abs(.5-drift)+terminal)*6)
    more=policy_path(weights,tape,10)
    assert more['wealth'][-1]<result['wealth'][-1]


def test_cash_has_no_undefined_ratio_invented():
    tape=PolicyTape(np.array([.1,-.1]),np.array([.001,.001]))
    result=policy_path(np.zeros(2),tape,5)
    assert result['riskRatio'] is None
    assert result['annualTurnover']==0


def test_policy_rejects_annual_label_returns_and_missing_intervals():
    with pytest.raises(ValueError,match='executable'):
        policy_path(np.ones(2),PolicyTape(np.ones(2),np.zeros(2),'OVERLAPPING_ANNUAL_LABELS'),5)
    with pytest.raises(ValueError,match='Missing'):
        policy_path(np.ones(2),PolicyTape(np.array([.1,np.nan]),np.zeros(2)),5)


def test_static_benchmark_uses_selection_only_and_lowest_weight_tie(config):
    selection=PolicyTape(np.zeros(24),np.zeros(24))
    confirmation=PolicyTape(np.linspace(-.1,.1,24),np.zeros(24))
    # Zero exposure gives a unique zero-cost constant benchmark, whose lowest grid weight is 0.
    result=policy_report(np.zeros(24),np.ones(24)*.75,selection,confirmation,config)
    assert result['staticSelectionWeight']==0
    assert len(result['costCases'])==2
    assert result['affectsPrimaryQualification'] is False


def test_daily_drawdown_uses_intramonth_closes_not_only_endpoints():
    dates=np.array(['2020-01-31','2020-02-14','2021-01-29'],dtype='datetime64[D]')
    result=daily_drawdown_labels(dates,np.array([100.,70.,110.]),dates[:1],dates[-1:])
    assert result[0]==1
    # Unavailable endpoint remains missing, not a negative event.
    result=daily_drawdown_labels(dates,np.array([100.,70.,110.]),dates[:1],np.array(['2021-02-26'],dtype='datetime64[D]'))
    assert np.isnan(result[0])


def test_episode_counts_merge_overlapping_positive_labels(config):
    months=np.arange('2000-01','2003-01',dtype='datetime64[M]')
    event=np.zeros(36,dtype=bool);event[[0,1,12,25]]=True
    assert distinct_event_episodes(months,event)==2
    support=downside_support(months,event.astype(float),config)
    assert support['status']=='INSUFFICIENT_SUPPORT'
    assert support['policyUseAllowed'] is False
    assert downside_support(months,None,config)['reason']=='NO_PREREGISTERED_DAILY_CLOSE_PATH'


def test_transfer_reuses_spy_models_without_refitting_them(paths,config,monkeypatch):
    import spy_predictor_quant.cycle1_procedure as procedure
    scores=score_partition(paths['SPY'],config,'confirmation',retain_fits=True)
    original=procedure.fit_distribution;calls=[]
    def reference_only(model,*args,**kwargs):
        calls.append(model)
        assert model=='unconditional-history'
        return original(model,*args,**kwargs)
    monkeypatch.setattr(procedure,'fit_distribution',reference_only)
    result=transfer_report(paths['QQQ'],scores,config,(True,False))
    assert calls and set(calls)=={'unconditional-history'}
    assert result['entries'][0]['pairedMonths']==97
    assert result['entries'][1]['status']=='SKIPPED_SPY_NOT_QUALIFIED'
    assert result['affectsSpyQualification'] is False


def test_procedure_never_rescues_primary_with_auxiliary_outputs(paths,config):
    from spy_predictor_quant.cycle1_evaluator import evaluate_primary
    result=evaluate_procedure(paths,config,exercise_confirmation=True)
    original=evaluate_primary(paths['SPY'],config)
    assert result['primary']['selection']==original['selection']
    assert result['primary']['confirmation']==original['confirmation']
    assert len(result['ledger'])==10
    assert result['realDataApproval'] is False
    assert result['downside']['status']=='INSUFFICIENT_SUPPORT'
    assert result['policy']['status']=='NOT_EVALUATED'


def test_secondary_logistic_solver_matches_score_equations():
    from spy_predictor_quant.cycle1_downside import logistic_fit
    rng=np.random.default_rng(921)
    x=rng.normal(size=(200,2));y=(rng.random(200)<1/(1+np.exp(-x[:,0]))).astype(float)
    beta=logistic_fit(x,y,10)
    z=np.column_stack([np.ones(len(x)),x]);p=1/(1+np.exp(-(z@beta)))
    gradient=z.T@(p-y)+np.array([0,10,10])*beta
    assert np.max(np.abs(gradient))<1e-8
    with pytest.raises(Exception,match='both classes'):
        logistic_fit(x,np.zeros(len(x)),10)


def test_secondary_smoothing_and_class_support_preserve_primary(paths,config):
    from spy_predictor_quant.cycle1_downside import event_forecasts
    scores=score_partition(paths['SPY'],config,'selection',retain_fits=True)
    cache=scores.fitted[(0,0)];train=cache['trainingIndices']
    events=np.zeros(len(paths['SPY'].months));events[train[::3]]=1
    forecast=event_forecasts(cache,paths['SPY'],events,config)
    assert forecast[0]==pytest.approx((40+1)/(120+2))
    assert np.isfinite(forecast).all()
    before=scores.losses.copy()
    unavailable=event_forecasts(cache,paths['SPY'],np.zeros_like(events),config)
    assert np.isnan(unavailable).all()
    np.testing.assert_array_equal(scores.losses,before)


def test_transfer_retains_frozen_numeric_gates_and_one_registered_reference(paths,config):
    scores=score_partition(paths['SPY'],config,'confirmation',retain_fits=True)
    result=transfer_report(paths['QQQ'],scores,config,(True,True))
    assert result['comparator']=='QQQ:unconditional-history'
    for row in result['entries']:
        assert len(row['claim']['componentPValues'])==2  # One reference in each mode.
        assert set(row['claim']['gates'])=={'materiality','bootstrapLowerBound','rmse','eras','concentration','confirmationHalves'}
    assert result['affectsSpyQualification'] is False
