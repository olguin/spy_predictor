from datetime import date, timedelta
import json
import math
from pathlib import Path

import pytest

from spy_predictor_quant.cycle1_calendar import _xnys, xnys_session_close, xnys_month_end
from spy_predictor_quant.cycle1_features import build_cycle_features
from spy_predictor_quant.cycle1_successor_features import SuccessorFeatureState
from spy_predictor_quant.cycle1_successor_inputs import SyntheticVintage
from spy_predictor_quant.cycle1_targets import TotalReturnPoint

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def inputs():
    config = json.loads((ROOT / 'config/cycle1-v5-draft.json').read_text())
    days = [x.date() for x in _xnys().sessions_in_range('1991-01-02', '1998-03-31')]
    points = [TotalReturnPoint(day, xnys_session_close(day),
                100 * math.exp(i * .0002 + .01 * math.sin(i / 13)),
                math.exp(i * .0002 + .01 * math.sin(i / 13))) for i, day in enumerate(days)]
    vintages = []
    for i in range(87):
        year, month = 1991 + i // 12, i % 12 + 1
        observed = date(year, month, 1)
        publication = xnys_session_close(xnys_month_end(year, month)) - timedelta(days=1)
        for series, value in [('CPIAUCSL', 100 + .2 * i), ('INDPRO', 90 + i * .1 + math.sin(i / 5)),
                              ('MPRIME', 5 + math.sin(i / 8)), ('GS3M', 3 + .3 * math.cos(i / 7))]:
            vintages.append(SyntheticVintage(series, observed, publication, 0, value))
    return config, points, tuple(vintages)


def build(config, points, vintages):
    state = SuccessorFeatureState(config)
    result = []
    for i, point in enumerate(points):
        if point.session_date == xnys_month_end(point.session_date.year, point.session_date.month):
            value = state.advance('SPY', points[:i + 1], vintages)
            if value is not None:
                result.append(value)
    return result, state


def test_all_nine_features_match_existing_math_on_complete_vintages(inputs):
    config, points, vintages = inputs
    records = [{'seriesId': row.series, 'observationDate': row.observation.isoformat(),
                'availableAt': row.published.isoformat(), 'realtimeStart': row.published.date().isoformat(),
                'value': row.value, 'missing': False} for row in vintages]
    original, _ = build_cycle_features(instrument='SPY', daily_points=points, macro_vintages=records, config=config)
    successor, _ = build(config, points, vintages)
    assert len(successor) == len(original) > 0
    for left, right in zip(successor, original, strict=True):
        for field in ('snapshotCutoff', 'rawFeatures', 'normalizedFeatures', 'dimensionScores', 'cycleScore'):
            assert left[field] == right[field]


def test_future_revision_does_not_change_computed_feature_history(inputs):
    config, points, vintages = inputs
    later = SyntheticVintage('MPRIME', date(1991, 1, 1), points[-1].event_time + timedelta(days=1), 1, 99)
    assert build(config, points, vintages)[0] == build(config, points, (*vintages, later))[0]


def test_exact_lag_withdrawal_cannot_resurrect_old_spread(inputs):
    config, points, vintages = inputs
    tombstone = SyntheticVintage('MPRIME', date(1997, 12, 1), points[-1].event_time, 1, None)
    baseline, _ = build(config, points, vintages)
    result, state = build(config, points, (*vintages, tombstone))
    assert baseline[-1]['snapshotDate'] == '1998-03-31'
    assert result[-1]['snapshotDate'] == '1998-02-27'
    assert 'bank-prime-minus-treasury-credit-spread-change-3m' in state.last_unavailable['SPY']


def test_month_skips_and_retroactive_market_edits_are_rejected(inputs):
    config, points, vintages = inputs
    state = SuccessorFeatureState(config)
    first = [p for p in points if p.session_date <= date(1991, 1, 31)]
    state.advance('SPY', first, vintages)
    with pytest.raises(ValueError, match='extend the unchanged'):
        state.advance('SPY', first, vintages)
    with pytest.raises(ValueError, match='skip a monthly'):
        state.advance('SPY', [p for p in points if p.session_date <= date(1991, 3, 28)], vintages)
