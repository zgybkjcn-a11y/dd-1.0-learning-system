"""P0 current-source registration/loader probe inside disposable Open WebUI.

Only native local auth/tools endpoints and the isolated Learning API are used.
No model calls or input/confirmation callbacks are executed.
"""
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request as HTTPRequest, urlopen


def request(path, payload=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(payload).encode() if payload is not None else None
    req = HTTPRequest("http://127.0.0.1:8080" + path, data=data, headers=headers)
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


assert os.environ["ENABLE_OPENAI_API"] == "false" and os.environ["ENABLE_OLLAMA_API"] == "false"
assert os.environ["OFFLINE_MODE"] == "true"
status, user = request("/api/v1/auths/signin", {
    "email": os.environ["WEBUI_ADMIN_EMAIL"], "password": os.environ["WEBUI_ADMIN_PASSWORD"]})
assert status == 200 and user["role"] == "admin"
token = user["token"]
tool_id = "dd_learning_v1"
source = Path("/tmp/dd-p0-tools.py").read_text()
source_hash = hashlib.sha256(source.encode()).hexdigest()

if sys.argv[1] == "register":
    status, record = request("/api/v1/tools/id/" + tool_id, token=token)
    if status != 200:
        status, record = request("/api/v1/tools/create", {
            "id": tool_id, "name": "DD Learning V1 P0", "content": source,
            "meta": {"description": "Current-source mock-only P0 adapter"}, "access_grants": []}, token)
    assert status == 200 and hashlib.sha256(record["content"].encode()).hexdigest() == source_hash
    status, _ = request(f"/api/v1/tools/id/{tool_id}/valves/update", {
        "DD_LEARNING_BASE_URL": "http://learning-api:31010",
        "DD_LEARNING_ADAPTER_SECRET": os.environ["DD_LEARNING_ADAPTER_SECRET"],
        "DD_TRUSTED_PROVIDER": "open-webui", "DD_TRUSTED_ISSUER": "dd-p0", "DD_TRUSTED_SUBJECT": ""}, token)
    assert status == 200
    status, _ = request(f"/api/v1/tools/id/{tool_id}/valves/user/update", {"DD_LEARNER_ID": "p0-learner-a"}, token)
    assert status == 200
    status, models = request("/api/models", token=token)
    assert status == 200 and models["data"] == []
    print(json.dumps({"user_id": user["id"], "tool_id": tool_id, "tool_sha256": source_hash,
                      "model_count": 0, "registration": "current_source_in_fresh_isolated_instance"}))
else:
    sys.path.insert(0, "/app/backend")
    from fastapi import Request
    from open_webui.models.users import Users
    from open_webui.utils.tools import get_tools

    async def load():
        host_user = await Users.get_user_by_id(user["id"])
        req = Request({"type": "http", "app": SimpleNamespace(state=SimpleNamespace()), "headers": []})
        status, record = request("/api/v1/tools/id/" + tool_id, token=token)
        assert status == 200 and hashlib.sha256(record["content"].encode()).hexdigest() == source_hash
        loaded = await get_tools(req, [tool_id], host_user, {"__user__": host_user.model_dump()})
        expected = {"get_attempt", "get_mistakes", "get_progress", "get_review_tasks", "list_learners",
                    "request_diagnosis", "request_document_analysis", "request_hint", "request_variant",
                    "request_visual", "start_trusted_interaction"}
        assert set(loaded) == expected
        assert all(not any(name.startswith("__") for name in t["spec"]["parameters"]["properties"]) for t in loaded.values())
        result = json.loads(await loaded["list_learners"]["callable"]())
        assert len(result["items"]) == 1 and result["items"][0]["id"] == "p0-learner-a"
        return {"tool_sha256": source_hash, "public_method_count": len(loaded),
                "native_loader": "passed_current_source", "authorized_learner_count": 1,
                "host_identity_and_user_valves": "passed_isolated_synthetic_identity",
                "real_model_tool_call": "not_executed", "trusted_browser_callback": "not_executed"}

    print(json.dumps(asyncio.run(load())))
