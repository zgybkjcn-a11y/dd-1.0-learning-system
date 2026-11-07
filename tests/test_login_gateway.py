"""Synthetic ASGI bridge only; never requests the deployed WebUI."""
from dataclasses import replace
import json
import re

import pytest
from fastapi.testclient import TestClient

from learning_service.app import create_app
from learning_service.browser_auth import CSRF_COOKIE, SESSION_COOKIE
from learning_service.gateway_http import GatewayResult
from learning_service.login_gateway import GatewaySettings, LoginNonces, GatewayError, create_gateway
from test_browser_auth import auth_env, csrf
from test_learning_service import env


class SyntheticBridge:
    evidence_mode = "synthetic_asgi"

    def __init__(self, api):
        self.api, self.calls, self.webui_status, self.webui_role = api, [], 200, "user"
        self.webui_body = None
        self.error = False
        self.identities = {"synthetic-token-a": "subject-a", "synthetic-token-b": "subject-b"}

    def send(self, upstream, method, path, headers, body=b"", **kwargs):
        self.calls.append((upstream, method, path, dict(headers), body))
        if self.error:
            raise TimeoutError("secret-in-exception synthetic-token-a")
        if upstream == "http://webui.invalid:8080":
            assert headers.keys() == {"Cookie", "Accept"}
            subject = self.identities.get(headers["Cookie"].removeprefix("token="))
            payload = self.webui_body if self.webui_body is not None else json.dumps({"id": subject, "role": self.webui_role, "token": "upstream-token-must-not-leak", "email": "private@example.invalid"}).encode()
            return GatewayResult(self.webui_status, payload, (("Set-Cookie", "token=must-not-leak; Path=/"),))
        assert upstream == "http://learning.invalid:8000"
        response = self.api.request(method, path, headers=headers, content=body, follow_redirects=False)
        return GatewayResult(response.status_code, response.content, tuple(response.headers.multi_items()))


@pytest.fixture
def gateway_env(auth_env):
    s, db, _ = auth_env
    s = replace(s, shared_learner_context_enabled=True, public_base_path="/learning")
    api = TestClient(create_app(s, db), base_url=s.browser_origin)
    settings = GatewaySettings(enabled=True, public_origin=s.browser_origin,
                               openwebui_url="http://webui.invalid:8080", learning_url="http://learning.invalid:8000",
                               assertion_secret=s.browser_auth_secret, assertion_issuer=s.browser_auth_issuer)
    transport = SyntheticBridge(api)
    client = TestClient(create_gateway(settings, transport), base_url=s.browser_origin)
    client.cookies.set("token", "synthetic-token-a")
    return s, db, settings, transport, client


def gateway_login(s, client):
    page = client.get("/learning/auth/login")
    assert page.status_code == 200
    nonce = re.search(r'name="csrf" value="([A-Za-z0-9_-]+)"', page.text)[1]
    return client.post("/learning/auth/session", data={"csrf": nonce}, headers={"Origin": s.browser_origin}, follow_redirects=False), nonce


def test_bridge_login_strips_tokens_and_binds_selected_context(gateway_env):
    s, db, settings, bridge, client = gateway_env
    response, _ = gateway_login(s, client)
    assert response.status_code == 303 and response.headers["location"] == "/learning/ui"
    assert len(response.headers.get_list("set-cookie")) == 2
    assert "upstream-token" not in str(response.headers) + response.text
    session = client.get("/learning/api/v1/auth/session").json()
    assert session["account_id"] == "acct-a" and session["context_version"] == 0 and "identity" not in session
    assert client.post("/learning/api/v1/learner-context", json={"learner_id": "learner-a", "expected_revision": 0}, headers=csrf(s, client)).json()["context_version"] == 1
    headers = {"X-Learner-Context-Version": "1", "X-Adapter-Secret": "attacker", "X-Account-Id": "acct-b", "X-Learner-Id": "learner-b", "X-Trusted-Subject": "subject-b"}
    assert client.get("/learning/api/v1/mistakes", headers=headers).status_code == 200
    forwarded = bridge.calls[-1][3]
    assert not any(k.lower() in {"x-adapter-secret", "x-account-id", "x-learner-id", "x-trusted-subject"} for k in forwarded)
    assert "token=" not in forwarded["Cookie"]
    assert "const publicBasePath = \"/learning\";" in client.get("/learning/ui").text


def test_login_csrf_replay_origin_and_token_switch_are_rejected(gateway_env):
    s, db, settings, bridge, client = gateway_env
    response, nonce = gateway_login(s, client)
    assert response.status_code == 303
    assert client.post("/learning/auth/session", data={"csrf": nonce}, headers={"Origin": s.browser_origin}).status_code == 403
    page = client.get("/learning/auth/login").text
    nonce = re.search(r'name="csrf" value="([A-Za-z0-9_-]+)"', page)[1]
    client.cookies.set("token", "synthetic-token-b")
    assert client.post("/learning/auth/session", data={"csrf": nonce}, headers={"Origin": s.browser_origin}).status_code == 403
    assert client.post("/learning/auth/session", data={"csrf": nonce}, headers={"Origin": "https://foreign.invalid"}).status_code == 403
    assert not any(call[1] == "POST" for call in bridge.calls if call[0] == settings.openwebui_url)


@pytest.mark.parametrize("change", ["missing", "other_subject", "pending", "expired", "unbound", "fault"])
def test_old_learning_cookie_cannot_survive_webui_change(gateway_env, change):
    s, db, settings, bridge, client = gateway_env
    assert gateway_login(s, client)[0].status_code == 303
    if change == "missing": client.cookies.delete("token")
    if change == "other_subject": client.cookies.set("token", "synthetic-token-b")
    if change == "pending": bridge.webui_role = "pending"
    if change == "expired": bridge.webui_status = 401
    if change == "fault": bridge.error = True
    if change == "unbound":
        with db.session(write=True) as conn:
            conn.execute("DELETE FROM identity_bindings WHERE provider='open-webui' AND subject='subject-a'")
    response = client.get("/learning/ui", follow_redirects=False)
    if change == 'missing':
        assert response.status_code == 303
        assert response.headers['location'] == '/auth?redirect=/learning/auth/login'
    else:
        assert response.status_code in {401, 503}
    assert "secret-in-exception" not in response.text
    assert not any(c[2] == "/ui" for c in bridge.calls)


@pytest.mark.parametrize("body", [b'{"id":"subject-a","id":"subject-b","role":"user"}', b'{"id":42,"role":"admin"}', b'[]', b'{bad', b'{"id":"subject-a","role":"service"}'])
def test_invalid_upstream_identity_never_mints_session(gateway_env, body):
    s, db, settings, bridge, client = gateway_env
    bridge.webui_body = body
    assert client.get("/learning/auth/login").status_code == 401
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM browser_sessions").fetchone()[0] == 0


@pytest.mark.parametrize("path,method", [("/learning/internal/bootstrap", "POST"), ("/learning/docs", "GET"), ("/learning/api/v1/auth/session", "POST"), ("/learning/api/v1/mistakes", "DELETE"), ("/learning/api/v1/mistakes%2Fextra", "GET"), ("/learning/auth/login?next=https://foreign.invalid", "GET"), ("/learning//ui", "GET")])
def test_routes_rejected_before_any_upstream_request(gateway_env, path, method):
    s, db, settings, bridge, client = gateway_env
    response = client.request(method, path, headers={"Origin": s.browser_origin})
    assert response.status_code == 404 and bridge.calls == []


def test_disabled_config_and_cookie_ambiguity_fail_closed(gateway_env):
    s, db, settings, bridge, client = gateway_env
    disabled = TestClient(create_gateway(replace(settings, enabled=False), bridge))
    assert disabled.get("/learning/ui").status_code == 503 and not bridge.calls
    response = client.get("/learning/auth/login", headers={"Cookie": "token=synthetic-token-a; token=synthetic-token-b"})
    assert response.status_code == 401 and not bridge.calls
    for changed in (replace(settings, public_origin="http://172.19.116.53:53001"), replace(settings, public_base_path="/learning/../"), replace(settings, assertion_secret=""), replace(settings, openwebui_url="http://user:pass@webui.invalid")):
        assert not changed.configured()


def test_nonce_bound_capacity_expiry_and_restart():
    store = LoginNonces(capacity=1)
    nonce = store.issue("token", "subject")
    assert "token" not in repr(store.values)
    with pytest.raises(GatewayError): store.issue("token", "subject")
    with pytest.raises(GatewayError): LoginNonces().consume(nonce, "token", "subject")
    digest = store.digest(nonce)
    a, b, _ = store.values[digest]
    store.values[digest] = (a, b, 0)
    with pytest.raises(GatewayError): store.consume(nonce, "token", "subject")
