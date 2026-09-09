"""Final repaired configuration, still barred from draws until registration.

The final authority binds the existing scientific contract and source audit by
hash without rewriting historical authorities. Stream recipes are data, not RNG
openers. Each primitive has an independent SeedSequence child; shared market
shocks arise only through the explicit equation mixing weights.
"""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from spy_predictor_quant.cycle1_redesign import load_proposal
from spy_predictor_quant.cycle1_successor_equations import EQUATION_SPEC, EQUATION_HASH
from spy_predictor_quant.cycle1_successor_laws import REPAIR_SPEC, REPAIR_HASH, validate_repair_scenario
from spy_predictor_quant.market_archive import content_hash

CONFIG_PATH = 'config/cycle1-simulation-v2.json'
SCHEMA_PATH = 'schemas/cycle1-simulation-v2.schema.json'

# Component draws within each vector are iid. Daily normals are never reused
# for the monthly Student innovation. Actions have deterministic calendar laws.
STREAM_LAWS = {
    'macro_normals': ['monthly', 'standard-normal', 4],
    'release_normals': ['monthly', 'standard-normal', 4],
    'revision_normals': ['monthly', 'standard-normal', 4],
    'release_uniforms': ['monthly', 'uniform-[0,1)', 4],
    'revision_uniforms': ['monthly', 'uniform-[0,1)', 4],
    'volatility_normal': ['monthly', 'standard-normal', 1],
    'spy_student': ['monthly', 'Student-t-scenario-df-unstandardized', 1],
    'qqq_student': ['monthly', 'Student-t-scenario-df-unstandardized', 1],
    'crash_uniform': ['monthly', 'uniform-[0,1)', 1],
    'crash_timing_uniform': ['monthly', 'uniform-[0,1)', 1],
    'missing_uniform': ['monthly', 'uniform-[0,1)', 1],
    'baseline_uniform': ['monthly', 'uniform-[0,1)', 1],
    'spy_overnight': ['session', 'standard-normal', 1],
    'spy_intraday': ['session', 'standard-normal', 1],
    'qqq_overnight': ['session', 'standard-normal', 1],
    'qqq_intraday': ['session', 'standard-normal', 1],
}


def configuration_core(proposal: dict) -> dict:
    return {
        'schemaVersion': 'cycle1-simulation-v2',
        'status': 'FINAL_CONFIGURATION_UNREGISTERED',
        'proposalHash': proposal['proposalHash'],
        'predecessor': proposal['predecessor'],
        'preregistrationPath': proposal['preregistrationPath'],
        'preregistrationHash': proposal['preregistrationHash'],
        'sourceAuditPath': proposal['sourceAuditPath'],
        'sourceAuditHash': proposal['sourceAuditHash'],
        **proposal['preserved'],
        'acceptance': proposal['acceptance'],
        'equations': {'base': EQUATION_SPEC, 'baseHash': EQUATION_HASH,
                      'amendment': REPAIR_SPEC, 'amendmentHash': REPAIR_HASH,
                      'executionHash': content_hash({'base': EQUATION_HASH, 'repair': REPAIR_HASH}),
                      'repaired': True},
        'streams': {
            **{key: proposal['streams'][key] for key in (
                'bitGenerator', 'developmentEntropy', 'validationEntropy',
                'developmentReplicationsPerScenario', 'validationReplicationsPerScenario', 'bootstrapSeed')},
            'status': 'UNOPENED_REGISTRATION_REQUIRED',
            'seedSequenceRule': 'SeedSequence([entropy,scenarioOrdinal,replicationIndex,substreamOrdinal])',
            'substreams': [{'ordinal': i, 'field': field, 'cadence': law[0], 'law': law[1], 'width': law[2]}
                           for i, (field, law) in enumerate(STREAM_LAWS.items())],
            'corporateActions': 'deterministic-equation-calendar-no-random-draws',
        },
        'pathContract': proposal['pathContract'],
        'redesign': proposal['redesign'],
        'permissions': proposal['permissions'],
        'remainingReleaseGates': [
            'deterministic-complete-procedure-branch-coverage',
            'atomic-registration-binding-final-code-config-schema-calendar-and-fixtures',
            'registered-development-profile-within-preserved-budget',
            'atomic-locked-opening-and-complete-20000-replication-audit',
        ],
    }


def load_successor_config(repo_root: Path, *, registered: bool | None = None) -> dict:
    raw = json.loads((repo_root / CONFIG_PATH).read_text())
    schema = json.loads((repo_root / SCHEMA_PATH).read_text())
    Draft202012Validator(schema).validate(raw)
    core = {key: value for key, value in raw.items() if key != 'designHash'}
    if content_hash(core) != raw['designHash']:
        raise ValueError('Repaired successor design hash mismatch')
    # Verifies the stopped predecessor, exact preserved constraints, current
    # preregistration/source-audit chain and distinct unopened entropies.
    if registered is None:
        registered = (repo_root / 'experiments/cycle1-power-redesign/registration.json').exists()
    expected = configuration_core(_registered_proposal(repo_root) if registered else load_proposal(repo_root))
    if core != expected:
        raise ValueError('Repaired successor differs from linked final laws or preserved gates')
    for scenario in raw['scenarios']:
        validate_repair_scenario(scenario)
    return raw


def _registered_proposal(root: Path) -> dict:
    """Verify historical links after registration without reopening its review."""
    from spy_predictor_quant.cycle1_redesign import PROPOSAL_PATH, SCHEMA_PATH
    from spy_predictor_quant.cycle1_power_gate import read_terminal_decision, _local, DECISION_PATH
    from spy_predictor_quant.cycle1_simulation_design import load_design
    from spy_predictor_quant.cycle1_config import load_cycle1_plan
    from spy_predictor_quant.cycle1_source_audit import load_cycle1_source_audit
    proposal = json.loads((root / PROPOSAL_PATH).read_text())
    Draft202012Validator(json.loads((root / SCHEMA_PATH).read_text())).validate(proposal)
    if content_hash({k: v for k, v in proposal.items() if k != 'proposalHash'}) != proposal['proposalHash']:
        raise ValueError('Historical proposal hash mismatch')
    prior = proposal['predecessor']
    decision = read_terminal_decision(root)
    if prior['decisionPath'] != DECISION_PATH or decision is None:
        raise ValueError('Missing canonical predecessor stop')
    if any(prior[k] != decision[k] for k in ('recordHash', 'designHash', 'reportPath', 'reportHash', 'reportSha256')):
        raise ValueError('Predecessor identity mismatch')
    previous = load_design(_local(root, prior['designPath']), repo_root=root)
    if previous['designHash'] != prior['designHash']:
        raise ValueError('Predecessor design mismatch')
    if any(previous[k] != v for k, v in proposal['preserved'].items()):
        raise ValueError('Preserved scientific constraints changed')
    if any(previous['acceptance'][k] != v for k, v in proposal['acceptance'].items()):
        raise ValueError('Acceptance gates changed')
    plan = load_cycle1_plan(_local(root, proposal['preregistrationPath']))
    audit = load_cycle1_source_audit(_local(root, proposal['sourceAuditPath']), plan=plan)
    if (plan.config_hash != proposal['preregistrationHash'] or plan.config_hash != previous['preregistrationHash']
            or audit.audit_hash != proposal['sourceAuditHash'] or audit.raw['preregistrationHash'] != plan.config_hash):
        raise ValueError('Linked scientific authorities changed')
    streams = proposal['streams']
    entropies = {streams['developmentEntropy'], streams['validationEntropy']}
    if len(entropies) != 2 or entropies.intersection(previous['streams'][k] for k in ('developmentEntropy', 'validationEntropy')):
        raise ValueError('Independent successor entropies required')
    if any(streams[k] != previous['streams'][k] for k in ('developmentReplicationsPerScenario', 'validationReplicationsPerScenario', 'bootstrapSeed')):
        raise ValueError('Replication budget changed')
    return proposal
