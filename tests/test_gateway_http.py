import http.server
import threading
import time

import pytest

from learning_service.gateway_http import GatewayHTTP, valid_upstream
from learning_service.provider_http import ResponseTooLarge


def test_loopback_transport_does_not_follow_redirect_or_environment_proxy(monkeypatch):
    paths = []
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            if self.path == "/redirect":
                self.send_response(302); self.send_header("Location", "/secret"); self.end_headers()
            else:
                self.send_response(200); self.end_headers(); self.wfile.write(b"x" * 100)
        def log_message(self, *args): pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    monkeypatch.setenv("http_proxy", "http://unreachable.invalid:1")
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        assert GatewayHTTP().send(base, "GET", "/redirect", {"Cookie": "synthetic=t"}).status == 302
        assert paths == ["/redirect"]
        with pytest.raises(ResponseTooLarge): GatewayHTTP().send(base, "GET", "/large", {}, limit=10)
    finally:
        server.shutdown(); server.server_close(); thread.join()


@pytest.mark.parametrize("url", ["http://user:secret@localhost", "http://localhost/path", "http://localhost?proxy=other", "file:///tmp/secret", "http://localhost:0", "http://localhost/#fragment"])
def test_transport_rejects_nonfixed_upstream(url):
    assert not valid_upstream(url)
    with pytest.raises(ValueError): GatewayHTTP().send(url, "GET", "/", {})


def test_total_deadline_interrupts_trickling_response_headers():
    class Slow(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                for char in b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n":
                    self.wfile.write(bytes([char])); self.wfile.flush(); time.sleep(0.02)
            except (BrokenPipeError, ConnectionResetError):
                pass
        def log_message(self, *args): pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    started = time.monotonic()
    try:
        with pytest.raises((OSError, http.client.HTTPException, TimeoutError)):
            GatewayHTTP().send(f"http://127.0.0.1:{server.server_port}", "GET", "/", {}, timeout=0.12)
        assert time.monotonic() - started < 0.6
    finally:
        server.shutdown(); server.server_close(); thread.join()
