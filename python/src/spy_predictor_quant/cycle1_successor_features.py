"""Chronological all-nine-feature bridge for deterministic successor paths.

Reuses the frozen raw mathematics without modifying its implementation. Vintage
admission is explicit and retains missing revision semantics; normalization is
updated once per completed month and never refitted from future feature values.
"""
from __future__ import annotations

import copy
from collections import defaultdict
import math

from spy_predictor_quant.cycle1_calendar import _xnys, xnys_session_close
from spy_predictor_quant.cycle1_features import FEATURE_IDS, _raw_features, _economic_signs, expanding_midrank
from spy_predictor_quant.cycle1_successor_inputs import SyntheticVintage, select_vintages
from spy_predictor_quant.cycle1_targets import TotalReturnPoint
from spy_predictor_quant.cycle1_successor_calendar import month_end
from spy_predictor_quant.market_archive import content_hash


class SuccessorFeatureState:
    def __init__(self, config: dict):
        self.config = copy.deepcopy(config)
        self.signs = _economic_signs(self.config)
        self.history = defaultdict(lambda: {feature: [] for feature in FEATURE_IDS})
        self.previous = {}
        self.last_unavailable = {}

    def advance(self, instrument: str, daily_points: list[TotalReturnPoint],
                macro_vintages: tuple[SyntheticVintage, ...]) -> dict | None:
        if instrument not in {'SPY', 'QQQ'} or not daily_points:
            raise ValueError('Feature bridge requires synthetic SPY/QQQ daily history')
        previous = self.previous.get(instrument, ())
        if len(daily_points) <= len(previous) or tuple(daily_points[:len(previous)]) != previous:
            raise ValueError('Feature history must extend the unchanged prior history')
        expected = tuple(x.date() for x in _xnys().sessions_in_range(
            daily_points[0].session_date.isoformat(), daily_points[-1].session_date.isoformat()))
        if tuple(x.session_date for x in daily_points) != expected:
            raise ValueError('Feature history requires every scheduled daily session')
        for point in daily_points:
            if point.event_time != xnys_session_close(point.session_date):
                raise ValueError('Feature timestamp must match scheduled session close')
            if not all(math.isfinite(x) and x > 0 for x in (point.close, point.total_return_index)):
                raise ValueError('Feature levels must be finite and positive')
        by_month = {(p.session_date.year, p.session_date.month): p for p in daily_points}
        monthly = list(by_month.values())
        if any(p.session_date != month_end(p.session_date.year, p.session_date.month) for p in monthly):
            raise ValueError('Every supplied monthly segment must end at its scheduled close')
        if not monthly or monthly[-1] != daily_points[-1]:
            raise ValueError('Advance features only at a completed month end')
        if previous:
            prior = previous[-1].session_date
            now = monthly[-1].session_date
            if now.year * 12 + now.month != prior.year * 12 + prior.month + 1:
                raise ValueError('Feature updates must not skip a monthly cutoff')
        elif len(monthly) != 1:
            raise ValueError('Initialize feature history at its first monthly cutoff')
        point = monthly[-1]
        selected = {series: select_vintages(macro_vintages, series, point.event_time)
                    for series in ('CPIAUCSL', 'INDPRO', 'MPRIME', 'GS3M')}
        values = {series: {observed: record.value for observed, record in rows.items()
                           if record.value is not None} for series, rows in selected.items()}
        raw, missing = _raw_features(point, daily_points, monthly, values, self.config)
        self.previous[instrument] = tuple(daily_points)
        self.last_unavailable[instrument] = sorted(missing)
        if missing:
            return None
        history = self.history[instrument]
        for feature in FEATURE_IDS:
            history[feature].append(float(raw[feature]))
        minimum = self.config['features']['normalization']['percentileMinimumHistoryMonths']
        if len(history[FEATURE_IDS[0]]) < minimum:
            self.last_unavailable[instrument] = ['normalization-warmup']
            return None
        normalized = {feature: self.signs[feature] * expanding_midrank(raw[feature], history[feature])
                      for feature in FEATURE_IDS}
        dimensions = {name: sum(normalized[f['id']] for f in spec['features']) / len(spec['features'])
                      for name, spec in self.config['features']['dimensions'].items()}
        result = {'instrument': instrument, 'snapshotDate': point.session_date.isoformat(),
                  'snapshotCutoff': point.event_time.isoformat(), 'rawFeatures': raw,
                  'normalizedFeatures': normalized, 'dimensionScores': dimensions,
                  'cycleScore': sum(dimensions.values()) / 3, 'evidenceTier': 'SYNTHETIC_ONLY',
                  'normalizationHistoryMonths': len(history[FEATURE_IDS[0]]),
                  'withdrawnObservations': {series: [day.isoformat() for day, record in rows.items() if record.value is None]
                                            for series, rows in selected.items()}}
        return {**result, 'hash': content_hash(result)}
