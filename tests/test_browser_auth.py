from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from learning_service.app import create_app
from learning_service.backup import backup_data, restore_data
from learning_service.browser_auth import CSRF_COOKIE, SESSION_COOKIE
from learning_service.db import utc_now
from test_learning_service import env


@pytest.fixture
def auth_env(env):
    s, db, _ = env
    s = replace(s, dev_mode=False, browser_auth_enabled=True, browser_auth_secret="synthetic-gateway-key-0123456789abcdef",
                browser_auth_issuer="synthetic-login-gateway", browser_origin="https://learning.example.invalid")
    with db.session(write=True) as conn:
        for account, subject in (("acct-a", "subject-a"), ("acct-b", "subject-b")):
            conn.execute("INSERT INTO identity_bindings(id,account_id,provider,issuer,subject,created_at) VALUES (?,?,?,?,?,?)",
                         ("binding-" + subject, account, "open-webui", "open-webui", subject, utc_now()))
    return s, db, TestClient(create_app(s, db), base_url=s.browser_origin)


def assertion(settings, *, changes=None, header=None, raw_body=None):
    now = int(time.time())
    payload = {"iss": settings.browser_auth_issuer, "aud": settings.browser_auth_audience,
               "sub": "subject-a", "iat": now, "exp": now + 90, "jti": "synthetic-jti"}
    payload.update(changes or {})
    def encode(data):
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
    head = encode(json.dumps(header or {"alg": "HS256", "typ": "JWT"}).encode())
    body = encode(raw_body.encode() if raw_body else json.dumps(payload).encode())
    signature = hmac.new(settings.browser_auth_secret.encode(), (head + "." + body).encode(), hashlib.sha256).digest()
    return head + "." + body + "." + encode(signature)


def login(s, client, **kwargs):
    return client.post("/api/v1/auth/session", headers={"Authorization": "Bearer " + assertion(s, **kwargs), "Origin": s.browser_origin})


def csrf(s, client):
    return {"Origin": s.browser_origin, "X-CSRF-Token": client.cookies.get(CSRF_COOKIE)}


@pytest.mark.parametrize("mutation", ["signature", "issuer", "audience", "expired", "future", "role", "algorithm", "bool_time", "duplicate", "unknown"])
def test_invalid_gateway_assertions_do_not_create_accounts_or_sessions(auth_env, mutation):
    s, db, client = auth_env
    now = int(time.time())
    changes, header, raw_body = {}, None, None
    if mutation == "issuer": changes["iss"] = "other-gateway"
    if mutation == "audience": changes["aud"] = "another-service"
    if mutation == "expired": changes.update(iat=now-120, exp=now-1)
    if mutation == "future": changes.update(iat=now+60, exp=now+100)
    if mutation == "role": changes["role"] = "admin"
    if mutation == "algorithm": header = {"alg": "none", "typ": "JWT"}
    if mutation == "bool_time": changes["iat"] = True
    if mutation == "duplicate": raw_body = '{"sub":"subject-a","sub":"subject-b"}'
    if mutation == "unknown": changes["sub"] = "unbound-subject"
    token = assertion(s, changes=changes, header=header, raw_body=raw_body)
    if mutation == "signature": token = token.rsplit(".", 1)[0] + ".invalid"
    result = client.post("/api/v1/auth/session", headers={"Authorization":"Bearer " + token, "Origin":s.browser_origin})
    assert result.status_code == 401
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM browser_sessions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 2


def test_session_cookies_hashes_replay_and_spoofed_headers(auth_env):
    s, db, client = auth_env
    response = login(s, client)
    assert response.status_code == 201
    cookies = response.headers.get_list("set-cookie")
    assert all("Secure" in c and "SameSite=strict" in c and "Path=/" in c for c in cookies)
    assert "HttpOnly" in cookies[0]
    assert response.headers["cache-control"] == "no-store"
    with db.session() as conn:
        row = conn.execute("SELECT * FROM browser_sessions").fetchone()
    assert row["token_hash"] != client.cookies.get(SESSION_COOKIE) and row["csrf_hash"] != client.cookies.get(CSRF_COOKIE)
    assert login(s, client).status_code == 409
    response = client.get("/api/v1/learners", headers={"X-Account-Id":"acct-b", "X-Trusted-Subject":"subject-b", "X-Learner-Id":"learner-a"})
    assert response.status_code == 200 and [x["id"] for x in response.json()["items"]] == ["learner-a"]
    assert client.get("/api/v1/learners/learner-b/progress").status_code == 404
    assert client.get("/api/v1/admin/metrics", headers={"X-Learner-Id":"learner-a"}).status_code == 200
    with db.session(write=True) as conn:
        conn.execute("UPDATE learner_access SET role='student' WHERE account_id='acct-a'")
    assert client.get("/api/v1/admin/metrics", headers={"X-Learner-Id":"learner-a"}).status_code == 403


def test_csrf_origin_learner_selection_logout_and_stale_cookie(auth_env):
    s, db, client = auth_env
    assert login(s, client).status_code == 201
    assert client.post("/api/v1/learner-context", json={"learner_id":"learner-a"}).status_code == 403
    bad = csrf(s, client); bad["Origin"] = "https://outside.example.invalid"
    assert client.post("/api/v1/learner-context", json={"learner_id":"learner-a"}, headers=bad).status_code == 403
    assert client.post("/api/v1/learner-context", json={"learner_id":"learner-b"}, headers=csrf(s, client)).status_code == 404
    assert client.post("/api/v1/learner-context", json={"learner_id":"learner-a"}, headers=csrf(s, client)).status_code == 200
    assert client.get("/api/v1/auth/session").json()["learner_id"] == "learner-a"
    token = client.cookies.get(SESSION_COOKIE)
    assert client.post("/api/v1/auth/logout", headers=csrf(s, client)).status_code == 200
    assert client.get("/api/v1/auth/session", headers={"Cookie":SESSION_COOKIE + "=" + token}).status_code == 401
    with db.session() as conn:
        assert conn.execute("SELECT revoked_at FROM browser_sessions").fetchone()[0] is not None


def test_revoked_access_and_secure_ui_have_no_client_identity_authority(auth_env):
    s, db, client = auth_env
    assert login(s, client).status_code == 201
    body = client.get("/ui").text
    assert "const browserSessionMode = true;" in body and '<input id="account" readonly>' in body
    assert '<select id="learner">' in body and "synthetic-gateway-key" not in body
    with db.session(write=True) as conn:
        conn.execute("UPDATE learner_access SET active=0 WHERE account_id='acct-a'")
    assert client.get("/api/v1/mistakes", headers={"X-Learner-Id":"learner-a"}).status_code == 404


def test_disabled_or_incomplete_auth_never_mints_session(auth_env):
    s, db, _ = auth_env
    for changed in (replace(s, browser_auth_enabled=False), replace(s, browser_auth_secret=s.adapter_secret), replace(s, browser_origin="http://insecure.invalid")):
        client = TestClient(create_app(changed, db), base_url=s.browser_origin)
        assert login(changed, client).status_code == 503


def test_restore_revokes_browser_sessions_and_pauses_provider_dispatch(auth_env, tmp_path):
    s, db, client = auth_env
    assert login(s, client).status_code == 201
    token = client.cookies.get(SESSION_COOKIE)
    backup_data(s.data_dir, tmp_path / "session-backup")
    target = tmp_path / "restored"
    restore_data(tmp_path / "session-backup", target)
    restored = replace(s, data_dir=target, db_path=target/"learning.db", attachment_dir=target/"attachments")
    client = TestClient(create_app(restored), base_url=s.browser_origin)
    assert client.get("/api/v1/auth/session", headers={"Cookie":SESSION_COOKIE + "=" + token}).status_code == 401
    with client.app.state.db.session() as conn:
        assert conn.execute("SELECT paused FROM provider_control").fetchone()[0] == 1
