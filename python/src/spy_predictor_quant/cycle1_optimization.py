"""Exact regression verification and bounded profiling on the frozen development set."""
from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np

from spy_predictor_quant.cycle1_config import load_cycle1_plan
from spy_predictor_quant.cycle1_evaluator import score_partition, assess_partition
from spy_predictor_quant.cycle1_simulation_design import load_design
from spy_predictor_quant.cycle1_synthetic import generate_paths
from spy_predictor_quant.cycle1_procedure import evaluate_procedure
from spy_predictor_quant.market_archive import content_hash, file_sha256
from spy_predictor_quant.cycle1_power_gate import _publish_once, read_terminal_decision

MODULES = ('cycle1_models.py','cycle1_evaluator.py','cycle1_synthetic.py','cycle1_simulation_design.py',
           'cycle1_synthetic_profile.py','cycle1_procedure.py','cycle1_downside.py','cycle1_optimization.py')


def run_optimization(repo_root: Path) -> tuple[Path, dict]:
    repo_root=repo_root.resolve()
    design=load_design(repo_root/'config/cycle1-simulation-v1.json',repo_root=repo_root)
    config=load_cycle1_plan(repo_root/design['preregistrationPath']).raw
    reference=repo_root/'reports/cycle1-optimization-reference-v1'
    identities={'designHash':design['designHash'],'preregistrationHash':design['preregistrationHash'],
                'implementationHashes':{name:file_sha256(Path(__file__).with_name(name)) for name in MODULES},
                'numpyVersion':np.__version__,'pythonVersion':platform.python_version(),
                'stream':'development','replicationsPerScenario':3,
                'referenceScoresSha256':file_sha256(reference/'scores.npz'),
                'referenceAssessmentsSha256':file_sha256(reference/'assessments.json')}
    identity_hash=content_hash(identities)
    folder=repo_root/'reports'/('cycle1-optimization-'+identity_hash[:16])
    output=folder/'report.json'
    if output.exists():
        result=json.loads(output.read_text())
        if result['identity']!=identities or result['reportHash']!=content_hash({k:v for k,v in result.items() if k!='reportHash'}):
            raise ValueError('Saved optimization report identity mismatch')
        return output,result
    if read_terminal_decision(repo_root) is not None:
        raise RuntimeError('Cycle 1 design is stopped; no new optimization run is authorized by this design')
    opening=folder/'opening.json'
    if opening.exists():
        raise ValueError('Interrupted optimization opening requires explicit investigation')
    _publish_once(opening,{'identity':identities,'identityHash':identity_hash})
    old=np.load(reference/'scores.npz')
    old_reports=json.loads((reference/'assessments.json').read_text())
    verified=0
    # Equivalence checks precede timed profiling. This also initializes the
    # outcome-independent cache; setup cost is separately recorded, not discarded.
    setup_start=time.perf_counter()
    for index in range(len(design['scenarios'])):
        for replication in range(3):
            paths=generate_paths(design,index,replication)
            for instrument,path in paths.items():
                for name in ('outcomes','monthly_returns'):
                    np.testing.assert_array_equal(old[f'{index}_{replication}_{instrument}_{name}'],getattr(path,name))
            for part in ('selection','confirmation'):
                scores=score_partition(paths['SPY'],config,part,retain_fits=True)
                key=f'{index}_{replication}_{part}'
                for name in ('losses','squared_errors','interval_coverage','interval_width','training_counts','score_groups'):
                    np.testing.assert_array_equal(old[key+'_'+name],getattr(scores,name))
                if assess_partition(scores,config,part)!=old_reports[key]:
                    raise ValueError('Optimization changed a frozen assessment: '+key)
                verified+=1
    setup_seconds=time.perf_counter()-setup_start
    scenarios=[];durations=[]
    begin=time.perf_counter()
    for index,scenario in enumerate(design['scenarios']):
        runs=[]
        for replication in range(3):
            if time.perf_counter()-begin>design['budget']['maximumProfileWallSeconds']:
                raise RuntimeError('Frozen development profile wall budget exhausted')
            start=time.perf_counter()
            paths=generate_paths(design,index,replication)
            procedure=evaluate_procedure(paths,config,exercise_confirmation=True)
            elapsed=time.perf_counter()-start
            # Exact primary reports must also survive orchestration and retained-fit reuse.
            if procedure['primary']['selection']!=old_reports[f'{index}_{replication}_selection']:
                raise ValueError('Orchestration changed the primary selection decision')
            if procedure['confirmationBranchExerciseOnly']!=old_reports[f'{index}_{replication}_confirmation']:
                raise ValueError('Orchestration changed the confirmation branch')
            durations.append(elapsed)
            primary=dict(procedure['primary'])
            primary.update(downside=procedure['downside']['status'],policy=procedure['policy']['status'],
                           transfer='SCOPED_TRANSFER_SCORED_IN_BRANCH_EXERCISE')
            runs.append({'replication':replication,'procedure':primary,'completeAvailableProcedure':procedure,
                         'procedureSeconds':elapsed,'extraConfirmationProfileSeconds':0.0})
        scenarios.append({'scenarioId':scenario['id'],'requirement':scenario['requirement'],
                          'completedReplications':3,'runs':runs})
    required=len(scenarios)*design['budget']['requiredOuterReplicationsPerScenario']
    projected=max(durations)*required
    limitations=sorted({reason for s in scenarios for r in s['runs']
                        for reason in r['completeAvailableProcedure']['scopeLimitations']})
    blockers=list(limitations)+['LOCKED_VALIDATION_NOT_RUN']
    if projected>design['budget']['maximumValidationWallSeconds']:
        blockers.append('PROJECTED_VALIDATION_EXCEEDS_COMPUTE_BUDGET')
    result={'schemaVersion':'cycle1-optimization-profile-v1','status':'DEVELOPMENT_ONLY_NOT_A_POWER_AUDIT',
            'identity':identities,'identityHash':identity_hash,'scenarios':scenarios,
            'equivalence':{'status':'EXACT_MATCH','partitionReports':verified,'scoreArrays':verified*6,
                           'pathArrays':30*2*2,'comparisonRule':'bit-for-bit-numpy-array-equality-and-exact-report-equality',
                           'scientificConfigChanged':False,'newReplicationIndicesUsed':False},
            'profileWallSeconds':time.perf_counter()-begin,'verificationAndSetupSeconds':setup_seconds,
            'conservativeProjectedValidationSeconds':projected,'requiredValidationReplications':required,
            'validationWallBudgetSeconds':design['budget']['maximumValidationWallSeconds'],
            'projectionRule':'maximum-observed-all-available-branches-duration-times-required-outer-count;cache-setup-recorded-separately',
            'profiledFullProcedure':False,'profiledScope':'all-implemented-available-branches-including-QQQ-transfer;missing-generator-and-claim-scope-remains-explicit',
            'blockingReasons':blockers,'evidenceDecision':'INSUFFICIENT_EVIDENCE',
            'realCandidateMetricsComputed':False,'realConfirmationOpened':False,
            'realEvaluationAuthorized':False,'lockedValidationReplications':0,'syntheticMetricsComputed':True}
    result['reportHash']=content_hash(result)
    _publish_once(output,result)
    return output,result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root',type=Path,default=Path('.'))
    args=parser.parse_args()
    path,result=run_optimization(args.repo_root)
    print(json.dumps({'reportPath':str(path),'reportHash':result['reportHash'],
                      'equivalence':result['equivalence'],'profileWallSeconds':result['profileWallSeconds'],
                      'conservativeProjectedValidationSeconds':result['conservativeProjectedValidationSeconds'],
                      'validationWallBudgetSeconds':result['validationWallBudgetSeconds'],
                      'profiledFullProcedure':False,'blockingReasons':result['blockingReasons']},indent=2))


if __name__=='__main__':main()
