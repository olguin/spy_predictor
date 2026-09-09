from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from spy_predictor_quant.cycle1_config import load_cycle1_plan
from spy_predictor_quant.cycle1_evaluator import (FoldScores, assess_partition, holm_rejections,
    moving_block_indices, paired_bootstrap, score_partition, training_indices)
from spy_predictor_quant.cycle1_models import (UnavailableFold, crps, fit_distribution,
    tertile_boundaries, tertile_index)
from spy_predictor_quant.cycle1_simulation_design import load_design
from spy_predictor_quant.cycle1_synthetic import generate_paths

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def config():
    return load_cycle1_plan(ROOT / 'config/cycle1-v5-draft.json').raw


@pytest.fixture(scope='module')
def design():
    return load_design(ROOT / 'config/cycle1-simulation-v1.json', repo_root=ROOT)


@pytest.fixture(scope='module')
def path(design):
    return generate_paths(design, 0, 0)['SPY']


def test_crps_matches_pairwise_definition():
    x = np.array([-1., 0., 0., 3.])
    expected = np.abs(x - .4).mean() - .5 * np.abs(x[:, None] - x).mean()
    assert crps(x, .4) == pytest.approx(expected)
    assert crps(np.array([0., 2.]), 1) == pytest.approx(.5)
    with pytest.raises(ValueError):
        crps(np.array([]), 1)


def test_ridge_centered_residuals_and_unpenalized_intercept():
    rng = np.random.default_rng(4)
    x = rng.normal(size=(120, 3)); x[:, 1] = 2
    y = 3 + .2 * x[:, 0] + rng.normal(0, .1, 120)
    v = np.ones(120)
    fit = fit_distribution('regularized-cycle', x, v, y)
    shifted = fit_distribution('regularized-cycle', x, v, y + 7)
    assert fit.residuals.mean() == pytest.approx(0, abs=1e-15)
    assert fit.slopes[1] == 0
    np.testing.assert_allclose(shifted.predict(x[0], 1), fit.predict(x[0], 1) + 7)
    z = (x - fit.means) / fit.scales
    np.testing.assert_allclose((z.T @ z + 10 * np.eye(3)) @ fit.slopes, z.T @ (y-y.mean()))


def test_tertile_ties_and_collapsed_bins():
    bounds = tertile_boundaries(np.arange(120.))
    assert tertile_index(bounds[0], bounds) == 0
    assert tertile_index(bounds[1], bounds) == 1
    with pytest.raises(UnavailableFold, match='Collapsed'):
        tertile_boundaries(np.ones(120))
    # Distinct boundaries do not guarantee all bins have minimum support.
    x = np.tile(np.concatenate([np.zeros(79), np.ones(40), [2]])[:, None], (1, 3))
    with pytest.raises(UnavailableFold):
        fit_distribution('fixed-cycle-score', x, np.ones(120), np.arange(120.))


def test_labels_are_overlapping_monthly_path_sums(path):
    for t in [30, 180, 360]:
        assert path.outcomes[t] == pytest.approx(path.monthly_returns[t+1:t+13].sum())
        assert path.outcomes[t+1]-path.outcomes[t] == pytest.approx(
            path.monthly_returns[t+13]-path.monthly_returns[t+1])
    assert np.isnan(path.outcomes[-12:]).all()


def test_streams_reproduce_and_validation_is_locked(design):
    a = generate_paths(design, 0, 0)
    b = generate_paths(design, 0, 0)
    c = generate_paths(design, 0, 1)
    np.testing.assert_equal(a['SPY'].outcomes, b['SPY'].outcomes)
    assert not np.allclose(a['SPY'].monthly_returns, c['SPY'].monthly_returns)
    assert not np.allclose(a['SPY'].monthly_returns, a['QQQ'].monthly_returns)
    with pytest.raises(RuntimeError, match='not released'):
        generate_paths(design, 0, 0, stream='validation')
    with pytest.raises(ValueError, match='budget'):
        generate_paths(design, 0, 3)


def test_maturity_calendar_rolling_and_embargo(path, config):
    lookup = lambda month: int(np.flatnonzero(path.months == np.datetime64(month, 'M'))[0])
    first = lookup('2010-11')
    for mode in ['expanding', 'rolling']:
        train = training_indices(path, first, mode, config)
        assert len(train) == 120
        assert np.all(path.months[train] + np.timedelta64(12, 'M') < path.months[first])
    assert len(training_indices(path, lookup('2016-06'), 'expanding', config)) == 187
    assert len(training_indices(path, lookup('2016-06'), 'rolling', config)) == 167
    later = training_indices(path, lookup('2020-01'), 'expanding', config)
    assert not np.any((path.months[later] >= np.datetime64('2016-07')) & (path.months[later] <= np.datetime64('2017-06')))
    assert np.any(path.months[later] >= np.datetime64('2017-07'))


def test_fixed_calendar_has_97_confirmation_months(path, config):
    scored = score_partition(path, config, 'confirmation')
    assert len(scored.months) == 97
    assert (scored.months < np.datetime64('2021-07')).sum() == 48
    assert (scored.months >= np.datetime64('2021-07')).sum() == 49
    assert np.datetime64('2024-10') in scored.months


def test_future_outcomes_do_not_change_selection_forecasts(path, config):
    y = path.outcomes.copy()
    y[path.months >= np.datetime64('2016-07')] = 1e6
    before = score_partition(path, config, 'selection')
    after = score_partition(replace(path, outcomes=y), config, 'selection')
    np.testing.assert_equal(before.losses, after.losses)
    # Also mutate labels that exist but cannot yet mature at the first cutoff.
    index = int(np.flatnonzero(path.months == np.datetime64('2010-11'))[0])
    y = path.outcomes.copy(); y[index-12:] = 1e6
    np.testing.assert_equal(training_indices(path, index, 'expanding', config),
                            training_indices(replace(path, outcomes=y), index, 'expanding', config))


def test_shared_block_bootstrap_matches_direct_resampling():
    d = np.column_stack([np.linspace(-.02, .04, 24), np.linspace(-.02, .04, 24)])
    idx = moving_block_indices(24, block_length=12, resamples=199, seed=42)
    assert np.all(np.diff(idx[:, :12], axis=1) == 1)
    p, lower = paired_bootstrap(d, idx)
    means = d[idx].mean(axis=1); observed = d.mean(axis=0)
    np.testing.assert_equal(p, (1 + (means-observed >= observed).sum(axis=0))/200)
    np.testing.assert_allclose(lower, np.quantile(means, .05, axis=0))
    assert p[0] == p[1]


def test_holm_keeps_skipped_claim_in_family():
    assert holm_rejections([.06, 1], .1) == [False, False]
    assert holm_rejections([.04, .09], .1) == [True, True]
    with pytest.raises(ValueError):
        holm_rejections([.04], .1)


def _fake_scores():
    months = np.arange('2010-11', '2016-07', dtype='datetime64[M]')
    loss = np.full((68, 2, 7), .1)
    loss[:, :, 5:] = .09
    zeros = np.zeros_like(loss)
    return FoldScores(months, loss, zeros, zeros, zeros,
                      np.full((68, 2), 120), np.zeros((68, 2), int), np.zeros(68))


def test_challenger_must_beat_strong_baseline_and_both_modes(config):
    scores = _fake_scores()
    scores.losses[:, :, 4] = .09
    result = assess_partition(scores, config, 'selection')
    assert all(c['pValue'] == 1 and not c['qualified'] for c in result['claims'])
    scores = _fake_scores()
    scores.losses[:, 1, 5:] = .1
    result = assess_partition(scores, config, 'selection')
    assert all(not c['qualified'] for c in result['claims'])


def test_complete_favorable_fixture_passes_and_missing_calendar_does_not(config):
    scores = _fake_scores()
    result = assess_partition(scores, config, 'selection')
    assert all(c['qualified'] for c in result['claims'])
    scores.losses[30, 0, 5] = np.nan
    result = assess_partition(scores, config, 'selection')
    assert result['claims'][0]['coveragePercent'] < 100
    assert result['claims'][0]['status'] == 'INVALID_EVALUATION_INTERNAL_CALENDAR_GAP'
    assert not result['claims'][0]['qualified']


def test_cannot_score_non_synthetic_or_qqq_as_development(path, config):
    for other in [replace(path, evidence_tier='RECONSTRUCTED_RESEARCH_ONLY'), replace(path, instrument='QQQ')]:
        with pytest.raises(ValueError, match='synthetic SPY'):
            score_partition(other, config, 'selection')


def test_resampling_cache_is_read_only_and_preserves_exact_arithmetic():
    from spy_predictor_quant.cycle1_evaluator import moving_block_counts
    idx, counts = moving_block_counts(24, 12, 199, 42)
    d = np.arange(48.).reshape(24, 2) / 100
    ordinary = paired_bootstrap(d, idx)
    cached = paired_bootstrap(d, idx, counts=counts)
    for before, after in zip(ordinary, cached, strict=True):
        np.testing.assert_array_equal(before, after)
    with pytest.raises(ValueError):
        counts[0, 0] = 123
    assert moving_block_counts(24, 12, 199, 42)[1] is counts


def test_calendar_audit_projects_metadata_and_checks_hashes(tmp_path):
    import hashlib
    import json
    from spy_predictor_quant.cycle1_calendar_audit import calendar_audit
    dates = [str(m) + '-28' for m in np.arange('2017-07', '2025-08', dtype='datetime64[M]')
             if m != np.datetime64('2024-10')]
    values = {'targets': [{'snapshotDate': d, 'forbiddenOutcome': 'never-report-me'} for d in dates],
              'macro-vintages': [{'seriesId':'CPIAUCSL','observationDate':'2025-10-01','missing':True}]}
    artifacts = []
    for kind, rows in values.items():
        data = ''.join(json.dumps(row)+'\n' for row in rows).encode()
        (tmp_path / (kind+'.ndjson')).write_bytes(data)
        artifacts.append({'kind':kind,'path':kind+'.ndjson','sha256':hashlib.sha256(data).hexdigest(),'records':len(rows)})
    track={'instrument':'SPY','normalizedArtifacts':artifacts,'resolvedPartitions':{
        'confirmation':{'start':'2017-07-31','end':'2025-07-31'}}}
    data=json.dumps(track).encode(); (tmp_path/'track.json').write_bytes(data)
    manifest={'datasetIdentityHash':'a'*64,'tracks':[{'role':'ACTUAL_ETF_VALIDATION',
        'manifestPath':'track.json','manifestSha256':hashlib.sha256(data).hexdigest()}]}
    p=tmp_path/'manifest.json';p.write_text(json.dumps(manifest))
    result=calendar_audit(tmp_path,p)
    assert result['tracks'][0]['fixedCalendarMonths']==97
    assert result['tracks'][0]['missingOriginMonths']==['2024-10']
    assert result['tracks'][0]['endpointCpiMetadata'][0]['nonmissingVintageRecords']==0
    assert 'never-report-me' not in json.dumps(result)
    (tmp_path/'targets.ndjson').write_text('corrupted')
    with pytest.raises(ValueError,match='hash mismatch'):
        calendar_audit(tmp_path,p)


def test_shared_roster_matches_scalar_fits(config):
    from spy_predictor_quant.cycle1_models import fit_roster
    rng=np.random.default_rng(803)
    for n in (120,167,200):
        x=rng.normal(size=(n,3)); y=rng.normal(size=n); v=rng.uniform(size=n)
        fitted=fit_roster(x,v,y,config['models']['perInstrument'])
        for spec in config['models']['perInstrument']:
            scalar=fit_distribution(spec['id'],x,v,y)
            np.testing.assert_array_equal(fitted[spec['id']].predict(x[0],v[0]),scalar.predict(x[0],v[0]))


def test_single_sort_scores_match_empirical_quantiles_for_all_training_sizes():
    from spy_predictor_quant.cycle1_models import distribution_scores
    rng=np.random.default_rng(91)
    for n in range(20,350):
        samples=rng.normal(size=n); y=.123
        score,error,covered,width=distribution_scores(samples,y)
        low,high=np.quantile(samples,[.05,.95],method='inverted_cdf')
        assert score==crps(samples,y)
        assert error==(samples.mean()-y)**2
        assert covered==bool(low<=y<=high)
        assert width==high-low


def test_retained_fits_do_not_change_forecasts(path,config):
    a=score_partition(path,config,'selection')
    b=score_partition(path,config,'selection',retain_fits=True)
    np.testing.assert_array_equal(a.losses,b.losses)
    assert b.fitted[(0,0)] is b.fitted[(0,1)]
