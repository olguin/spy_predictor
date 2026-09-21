"""Compatibility address for the latest workspace run; never starts research.

Old open monitor tabs can continue polling read-only APIs. New navigation moves
to the canonical workspace URL. This process is independent of the controller.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import urlopen
import uuid

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT/'reports/investment-research/workspace-v1'
DESTINATION = 'http://127.0.0.1:8766'


def latest():
    jobs = [json.loads(p.read_text()) for p in WORKSPACE.glob('*/job.json')]
    if not jobs:
        return None
    job = max(jobs, key=lambda j: j['created_at'])
    return str(uuid.UUID(job['id']))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Host') not in {'127.0.0.1:8765', 'localhost:8765'} or self.headers.get('Origin'):
            self.send_error(403)
            return
        try:
            identity = latest()
            url = urlsplit(self.path)
            api = url.path == '/api/snapshot' or re.fullmatch(r'/api/artifact/(evidence|documents|manifests|requests|responses|products)/[a-f0-9]{64}', url.path)
            if api and identity:
                target = DESTINATION+'/api/runs/'+identity+url.path[4:]+('?' + url.query if url.query else '')
                with urlopen(target, timeout=8) as response:
                    body = response.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(302)
                self.send_header('Location', DESTINATION+('/monitor?run='+identity if identity else '/'))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
        except (OSError, ValueError, KeyError):
            self.send_error(503, 'Research workspace unavailable')

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    print('Monitor compatibility address: http://127.0.0.1:8765/ → latest workspace run', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
