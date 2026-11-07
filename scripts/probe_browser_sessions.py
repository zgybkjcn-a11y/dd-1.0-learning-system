#!/usr/bin/env python3
"""Chromium + synthetic session/ASGI probe, with all browser traffic intercepted."""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import secrets
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from learning_service.app import create_app
from learning_service.browser_auth import CSRF_COOKIE, SESSION_COOKIE
from learning_service.config import Settings
from learning_service.db import Database, utc_now


def run(output: Path) -> dict:
    if output.exists():
        raise ValueError("probe output already exists; existing evidence is preserved")
    work = ROOT/"learning_data/verification"
    work.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="browser-auth-", dir=work))
    s = Settings(run_dir, run_dir/"learning.db", run_dir/"attachments", "synthetic-admin", "synthetic-adapter", False,
                 browser_auth_enabled=True, browser_auth_secret="synthetic-gateway-key-0123456789abcdef",
                 browser_auth_issuer="synthetic-login-gateway", browser_origin="https://learning.example.invalid")
    db = Database(s.db_path)
    with db.session(write=True) as conn:
        for suffix in ("a", "b"):
            conn.execute("INSERT INTO accounts(id,created_at) VALUES (?,?)", ("synthetic-account-"+suffix, utc_now()))
            conn.execute("INSERT INTO identity_bindings(id,account_id,provider,issuer,subject,created_at) VALUES (?,?,?,?,?,?)",
                         ("binding-"+suffix, "synthetic-account-"+suffix, "open-webui", "open-webui", "synthetic-subject-"+suffix, utc_now()))
            conn.execute("INSERT INTO learners(id,display_name,created_at) VALUES (?,?,?)", ("synthetic-learner-"+suffix, "合成学习者 "+suffix.upper(), utc_now()))
            conn.execute("INSERT INTO learner_access(account_id,learner_id,role,created_at) VALUES (?,?,?,?)",
                         ("synthetic-account-"+suffix, "synthetic-learner-"+suffix, "student", utc_now()))
    app = create_app(s, db)
    records = []
    with TestClient(app, base_url=s.browser_origin) as client, sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                                    args=["--no-sandbox", "--disable-background-networking", "--disable-component-update"])
        for width in (390, 1280):
            now = int(time.time())
            claims = {"iss":s.browser_auth_issuer, "aud":s.browser_auth_audience, "sub":"synthetic-subject-a",
                      "iat":now, "exp":now+90, "jti":secrets.token_urlsafe(12)}
            def encode(value):
                return base64.urlsafe_b64encode(value).rstrip(b"=").decode()
            head = encode(b'{"alg":"HS256","typ":"JWT"}')
            body = encode(json.dumps(claims).encode())
            sig = encode(hmac.new(s.browser_auth_secret.encode(), (head+"."+body).encode(), hashlib.sha256).digest())
            login = client.post("/api/v1/auth/session", headers={"Authorization":"Bearer "+head+"."+body+"."+sig, "Origin":s.browser_origin})
            assert login.status_code == 201
            context = browser.new_context(viewport={"width":width, "height":900}, service_workers="block")
            context.add_cookies([
                {"name":name, "value":client.cookies.get(name), "url":s.browser_origin, "secure":True,
                 "httpOnly":name == SESSION_COOKIE, "sameSite":"Strict"}
                for name in (SESSION_COOKIE, CSRF_COOKIE)
            ])
            calls, errors, unexpected = [], [], []
            def handler(route):
                request = route.request
                parsed = urlsplit(request.url)
                if parsed.scheme+"://"+parsed.netloc != s.browser_origin:
                    unexpected.append(parsed.scheme+"://"+parsed.netloc)
                    route.abort()
                    return
                result = client.request(request.method, parsed.path + ("?"+parsed.query if parsed.query else ""),
                                        content=request.post_data_buffer, headers=request.all_headers())
                calls.append({"path":parsed.path, "method":request.method, "status":result.status_code})
                headers = {k:v for k,v in result.headers.items() if k not in {"content-length","set-cookie"}}
                route.fulfill(status=result.status_code, body=result.content, headers=headers)
            context.route("**/*", handler)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(s.browser_origin+"/ui", wait_until="domcontentloaded")
            page.wait_for_function("document.querySelector('main').inert === false")
            assert page.locator("#account").input_value() == "synthetic-account-a"
            assert page.locator("#account").get_attribute("readonly") is not None
            assert page.locator("#learner").input_value() == "synthetic-learner-a"
            page.locator("#manualQuestion").fill("-3 - (-5) = ?")
            page.locator("#manualStudentAnswer").fill("-8")
            page.locator("#manualCorrectAnswer").fill("2")
            with page.expect_response(lambda r: r.url.endswith("/api/v1/mistakes/manual")) as saved:
                page.locator("#saveManualMistake").click()
            assert saved.value.status == 201
            page.wait_for_function("document.getElementById('uploadStatus').textContent.includes('已加入错题本')")
            page.locator("#loadMistakes").click()
            page.wait_for_function("document.getElementById('mistakes').textContent.includes('-3 - (-5)')")
            with page.expect_response(lambda r: r.url.endswith("/api/v1/review-tasks")) as review:
                page.locator("#loadReview").click()
            assert review.value.status == 200
            denied = page.evaluate("async () => (await fetch('/api/v1/mistakes', {headers:{'X-Learner-Id':'synthetic-learner-b'}})).status")
            assert denied == 404
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            assert not overflow and not errors and not unexpected
            page.locator("#loadLearners").click()
            page.wait_for_function("document.querySelector('main').inert === true && document.getElementById('loadLearners').disabled")
            assert client.get("/api/v1/auth/session").status_code == 401
            records.append({"width":width, "authenticated_account_readonly":True, "learner_selected_from_server":True,
                            "csrf_manual_write":True, "cross_learner_status":denied, "logout_revoked":True,
                            "horizontal_overflow":overflow, "page_errors":errors, "unexpected_origins":unexpected,
                            "requests":calls})
            context.close()
        browser.close()
    with db.session() as conn:
        summary = {"synthetic_mistakes":conn.execute("SELECT COUNT(*) FROM mistake_entries").fetchone()[0],
                   "live_provider_calls":conn.execute("SELECT COUNT(*) FROM provider_calls WHERE evidence_mode='live_http'").fetchone()[0]}
        schema_revision = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
    result = {"evidence_kind":"synthetic_browser_asgi_probe", "transport":"in-process ASGI routing; every browser URL intercepted",
              "real_gateway_tls_or_open_webui_callback_verified":False, "real_model_or_ocr_calls":False,
              "data_kind":"synthetic_only", "schema_revision":schema_revision, "viewports":records, "database":summary}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({"evidence_kind":result["evidence_kind"], "viewports":len(result["viewports"]), **result["database"]}))


if __name__ == "__main__":
    main()
