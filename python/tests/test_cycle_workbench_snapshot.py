from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pytest

from spy_predictor_quant.cycle_workbench_snapshot import verify_growth, price_metrics


def test_growth_requires_matching_release_and_table_extractions():
    release = 'Release Date: August 18, 2026 total IP in July was 1.1 percent above its year-earlier level'
    table = "Release Date: August 18, 2026 July '26 <table><tr><th>Total&nbsp;IP</th><td>100</td><td>1.1</td></tr></table>"
    result = verify_growth(release, table)
    assert result['value'] == 1.1
    assert result['observed_at'] == '2026-07-31T23:59:59+00:00'
    assert result['published_at'] == '2026-08-18T23:59:59+00:00'
    for incorrect in (table.replace('1.1', '1.2'), table.replace('August 18', 'August 19'), table.replace("July '26", "July '25")):
        with pytest.raises(ValueError):
            verify_growth(release, incorrect)


@pytest.fixture
def capture():
    cal = xcals.get_calendar('XNYS')
    days = cal.sessions_in_range('2025-08-01', '2026-09-09')
    rows = [{'date': d.strftime('%Y%m%d'), 'open': str(100+i), 'high': str(102+i),
             'low': str(99+i), 'close': str(101+i), 'volume': '1000'} for i, d in enumerate(days)]
    return {'symbol': 'SPY', 'received_at': '2026-09-09T12:00:00+00:00',
            'whatToShow': 'TRADES', 'barSize': '1 day', 'useRTH': 1, 'bars': rows}


def test_price_metrics_exclude_incomplete_session_and_verify_exact_window(capture):
    result = price_metrics(capture, '2026-09-09T12:01:00+00:00')
    assert result['observed_at'] == '2026-09-08T20:00:00+00:00'
    assert result['sessions'] == 200
    closes = np.array([float(row['close']) for row in capture['bars'][:-1]][-200:])
    assert result['price_to_ma200_ratio'] == pytest.approx(closes[-1]/closes.mean())
    assert result['realized_vol_pct'] == pytest.approx(np.std(np.diff(np.log(closes[-64:])), ddof=1)*np.sqrt(252)*100)
    altered = deepcopy(capture)
    altered['bars'][-1]['close'] = '99999'
    assert price_metrics(altered, '2026-09-09T12:01:00+00:00') == result


@pytest.mark.parametrize('problem', ['gap', 'duplicate', 'stale', 'future-receipt', 'negative'])
def test_unqualified_market_windows_fail_closed(capture, problem):
    if problem == 'gap': del capture['bars'][-30]
    if problem == 'duplicate': capture['bars'].insert(-30, capture['bars'][-30])
    if problem == 'stale': capture['bars'] = capture['bars'][:-3]
    if problem == 'future-receipt': capture['received_at'] = '2026-09-10T00:00:00+00:00'
    if problem == 'negative': capture['bars'][-10]['close'] = '-1'
    with pytest.raises(ValueError):
        price_metrics(capture, '2026-09-09T12:01:00+00:00')
