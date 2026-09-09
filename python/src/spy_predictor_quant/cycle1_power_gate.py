"""Terminal, append-only review of frozen Cycle 1 power-audit prerequisites.

This command reads verified synthetic evidence only. It cannot draw validation
samples, fit candidates, start acquisition, or issue a positive power decision.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from spy_predictor_quant.cycle1_config import load_cycle1_plan
from spy_predictor_quant.cycle1_simulation_design import load_design
from spy_predictor_quant.cycle1_source_audit import load_cycle1_source_audit
from spy_predictor_quant.market_archive import content_hash, file_sha256

REVIEW_PATH = 'config/cycle1-power-review-v1.json'
DECISION_PATH = 'experiments/cycle1-power-v1/decision.json'
PROFILE_MODULES = ('cycle1_models.py', 'cycle1_evaluator.py', 'cycle1_synthetic.py',
                   'cycle1_simulation_design.py', 'cycle1_synthetic_profile.py',
                   'cycle1_procedure.py', 'cycle1_downside.py', 'cycle1_optimization.py')


def _local(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError('Power evidence path escapes repository')
    return path


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('Power evidence must be a JSON object')
    return value


def _check_hash(value: dict, key: str) -> None:
    if value.get(key) != content_hash({k:v for k,v in value.items() if k != key}):
        raise ValueError(f'Power evidence {key} mismatch')


def _review(root: Path) -> dict:
    review = _read(root / REVIEW_PATH)
    schema = _read(root / 'schemas/cycle1-power-review-v1.schema.json')
    errors = list(Draft202012Validator(schema).iter_errors(review))
    if errors:
        raise ValueError('Invalid frozen power review: ' + errors[0].message)
    _check_hash(review, 'reviewHash')
    return review


def _publish_once(path: Path, value: dict) -> None:
    """Publish complete bytes with atomic no-replace semantics and durable flush."""
    encoded = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.power-', delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise ValueError(f'Refusing to replace immutable power artifact: {path.name}')
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink()


def read_terminal_decision(repo_root: Path) -> dict | None:
    """Read the stop without fitting or requiring the old implementation to run."""
    record_path = repo_root / DECISION_PATH
    if not record_path.exists():
        return None
    record = _read(record_path)
    _check_hash(record, 'recordHash')
    if (record.get('state') != 'STOPPED' or record.get('decision') != 'INSUFFICIENT_EVIDENCE'
            or record.get('historicalConfirmationAllowed') is not False
            or record.get('realCandidateEvaluationAllowed') is not False
            or record.get('maximumRedesigns') != 1 or record.get('redesignsUsed') != 0
            or record.get('automaticRedesign') is not False):
        raise ValueError('Invalid terminal Cycle 1 state; progression remains closed')
    report_path = _local(repo_root, record['reportPath'])
    if file_sha256(report_path) != record['reportSha256']:
        raise ValueError('Terminal power report file hash mismatch')
    report = _read(report_path)
    _check_hash(report, 'reportHash')
    if (report['reportHash'] != record['reportHash'] or report['decision'] != record['decision']
            or report['designHash'] != record['designHash'] or report['reviewHash'] != record['reviewHash']
            or report['progression']['historicalConfirmationAllowed'] is not False
            or report['progression']['realCandidateEvaluationAllowed'] is not False):
        raise ValueError('Terminal report and decision record disagree')
    return record


def _verified_profile(root: Path, review: dict, design: dict) -> tuple[dict, float]:
    path = _local(root, review['profilePath'])
    if file_sha256(path) != review['profileSha256']:
        raise ValueError('Pinned development profile file hash mismatch')
    profile = _read(path)
    _check_hash(profile, 'reportHash')
    if profile['reportHash'] != review['profileReportHash']:
        raise ValueError('Pinned development report identity mismatch')
    identity = profile['identity']
    if (content_hash(identity) != review['profileIdentityHash']
            or profile['identityHash'] != review['profileIdentityHash']
            or identity['designHash'] != design['designHash']
            or identity['preregistrationHash'] != design['preregistrationHash']
            or identity['stream'] != 'development'):
        raise ValueError('Development profile belongs to another scientific identity')
    opening = _read(path.with_name('opening.json'))
    if opening != {'identity': identity, 'identityHash': profile['identityHash']}:
        raise ValueError('Development opening does not match the completed report')
    hashes = identity['implementationHashes']
    if set(hashes) != set(PROFILE_MODULES):
        raise ValueError('Incomplete profiled implementation inventory')
    for name, expected in hashes.items():
        if file_sha256(Path(__file__).with_name(name)) != expected:
            raise ValueError(f'Profiled implementation changed: {name}')
    if (profile['status'] != 'DEVELOPMENT_ONLY_NOT_A_POWER_AUDIT'
            or profile['lockedValidationReplications'] != 0
            or any(profile[key] is not False for key in (
                'realCandidateMetricsComputed', 'realConfirmationOpened', 'realEvaluationAuthorized'))):
        raise ValueError('Profile is not unopened synthetic-only evidence')
    equivalence = profile.get('equivalence', {})
    if (equivalence.get('status') != 'EXACT_MATCH'
            or equivalence.get('partitionReports') != 60 or equivalence.get('scoreArrays') != 360
            or equivalence.get('pathArrays') != 120
            or equivalence.get('scientificConfigChanged') is not False
            or equivalence.get('newReplicationIndicesUsed') is not False):
        raise ValueError('Optimization lacks complete frozen-result equivalence evidence')
    scenarios = profile['scenarios']
    if [s['scenarioId'] for s in scenarios] != [s['id'] for s in design['scenarios']]:
        raise ValueError('Incomplete or reordered development scenario inventory')
    replications = design['streams']['developmentReplicationsPerScenario']
    durations = []
    for result, scenario in zip(scenarios, design['scenarios'], strict=True):
        if (result['requirement'] != scenario['requirement'] or result['completedReplications'] != replications
                or [r['replication'] for r in result['runs']] != list(range(replications))):
            raise ValueError('Incomplete development replication inventory')
        for run in result['runs']:
            duration = run['procedureSeconds'] + run['extraConfirmationProfileSeconds']
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError('Invalid development timing evidence')
            if run['procedure']['realDataApproval'] is not False:
                raise ValueError('Synthetic procedure cannot authorize real data')
            durations.append(duration)
    required = len(scenarios) * design['budget']['requiredOuterReplicationsPerScenario']
    projected = max(durations) * required
    if (required != review['requiredValidationReplications']
            or profile['requiredValidationReplications'] != required
            or profile['validationWallBudgetSeconds'] != design['budget']['maximumValidationWallSeconds']
            or not math.isclose(projected, profile['conservativeProjectedValidationSeconds'], rel_tol=1e-12)):
        raise ValueError('Profile budget arithmetic disagrees with frozen design')
    return profile, projected


def finalize_stop(repo_root: Path) -> tuple[Path, dict]:
    repo_root = repo_root.resolve()
    review = _review(repo_root)
    existing = read_terminal_decision(repo_root)
    if existing is not None:
        if existing['reviewHash'] != review['reviewHash']:
            raise ValueError('Experiment already stopped; cannot replace its review authority')
        path = _local(repo_root, existing['reportPath'])
        return path, _read(path)
    design = load_design(_local(repo_root, review['designPath']), repo_root=repo_root)
    plan = load_cycle1_plan(_local(repo_root, design['preregistrationPath']))
    audit = load_cycle1_source_audit(_local(repo_root, review['sourceAuditPath']), plan=plan)
    if (design['designHash'] != review['designHash'] or plan.config_hash != review['preregistrationHash']
            or audit.audit_hash != review['sourceAuditHash']):
        raise ValueError('Power review authorities disagree')
    profile, projected = _verified_profile(repo_root, review, design)
    # Recompute prerequisite decisions rather than trusting profile status strings.
    scope_inadequate = design['acceptance']['scopeLimitationsBlockRealApproval'] is True
    over_budget = projected > design['budget']['maximumValidationWallSeconds']
    unavailable = sorted({reason for scenario in profile['scenarios'] for run in scenario['runs']
                          for reason in run['completeAvailableProcedure']['scopeLimitations']})
    reasons = []
    if scope_inadequate:
        reasons.append('FROZEN_SIMULATION_SCOPE_CANNOT_SUPPORT_REAL_APPROVAL')
    if unavailable:
        reasons.append('REQUIRED_EVIDENCE_PATHS_NOT_SPECIFIED')
    if over_budget:
        reasons.append('PROJECTED_VALIDATION_EXCEEDS_FROZEN_COMPUTE_BUDGET')
    if not reasons:
        raise ValueError('No stop prerequisite established; this command cannot grant power approval')
    report = {
        'schemaVersion': 'cycle1-power-stop-v1', 'experimentId': review['experimentId'],
        'decision': 'INSUFFICIENT_EVIDENCE', 'stage': 'STOPPED_BEFORE_LOCKED_VALIDATION',
        'reviewHash': review['reviewHash'], 'designHash': design['designHash'],
        'preregistrationHash': plan.config_hash, 'sourceAuditHash': audit.audit_hash,
        'implementationHashes': {name: file_sha256(Path(__file__).with_name(name)) for name in
                                 ('cycle1_power_gate.py', 'cycle1_config.py', 'cycle1_source_audit.py')},
        'evidence': {'profilePath': review['profilePath'], 'profileSha256': review['profileSha256'],
                     'profileReportHash': profile['reportHash'], 'profileIdentityHash': profile['identityHash'],
                     'developmentReplications': sum(s['completedReplications'] for s in profile['scenarios']),
                     'unavailableEvidencePaths': unavailable,
                     'optimizationEquivalence': profile['equivalence'],
                     'availableBranchComputeBudgetPassed': not over_budget,
                     'fullProcedureProfileAvailable': profile['profiledFullProcedure'],
                     'projectedValidationSeconds': projected,
                     'validationBudgetSeconds': design['budget']['maximumValidationWallSeconds'],
                     'simulationScope': design['scope']},
        'blockingReasons': reasons,
        'validation': {'status': 'NOT_RUN_PREREQUISITES_FAILED', 'completedReplications': 0,
                       'requiredReplications': review['requiredValidationReplications'],
                       'estimatedPower': None, 'estimatedFamilyWiseError': None,
                       'monteCarloBounds': None, 'statisticalDesignFailureEstablished': False},
        'progression': {'state': 'STOPPED', 'lockedValidationAllowed': False,
                        'realCandidateEvaluationAllowed': False, 'historicalConfirmationAllowed': False,
                        'datasetRebuildAllowed': False, 'sourceMigrationAllowed': False,
                        'deploymentAllowed': False},
        'redesign': {'maximum': 1, 'used': 0, 'remaining': 1, 'automatic': False,
                     'requirements': ['separate-versioned-design-and-rationale-linked-to-this-stop',
                                      'single-redesign-slot-before-any-successor-validation',
                                      'new-locked-streams-and-identity',
                                      'no-increased-effects-or-relaxed-usefulness-gates-to-force-a-pass'],
                     'currentDesignMayBeReopened': False},
        'interpretation': 'The frozen design lacks sufficient admissible audit evidence. '
                          'No statistical power or false-qualification estimate was established. '
                          'Available-branch optimization and timing do not establish full-procedure power. '
                          'The current design is closed; development results cannot substitute for locked validation.',
    }
    report['reportHash'] = content_hash(report)
    report_path = repo_root / 'reports' / ('cycle1-power-stop-' + report['reportHash'][:16]) / 'report.json'
    _publish_once(report_path, report)
    record = {'schemaVersion': 'cycle1-power-decision-v1', 'experimentId': review['experimentId'],
              'state': 'STOPPED', 'decision': report['decision'], 'reviewHash': review['reviewHash'],
              'designHash': design['designHash'], 'reportPath': str(report_path.relative_to(repo_root)),
              'reportHash': report['reportHash'], 'reportSha256': file_sha256(report_path),
              'historicalConfirmationAllowed': False, 'realCandidateEvaluationAllowed': False,
              'maximumRedesigns': 1, 'redesignsUsed': 0, 'automaticRedesign': False}
    record['recordHash'] = content_hash(record)
    _publish_once(repo_root / DECISION_PATH, record)
    read_terminal_decision(repo_root)
    return report_path, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path('.'))
    args = parser.parse_args()
    try:
        path, report = finalize_stop(args.repo_root)
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(json.dumps({'decision': 'INVALID_EVALUATION', 'message': str(error),
                          'historicalConfirmationAllowed': False}, indent=2))
        return 1
    print(json.dumps({'decision': report['decision'], 'stage': report['stage'],
                      'blockingReasons': report['blockingReasons'], 'reportPath': str(path),
                      'reportHash': report['reportHash'], 'lockedValidationReplications': 0,
                      'historicalConfirmationAllowed': False, 'redesignsUsed': 0,
                      'maximumRedesigns': 1}, indent=2))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
