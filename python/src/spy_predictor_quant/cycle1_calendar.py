"""Exact XNYS session boundaries used by the frozen Cycle 1 protocol."""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache

import exchange_calendars


@lru_cache(maxsize=1)
def _xnys():
    # The library's default schedule is a moving window around today.  Cycle 1
    # instead needs the entire frozen ETF history through its 2026 cutoff.
    # Keep a buffer around that range so month-boundary queries never equal
    # the calendar object's first or last supported date.
    return exchange_calendars.get_calendar(
        "XNYS", start="1990-01-01", end="2031-01-01"
    )


def xnys_session_close(session_date: date) -> datetime:
    calendar = _xnys()
    if not is_xnys_session(session_date):
        raise ValueError(f"{session_date} is not a scheduled XNYS session")
    return calendar.session_close(session_date.isoformat()).to_pydatetime()


def is_xnys_session(session_date: date) -> bool:
    return bool(_xnys().is_session(session_date.isoformat()))


def xnys_month_end(year: int, month: int) -> date:
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    sessions = _xnys().sessions_in_range(start.isoformat(), end.isoformat())
    eligible = [value.date() for value in sessions if value.date() < end]
    if not eligible:
        raise ValueError(f"No XNYS sessions in {year:04d}-{month:02d}")
    return eligible[-1]


def xnys_next_session_open(session_date: date) -> tuple[date, datetime]:
    calendar = _xnys()
    if not calendar.is_session(session_date.isoformat()):
        raise ValueError(f"{session_date} is not a scheduled XNYS session")
    following = calendar.next_session(session_date.isoformat())
    return following.date(), calendar.session_open(following).to_pydatetime()
