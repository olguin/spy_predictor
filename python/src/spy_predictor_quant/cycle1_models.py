"""Deterministic return distributions shared by synthetic Cycle 1 evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

MODEL_IDS = ('unconditional-history', 'volatility-conditioned-history', 'valuation-only',
             'direction-only', 'position-plus-direction', 'fixed-cycle-score', 'regularized-cycle')
RIDGE_COLUMNS = {'valuation-only': (0,), 'direction-only': (2,),
                 'position-plus-direction': (0, 2), 'regularized-cycle': (0, 1, 2)}


class UnavailableFold(ValueError):
    """An explicitly unavailable forecast, counted against calendar coverage."""


def crps(samples: np.ndarray, outcome: float) -> float:
    """Empirical CRPS, using an O(n log n) sorted pair-distance identity."""
    samples = np.sort(np.asarray(samples, dtype=float))
    n = len(samples)
    if n == 0 or not np.isfinite(samples).all() or not np.isfinite(outcome):
        raise ValueError('CRPS requires finite nonempty samples and an outcome')
    pair_half = np.dot(2 * np.arange(n) - n + 1, samples) / n**2
    return float(np.mean(np.abs(samples - outcome)) - pair_half)


@lru_cache(maxsize=512)
def _score_constants(n: int) -> tuple[np.ndarray, np.ndarray]:
    weights = 2 * np.arange(n) - n + 1
    quantile_indices = np.ceil(n * np.array([0.05, 0.95])).astype(int) - 1
    weights.setflags(write=False)
    quantile_indices.setflags(write=False)
    return weights, quantile_indices


def distribution_scores(samples: np.ndarray, outcome: float) -> tuple[float, float, bool, float]:
    """One sort supplies CRPS and the frozen empirical 5/95% quantiles."""
    if len(samples) == 0 or not np.isfinite(samples).all() or not np.isfinite(outcome):
        raise ValueError('Distribution scoring requires finite samples and outcome')
    mean = samples.mean()  # Keep the original reduction order for location error.
    ordered = np.sort(samples)
    weights, quantile_indices = _score_constants(len(samples))
    loss = np.mean(np.abs(ordered - outcome)) - np.dot(weights, ordered) / len(samples)**2
    low, high = ordered[quantile_indices]
    return float(loss), float((mean-outcome)**2), bool(low <= outcome <= high), float(high-low)


def tertile_boundaries(values: np.ndarray) -> np.ndarray:
    if len(values) == 0 or not np.isfinite(values).all():
        raise UnavailableFold('Invalid tertile training data')
    bounds = np.quantile(values, [1 / 3, 2 / 3], method='linear')
    if bounds[0] >= bounds[1]:
        raise UnavailableFold('Collapsed tertile boundaries')
    return bounds


def tertile_index(value: float | np.ndarray, bounds: np.ndarray):
    # side=left makes equality belong to the lower bin.
    return np.searchsorted(bounds, value, side='left')


@dataclass(frozen=True)
class FittedDistribution:
    model_id: str
    columns: tuple[int, ...]
    means: np.ndarray
    scales: np.ndarray
    slopes: np.ndarray
    intercept: float
    residuals: np.ndarray
    boundaries: np.ndarray
    bins: tuple[np.ndarray, ...]

    def predict(self, dimensions: np.ndarray, volatility: float) -> np.ndarray:
        if not np.isfinite(dimensions).all() or not np.isfinite(volatility):
            raise UnavailableFold('Missing forecast input')
        if self.model_id in RIDGE_COLUMNS:
            location = self.intercept + ((dimensions[list(self.columns)] - self.means)
                                         / self.scales) @ self.slopes
            return self.residuals + location
        if self.model_id == 'unconditional-history':
            return self.residuals.copy()
        value = volatility if self.model_id == 'volatility-conditioned-history' else float(np.mean(dimensions))
        return self.bins[int(tertile_index(value, self.boundaries))].copy()


def fit_distribution(model_id: str, dimensions: np.ndarray, volatility: np.ndarray,
                     outcomes: np.ndarray, *, minimum: int = 120, alpha: float = 10,
                     minimum_bin: int = 20) -> FittedDistribution:
    x, v, y = (np.asarray(a, dtype=float) for a in (dimensions, volatility, outcomes))
    if model_id not in MODEL_IDS:
        raise ValueError('Unregistered model')
    if x.shape != (len(y), 3) or v.shape != y.shape:
        raise ValueError('Mismatched fold shapes')
    if len(y) < minimum or not all(np.isfinite(a).all() for a in (x, v, y)):
        raise UnavailableFold('Insufficient finite training observations')
    empty = np.empty(0)
    if model_id in RIDGE_COLUMNS:
        cols = RIDGE_COLUMNS[model_id]
        raw = x[:, cols]
        means = raw.mean(axis=0)
        scales = raw.std(axis=0, ddof=0)
        scales = np.where(scales == 0, 1.0, scales)
        z = (raw - means) / scales
        intercept = float(y.mean())
        slopes = np.linalg.solve(z.T @ z + alpha * np.eye(len(cols)), z.T @ (y - intercept))
        residuals = y - intercept - z @ slopes
        residuals -= residuals.mean()
        return FittedDistribution(model_id, cols, means, scales, slopes, intercept,
                                  residuals, empty, ())
    if model_id == 'unconditional-history':
        return FittedDistribution(model_id, (), empty, empty, empty, 0, y.copy(), empty, ())
    feature = v if model_id == 'volatility-conditioned-history' else x.mean(axis=1)
    bounds = tertile_boundaries(feature)
    groups = tertile_index(feature, bounds)
    bins = tuple(y[groups == i].copy() for i in range(3))
    if min(map(len, bins)) < minimum_bin:
        raise UnavailableFold('Insufficient tertile bin support')
    return FittedDistribution(model_id, (), empty, empty, empty, 0, empty, bounds, bins)


def fit_roster(dimensions: np.ndarray, volatility: np.ndarray, outcomes: np.ndarray,
               specs: list[dict], *, minimum: int = 120, minimum_bin: int = 20
               ) -> dict[str, FittedDistribution | None]:
    """Share fold standardization and residual centering across the fixed roster.

    Each model retains its own Gram matrix, solve and residual distribution.
    Column-major reductions match the scalar fitter's advanced column indexing.
    """
    x, v, y = dimensions, volatility, outcomes
    if x.shape != (len(y), 3) or v.shape != y.shape:
        raise ValueError('Mismatched fold shapes')
    if len(y) < minimum or not all(np.isfinite(a).all() for a in (x, v, y)):
        return {spec['id']: None for spec in specs}
    raw = x[:, (0, 1, 2)]
    means = raw.mean(axis=0)
    scales = raw.std(axis=0, ddof=0)
    scales = np.where(scales == 0, 1.0, scales)
    z = (raw - means) / scales
    intercept = float(y.mean())
    centered = y - intercept
    empty = np.empty(0)
    result = {}
    for spec in specs:
        model_id = spec['id']
        if model_id in RIDGE_COLUMNS:
            cols = RIDGE_COLUMNS[model_id]
            subset = z[:, cols]
            slopes = np.linalg.solve(subset.T @ subset + spec['ridgeAlpha'] * np.eye(len(cols)),
                                     subset.T @ centered)
            residuals = y - intercept - subset @ slopes
            residuals -= residuals.mean()
            result[model_id] = FittedDistribution(model_id, cols, means[list(cols)], scales[list(cols)],
                                                  slopes, intercept, residuals, empty, ())
        else:
            try:
                result[model_id] = fit_distribution(model_id, x, v, y, minimum=minimum,
                                                     minimum_bin=minimum_bin)
            except UnavailableFold:
                result[model_id] = None
    return result
