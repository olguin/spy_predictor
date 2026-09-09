"""Exact finite-state checks of an annual incremental-information null.

This is deterministic algebra on supplied transition tables, not a simulator or
a release of Cycle 1 random streams. Rewards are integer units of monthly excess
log return; their sum is the annual target. These fixtures do not establish that
the proposed continuous, price-derived generator has the same conditional law.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations


@dataclass(frozen=True)
class Transition:
    next_state: str
    excess_reward: int
    probability: Fraction


@dataclass(frozen=True)
class MarkedKernel:
    baseline_state: dict[str, str]
    transitions: dict[str, tuple[Transition, ...]]


def validate_kernel(kernel: MarkedKernel) -> None:
    if not kernel.baseline_state or set(kernel.baseline_state) != set(kernel.transitions):
        raise ValueError('Every full state needs a baseline group and transition row')
    if len(set(kernel.baseline_state.values())) == len(kernel.baseline_state):
        raise ValueError('A null comparison requires full states sharing baseline information')
    for row in kernel.transitions.values():
        if not row or sum((t.probability for t in row), Fraction()) != 1:
            raise ValueError('Transition probabilities must sum exactly to one')
        for transition in row:
            if transition.next_state not in kernel.baseline_state:
                raise ValueError('Unknown transition destination')
            if type(transition.excess_reward) is not int:
                raise ValueError('Rewards require explicit integer log-return units')
            if not isinstance(transition.probability, Fraction) or transition.probability < 0:
                raise ValueError('Probabilities must be nonnegative exact fractions')


def _grouped_row(kernel: MarkedKernel, state: str) -> dict:
    output = defaultdict(Fraction)
    for t in kernel.transitions[state]:
        if t.probability:
            output[(kernel.baseline_state[t.next_state], t.excess_reward)] += t.probability
    return dict(output)


def _law(kernel: MarkedKernel, start: str, horizon: int) -> dict[int, Fraction]:
    current = {(start, 0): Fraction(1)}
    for _ in range(horizon):
        following = defaultdict(Fraction)
        for (state, reward), mass in current.items():
            for transition in kernel.transitions[state]:
                if transition.probability:
                    following[(transition.next_state, reward + transition.excess_reward)] += mass * transition.probability
        current = following
    result = defaultdict(Fraction)
    for (_, reward), probability in current.items():
        result[reward] += probability
    return dict(sorted(result.items()))


def _total_variation(left: dict, right: dict) -> Fraction:
    return sum((abs(left.get(key, Fraction()) - right.get(key, Fraction()))
                for key in left.keys() | right.keys()), Fraction()) / 2


def audit_conditional_law(kernel: MarkedKernel, horizon: int = 12) -> dict:
    """Check the full reward law, and a sufficient all-horizon kernel condition.

    For full states (baseline, extra), equality of the JOINT next-baseline and
    reward distribution within each baseline group implies equality at every
    horizon by induction. Matching just the next reward marginal is insufficient.
    """
    validate_kernel(kernel)
    if type(horizon) is not int or not 1 <= horizon <= 120:
        raise ValueError('Horizon must be an integer from 1 through 120')
    states = sorted(kernel.baseline_state)
    laws = {state: _law(kernel, state, horizon) for state in states}
    pairs = []
    for left, right in combinations(states, 2):
        if kernel.baseline_state[left] != kernel.baseline_state[right]:
            continue
        distance = _total_variation(laws[left], laws[right])
        joint_distance = _total_variation(_grouped_row(kernel, left), _grouped_row(kernel, right))
        pairs.append({'states': [left, right], 'annualTotalVariation': str(distance),
                      'markedKernelTotalVariation': str(joint_distance),
                      'equalTargetLaw': distance == 0, 'equalMarkedKernel': joint_distance == 0})
    return {
        'status': 'EXACT_FINITE_STATE_INFORMATION_NULL' if all(p['equalTargetLaw'] for p in pairs)
                  else 'EXTRA_STATE_CONTAINS_TARGET_INFORMATION',
        'horizonMonths': horizon, 'statePairs': pairs,
        'sufficientAllHorizonCondition': all(p['equalMarkedKernel'] for p in pairs),
        'targetLaws': {state: {str(reward): str(mass) for reward, mass in law.items()}
                       for state, law in laws.items()},
        'scope': 'supplied-finite-state-table-only;not-full-price-feature-generator',
        'falseQualificationRateEstimated': False,
        'developmentDraws': 0, 'lockedValidationDraws': 0, 'realDataApproval': False,
    }


def partial_null_fixture() -> MarkedKernel:
    """Predictable baseline, persistent states, but extra state adds no law info."""
    baseline = {f'{b}:{extra}': b for b in ('low', 'high') for extra in (0, 1)}
    rows = {}
    for state, group in baseline.items():
        extra = int(state[-1])
        next_group = 'high' if group == 'low' else 'low'
        positive = Fraction(1, 4) if group == 'low' else Fraction(3, 4)
        rows[state] = tuple(
            Transition(f'{b}:{s}', reward, bp * sp * rp)
            for b, bp in ((group, Fraction(3, 4)), (next_group, Fraction(1, 4)))
            for s, sp in ((extra, Fraction(3, 4)), (1 - extra, Fraction(1, 4)))
            for reward, rp in ((1, positive), (-1, 1 - positive))
        )
    return MarkedKernel(baseline, rows)


def feedback_counterexample() -> MarkedKernel:
    # A and B have the same one-step reward (zero). Their extra state determines
    # whether the next baseline is permanently profitable or unprofitable.
    return MarkedKernel(
        {'A': 'neutral', 'B': 'neutral', 'UP': 'up', 'DOWN': 'down'},
        {'A': (Transition('UP', 0, Fraction(1)),),
         'B': (Transition('DOWN', 0, Fraction(1)),),
         'UP': (Transition('UP', 1, Fraction(1)),),
         'DOWN': (Transition('DOWN', -1, Fraction(1)),)},
    )


def fixture_report() -> dict:
    counterexample = feedback_counterexample()
    return {
        'schemaVersion': 'cycle1-null-law-fixtures-v1',
        'purpose': 'deterministic-pre-freeze-algebra;no-scenario-performance',
        'validPartialNull': audit_conditional_law(partial_null_fixture()),
        'feedbackOneMonth': audit_conditional_law(counterexample, 1),
        'feedbackTwelveMonths': audit_conditional_law(counterexample, 12),
        'successorNullEstablished': False,
        'nextRequirement': 'Prove the actual full-path generator obeys the same baseline-grouped marked kernel or derive its twelve-month conditional laws directly.',
    }


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(fixture_report(), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
