import json
from pathlib import Path
import shutil
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from spy_predictor_quant import cycle1_successor_runtime as runtime
from spy_predictor_quant.cycle1_successor_config import load_successor_config

ROOT = Path(__file__).resolve().parents[2]


def test_claim_is_complete_and_only_one_concurrent_caller_wins(tmp_path):
    path = tmp_path / 'claim.json'
    def attempt(i):
        try:
            runtime._claim(path, {'caller': i, 'payload': list(range(100))})
            return i
        except FileExistsError:
            return None
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(attempt, range(4)))
    winners = [x for x in results if x is not None]
    assert len(winners) == 1
    assert json.loads(path.read_text())['caller'] == winners[0]
    assert len(json.loads(path.read_text())['payload']) == 100
    assert not list(tmp_path.glob('.claim-*'))


def test_sampler_uses_independent_coordinates_without_opening_any_rng():
    design = load_successor_config(ROOT)
    calls = []
    class Fake:
        def __init__(self, seed):
            self.seed = seed
        def normal(self, size):
            calls.append((self.seed, 'normal', size))
            return np.zeros(size)
        def random(self, size):
            calls.append((self.seed, 'uniform', size))
            return np.full(size, .5)
        def standard_t(self, df, size):
            calls.append((self.seed, 'student', size))
            assert df == 8
            return np.zeros(size)
    start, end, monthly, daily = runtime._innovations(design, 0, 2, factory=Fake)
    assert len(calls) == 16
    assert len({tuple(row[0]) for row in calls}) == 16
    assert all(seed[:3] == [design['streams']['developmentEntropy'], 0, 2] for seed, _, _ in calls)
    assert sum(law == 'student' for _, law, _ in calls) == 2
    assert start.isoformat() == '1990-01-31'
    assert end.isoformat() == '2026-07-31'
    assert len(daily) == 9190
    assert monthly[0].month.isoformat() == '1989-11-01'
    assert monthly[-1].month.isoformat() == '2026-07-01'
    assert monthly[0].baseline_uniform == .5
    with pytest.raises(ValueError, match='budget'):
        runtime._innovations(design, 0, 3, factory=Fake)
    with pytest.raises(ValueError, match='ordinal'):
        runtime._innovations(design, -1, 0, factory=Fake)


def test_profile_cannot_open_without_registration(tmp_path):
    with pytest.raises(FileNotFoundError):
        runtime.profile(tmp_path)
    assert not (tmp_path / runtime.RUN_ROOT).exists()


@pytest.fixture
def repo(tmp_path):
    for directory in ('config', 'schemas', 'python/src'):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    for relative in ('python/uv.lock', 'python/pyproject.toml', 'experiments/cycle1-power-v1/decision.json'):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    decision = json.loads((ROOT / 'experiments/cycle1-power-v1/decision.json').read_text())
    target = tmp_path / decision['reportPath']
    target.parent.mkdir(parents=True)
    shutil.copy2(ROOT / decision['reportPath'], target)
    # A registration mechanics fixture is explicit, not scientific evidence.
    from spy_predictor_quant.market_archive import content_hash
    design = load_successor_config(tmp_path)
    fixture = {'status': 'FULL_PIPELINE_FIXTURE_NOT_REGISTERED', 'randomDraws': 0,
               'designHash': design['designHash'], 'realDataApproval': False,
               'implementationHashes': {Path(k).name: v for k, v in runtime.code_inventory(tmp_path).items() if Path(k).name.startswith('cycle1')},
               'procedure': {'policyBranchExerciseOnly': [{'costCases': [1, 2]}] * 4,
                             'transferBranchExerciseOnly': {'entries': [{'pairedMonths': 97}] * 2}}}
    fixture['reportHash'] = content_hash(fixture)
    (tmp_path / 'fixture.json').write_text(json.dumps(fixture))
    return tmp_path


def test_registration_survives_review_closure_and_rejects_code_mutation(repo):
    record = runtime.register(repo, Path('fixture.json'))
    assert record['redesignsUsed'] == 1
    assert runtime.verify_registration(repo)[0] == record
    with pytest.raises(ValueError, match='already registered'):
        runtime.register(repo, Path('fixture.json'))
    changed = repo / 'python/src/spy_predictor_quant/cycle1_successor_pipeline.py'
    changed.write_text(changed.read_text() + '\n# changed\n')
    with pytest.raises(ValueError, match='implementation'):
        runtime.verify_registration(repo)


def test_registered_design_keeps_historical_authorities_and_rejects_schema_mutation(repo):
    runtime.register(repo, Path('fixture.json'))
    assert load_successor_config(repo)['acceptance']['powerLowerMinimum'] == .8
    schema = repo / 'schemas/cycle1-simulation-v2.schema.json'
    schema.write_text('{}')
    with pytest.raises(ValueError, match='authority'):
        runtime.verify_registration(repo)


def test_failed_budget_projection_closes_without_a_second_draw(repo, monkeypatch):
    runtime.register(repo, Path('fixture.json'))
    instances = []
    class Process:
        def __init__(self, target, args):
            self.args = args
            instances.append(self)
        def start(self):
            Path(self.args[-1]).parent.mkdir(parents=True, exist_ok=True)
            Path(self.args[-1]).write_text(json.dumps({'status': 'COMPLETED', 'procedure': {'fixtureOnly': True}}))
        def join(self, timeout=None):
            pass
        def is_alive(self):
            return False
    class Context:
        pass
    context = Context()
    context.Process = Process
    monkeypatch.setattr(runtime.mp, 'get_context', lambda method: context)
    times = iter([0., 0., 0., 2., 2.])
    monkeypatch.setattr(runtime.time, 'monotonic', lambda: next(times))
    report = runtime.profile(repo)
    assert report['decision'] == 'INSUFFICIENT_EVIDENCE'
    assert report['projectedValidationSeconds'] == 40000
    assert report['completedValidationReplications'] == 0
    assert not report['statisticalPowerFailureEstablished']
    assert len(instances) == 1
    assert runtime.profile(repo) == report
    assert len(instances) == 1
