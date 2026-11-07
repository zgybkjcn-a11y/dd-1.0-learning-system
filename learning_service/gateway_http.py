"""Fixed-upstream HTTP transport without proxies, redirects or retries."""
from __future__ import annotations

import http.client
import socket
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from .provider_http import ResponseTooLarge


@dataclass(frozen=True)
class GatewayResult:
    status: int
    body: bytes
    headers: tuple[tuple[str, str], ...] = ()


def valid_upstream(url: str) -> bool:
    try:
        p = urlsplit(url)
        return bool(p.scheme in {"http", "https"} and p.hostname and p.port != 0
                    and not p.username and not p.password and p.path in {"", "/"}
                    and not p.query and not p.fragment and url.isascii()
                    and not any(c.isspace() for c in url))
    except ValueError:
        return False


class GatewayHTTP:
    evidence_mode = "live_http"

    def send(self, upstream: str, method: str, path: str, headers: dict[str, str],
             body: bytes = b"", *, timeout: float = 3, limit: int = 65536) -> GatewayResult:
        if (not valid_upstream(upstream) or not path.startswith("/") or path.startswith("//")
                or any(ord(c) < 32 or ord(c) == 127 for c in path)):
            raise ValueError("invalid gateway upstream request")
        p = urlsplit(upstream)
        connection_type = http.client.HTTPSConnection if p.scheme == "https" else http.client.HTTPConnection
        connection = connection_type(p.hostname, p.port, timeout=timeout)
        deadline = time.monotonic() + timeout
        timer = None
        try:
            connection.connect()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            connection.sock.settimeout(remaining)
            connected_socket = connection.sock
            def expire():
                try:
                    connected_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            # Socket timeouts alone allow trickling status/header bytes to
            # extend a read indefinitely. Interrupt the connected socket at
            # the total deadline, including request writing and header parsing.
            timer = threading.Timer(remaining, expire)
            timer.daemon = True
            timer.start()
            connection.request(method, path, body=body, headers=headers)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            connection.sock.settimeout(remaining)
            response = connection.getresponse()
            sock = connection.sock or getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
            chunks, size = [], 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                if sock is not None:
                    sock.settimeout(remaining)
                chunk = response.read1(min(65536, limit + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > limit:
                    raise ResponseTooLarge()
            if time.monotonic() >= deadline:
                raise TimeoutError()
            if response.length not in (None, 0):
                raise http.client.IncompleteRead(b"".join(chunks), response.length)
            return GatewayResult(response.status, b"".join(chunks), tuple(response.getheaders()))
        finally:
            if timer is not None:
                timer.cancel()
            connection.close()
