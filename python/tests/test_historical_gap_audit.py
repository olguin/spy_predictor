from copy import deepcopy

import pytest

from spy_predictor_quant.historical_gap_audit import assess


def fixture():
    bars = [{'date': d, 'open': '100', 'high': '102', 'low': '99', 'close': '101'}
            for d in ('20070629', '20070702', '20070703')]
    payload = {'targetSession': '2007-07-02', 'instrument': 'SPY', 'contract': {'conId': 756733, 'exchange': 'SMART'},
               'whatToShow': 'TRADES', 'useRTH': 1, 'barSize': '1 day', 'bars': bars}
    original = {b['date']: deepcopy(b) for b in bars if b['date'] != '20070702'}
    return payload, original


def test_target_requires_compatible_bracketing_bars():
    payload, original = fixture()
    assert assess(payload, original)['eligibleReplacement']
    payload['bars'] = payload['bars'][1:]
    assert not assess(payload, original)['eligibleReplacement']


def test_venue_close_mismatch_rejects_replacement():
    payload, original = fixture()
    payload['contract']['exchange'] = 'ARCA'
    payload['bars'][0]['close'] = '100.9'
    result = assess(payload, original)
    assert not result['eligibleReplacement']
    assert len(result['closeMismatches']) == 1


def test_missing_target_is_not_filled_from_neighbors():
    payload, original = fixture()
    payload['bars'].pop(1)
    result = assess(payload, original)
    assert not result['targetPresent']
    assert not result['eligibleReplacement']


def test_wrong_contract_or_later_date_rejected():
    payload, original = fixture()
    payload['bars'][-1]['date'] = '20170731'
    with pytest.raises(ValueError, match='bounded'):
        assess(payload, original)
    payload, original = fixture()
    payload['contract']['conId'] = 1
    with pytest.raises(ValueError, match='contract'):
        assess(payload, original)


def test_error_response_remains_failed():
    result = assess({'targetSession': '2004-07-12', 'status': 'REQUEST_FAILED',
                     'exchange': 'SMART', 'error': '162: no data'}, {})
    assert result['status'] == 'REQUEST_FAILED'
    assert not result['eligibleReplacement']
