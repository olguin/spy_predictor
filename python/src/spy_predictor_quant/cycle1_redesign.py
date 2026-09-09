"""Review the single-successor proposal without releasing any random stream.

The stopped design remains immutable. This module is deliberately separate from
its hash-pinned loader, profiler and runner. A valid proposal is not a frozen
design, a redesign registration, or permission to run an experiment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from spy_predictor_quant.cycle1_config import load_cycle1_plan
from spy_predictor_quant.cycle1_power_gate import (
    DECISION_PATH, _local, _publish_once, read_terminal_decision,
)
from spy_predictor_quant.cycle1_simulation_design import load_design
from spy_predictor_quant.cycle1_source_audit import load_cycle1_source_audit
from spy_predictor_quant.market_archive import content_hash, file_sha256

PROPOSAL_PATH = 'config/cycle1-simulation-v2-proposal.json'
SCHEMA_PATH = 'schemas/cycle1-simulation-v2-proposal.schema.json'


def load_proposal(repo_root: Path) -> dict[str, Any]:
    proposal = json.loads((repo_root / PROPOSAL_PATH).read_text())
    schema = json.loads((repo_root / SCHEMA_PATH).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(proposal))
    if errors:
        raise ValueError('Invalid successor proposal: ' + errors[0].message)
    core = {key: value for key, value in proposal.items() if key != 'proposalHash'}
    if content_hash(core) != proposal['proposalHash']:
        raise ValueError('Successor proposal hash mismatch')

    prior = proposal['predecessor']
    if prior['decisionPath'] != DECISION_PATH:
        raise ValueError('Successor must link the canonical stopped decision')
    decision = read_terminal_decision(repo_root)
    if decision is None:
        raise ValueError('Successor requires the verified terminal decision')
    for key in ('recordHash', 'designHash', 'reportPath', 'reportHash', 'reportSha256'):
        if decision[key] != prior[key]:
            raise ValueError('Successor predecessor identity mismatch: ' + key)
    previous = load_design(_local(repo_root, prior['designPath']), repo_root=repo_root)
    if previous['designHash'] != prior['designHash']:
        raise ValueError('Successor predecessor design mismatch')
    for key, value in proposal['preserved'].items():
        if value != previous[key]:
            raise ValueError('Successor changes frozen scientific constraints: ' + key)
    for key, value in proposal['acceptance'].items():
        if value != previous['acceptance'][key]:
            raise ValueError('Successor changes qualification gates: ' + key)

    plan = load_cycle1_plan(_local(repo_root, proposal['preregistrationPath']))
    if plan.config_hash != proposal['preregistrationHash']:
        raise ValueError('Successor preregistration identity mismatch')
    if plan.config_hash != previous['preregistrationHash']:
        raise ValueError('Successor proposal cannot switch the scientific contract')
    audit = load_cycle1_source_audit(_local(repo_root, proposal['sourceAuditPath']), plan=plan)
    if audit.audit_hash != proposal['sourceAuditHash']:
        raise ValueError('Successor source audit identity mismatch')
    if audit.raw['preregistrationHash'] != plan.config_hash:
        raise ValueError('Successor source audit links another preregistration')

    new_streams = proposal['streams']
    entropies = [new_streams[key] for key in ('developmentEntropy', 'validationEntropy')]
    old_entropies = {previous['streams'][key] for key in ('developmentEntropy', 'validationEntropy')}
    if len(set(entropies)) != 2 or old_entropies.intersection(entropies):
        raise ValueError('Successor streams must be distinct and new')
    for key in ('developmentReplicationsPerScenario', 'validationReplicationsPerScenario', 'bootstrapSeed'):
        if new_streams[key] != previous['streams'][key]:
            raise ValueError('Successor changes replication or bootstrap budget')
    if proposal['status'] != 'PROPOSED_NO_DRAWS' or any(proposal['permissions'].values()):
        raise ValueError('Proposal cannot authorize experiment execution')
    if proposal['redesign']['maximum'] != decision['maximumRedesigns']:
        raise ValueError('Successor cannot increase the redesign budget')
    registration = _local(repo_root, proposal['redesign']['registrationPath'])
    if registration.exists():
        raise ValueError('Successor already registered; this pre-registration review cannot replace it')
    return proposal


def review_proposal(repo_root: Path) -> dict[str, Any]:
    proposal = load_proposal(repo_root)
    identity = {
        'proposalHash': proposal['proposalHash'],
        'predecessorRecordHash': proposal['predecessor']['recordHash'],
        'preregistrationHash': proposal['preregistrationHash'],
        'sourceAuditHash': proposal['sourceAuditHash'],
        'schemaSha256': file_sha256(repo_root / SCHEMA_PATH),
        'implementationSha256': file_sha256(Path(__file__)),
    }
    result = {
        'schemaVersion': 'cycle1-redesign-proposal-review-v1',
        'status': 'VALID_PROPOSAL_NOT_FROZEN',
        'identity': identity,
        'identityHash': content_hash(identity),
        'preservedConstraints': list(proposal['preserved']) + list(proposal['acceptance']),
        'unresolvedBeforeFreeze': proposal['unresolvedBeforeFreeze'],
        'releaseGates': proposal['releaseGates'],
        'redesignAccounting': {
            'maximum': 1, 'registeredSuccessors': 0, 'remaining': 1,
            'proposalConsumesSlot': False, 'registrationCreated': False,
        },
        'permissions': proposal['permissions'],
        'evidence': {
            'samplesDrawnByReview': 0, 'candidateMetricsComputed': False,
            'powerEstimated': False, 'fullPathImplementationVerified': False,
            'predecessorState': 'STOPPED',
        },
        'nextAction': 'Resolve and freeze the causal path equations and annual-null validity, then register the one final successor before development draws.',
    }
    return {**result, 'reportHash': content_hash(result)}


def publish_review(repo_root: Path) -> tuple[Path, dict[str, Any]]:
    report = review_proposal(repo_root)
    path = repo_root / 'reports' / ('cycle1-redesign-proposal-' + report['reportHash'][:16]) / 'report.json'
    _publish_once(path, report)
    return path, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path('.'))
    args = parser.parse_args()
    try:
        path, report = publish_review(args.repo_root.resolve())
    except (ValueError, KeyError, OSError) as error:
        print(json.dumps({'status': 'INVALID_PROPOSAL', 'error': str(error)}))
        return 1
    print(json.dumps({'status': report['status'], 'reportPath': str(path),
                      'reportHash': report['reportHash'], 'permissions': report['permissions']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
