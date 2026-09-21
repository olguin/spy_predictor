"""Local, read-only projection. Never takes the controller execution lock."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, parse_qs

from .store import Store

KINDS = {'evidence', 'documents', 'manifests', 'requests', 'responses', 'products'}
TERMINAL = {'DRAFT', 'INCOMPLETE', 'INTERRUPTED', 'FAILED', 'PUBLISHED', 'CAPABILITY_CHECK'}


def instant(value):
    return datetime.fromisoformat(value) if value else None


def project(store, *, after=0, now=None):
    state = store.load()
    now = now or datetime.now(timezone.utc)
    end = instant(state.get('completed_at'))
    last = instant(state.get('updated_at'))
    active = [a for a in state['attempts'] if a['status'] == 'STARTED']
    deadlines = [instant(a.get('worker_deadline_at')) for a in active if a.get('worker_deadline_at')]
    stale = state['status'] not in TERMINAL and (
        (deadlines and now > max(deadlines)) or (not active and last and (now-last).total_seconds() > 10))
    observed = end or (last if stale or state['status'] in TERMINAL else now)
    start = instant(state['started_at'])
    deadline = instant(state.get('run_deadline_at')) or start + timedelta(seconds=state['limits']['wall_seconds'])
    events = state['events']
    sequenced = bool(state.get('telemetry_version'))
    tasks = []
    receipt_totals = dict.fromkeys(('input_tokens', 'output_tokens', 'catalog_cost_usd'), 0)
    unknown_attempts = []
    for task in state['tasks']:
        attempts = []
        for attempt in state['attempts']:
            if attempt.get('task_id') != task['task_id']:
                continue
            receipt = store.get('responses', attempt['response_id']).get('receipt') if attempt.get('response_id') else None
            if not receipt or any(receipt.get(k) is None for k in receipt_totals):
                unknown_attempts.append(attempt['attempt_id'])
            for key in receipt_totals:
                amount = (receipt or {}).get(key)
                if isinstance(amount, (int, float)) and not isinstance(amount, bool):
                    receipt_totals[key] += amount
            attempts.append({**attempt, 'receipt': receipt})
        task_end = instant(task.get('completed_at'))
        task_start = instant(task.get('started_at'))
        stop = task_end or (observed if task['status'] == 'RUNNING' else None)
        tasks.append({**task, 'attempts': attempts, 'horizon_sessions': state['mandate']['horizon_sessions'],
            'duration_seconds': max(0, (stop-task_start).total_seconds()) if stop and task_start else None,
            'turns_remaining': max(0, task['model_turn_limit']-len(attempts)),
            'timing_uncertain': task.get('terminal_time_uncertain', False) or bool(stale and task['status'] == 'RUNNING')})
    edges = [{'kind': 'parent assignment', 'from': t['parent_task_id'], 'to': t['task_id']}
             for t in tasks if t.get('parent_task_id')]
    edges += [{'kind': 'reused answer' if q.get('answer_reused') else 'research request',
               'from': q['parent_task_id'], 'to': q['answer_task_id'], 'question_id': q['question_id'],
               'reason': q['decision_impact']} for q in state['questions'] if q.get('answer_task_id')]
    final = next((t['result'] for t in reversed(tasks) if t['stage'] == 'final' and t['result']), {})
    omissions = [r for r in final.get('role_coverage', []) if r['status'] != 'completed']
    return {'schema_version': 'investment-research-monitor-v1', 'telemetry_version': state.get('telemetry_version'),
        'run_id': state['run_id'], 'status': state['status'], 'phase': state['phase'],
        'updated_at': state.get('updated_at'), 'completed_at': state.get('completed_at'),
        'started_at': state['started_at'], 'view_at': observed.isoformat() if observed else None,
        'stale': bool(stale), 'historical_timing_unknown': not sequenced,
        'elapsed_seconds': max(0, (observed-start).total_seconds()) if observed else None,
        'run_deadline_at': deadline.isoformat(), 'wall_remaining_seconds': max(0, (deadline-now).total_seconds()) if state['status'] not in TERMINAL else 0,
        'usage': state['usage'], 'limits': state['limits'], 'usage_unknown': state['usage_unknown'],
        'receipt_totals': receipt_totals, 'unknown_attempts': unknown_attempts,
        'receipts_reconcile': all(abs(receipt_totals[k]-state['usage'][k]) < 1e-8 for k in receipt_totals),
        'reservations': {**state['reservations'], 'model_calls': state['limits']['reserved_final_calls'],
                         'publication_refresh': state.get('publication_reservations', {})},
        'tasks': tasks, 'questions': state['questions'], 'edges': edges, 'omissions': omissions,
        'planned_stages': [s for s in ('draft', 'review', 'final') if not any(t['stage'] == s for t in tasks)] if state['status'] not in TERMINAL else [],
        'events': [e for e in events if e.get('sequence', 0) > after] if sequenced else events if after == 0 else [],
        'sequence': state.get('event_sequence'), 'product_id': state.get('product_id')}


def artifact(store, kind, identity):
    if kind not in KINDS or not re.fullmatch('[a-f0-9]{64}', identity):
        raise ValueError('Unknown artifact')
    state = store.load()
    # Only artifacts in this run's saved graph are exposed, never caller paths.
    allowed = set(state.get('evidence_ids', [])) | {state.get('manifest_id'), state.get('product_id')}
    for task in state['tasks']:
        allowed.update((task.get('manifest_id'), task.get('accepted_manifest_id')))
        allowed.update(h.get('manifest_id') for h in task['history'])
    for attempt in state['attempts']:
        allowed.update(attempt.get(k) for k in ('request_id', 'response_id', 'manifest_id'))
    if kind == 'documents':
        allowed.update(store.get('evidence', i).get('document_id') for i in state['evidence_ids'])
    if identity not in allowed:
        raise ValueError('Artifact outside run graph')
    path = store.root / kind / (identity + '.json')
    if not path.resolve().is_relative_to(store.root.resolve()) or path.is_symlink():
        raise ValueError('Artifact outside run directory')
    value = store.get(kind, identity)
    if kind == 'requests':
        value = {k: v for k, v in value.items() if k != 'runtime'}
        value['monitor_projection'] = 'Runtime launch configuration omitted; immutable original remains in the run request artifact.'
    return value


def handler(store):
    class ReadOnlyHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Refuse cross-origin browser reads and DNS rebinding hosts.
            if self.headers.get('Origin') or self.headers.get('Host', '').split(':')[0] not in {'127.0.0.1', 'localhost'}:
                self.send_error(403)
                return
            url = urlsplit(self.path)
            try:
                if url.path == '/api/snapshot':
                    body = json.dumps(project(store, after=int(parse_qs(url.query).get('after', ['0'])[0])), allow_nan=False).encode()
                    mime = 'application/json'
                elif url.path.startswith('/api/artifact/'):
                    _, _, _, kind, identity = url.path.split('/')
                    body = json.dumps(artifact(store, kind, identity), allow_nan=False).encode()
                    mime = 'application/json'
                elif url.path in ('/', '/monitor.js', '/monitor.css'):
                    filename = 'monitor.html' if url.path == '/' else url.path[1:]
                    body = (Path(__file__).parent / 'web' / filename).read_bytes()
                    mime = {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css'}[filename.split('.')[-1]]
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', mime + '; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
                self.end_headers()
                self.wfile.write(body)
            except (ValueError, KeyError, FileNotFoundError):
                self.send_error(404, 'Unknown record')

        def log_message(self, *args):
            pass
    return ReadOnlyHandler


def serve(root, port=8765):
    if not (root / 'state.json').is_file():
        raise ValueError('Run does not exist')
    server = ThreadingHTTPServer(('127.0.0.1', port), handler(Store(root)))
    print(f'Read-only run monitor: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
