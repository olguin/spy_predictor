from types import SimpleNamespace
from urllib.error import URLError

import pytest

from spy_predictor_quant import meta_analysis as module


def test_fred_public_transport_is_bounded_https_and_keeps_exact_payload(monkeypatch):
    seen = []
    payload = b"observation_date,DFF\n2026-09-15,3.5\n"
    def run(argv, **kwargs):
        seen.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=payload, stderr=b"")
    monkeypatch.setattr(module.subprocess, "run", run)
    assert module.get_raw("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF") == payload
    argv, options = seen[0]
    assert argv[0] == "curl" and options["timeout"] == 30
    assert argv[argv.index("--proto-redir") + 1] == "=https"
    assert argv[argv.index("--max-filesize") + 1] == "20000000"
    assert argv[-1] == "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF"


def test_fred_failure_cannot_be_returned_as_data_and_other_sources_keep_headers(monkeypatch):
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=28, stdout=b"partial", stderr=b"private diagnostic"))
    with pytest.raises(URLError, match="curl exit 28") as error:
        module.get_raw("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF")
    assert "private diagnostic" not in str(error.value)
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, limit):
            return b"{}"
    def urlopen(request, timeout):
        assert request.get_header("X-test") == "test-value"
        return Response()
    monkeypatch.setattr(module, "urlopen", urlopen)
    assert module.get_raw("https://data.alpaca.markets/example", {"X-Test": "test-value"}) == b"{}"
