"""Open WebUI Cookie bridge. Disabled by default; no WebUI secrets or imports."""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from urllib.parse import parse_qs
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from .browser_auth import CSRF_COOKIE, SESSION_COOKIE
from .gateway_http import GatewayHTTP, GatewayResult, valid_upstream
from .provider_usage import safe_reference
from .secret_files import env_secret
from .textbooks import bounded_references, chapter_references


@dataclass(frozen=True)
class GatewaySettings:
    enabled: bool = False
    public_origin: str = ""
    public_base_path: str = "/learning"
    openwebui_url: str = "http://open-webui:8080"
    learning_url: str = "http://learning-api:8000"
    assertion_secret: str = field(default="", repr=False)
    assertion_issuer: str = ""
    assertion_audience: str = "dd-learning-v1"
    identity_provider: str = "open-webui"
    identity_issuer: str = "open-webui"
    family_setup_enabled: bool = False

    @classmethod
    def from_env(cls):
        return cls(enabled=os.getenv("DD_GATEWAY_ENABLED", "0") == "1",
                   public_origin=os.getenv("DD_GATEWAY_PUBLIC_ORIGIN", ""),
                   public_base_path=os.getenv("LEARNING_PUBLIC_BASE_PATH", "/learning"),
                   openwebui_url=os.getenv("DD_GATEWAY_OPENWEBUI_URL", "http://open-webui:8080"),
                   learning_url=os.getenv("DD_GATEWAY_LEARNING_URL", "http://learning-api:8000"),
                   assertion_secret=env_secret("LEARNING_BROWSER_AUTH_SECRET"),
                   assertion_issuer=os.getenv("LEARNING_BROWSER_AUTH_ISSUER", ""),
                   assertion_audience=os.getenv("LEARNING_BROWSER_AUTH_AUDIENCE", "dd-learning-v1"),
                   identity_provider=os.getenv("LEARNING_BROWSER_IDENTITY_PROVIDER", "open-webui"),
                   identity_issuer=os.getenv("LEARNING_BROWSER_IDENTITY_ISSUER", "open-webui"),
                   family_setup_enabled=os.getenv("DD_FAMILY_SETUP_ENABLED", "0") == "1")

    def configured(self) -> bool:
        try:
            p = urlsplit(self.public_origin)
            return bool(self.enabled and p.scheme == "https" and p.hostname and p.port in {None, 443}
                        and not p.username and not p.password and not p.path and not p.query and not p.fragment
                        and self.public_origin.isascii() and not any(c.isspace() for c in self.public_origin)
                        and re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", self.public_base_path)
                        and valid_upstream(self.openwebui_url) and valid_upstream(self.learning_url)
                        and len(self.assertion_secret) >= 32
                        and all(safe_reference(x) for x in (self.assertion_issuer, self.assertion_audience,
                                                          self.identity_provider, self.identity_issuer)))
        except ValueError:
            return False


class GatewayError(Exception):
    def __init__(self, code: str, status: int = 401):
        super().__init__(code)
        self.code, self.status = code, status


def strict_json(body: bytes) -> dict:
    def pairs(items):
        d = {}
        for key, value in items:
            if key in d:
                raise ValueError("duplicate field")
            d[key] = value
        return d
    value = json.loads(body, object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise ValueError("object required")
    return value


class LoginNonces:
    """Bounded, one-process, one-use nonces; no original token is retained."""
    def __init__(self, capacity: int = 1024):
        self.capacity, self.values, self.lock = capacity, {}, threading.Lock()

    @staticmethod
    def digest(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def issue(self, token: str, subject: str) -> str:
        with self.lock:
            now = time.monotonic()
            self.values = {k: v for k, v in self.values.items() if v[2] > now}
            if len(self.values) >= self.capacity:
                raise GatewayError("LOGIN_CAPACITY_REACHED", 429)
            nonce = secrets.token_urlsafe(32)
            self.values[self.digest(nonce)] = (self.digest(token), subject, now + 120)
            return nonce

    def consume(self, nonce: str, token: str, subject: str):
        with self.lock:
            value = self.values.pop(self.digest(nonce), None)
        if not value or value[2] <= time.monotonic() or value[:2] != (self.digest(token), subject):
            raise GatewayError("LOGIN_CSRF_REJECTED", 403)


# Explicit public business routes. Adding an API route does not expose it here.
ID = r"[A-Za-z0-9_-]{1,128}"
ROUTES = {
    "GET": [r"/ui", r"/health", r"/api/v1/(?:auth/session|learners|learner-context|review-tasks|progress|mistakes|question-choices)",
            rf"/api/v1/(?:documents|import-batches|mistakes|learning-drafts|diagnoses|test-sessions|test-items|attempts|operations|visual-assets|agent-runs|jobs|assets)/{ID}",
            rf"/api/v1/import-batches/{ID}/items", rf"/api/v1/source-pages/{ID}/content",
            r"/api/v1/admin/(?:metrics|provider-calls|variant-jobs)", rf"/api/v1/admin/variant-jobs/{ID}", rf"/api/v1/admin/exports/{ID}"],
    "POST": [r"/api/v1/(?:auth/logout|learner-context|documents|import-batches|mistakes/manual|learning-drafts|test-sessions|visual-jobs|variant-jobs|agent-runs)",
             rf"/api/v1/import-batches/{ID}/(?:analysis|cancel|confirmation-challenges|confirmations)",
             rf"/api/v1/mistakes/{ID}/(?:retractions|diagnoses)",
             rf"/api/v1/learning-drafts/{ID}/(?:confirmation-challenges|confirmations)",
             rf"/api/v1/test-sessions/{ID}/cancel", rf"/api/v1/test-items/{ID}/(?:hints|submission-challenges|answers)",
             rf"/api/v1/attempts/{ID}/review-requests", rf"/api/v1/admin/reviews/{ID}/decisions",
             rf"/api/v1/visual-assets/{ID}/issues", rf"/api/v1/agent-runs/{ID}/steps", rf"/api/v1/jobs/{ID}/cancel",
             r"/api/v1/admin/(?:provider-control|exports|deletions)", rf"/api/v1/admin/provider-calls/{ID}/reconcile", rf"/api/v1/admin/variant-jobs/{ID}/review", rf"/api/v1/admin/variant-reviews/{ID}/revoke"],
    "PATCH": [rf"/api/v1/documents/{ID}/pages", rf"/api/v1/import-items/{ID}"],
}
ROUTES['GET'].append(r'/api/v1/textbooks')
ROUTES['GET'].append(r'/api/v1/math-references')
ROUTES['GET'].append(r'/api/v1/study-support')
ROUTES['GET'].append(r'/api/v1/textbooks/(?:chinese|math|english|ethics|history|geography|physics|chemistry|biology)-g[27]-(?:upper|lower)/pages/[1-9][0-9]{0,2}/image')
ROUTES['POST'].append(r'/api/v1/textbooks/search')


def _cookies(request: Request) -> dict[str, str]:
    # Reject ambiguity rather than rely on different upstream Cookie parsers.
    result = {}
    for header in request.headers.getlist("cookie"):
        for part in header.split(";"):
            key, separator, value = part.strip().partition("=")
            if key not in {"token", SESSION_COOKIE, CSRF_COOKIE}:
                continue
            if key in result or not separator or not re.fullmatch(r"[A-Za-z0-9._~-]{1,8192}", value):
                raise GatewayError("COOKIE_REJECTED")
            result[key] = value
    return result


def _learning_cookies(cookies: dict[str, str]) -> str:
    return "; ".join(k + "=" + cookies[k] for k in (SESSION_COOKIE, CSRF_COOKIE) if k in cookies)


def _set_cookies(result: GatewayResult) -> list[str]:
    output, seen = [], set()
    for key, value in result.headers:
        if key.lower() != "set-cookie":
            continue
        parsed = SimpleCookie()
        parsed.load(value)
        if len(parsed) != 1:
            raise GatewayError("LEARNING_UPSTREAM_INVALID", 502)
        name, cookie = next(iter(parsed.items()))
        if (name not in {SESSION_COOKIE, CSRF_COOKIE} or name in seen or cookie["domain"]
                or cookie["path"] != "/" or not cookie["secure"] or cookie["samesite"].lower() != "strict"
                or (name == SESSION_COOKIE and not cookie["httponly"])):
            raise GatewayError("LEARNING_UPSTREAM_INVALID", 502)
        seen.add(name)
        output.append(value)
    return output


def create_gateway(settings: GatewaySettings | None = None, transport=None) -> FastAPI:
    settings = settings or GatewaySettings.from_env()
    transport = transport or GatewayHTTP()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    nonces = LoginNonces()
    app.state.settings, app.state.nonces = settings, nonces

    async def send(upstream, method, path, headers, body=b"", timeout=3, limit=65536):
        try:
            result = await run_in_threadpool(transport.send, upstream, method, path, headers, body, timeout=timeout, limit=limit)
            if len(result.body) > limit or result.status < 100 or result.status >= 600:
                raise ValueError()
            return result
        except Exception:
            # Never echo exception text containing URLs, cookies or assertions.
            raise GatewayError("AUTH_UPSTREAM_UNAVAILABLE" if upstream == settings.openwebui_url else "LEARNING_UPSTREAM_UNAVAILABLE", 503)

    async def identity(cookies):
        token = cookies.get("token")
        if not token:
            raise GatewayError("WEBUI_LOGIN_REQUIRED")
        result = await send(settings.openwebui_url, "GET", "/api/v1/auths/", {"Cookie": "token=" + token, "Accept": "application/json"})
        if result.status != 200:
            raise GatewayError("WEBUI_LOGIN_REJECTED")
        try:
            data = strict_json(result.body)
            if not safe_reference(data.get("id")) or data.get("role") not in {"admin", "user"}:
                raise ValueError()
            return data["id"]
        except (ValueError, TypeError, RecursionError):
            raise GatewayError("WEBUI_LOGIN_REJECTED")

    def origin(request):
        if request.headers.getlist("origin") != [settings.public_origin]:
            raise GatewayError("ORIGIN_REJECTED", 403)

    async def body_bytes(request, limit):
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > limit:
                raise GatewayError("REQUEST_TOO_LARGE", 413)
        return bytes(payload)

    @app.exception_handler(GatewayError)
    async def failure(request, exc):
        response = JSONResponse({"error": {"code": exc.code, "message": "请重新登录学习工作区；若问题持续，请联系管理员。"}},
                                status_code=exc.status, headers={"Cache-Control": "no-store"})
        if exc.status in {401, 403}:
            response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="strict", path="/")
            response.delete_cookie(CSRF_COOKIE, secure=True, samesite="strict", path="/")
        return response

    @app.api_route("/{rest:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE", "HEAD", "OPTIONS"])
    async def route(request: Request, rest: str):
        if not settings.configured():
            raise GatewayError("GATEWAY_DISABLED_OR_UNCONFIGURED", 503)
        raw = request.scope.get("raw_path", b"")
        if (b"%" in raw or b"\\" in raw or b"//" in raw or request.headers.getlist("authorization")):
            raise GatewayError("ROUTE_REJECTED", 404)
        prefix = settings.public_base_path
        path = request.url.path
        if not path.startswith(prefix + "/"):
            raise GatewayError("ROUTE_REJECTED", 404)
        path = path[len(prefix):]
        if path in {"/auth/login", "/auth/session"}:
            if request.url.query or request.method != ("GET" if path == "/auth/login" else "POST"):
                raise GatewayError("ROUTE_REJECTED", 404)
        elif not any(re.fullmatch(p, path) for p in ROUTES.get(request.method, [])):
            raise GatewayError("ROUTE_REJECTED", 404)
        if request.method not in {"GET", "HEAD"}:
            origin(request)
        cookies = _cookies(request)
        if path in {'/auth/login', '/ui'} and not cookies.get('token'):
            return RedirectResponse('/auth?redirect=' + settings.public_base_path + '/auth/login', status_code=303)
        subject = await identity(cookies)
        if path == "/auth/login":
            nonce = nonces.issue(cookies["token"], subject)
            return HTMLResponse('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>登录学习工作区</title>'
                                '<form method="post" action="' + html.escape(prefix + "/auth/session", quote=True) + '">'
                                '<input type="hidden" name="csrf" value="' + nonce + '">'
                                + ('<p>首次使用请输入家庭启用码；绑定后可留空。</p><label>家庭启用码 <input type="password" name="family_setup_code" maxlength="128" autocomplete="off"></label>' if settings.family_setup_enabled else '') +
                                '<button type="submit">进入学习工作区</button></form></html>',
                                headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'", "Referrer-Policy": "same-origin"})
        if path == "/auth/session":
            payload = await body_bytes(request, 1024)
            try:
                form = parse_qs(payload.decode('ascii'), keep_blank_values=True, max_num_fields=2)
            except (ValueError, UnicodeError):
                raise GatewayError("LOGIN_CSRF_REJECTED", 403)
            if (set(form) - {'csrf', 'family_setup_code'} or any(len(v) != 1 for v in form.values())
                    or not re.fullmatch(r"[A-Za-z0-9_-]{40,64}", form.get('csrf', [''])[0])):
                raise GatewayError("LOGIN_CSRF_REJECTED", 403)
            setup_code = form.get('family_setup_code', [''])[0]
            if setup_code and (not settings.family_setup_enabled or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', setup_code)):
                raise GatewayError("LOGIN_CSRF_REJECTED", 403)
            nonces.consume(form['csrf'][0], cookies["token"], subject)
            now = int(time.time())
            encode = lambda data: base64.urlsafe_b64encode(data).rstrip(b"=").decode()
            head = encode(b'{"alg":"HS256","typ":"JWT"}')
            claim = encode(json.dumps({"iss": settings.assertion_issuer, "aud": settings.assertion_audience,
                                       "sub": subject, "iat": now, "exp": now + 60, "jti": secrets.token_urlsafe(24)}, separators=(",", ":")).encode())
            signed = head + "." + claim
            assertion = signed + "." + encode(hmac.new(settings.assertion_secret.encode(), signed.encode(), hashlib.sha256).digest())
            result = await send(settings.learning_url, "POST", "/api/v1/auth/session",
                                {"Authorization": "Bearer " + assertion, "Origin": settings.public_origin, "X-Family-Setup-Code": setup_code,
                                 "Cookie": _learning_cookies(cookies)}, b"")
            if result.status != 201:
                raise GatewayError("LEARNING_LOGIN_REJECTED", 401 if result.status in {401, 403, 409} else 502)
            issued = _set_cookies(result)
            if len(issued) != 2:
                raise GatewayError("LEARNING_UPSTREAM_INVALID", 502)
            response = RedirectResponse(prefix + "/ui", status_code=303, headers={"Cache-Control": "no-store"})
            for value in issued:
                response.headers.append("set-cookie", value)
            return response
        session_result = await send(settings.learning_url, "GET", "/api/v1/auth/session", {"Cookie": _learning_cookies(cookies)})
        try:
            session = strict_json(session_result.body)
            if (session_result.status != 200 or session.get("server_context_mode") is not True
                    or session.get("identity") != {"provider": settings.identity_provider, "issuer": settings.identity_issuer, "subject": subject}):
                raise ValueError()
        except (ValueError, TypeError, RecursionError):
            raise GatewayError("LEARNING_IDENTITY_MISMATCH")
        if path == "/api/v1/auth/session":
            session.pop("identity", None)
            return JSONResponse(session, headers={"Cache-Control": "no-store"})
        headers = {"Cookie": _learning_cookies(cookies), "Accept": "application/json"}
        for name in ("content-type", "x-csrf-token", "x-learner-context-version", "idempotency-key"):
            values = request.headers.getlist(name)
            if len(values) > 1 or values and (len(values[0]) > 512 or any(ord(c) < 32 for c in values[0])):
                raise GatewayError("REQUEST_HEADERS_REJECTED", 400)
            if values:
                headers[name] = values[0]
        if request.method not in {"GET", "HEAD"}:
            headers["Origin"] = settings.public_origin
        payload = await body_bytes(request, 4096 if path == '/api/v1/textbooks/search' else 25 * 1024 * 1024)
        target = path + ("?" + request.url.query if request.url.query else "")
        result = await send(settings.learning_url, request.method, target, headers, payload, timeout=30, limit=32 * 1024 * 1024)
        if path == '/api/v1/textbooks/search' and result.status == 200:
            try:
                scope = strict_json(result.body)
                if scope.get('mode') == 'browse':
                    return JSONResponse(chapter_references(scope), headers={'Cache-Control':'no-store'})
                query_body = json.dumps({'collection_name':scope['book']['collection'],
                                         'query':scope['query'],'k':40,'hybrid':False}).encode()
                retrieved = await send(settings.openwebui_url, 'POST', '/api/v1/retrieval/query/doc',
                    {'Cookie':'token='+cookies['token'],'Accept':'application/json','Content-Type':'application/json'},
                    query_body, timeout=30, limit=256*1024)
                if retrieved.status != 200:
                    raise GatewayError('TEXTBOOK_RETRIEVAL_UNAVAILABLE', 503)
                references = bounded_references(scope, strict_json(retrieved.body))
            except (KeyError, ValueError, TypeError, RecursionError):
                raise GatewayError('TEXTBOOK_RETRIEVAL_INVALID', 502)
            return JSONResponse(references, headers={'Cache-Control':'no-store'})
        if 300 <= result.status < 400:
            raise GatewayError("LEARNING_REDIRECT_REJECTED", 502)
        response = Response(result.body, status_code=result.status, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        for name, value in result.headers:
            if name.lower() == "content-type":
                response.headers["content-type"] = value
        for value in _set_cookies(result):
            response.headers.append("set-cookie", value)
        return response

    return app


if __name__ == "__main__":
    import uvicorn
    # Nonces are process-local: keep exactly one worker and suppress URL logs.
    uvicorn.run(create_gateway(), host="0.0.0.0", port=8000, workers=1, access_log=False)
