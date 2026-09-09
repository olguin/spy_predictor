"""Separate downside scoring; unavailable daily-close evidence never becomes a label."""
from __future__ import annotations

import numpy as np

from spy_predictor_quant.cycle1_models import MODEL_IDS, RIDGE_COLUMNS, UnavailableFold, tertile_index
from spy_predictor_quant.cycle1_evaluator import moving_block_counts, paired_bootstrap, holm_rejections


def logistic_fit(x: np.ndarray, y: np.ndarray, penalty: float) -> np.ndarray:
    """Deterministic damped Newton solve; summed log loss, unpenalized intercept."""
    design = np.column_stack([np.ones(len(x)), x])
    if not np.isfinite(design).all() or not np.isfinite(y).all() or np.unique(y).size != 2:
        raise UnavailableFold('Logistic fit requires finite observations and both classes')
    weights = np.full(design.shape[1], penalty); weights[0] = 0
    beta = np.zeros(design.shape[1]); beta[0] = np.log((y.sum()+1)/(len(y)-y.sum()+1))
    def objective(b):
        eta = design @ b
        return float(np.logaddexp(0,eta).sum()-y@eta+.5*np.dot(weights,b*b))
    for _ in range(100):
        eta = np.clip(design @ beta,-700,700)
        p = 1/(1+np.exp(-eta))
        gradient = design.T@(p-y)+weights*beta
        if np.max(np.abs(gradient)) < 1e-8:
            return beta
        hessian = design.T @ (design*(p*(1-p))[:,None]) + np.diag(weights)
        try:
            step = np.linalg.solve(hessian,gradient)
        except np.linalg.LinAlgError as error:
            raise UnavailableFold('Logistic curvature is singular') from error
        before=objective(beta);scale=1.0
        for _ in range(30):
            candidate=beta-scale*step
            if np.isfinite(candidate).all() and objective(candidate) <= before:
                beta=candidate;break
            scale*=.5
        else:
            raise UnavailableFold('Logistic solver failed to descend')
    raise UnavailableFold('Logistic solver did not converge')


def event_forecasts(cache: dict, path, events: np.ndarray, config: dict) -> np.ndarray:
    train=cache['trainingIndices']; index=cache['originIndex']
    y=events[train]; counts=[int(np.sum(y==value)) for value in (0,1)]
    result=np.full(7,np.nan)
    if not np.isfinite(y).all() or min(counts)<config['evaluationContract']['drawdown']['minimumClassObservations']:
        return result
    for m,spec in enumerate(config['models']['perInstrument']):
        model=cache['models'][spec['id']]
        if model is None:continue
        try:
            if spec['id'] in RIDGE_COLUMNS:
                cols=list(model.columns)
                train_x=(path.dimensions[train][:,cols]-model.means)/model.scales
                x=(path.dimensions[index,cols]-model.means)/model.scales
                beta=logistic_fit(train_x,y,1/spec['logisticC'])
                eta=beta[0]+x@beta[1:]
                result[m]=1/(1+np.exp(-np.clip(eta,-700,700)))
            elif spec['id']=='unconditional-history':
                result[m]=(y.sum()+1)/(len(y)+2)
            else:
                feature=(path.volatility[train] if spec['id']=='volatility-conditioned-history'
                         else path.dimensions[train].mean(axis=1))
                now=(path.volatility[index] if spec['id']=='volatility-conditioned-history'
                     else path.dimensions[index].mean())
                group=tertile_index(now,model.boundaries)
                selected=y[tertile_index(feature,model.boundaries)==group]
                result[m]=(selected.sum()+1)/(len(selected)+2)
        except UnavailableFold:
            pass
    return result


def calibration(y: np.ndarray, probabilities: np.ndarray, config: dict) -> dict:
    spec=config['evaluationContract']['drawdown']
    clip=spec['probabilityClip'];p=np.clip(probabilities,clip,1-clip)
    bins=np.minimum((p*spec['calibrationBins']).astype(int),spec['calibrationBins']-1)
    ece=0.0
    for group in range(spec['calibrationBins']):
        mask=bins==group
        if mask.any():ece+=mask.mean()*abs(p[mask].mean()-y[mask].mean())
    try:
        slope=float(logistic_fit(np.log(p/(1-p))[:,None],y,0)[1])
    except UnavailableFold:
        slope=None
    return {'brier':float(np.mean((p-y)**2)),
            'logLoss':float(np.mean(-y*np.log(p)-(1-y)*np.log1p(-p))),
            'expectedCalibrationError':float(ece),'slope':slope}


def assess_downside(scores, path, events: np.ndarray | None, config: dict,
                    eligible_claims: tuple[bool,bool]) -> dict:
    from spy_predictor_quant.cycle1_procedure import downside_support
    lookup={month:i for i,month in enumerate(path.months)}
    index=np.array([lookup[month] for month in scores.months])
    selected=None if events is None else events[index]
    support=downside_support(scores.months,selected,config)
    if support['status']=='INSUFFICIENT_SUPPORT':
        return support
    if scores.fitted is None:
        raise ValueError('Downside requires retained primary training folds')
    probabilities=np.full((len(index),2,7),np.nan)
    for (row,mode),cache in scores.fitted.items():
        probabilities[row,mode]=event_forecasts(cache,path,events,config)
    claims=[];gates=config['promotionGates']['drawdown']
    for claim,model in enumerate((5,6)):
        entry={'modelId':MODEL_IDS[model],'status':'INSUFFICIENT_SUPPORT','pValue':1.0,'qualified':False}
        if not eligible_claims[claim]:
            entry['status']='NOT_EVALUATED_PRIMARY_FAILED';claims.append(entry);continue
        valid=np.isfinite(probabilities[:,:,[0,1,2,3,4,model]]).all(axis=(1,2)) & np.isfinite(selected)
        pos=np.flatnonzero(valid)
        if len(pos)/len(index)<.95 or len(pos)<12 or np.any(np.diff(pos)!=1):
            claims.append(entry);continue
        y=selected[pos];p=probabilities[pos]
        improvements=(p[:,:,:5]-y[:,None,None])**2-(p[:,:,model,None]-y[:,None,None])**2
        bs=config['partitions']['bootstrap']
        indices,counts=moving_block_counts(len(pos),bs['blockLengthMonths'],bs['resamples'],bs['seed'])
        pvalues,_=paired_bootstrap(improvements.reshape(len(pos),10),indices,counts=counts)
        diagnostics=[];okay=True
        for mode in range(2):
            candidate=calibration(y,p[:,mode,model],config)
            baselines=[calibration(y,p[:,mode,b],config) for b in range(5)]
            slope=candidate['slope']
            mode_ok=(slope is not None and gates['minimumCalibrationSlope']<=slope<=gates['maximumCalibrationSlope']
                     and candidate['expectedCalibrationError']<=gates['maximumExpectedCalibrationError']
                     and all(candidate['logLoss']<=b['logLoss']+gates['maximumLogLossDegradation'] for b in baselines))
            okay=okay and mode_ok
            diagnostics.append({'mode':('expanding','rolling')[mode],**candidate})
        okay=okay and bool(np.all(improvements.mean(axis=0)>=gates['minimumAbsoluteBrierImprovement']))
        entry.update(status='EVALUATED',pValue=float(pvalues.max()),otherGatesPassed=bool(okay),diagnostics=diagnostics)
        claims.append(entry)
    rejections=holm_rejections([c['pValue'] for c in claims],config['promotionGates']['multipleTesting']['familyWiseAlpha'])
    for c,passed in zip(claims,rejections,strict=True):c['qualified']=bool(passed and c.get('otherGatesPassed',False))
    return {'status':'QUALIFIED_SECONDARY' if any(c['qualified'] for c in claims) else 'FAILED',
            'claims':claims,'affectsPrimaryQualification':False,
            'policyUseAllowed':any(c['qualified'] for c in claims)}
