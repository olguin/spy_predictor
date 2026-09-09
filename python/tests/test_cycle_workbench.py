from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from spy_predictor_quant.cycle_workbench import assess, synthetic_fixture, export_report

AS_OF = '2026-08-31T20:00:00+00:00'


@pytest.mark.parametrize(('scenario', 'action'), [
    ('recovery', 'CANDIDATE_FOR_RESEARCH'),
    ('cheap-deteriorating', 'WAIT_FOR_CONFIRMATION'),
    ('stressed-selloff', 'DEFENSIVE_REVIEW'),
    ('expensive-rally', 'NEUTRAL'),
    ('conflicting', 'WAIT_FOR_CONFIRMATION'),
    ('missing-data', 'INSUFFICIENT_EVIDENCE'),
])
def test_conditional_assessment_does_not_hide_conflicting_or_missing_evidence(scenario, action):
    result = assess(synthetic_fixture(scenario), as_of=AS_OF)
    assert result['instrument']['action'] == action
    assert result['instrument']['reasons']
    assert 'probability' not in result['instrument']
    if scenario == 'cheap-deteriorating':
        assert 'TIMING_ADVERSE' in result['instrument']['counterevidence']
        assert result['market']['posture'] == 'SUPPORTIVE'


def test_future_release_and_late_first_seen_do_not_change_past_identity():
    rows = synthetic_fixture()
    baseline = assess(rows, as_of=AS_OF)
    later = datetime(2026, 9, 2, tzinfo=timezone.utc)
    revision = replace(rows[0], score=-1, published_at=later, first_seen_at=later, revision='later')
    unseen = replace(rows[1], score=-1, first_seen_at=later, revision='late-capture')
    assert assess((*rows, revision, unseen), as_of=AS_OF) == baseline


def test_published_revision_is_used_and_revised_old_evidence_stays_stale():
    rows = synthetic_fixture()
    later = datetime(2026, 8, 20, tzinfo=timezone.utc)
    revision = replace(rows[0], score=-1, published_at=later, first_seen_at=later, revision='revision')
    result = assess((*rows, revision), as_of=AS_OF)
    assert result['components']['growth']['score'] == -1
    assert result['market']['posture'] == 'MIXED'
    assert assess((*rows, revision), as_of='2026-10-01T00:00:00+00:00')['components']['growth']['status'] == 'STALE'


def test_no_admissible_data_means_abstention_not_a_synthetic_fallback():
    result = assess(synthetic_fixture(), as_of='2026-07-01T00:00:00+00:00')
    assert result['instrument']['action'] == 'INSUFFICIENT_EVIDENCE'
    assert result['evidence_quality']['fresh_components'] == 0


def test_ambiguous_vintage_is_rejected():
    rows = synthetic_fixture()
    with pytest.raises(ValueError, match='Ambiguous'):
        assess((*rows, replace(rows[0], score=-1)), as_of=AS_OF)


def test_export_matches_report_and_escapes_display_identity(tmp_path):
    result = assess(synthetic_fixture(), as_of=AS_OF, symbol='<script>alert(1)</script>')
    paths = export_report(result, tmp_path)
    from pathlib import Path
    assert json.loads(Path(paths['json']).read_text()) == result
    html = Path(paths['html']).read_text()
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html
    assert result['report_hash'] in html
    before = Path(paths['json']).stat().st_mtime_ns
    assert export_report(result, tmp_path) == paths
    assert Path(paths['json']).stat().st_mtime_ns == before
    result['instrument']['action'] = 'BUY_NOW'
    with pytest.raises(ValueError, match='identity'):
        export_report(result, tmp_path)


def test_synthetic_adapter_rejects_real_sources_and_naive_cutoff():
    with pytest.raises(ValueError, match='synthetic'):
        replace(synthetic_fixture()[0], evidence='OBSERVED_AS_OF', source='https://example.com')
    with pytest.raises(ValueError, match='timezone-aware'):
        assess(synthetic_fixture(), as_of='2026-08-31')
