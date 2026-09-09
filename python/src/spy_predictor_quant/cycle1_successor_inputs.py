"""Deterministic synthetic vintage and monthly cash fixtures for the successor.

No archived inputs or random streams are read. These functions do not replace
the stopped experiment's implementation or establish full feature-path parity.
"""
from dataclasses import dataclass
from datetime import date, datetime
import math

from spy_predictor_quant.cycle1_calendar import xnys_session_close
from spy_predictor_quant.cycle1_successor_calendar import month_end as xnys_month_end


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Publication and cutoff require explicit timezones')


@dataclass(frozen=True)
class SyntheticVintage:
    series: str
    observation: date
    published: datetime
    revision: int
    value: float | None
    evidence_tier: str = 'SYNTHETIC_ONLY'

    def __post_init__(self):
        _aware(self.published)
        if self.evidence_tier != 'SYNTHETIC_ONLY':
            raise ValueError('Only synthetic vintage fixtures are accepted')
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError('Revision must be a nonnegative integer')
        if self.value is not None and (isinstance(self.value, bool) or not math.isfinite(self.value)):
            raise ValueError('Vintage value must be finite or a missing tombstone')


def select_vintages(records: tuple[SyntheticVintage, ...], series: str,
                    cutoff: datetime, *, strict: bool = False) -> dict[date, SyntheticVintage]:
    """Retain missing revision tombstones; never resurrect their previous value."""
    _aware(cutoff)
    chosen = {}
    for record in records:
        if record.series != series or record.observation > cutoff.date():
            continue
        admitted = record.published < cutoff if strict else record.published <= cutoff
        if not admitted:
            continue
        old = chosen.get(record.observation)
        key = (record.published, record.revision)
        if old is None or key > (old.published, old.revision):
            chosen[record.observation] = record
        elif key == (old.published, old.revision) and record != old:
            raise ValueError('Conflicting same-time vintage revision')
    return chosen


def monthly_cash_accrual(boundaries: tuple[date, ...], records: tuple[SyntheticVintage, ...]) -> dict:
    """Strict GS3M publication at each XNYS month-close holding-period start."""
    if len(boundaries) < 2 or tuple(sorted(set(boundaries))) != boundaries:
        raise ValueError('Cash boundaries must be unique and chronological')
    for index, point in enumerate(boundaries):
        if point != xnys_month_end(point.year, point.month):
            raise ValueError('Cash boundaries must be scheduled month ends')
        if index:
            old = boundaries[index - 1]
            if point.year * 12 + point.month - (old.year * 12 + old.month) != 1:
                raise ValueError('Missing internal monthly cash boundary')
    intervals = []
    for start, end in zip(boundaries, boundaries[1:]):
        cutoff = xnys_session_close(start)
        selected = select_vintages(records, 'GS3M', cutoff, strict=True)
        valid = [record for record in selected.values() if record.value is not None]
        if not valid:
            raise ValueError('No publication-admissible GS3M cash rate')
        rate = max(valid, key=lambda record: record.observation)
        days = (end - start).days
        growth = 1 + rate.value / 100 * days / 365
        if growth <= 0 or not math.isfinite(growth):
            raise ValueError('Cash growth must be positive and finite')
        intervals.append({'start': start.isoformat(), 'end': end.isoformat(),
                          'actualDays': days, 'annualPercent': rate.value,
                          'observation': rate.observation.isoformat(),
                          'published': rate.published.isoformat(), 'revision': rate.revision,
                          'logReturn': math.log(growth)})
    return {'intervals': intervals, 'cashLogReturn': sum(x['logReturn'] for x in intervals),
            'evidenceTier': 'SYNTHETIC_ONLY', 'realDataApproval': False}
