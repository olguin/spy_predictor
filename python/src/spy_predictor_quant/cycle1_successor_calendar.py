"""Successor-only month boundaries, including the first calendar buffer month."""
from datetime import date

from spy_predictor_quant.cycle1_calendar import _xnys


def month_end(year: int, month: int) -> date:
    calendar = _xnys()
    start = max(date(year, month, 1), calendar.first_session.date())
    following = date(year + (month == 12), month % 12 + 1, 1)
    end = min(following, calendar.last_session.date())
    if start >= following or end < start:
        raise ValueError('Requested month is outside the successor calendar')
    eligible = [session.date() for session in calendar.sessions_in_range(start.isoformat(), end.isoformat())
                if session.date() < following]
    if not eligible:
        raise ValueError('No scheduled sessions in requested month')
    return eligible[-1]
