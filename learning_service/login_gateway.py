"""Open WebUI Cookie bridge. Disabled by default; no WebUI secrets or imports."""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import logging
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
from .textbooks import bounded_references, chapter_references, SEARCH_CANDIDATE_LIMIT


LOGGER = logging.getLogger('dd.study.gateway')
# Closed recovery vocabulary; never use an upstream message or exception text.
RECOVERY = {
    'login': ('请先登录主站，再从家庭学习入口重新进入。', 'sign_in', False),
    'session': ('学习会话已失效，请从家庭学习入口重新进入。', 'reenter', False),
    'expired': ('学习会话已过期，请从家庭学习入口重新进入。', 'reenter', False),
    'identity': ('当前登录与学习会话不一致，已停止读取。请确认主站账号后重新进入家庭学习。', 'confirm_login', False),
    'context': ('当前档案已变化，已停止返回旧资料。请刷新家庭学习，重新选择档案和课本范围。', 'reselect_scope', False),
    'scope': ('请在家庭学习中重新选择当前档案的课本和章节，再重试。', 'reselect_scope', False),
    'textbook': ('当前教材原件缺失或版本校验未通过，请联系维护者核对材料后重试。', 'contact_maintainer', False),
    'reference': ('当前范围暂未提供这项资料，请查看已有目录或选择其他已列出的项目。', 'browse_available', False),
    'timeout': ('请求超时，请稍后重试。', 'retry_later', True),
    'retrieval_timeout': ('教材检索超时，请稍后重试；本次没有可用证据，不能据此判断教材没有相关内容。', 'retry_later', True),
    'unavailable': ('服务暂不可用，请稍后重试；若持续失败，请提供本次请求编号给维护者。', 'retry_later', True),
    'request': ('请求校验未通过，请刷新家庭学习后重新操作。', 'refresh', False),
}
ERROR_RECOVERY = {
    'TEXTBOOK_PASSAGES_DISABLED': 'reference', 'TEXTBOOK_PASSAGE_NOT_FOUND': 'reference',
    'TEXTBOOK_PASSAGES_UNAVAILABLE': 'textbook', 'TEXTBOOK_PASSAGE_STALE': 'reference',
    **dict.fromkeys(('WEBUI_LOGIN_REQUIRED', 'WEBUI_LOGIN_REJECTED'), 'login'),
    **dict.fromkeys(('BROWSER_LOGIN_REQUIRED', 'BROWSER_SESSION_INVALID', 'LEARNING_LOGIN_REJECTED'), 'session'),
    'BROWSER_SESSION_EXPIRED': 'expired', 'LEARNING_IDENTITY_MISMATCH': 'identity',
    'LEARNER_CONTEXT_CHANGED': 'context', 'LEARNER_CONTEXT_REQUIRED': 'scope',
    **dict.fromkeys(('TEXTBOOK_SCOPE_INVALID', 'MATH_REFERENCE_SCOPE_INVALID', 'STUDY_SUPPORT_SCOPE_INVALID', 'TEXTBOOK_PAGE_NOT_FOUND'), 'scope'),
    **dict.fromkeys(('TEXTBOOK_PAGE_UNAVAILABLE', 'MATH_REFERENCE_TEXTBOOK_UNAVAILABLE'), 'textbook'),
    **dict.fromkeys(('MATH_REFERENCE_NOT_FOUND', 'STUDY_SUPPORT_NOT_FOUND'), 'reference'),
    **dict.fromkeys(('AUTH_UPSTREAM_TIMEOUT', 'LEARNING_UPSTREAM_TIMEOUT', 'TEXTBOOK_RETRIEVAL_TIMEOUT'), 'timeout'),
    'TEXTBOOK_RETRIEVAL_TIMEOUT': 'retrieval_timeout',
    **dict.fromkeys(('COOKIE_REJECTED', 'LOGIN_CSRF_REJECTED', 'ORIGIN_REJECTED', 'BROWSER_CSRF_REJECTED', 'BROWSER_ORIGIN_REJECTED', 'REQUEST_HEADERS_REJECTED', 'REQUEST_TOO_LARGE', 'ROUTE_REJECTED'), 'request'),
    **dict.fromkeys(('GATEWAY_DISABLED_OR_UNCONFIGURED', 'LOGIN_CAPACITY_REACHED', 'AUTH_UPSTREAM_UNAVAILABLE', 'AUTH_UPSTREAM_INVALID', 'LEARNING_UPSTREAM_UNAVAILABLE', 'LEARNING_UPSTREAM_INVALID', 'LEARNING_REDIRECT_REJECTED', 'TEXTBOOK_RETRIEVAL_UNAVAILABLE', 'TEXTBOOK_RETRIEVAL_INVALID', 'MATH_REFERENCE_UNAVAILABLE', 'MATH_REFERENCE_VERSION_MISMATCH', 'STUDY_SUPPORT_UNAVAILABLE', 'STUDY_REQUEST_UNAVAILABLE'), 'unavailable'),
}
SERVICE_ERRORS = {
    'BROWSER_LOGIN_REQUIRED': 401, 'BROWSER_SESSION_INVALID': 401, 'BROWSER_SESSION_EXPIRED': 401,
    'BROWSER_CSRF_REJECTED': 403, 'BROWSER_ORIGIN_REJECTED': 403,
    'LEARNER_CONTEXT_CHANGED': 409, 'LEARNER_CONTEXT_REQUIRED': 409,
    'TEXTBOOK_SCOPE_INVALID': 422, 'MATH_REFERENCE_SCOPE_INVALID': 422, 'STUDY_SUPPORT_SCOPE_INVALID': 422,
    'TEXTBOOK_PASSAGES_DISABLED': 404, 'TEXTBOOK_PASSAGE_NOT_FOUND': 404,
    'TEXTBOOK_PASSAGES_UNAVAILABLE': 503, 'TEXTBOOK_PASSAGE_STALE': 409,
    'TEXTBOOK_PAGE_NOT_FOUND': 404, 'TEXTBOOK_PAGE_UNAVAILABLE': 503,
    'MATH_REFERENCE_NOT_FOUND': 404, 'STUDY_SUPPORT_NOT_FOUND': 404,
    'MATH_REFERENCE_TEXTBOOK_UNAVAILABLE': 503, 'MATH_REFERENCE_UNAVAILABLE': 503,
    'MATH_REFERENCE_VERSION_MISMATCH': 503, 'STUDY_SUPPORT_UNAVAILABLE': 503,
}


def service_error(result):
    """Keep only a known code with its expected status; discard all other data."""
    try:
        error = strict_json(result.body).get('error')
        code = error.get('code') if isinstance(error, dict) else None
        if isinstance(code, str) and SERVICE_ERRORS.get(code) == result.status:
            return code
    except (ValueError, TypeError, RecursionError):
        pass
    return None


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
ROUTES['GET'].append(r'/api/v1/textbooks/(?:chinese|math|english|ethics|history|geography|physics|chemistry|biology)-g[27]-(?:upper|lower)/passages/dd-excerpt-[a-f0-9]{64}(?:/image)?')


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
        component = ('TEXTBOOK_RETRIEVAL' if path == '/api/v1/retrieval/query/doc' else
                     'AUTH_UPSTREAM' if upstream == settings.openwebui_url else 'LEARNING_UPSTREAM')
        try:
            result = await run_in_threadpool(transport.send, upstream, method, path, headers, body, timeout=timeout, limit=limit)
            if len(result.body) > limit or result.status < 100 or result.status >= 600:
                raise ValueError()
            return result
        except TimeoutError:
            raise GatewayError(component + '_TIMEOUT', 504) from None
        except Exception:
            # Never echo exception text containing URLs, cookies or assertions.
            raise GatewayError(component + '_UNAVAILABLE', 503) from None

    async def identity(cookies):
        token = cookies.get("token")
        if not token:
            raise GatewayError("WEBUI_LOGIN_REQUIRED")
        result = await send(settings.openwebui_url, "GET", "/api/v1/auths/", {"Cookie": "token=" + token, "Accept": "application/json"})
        if result.status in {401, 403}:
            raise GatewayError("WEBUI_LOGIN_REJECTED")
        if result.status != 200:
            raise GatewayError("AUTH_UPSTREAM_UNAVAILABLE", 503)
        try:
            data = strict_json(result.body)
            if not safe_reference(data.get("id")) or not isinstance(data.get('role'), str):
                raise ValueError()
            if data['role'] not in {'admin', 'user'}:
                raise GatewayError('WEBUI_LOGIN_REJECTED')
            return data["id"]
        except (ValueError, TypeError, RecursionError):
            raise GatewayError("AUTH_UPSTREAM_INVALID", 502) from None

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
        code = exc.code if exc.code in ERROR_RECOVERY else 'STUDY_REQUEST_UNAVAILABLE'
        message, action, retryable = RECOVERY[ERROR_RECOVERY[code]]
        request_id = request.state.study_request_id
        LOGGER.warning('study_failure request_id=%s code=%s status=%s', request_id, code, exc.status)
        response = JSONResponse({"error": {"code": code, "message": message,
                                           "action": action, "retryable": retryable, "request_id": request_id}},
                                status_code=exc.status, headers={"Cache-Control": "no-store"})
        if exc.status in {401, 403}:
            response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="strict", path="/")
            response.delete_cookie(CSRF_COOKIE, secure=True, samesite="strict", path="/")
        return response

    @app.middleware('http')
    async def request_correlation(request, call_next):
        # Ignore caller-supplied IDs; IDs never derive from cookies or identities.
        request.state.study_request_id = 'ddreq_' + secrets.token_hex(16)
        try:
            response = await call_next(request)
        except Exception:
            response = await failure(request, GatewayError('STUDY_REQUEST_UNAVAILABLE', 503))
        response.headers['X-DD-Request-ID'] = request.state.study_request_id
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
        if session_result.status != 200:
            code = service_error(session_result)
            if code in {'BROWSER_LOGIN_REQUIRED', 'BROWSER_SESSION_INVALID', 'BROWSER_SESSION_EXPIRED'}:
                raise GatewayError(code, 401)
            if session_result.status in {401, 403}:
                raise GatewayError('BROWSER_SESSION_INVALID', 401)
            raise GatewayError('LEARNING_UPSTREAM_UNAVAILABLE', 503)
        try:
            session = strict_json(session_result.body)
            identity_data = session.get('identity')
            if (session.get('server_context_mode') is not True or not isinstance(identity_data, dict)
                    or set(identity_data) != {'provider', 'issuer', 'subject'}
                    or not all(safe_reference(v) for v in identity_data.values())):
                raise ValueError()
        except (ValueError, TypeError, RecursionError):
            raise GatewayError('LEARNING_UPSTREAM_INVALID', 502) from None
        if identity_data != {"provider": settings.identity_provider, "issuer": settings.identity_issuer, "subject": subject}:
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
        study_route = path in {'/api/v1/textbooks', '/api/v1/textbooks/search', '/api/v1/math-references', '/api/v1/study-support'} or path.startswith('/api/v1/textbooks/')
        if study_route and result.status >= 400:
            code = service_error(result)
            raise GatewayError(code or 'STUDY_REQUEST_UNAVAILABLE', result.status)
        async def check_study_context():
            checked = await send(settings.learning_url, 'GET', '/api/v1/auth/session',
                                 headers, timeout=30, limit=65536)
            if checked.status != 200:
                raise GatewayError(service_error(checked) or 'LEARNING_UPSTREAM_UNAVAILABLE',
                                   checked.status if checked.status >= 400 else 503)
            current = strict_json(checked.body)
            if (current.get('server_context_mode') is not True or not isinstance(current.get('identity'), dict)
                    or any(k not in current for k in ('account_id', 'learner_id', 'context_version'))):
                raise GatewayError('LEARNING_UPSTREAM_INVALID', 502)
            if current['identity'] != identity_data or current['account_id'] != session.get('account_id'):
                raise GatewayError('LEARNING_IDENTITY_MISMATCH')
            if any(type(current[k]) is not type(session.get(k)) or current[k] != session.get(k)
                   for k in ('learner_id', 'context_version')):
                raise GatewayError('LEARNER_CONTEXT_CHANGED', 409)

        if '/passages/' in path and result.status == 200:
            try:
                await check_study_context()
            except (KeyError, ValueError, TypeError, RecursionError):
                raise GatewayError('LEARNING_UPSTREAM_INVALID', 502)
        if path == '/api/v1/textbooks/search' and result.status == 200:
            try:
                scope = strict_json(result.body)
                if scope.get('mode') == 'browse':
                    return JSONResponse(chapter_references(scope), headers={'Cache-Control':'no-store'})
                if scope.get('mode') == 'passages':
                    references = scope
                else:
                    query_body = json.dumps({'collection_name':scope['book']['collection'],
                                             'query':scope['query'],'k':SEARCH_CANDIDATE_LIMIT,'hybrid':False}).encode()
                    retrieved = await send(settings.openwebui_url, 'POST', '/api/v1/retrieval/query/doc',
                        {'Cookie':'token='+cookies['token'],'Accept':'application/json','Content-Type':'application/json'},
                        query_body, timeout=30, limit=256*1024)
                    if retrieved.status != 200:
                        raise GatewayError('TEXTBOOK_RETRIEVAL_UNAVAILABLE', 503)
                    references = bounded_references(scope, strict_json(retrieved.body), candidate_limit=SEARCH_CANDIDATE_LIMIT)
                # A browser may switch profiles while the vector query is in flight.
                await check_study_context()
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
