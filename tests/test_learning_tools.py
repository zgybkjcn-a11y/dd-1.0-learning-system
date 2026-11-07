from __future__ import annotations

import io
import json
import asyncio
import pytest
from urllib.error import HTTPError, URLError

from learning_service import tools as tools_module
from learning_service.tools import Tools


@pytest.fixture(autouse=True)
def legacy_transport_profile(monkeypatch):
    # Preserve coverage of the existing compatibility transport and callbacks.
    # The shared formal profile has separate ASGI integration tests.
    monkeypatch.setenv('DD_SHARED_LEARNER_CONTEXT', 'false')
    monkeypatch.setenv('DD_WORKBENCH_URL', '')


class _Response:
    def __init__(self, body: bytes = b'{"ok":true}'):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


def test_tools_forwards_trusted_context_and_json_payload(monkeypatch):
    monkeypatch.setenv("DD_LEARNING_BASE_URL", "http://learning-api:31010/")
    monkeypatch.setenv("DD_LEARNING_ADAPTER_SECRET", "adapter-test-secret")
    monkeypatch.setenv("DD_ACCOUNT_ID", "acct-test")
    monkeypatch.setenv("DD_LEARNER_ID", "learner-test")
    monkeypatch.setenv("DD_TRUSTED_PROVIDER", "open-webui")
    monkeypatch.setenv("DD_TRUSTED_ISSUER", "test-installation")
    monkeypatch.setenv("DD_TRUSTED_SUBJECT", "user-42")
    observed = {}

    def fake_urlopen(request, timeout):
        observed["request"] = request
        observed["timeout"] = timeout
        return _Response(b'{"job_id":"job-1","status":"queued"}')

    monkeypatch.setattr(tools_module, "urlopen", fake_urlopen)
    result = Tools().request_variant("obj-1", "question-v2")

    request = observed["request"]
    assert json.loads(result) == {"job_id": "job-1", "status": "queued"}
    assert request.full_url == "http://learning-api:31010/api/v1/variant-jobs"
    assert request.get_method() == "POST"
    assert json.loads(request.data.decode("utf-8")) == {
        "objective_id": "obj-1",
        "source_question_version_id": "question-v2",
    }
    assert request.get_header("X-adapter-secret") == "adapter-test-secret"
    assert request.get_header("X-account-id") == "acct-test"
    assert request.get_header("X-learner-id") == "learner-test"
    assert request.get_header("X-trusted-provider") == "open-webui"
    assert request.get_header("X-trusted-issuer") == "test-installation"
    assert request.get_header("X-trusted-subject") == "user-42"
    assert request.get_header("Content-type") == "application/json"
    assert observed["timeout"] == 15


def test_tools_encodes_resource_ids_as_single_path_segments(monkeypatch):
    monkeypatch.delenv("DD_LEARNING_ADAPTER_SECRET", raising=False)
    observed = {}

    def fake_urlopen(request, timeout):
        observed["request"] = request
        return _Response()

    monkeypatch.setattr(tools_module, "urlopen", fake_urlopen)
    Tools().get_attempt("attempt/with space")

    assert observed["request"].full_url.endswith("/api/v1/attempts/attempt%2Fwith%20space")
    assert observed["request"].get_method() == "GET"
    assert observed["request"].data is None
    assert observed["request"].get_header("Content-type") is None


def test_tools_preserves_structured_service_http_errors(monkeypatch):
    error_body = b'{"error":{"code":"LEARNER_NOT_FOUND","message":"no access","retryable":false}}'

    def fail(request, timeout):
        raise HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO(error_body))

    monkeypatch.setattr(tools_module, "urlopen", fail)
    result = json.loads(Tools().get_review_tasks())
    assert result == {"error": {"code": "LEARNER_NOT_FOUND"}}


def test_tools_wraps_unstructured_http_errors_without_returning_unbounded_body(monkeypatch):
    def fail(request, timeout):
        raise HTTPError(request.full_url, 502, "Bad Gateway", {}, io.BytesIO(b"x" * 2000))

    monkeypatch.setattr(tools_module, "urlopen", fail)
    result = json.loads(Tools().get_progress())
    assert result["error"]["code"] == "LEARNING_SERVICE_HTTP_ERROR"
    assert "status" not in result["error"] and "message" not in result["error"]


def test_tools_maps_network_and_timeout_errors_as_unavailable(monkeypatch):
    def fail_network(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr(tools_module, "urlopen", fail_network)
    network = json.loads(Tools().get_progress())
    assert network == {"error": {"code": "LEARNING_SERVICE_UNAVAILABLE"}}

    def fail_timeout(request, timeout):
        assert timeout == 15
        raise TimeoutError("timed out")

    monkeypatch.setattr(tools_module, "urlopen", fail_timeout)
    timed_out = json.loads(Tools().get_progress())
    assert timed_out == {"error": {"code": "LEARNING_SERVICE_UNAVAILABLE"}}


def _route_response(request, routes):
    key = (request.get_method(), request.full_url.removeprefix("http://learning-api:31010"))
    if key not in routes:
        raise AssertionError(f"unexpected learning API request: {key}")
    response = routes[key]
    return response(request) if callable(response) else response


def test_import_confirmation_uses_current_batch_and_strict_native_confirmation(monkeypatch):
    adapter = Tools()
    adapter.valves.DD_LEARNING_BASE_URL = "http://learning-api:31010"
    selected = [{"item_id": "item-1", "expected_revision": 4}]
    routes = {
        ("GET", "/api/v1/import-batches/batch-1"): _Response(
            b'{"revision":8,"status":"awaiting_review","failed_pages":0}'
        ),
        ("GET", "/api/v1/import-batches/batch-1/items"): _Response(
            json.dumps({"items": [{"id": "item-1", "revision": 4, "status": "ready", "verification_status": "manual", "locator": "第1题", "content": {"prompt": "7-(-2)"}, "raw_answer": "7-(-2)=5", "verdict": "incorrect", "teacher_evidence": {"note": "符号错误"}}]}, ensure_ascii=False).encode()
        ),
        ("POST", "/api/v1/import-batches/batch-1/confirmation-challenges"): _Response(
            b'{"challenge_id":"secret-challenge","nonce":"secret-nonce","operation":"confirm_import","resource_id":"batch-1"}'
        ),
        ("POST", "/api/v1/import-batches/batch-1/confirmations"): _Response(
            b'{"status":"accepted","confirmed_count":1,"challenge_id":"must-not-leak"}'
        ),
    }
    observed = []

    def fake_urlopen(request, timeout):
        observed.append(request)
        return _route_response(request, routes)

    monkeypatch.setattr(tools_module, "urlopen", fake_urlopen)
    events = []

    async def event_call(event):
        events.append(event)
        return True

    result = json.loads(
        asyncio.run(
            adapter.start_trusted_interaction(
                "confirm_import", "batch-1", selected,
                __user__={"id": "trusted-user"}, __event_call__=event_call,
            )
        )
    )
    assert result == {"status": "accepted", "selected_count": 1, "confirmed_count": 1}
    assert len(events) == 1 and events[0]["type"] == "confirmation"
    assert "7-(-2)" in events[0]["data"]["message"]
    assert "7-(-2)=5" in events[0]["data"]["message"]
    assert "符号错误" in events[0]["data"]["message"]
    challenge_request = next(r for r in observed if r.full_url.endswith("confirmation-challenges"))
    assert json.loads(challenge_request.data) == {
        "items": selected,
        "expected_batch_revision": 8,
    }
    submission = next(r for r in observed if r.full_url.endswith("/confirmations"))
    assert json.loads(submission.data) == {
        "challenge_id": "secret-challenge",
        "nonce": "secret-nonce",
        "items": selected,
    }
    assert submission.get_header("Idempotency-key")
    assert "nonce" not in json.dumps(result) and "challenge_id" not in json.dumps(result)


def test_import_confirmation_cancel_error_and_missing_callback_never_create_challenge(monkeypatch):
    adapter = Tools()
    adapter.valves.DD_LEARNING_BASE_URL = "http://learning-api:31010"
    routes = {
        ("GET", "/api/v1/import-batches/batch-1"): _Response(
            b'{"revision":8,"status":"awaiting_review","failed_pages":0}'
        ),
        ("GET", "/api/v1/import-batches/batch-1/items"): _Response(
            b'{"items":[{"id":"item-1","revision":4,"status":"ready","verification_status":"manual","content":{"prompt":"question"}}]}'
        ),
    }
    observed = []

    def fake_urlopen(request, timeout):
        observed.append(request)
        return _route_response(request, routes)

    monkeypatch.setattr(tools_module, "urlopen", fake_urlopen)
    candidate = [{"item_id": "item-1", "expected_revision": 4}]
    callbacks = [lambda event: False, lambda event: {"error": "disconnected"}]

    async def raises(event):
        raise RuntimeError("callback disconnected")

    callbacks.append(raises)
    for callback in callbacks:
        result = json.loads(asyncio.run(adapter.start_trusted_interaction(
            "confirm_import", "batch-1", candidate, __event_call__=callback
        )))
        assert result["error"]["code"] == "TRUSTED_UI_NOT_CONFIRMED"
    missing = json.loads(asyncio.run(adapter.start_trusted_interaction("confirm_import", "batch-1", candidate)))
    assert missing["error"]["code"] == "TRUSTED_UI_CALLBACK_REQUIRED"
    assert all(not request.full_url.endswith(("confirmation-challenges", "/confirmations")) for request in observed)


def test_trusted_ui_callback_timeout_never_creates_or_submits_a_challenge(monkeypatch):
    adapter = Tools()
    adapter.valves.DD_LEARNING_BASE_URL = "http://learning-api:31010"
    monkeypatch.setattr(tools_module, "TRUSTED_UI_TIMEOUT_SECONDS", 0.001)
    routes = {
        ("GET", "/api/v1/import-batches/batch-1"): _Response(
            b'{"revision":8,"status":"awaiting_review","failed_pages":0}'
        ),
        ("GET", "/api/v1/import-batches/batch-1/items"): _Response(
            b'{"items":[{"id":"item-1","revision":4,"status":"ready","verification_status":"manual","content":{"prompt":"question"}}]}'
        ),
        ("GET", "/api/v1/test-items/item-1"): _Response(
            b'{"test_item_id":"item-1","prompt":"question"}'
        ),
    }
    observed = []
    event_timeouts = []
    monkeypatch.setattr(
        tools_module,
        "urlopen",
        lambda request, timeout: (observed.append(request), _route_response(request, routes))[1],
    )

    async def callback_never_returns(event):
        event_timeouts.append(event["data"]["timeout_ms"])
        await asyncio.Event().wait()

    import_result = json.loads(
        asyncio.run(
            adapter.start_trusted_interaction(
                "confirm_import",
                "batch-1",
                [{"item_id": "item-1", "expected_revision": 4}],
                __event_call__=callback_never_returns,
            )
        )
    )
    answer_result = json.loads(
        asyncio.run(
            adapter.start_trusted_interaction(
                "submit_answer", "item-1", __event_call__=callback_never_returns
            )
        )
    )

    assert import_result["error"]["code"] == "TRUSTED_UI_NOT_CONFIRMED"
    assert answer_result["error"]["code"] == "TRUSTED_UI_NOT_CONFIRMED"
    assert event_timeouts == [1, 1]
    assert all(
        not request.full_url.endswith(
            ("confirmation-challenges", "/confirmations", "submission-challenges", "/answers")
        )
        for request in observed
    )


def test_learning_draft_confirmation_uses_server_content_and_does_not_echo_it(monkeypatch):
    adapter = Tools()
    adapter.valves.DD_LEARNING_BASE_URL = "http://learning-api:31010"
    raw_content = {"answer": "原始记录: 4×3=12", "note": "学生原文"}
    routes = {
        ("GET", "/api/v1/learning-drafts/draft-1"): _Response(
            json.dumps({"id": "draft-1", "revision": 3, "content": raw_content}, ensure_ascii=False).encode()
        ),
        ("POST", "/api/v1/learning-drafts/draft-1/confirmation-challenges"): _Response(
            b'{"challenge_id":"draft-challenge","nonce":"draft-nonce","operation":"confirm_learning","resource_id":"draft-1"}'
        ),
        ("POST", "/api/v1/learning-drafts/draft-1/confirmations"): _Response(
            b'{"status":"confirmed","draft_id":"draft-1","card_id":"card-1","content":"must-not-leak"}'
        ),
    }
    observed = []
    monkeypatch.setattr(tools_module, "urlopen", lambda request, timeout: (observed.append(request), _route_response(request, routes))[1])
    shown = []

    def event_call(event):
        shown.append(event)
        return True

    result = json.loads(asyncio.run(adapter.start_trusted_interaction(
        "confirm_learning", "draft-1", __event_call__=event_call
    )))
    assert result == {"status": "confirmed", "draft_id": "draft-1", "card_id": "card-1"}
    assert "学生原文" in shown[0]["data"]["message"]
    challenge_index = next(i for i, r in enumerate(observed) if r.full_url.endswith("confirmation-challenges"))
    submit_index = next(i for i, r in enumerate(observed) if r.full_url.endswith("/confirmations"))
    assert challenge_index > 0 and submit_index > challenge_index
    assert json.loads(observed[submit_index].data)["raw_content"] == raw_content
    assert "学生原文" not in json.dumps(result)


def test_answer_input_is_host_callback_only_and_raw_answer_is_not_returned(monkeypatch):
    adapter = Tools()
    adapter.valves.DD_LEARNING_BASE_URL = "http://learning-api:31010"
    routes = {
        ("GET", "/api/v1/test-items/item-1"): _Response(
            b'{"test_item_id":"item-1","prompt":"7-(-2)=?","answer_key":{"accepted":["9"]}}'
        ),
        ("POST", "/api/v1/test-items/item-1/submission-challenges"): _Response(
            b'{"challenge_id":"answer-challenge","nonce":"answer-nonce","operation":"submit_answer","resource_id":"item-1"}'
        ),
        ("POST", "/api/v1/test-items/item-1/answers"): _Response(
            b'{"attempt_id":"attempt-1","job_id":"job-1","status":"grading_pending","assessment_eligibility":true,"raw_answer":"must-not-leak"}'
        ),
    }
    observed = []
    monkeypatch.setattr(tools_module, "urlopen", lambda request, timeout: (observed.append(request), _route_response(request, routes))[1])
    shown = []

    async def event_call(event):
        shown.append(event)
        return " 7-(-2) = 9 "

    result = json.loads(asyncio.run(adapter.start_trusted_interaction(
        "submit_answer", "item-1", __event_call__=event_call
    )))
    assert result == {"status": "grading_pending", "attempt_id": "attempt-1", "assessment_eligibility": True}
    assert shown[0]["type"] == "input" and shown[0]["data"]["message"] == "7-(-2)=?"
    submitted = next(r for r in observed if r.full_url.endswith("/answers"))
    assert json.loads(submitted.data)["raw_answer"] == " 7-(-2) = 9 "
    assert "answer_key" not in shown[0]["data"]["message"]
    assert "raw_answer" not in json.dumps(result) and "nonce" not in json.dumps(result)


def test_answer_input_cancel_and_invalid_values_do_not_create_challenge(monkeypatch):
    adapter = Tools()
    adapter.valves.DD_LEARNING_BASE_URL = "http://learning-api:31010"
    routes = {
        ("GET", "/api/v1/test-items/item-1"): _Response(
            b'{"test_item_id":"item-1","prompt":"question"}'
        ),
    }
    observed = []
    monkeypatch.setattr(tools_module, "urlopen", lambda request, timeout: (observed.append(request), _route_response(request, routes))[1])
    for value, expected in [(False, "TRUSTED_UI_NOT_CONFIRMED"), (None, "TRUSTED_UI_NOT_CONFIRMED"), ("  ", "TRUSTED_UI_INPUT_INVALID"), ({"answer": "x"}, "TRUSTED_UI_INPUT_INVALID")]:
        result = json.loads(asyncio.run(adapter.start_trusted_interaction(
            "submit_answer", "item-1", __event_call__=lambda event, value=value: value
        )))
        assert result["error"]["code"] == expected
    assert all(not request.full_url.endswith("submission-challenges") for request in observed)
