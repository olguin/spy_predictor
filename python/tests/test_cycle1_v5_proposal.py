"""Proposal validation must never grant data access or shrink the claim family."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from spy_predictor_quant.cycle1 import run
from spy_predictor_quant.cycle1_config import load_cycle1_plan, assert_candidate_evaluation_allowed
from spy_predictor_quant.cycle1_dataset import build_cycle1_dataset
from spy_predictor_quant.cycle1_source_audit import load_cycle1_source_audit

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'config/cycle1-v5-draft.json'
AUDIT = ROOT / 'config/cycle1-source-audit-v4-draft.json'
SCHEMA = ROOT / 'schemas/cycle1-config-v5-draft.schema.json'


def test_proposal_resolves_ledger_and_keeps_real_boundary_closed():
    plan = load_cycle1_plan(CONFIG)
    assert plan.hypothesis_count == 10
    assert len(plan.model_ids) == 7
    audit = load_cycle1_source_audit(AUDIT, plan=plan)
    assert 'GS3M' in audit.accepted_series
    assert 'BAA' in audit.excluded_series
    with pytest.raises(RuntimeError, match='real evaluation is blocked'):
        assert_candidate_evaluation_allowed(plan)


@pytest.mark.parametrize('path,value', [
    ('status', 'frozen-before-candidate-output'),
    ('execution.realCandidateEvaluationAllowed', True),
    ('execution.powerApproval', 'PASS'),
    ('execution.requiredDatasetIdentity', 'a' * 64),
    ('hypothesisBudget.totalLedgerEntries', 11),
    ('hypothesisBudget.compositePrimaryClaims', 1),
    ('partitions.fixedCalendar.confirmationEnd', '2026-07-31'),
    ('partitions.qqqSelectionMetricsAllowed', True),
    ('evaluationContract.comparisons.challengerBaselines', ['unconditional-history']),
])
def test_scientific_mutation_fails_closed(tmp_path, path, value):
    payload = json.loads(CONFIG.read_text())
    node = payload
    parts = path.split('.')
    for key in parts[:-1]:
        node = node[key]
    node[parts[-1]] = value
    mutated = tmp_path / 'proposal.json'
    mutated.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='Invalid Cycle 1'):
        load_cycle1_plan(mutated, schema_path=SCHEMA)


def test_missing_contract_is_rejected(tmp_path):
    payload = json.loads(CONFIG.read_text())
    del payload['evaluationContract']['coverage']
    path = tmp_path / 'proposal.json'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='required property'):
        load_cycle1_plan(path, schema_path=SCHEMA)


def test_contract_report_never_calls_builder(tmp_path):
    def forbidden(**kwargs):
        raise AssertionError('No real-data access allowed')
    result = run(config_path=CONFIG, source_audit_path=AUDIT, repo_root=tmp_path,
                 contract_only=True, dataset_builder=forbidden)
    assert result['ledgerEntries'] == 10
    assert result['compositePrimaryClaims'] == 2
    assert result['candidateMetricsComputed'] is False
    assert result['syntheticMetricsComputed'] is False
    assert result == run(config_path=CONFIG, source_audit_path=AUDIT, repo_root=tmp_path,
                         contract_only=True, dataset_builder=forbidden)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('dataset_only', [False, True])
def test_v5_runner_blocks_acquisition_even_with_dataset_only(tmp_path, dataset_only):
    with pytest.raises(RuntimeError, match='real evaluation is blocked'):
        run(config_path=CONFIG, source_audit_path=AUDIT, repo_root=tmp_path,
            dataset_only=dataset_only)
    assert list(tmp_path.iterdir()) == []


def test_direct_dataset_call_cannot_bypass_proposal_guard(tmp_path):
    plan = load_cycle1_plan(CONFIG)
    audit = load_cycle1_source_audit(AUDIT, plan=plan)
    with pytest.raises(RuntimeError, match='Dataset build blocked'):
        build_cycle1_dataset(plan=plan, audit=audit, repo_root=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_v4_source_audit_cannot_authorize_v5():
    with pytest.raises(ValueError, match='preregistration hash'):
        load_cycle1_source_audit(ROOT / 'config/cycle1-source-audit-v3.json',
                                plan=load_cycle1_plan(CONFIG))


def test_archive_validator_remains_unchanged():
    active = load_cycle1_plan(ROOT / 'config/cycle1.json')
    archived = load_cycle1_plan(ROOT / 'config/cycle1-v4.json')
    assert active.config_hash == archived.config_hash
    assert active.config_hash == '887ab9410f79e7fd2884af731c029d81ba2f0d57d4d3c3e22b9bb68671bfdbc8'
