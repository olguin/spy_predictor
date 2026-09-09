"""Deterministic daily-path checks for the proposed successor, with no generator.

Inputs are synthetic total-return levels, not raw prices. Their construction
from corporate actions and the macro/cash pipeline remain separate prerequisites.
The annual equity leg returned here is deliberately not called an excess target.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from spy_predictor_quant.cycle1_calendar import (
    _xnys, xnys_month_end, xnys_next_session_open,
)


@dataclass(frozen=True)
class SyntheticSessionLevels:
    instrument: str
    sessions: tuple[date, ...]
    open_total_return_levels: tuple[float, ...]
    close_total_return_levels: tuple[float, ...]
    evidence_tier: str = 'SYNTHETIC_ONLY'
    units: str = 'TOTAL_RETURN_LEVELS'


def validate_session_levels(tape: SyntheticSessionLevels) -> None:
    if tape.evidence_tier != 'SYNTHETIC_ONLY' or tape.instrument not in ('SPY', 'QQQ'):
        raise ValueError('Successor fixtures require synthetic SPY or QQQ')
    if tape.units != 'TOTAL_RETURN_LEVELS':
        raise ValueError('Raw prices cannot substitute for total-return levels')
    if not tape.sessions or len(tape.sessions) != len(set(tape.sessions)):
        raise ValueError('Session inventory must be nonempty and unique')
    if tuple(sorted(tape.sessions)) != tape.sessions:
        raise ValueError('Session inventory must be chronological')
    expected = tuple(value.date() for value in _xnys().sessions_in_range(
        tape.sessions[0].isoformat(), tape.sessions[-1].isoformat()))
    if tape.sessions != expected:
        raise ValueError('Incomplete scheduled XNYS session inventory')
    for levels in (tape.open_total_return_levels, tape.close_total_return_levels):
        if len(levels) != len(tape.sessions):
            raise ValueError('Every session requires both open and close levels')
        if any(not math.isfinite(value) or value <= 0 for value in levels):
            raise ValueError('Total-return levels must be positive and finite')


def _month_end_after(origin: date, months: int) -> date:
    ordinal = origin.year * 12 + origin.month - 1 + months
    return xnys_month_end(ordinal // 12, ordinal % 12 + 1)


def derive_market_evidence(tape: SyntheticSessionLevels, origins: tuple[date, ...]) -> list[dict]:
    """Use full daily paths for drawdown and distinct open intervals for policy.

    Missing internal sessions or required endpoints are invalid, not imputable.
    The fixed origin calendar must be supplied explicitly by the future caller.
    Cash publication, feature availability and raw action units are not verified
    by this function and no complete primary/policy qualification is returned.
    """
    validate_session_levels(tape)
    if not origins or tuple(sorted(set(origins))) != origins:
        raise ValueError('Origin calendar must be explicit, unique and chronological')
    lookup = {session: index for index, session in enumerate(tape.sessions)}
    output = []
    for origin in origins:
        if xnys_month_end(origin.year, origin.month) != origin:
            raise ValueError('Origin is not the final scheduled monthly session')
        end = _month_end_after(origin, 12)
        next_origin = _month_end_after(origin, 1)
        entry, entry_time = xnys_next_session_open(origin)
        exit_session, exit_time = xnys_next_session_open(next_origin)
        if any(session not in lookup for session in (origin, end, entry, exit_session)):
            raise ValueError('Required target or execution endpoint is absent')
        first, last = lookup[origin], lookup[end]
        closes = tape.close_total_return_levels[first:last + 1]
        peak = closes[0]
        drawdown = 0.0
        for level in closes:
            peak = max(peak, level)
            drawdown = min(drawdown, level / peak - 1)
        output.append({
            'instrument': tape.instrument,
            'origin': origin.isoformat(), 'targetEnd': end.isoformat(),
            'scheduledDailyCloses': len(closes),
            'annualEquityLogReturn': math.log(closes[-1] / closes[0]),
            'maximumDailyCloseDrawdown': drawdown,
            'drawdownEvent': drawdown <= -0.2,
            'executionStart': entry_time.isoformat(),
            'executionEnd': exit_time.isoformat(),
            'monthlyExecutionEquityReturn': (
                tape.open_total_return_levels[lookup[exit_session]]
                / tape.open_total_return_levels[lookup[entry]] - 1
            ),
            'evidenceTier': 'SYNTHETIC_ONLY',
            'cashAccrualIncluded': False,
            'completePrimaryTarget': False,
            'realDataApproval': False,
        })
    return output
