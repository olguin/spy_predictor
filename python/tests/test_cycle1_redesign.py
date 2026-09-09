from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from spy_predictor_quant.cycle1_redesign import (
    PROPOSAL_PATH, SCHEMA_PATH, load_proposal, publish_review, review_proposal,
)
from spy_predictor_quant.market_archive import content_hash

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repo(tmp_path):
    for directory in ('config', 'schemas'):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    decision_path = Path('experiments/cycle1-power-v1/decision.json')
    decision = json.loads((ROOT / decision_path).read_text())
    for relative in (decision_path, Path(decision['reportPath'])):
        (tmp_path / relative.parent).mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, tmp_path / relative)
    return tmp_path


def change_proposal(repo, change, *, update_schema=False):
    path = repo / PROPOSAL_PATH
    proposal = json.loads(path.read_text())
    change(proposal)
    proposal['proposalHash'] = content_hash({k: v for k, v in proposal.items() if k != 'proposalHash'})
    path.write_text(json.dumps(proposal))
    if update_schema:
        schema_path = repo / SCHEMA_PATH
        schema = json.loads(schema_path.read_text())
        for key, value in proposal.items():
            if key != 'proposalHash':
                schema['properties'][key] = {'const': value}
        schema_path.write_text(json.dumps(schema))


def test_review_uses_no_samples_or_market_data_and_preserves_stop(repo, monkeypatch):
    from spy_predictor_quant import cycle1_synthetic

    def forbidden(*args, **kwargs):
        raise AssertionError('Proposal review must not generate samples')

    monkeypatch.setattr(cycle1_synthetic, 'generate_paths', forbidden)
    # The fixture has no datasets, raw archive, development profiles or seeds.
    prior = {p: p.read_bytes() for p in repo.rglob('*.json')}
    path, report = publish_review(repo)
    assert report['status'] == 'VALID_PROPOSAL_NOT_FROZEN'
    assert not any(report['permissions'].values())
    assert report['evidence']['samplesDrawnByReview'] == 0
    assert report['redesignAccounting']['remaining'] == 1
    assert not (repo / 'experiments/cycle1-power-redesign').exists()
    assert all(p.read_bytes() == data for p, data in prior.items())
    modified = path.stat().st_mtime_ns
    assert publish_review(repo) == (path, report)
    assert path.stat().st_mtime_ns == modified


@pytest.mark.parametrize('change', [
    lambda p: p['permissions'].update(lockedValidation=True),
    lambda p: p['redesign'].update(maximum=2),
    lambda p: p['preserved']['effects'].update(locationDesignAnnualAmplitude=0.16),
    lambda p: p['acceptance'].update(powerLowerMinimum=0.5),
    lambda p: p['preserved']['calendar'].update(confirmationEnd='2026-07'),
    lambda p: p['preserved']['budget'].update(requiredOuterReplicationsPerScenario=20),
    lambda p: p['preserved']['scenarios'][2].update(requirement='report-only'),
])
def test_scientific_edits_do_not_become_valid_by_rehashing(repo, change):
    change_proposal(repo, change)
    with pytest.raises(ValueError, match='Invalid successor proposal'):
        review_proposal(repo)


@pytest.mark.parametrize(('change', 'message'), [
    (lambda p: p['preserved']['effects'].update(locationDesignAnnualAmplitude=0.16), 'frozen scientific'),
    (lambda p: p['streams'].update(validationEntropy=2026090802), 'distinct and new'),
    (lambda p: p['streams'].update(validationEntropy=p['streams']['developmentEntropy']), 'distinct and new'),
    (lambda p: p['streams'].update(validationReplicationsPerScenario=20), 'replication or bootstrap'),
    (lambda p: p['permissions'].update(realCandidateEvaluation=True), 'authorize experiment'),
    (lambda p: p['predecessor'].update(recordHash='0' * 64), 'predecessor identity'),
    (lambda p: p['predecessor'].update(decisionPath='../decision.json'), 'canonical stopped'),
])
def test_semantic_constraints_survive_accidental_matching_schema_edits(repo, change, message):
    change_proposal(repo, change, update_schema=True)
    with pytest.raises(ValueError, match=message):
        load_proposal(repo)


def test_tampered_stop_report_prevents_successor_review(repo):
    proposal = json.loads((repo / PROPOSAL_PATH).read_text())
    (repo / proposal['predecessor']['reportPath']).write_text('{}')
    with pytest.raises(ValueError, match='report file hash mismatch'):
        publish_review(repo)
    assert not list((repo / 'reports').glob('cycle1-redesign-proposal-*'))


def test_missing_stop_cannot_create_a_successor(repo):
    (repo / 'experiments/cycle1-power-v1/decision.json').unlink()
    with pytest.raises(ValueError, match='verified terminal decision'):
        review_proposal(repo)


def test_existing_registration_cannot_be_replaced_or_reset(repo):
    path = repo / 'experiments/cycle1-power-redesign/registration.json'
    path.parent.mkdir(parents=True)
    path.write_text('{"reserved":true}')
    with pytest.raises(ValueError, match='already registered'):
        publish_review(repo)
    assert path.read_text() == '{"reserved":true}'


def test_proposal_hash_is_checked(repo):
    path = repo / PROPOSAL_PATH
    value = json.loads(path.read_text())
    value['proposalHash'] = '0' * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='proposal hash mismatch'):
        load_proposal(repo)
