"""Single-successor registration, independently sampled development and budget gate.

No validation sampler is released here. An unsuccessful complete-path profile
closes this successor with insufficient evidence, never a statistical rejection.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import importlib.metadata
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import tempfile
import time

import numpy as np

from spy_predictor_quant.cycle1_calendar import _xnys
from spy_predictor_quant.cycle1_successor_calendar import month_end
from spy_predictor_quant.cycle1_successor_config import load_successor_config, CONFIG_PATH, SCHEMA_PATH
from spy_predictor_quant.cycle1_successor_equations import MonthInnovations, SessionInnovations
from spy_predictor_quant.cycle1_successor_pipeline import run_pipeline
from spy_predictor_quant.cycle1_power_gate import _local, _publish_once
from spy_predictor_quant.market_archive import content_hash, file_sha256

REGISTRATION = 'experiments/cycle1-power-redesign/registration.json'
RUN_ROOT = 'experiments/cycle1-power-v2'
PROFILE_SPEC = {
    'version': 'successor-development-profile-v1',
    'order': 'scenario-ordinal-then-replication;maximum-three-per-scenario',
    'procedure': 'generate-full-path-and-exercise-all-conditional-branches',
    'projection': 'maximum-completed-replication-wall-seconds-times-20000',
    'earlyStop': 'first-projection-over-3600-seconds-or-profile-deadline',
    'success': 'all-thirty-development-replications-and-projection-within-budget',
    'timeout': 'terminate-worker;no-redraw;INSUFFICIENT_EVIDENCE_COMPUTATIONAL_BUDGET',
    'failure': 'numerical-or-procedure-error-INVALID_EVALUATION;no-redraw',
    'lockedValidationReleased': False,
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path, key: str) -> dict:
    raw = json.loads(path.read_text())
    if content_hash({k: v for k, v in raw.items() if k != key}) != raw[key]:
        raise ValueError('Immutable artifact hash mismatch: ' + str(path))
    return raw


def _claim(path: Path, record: dict) -> None:
    """An exclusive durable claim; existing claims can never start a second run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.claim-', delete=False) as handle:
        temporary = Path(handle.name)
        try:
            json.dump(record, handle, sort_keys=True, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink()
            raise
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink()
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def code_inventory(root: Path) -> dict:
    # Covers the whole Cycle 1 dependency surface and shared archive helpers.
    directory = root / 'python/src/spy_predictor_quant'
    files = set(directory.glob('cycle1*.py')) | {directory / 'market_archive.py'}
    return {str(p.relative_to(root)): file_sha256(p) for p in sorted(files)}


def calendar_inventory(design: dict) -> dict:
    first, last = (date.fromisoformat(design['calendar'][k] + '-01') for k in ('warmupStart', 'pathEnd'))
    start, end = month_end(first.year, first.month), month_end(last.year, last.month)
    cal = _xnys()
    sessions = cal.sessions_in_range(start.isoformat(), end.isoformat())
    rows = [[x.date().isoformat(), cal.session_open(x).isoformat(), cal.session_close(x).isoformat()] for x in sessions]
    return {'start': start.isoformat(), 'end': end.isoformat(), 'sessions': len(rows), 'hash': content_hash(rows)}


def register(root: Path, fixture_path: Path) -> dict:
    design = load_successor_config(root, registered=False)
    if design['redesign']['registrationPath'] != REGISTRATION:
        raise ValueError('Noncanonical successor registration path')
    fixture_path = _local(root, str(fixture_path))
    fixture = _read(fixture_path, 'reportHash')
    if (fixture['status'] != 'FULL_PIPELINE_FIXTURE_NOT_REGISTERED' or fixture['randomDraws'] != 0
            or fixture['designHash'] != design['designHash'] or fixture['realDataApproval'] is not False):
        raise ValueError('Registration requires current complete deterministic fixture evidence')
    inventory = code_inventory(root)
    for name, digest in fixture['implementationHashes'].items():
        if inventory.get('python/src/spy_predictor_quant/' + name) != digest:
            raise ValueError('Fixture implementation changed: ' + name)
    if set(fixture['implementationHashes']) != {Path(p).name for p in inventory if Path(p).name.startswith('cycle1')}:
        raise ValueError('Fixture code inventory is incomplete')
    procedure = fixture['procedure']
    policies = procedure['policyBranchExerciseOnly']
    if (len(policies) != 4 or any(len(p.get('costCases', [])) != 2 for p in policies)
            or any(e['pairedMonths'] != 97 for e in procedure['transferBranchExerciseOnly']['entries'])):
        raise ValueError('Incomplete deterministic policy/transfer exercises')
    record = {
        'schemaVersion': 'cycle1-successor-registration-v1', 'registeredAt': _now(),
        'designHash': design['designHash'], 'predecessorRecordHash': design['predecessor']['recordHash'],
        'redesignsUsed': 1, 'maximumRedesigns': 1, 'implementationHashes': inventory,
        'authorityHashes': {p: file_sha256(root / p) for p in (
            CONFIG_PATH, SCHEMA_PATH, design['preregistrationPath'], design['sourceAuditPath'],
            'config/cycle1-simulation-v2-proposal.json', 'python/uv.lock', 'python/pyproject.toml')},
        'environment': {'python': platform.python_version(),
                        **{p: importlib.metadata.version(p) for p in ('numpy', 'exchange-calendars', 'scikit-learn', 'jsonschema')}},
        'calendar': calendar_inventory(design), 'profileSpec': PROFILE_SPEC,
        'fixturePath': str(fixture_path.relative_to(root)), 'fixtureSha256': file_sha256(fixture_path),
        'fixtureHash': fixture['reportHash'], 'realDataApproval': False,
        'lockedValidationReleased': False,
    }
    record['registrationHash'] = content_hash(record)
    _claim(root / REGISTRATION, record)
    return record


def verify_registration(root: Path) -> tuple[dict, dict]:
    record = _read(root / REGISTRATION, 'registrationHash')
    design = load_successor_config(root, registered=True)
    if (record['designHash'] != design['designHash'] or record['redesignsUsed'] != 1
            or record['profileSpec'] != PROFILE_SPEC or record['implementationHashes'] != code_inventory(root)):
        raise ValueError('Registered implementation or design changed')
    for path, digest in record['authorityHashes'].items():
        if file_sha256(_local(root, path)) != digest:
            raise ValueError('Registered authority changed: ' + path)
    if calendar_inventory(design) != record['calendar']:
        raise ValueError('Registered session calendar changed')
    if file_sha256(_local(root, record['fixturePath'])) != record['fixtureSha256']:
        raise ValueError('Registered fixture changed')
    current = {'python': platform.python_version(),
               **{p: importlib.metadata.version(p) for p in ('numpy', 'exchange-calendars', 'scikit-learn', 'jsonschema')}}
    if current != record['environment']:
        raise ValueError('Registered runtime environment changed')
    return record, design


def _innovations(design: dict, scenario: int, replication: int, *, factory=None):
    """Internal primitive sampler; caller must own the durable development claim."""
    if type(scenario) is not int or not 0 <= scenario < len(design['scenarios']):
        raise ValueError('Invalid scenario ordinal')
    if type(replication) is not int or not 0 <= replication < design['streams']['developmentReplicationsPerScenario']:
        raise ValueError('Development replication budget exceeded')
    factory = factory or (lambda seed: np.random.Generator(np.random.PCG64(np.random.SeedSequence(seed))))
    calendar = calendar_inventory(design)
    start, end = date.fromisoformat(calendar['start']), date.fromisoformat(calendar['end'])
    months = tuple(date(i // 12, i % 12 + 1, 1) for i in range(
        start.year * 12 + start.month - 3, end.year * 12 + end.month))
    sessions = tuple(x.date() for x in _xnys().sessions_in_range(start.isoformat(), end.isoformat())[1:])
    groups = {'monthly': {}, 'session': {}}
    for spec in design['streams']['substreams']:
        rng = factory([design['streams']['developmentEntropy'], scenario, replication, spec['ordinal']])
        n = len(months) if spec['cadence'] == 'monthly' else len(sessions)
        shape = (n, spec['width']) if spec['width'] > 1 else n
        if spec['law'] == 'standard-normal':
            values = rng.normal(size=shape)
        elif spec['law'] == 'uniform-[0,1)':
            values = rng.random(size=shape)
        elif spec['law'] == 'Student-t-scenario-df-unstandardized':
            values = rng.standard_t(design['scenarios'][scenario]['studentDegreesOfFreedom'], size=shape)
        else:
            raise ValueError('Unknown primitive innovation law')
        groups[spec['cadence']][spec['field']] = values
    def kwargs(group, i):
        return {k: tuple(v[i]) if np.ndim(v[i]) else float(v[i]) for k, v in groups[group].items()}
    return start, end, tuple(MonthInnovations(m, **kwargs('monthly', i)) for i, m in enumerate(months)), tuple(
        SessionInnovations(d, **kwargs('session', i)) for i, d in enumerate(sessions))


def _worker(root_string: str, scenario: int, replication: int, output: str):
    root = Path(root_string)
    try:
        record, design = verify_registration(root)
        if (root / RUN_ROOT / 'decision.json').exists():
            raise ValueError('Successor is terminal; draws remain closed')
        opening = _read(root / RUN_ROOT / 'profile-opening.json', 'openingHash')
        if opening['registrationHash'] != record['registrationHash']:
            raise ValueError('Profile opening belongs to another registration')
        _claim(root / RUN_ROOT / 'draws' / f'{scenario}-{replication}.json', {
            'registrationHash': record['registrationHash'], 'stream': 'development',
            'scenario': scenario, 'replication': replication, 'claimedAt': _now()})
        start, end, monthly, daily = _innovations(design, scenario, replication)
        config = json.loads((root / design['preregistrationPath']).read_text())
        procedure = run_pipeline(start=start, end=end, monthly=monthly, daily=daily,
                                  scenario=design['scenarios'][scenario], config=config, exercise_branches=True)
        result = {'status': 'COMPLETED', 'procedure': procedure}
    except Exception as error:
        result = {'status': 'INVALID_EVALUATION', 'error': type(error).__name__ + ': ' + str(error)}
    _publish_once(Path(output), result)


def profile(root: Path) -> dict:
    record, design = verify_registration(root)
    terminal = root / RUN_ROOT / 'decision.json'
    if terminal.exists():
        return _read(terminal, 'decisionHash')
    opening = {'registrationHash': record['registrationHash'], 'openedAt': _now(), 'profileSpec': PROFILE_SPEC}
    opening['openingHash'] = content_hash(opening)
    _claim(root / RUN_ROOT / 'profile-opening.json', opening)
    began = time.monotonic()
    runs, reason = [], None
    required = len(design['scenarios']) * design['budget']['requiredOuterReplicationsPerScenario']
    for scenario in range(len(design['scenarios'])):
        for replication in range(design['streams']['developmentReplicationsPerScenario']):
            remaining = design['budget']['maximumProfileWallSeconds'] - (time.monotonic() - began)
            if remaining <= 0:
                reason = 'INSUFFICIENT_EVIDENCE_COMPUTATIONAL_BUDGET'
                break
            output = root / RUN_ROOT / 'development' / f'{scenario}-{replication}.json'
            child = mp.get_context('spawn').Process(target=_worker, args=(str(root), scenario, replication, str(output)))
            start = time.monotonic()
            child.start()
            child.join(remaining)
            if child.is_alive():
                child.terminate()
                child.join(5)
                if child.is_alive():
                    child.kill()
                    child.join()
                reason = 'INSUFFICIENT_EVIDENCE_COMPUTATIONAL_BUDGET'
                runs.append({'scenario': scenario, 'replication': replication, 'status': 'TIMED_OUT', 'seconds': time.monotonic()-start})
                break
            duration = time.monotonic() - start
            result = json.loads(output.read_text()) if output.exists() else {'status': 'INVALID_EVALUATION', 'error': 'worker exited without durable result'}
            runs.append({'scenario': scenario, 'replication': replication, 'seconds': duration,
                         'status': result['status'], 'resultPath': str(output.relative_to(root)),
                         'resultSha256': file_sha256(output) if output.exists() else None})
            if result['status'] != 'COMPLETED':
                reason = 'INVALID_EVALUATION'
                break
            if max(r['seconds'] for r in runs) * required > design['budget']['maximumValidationWallSeconds']:
                reason = 'INSUFFICIENT_EVIDENCE_COMPUTATIONAL_BUDGET'
                break
        if reason:
            break
    result = {
        'schemaVersion': 'cycle1-successor-profile-decision-v1', 'registrationHash': record['registrationHash'],
        'decision': 'INVALID_EVALUATION' if reason == 'INVALID_EVALUATION' else 'INSUFFICIENT_EVIDENCE' if reason else 'PROFILE_PASSED',
        'reason': reason, 'runs': runs, 'profileWallSeconds': time.monotonic() - began,
        'projectedValidationSeconds': max((r['seconds'] for r in runs), default=0) * required,
        'requiredValidationReplications': required, 'completedValidationReplications': 0,
        'lockedValidationReleased': False, 'realDataApproval': False, 'redesignsRemaining': 0,
        'statisticalPowerFailureEstablished': False,
    }
    result['decisionHash'] = content_hash(result)
    destination = terminal if reason else root / RUN_ROOT / 'profile.json'
    _publish_once(destination, result)
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('register', 'profile', 'status'))
    parser.add_argument('--repo-root', type=Path, default=Path('.'))
    parser.add_argument('--fixture', type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    if args.action == 'register':
        if args.fixture is None:
            parser.error('register requires --fixture')
        result = register(root, args.fixture)
    elif args.action == 'profile':
        result = profile(root)
    else:
        record, _ = verify_registration(root)
        terminal = root / RUN_ROOT / 'decision.json'
        result = _read(terminal, 'decisionHash') if terminal.exists() else record
    print(json.dumps(result, indent=2, allow_nan=False))
    return 2 if result.get('decision') == 'INSUFFICIENT_EVIDENCE' else 1 if result.get('decision') == 'INVALID_EVALUATION' else 0


if __name__ == '__main__':
    raise SystemExit(main())
