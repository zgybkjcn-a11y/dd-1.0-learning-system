#!/usr/bin/env python3
"""W04/W06 changed-workbench probe; every URL is intercepted and every identity is synthetic."""
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
from learning_service.app import create_app, run_worker_once
from learning_service.db import json_dumps, utc_now
from learning_service.providers import ProviderResult
import importlib
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
    run_dir = Path(tempfile.mkdtemp(prefix="reuse-workbench-", dir=work))
    origin = "https://learning.example.invalid"
    s = Settings(run_dir, run_dir/"learning.db", run_dir/"attachments", "synthetic-admin", "synthetic-adapter", False,
                 browser_auth_enabled=True, browser_auth_secret="synthetic-gateway-key-0123456789abcdef",
                 browser_auth_issuer="synthetic-login-gateway", browser_origin=origin,
                 shared_learner_context_enabled=True, public_base_path="/learning")
    manifest = {"format": "dd-learning-identities-v1", "initialize_math": True,
                "accounts": [{"id": "synthetic-account"}],
                "learners": [{"id": "synthetic-learner-" + a, "display_name": "合成学习者 " + a.upper(), "timezone": "Asia/Shanghai", "curriculum_id": "math-g7-v1"} for a in ("a", "b")],
                "bindings": [{"account_id": "synthetic-account", "provider": "open-webui", "issuer": "open-webui", "subject": "synthetic-subject"}],
                "grants": [{"account_id": "synthetic-account", "learner_id": "synthetic-learner-" + a, "role": "admin" if a == "a" else "guardian"} for a in ("a", "b")],
                "revocations": [], "unbinds": []}
    plan = plan_identity(manifest, s.db_path, "synthetic-operator")
    apply_identity(manifest, s.db_path, "synthetic-operator", plan["plan_sha256"])
    db = Database(s.db_path)
    with db.session(write=True) as conn:
        objective_id = conn.execute("SELECT id FROM review_objectives LIMIT 1").fetchone()[0]
        conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES ('synthetic-source','shared','approved',?,?)", (objective_id, utc_now(),))
        content = {'template_id':'signed_number_subtraction','prompt':'-3 - (-5) = ?', 'parameters':{'start':-3,'subtrahend':-5},'domain':'integers','unit':None}
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES ('synthetic-source-v1','synthetic-source',1,?,?,'exact-text-v1','approved',?)", (json_dumps(content), '{"accepted":["2"]}', utc_now()))
    class SyntheticVariant:
        def generate(self, snapshot):
            draft = {'objective_id':snapshot['objective_id'],'source_question_version_id':snapshot['source_question_version_id'],
                     'content':{'template_id':'signed_number_subtraction','prompt':'-4 - (-7) = ?', 'parameters':{'start':-4,'subtrahend':-7},'domain':'integers','unit':None},
                     'answer_key':{'accepted':['3']},'validator_version':'exact-text-v1','approval':'draft'}
            return ProviderResult('synthetic-variant','needs_review',{'draft':draft,'approval_required':True},{'external_call':False,'mode':'synthetic_fixture'})
    importlib.import_module('learning_service.app').variant_provider = lambda *_: SyntheticVariant()
    api = TestClient(create_app(s, db), base_url=origin)
    class Transport:
        evidence_mode = "synthetic_asgi"
        def send(self, upstream, method, path, headers, body=b"", **kwargs):
            if upstream == "http://webui.invalid:8080":
                assert method == "GET" and path == "/api/v1/auths/"
                assert headers["Cookie"] in {"token=synthetic-token", "token=synthetic-other-token"}
                subject = "synthetic-subject" if headers["Cookie"] == "token=synthetic-token" else "synthetic-other-subject"
                return GatewayResult(200, json.dumps({"id":subject,"role":"user","token":"never-forward"}).encode())
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
            print('viewport', width, flush=True)
            context = browser.new_context(viewport={"width": width, "height": 900}, service_workers="block")
            context.add_cookies([{"name": "token", "value": "synthetic-token", "url": origin, "secure": True, "httpOnly": True, "sameSite": "Strict"}])
            calls, errors, unexpected, redirect_targets = [], [], [], []
            delayed = {'arm':False,'response':None,'route':None}
            context.add_init_script("window.revokedUrls=[];const revoke=URL.revokeObjectURL;URL.revokeObjectURL=(url)=>{window.revokedUrls.push(url);revoke.call(URL,url);};")
            def handler(route):
                request = route.request
                parsed = urlsplit(request.url)
                if parsed.scheme + "://" + parsed.netloc != origin:
                    unexpected.append(parsed.netloc); route.abort(); return
                if parsed.path == "/favicon.ico":
                    route.fulfill(status=404); return
                if not parsed.path.startswith("/learning/"):
                    unexpected.append(parsed.path); route.abort(); return
                if '/api/v1/attempts/' in parsed.path and request.method == 'GET':
                    run_worker_once(db, s)
                response = gateway.request(request.method, parsed.path + ("?" + parsed.query if parsed.query else ""), content=request.post_data_buffer,
                                           headers=request.all_headers(), follow_redirects=False)
                calls.append({"path": parsed.path, "method": request.method, "status": response.status_code})
                if delayed['arm'] and parsed.path == '/learning/api/v1/mistakes':
                    delayed.update(arm=False,response=response,route=route)
                    return
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
            context.set_default_timeout(7000)
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
            page.wait_for_function("document.getElementById('today').textContent.includes('开始测验')")
            print('today-start', flush=True)
            page.locator('#today button').first.click()
            page.wait_for_function("document.getElementById('testPrompt').textContent.includes('-3')")
            first_session = page.locator('#session').input_value()
            page.locator('#answer').fill('PRIVATE_UNSUBMITTED_ANSWER')
            print('reload', flush=True)
            page.reload()
            page.wait_for_function("document.getElementById('testPrompt').textContent.includes('-3')")
            assert page.locator('#session').input_value() == first_session and page.locator('#answer').input_value() == ''
            print('answer', flush=True)
            page.locator('#answer').fill('2'); page.locator('#submitAnswer').click()
            page.wait_for_function("document.getElementById('testStatus').textContent.includes('correct')")
            assert page.locator('#answer').input_value() == ''
            page.once('dialog',lambda dialog:dialog.accept('合成复核请求'))
            page.locator('#requestReview').click()
            page.wait_for_function("document.getElementById('testStatus').textContent.includes('复核申请已提交')")
            print('today-start', flush=True)
            page.locator('#today button').first.click()
            page.wait_for_function("document.getElementById('session').value !== " + json.dumps(first_session))
            page.locator('#cancelTest').click()
            page.wait_for_function("document.getElementById('testStatus').textContent.includes('cancelled')")
            # New representative image chain: upload, review, and source URLs.
            print('png', flush=True)
            pixels = io.BytesIO(); Image.new('RGB',(32,32),'white').save(pixels,format='PNG')
            page.locator('#file').set_input_files({'name':'synthetic.png','mimeType':'image/png','buffer':pixels.getvalue()})
            page.locator('#upload').click(); page.wait_for_function("document.getElementById('document').value !== ''")
            page.locator('#makeBatch').click(); page.wait_for_function("document.getElementById('batch').value !== ''")
            print('analyze', flush=True)
            page.locator('#analyze').click(); page.wait_for_function("document.getElementById('uploadStatus').textContent.includes('queued')")
            assert run_worker_once(db,s)['status']=='succeeded'
            page.locator('#refreshItems').click();page.wait_for_function("document.querySelectorAll('#items img').length === 1")
            page.locator('#items select[data-verdict]').select_option('incorrect')
            page.locator('#items textarea').nth(0).fill('PRIVATE_SYNTHETIC_QUESTION')
            page.locator('#items textarea').nth(1).fill('PRIVATE_SYNTHETIC_RAW_ANSWER')
            page.locator('#items textarea[data-evidence]').fill('人工合成复核证据')
            page.get_by_role('button',name='保存复核',exact=True).click()
            page.wait_for_function("document.querySelector('#items [data-revision]').dataset.revision === '2'")
            page.locator('#items input[type=checkbox]').check()
            page.once('dialog',lambda dialog:dialog.accept())
            print('confirm', flush=True)
            page.locator('#confirm').click();page.wait_for_function("document.getElementById('output').textContent.includes('confirmed_count')")
            # Reviewer-only publication UI uses a deterministic provider stub.
            print('variant', flush=True)
            page.locator('#variantObjective').fill(objective_id)
            page.locator('#variantSource').fill('synthetic-source-v1')
            page.locator('#createVariant').click()
            page.wait_for_function("document.getElementById('output').textContent.includes('queued')")
            run_worker_once(db,s)
            page.locator('#loadVariants').click()
            page.wait_for_function("document.querySelectorAll('#variantJobs button').length > 0")
            page.locator('#variantJobs button').first.click()
            page.wait_for_function("document.querySelector('#variantDetail textarea') !== null")
            page.locator('#variantDetail textarea').fill('合成审核：核对母题、整数域、范围与答案。')
            page.once('dialog',lambda dialog:dialog.accept())
            page.get_by_role('button',name='批准并冻结版本',exact=True).click()
            page.wait_for_function("document.getElementById('output').textContent.includes('question_version_id')")
            page.wait_for_function("document.querySelector('#variantDetail button').textContent.includes('撤销')")
            page.locator('#variantDetail textarea').fill('合成撤销说明')
            page.once('dialog',lambda dialog:dialog.accept())
            page.get_by_role('button',name='撤销投放',exact=True).click()
            page.wait_for_function("document.getElementById('output').textContent.includes('prior_grades_unchanged')")
            # Delay an authorized old-context read, then switch. The transport
            # deliberately supplies a late success even after cancellation.
            page.locator('#answer').fill('PRIVATE_DRAFT_ANSWER')
            page.locator('#manualQuestion').fill('PRIVATE_DRAFT_QUESTION')
            page.locator('#manualStudentAnswer').fill('PRIVATE_DRAFT_STUDENT')
            page.locator('#manualCorrectAnswer').fill('PRIVATE_DRAFT_KEY')
            print('delayed-switch', flush=True)
            delayed['arm']=True;page.locator('#loadMistakes').click()
            page.wait_for_timeout(50)
            assert delayed['route'] is not None
            page.locator('#learner').select_option('synthetic-learner-b')
            page.wait_for_function("document.querySelector('main').inert === false")
            try: delayed['route'].fulfill(status=delayed['response'].status_code,body=delayed['response'].content,headers={'content-type':'application/json'})
            except Exception: pass  # Chromium may already have aborted it.
            page.wait_for_timeout(80)
            assert 'PRIVATE_' not in page.locator('body').inner_text()
            assert all(page.locator('#'+field).input_value()=='' for field in ['answer','manualQuestion','manualStudentAnswer','manualCorrectAnswer','file','session','batch'])
            assert page.locator('#items img').count()==0
            assert page.evaluate('window.revokedUrls.length') > 0
            saved_state=page.evaluate("JSON.stringify({...localStorage,...sessionStorage})")
            assert 'PRIVATE_' not in saved_state and 'synthetic-learner-a' not in saved_state
            # Separate synthetic account change rejects the prior learning
            # session, and clears pending raw inputs before leaving the page.
            print('cross-tab', flush=True)
            other = context.new_page(); other.on("pageerror", lambda error: errors.append(str(error)))
            other.goto(origin + "/learning/ui", wait_until="domcontentloaded")
            other.wait_for_function("document.querySelector('main').inert === false")
            other.locator("#learner").select_option("synthetic-learner-a")
            other.wait_for_function("document.querySelector('main').inert === false")
            with page.expect_response(lambda r: r.url.endswith("/api/v1/mistakes")) as stale:
                page.locator("#loadMistakes").click()
            assert stale.value.status == 409
            page.wait_for_function("document.querySelector('main').inert === true")
            print('reload', flush=True)
            page.reload(); page.wait_for_function("document.querySelector('main').inert === false")
            assert page.locator("#learner").input_value() == "synthetic-learner-a"
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            assert not overflow and not errors and not unexpected
            with page.expect_response(lambda r: r.url == origin + "/learning/ui") as logged_out:
                page.locator("#loadLearners").click()
            assert logged_out.value.status == 401
            page.wait_for_function("document.querySelector('main') === null")
            assert not any(c["name"] in {SESSION_COOKIE, CSRF_COOKIE} for c in context.cookies())
            # Recreate only the synthetic session, then change the synthetic
            # WebUI identity. No real account or credential is involved.
            page.goto(origin + '/learning/auth/login',wait_until='domcontentloaded')
            page.get_by_role('button',name='进入学习工作区').click()
            page.wait_for_url('**/learning/auth/session')
            page.goto(origin + '/learning/ui',wait_until='domcontentloaded')
            page.wait_for_function("document.querySelector('main').inert === false")
            page.locator('#answer').fill('PRIVATE_AFTER_ACCOUNT_CHANGE')
            context.add_cookies([{'name':'token','value':'synthetic-other-token','url':origin,'secure':True,'httpOnly':True,'sameSite':'Strict'}])
            with page.expect_response(lambda r:r.url.endswith('/api/v1/mistakes')) as mismatched:
                page.locator('#loadMistakes').click()
            assert mismatched.value.status == 401
            page.wait_for_function("document.querySelector('main').inert === true")
            assert page.locator('#answer').input_value() == '' and page.locator('#account').input_value() == ''
            assert 'PRIVATE_' not in page.locator('body').inner_text()
            assert not any(cookie['name'] in {SESSION_COOKIE,CSRF_COOKIE} for cookie in context.cookies())
            assert not errors and not unexpected
            records.append({"width": width, "login_form_asgi": True, "representative_png_review": True, "today_test_reload_submit_cancel_review": True, "variant_ui_approve_revoke": True, "raw_fields_and_late_response_cleared": True, "object_urls_revoked": True, "account_change_401_and_cleanup": True,
                            "asgi_redirect_status": 303, "redirect_follow_emulated_by_probe": True,
                            "stale_tab_read_status": 409, "refresh_shared_context": True, "logout": True,
                            "horizontal_overflow": overflow, "page_errors": errors, "unexpected_requests": unexpected, "requests": calls})
            context.close()
        browser.close()
    with db.session() as conn:
        schema = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        live = conn.execute("SELECT COUNT(*) FROM provider_calls WHERE evidence_mode='live_http'").fetchone()[0]
    result = {"evidence_kind": "synthetic_chromium_w04_w06_asgi", "schema_revision": schema, "viewports": records,
              "real_openwebui_authentication": False, "real_tls_or_tool_callback": False, "live_provider_calls": live,
              "network_boundary": "all page URLs intercepted; WebUI auth response synthesized; API/gateway in process"}
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--output", type=Path, required=True)
    result = run(parser.parse_args().output)
    print(json.dumps({"evidence_kind": result["evidence_kind"], "schema_revision": result["schema_revision"], "viewports": len(result["viewports"]), "live_provider_calls": result["live_provider_calls"]}))
