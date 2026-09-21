"""Launch boundaries and report authority; no real provider calls."""
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

import pytest

from spy_predictor_quant.investment_research.workspace import Workspace, QUESTION, handler, mandate_for
from spy_predictor_quant.investment_research.publication import publish
from test_investment_research_m3 import draft


def test_publisher_main_region_preserves_body_and_excludes_navigation():
    from spy_predictor_quant.investment_research.broker import Excerpt
    parser = Excerpt()
    parser.feed('<header>Navigation</header><main><h1>Earnings</h1><p>Revenue 100</p><div hidden>Hidden 999</div></main><footer>Contacts</footer>')
    assert parser.main_parts == ['Earnings', 'Revenue 100']
    assert parser.parts == ['Navigation', 'Earnings', 'Revenue 100', 'Contacts']


def test_registered_scope_fresh_window_and_budget():
    now = datetime(2026, 9, 21, tzinfo=timezone.utc)
    mandate = mandate_for(QUESTION, now=now)
    assert [s['symbol'] for s in mandate['watchlist']] == ['NVDA', 'MU', 'QQQ']
    assert [s['benchmark'] for s in mandate['watchlist']] == ['QQQ', 'QQQ', 'SPY']
    assert mandate['horizon_sessions'] == [63]
    assert mandate['budgets']['model_calls'] == 40 and mandate['budgets']['wall_seconds'] == 1200
    assert '2026-09-20T23' in next(s['url'] for s in mandate['sources'] if s['source_id'] == 'price-NVDA')
    assert not any(set(s['symbols']) & {'ANET', 'META', 'XLC'} for s in mandate['sources'])
    assert set(mandate['publication_policy']['refresh_source_ids']) <= set(mandate['seed_source_ids'])


def test_launch_idempotency_single_active_and_restart_no_retry(tmp_path):
    calls = []
    w = Workspace(tmp_path, tmp_path/'ledger', launch=lambda *args: calls.append(args))
    identity = str(uuid.uuid4())
    first = w.start(identity, QUESTION)
    assert w.start(identity, QUESTION)['id'] == first['id']
    assert calls == [(identity, 'research')]
    with pytest.raises(ValueError, match='different question'):
        w.start(identity, QUESTION+' More.')
    with pytest.raises(ValueError, match='already running'):
        w.start(str(uuid.uuid4()), QUESTION)
    restarted = Workspace(tmp_path, tmp_path/'ledger', launch=lambda *args: calls.append(args))
    assert restarted.summary(identity)['interrupted']
    restarted.start(identity, QUESTION)
    assert len(calls) == 1
    with pytest.raises(ValueError):
        w.directory('../../config')


def test_mutating_routes_require_origin_token_and_fixed_payload(tmp_path):
    calls = []
    w = Workspace(tmp_path, tmp_path/'ledger', launch=lambda *args: calls.append(args))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler(w))
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    value = {'id': str(uuid.uuid4()), 'question': QUESTION}
    try:
        bootstrap = json.load(urlopen(base+'/api/workspace'))
        headers = {'Content-Type': 'application/json', 'Origin': base, 'X-Research-Token': bootstrap['token']}
        for wrong in ({}, headers | {'Origin': 'https://example.com'}, headers | {'X-Research-Token': 'bad'}):
            with pytest.raises(HTTPError) as error:
                urlopen(Request(base+'/api/runs', data=json.dumps(value).encode(), headers=wrong))
            assert error.value.code == 403
        with pytest.raises(HTTPError) as error:
            urlopen(Request(base+'/api/runs', data=json.dumps(value | {'model': 'other'}).encode(), headers=headers))
        assert error.value.code == 400
        for _ in range(2):
            assert urlopen(Request(base+'/api/runs', data=json.dumps(value).encode(), headers=headers)).status == 202
        assert len(calls) == 1
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_reports_use_verified_publication_not_stale_draft(tmp_path, monkeypatch):
    from spy_predictor_quant.investment_research.broker import Broker
    calls = []
    w = Workspace(tmp_path/'workspace', tmp_path/'ledger', launch=lambda *args: calls.append(args))
    identity = str(uuid.uuid4())
    w.start(identity, QUESTION)
    c = draft(w.directory(identity)/'run')
    assert w.report(identity)['product']['status'] == 'DRAFT'
    original = Broker.fetch
    monkeypatch.setattr(Broker, 'fetch', lambda self, s: b'Changed event' if s['source_id'] == 'ANET' else original(self, s))
    published = publish(c.store, w.ledger)
    report = w.report(identity)
    assert report['publication']['publication_id'] == published['publication_id']
    assert 'withdrew' in report['product']['findings']['summary']
    row = next(r for r in report['product']['findings']['instruments'] if r['symbol'] == 'ANET')
    assert row['assessment'] == 'insufficient_evidence' and row['review_conditions'] == []
    frozen = w.ledger/'publications'/published['publication_id']/'publication.json'
    frozen.write_text('{}')
    with pytest.raises(ValueError):
        w.report(identity)
