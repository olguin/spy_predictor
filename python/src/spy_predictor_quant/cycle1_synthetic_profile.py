"""Bounded development profile; never releases locked seeds or authorizes real data."""
from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np

from spy_predictor_quant.cycle1_config import load_cycle1_plan
from spy_predictor_quant.cycle1_evaluator import evaluate_primary, score_partition, assess_partition
from spy_predictor_quant.cycle1_simulation_design import load_design
from spy_predictor_quant.cycle1_synthetic import generate_paths
from spy_predictor_quant.market_archive import content_hash, file_sha256


def profile(repo_root: Path) -> tuple[Path, dict]:
    design = load_design(repo_root / 'config/cycle1-simulation-v1.json', repo_root=repo_root)
    config = load_cycle1_plan(repo_root / design['preregistrationPath']).raw
    modules = ['cycle1_models.py', 'cycle1_evaluator.py', 'cycle1_synthetic.py',
               'cycle1_simulation_design.py', 'cycle1_synthetic_profile.py']
    identity = {'designHash': design['designHash'], 'preregistrationHash': design['preregistrationHash'],
                'implementationHashes': {name: file_sha256(Path(__file__).with_name(name)) for name in modules},
                'numpyVersion': np.__version__, 'pythonVersion': platform.python_version(),
                'stream': 'development', 'replicationsPerScenario': design['streams']['developmentReplicationsPerScenario']}
    identity_hash = content_hash(identity)
    directory = repo_root / 'reports' / ('cycle1-synthetic-profile-' + identity_hash[:16])
    output = directory / 'report.json'
    if output.exists():
        report = json.loads(output.read_text())
        if report['identity'] != identity or report['reportHash'] != content_hash({k:v for k,v in report.items() if k!='reportHash'}):
            raise ValueError('Existing profile identity/report hash mismatch')
        return output, report
    from spy_predictor_quant.cycle1_power_gate import read_terminal_decision
    if read_terminal_decision(repo_root) is not None:
        raise RuntimeError('Cycle 1 design is stopped; a new profile requires a documented successor design')
    directory.mkdir(parents=True, exist_ok=True)
    # The ledger must exist before the first scenario draw. An interrupted run
    # cannot silently reset the development budget or rerun under a new identity.
    opening = directory / 'opening.json'
    with opening.open('x') as handle:
        json.dump({'identity': identity, 'identityHash': identity_hash}, handle, indent=2)
    started = time.perf_counter()
    scenarios = []
    timed_out = False
    worst_seconds = []
    for index, scenario in enumerate(design['scenarios']):
        runs = []
        for replication in range(design['streams']['developmentReplicationsPerScenario']):
            if time.perf_counter()-started >= design['budget']['maximumProfileWallSeconds']:
                timed_out = True; break
            begin = time.perf_counter()
            path = generate_paths(design, index, replication)['SPY']
            result = evaluate_primary(path, config)
            procedure_seconds = time.perf_counter()-begin
            # Exercise the confirmation branch even if selection failed. This is
            # synthetic profiling only and never changes the procedure's decision.
            begin = time.perf_counter()
            exercise = assess_partition(score_partition(path, config, 'confirmation'), config, 'confirmation')
            extra_seconds = time.perf_counter()-begin
            worst_seconds.append(procedure_seconds+extra_seconds)
            runs.append({'replication':replication, 'procedure':result,
                         'confirmationBranchExerciseOnly':exercise,
                         'procedureSeconds':procedure_seconds, 'extraConfirmationProfileSeconds':extra_seconds})
        scenarios.append({'scenarioId':scenario['id'], 'requirement':scenario['requirement'],
                          'completedReplications':len(runs), 'runs':runs})
        if timed_out:
            break
    total_outer = len(design['scenarios']) * design['budget']['requiredOuterReplicationsPerScenario']
    projected = max(worst_seconds, default=0) * total_outer
    blockers = ['CONDITIONAL_FEATURE_SURROGATES_ONLY', 'DOWNSIDE_POLICY_TRANSFER_NOT_IMPLEMENTED',
                'LOCKED_VALIDATION_NOT_RUN']
    if timed_out:
        blockers.append('DEVELOPMENT_PROFILE_BUDGET_EXHAUSTED')
    if projected > design['budget']['maximumValidationWallSeconds']:
        blockers.append('PROJECTED_VALIDATION_EXCEEDS_COMPUTE_BUDGET')
    report = {'schemaVersion':'cycle1-synthetic-profile-v1', 'identity':identity, 'identityHash':identity_hash,
              'status':'DEVELOPMENT_ONLY_NOT_A_POWER_AUDIT', 'evidenceDecision':'INSUFFICIENT_EVIDENCE',
              'blockingReasons':blockers, 'realCandidateMetricsComputed':False,
              'realConfirmationOpened':False, 'lockedValidationReplications':0,
              'realEvaluationAuthorized':False, 'syntheticMetricsComputed':True,
              'scenarios':scenarios, 'profileWallSeconds':time.perf_counter()-started,
              'conservativeProjectedValidationSeconds':projected,
              'projectionRule':'maximum-observed-procedure-plus-extra-confirmation-branch-seconds-times-required-outer-count',
              'requiredValidationReplications':total_outer,
              'validationWallBudgetSeconds':design['budget']['maximumValidationWallSeconds'],
              'interpretation':'three-development-replications-are-not-estimates-of-qualified-power-or-family-wise-error;no-threshold-or-effect-changes-follow-from-this-profile'}
    report['reportHash'] = content_hash(report)
    with output.open('x') as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')
    return output, report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root',type=Path,default=Path('.'))
    args=parser.parse_args()
    path, report=profile(args.repo_root.resolve())
    print(json.dumps({k:v for k,v in report.items() if k not in ('scenarios','identity')}
                     | {'reportPath':str(path)},indent=2))


if __name__=='__main__':
    main()
