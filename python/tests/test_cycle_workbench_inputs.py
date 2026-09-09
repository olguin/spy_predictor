from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from spy_predictor_quant.cycle_workbench import assess
from spy_predictor_quant.cycle_workbench_inputs import load_workbench_inputs

EXAMPLE = Path(__file__).resolve().parents[2] / 'examples/cycle-workbench'
CUTOFF = '2026-08-31T23:59:59+00:00'


@pytest.fixture
def local_inputs(tmp_path):
    root = tmp_path / 'workbench-inputs'
    root.mkdir()
    manifest = json.loads((EXAMPLE / 'synthetic-manifest.json').read_text())
    snapshot = json.loads((EXAMPLE / 'synthetic-observations.json').read_text())
    return root, manifest, snapshot


def write_inputs(inputs):
    root, manifest, snapshot = inputs
    raw = (json.dumps(snapshot, indent=2) + '\n').encode()
    (root / 'synthetic-observations.json').write_bytes(raw)
    manifest['snapshot']['sha256'] = hashlib.sha256(raw).hexdigest()
    path = root / 'synthetic-manifest.json'
    path.write_text(json.dumps(manifest))
    return path


def load(inputs, as_of=CUTOFF):
    return load_workbench_inputs(write_inputs(inputs), allowed_root=inputs[0], as_of=as_of)


def test_raw_metric_transform_and_adverse_timing(local_inputs):
    result = load(local_inputs)
    assert result.metadata['validated'] is True
    assert result.metadata['symbol'] == 'DEMO'
    timing = next(x for x in result.observations if x.component == 'timing')
    assert timing.score == pytest.approx(-.8)
    assert timing.raw_value == .88
    assert timing.raw_unit == 'ratio'
    assert timing.provenance_hash
    report = assess(result.observations, as_of=CUTOFF, input_metadata=result.metadata)
    assert report['instrument']['action'] == 'WAIT_FOR_CONFIRMATION'
    assert report['market']['posture'] == 'SUPPORTIVE'


def test_future_records_and_revisions_do_not_change_selected_identity(local_inputs):
    before = load(local_inputs)
    future = deepcopy(local_inputs[2]['observations'][-1])
    future.update(value=1.2, revision='future-correction', published_at='2026-09-02T12:00:00+00:00', first_seen_at='2026-09-02T12:00:00+00:00', retrieved_at='2026-09-02T12:00:00+00:00')
    local_inputs[2]['observations'].append(future)
    after = load(local_inputs)
    assert before.observations == after.observations
    assert before.metadata == after.metadata
    assert before.audit['snapshot_sha256'] != after.audit['snapshot_sha256']
    opened = load(local_inputs, '2026-09-03T00:00:00+00:00')
    assert next(x for x in opened.observations if x.component == 'timing').score == 1


def test_later_withdrawal_does_not_resurrect_old_value(local_inputs):
    withdrawn = deepcopy(local_inputs[2]['observations'][-1])
    withdrawn.update(value=None, status='WITHDRAWN', revision='withdrawn', published_at='2026-08-10T12:00:00+00:00', first_seen_at='2026-08-10T12:00:00+00:00', retrieved_at='2026-08-10T12:00:00+00:00')
    local_inputs[2]['observations'].append(withdrawn)
    result = load(local_inputs)
    timing = next(x for x in result.observations if x.component == 'timing')
    assert timing.score is None
    assert result.metadata['selected_provenance']['timing']['status'] == 'MISSING'
    report = assess(result.observations, as_of=CUTOFF, input_metadata=result.metadata)
    assert report['instrument']['action'] == 'INSUFFICIENT_EVIDENCE'


def test_missing_fundamentals_and_stale_inputs_abstain(local_inputs):
    local_inputs[2]['observations'] = [x for x in local_inputs[2]['observations'] if x['metric'] != 'trailing_pe']
    result = load(local_inputs)
    assert result.metadata['selected_provenance']['valuation']['status'] == 'MISSING'
    assert assess(result.observations, as_of=CUTOFF)['instrument']['action'] == 'INSUFFICIENT_EVIDENCE'
    stale = load(local_inputs, '2026-12-31T00:00:00+00:00')
    assert stale.metadata['selected_provenance']['growth']['status'] == 'STALE'


@pytest.mark.parametrize('mutation,match', [
    (lambda row: row.update(score=.8), 'schema violation'),
    (lambda row: row.update(unit='ratio'), 'Unit mismatch'),
    (lambda row: row.update(instrument_id='OTHER'), 'identity mismatch'),
    (lambda row: row.update(observed_at='2026-08-01'), 'schema violation'),
    (lambda row: row.update(evidence='OBSERVED_AS_OF'), 'Mixed evidence'),
    (lambda row: row.update(value=float('nan')), 'Non-finite'),
    (lambda row: row.update(value=float('inf')), 'Non-finite'),
    (lambda row: row.update(first_seen_at='2026-08-02T00:00:00+00:00'), 'Expected observed'),
    (lambda row: row.update(status='WITHDRAWN'), 'WITHDRAWN requires'),
])
def test_invalid_raw_inputs_rejected(local_inputs, mutation, match):
    mutation(local_inputs[2]['observations'][0])
    with pytest.raises(ValueError, match=match):
        load(local_inputs)


def test_duplicates_tampering_and_json_duplicate_keys_rejected(local_inputs):
    local_inputs[2]['observations'].append(deepcopy(local_inputs[2]['observations'][0]))
    with pytest.raises(ValueError, match='Duplicate or ambiguous'):
        load(local_inputs)
    local_inputs[2]['observations'].pop()
    path = write_inputs(local_inputs)
    (local_inputs[0] / 'synthetic-observations.json').write_text('{}')
    with pytest.raises(ValueError, match='SHA256 mismatch'):
        load_workbench_inputs(path, allowed_root=local_inputs[0], as_of=CUTOFF)
    path.write_text('{"schema_version":"a","schema_version":"b"}')
    with pytest.raises(ValueError, match='Duplicate JSON key'):
        load_workbench_inputs(path, allowed_root=local_inputs[0], as_of=CUTOFF)


def test_path_escape_symlink_and_cycle1_directory_rejected(local_inputs, tmp_path):
    path = write_inputs(local_inputs)
    outside = tmp_path / 'outside.json'
    outside.write_text('{}')
    link = local_inputs[0] / 'linked.json'
    link.symlink_to(outside)
    local_inputs[1]['snapshot']['path'] = 'linked.json'
    path.write_text(json.dumps(local_inputs[1]))
    with pytest.raises(ValueError, match='escapes allowed_root'):
        load_workbench_inputs(path, allowed_root=local_inputs[0], as_of=CUTOFF)
    local_inputs[1]['snapshot']['path'] = '../outside.json'
    path.write_text(json.dumps(local_inputs[1]))
    with pytest.raises(ValueError, match='confined and relative'):
        load_workbench_inputs(path, allowed_root=local_inputs[0], as_of=CUTOFF)
    cycle1 = local_inputs[0] / 'cycle1-private'
    cycle1.mkdir()
    forbidden = cycle1 / 'manifest.json'
    forbidden.write_text('{}')
    with pytest.raises(ValueError, match='Cycle 1'):
        load_workbench_inputs(forbidden, allowed_root=local_inputs[0], as_of=CUTOFF)


def test_etf_does_not_accept_company_fundamental_proxy(local_inputs):
    local_inputs[1]['instrument_type'] = 'etf'
    with pytest.raises(ValueError, match='not qualified ETF'):
        load(local_inputs)
    local_inputs[2]['observations'] = [r for r in local_inputs[2]['observations'] if r['metric'] not in {'operating_margin_pct','trailing_pe'}]
    result = load(local_inputs)
    assert assess(result.observations, as_of=CUTOFF)['instrument']['action'] == 'INSUFFICIENT_EVIDENCE'


@pytest.mark.parametrize('tier', ['OBSERVED_AS_OF','RECONSTRUCTED_RESEARCH'])
def test_declared_real_tiers_remain_honest_and_require_raw_lineage(local_inputs, tier):
    local_inputs[1]['evidence'] = tier
    for row in local_inputs[2]['observations']:
        row['evidence'] = tier
        row['source_url'] = 'https://example.org/fixture-extract'
    result = load(local_inputs)
    assert result.metadata['evidence_tier'] == tier
    assert all(r.evidence == tier and r.raw_metric and r.transform and r.provenance_hash for r in result.observations)
    assert 'NOT_INDEPENDENTLY_VERIFIED' in result.metadata['validation_scope']
    local_inputs[2]['observations'][0]['source_url'] = 'synthetic://fake-promotion'
    with pytest.raises(ValueError, match='Real source extracts'):
        load(local_inputs)


def test_reused_revision_identity_and_nonpositive_pe_rejected(local_inputs):
    duplicate = deepcopy(local_inputs[2]['observations'][0])
    duplicate.update(published_at='2026-08-05T00:00:00+00:00', first_seen_at='2026-08-05T00:00:00+00:00', retrieved_at='2026-08-05T00:00:00+00:00')
    local_inputs[2]['observations'].append(duplicate)
    with pytest.raises(ValueError, match='Duplicate revision identity'):
        load(local_inputs)
    local_inputs[2]['observations'].pop()
    pe = next(r for r in local_inputs[2]['observations'] if r['metric'] == 'trailing_pe')
    pe['value'] = -5
    with pytest.raises(ValueError, match='unavailable denominators require withdrawal'):
        load(local_inputs)


def test_real_source_published_before_but_first_seen_after_cutoff_is_missing(local_inputs):
    local_inputs[1]['evidence'] = 'RECONSTRUCTED_RESEARCH'
    for row in local_inputs[2]['observations']:
        row.update(evidence='RECONSTRUCTED_RESEARCH', source_url='https://example.org/fixture-extract', first_seen_at='2026-09-02T00:00:00+00:00', retrieved_at='2026-09-02T00:00:00+00:00')
    result = load(local_inputs)
    assert result.observations == ()
    assert all(row['status'] == 'MISSING' for row in result.metadata['selected_provenance'].values())
