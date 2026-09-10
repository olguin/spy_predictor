from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from spy_predictor_quant import prospective_observation as cohort

ROOT = Path(__file__).resolve().parents[2]


def test_frozen_schedule_is_exact_and_excludes_reserved_history():
    config = json.loads((ROOT/'config/prospective-observation-v1.json').read_text())
    assert config['scheduledOrigins'] == cohort.dev.calendar('2026-09-30', '2027-08-31')
    assert all(x > config['reservedHistoricalPeriod']['end'] for x in config['scheduledOrigins'])
    assert not config['finalEvaluationAccessAllowed']


def test_registration_and_pre_cutoff_status(tmp_path, monkeypatch):
    config = json.loads((ROOT/'config/prospective-observation-v1.json').read_text())
    samples = cohort.np.arange(161, dtype=float)
    monkeypatch.setattr(cohort, 'authority', lambda root: (config, {}))
    monkeypatch.setattr(cohort, 'frozen_distribution', lambda root, c, m: (samples, ['x']*161))
    monkeypatch.setattr(cohort.dev, 'file_sha256', lambda path: 'hash')
    folder, registration = cohort.register(tmp_path)
    assert registration['sampleCount'] == 161
    result = cohort.issue(tmp_path, datetime(2026, 9, 30, 19, tzinfo=timezone.utc))
    assert result['status'] == 'NOT_DUE'
    assert result['nextOrigin'] == '2026-09-30'
    assert not (folder/'forecasts').exists()
    status = cohort.status(tmp_path, datetime(2026, 9, 30, 19, tzinfo=timezone.utc))
    assert status['status'] == 'NOT_DUE'
    assert not (folder/'forecasts').exists()
    missed = cohort.status(tmp_path, datetime(2026, 10, 2, tzinfo=timezone.utc))
    assert missed['missedOrigins'] == ['2026-09-30']


def test_issue_window_and_immutable_resume(tmp_path, monkeypatch):
    config = json.loads((ROOT/'config/prospective-observation-v1.json').read_text())
    samples = cohort.np.linspace(-.2, .3, 161)
    monkeypatch.setattr(cohort, 'authority', lambda root: (config, {}))
    monkeypatch.setattr(cohort, 'frozen_distribution', lambda root, c, m: (samples, ['x']*161))
    monkeypatch.setattr(cohort.dev, 'file_sha256', lambda path: 'hash')
    now = datetime(2026, 9, 30, 21, tzinfo=timezone.utc)
    first = cohort.issue(tmp_path, now)
    assert first['status'] == 'ISSUED' and not first['finalEvaluationOpened']
    assert first['targetEndDate'] == '2027-09-30'
    second = cohort.issue(tmp_path, now)
    assert second['status'] == 'NOT_DUE' and second['issuedOrigins'] == ['2026-09-30']


def test_outcome_requires_prior_forecast_and_availability(tmp_path, monkeypatch):
    config = json.loads((ROOT/'config/prospective-observation-v1.json').read_text())
    samples = cohort.np.linspace(-.2, .3, 161)
    monkeypatch.setattr(cohort, 'authority', lambda root: (config, {}))
    monkeypatch.setattr(cohort, 'frozen_distribution', lambda root, c, m: (samples, ['x']*161))
    monkeypatch.setattr(cohort.dev, 'file_sha256', lambda path: 'hash')
    with pytest.raises(ValueError, match='issued'):
        cohort.attach_outcome(tmp_path, '2026-09-30', .1,
            datetime(2027, 10, 1, tzinfo=timezone.utc), datetime(2027, 10, 1, tzinfo=timezone.utc))
    cohort.issue(tmp_path, datetime(2026, 9, 30, 21, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match='not available'):
        cohort.attach_outcome(tmp_path, '2026-09-30', .1,
            datetime(2027, 10, 1, tzinfo=timezone.utc), datetime(2027, 9, 30, tzinfo=timezone.utc))
    result = cohort.attach_outcome(tmp_path, '2026-09-30', .1,
        datetime(2027, 10, 1, tzinfo=timezone.utc), datetime(2027, 10, 1, tzinfo=timezone.utc))
    assert result['status'] == 'OUTCOME_ATTACHED_NO_INTERIM_REVIEW'
