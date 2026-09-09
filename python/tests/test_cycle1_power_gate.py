from __future__ import annotations

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from spy_predictor_quant.cycle1_power_gate import (
    DECISION_PATH, _publish_once, finalize_stop, read_terminal_decision,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repo(tmp_path):
    for name in ('config','schemas'):
        shutil.copytree(ROOT/name,tmp_path/name)
    review=json.loads((ROOT/'config/cycle1-power-review-v1.json').read_text())
    profile=Path(review['profilePath'])
    (tmp_path/profile.parent).mkdir(parents=True)
    for name in ('report.json','opening.json'):
        shutil.copy2(ROOT/profile.parent/name,tmp_path/profile.parent/name)
    return tmp_path


def test_terminal_stop_verifies_optimized_evidence_without_drawing_samples(repo,monkeypatch):
    import spy_predictor_quant.cycle1_synthetic as synthetic
    def prohibited(*args,**kwargs):raise AssertionError('No new samples allowed during terminal review')
    monkeypatch.setattr(synthetic,'generate_paths',prohibited)
    path,report=finalize_stop(repo)
    assert report['decision']=='INSUFFICIENT_EVIDENCE'
    assert report['validation']['completedReplications']==0
    assert report['validation']['estimatedPower'] is None
    assert report['validation']['statisticalDesignFailureEstablished'] is False
    assert report['evidence']['availableBranchComputeBudgetPassed'] is True
    assert report['evidence']['fullProcedureProfileAvailable'] is False
    assert report['evidence']['optimizationEquivalence']['partitionReports']==60
    assert report['redesign']['maximum']==1 and report['redesign']['used']==0
    assert report['progression']['historicalConfirmationAllowed'] is False
    record=read_terminal_decision(repo)
    assert record['reportPath']==str(path.relative_to(repo))
    before=(path.stat().st_mtime_ns,(repo/DECISION_PATH).stat().st_mtime_ns)
    assert finalize_stop(repo)==(path,report)
    assert before==(path.stat().st_mtime_ns,(repo/DECISION_PATH).stat().st_mtime_ns)


def test_atomic_publication_is_repeatable_and_cannot_replace(tmp_path):
    path=tmp_path/'decision.json'
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: _publish_once(path,{'state':'STOPPED'}),range(2)))
    with pytest.raises(ValueError,match='Refusing to replace'):
        _publish_once(path,{'state':'PASS'})
    assert json.loads(path.read_text())=={'state':'STOPPED'}
    assert not list(tmp_path.glob('.power-*'))


def test_tampered_profile_cannot_issue_a_decision(repo):
    review=json.loads((repo/'config/cycle1-power-review-v1.json').read_text())
    (repo/review['profilePath']).write_text('{}')
    with pytest.raises(ValueError,match='file hash mismatch'):
        finalize_stop(repo)
    assert not (repo/DECISION_PATH).exists()


def test_stale_implementation_cannot_use_old_profile(repo,monkeypatch):
    import spy_predictor_quant.cycle1_power_gate as gate
    original=gate.file_sha256
    def stale(path):return '0'*64 if path.name=='cycle1_models.py' else original(path)
    monkeypatch.setattr(gate,'file_sha256',stale)
    with pytest.raises(ValueError,match='implementation changed'):
        finalize_stop(repo)
    assert not (repo/DECISION_PATH).exists()


def test_corrupted_terminal_report_never_reopens(repo):
    path,_=finalize_stop(repo)
    path.write_text('{}')
    with pytest.raises(ValueError,match='report file hash mismatch'):
        read_terminal_decision(repo)
    with pytest.raises(ValueError):finalize_stop(repo)


def test_larger_redesign_budget_cannot_be_smuggled_into_review(repo):
    p=repo/'config/cycle1-power-review-v1.json';review=json.loads(p.read_text())
    review['maximumRedesigns']=2;p.write_text(json.dumps(review))
    with pytest.raises(ValueError,match='Invalid frozen power review'):
        finalize_stop(repo)
    assert not (repo/DECISION_PATH).exists()


def test_runner_observes_terminal_stop_and_contract_review_reports_it(repo):
    from spy_predictor_quant.cycle1 import run
    finalize_stop(repo)
    kwargs=dict(config_path=repo/'config/cycle1-v5-draft.json',
                source_audit_path=repo/'config/cycle1-source-audit-v4-draft.json',repo_root=repo)
    result=run(**kwargs,contract_only=True)
    assert result['status']=='STOPPED_INSUFFICIENT_EVIDENCE'
    assert result['terminalPowerDecision']['state']=='STOPPED'
    for dataset_only in (False,True):
        with pytest.raises(RuntimeError,match='power audit is stopped'):
            run(**kwargs,dataset_only=dataset_only)


def test_stop_prevents_new_profiles_without_new_draws(repo,monkeypatch):
    from spy_predictor_quant import cycle1_synthetic_profile as profiler
    finalize_stop(repo)
    def forbidden(*args,**kwargs):raise AssertionError('Stopped design may not draw samples')
    monkeypatch.setattr(profiler,'generate_paths',forbidden)
    with pytest.raises(RuntimeError,match='design is stopped'):
        profiler.profile(repo)
