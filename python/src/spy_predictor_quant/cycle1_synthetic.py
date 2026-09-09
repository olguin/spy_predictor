"""Monthly paths with overlapping labels; no market archive reader exists here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SyntheticPath:
    months: np.ndarray
    dimensions: np.ndarray
    volatility: np.ndarray
    outcomes: np.ndarray
    monthly_returns: np.ndarray
    missing: np.ndarray
    instrument: str
    evidence_tier: str = 'SYNTHETIC_ONLY'


def generate_paths(design: dict[str, Any], scenario_index: int, replication: int,
                   *, stream: str = 'development') -> dict[str, SyntheticPath]:
    # Locked streams have no callable path until the complete audit release exists.
    if stream != 'development':
        raise RuntimeError('Locked validation stream is not released')
    if not 0 <= replication < design['streams']['developmentReplicationsPerScenario']:
        raise ValueError('Development replication budget exceeded')
    p = design['scenarios'][scenario_index]
    entropy = design['streams']['developmentEntropy']
    rng = [np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [entropy, scenario_index, replication, sub]))) for sub in range(6)]
    first = np.datetime64(design['calendar']['warmupStart'], 'M')
    last = np.datetime64(design['calendar']['pathEnd'], 'M')
    months = np.arange(first, last + np.timedelta64(1, 'M'), dtype='datetime64[M]')
    n = len(months)
    z = np.empty((n, 3)); z[0] = rng[0].normal(size=3)
    h = np.zeros(n)
    for t in range(1, n):
        z[t] = p['predictorPersistence'] * z[t-1] + np.sqrt(1-p['predictorPersistence']**2) * rng[0].normal(size=3)
        h[t] = p['volatilityPersistence'] * h[t-1] + p['volatilityInnovationSd'] * rng[1].normal()
    dimensions = np.tanh(z)
    signal = {'none': np.zeros(n), 'cycle': dimensions.mean(axis=1),
              'position-direction': dimensions[:, [0, 2]].mean(axis=1),
              'stress': dimensions[:, 1]}[p['signal']]
    regime = np.where(months >= np.datetime64(p['breakMonth'], 'M'), p['afterBreakMultiplier'], 1)
    mu = 0.04 / 12 + p['annualLocationAmplitude'] / 12 * signal * regime
    sigma = 0.15 / np.sqrt(12) * np.exp(h + p['logScaleLoading'] * signal)
    df = p['studentDegreesOfFreedom']
    eps = rng[2].standard_t(df, n) / np.sqrt(df / (df - 2))
    other = rng[3].standard_t(df, n) / np.sqrt(df / (df - 2))
    crashes = (rng[4].random(n) < p['crashProbability']) * p['crashLogReturn']
    missing = rng[5].random(n) < p['missingProbability']
    result = {}
    for instrument, shock, multiplier in [('SPY', eps, 1.0), ('QQQ', 0.8 * eps + 0.6 * other, 1.2)]:
        returns = np.zeros(n)
        returns[1:] = multiplier * (mu[:-1] + sigma[:-1] * shock[1:]) + crashes[1:]
        outcomes = np.full(n, np.nan)
        # Label at origin t contains returns realized in months t+1 ... t+12.
        sums = np.concatenate([[0.0], np.cumsum(returns)])
        outcomes[:-12] = sums[13:] - sums[1:-12]
        vol = np.full(n, np.nan)
        for t in range(2, n):
            vol[t] = np.sqrt(12) * np.std(returns[t-2:t+1], ddof=0)
        result[instrument] = SyntheticPath(months.copy(), dimensions.copy(), vol, outcomes,
                                            returns, missing.copy(), instrument)
    return result
