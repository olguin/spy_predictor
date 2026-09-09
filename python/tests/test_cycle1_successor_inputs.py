from datetime import date, datetime, timedelta, timezone
import math

import pytest

from spy_predictor_quant.cycle1_calendar import xnys_session_close
from spy_predictor_quant.cycle1_successor_inputs import SyntheticVintage, select_vintages, monthly_cash_accrual

START = date(2020, 1, 31)
END = date(2020, 2, 28)
CUTOFF = xnys_session_close(START)


def vintage(value=3.65, published=CUTOFF - timedelta(days=1), revision=0):
    return SyntheticVintage('GS3M', date(2020, 1, 1), published, revision, value)


def test_inclusive_features_and_strict_cash_differ_at_exact_release():
    row = vintage(published=CUTOFF)
    assert select_vintages((row,), 'GS3M', CUTOFF)
    assert not select_vintages((row,), 'GS3M', CUTOFF, strict=True)
    with pytest.raises(ValueError, match='publication-admissible'):
        monthly_cash_accrual((START, END), (row,))


def test_missing_revision_tombstone_does_not_resurrect_same_month():
    missing = vintage(None, CUTOFF - timedelta(hours=1), 1)
    records = (missing, vintage())
    assert select_vintages(records, 'GS3M', CUTOFF)[date(2020, 1, 1)].value is None
    with pytest.raises(ValueError, match='publication-admissible'):
        monthly_cash_accrual((START, END), records)


def test_cash_actual365_and_future_revision_noninterference():
    baseline = monthly_cash_accrual((START, END), (vintage(),))
    assert baseline['cashLogReturn'] == pytest.approx(math.log(1 + .0365 * 28 / 365))
    future = vintage(99, CUTOFF + timedelta(seconds=1), 1)
    assert monthly_cash_accrual((START, END), (future, vintage())) == baseline


def test_internal_gap_is_invalid_even_with_endpoints():
    with pytest.raises(ValueError, match='internal monthly'):
        monthly_cash_accrual((START, date(2020, 3, 31)), (vintage(),))


def test_earlier_observation_can_supply_cash_but_deleted_value_cannot():
    old = SyntheticVintage('GS3M', date(2019, 12, 1), CUTOFF - timedelta(days=30), 0, 1.0)
    missing = vintage(None, CUTOFF - timedelta(hours=1), 1)
    result = monthly_cash_accrual((START, END), (old, vintage(), missing))
    assert result['intervals'][0]['annualPercent'] == 1


def test_ambiguous_revision_and_naive_timestamps_fail():
    with pytest.raises(ValueError, match='Conflicting'):
        select_vintages((vintage(), vintage(8)), 'GS3M', CUTOFF)
    with pytest.raises(ValueError, match='timezones'):
        vintage(published=datetime(2020, 1, 1))


def test_later_period_uses_new_rate_without_rewriting_first_period():
    revision = vintage(7.3, CUTOFF + timedelta(days=2), 1)
    result = monthly_cash_accrual((START, END, date(2020, 3, 31)), (revision, vintage()))
    assert [x['annualPercent'] for x in result['intervals']] == [3.65, 7.3]
