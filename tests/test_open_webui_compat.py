from __future__ import annotations

import json
import asyncio
from pathlib import Path

from open_webui_harness import call_tool, call_tool_async, discover_functions, inject_valves, load_tool_module, parse_tool_metadata, visible_parameters


class _Response:
    def __init__(self, body: bytes = b'{"ok":true}'):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


TOOL_SOURCE = Path(__file__).parents[1] / "learning_service" / "tools.py"
EXPECTED_FUNCTIONS = {
    "get_attempt",
    "get_mistakes",
    "get_progress",
    "get_review_tasks",
    "list_learners",
    "request_diagnosis",
    "request_document_analysis",
    "request_hint",
    "request_variant",
    "request_visual",
    "start_trusted_interaction",
}


def test_tool_metadata_is_parseable_and_pins_compatibility_contract():
    metadata = parse_tool_metadata(TOOL_SOURCE)
    assert metadata == {
        "title": "DD-1.0 Learning Adapter",
        "author": "DD-1.0",
        "description": "Thin adapter for the isolated DD-1.0 learning service.",
        "required_open_webui_version": "0.12.5",
        "version": "1.0.0",
    }


def test_loader_valves_and_signature_filter_match_open_webui(monkeypatch):
    monkeypatch.delenv("DD_LEARNING_BASE_URL", raising=False)
    monkeypatch.delenv("DD_LEARNING_ADAPTER_SECRET", raising=False)
    monkeypatch.delenv("DD_TRUSTED_SUBJECT", raising=False)
    module, tool = load_tool_module(TOOL_SOURCE)
    inject_valves(
        tool,
        {
            "DD_LEARNING_BASE_URL": "http://isolated-learning:32000",
            "DD_LEARNING_ADAPTER_SECRET": "valve-secret",
            "DD_TRUSTED_PROVIDER": "open-webui-test",
            "DD_TRUSTED_ISSUER": "isolated-installation",
        },
    )

    functions = discover_functions(tool)
    assert set(functions) == EXPECTED_FUNCTIONS
    assert tool.valves.model_dump()["DD_LEARNING_BASE_URL"] == "http://isolated-learning:32000"
    assert all("__user__" not in visible_parameters(function) for function in functions.values())
    assert all(not name.startswith("_") for name in functions)

    observed = {}

    def fake_urlopen(request, timeout):
        observed["request"] = request
        observed["timeout"] = timeout
        return _Response(b'{"learner_id":"learner-1"}')

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    result = json.loads(
        call_tool(
            tool,
            "get_progress",
            {"__user__": {"id": "model-controlled-subject"}},
            {"id": "trusted-open-webui-user", "email": "not-used@example.test"},
        )
    )
    assert result == {"learner_id": "learner-1"}
    request = observed["request"]
    assert request.full_url == "http://isolated-learning:32000/api/v1/progress"
    assert request.get_header("X-adapter-secret") == "valve-secret"
    assert request.get_header("X-trusted-provider") == "open-webui-test"
    assert request.get_header("X-trusted-issuer") == "isolated-installation"
    assert request.get_header("X-trusted-subject") == "trusted-open-webui-user"
    assert observed["timeout"] == 15

    # A host-owned per-user valve can carry the selected learner; model input
    # still has no path to replace it.
    call_tool(
        tool,
        "get_progress",
        {},
        {"id": "trusted-open-webui-user", "valves": tool.UserValves(DD_LEARNER_ID="learner-7")},
    )
    assert observed["request"].get_header("X-learner-id") == "learner-7"


def test_trusted_interaction_uses_native_input_callback_and_keeps_answer_out_of_tool_result(monkeypatch):
    module, tool = load_tool_module(TOOL_SOURCE)
    inject_valves(tool, {"DD_LEARNING_BASE_URL": "http://isolated-learning:32000"})
    observed = []

    def fake_urlopen(request, timeout):
        observed.append(request)
        if request.full_url.endswith("/api/v1/test-items/item%2F1"):
            return _Response(b'{"test_item_id":"item/1","prompt":"7-(-2)=?","answer_key":{"accepted":["9"]}}')
        if request.full_url.endswith("/submission-challenges"):
            return _Response(b'{"challenge_id":"challenge-1","nonce":"nonce-only-for-ui","operation":"submit_answer","resource_id":"item/1"}')
        if request.full_url.endswith("/answers"):
            return _Response(b'{"attempt_id":"attempt-1","status":"grading_pending","assessment_eligibility":true,"raw_answer":"private-answer"}')
        raise AssertionError(request.full_url)

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    events = []

    def event_call(event):
        events.append(event)
        return " 7-(-2)=9 "

    result = json.loads(
        asyncio.run(call_tool_async(
            tool,
            "start_trusted_interaction",
            {"operation": "submit_answer", "resource_id": "item/1", "__user__": {"id": "attacker"}, "__event_call__": "model-controlled"},
            {"id": "trusted-user"},
            event_call=event_call,
        ))
    )
    assert result == {"status": "grading_pending", "attempt_id": "attempt-1", "assessment_eligibility": True}
    assert events[0]["type"] == "input" and events[0]["data"]["message"] == "7-(-2)=?"
    assert "answer_key" not in events[0]["data"]["message"]
    assert len(observed) == 3
    assert observed[0].get_header("X-trusted-subject") == "trusted-user"
    assert json.loads(observed[-1].data)["raw_answer"] == " 7-(-2)=9 "
    assert "private-answer" not in json.dumps(result)
    assert "nonce" not in json.dumps(result) and "challenge_id" not in json.dumps(result)

    # Model-visible arguments exclude host event and user context. Only the
    # native loader supplies those reserved values during invocation.
    names = set(discover_functions(tool))
    assert not names.intersection({"confirm_import", "confirm_learning", "submit_answer", "consume_challenge"})
    assert "__event_call__" not in visible_parameters(discover_functions(tool)["start_trusted_interaction"])
    forbidden = json.loads(
        call_tool(
            tool,
            "start_trusted_interaction",
            {"operation": "submit_answer/../../answers", "resource_id": "item-1"},
            {"id": "trusted-user"},
        )
    )
    assert forbidden["error"]["code"] == "INTERACTION_OPERATION_FORBIDDEN"
    assert len(observed) == 3
