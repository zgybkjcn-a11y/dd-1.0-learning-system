"""Bounded HTTPS POST transport: exact endpoint, no proxy or redirect hops."""
from __future__ import annotations

from dataclasses import dataclass
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class ResponseTooLarge(Exception):
    pass


@dataclass(frozen=True)
class HTTPResult:
    status: int
    body: bytes
    request_id: str | None = None


def valid_endpoint(value: str) -> bool:
    try:
        p = urlsplit(value)
        return bool(p.scheme == "https" and p.hostname and not p.username and not p.password
                    and not p.query and not p.fragment and p.port in (None, 443)
                    and value.isascii() and not any(c.isspace() for c in value))
    except ValueError:
        return False


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTPTransport:
    evidence_mode = "live_http"

    def send(self, request: Request, timeout: int, limit: int) -> HTTPResult:
        # Do not honor ambient proxy credentials or follow a provider redirect
        # with the Authorization header or a student's evidence.
        if request.get_method() != "POST" or not valid_endpoint(request.full_url):
            raise ValueError("invalid provider transport request")
        deadline = time.monotonic() + timeout
        opener = build_opener(ProxyHandler({}), _NoRedirect())
        try:
            response = opener.open(request, timeout=timeout)
        except HTTPError as exc:
            response = exc
        with response:
            chunks, size = [], 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                raw_response = response.fp if isinstance(response, HTTPError) else response
                # HTTPResponse.read1 performs at most one buffered socket read.
                # Reduce the read timeout to the remaining response deadline.
                sock = getattr(getattr(getattr(raw_response, "fp", None), "raw", None), "_sock", None)
                if sock is not None:
                    sock.settimeout(remaining)
                read_once = getattr(raw_response, "read1", raw_response.read)
                chunk = read_once(min(65536, limit + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > limit:
                    raise ResponseTooLarge()
            return HTTPResult(response.status, b"".join(chunks), response.headers.get("x-request-id"))
