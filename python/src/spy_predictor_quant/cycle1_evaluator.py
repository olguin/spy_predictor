"""Primary return procedure, exercised only through the synthetic runner for now.

This module has no market-data loader or confirmation-opening mechanism.
Separate downstream calculations and orchestration live in cycle1_procedure.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np

from spy_predictor_quant.cycle1_models import (
    MODEL_IDS, UnavailableFold, distribution_scores, fit_roster, tertile_boundaries, tertile_index,
)
from spy_predictor_quant.cycle1_synthetic import SyntheticPath


@dataclass(frozen=True)
class FoldScores:
    months: np.ndarray
    losses: np.ndarray       # date, mode, model
    squared_errors: np.ndarray
    interval_coverage: np.ndarray
    interval_width: np.ndarray
    training_counts: np.ndarray
    score_groups: np.ndarray # date, mode
    outcomes: np.ndarray
    fitted: dict | None = None


def training_indices(path: SyntheticPath, index: int, mode: str, config: dict) -> np.ndarray:
    p = config['partitions']; cal = p['fixedCalendar']
    if mode not in p['modes']:
        raise ValueError('Unknown walk-forward mode')
    origin_start = cal['selectionOriginStart'] if path.instrument == 'SPY' else cal['qqqOriginStart']
    origins = path.months
    cutoff = origins[index]
    # Strict maturity: a label ending at the same month-end is not yet training data.
    mask = (origins >= np.datetime64(origin_start[:7], 'M')) & (origins + np.timedelta64(12, 'M') < cutoff)
    mask &= ~((origins >= np.datetime64(cal['embargoStart'][:7], 'M'))
              & (origins <= np.datetime64(cal['embargoEnd'][:7], 'M')))
    if mode == 'rolling':
        mask &= origins > cutoff - np.timedelta64(p['rollingWindowMonths'], 'M')
    mask &= np.isfinite(path.outcomes) & np.isfinite(path.dimensions).all(axis=1)
    mask &= np.isfinite(path.volatility) & ~path.missing
    return np.flatnonzero(mask)


def score_partition(path: SyntheticPath, config: dict, partition: str,
                    *, retain_fits: bool = False) -> FoldScores:
    if path.evidence_tier != 'SYNTHETIC_ONLY' or path.instrument != 'SPY':
        raise ValueError('Current evaluator entry is restricted to synthetic SPY')
    if partition not in ('selection', 'confirmation'):
        raise ValueError('Unknown partition')
    cal = config['partitions']['fixedCalendar']
    start_key = 'selectionForecastStart' if partition == 'selection' else 'confirmationStart'
    indices = np.flatnonzero((path.months >= np.datetime64(cal[start_key][:7], 'M')) &
                             (path.months <= np.datetime64(cal[partition + 'End'][:7], 'M')))
    expected = config['partitions']['fixedCalendarCounts'][partition]
    if len(indices) != expected or np.any(np.diff(path.months[indices].astype(int)) != 1):
        raise ValueError('Fixed eligible calendar is missing or compressed')
    shape = (len(indices), 2, 7)
    loss, error, coverage, width = (np.full(shape, np.nan) for _ in range(4))
    counts = np.zeros((len(indices), 2), dtype=int)
    groups = np.full((len(indices), 2), -1, dtype=int)
    model_specs = config['models']['perInstrument']
    retained = {} if retain_fits else None
    for row, index in enumerate(indices):
        # Expanding and rolling folds often have the same training rows early in
        # selection. Reuse their fits/scores only when the entire index sets match.
        previous_train = None
        for mode_index, mode in enumerate(config['partitions']['modes']):
            train = training_indices(path, index, mode, config)
            counts[row, mode_index] = len(train)
            if path.missing[index] or not np.isfinite(path.outcomes[index]):
                continue
            if previous_train is not None and np.array_equal(train, previous_train):
                for array in (loss, error, coverage, width):
                    array[row, mode_index] = array[row, mode_index-1]
                groups[row, mode_index] = groups[row, mode_index-1]
                if retained is not None:
                    retained[(row, mode_index)] = retained[(row, mode_index-1)]
                continue
            previous_train = train
            train_x, train_v, train_y = path.dimensions[train], path.volatility[train], path.outcomes[train]
            fitted = fit_roster(train_x, train_v, train_y, model_specs,
                                minimum=config['partitions']['minimumTrainingMonths'],
                                minimum_bin=config['evaluationContract']['tertiles']['minimumBinObservations'])
            if retained is not None:
                retained[(row, mode_index)] = {'models': fitted, 'trainingIndices': train, 'originIndex': int(index)}
            try:
                cycle = fitted['fixed-cycle-score']
                bounds = cycle.boundaries if cycle is not None else tertile_boundaries(train_x.mean(axis=1))
                groups[row, mode_index] = tertile_index(path.dimensions[index].mean(), bounds)
            except UnavailableFold:
                pass
            for model_index, spec in enumerate(model_specs):
                try:
                    model = fitted[spec['id']]
                    if model is None:
                        continue
                    samples = model.predict(path.dimensions[index], path.volatility[index])
                except UnavailableFold:
                    continue
                y = path.outcomes[index]
                values = distribution_scores(samples, y)
                for array, value in zip((loss, error, coverage, width), values, strict=True):
                    array[row, mode_index, model_index] = value
    return FoldScores(path.months[indices], loss, error, coverage, width, counts,
                      groups, path.outcomes[indices], retained)


def moving_block_indices(n: int, *, block_length: int, resamples: int, seed: int) -> np.ndarray:
    if n < block_length or min(block_length, resamples) < 1:
        raise ValueError('Insufficient bootstrap support')
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n - block_length + 1,
                          size=(resamples, (n + block_length - 1) // block_length))
    return (starts[:, :, None] + np.arange(block_length)).reshape(resamples, -1)[:, :n]


@lru_cache(maxsize=8)
def moving_block_counts(n: int, block_length: int, resamples: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Reuse the frozen resampling plan; it never depends on simulated outcomes."""
    indices = moving_block_indices(n, block_length=block_length, resamples=resamples, seed=seed)
    counts = np.zeros((resamples, n), dtype=float)
    np.add.at(counts, (np.arange(resamples)[:, None], indices), 1)
    indices.setflags(write=False)
    counts.setflags(write=False)
    return indices, counts


def paired_bootstrap(differences: np.ndarray, indices: np.ndarray,
                     *, counts: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Shared resamples over every comparison; null-centered one-sided p-values."""
    if differences.ndim != 2 or not np.isfinite(differences).all():
        raise ValueError('Paired differences must be a finite date/comparison matrix')
    observed = differences.mean(axis=0)
    # Build date frequencies once, avoiding a resamples x dates x comparisons cube.
    if counts is None:
        counts = np.zeros((len(indices), len(differences)), dtype=float)
        np.add.at(counts, (np.arange(len(indices))[:, None], indices), 1)
    means = counts @ differences / indices.shape[1]
    pvalues = (1 + np.sum(means - observed >= observed, axis=0)) / (len(indices) + 1)
    lower = np.quantile(means, 0.05, axis=0, method='linear')
    return pvalues, lower


def holm_rejections(pvalues: list[float], alpha: float) -> list[bool]:
    if len(pvalues) != 2 or any(not np.isfinite(p) or not 0 <= p <= 1 for p in pvalues):
        raise ValueError('The composite Holm family always has exactly two p-values')
    result = [False, False]
    for rank, index in enumerate(sorted(range(2), key=lambda i: (pvalues[i], i))):
        if pvalues[index] > alpha / (2 - rank):
            break
        result[index] = True
    return result


def assess_partition(scores: FoldScores, config: dict, partition: str,
                     *, eligible_claims: tuple[bool, bool] = (True, True),
                     transfer_only: bool = False) -> dict[str, Any]:
    if transfer_only and (partition != 'confirmation' or scores.losses.shape[2] != 3):
        raise ValueError('Transfer assessment requires its reference and two registered transfers')
    if not transfer_only and scores.losses.shape[2] != 7:
        raise ValueError('Primary assessment requires all seven registered SPY models')
    comparator_count = 1 if transfer_only else 5
    challenger_indices = (1, 2) if transfer_only else (5, 6)
    gates = config['promotionGates']; contract = config['evaluationContract']
    n = len(scores.months)
    bootstrap = config['partitions']['bootstrap']
    # A single full-calendar draw is shared by both claims. If boundary-only
    # unavailable folds occur, use the same starts for their common-date length.
    shared_indices: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    claims = []
    for claim_index, model_index in enumerate(challenger_indices):
        selected = [*range(comparator_count), model_index]
        available = np.isfinite(scores.losses[:, :, selected]).all(axis=(1, 2))
        pos = np.flatnonzero(available)
        sufficient = len(pos) >= (config['partitions']['minimumSelectionForecastsPerMode']
                                  if partition == 'selection' else config['partitions']['minimumConfirmationLabeledMonths'])
        sufficient &= len(pos) / n * 100 >= contract['coverage']['pairedMinimumPercent']
        interior_gap = bool(len(pos) and np.any(np.diff(pos) != 1))
        claim = {'modelId': MODEL_IDS[5+claim_index], 'status': 'INSUFFICIENT_EVIDENCE',
                 'pValue': 1.0, 'pairedDates': len(pos), 'calendarDates': n,
                 'coveragePercent': 100 * len(pos) / n, 'nonSignificanceGatesPassed': False,
                 'qualified': False}
        if not eligible_claims[claim_index]:
            claim['status'] = 'SKIPPED_SELECTION_FAILED'
            claims.append(claim); continue
        if interior_gap:
            claim['status'] = 'INVALID_EVALUATION_INTERNAL_CALENDAR_GAP'
            claims.append(claim); continue
        if not sufficient:
            claims.append(claim); continue
        base = scores.losses[pos, :, :comparator_count]
        candidate = scores.losses[pos, :, model_index, None]
        delta = base - candidate
        flat = delta.reshape(len(pos), 2*comparator_count)
        if len(pos) not in shared_indices:
            shared_indices[len(pos)] = moving_block_counts(
                len(pos), bootstrap['blockLengthMonths'], bootstrap['resamples'], bootstrap['seed'])
        indices, counts = shared_indices[len(pos)]
        pvalues, lower = paired_bootstrap(flat, indices, counts=counts)
        mean = delta.mean(axis=0)
        base_mean = base.mean(axis=0)
        relative = np.divide(mean, base_mean, out=np.full_like(mean, -np.inf), where=base_mean > 0)
        g = gates['returnDistribution']
        material = bool(np.all(mean >= g['minimumAbsoluteImprovement']) and
                        np.all(relative >= g['minimumRelativeImprovement']))
        interval = bool(np.all(lower > g['bootstrapLowerBoundMustExceed']))
        rmse_delta = (np.sqrt(scores.squared_errors[pos, :, model_index].mean(axis=0))[:, None]
                      - np.sqrt(scores.squared_errors[pos, :, :comparator_count].mean(axis=0)))
        rmse_ok = bool(np.all(rmse_delta <= g['maximumRmseDegradation']))
        eras = []
        for era in contract['eras'][partition]:
            mask = (scores.months[pos] >= np.datetime64(era['start'][:7], 'M')) & (scores.months[pos] <= np.datetime64(era['end'][:7], 'M'))
            support = int(mask.sum())
            eras.append((support, delta[mask].mean(axis=0) if support else np.full((2, comparator_count), -np.inf),
                         base[mask].mean(axis=0) if support else np.zeros((2, comparator_count))))
        stability = gates['stability']
        era_support = all(e[0] >= stability['minimumObservationsPerEra'] for e in eras)
        era_positive = np.mean([e[1] > 0 for e in eras], axis=0)
        era_floor = all(np.all(e[1] >= -stability['maximumRelativeLossDegradationAnyEra'] * e[2]) for e in eras)
        era_ok = bool(era_support and len(eras) >= stability['minimumEvaluableEras'] and
                      np.all(era_positive >= stability['minimumPositiveEraFraction']) and era_floor)
        benefits = []
        for block in range((n + 11) // 12):
            benefits.append(np.maximum(delta[(pos // 12) == block], 0).sum(axis=0))
        benefits = np.array(benefits); total = benefits.sum(axis=0)
        concentration = np.divide(benefits.max(axis=0), total,
                                  out=np.full_like(total, np.inf), where=total > 0)
        concentration_ok = bool(np.all(concentration <= stability['maximumSingleBlockBenefitFraction']))
        half_ok = True
        if partition == 'confirmation':
            split = np.datetime64(config['partitions']['fixedCalendar']['confirmationSecondHalfStart'][:7], 'M')
            first = scores.months[pos] < split
            half_ok = all(mask.sum() >= config['partitions']['minimumLabeledMonthsPerHalf']
                          and np.all(delta[mask].mean(axis=0) > 0) for mask in (first, ~first))
        checks = {'materiality': material, 'bootstrapLowerBound': interval, 'rmse': rmse_ok,
                  'eras': era_ok, 'concentration': concentration_ok, 'confirmationHalves': bool(half_ok)}
        claim.update(status='EVALUATED', pValue=float(pvalues.max()),
                     nonSignificanceGatesPassed=all(checks.values()), gates=checks,
                     componentPValues=pvalues.tolist(), lowerBounds=lower.tolist(),
                     meanImprovement=mean.tolist(), relativeImprovement=relative.tolist())
        claims.append(claim)
    decisions = holm_rejections([c['pValue'] for c in claims], gates['multipleTesting']['familyWiseAlpha'])
    for claim, reject in zip(claims, decisions, strict=True):
        claim['holmRejected'] = reject
        claim['qualified'] = bool(reject and claim['nonSignificanceGatesPassed'])
    return {'partition': partition, 'claims': claims,
            'intervalDiagnostics': _interval_diagnostics(scores, transfer_only=transfer_only)}


def _interval_diagnostics(scores: FoldScores, *, transfer_only: bool = False) -> list[dict]:
    result = []
    names = (MODEL_IDS[0], *MODEL_IDS[5:]) if transfer_only else MODEL_IDS
    for model, name in enumerate(names):
        for mode in range(2):
            mask = np.isfinite(scores.losses[:, mode, model])
            result.append({'modelId': name, 'mode': ('expanding', 'rolling')[mode],
                           'availableForecasts': int(mask.sum()),
                           'coverage90': float(scores.interval_coverage[mask, mode, model].mean()) if mask.any() else None,
                           'meanIntervalWidth': float(scores.interval_width[mask, mode, model].mean()) if mask.any() else None})
    return result


def evaluate_primary(path: SyntheticPath, config: dict) -> dict[str, Any]:
    selection = assess_partition(score_partition(path, config, 'selection'), config, 'selection')
    survivors = tuple(c['qualified'] for c in selection['claims'])
    if any(survivors):
        confirmation = assess_partition(score_partition(path, config, 'confirmation'), config,
                                         'confirmation', eligible_claims=survivors)
    else:
        confirmation = {'partition': 'confirmation', 'status': 'NOT_OPENED_NO_SELECTION_SURVIVOR',
                        'claims': [{'modelId': name, 'qualified': False, 'pValue': 1.0,
                                    'status': 'SKIPPED_SELECTION_FAILED'} for name in MODEL_IDS[5:]]}
    return {'evidenceTier': 'SYNTHETIC_ONLY', 'selection': selection, 'confirmation': confirmation,
            'qualified': any(c['qualified'] for c in confirmation['claims']),
            'downside': 'NOT_IMPLEMENTED', 'policy': 'NOT_IMPLEMENTED', 'transfer': 'NOT_IMPLEMENTED',
            'realDataApproval': False}
