from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from learning_service.app import APIError, Context, DiagnosisRequest, ProviderControlRequest, ProviderReconciliationRequest, run_worker_once
from learning_service.config import Settings
from learning_service.db import Database, json_dumps, utc_now
from learning_service.model_providers import OpenAICompatibleDiagnosisProvider, OpenAICompatibleVariantProvider
from learning_service.provider_http import HTTPResult, HTTPTransport, ResponseTooLarge
from learning_service.provider_usage import ProviderLimit, UsageLedger
from learning_service.providers import diagnosis_provider, variant_provider, TencentEducationOCRProvider
from test_learning_service import env, _route

_TRANSPORT_SEND = HTTPTransport.send


@pytest.fixture(autouse=True)
def no_live_transport(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("these tests must never dispatch a live request")
    monkeypatch.setattr(HTTPTransport, "send", forbidden)


def configured(settings):
    return replace(settings, model_external_calls_enabled=True, model_api_key="synthetic-api-key",
                   model_endpoint="https://model.example.invalid/v1/chat/completions",
                   model_allowed_endpoints=("https://model.example.invalid/v1/chat/completions",), model_id="synthetic-model",
                   model_input_micros_per_million=1000000, model_output_micros_per_million=2000000,
                   provider_pricing_reference="synthetic-rates-v1", provider_total_budget_micros=1000000,
                   provider_daily_budget_micros=1000000, provider_max_cost_micros_per_call=100000,
                   provider_max_calls_per_day=20, provider_max_calls_per_minute=20, provider_max_inflight=2,
                   tencent_ocr_cost_micros_per_call=10000)


def diagnosis_input():
    return {"source_item_id": "do-not-send-source-id", "account_id": "do-not-send-account-id", "knowledge_point_ids": ["kp-1"],
            "evidence_fields": [{"ref_id": "question_text", "text": "-3 - (-5) = ?"},
                                {"ref_id": "student_answer", "text": "-8"},
                                {"ref_id": "student_steps", "text": "-3 - 5 = -8"}]}


def diagnosis_output():
    return {"knowledge_point_ids": ["kp-1"], "error_types": ["符号规则"], "needs_clarification": False,
            "evidence_steps": [{"ref_id": "student_steps", "quote": "-3 - 5 = -8"}],
            "hypotheses": [{"text": "可能未转换减去负数的符号。", "basis_refs": ["student_steps"]}],
            "missing_information": [], "remedy_notes": "请复核原始步骤。"}


def variant_input():
    return {"objective_id": "obj-1", "source_question_version_id": "qv-1", "template_id": "signed_number_subtraction",
            "parameters": {"start": -3, "subtrahend": -5}, "domain": "integers", "unit": None}


def variant_output():
    return {"objective_id": "obj-1", "source_question_version_id": "qv-1", "template_id": "signed_number_subtraction",
            "start": -4, "subtrahend": -7, "answer": 3, "domain": "integers", "unit": None}


def response(payload=None, *, status=200, usage=None, **overrides):
    data = {"id": "synthetic-request-1", "model": "synthetic-model",
            "usage": usage if usage is not None else {"prompt_tokens": 50, "completion_tokens": 30},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload if payload is not None else diagnosis_output(), ensure_ascii=False)}}]}
    data.update(overrides)
    return HTTPResult(status, json.dumps(data).encode())


class SyntheticTransport:
    evidence_mode = "synthetic_http"

    def __init__(self, *responses, during_send=None):
        self.responses, self.requests, self.during_send = list(responses), [], during_send

    def send(self, request, timeout, limit):
        self.requests.append((request, timeout, limit))
        if self.during_send:
            self.during_send()
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        if len(result.body) > limit:
            raise ResponseTooLarge()
        return result


@pytest.fixture
def controls(tmp_path):
    s = configured(Settings(tmp_path, tmp_path / "learning.db", tmp_path / "attachments", "admin", "adapter", True))
    db = Database(s.db_path)
    return s, db, UsageLedger(db, s)


def test_real_factory_code_exists_and_defaults_never_dispatch(controls):
    s, db, ledger = controls
    default = replace(s, model_external_calls_enabled=False)
    assert isinstance(diagnosis_provider("openai-compatible-diagnosis-v1", default, ledger), OpenAICompatibleDiagnosisProvider)
    assert isinstance(variant_provider("openai-compatible-variant-v1", default, ledger), OpenAICompatibleVariantProvider)
    result = diagnosis_provider("openai-compatible-diagnosis-v1", default, ledger).diagnose(diagnosis_input())
    assert result.evidence["error_code"] == "MODEL_EXTERNAL_CALLS_DISABLED"
    assert ledger.summary()["by_evidence_mode"] == {}


@pytest.mark.parametrize("change,expected", [
    ({"model_api_key": "replace-with-key"}, "MODEL_NOT_CONFIGURED"),
    ({"model_allowed_endpoints": ()}, "MODEL_ENDPOINT_NOT_ALLOWED"),
    ({"model_endpoint": "http://model.example.invalid/v1/chat/completions"}, "MODEL_ENDPOINT_NOT_ALLOWED"),
    ({"model_endpoint": "https://secret@model.example.invalid/v1/chat/completions"}, "MODEL_ENDPOINT_NOT_ALLOWED"),
    ({"model_max_attempts": 3}, "MODEL_LIMITS_NOT_CONFIGURED"),
    ({"provider_total_budget_micros": 0}, "BUDGET_NOT_CONFIGURED"),
    ({"provider_max_cost_micros_per_call": 1}, "CALL_COST_LIMIT"),
])
def test_configuration_and_money_gates_precede_http(controls, change, expected):
    s, db, _ = controls; s = replace(s, **change)
    fake = SyntheticTransport()
    result = OpenAICompatibleDiagnosisProvider(s, UsageLedger(db, s), fake).diagnose(diagnosis_input())
    assert result.evidence["error_code"] == expected
    assert not fake.requests and result.evidence["external_call"] is False


def test_diagnosis_request_citations_minimal_data_and_usage(controls):
    s, db, ledger = controls
    fake = SyntheticTransport(response())
    result = OpenAICompatibleDiagnosisProvider(s, ledger, fake).diagnose(diagnosis_input())
    assert result.status == "needs_review" and result.payload == diagnosis_output()
    assert result.evidence["mode"] == "synthetic_http" and result.evidence["external_call"] is False
    request, timeout, limit = fake.requests[0]
    sent = json.loads(request.data)
    assert request.full_url == s.model_endpoint and timeout == 15 and limit == 256 * 1024
    assert "tools" not in sent and sent["response_format"]["type"] == "json_schema"
    assert "do-not-send" not in request.data.decode()
    with db.session() as conn:
        call = dict(conn.execute("SELECT * FROM provider_calls").fetchone())
    assert call["reserved_cost_micros"] == 18000 and call["estimated_cost_micros"] == 110
    assert call["prompt_tokens"] == 50 and call["completion_tokens"] == 30
    assert ledger.summary()["budget_charge_micros"] == 18000
    assert "student_steps" not in json.dumps(call) and "synthetic-api-key" not in json.dumps(call)


@pytest.mark.parametrize("mutation", ["quote", "reference", "knowledge", "approval", "wrong_model", "truncated", "tool_call", "duplicate_json", "invalid_usage"])
def test_invalid_output_degrades_to_review(controls, mutation):
    s, db, ledger = controls
    payload, overrides = diagnosis_output(), {}
    if mutation == "quote": payload["evidence_steps"][0]["quote"] = "invented steps"
    if mutation == "reference": payload["hypotheses"][0]["basis_refs"] = ["other-student"]
    if mutation == "knowledge": payload["knowledge_point_ids"] = ["outside-scope"]
    if mutation == "approval": payload["approved"] = True
    if mutation == "wrong_model": overrides["model"] = "unexpected-model"
    if mutation == "truncated": overrides["choices"] = [{"finish_reason": "length", "message": {"content": json.dumps(payload)}}]
    if mutation == "tool_call": overrides["choices"] = [{"finish_reason": "stop", "message": {"content": json.dumps(payload), "tool_calls": [{"name": "confirm"}]}}]
    if mutation == "duplicate_json": overrides["choices"] = [{"finish_reason": "stop", "message": {"content": '{"needs_clarification":true,"needs_clarification":false}'}}]
    if mutation == "invalid_usage": overrides["usage"] = {"prompt_tokens": 16001, "completion_tokens": 30}
    result = OpenAICompatibleDiagnosisProvider(s, ledger, SyntheticTransport(response(payload, **overrides))).diagnose(diagnosis_input())
    assert result.status == "needs_review" and result.payload["needs_clarification"] is True
    assert result.evidence["error_code"] == ("MODEL_USAGE_LIMIT_EXCEEDED" if mutation == "invalid_usage" else "MODEL_OUTPUT_INVALID")
    assert ledger.summary()["budget_charge_micros"] >= 18000
    assert ledger.summary()["paused"] is (mutation == "invalid_usage")


def test_missing_steps_and_input_ceiling(controls):
    s, db, ledger = controls
    data = diagnosis_input(); data["evidence_fields"].pop()
    payload = diagnosis_output(); payload["evidence_steps"] = []; payload["hypotheses"] = []
    fake = SyntheticTransport(response(payload))
    assert OpenAICompatibleDiagnosisProvider(s, ledger, fake).diagnose(data).payload["needs_clarification"] is True
    data["evidence_fields"][0]["text"] = "长" * 10000
    before = len(fake.requests)
    result = OpenAICompatibleDiagnosisProvider(s, ledger, fake).diagnose(data)
    assert result.evidence["error_code"] == "MODEL_INPUT_TOO_LARGE" and len(fake.requests) == before


@pytest.mark.parametrize("mutation", [None, "answer", "objective", "source", "same", "unit", "boolean", "approval"])
def test_variant_scope_math_and_manual_approval(controls, mutation):
    s, db, ledger = controls
    payload = variant_output()
    if mutation == "answer": payload["answer"] = 9
    if mutation == "objective": payload["objective_id"] = "outside-objective"
    if mutation == "source": payload["source_question_version_id"] = "other-source"
    if mutation == "same": payload.update(start=-3, subtrahend=-5, answer=2)
    if mutation == "unit": payload["unit"] = "cm"
    if mutation == "boolean": payload["start"] = True
    if mutation == "approval": payload["approval"] = "approved"
    result = OpenAICompatibleVariantProvider(s, ledger, SyntheticTransport(response(payload))).generate(variant_input())
    assert result.status == "needs_review" and result.payload["approval_required"] is True
    if mutation:
        assert result.payload["draft"] is None
    else:
        draft = result.payload["draft"]
        assert draft["approval"] == "draft" and draft["answer_key"] == {"accepted": ["3"]}
        assert draft["content"]["prompt"] == "-4 - (-7) = ?"
    assert result.evidence["external_call"] is False


def test_retry_timeout_and_unknown_usage_keep_every_hold(controls):
    s, db, _ = controls; s = replace(s, model_max_attempts=2)
    ledger = UsageLedger(db, s)
    fake = SyntheticTransport(response(status=429), response())
    result = OpenAICompatibleDiagnosisProvider(s, ledger, fake).diagnose(diagnosis_input())
    assert len(fake.requests) == 2 and len(result.evidence["call_ids"]) == 2
    fake = SyntheticTransport(TimeoutError("private network error"))
    result = OpenAICompatibleDiagnosisProvider(s, ledger, fake).diagnose(diagnosis_input())
    assert len(fake.requests) == 1 and result.evidence["error_code"] == "MODEL_TRANSPORT_FAILED"
    assert "private network error" not in json.dumps(result.evidence)
    assert ledger.summary()["by_state"]["unknown"] == 1
    result = OpenAICompatibleDiagnosisProvider(s, ledger, SyntheticTransport(response(usage={}))).diagnose(diagnosis_input())
    assert result.evidence["usage_status"] == "unknown"
    assert ledger.summary()["budget_charge_micros"] == 72000


def test_concurrent_reservations_cannot_exceed_total_budget(controls):
    s, db, _ = controls; s = replace(s, provider_total_budget_micros=18000, provider_max_inflight=20)
    ledger = UsageLedger(db, s)
    def reserve(_):
        try: return ledger.reserve("synthetic-provider", "diagnosis", "synthetic-model", 18000, "synthetic_http")
        except ProviderLimit as exc: return exc.code
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(reserve, range(8)))
    assert len([x for x in results if x.startswith("provider_call_")]) == 1
    assert results.count("TOTAL_COST_LIMIT") == 7 and ledger.summary()["budget_charge_micros"] == 18000


@pytest.mark.parametrize("setting,code", [("provider_max_calls_per_day", "DAILY_CALL_LIMIT"), ("provider_max_calls_per_minute", "PROVIDER_RATE_LIMIT"), ("provider_max_inflight", "PROVIDER_INFLIGHT_LIMIT")])
def test_durable_call_rate_and_inflight_limits(controls, setting, code):
    s, db, _ = controls; s = replace(s, **{setting: 1})
    ledger = UsageLedger(db, s)
    ledger.reserve("synthetic-provider", "diagnosis", "synthetic-model", 18000, "synthetic_http")
    with pytest.raises(ProviderLimit) as error: ledger.reserve("synthetic-provider", "diagnosis", "synthetic-model", 18000, "synthetic_http")
    assert error.value.code == code


def test_invoice_contract_and_pause_persist_without_network(controls):
    s, db, ledger = controls
    # Direct ledger fixtures; no HTTP request or actual invoice exists.
    call = ledger.reserve("synthetic-provider", "diagnosis", "synthetic-model", 18000)
    ledger.finish(call, state="unknown")
    with pytest.raises(ProviderLimit): ledger.reconcile(call, 20, "CNY", "synthetic-invoice", "synthetic-request")
    result = ledger.reconcile(call, 20, "USD", "synthetic-invoice", "synthetic-request")
    assert result["billing_evidence"] == "operator_invoice_reference"
    assert ledger.reconcile(call, 20, "USD", "synthetic-invoice", "synthetic-request") == result
    with pytest.raises(ProviderLimit): ledger.reconcile(call, 21, "USD", "synthetic-invoice", "synthetic-request")
    call = ledger.reserve("synthetic-provider", "diagnosis", "synthetic-model", 18000, "synthetic_http")
    ledger.finish(call, state="returned")
    with pytest.raises(ProviderLimit) as error: ledger.reconcile(call, 20, "USD", "synthetic-invoice", "synthetic-request")
    assert error.value.code == "SYNTHETIC_CALL_HAS_NO_INVOICE"
    ledger.set_paused(True)
    with pytest.raises(ProviderLimit) as error: UsageLedger(Database(db.path), s).reserve("synthetic-provider", "diagnosis", "synthetic-model", 18000)
    assert error.value.code == "PROVIDER_PAUSED"


def _seed_mistake(db):
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO mistake_entries(id,learner_id,objective_id,status,diagnosis_status,content_json,created_at) VALUES (?,?,?,?,?,?,?)",
                     ("mistake-provider", "learner-a", "obj-1", "active", "draft", json_dumps({x["ref_id"]:x["text"] for x in diagnosis_input()["evidence_fields"]}), utc_now()))


def test_diagnosis_route_persists_adapter_fields_not_client_model(env, monkeypatch):
    s, db, app = env; s = configured(s); _seed_mistake(db)
    fake = SyntheticTransport(response())
    monkeypatch.setattr("learning_service.app.diagnosis_provider", lambda _id, settings, ledger: OpenAICompatibleDiagnosisProvider(settings, ledger, fake))
    result = _route(app, "/api/v1/mistakes/{mistake_id}/diagnoses")("mistake-provider", DiagnosisRequest(model_id="client-cannot-choose-model"), Context(account_id="acct-a", learner_id="learner-a"), db, s)
    with db.session() as conn: row = conn.execute("SELECT * FROM diagnoses WHERE id=?", (result["diagnosis_id"],)).fetchone()
    assert row["model_id"] == "synthetic-model" and row["prompt_version"] == "dd-diagnosis-v1"
    assert json.loads(row["output_json"])["evidence_steps"] == diagnosis_output()["evidence_steps"]
    assert row["status"] == "needs_review"


def test_changed_diagnosis_evidence_rejects_output_but_keeps_usage(env, monkeypatch):
    s, db, app = env; s = configured(s); _seed_mistake(db)
    def mutate():
        with db.session(write=True) as conn: conn.execute("UPDATE mistake_entries SET content_json='{}' WHERE id='mistake-provider'")
    fake = SyntheticTransport(response(), during_send=mutate)
    monkeypatch.setattr("learning_service.app.diagnosis_provider", lambda _id, settings, ledger: OpenAICompatibleDiagnosisProvider(settings, ledger, fake))
    with pytest.raises(APIError) as error:
        _route(app, "/api/v1/mistakes/{mistake_id}/diagnoses")("mistake-provider", DiagnosisRequest(), Context(account_id="acct-a", learner_id="learner-a"), db, s)
    assert error.value.code == "STALE_DIAGNOSIS_EVIDENCE"
    with db.session() as conn: assert conn.execute("SELECT COUNT(*) FROM diagnoses").fetchone()[0] == 0
    assert UsageLedger(db, s).summary()["budget_charge_micros"] == 18000


@pytest.mark.parametrize("change", [None, "revoke", "foreign"])
def test_variant_worker_rechecks_source_before_persistence(env, monkeypatch, change):
    s, db, app = env; s = configured(s)
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO questions(id,learner_id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?,?)", ("q-1", "learner-b" if change == "foreign" else "learner-a", "private", "approved", "obj-1", now))
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,?,?,?,?,?,?)", ("qv-1", "q-1", 1, json_dumps({k:variant_input()[k] for k in ("template_id", "parameters", "domain", "unit")}), '{"accepted":["2"]}', "exact-text-v1", "approved", now))
        conn.execute("INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", ("variant-job", "learner-a", "variant_generation", '{"objective_id":"obj-1","source_question_version_id":"qv-1"}', "variant-provider-test", "queued", now, now))
    def mutate():
        if change == "revoke":
            with db.session(write=True) as conn: conn.execute("UPDATE question_versions SET approval='draft' WHERE id='qv-1'")
    fake = SyntheticTransport(response(variant_output()), during_send=mutate)
    monkeypatch.setattr("learning_service.app.variant_provider", lambda _id, settings, ledger: OpenAICompatibleVariantProvider(settings, ledger, fake))
    result = run_worker_once(db, s)
    if change:
        assert result["status"] == "failed" and result["error"] == ("SOURCE_QUESTION_NOT_FOUND" if change == "foreign" else "SOURCE_QUESTION_NOT_APPROVED")
        assert len(fake.requests) == (0 if change == "foreign" else 1)
    else:
        assert result["result"]["payload"]["draft"]["approval"] == "draft" and result["result"]["external_call"] is False
    with db.session() as conn: assert conn.execute("SELECT COUNT(*) FROM question_versions").fetchone()[0] == 1


def test_ocr_cannot_bypass_shared_limits(controls):
    s, db, ledger = controls; ledger.set_paused(True)
    fake = SyntheticTransport()
    ocr = TencentEducationOCRProvider("synthetic-id", "synthetic-secret", external_calls_enabled=True, ledger=ledger, transport=fake)
    result = ocr.analyze_page({"id": "page-1", "image_bytes": b"synthetic"})
    assert result.payload["ocr_error_code"] == "PROVIDER_PAUSED" and not fake.requests


def test_completed_diagnosis_write_is_reused_after_worker_interruption(env, monkeypatch):
    s, db, app = env; s = configured(s); _seed_mistake(db)
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                     ("diagnosis-retry", "learner-a", "diagnosis", '{"mistake_id":"mistake-provider"}', "diagnosis-retry-key", "queued", now, now))
    fake = SyntheticTransport(response())
    monkeypatch.setattr("learning_service.app.diagnosis_provider", lambda _id, settings, ledger: OpenAICompatibleDiagnosisProvider(settings, ledger, fake))
    first = run_worker_once(db, s)
    with db.session(write=True) as conn:
        # Simulate losing the final job acknowledgement after the diagnosis
        # transaction committed; the provider result must not be requested twice.
        conn.execute("UPDATE jobs SET status='running',lease_token='old',lease_until='2000-01-01T00:00:00+00:00' WHERE id='diagnosis-retry'")
    second = run_worker_once(db, s)
    assert first["result"] == second["result"] and len(fake.requests) == 1
    assert UsageLedger(db, s).summary()["budget_charge_micros"] == 18000
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM diagnoses").fetchone()[0] == 1


def test_daily_cost_currency_and_inflight_reconciliation_boundaries(controls):
    s, db, _ = controls; s = replace(s, provider_daily_budget_micros=18000)
    ledger = UsageLedger(db, s)
    call = ledger.reserve("synthetic-provider", "diagnosis", "synthetic-model", 18000)
    with pytest.raises(ProviderLimit) as error:
        ledger.reconcile(call, 1, "USD", "synthetic-invoice", "synthetic-request")
    assert error.value.code == "CALL_STILL_RESERVED"
    ledger.finish(call, state="unknown")
    with pytest.raises(ProviderLimit) as error:
        ledger.reserve("synthetic-provider", "diagnosis", "synthetic-model", 18000)
    assert error.value.code == "DAILY_COST_LIMIT"
    changed = UsageLedger(db, replace(s, provider_currency="CNY"))
    assert changed.summary()["currency"] == "USD" and changed.summary()["configured_currency"] == "CNY"
    with pytest.raises(ProviderLimit) as error:
        changed.reserve("synthetic-provider", "diagnosis", "synthetic-model", 18000)
    assert error.value.code == "BUDGET_CURRENCY_CHANGED"


def test_http_transport_blocks_redirects_and_ignores_proxies_without_network(monkeypatch):
    from urllib.request import Request, ProxyHandler
    captured = {}
    class LocalResponse:
        status = 302
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, _size): return b""
    class LocalOpener:
        def open(self, request, timeout):
            captured["request"] = request
            return LocalResponse()
    def build(*handlers):
        captured["handlers"] = handlers
        return LocalOpener()
    monkeypatch.setattr("learning_service.provider_http.build_opener", build)
    # The original transport runs against the local opener above, never a socket.
    result = _TRANSPORT_SEND(HTTPTransport(), Request("https://model.example.invalid/v1/chat/completions", data=b"{}", method="POST"), 1, 1024)
    assert result.status == 302
    assert isinstance(captured["handlers"][0], ProxyHandler) and captured["handlers"][0].proxies == {}
    redirect = captured["handlers"][1]
    assert redirect.redirect_request(None, None, 302, "", {}, "https://outside.example.invalid") is None


def test_admin_ledger_routes_require_role_and_expose_no_student_payload(env):
    s, db, app = env; s = configured(s); app.state.settings = s
    admin = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    student = Context(account_id="acct-b", learner_id="learner-b", role="student")
    list_calls = _route(app, "/api/v1/admin/provider-calls")
    control = _route(app, "/api/v1/admin/provider-control")
    reconcile = _route(app, "/api/v1/admin/provider-calls/{call_id}/reconcile")
    body = ProviderReconciliationRequest(cost_micros=1, currency="USD", billing_reference="synthetic-invoice", request_id="synthetic-request")
    for call in (lambda: list_calls(student, db), lambda: control(ProviderControlRequest(paused=True), student, db), lambda: reconcile("unknown", body, student, db)):
        with pytest.raises(APIError) as error: call()
        assert error.value.code == "FORBIDDEN"
    ledger = UsageLedger(db, s)
    call_id = ledger.reserve("synthetic-provider", "diagnosis", "synthetic-model", 18000)
    ledger.finish(call_id, state="unknown")
    listed = list_calls(admin, db)
    assert listed["items"][0]["id"] == call_id and "learner-a" not in json.dumps(listed)
    assert reconcile(call_id, body, admin, db)["status"] == "reconciled"
    assert control(ProviderControlRequest(paused=True), admin, db) == {"paused": True}


def test_partial_response_and_invoice_overrun_fail_safely(controls):
    from http.client import IncompleteRead
    s, db, ledger = controls
    result = OpenAICompatibleDiagnosisProvider(s, ledger, SyntheticTransport(IncompleteRead(b"sensitive incomplete data"))).diagnose(diagnosis_input())
    assert result.evidence["error_code"] == "MODEL_TRANSPORT_FAILED"
    assert "sensitive" not in json.dumps(result.evidence)
    call = ledger.reserve("synthetic-provider", "diagnosis", "synthetic-model", 18000)
    ledger.finish(call, state="unknown")
    ledger.reconcile(call, 18001, "USD", "synthetic-invoice-overrun", "synthetic-request")
    assert ledger.summary()["paused"] is True
