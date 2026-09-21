"""Local question entry, bounded launch, and saved conclusions. No automatic retries."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
from threading import Lock, Thread
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
import uuid

from .contracts import ROOT, validate
from .controller import Controller
from .monitor import artifact, project
from .publication import publish, read_publication
from .store import Store

QUESTION = ('Research NVDA and MU over the next three months. Compare their valuation '
            'assumptions, demand drivers, and downside risks against QQQ. Explain what '
            'evidence would change each assessment.')
SYMBOLS = ['NVDA', 'MU', 'QQQ']
DEFAULT_ROOT = ROOT / 'reports/investment-research/workspace-v1'
DEFAULT_LEDGER = ROOT / 'datasets/investment-research/workspace-v1'


def mandate_for(question, *, now=None):
    """V1 supports this explicitly displayed universe; prose cannot change execution policy."""
    if not isinstance(question, str) or not 12 <= len(question.strip()) <= 8000:
        raise ValueError('Enter a research question between 12 and 8,000 characters.')
    now = now or datetime.now(timezone.utc)
    mandate = json.loads((ROOT / 'config/investment-research-m2-live-v7.json').read_text())
    mandate['schema_version'] = 'investment-research-mandate-v4'
    mandate['objective'] = question.strip() + (
        '\nRegistered scope: NVDA and MU compared against QQQ, over 63 trading sessions '
        '(approximately three months). Research only. Explain demand drivers, explicit '
        'valuation assumptions, downside cases, and symbol-specific evidence that would '
        'change the assessment. Use deterministic scenario calculations when supported; '
        'distinguish assumptions from facts, fiscal periods from annual earnings, and '
        'dated ETF holdings from current holdings. Missing consensus is unknown. '
        'The registered universe, budgets and tools cannot be changed by the question.')
    mandate['watchlist'] = [next(deepcopy(w) for w in mandate['watchlist'] if w['symbol'] == s) for s in SYMBOLS]
    for item in mandate['watchlist']:
        if item['kind'] == 'company':
            item['benchmark'] = 'QQQ'
    mandate['horizon_sessions'] = [63]
    allowed = set(SYMBOLS + ['SPY', 'XLK', 'IWM', 'HYG'])
    mandate['sources'] = [s for s in mandate['sources'] if not s['symbols'] or set(s['symbols']) <= allowed]
    for source in mandate['sources']:
        if source['adapter'] == 'alpaca_daily':
            parts = urlsplit(source['url'])
            query = parse_qs(parts.query)
            query.update(start=[(now-timedelta(days=410)).isoformat()], end=[(now-timedelta(minutes=20)).isoformat()])
            source['url'] = urlunsplit(parts._replace(query=urlencode(query, doseq=True)))
            source['critical'] = source['symbols'][0] in SYMBOLS
        elif source['adapter'] == 'fred_csv':
            source['url'] = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={source['series_id']}&cosd={(now-timedelta(days=120)).date()}"
    template = next(s for s in mandate['sources'] if s['source_id'] == 'nvda-press-feed')
    for identity, symbol, title, url in [
        ('nvda-quarterly-results', 'NVDA', 'NVIDIA Q2 FY2027 results, August 26 2026', 'https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2027'),
        ('mu-quarterly-results', 'MU', 'Micron Q3 FY2026 results, June 24 2026', 'https://investors.micron.com/news/press-release/2026/Micron-Technology-Inc--Reports-Record-Results-for-the-Third-Quarter-of-Fiscal-2026/default.aspx'),
        ('mu-earnings-event', 'MU', 'Micron scheduled earnings announcement', 'https://investors.micron.com/news/press-release/2026/Micron-Technology-to-Report-Fiscal-Fourth-Quarter-Results-on-September-30-2026/default.aspx'),
        ('qqq-sponsor-current', 'QQQ', 'Invesco QQQ sponsor overview at retrieval', 'https://www.invesco.com/qqq-etf/en/about.html'),
    ]:
        source = deepcopy(template)
        source.update(source_id=identity, symbols=[symbol], title=title, publisher='Invesco' if symbol == 'QQQ' else 'Micron' if symbol == 'MU' else 'NVIDIA', url=url, kind='etf' if symbol == 'QQQ' else 'company')
        mandate['sources'].append(source)
    mandate['seed_source_ids'] = [s['source_id'] for s in mandate['sources']]
    mandate['publication_policy'] = {
        'version': 'investment-research-publication-policy-v1',
        'refresh_source_ids': [s['source_id'] for s in mandate['sources'] if s['adapter'] == 'alpaca_daily'] +
            ['nvda-press-feed', 'sec-submissions-NVDA', 'sec-submissions-MU', 'mu-earnings-event', 'fed-monetary-feed'],
        'material_price_move_pct': 2, 'maximum_refresh_age_seconds': 600, 'maximum_quote_age_seconds': 60,
    }
    validate('mandate', mandate)
    return mandate


class Workspace:
    def __init__(self, root=DEFAULT_ROOT, ledger=DEFAULT_LEDGER, *, launch=None):
        self.root, self.ledger = Path(root), Path(ledger)
        self.root.mkdir(parents=True, exist_ok=True)
        self.guard = Lock()
        self.active = None
        self.launch = launch or self._launch
        self.csrf = secrets.token_urlsafe(32)

    def directory(self, identity):
        if not isinstance(identity, str) or str(uuid.UUID(identity)) != identity:
            raise ValueError('Unknown research identifier')
        path = self.root / identity
        if path.is_symlink() or not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError('Invalid research path')
        return path

    def job(self, identity):
        return json.loads((self.directory(identity) / 'job.json').read_text())

    def save_job(self, job):
        path = self.directory(job['id'])
        temp = path / 'job.tmp'
        temp.write_text(json.dumps(job, indent=2) + '\n')
        temp.replace(path / 'job.json')

    def summary(self, identity):
        job = self.job(identity)
        path = self.directory(identity) / 'run'
        if (path / 'state.json').exists():
            state = Store(path).load()
            job.update(status=state['status'], usage=state['usage'], usage_unknown=state['usage_unknown'],
                       run_id=state['run_id'], publication_id=state.get('publication_id'),
                       completed_at=state.get('completed_at'), stop_reason=state.get('stop_reason'))
        job['busy'] = self.active == identity
        if job.get('operation') in {'research', 'publication'} and not job['busy']:
            job['interrupted'] = True
            job['error'] = 'Workspace stopped before operation completion. No automatic retry; inspect saved usage and artifacts.'
        return job

    def listing(self):
        return sorted([self.summary(p.parent.name) for p in self.root.glob('*/job.json')], key=lambda j: j['created_at'], reverse=True)

    def start(self, identity, question):
        path = self.directory(identity)
        with self.guard:
            if (path / 'job.json').exists():
                job = self.job(identity)
                if job['question'] != question.strip():
                    raise ValueError('Request identifier already belongs to a different question')
                return self.summary(identity)  # Duplicate browser submission never starts another worker.
            if self.active:
                raise ValueError('A research or publication operation is already running.')
            mandate = mandate_for(question)
            path.mkdir(exist_ok=False)
            (path / 'mandate.json').write_text(json.dumps(mandate, indent=2) + '\n')
            job = {'id': identity, 'question': question.strip(), 'created_at': datetime.now(timezone.utc).isoformat(),
                   'status': 'QUEUED', 'operation': 'research', 'scope': SYMBOLS, 'horizon_sessions': [63],
                   'budgets': mandate['budgets'], 'model': mandate['runtime']['model'], 'mode': 'live'}
            self.save_job(job)
            self.active = identity
            self.launch(identity, 'research')
            return job

    def start_publication(self, identity):
        with self.guard:
            job = self.job(identity)
            if job.get('publication_attempted'):
                return self.summary(identity)
            if self.active:
                raise ValueError('An operation is already running.')
            state = Store(self.directory(identity) / 'run').load()
            if state['status'] != 'DRAFT' or state['usage_unknown']:
                raise ValueError('Publication requires a completed draft with known usage.')
            job.update(operation='publication', publication_attempted=True)
            self.save_job(job)
            self.active = identity
            self.launch(identity, 'publication')
            return job

    def _launch(self, identity, operation):
        Thread(target=self.execute, args=(identity, operation), daemon=True).start()

    def execute(self, identity, operation):
        job = self.job(identity)
        try:
            controller = Controller(self.directory(identity) / 'run')
            if operation == 'research':
                controller.create(json.loads((self.directory(identity) / 'mandate.json').read_text()))
                state = controller.run()
                job['status'] = state['status']
            else:
                result = publish(controller.store, self.ledger)
                job.update(status='PUBLISHED', publication_id=result['publication_id'])
        except Exception as error:
            # Preserve actual failure, never invoke a paid retry or rewrite research state.
            job.update(error=f'{type(error).__name__}: {error}', status='FAILED')
        finally:
            job['operation'] = None
            with self.guard:
                self.save_job(job)
                self.active = None

    def report(self, identity):
        job = self.summary(identity)
        store = Store(self.directory(identity) / 'run')
        state = store.load()
        publication = read_publication(self.ledger, state['publication_id']) if state.get('publication_id') else None
        product = publication['product'] if publication else store.get('products', state['product_id']) if state.get('product_id') else None
        return {'job': job, 'product': product, 'publication': publication,
                'sources': [{k: e.get(k) for k in ('evidence_id', 'source_id', 'url', 'title', 'published_at', 'retrieved_at', 'adapter', 'data')} | {'evidence_id': i}
                            for i in (product or {}).get('evidence_ids', []) for e in [store.get('evidence', i)]]}


def handler(workspace):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, value, status=200, mime='application/json'):
            body = value if isinstance(value, bytes) else json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def local(self, write=False):
            host = self.headers.get('Host', '')
            expected = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            origin = self.headers.get('Origin')
            okay = host in expected and (origin is None or origin == 'http://' + host)
            if write:
                okay = okay and origin == 'http://' + host and secrets.compare_digest(self.headers.get('X-Research-Token', ''), workspace.csrf)
            if not okay:
                self.respond({'error': 'Local same-origin request required'}, 403)
            return okay

        def do_GET(self):
            if not self.local():
                return
            url = urlsplit(self.path)
            try:
                if url.path == '/api/workspace':
                    mandate = mandate_for(QUESTION)
                    return self.respond({'question': QUESTION, 'scope': SYMBOLS, 'horizon_sessions': [63],
                        'budgets': mandate['budgets'], 'model': mandate['runtime']['model'], 'token': workspace.csrf,
                        'jobs': workspace.listing()})
                match = re.fullmatch(r'/api/runs/([a-f0-9-]+)/(snapshot|report|artifact/(\w+)/([a-f0-9]+))', url.path)
                if match:
                    identity, action, kind, digest = match.groups()
                    workspace.job(identity)
                    store = Store(workspace.directory(identity) / 'run')
                    value = (project(store, after=int(parse_qs(url.query).get('after', ['0'])[0])) if action == 'snapshot'
                             else workspace.report(identity) if action == 'report' else artifact(store, kind, digest))
                    return self.respond(value)
                pages = {'/': 'workspace.html', '/reports': 'workspace.html', '/monitor': 'monitor.html',
                         '/workspace.js': 'workspace.js', '/workspace.css': 'workspace.css', '/monitor.js': 'monitor.js', '/monitor.css': 'monitor.css'}
                if url.path in pages:
                    filename = pages[url.path]
                    mime = {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css'}[filename.split('.')[-1]]
                    return self.respond((Path(__file__).parent / 'web' / filename).read_bytes(), mime=mime)
                self.respond({'error': 'Unknown page'}, 404)
            except (ValueError, KeyError, FileNotFoundError):
                self.respond({'error': 'Saved record unavailable or failed integrity validation'}, 404)

        def do_POST(self):
            if not self.local(write=True):
                return
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 40000 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('Expected bounded JSON request')
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise ValueError('Expected JSON object')
                if self.path == '/api/runs' and set(value) == {'id', 'question'}:
                    result = workspace.start(value['id'], value['question'])
                elif re.fullmatch(r'/api/runs/[a-f0-9-]+/publish', self.path) and value == {'reviewed': True}:
                    result = workspace.start_publication(self.path.split('/')[3])
                else:
                    raise ValueError('Unsupported operation')
                self.respond(result, 202)
            except (ValueError, KeyError, TypeError, AttributeError, FileNotFoundError) as error:
                self.respond({'error': str(error)}, 400)

        def log_message(self, *args):
            pass
    return Handler


def serve(root=DEFAULT_ROOT, ledger=DEFAULT_LEDGER, port=8766):
    workspace = Workspace(root, ledger)
    with Store(workspace.root).lock():
        server = ThreadingHTTPServer(('127.0.0.1', port), handler(workspace))
        print(f'Research workspace: http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
