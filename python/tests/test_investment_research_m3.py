"""M3 safety/engineering fixtures; never M4 usefulness or performance evidence."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from threading import Thread
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import exchange_calendars as xcals
import pytest

from spy_predictor_quant.investment_research.controller import Controller
from spy_predictor_quant.investment_research.monitor import project, artifact, handler
from spy_predictor_quant.investment_research.observations import schedule, observe, timestamp
from spy_predictor_quant.investment_research.publication import publish, read_publication, feedback, review, condition_state, market_status, qualify_quote
from spy_predictor_quant.investment_research.store import Store
from test_investment_research import response, findings
from test_investment_research_m2 import mandate, source, FiveSymbolWorker, SYMBOLS


def m3_mandate():
    m = mandate()
    m['schema_version'] = 'investment-research-mandate-v4'
    event_source = source('m3-events', [], text='Synthetic global policy source; no new event.')
    event_source['kind'] = 'policy'
    m['sources'].append(event_source)
    now = datetime.now(timezone.utc)
    cal = xcals.get_calendar('XNYS')
    sessions = [s for s in cal.sessions if cal.session_close(s).to_pydatetime() < now][-210:]
    for symbol in [*SYMBOLS, 'SPY', 'XLK']:
        payload = {'symbol': symbol, 'bars': [{'t': cal.session_open(s).isoformat(), 'o': 100, 'h': 101, 'l': 99, 'c': 100, 'v': 10000} for s in sessions]}
        row = source('price-'+symbol, [symbol], text=json.dumps(payload), adapter='alpaca_daily')
        row.update(kind='market', share_basis='split_adjusted', captured_at=now.isoformat(), data_end=now.isoformat(), feed='synthetic')
        m['sources'].append(row)
    m['seed_source_ids'] = [s['source_id'] for s in m['sources']]
    m['publication_policy'] = {'version': 'investment-research-publication-policy-v1',
        'refresh_source_ids': ['price-'+s for s in [*SYMBOLS, 'SPY', 'XLK']] + ['ANET', 'm3-events'],
        'material_price_move_pct': 3, 'maximum_refresh_age_seconds': 120, 'maximum_quote_age_seconds': 60}
    return m


def draft(path):
    c = Controller(path, FiveSymbolWorker())
    c.create(m3_mandate())
    assert c.run()['status'] == 'DRAFT'
    return c


def test_telemetry_and_replay_reconcile_without_lock(tmp_path):
    c = draft(tmp_path)
    before = (tmp_path/'state.json').read_bytes()
    with c.store.lock():
        snap = project(c.store)
    assert snap['receipts_reconcile'] and not snap['usage_unknown']
    assert snap['research_question'] == c.store.load()['mandate']['objective']
    assert snap['symbols'] == SYMBOLS and snap['horizon_sessions']
    assert [e['sequence'] for e in snap['events']] == list(range(1, snap['sequence']+1))
    assert not project(c.store, after=snap['sequence'])['events']
    assert any(e['kind'] == 'reused answer' for e in snap['edges'])
    assert snap['omissions'][0]['role'] == 'commodities'
    assert all(t['completed_at'] and t['duration_seconds'] >= 0 for t in snap['tasks'])
    assert all(a['worker_deadline_at'] and a['completed_at'] for t in snap['tasks'] for a in t['attempts'])
    assert before == (tmp_path/'state.json').read_bytes()
    assert project(c.store)['elapsed_seconds'] == snap['elapsed_seconds']


@pytest.mark.parametrize('error', [TimeoutError, KeyboardInterrupt])
def test_terminal_failure_frozen_once_and_not_retried(tmp_path, error):
    calls = []
    def worker(*args):
        calls.append(1)
        raise error()
    c = Controller(tmp_path, worker); c.create(m3_mandate())
    state = c.run()
    assert state['completed_at'] and state['usage_unknown']
    assert state['attempts'][0]['completed_at'] and state['attempts'][0]['failure_type'] == error.__name__
    assert all(t['completed_at'] for t in state['tasks'])
    assert len(c.run()['attempts']) == 1 and len(calls) == 1
    snap = project(c.store)
    assert snap['unknown_attempts'] == ['attempt-1']


def test_crash_last_observation_and_two_active_slots(tmp_path):
    c = Controller(tmp_path); state = c.create(m3_mandate())
    for index, task in enumerate(state['tasks']):
        task.update(status='RUNNING', started_at=state['started_at'])
        state['attempts'].append({'attempt_id': 'attempt-'+str(index+1), 'task_id': task['task_id'], 'status': 'STARTED',
            'started_at': state['started_at'], 'worker_deadline_at': state['started_at']})
    state['status'] = 'RUNNING'; c.store.save(state)
    snap = project(c.store)
    assert snap['stale'] and len(snap['unknown_attempts']) == 2
    assert all(t['timing_uncertain'] for t in snap['tasks'])
    state = c.run()
    assert state['terminal_time_uncertain'] and all(a['completed_at'] for a in state['attempts'])
    assert all(a['status'] == 'INTERRUPTED' for a in state['attempts'])


def test_publication_freezes_bundle_feedback_review_and_resume(tmp_path):
    c = draft(tmp_path/'run'); ledger = tmp_path/'ledger'
    old_product = (c.store.root/'products'/f"{c.store.load()['product_id']}.json").read_bytes()
    result = publish(c.store, ledger)
    identity = result['publication_id']
    frozen = read_publication(ledger, identity)
    assert frozen == result and timestamp(result['published_at']) >= timestamp(result['refresh']['completed_at'])
    assert result['product']['market_status']['status'] in {'OPEN', 'CLOSED'}
    assert result['product']['immediate_entry_quote'].startswith('UNAVAILABLE')
    assert timestamp(result['observation_contract']['origin_at']) > timestamp(result['published_at'])
    assert publish(c.store, ledger)['publication_id'] == identity
    assert c.run()['status'] == 'PUBLISHED'
    assert old_product == (c.store.root/'products'/f"{result['draft_product_id']}.json").read_bytes()
    frozen_store = Store(ledger/'publications'/identity)
    assert project(frozen_store)['usage'] == result['usage']
    assert project(frozen_store)['receipts_reconcile']
    f = feedback(ledger, identity, {'category':'omission','symbol':'QQQ','text':'Explain missing holdings'})
    a = review(ledger, identity, {'decision':'needs_research','symbol':'QQQ','reason':'New sponsor holdings'})
    b = review(ledger, identity, {'decision':'retain','symbol':'QQQ','reason':'No new evidence'})
    assert a['review_id'] != b['review_id'] and f['feedback_id']
    assert read_publication(ledger, identity) == frozen
    c2 = draft(tmp_path/'review-run'); child = publish(c2.store, ledger, parent_publication_id=identity)
    assert child['parent_publication_id'] == identity and child['publication_id'] != identity
    assert read_publication(ledger, identity) == frozen


@pytest.mark.parametrize('change', ['price', 'news', 'failure'])
def test_material_refresh_withdraws_only_affected_instruments(tmp_path, monkeypatch, change):
    from spy_predictor_quant.investment_research.broker import Broker
    c = draft(tmp_path/'run')
    original = Broker.fetch
    def fetch(self, s):
        if change == 'price' and s['source_id'] == 'price-NVDA':
            data = json.loads(s['fixture_text']); data['bars'][-1].update(c=110, h=111)
            return json.dumps(data).encode()
        if change == 'news' and s['source_id'] == 'ANET':
            return b'Material new issuer event during research'
        if change == 'failure' and s['source_id'] == 'ANET':
            raise OSError('Source unavailable')
        return original(self, s)
    monkeypatch.setattr(Broker, 'fetch', fetch)
    result = publish(c.store, tmp_path/'ledger')
    affected = 'NVDA' if change == 'price' else 'ANET'
    rows = {r['symbol']:r for r in result['product']['findings']['instruments']}
    assert rows[affected]['assessment'] == 'insufficient_evidence' and not rows[affected]['claim_ids']
    assert rows['QQQ']['assessment'] == 'watch'
    assert affected in result['refresh']['invalidation']['symbols']
    assert result['product']['invalidated_original_findings']


def test_no_backdating_no_refresh_retry_or_old_mandate_publication(tmp_path):
    c = Controller(tmp_path/'m2', FiveSymbolWorker()); c.create(mandate()); c.run()
    with pytest.raises(ValueError, match='pre-registered'):
        publish(c.store, tmp_path/'ledger')
    c = draft(tmp_path/'m3'); state = c.store.load()
    state['started_at'] = (datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(); c.store.save(state)
    with pytest.raises(RuntimeError, match='wall_seconds'):
        publish(c.store, tmp_path/'ledger')
    with pytest.raises(ValueError):
        publish(c.store, tmp_path/'ledger')
    assert not list((tmp_path/'ledger').glob('publications/*'))


def test_conditions_closure_stale_basis_expiry_and_no_intraday_fill():
    at = timestamp('2026-09-20T16:00:00+00:00')
    c = {'kind':'completed_close','symbol':'NVDA','operator':'above','threshold_decimal':'100',
         'price_basis':'split_adjusted','expires_at':'2026-09-22T00:00:00+00:00','evidence_ids':[]}
    e = {'data':{'price_date':'2026-09-18','latest_close':101,'adjustment':'split_adjusted'}}
    assert market_status(at)['status'] == 'CLOSED'
    assert condition_state(c,e,at)['status'] == 'MET'
    e['data']['price_date'] = '2026-09-17'
    assert condition_state(c,e,at)['status'] == 'UNAVAILABLE'
    e['data'].update(price_date='2026-09-18', adjustment='raw')
    assert condition_state(c,e,at)['status'] == 'UNAVAILABLE'
    c['expires_at'] = at.isoformat()
    assert condition_state(c,e,at)['status'] == 'EXPIRED'


@pytest.mark.parametrize('published,expected', [
    ('2026-09-18T13:29:59+00:00','2026-09-18'),
    ('2026-09-18T13:30:00+00:00','2026-09-21'),
    ('2026-09-18T17:00:00+00:00','2026-09-21'),
    ('2026-09-20T17:00:00+00:00','2026-09-21'),
    ('2026-11-26T17:00:00+00:00','2026-11-27'),
])
def test_origin_strictly_after_publication_with_holidays_and_half_days(published,expected):
    c = schedule(published, [{'symbol':'NVDA','benchmark':'SPY','sector_benchmark':'XLK'}], [1,5,21,63])
    assert c['origin_session'] == expected and c['targets']['1']['session'] == expected
    assert timestamp(c['origin_at']) > timestamp(published)
    if expected == '2026-11-27':
        assert timestamp(c['targets']['1']['at']).hour == 18


def observation_data(c, symbol, origin='100', target='110', events=None):
    return {'symbol':symbol,'currency':'USD','return_basis':'price_return','cash_dividends':'excluded','share_basis':'raw',
        'origin':{'at':c['origin_at'],'available_at':c['origin_at'],'price_decimal':origin,'source_hash':'a'*64,'feed':'synthetic','session':'regular'},
        'target':{'at':c['targets']['5']['at'],'available_at':c['targets']['5']['at'],'price_decimal':target,'source_hash':'b'*64,'feed':'synthetic','session':'regular'},
        'corporate_actions':{'status':'complete','from':c['origin_at'],'through':c['targets']['5']['at'],'source_hash':'c'*64,'events':events or []}}


def test_split_adjustment_paired_returns_and_immutable_pending_origin():
    c = schedule('2026-09-20T16:00:00+00:00',[{'symbol':'NVDA','benchmark':'SPY','sector_benchmark':'XLK'}],[5])
    events = [{'event_id':'split1','kind':'split','effective_at':'2026-09-23T13:30:00+00:00','new_shares_per_old_share':'4'}]
    data = observation_data(c,'NVDA','100','27.5',events)
    benchmarks = {s:observation_data(c,s) for s in ('SPY','XLK')}
    result = observe(c,'NVDA',5,data,benchmarks,now=timestamp('2026-09-26T00:00:00+00:00'))
    assert result['status'] == 'OBSERVED', result
    assert result['instrument']['return_pct_decimal'] == '10.0'
    assert result['instrument']['origin_on_target_share_basis_decimal'] == '25'
    assert set(result['excess_percentage_points'].values()) == {'0.0'}
    assert c['origin_price'] is None
    assert observe(c,'NVDA',5,data,benchmarks,now=timestamp(c['origin_at']))['status'] == 'PENDING'


@pytest.mark.parametrize('defect',['basis','coverage','timestamp','feed','dividends','duplicate','merger'])
def test_incompatible_outcomes_retained_unscorable(defect):
    c = schedule('2026-09-20T16:00:00+00:00',[{'symbol':'NVDA','benchmark':'SPY','sector_benchmark':'XLK'}],[5])
    data = observation_data(c,'NVDA'); benchmarks = {s:observation_data(c,s) for s in ('SPY','XLK')}
    if defect == 'basis': benchmarks['SPY']['return_basis'] = 'total_return'
    if defect == 'coverage': data['corporate_actions']['status'] = 'unknown'
    if defect == 'timestamp': data['origin']['at'] = c['published_at']
    if defect == 'feed': benchmarks['SPY']['origin']['feed'] = 'other'
    if defect == 'dividends': data['cash_dividends'] = 'included'
    if defect == 'duplicate': data['corporate_actions']['events'] = [{'event_id':'same','kind':'split','effective_at':c['origin_at'],'new_shares_per_old_share':'2'}]*2
    if defect == 'merger': data['corporate_actions']['events'] = [{'event_id':'merger','kind':'merger'}]
    result = observe(c,'NVDA',5,data,benchmarks,now=timestamp('2026-09-26T00:00:00+00:00'))
    assert result['status'] == 'UNSCORABLE' and result['reason'] and 'instrument' not in result


def test_monitor_http_readonly_paths_credentials_and_injection(tmp_path):
    from http.server import ThreadingHTTPServer
    c = draft(tmp_path)
    state = c.store.load(); state['tasks'][0]['question'] = '<script>alert("x")</script>'; c.store.save(state)
    server = ThreadingHTTPServer(('127.0.0.1',0), handler(c.store)); thread = Thread(target=server.serve_forever,daemon=True);thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base+'/api/snapshot') as r:
            assert r.headers['Cache-Control'] == 'no-store'
            assert json.load(r)['tasks'][0]['question'].startswith('<script>')
        with urlopen(base+'/monitor.js') as r:
            script = r.read().decode(); assert '.innerHTML' not in script and '.textContent' in script
        request_id = state['attempts'][0]['request_id']
        assert 'runtime' not in artifact(c.store,'requests',request_id)
        for path in ['/api/artifact/code/'+'a'*64,'/../.env','/api/artifact/evidence/../state.json']:
            with pytest.raises(HTTPError): urlopen(base+path)
        with pytest.raises(HTTPError): urlopen(Request(base+'/api/snapshot',data=b'{}',method='POST'))
        with pytest.raises(HTTPError): urlopen(Request(base+'/api/snapshot',headers={'Origin':'https://evil.example'}))
    finally:
        server.shutdown();server.server_close();thread.join()


def test_published_bundle_detects_tamper(tmp_path):
    c = draft(tmp_path/'run'); ledger=tmp_path/'ledger'; record=publish(c.store,ledger)
    (ledger/'publications'/record['publication_id']/'report.md').write_text('altered')
    with pytest.raises(ValueError,match='integrity'):
        read_publication(ledger,record['publication_id'])


def test_quote_freshness_rejects_daily_close_delay_partial_venue_and_closure():
    at = timestamp('2026-09-18T15:00:00+00:00')
    quote = {'kind':'quote','observed_at':at.isoformat(),'delayed':False,'coverage':'consolidated',
             'bid_decimal':'100','ask_decimal':'100.05'}
    assert qualify_quote(quote,at,60)['status'] == 'FRESH_REFERENCE'
    assert qualify_quote({'kind':'daily_close'},at,60)['status'] == 'UNAVAILABLE'
    assert qualify_quote(quote,at+timedelta(seconds=61),60)['status'] == 'STALE'
    assert qualify_quote({**quote,'coverage':'iex'},at,60)['status'] == 'UNAVAILABLE'
    assert qualify_quote({**quote,'delayed':True},at,60)['status'] == 'UNAVAILABLE'
    closed = timestamp('2026-09-20T15:00:00+00:00')
    assert qualify_quote({**quote,'observed_at':closed.isoformat()},closed,60)['status'] == 'MARKET_CLOSED'


def test_monitor_keeps_rejected_submission_once_with_its_receipt(tmp_path):
    worker = FiveSymbolWorker()
    def reject_once(request,runtime,timeout):
        result = worker(request,runtime,timeout)
        if len(worker.requests) == 1:
            result['action']['arguments']['assessment'] = 'INVALID'
        return result
    c = Controller(tmp_path,reject_once);c.create(m3_mandate());state=c.run()
    assert state['status'] == 'DRAFT'
    snap=project(c.store)
    attempts=[a for t in snap['tasks'] for a in t['attempts']]
    rejected=[a for a in attempts if a['status']=='REJECTED_VALIDATION']
    assert len(rejected)==1 and rejected[0]['completed_at'] and rejected[0]['receipt']
    assert snap['receipts_reconcile']
