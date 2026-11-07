#!/usr/bin/env python3
"""Chromium gateway/prefix/context probe with synthetic identities and ASGI routing."""
from __future__ import annotations

import argparse
from http.cookies import SimpleCookie
import io
import json
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning_service.app import create_app
from learning_service.browser_auth import CSRF_COOKIE, SESSION_COOKIE
from learning_service.config import Settings
from learning_service.db import Database
from learning_service.gateway_http import GatewayResult
from learning_service.identity_admin import apply_identity, plan_identity
from learning_service.login_gateway import GatewaySettings, create_gateway


def run(output: Path) -> dict:
    if output.exists():
        raise ValueError("choose a new output; existing evidence is preserved")
    work = ROOT/"learning_data/verification"
    work.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="reuse-gateway-", dir=work))
    origin = "https://learning.example.invalid"
    s = Settings(run_dir, run_dir/"learning.db", run_dir/"attachments", "synthetic-admin", "synthetic-adapter", False,
                 browser_auth_enabled=True, browser_auth_secret="synthetic-gateway-key-0123456789abcdef",
                 browser_auth_issuer="synthetic-login-gateway", browser_origin=origin,
                 shared_learner_context_enabled=True, public_base_path="/learning")
    manifest = {"format": "dd-learning-identities-v1", "initialize_math": True,
                "accounts": [{"id": "synthetic-account"}],
                "learners": [{"id": "synthetic-learner-" + a, "display_name": "合成学习者 " + a.upper(), "timezone": "Asia/Shanghai", "curriculum_id": "math-g7-v1"} for a in ("a", "b")],
                "bindings": [{"account_id": "synthetic-account", "provider": "open-webui", "issuer": "open-webui", "subject": "synthetic-subject"}],
                "grants": [{"account_id": "synthetic-account", "learner_id": "synthetic-learner-" + a, "role": "guardian"} for a in ("a", "b")],
                "revocations": [], "unbinds": []}
    plan = plan_identity(manifest, s.db_path, "synthetic-operator")
    apply_identity(manifest, s.db_path, "synthetic-operator", plan["plan_sha256"])
    db = Database(s.db_path)
    api = TestClient(create_app(s, db), base_url=origin)
    class Transport:
        evidence_mode = "synthetic_asgi"
        def send(self, upstream, method, path, headers, body=b"", **kwargs):
            if upstream == "http://webui.invalid:8080":
                assert method == "GET" and path == "/api/v1/auths/" and headers["Cookie"] == "token=synthetic-token"
                return GatewayResult(200, b'{"id":"synthetic-subject","role":"user","token":"never-forward"}')
            assert upstream == "http://learning.invalid:8000"
            response = api.request(method, path, content=body, headers=headers, follow_redirects=False)
            return GatewayResult(response.status_code, response.content, tuple(response.headers.multi_items()))
    g = GatewaySettings(enabled=True, public_origin=origin, openwebui_url="http://webui.invalid:8080", learning_url="http://learning.invalid:8000",
                        assertion_secret=s.browser_auth_secret, assertion_issuer=s.browser_auth_issuer)
    gateway = TestClient(create_gateway(g, Transport()), base_url=origin)
    records = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                                    args=["--no-sandbox", "--disable-background-networking", "--disable-component-update"])
        for width in (390, 1280):
            context = browser.new_context(viewport={"width": width, "height": 900}, service_workers="block")
            context.add_cookies([{"name": "token", "value": "synthetic-token", "url": origin, "secure": True, "httpOnly": True, "sameSite": "Strict"}])
            calls, errors, unexpected, redirect_targets = [], [], [], []
            def handler(route):
                request = route.request
                parsed = urlsplit(request.url)
                if parsed.scheme + "://" + parsed.netloc != origin:
                    unexpected.append(parsed.netloc); route.abort(); return
                if parsed.path == "/favicon.ico":
                    route.fulfill(status=404); return
                if not parsed.path.startswith("/learning/"):
                    unexpected.append(parsed.path); route.abort(); return
                response = gateway.request(request.method, parsed.path + ("?" + parsed.query if parsed.query else ""), content=request.post_data_buffer,
                                           headers=request.all_headers(), follow_redirects=False)
                calls.append({"path": parsed.path, "method": request.method, "status": response.status_code})
                if response.status_code >= 400:
                    try:
                        calls[-1]["error_code"] = response.json().get("error", {}).get("code")
                    except ValueError:
                        pass
                for raw in response.headers.get_list("set-cookie"):
                    cookies = SimpleCookie(); cookies.load(raw)
                    for name, cookie in cookies.items():
                        assert name in {SESSION_COOKIE, CSRF_COOKIE}
                        if not cookie.value or cookie["max-age"] == "0":
                            context.clear_cookies(name=name)
                        else:
                            context.add_cookies([{"name": name, "value": cookie.value, "url": origin, "secure": True, "httpOnly": name == SESSION_COOKIE, "sameSite": "Strict"}])
                if response.status_code == 303:
                    # Chromium's fulfilled navigation redirects escape this
                    # interception path. Verify the fixed ASGI redirect and
                    # explicitly navigate, so no URL falls through to network.
                    assert response.headers["location"] == "/learning/ui"
                    redirect_targets.append(response.headers["location"])
                    route.fulfill(status=200, body="synthetic login exchange completed", headers={"content-type": "text/plain"})
                    return
                route.fulfill(status=response.status_code, body=response.content,
                              headers={k:v for k,v in response.headers.items() if k not in {"content-length", "set-cookie"}})
            context.route("**/*", handler)
            page = context.new_page(); page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(origin + "/learning/auth/login", wait_until="domcontentloaded")
            page.get_by_role("button", name="进入学习工作区").click()
            page.wait_for_url("**/learning/auth/session", timeout=5000)
            assert redirect_targets == ["/learning/ui"], calls
            page.goto(origin + redirect_targets[0], wait_until="domcontentloaded")
            page.wait_for_function("document.getElementById('learner').options.length === 3")
            page.locator("#learner").select_option("synthetic-learner-a")
            page.wait_for_function("document.querySelector('main').inert === false")
            assert page.locator("#account").input_value() == "synthetic-account"
            assert page.locator("#account").get_attribute("readonly") is not None
            page.locator("#manualQuestion").fill("-3 - (-5) = ?")
            page.locator("#manualStudentAnswer").fill("-8")
            page.locator("#manualCorrectAnswer").fill("2")
            with page.expect_response(lambda r: r.url.endswith("/api/v1/mistakes/manual")) as saved:
                page.locator("#saveManualMistake").click()
            assert saved.value.status == 201
            page.wait_for_function("document.getElementById('uploadStatus').textContent.includes('已加入错题本')")
            # A tiny synthetic image exercises multipart and authenticated page
            # content routing; no OCR, four-format parsing or P0 repetition.
            pixels = io.BytesIO(); Image.new("RGB", (32, 32), "white").save(pixels, format="PNG")
            page.locator("#file").set_input_files({"name": "synthetic.png", "mimeType": "image/png", "buffer": pixels.getvalue()})
            with page.expect_response(lambda r: "/api/v1/documents" in r.url and r.request.method == "POST") as upload:
                page.locator("#upload").click()
            assert upload.value.status == 201
            document = upload.value.json()
            with db.session() as conn:
                page_id = conn.execute("SELECT id FROM source_pages WHERE document_id=?", (document["document_id"],)).fetchone()[0]
            status = page.evaluate("async id => {const csrf=document.cookie.split('; ').find(p=>p.startsWith('__Host-dd_learning_csrf=')).split('=')[1]; const session=await (await fetch('/learning/api/v1/auth/session')).json(); return (await fetch('/learning/api/v1/source-pages/'+id+'/content',{headers:{'X-Learner-Context-Version':String(session.context_version),'X-CSRF-Token':csrf}})).status;}", page_id)
            assert status == 200
            other = context.new_page(); other.on("pageerror", lambda error: errors.append(str(error)))
            other.goto(origin + "/learning/ui", wait_until="domcontentloaded")
            other.wait_for_function("document.querySelector('main').inert === false")
            other.locator("#learner").select_option("synthetic-learner-b")
            other.wait_for_function("document.querySelector('main').inert === false")
            with page.expect_response(lambda r: r.url.endswith("/api/v1/mistakes")) as stale:
                page.locator("#loadMistakes").click()
            assert stale.value.status == 409
            page.wait_for_function("document.querySelector('main').inert === true")
            page.reload(); page.wait_for_function("document.querySelector('main').inert === false")
            assert page.locator("#learner").input_value() == "synthetic-learner-b"
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            assert not overflow and not errors and not unexpected
            with page.expect_response(lambda r: r.url == origin + "/learning/ui") as logged_out:
                page.locator("#loadLearners").click()
            assert logged_out.value.status == 401
            assert not any(c["name"] in {SESSION_COOKIE, CSRF_COOKIE} for c in context.cookies())
            records.append({"width": width, "login_form_asgi": True, "prefixed_manual_upload_and_content": True,
                            "asgi_redirect_status": 303, "redirect_follow_emulated_by_probe": True,
                            "stale_tab_read_status": 409, "refresh_shared_context": True, "logout": True,
                            "horizontal_overflow": overflow, "page_errors": errors, "unexpected_requests": unexpected, "requests": calls})
            context.close()
        browser.close()
    with db.session() as conn:
        schema = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        live = conn.execute("SELECT COUNT(*) FROM provider_calls WHERE evidence_mode='live_http'").fetchone()[0]
    result = {"evidence_kind": "synthetic_chromium_gateway_asgi", "schema_revision": schema, "viewports": records,
              "real_openwebui_authentication": False, "real_tls_or_tool_callback": False, "live_provider_calls": live,
              "network_boundary": "all page URLs intercepted; WebUI auth response synthesized; API/gateway in process"}
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--output", type=Path, required=True)
    result = run(parser.parse_args().output)
    print(json.dumps({"evidence_kind": result["evidence_kind"], "schema_revision": result["schema_revision"], "viewports": len(result["viewports"]), "live_provider_calls": result["live_provider_calls"]}))
