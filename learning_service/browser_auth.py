"""Browser sessions minted only from short-lived signed login-gateway assertions.

The gateway must first authenticate the human. This module never accepts an
account/role claim, auto-provisions a binding, or exposes a shared secret to
the browser. Assertions are single-use; opaque session/CSRF tokens are hashed.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from starlette.requests import Request

from .config import Settings
from .db import Database, new_id, utc_now
from .provider_usage import safe_reference


SESSION_COOKIE = "__Host-dd_learning_session"
CSRF_COOKIE = "__Host-dd_learning_csrf"


class AuthError(Exception):
    def __init__(self, code: str, status: int = 401):
        self.code, self.status = code, status
        super().__init__(code)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _decode(segment: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", segment):
        raise ValueError("invalid encoding")
    return base64.b64decode(segment + "=" * (-len(segment) % 4), altchars=b"-_", validate=True)


def _json(value: bytes):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = item
        return result
    return json.loads(value, object_pairs_hook=pairs)


class BrowserSessions:
    def __init__(self, settings: Settings, db: Database):
        self.settings, self.db = settings, db

    def configured(self) -> bool:
        s = self.settings
        try:
            p = urlsplit(s.browser_origin)
            origin_valid = bool(p.scheme == "https" and p.hostname and not p.username and not p.password
                                and not p.path and not p.query and not p.fragment and p.port in (None, 443)
                                and s.browser_origin.isascii() and not any(c.isspace() for c in s.browser_origin))
        except ValueError:
            origin_valid = False
        return bool(s.browser_auth_enabled and len(s.browser_auth_secret) >= 32
                    and not any(x in s.browser_auth_secret.lower() for x in ("replace", "placeholder", "changeme"))
                    and s.browser_auth_secret not in (s.admin_secret, s.adapter_secret)
                    and safe_reference(s.browser_auth_issuer) and safe_reference(s.browser_auth_audience)
                    and safe_reference(s.browser_identity_provider) and safe_reference(s.browser_identity_issuer)
                    and origin_valid and 300 <= s.browser_session_ttl_seconds <= 28800)

    def _require_configured(self):
        if not self.configured():
            raise AuthError("BROWSER_AUTH_NOT_CONFIGURED", 503)

    def require_origin(self, request: Request):
        if request.headers.get("Origin") != self.settings.browser_origin:
            raise AuthError("BROWSER_ORIGIN_REJECTED", 403)

    def _assertion(self, token: str) -> dict:
        try:
            if len(token) > 4096:
                raise ValueError("oversized assertion")
            head, body, signature = token.split(".")
            header = _json(_decode(head))
            claims = _json(_decode(body))
            if header != {"alg": "HS256", "typ": "JWT"}:
                raise ValueError("unsupported algorithm")
            expected = hmac.new(self.settings.browser_auth_secret.encode(), (head + "." + body).encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(_decode(signature), expected):
                raise ValueError("bad signature")
            if not isinstance(claims, dict) or set(claims) != {"iss", "aud", "sub", "iat", "exp", "jti"}:
                raise ValueError("invalid claims")
            if claims["iss"] != self.settings.browser_auth_issuer or claims["aud"] != self.settings.browser_auth_audience:
                raise ValueError("wrong issuer or audience")
            now = int(time.time())
            if (type(claims["iat"]) is not int or type(claims["exp"]) is not int
                    or not now - 120 <= claims["iat"] <= now + 5
                    or not now < claims["exp"] <= claims["iat"] + 120
                    or not safe_reference(claims["sub"]) or not safe_reference(claims["jti"])):
                raise ValueError("invalid lifetime or subject")
            return claims
        except (ValueError, TypeError, UnicodeDecodeError, RecursionError):
            raise AuthError("GATEWAY_ASSERTION_INVALID")

    def exchange(self, request: Request) -> tuple[str, str, str]:
        self._require_configured()
        self.require_origin(request)
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise AuthError("GATEWAY_ASSERTION_REQUIRED")
        claims = self._assertion(authorization[7:])
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(seconds=self.settings.browser_session_ttl_seconds)).replace(microsecond=0).isoformat()
        with self.db.session(write=True) as conn:
            row = conn.execute("SELECT account_id FROM identity_bindings WHERE provider=? AND issuer=? AND subject=?",
                               (self.settings.browser_identity_provider, self.settings.browser_identity_issuer, claims["sub"])).fetchone()
            # One household, one parent: possession of the setup code plus a
            # signed WebUI login can claim only the pre-created family account.
            code = self.settings.family_setup_code
            if (not row and len(code) >= 32
                    and hmac.compare_digest(request.headers.get('X-Family-Setup-Code', ''), code)
                    and not conn.execute('SELECT 1 FROM identity_bindings LIMIT 1').fetchone()
                    and not conn.execute("SELECT 1 FROM audit_events WHERE id='family-parent-claimed'").fetchone()
                    and conn.execute("SELECT 1 FROM accounts WHERE id='family-parent'").fetchone()):
                conn.execute('INSERT INTO identity_bindings(id,account_id,provider,issuer,subject,created_at) VALUES (?,?,?,?,?,?)',
                             (new_id('binding'), 'family-parent', self.settings.browser_identity_provider,
                              self.settings.browser_identity_issuer, claims['sub'], utc_now()))
                conn.execute("INSERT INTO audit_events(id,account_id,operation,resource_type,resource_id,result,metadata_json,created_at) VALUES ('family-parent-claimed','family-parent','claim_family_parent','account','family-parent','accepted','{}',?)", (utc_now(),))
                row = {'account_id': 'family-parent'}
            if not row:
                raise AuthError("UNKNOWN_IDENTITY")
            conn.execute("DELETE FROM gateway_assertions WHERE expires_at<?", (int(time.time()),))
            jti_hash = _hash(claims["iss"] + ":" + claims["jti"])
            if conn.execute("SELECT 1 FROM gateway_assertions WHERE jti_hash=?", (jti_hash,)).fetchone():
                raise AuthError("GATEWAY_ASSERTION_REPLAY", 409)
            conn.execute("INSERT INTO gateway_assertions(jti_hash,expires_at) VALUES (?,?)", (jti_hash, claims["exp"]))
            previous = request.cookies.get(SESSION_COOKIE, "")
            if previous:
                conn.execute("UPDATE browser_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL", (utc_now(), _hash(previous)))
            context = conn.execute("SELECT learner_id FROM account_contexts WHERE account_id=?", (row["account_id"],)).fetchone()
            conn.execute("INSERT INTO browser_sessions(id,token_hash,csrf_hash,account_id,provider,issuer,subject,learner_id,expires_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (new_id("session"), _hash(token), _hash(csrf), row["account_id"], self.settings.browser_identity_provider,
                          self.settings.browser_identity_issuer, claims["sub"], context["learner_id"] if context and self.settings.shared_learner_context_enabled else None, expires, utc_now()))
        return token, csrf, expires

    def authenticate(self, request: Request) -> dict:
        self._require_configured()
        token = request.cookies.get(SESSION_COOKIE, "")
        if not token or len(token) > 256:
            raise AuthError("BROWSER_LOGIN_REQUIRED")
        with self.db.session() as conn:
            row = conn.execute("SELECT s.* FROM browser_sessions s JOIN identity_bindings b ON b.account_id=s.account_id AND b.provider=s.provider AND b.issuer=s.issuer AND b.subject=s.subject WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>?",
                               (_hash(token), utc_now())).fetchone()
        if not row:
            raise AuthError("BROWSER_SESSION_INVALID")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            self.require_origin(request)
            header = request.headers.get("X-CSRF-Token", "")
            cookie = request.cookies.get(CSRF_COOKIE, "")
            if not header or len(header) > 256 or not secrets.compare_digest(header, cookie) or not secrets.compare_digest(_hash(header), row["csrf_hash"]):
                raise AuthError("BROWSER_CSRF_REJECTED", 403)
        return dict(row)

    def logout(self, request: Request):
        session = self.authenticate(request)
        with self.db.session(write=True) as conn:
            conn.execute("UPDATE browser_sessions SET revoked_at=? WHERE id=?", (utc_now(), session["id"]))

