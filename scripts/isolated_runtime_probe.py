"""Executed only inside the P0 learning-api container; no provider calls."""
import importlib.metadata
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from learning_service.config import Settings
from learning_service.db import Database, utc_now


def request(path, payload=None, headers=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(path, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(req, timeout=3) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


settings = Settings.from_env()
assert not settings.dev_mode and not settings.tencent_ocr_external_calls_enabled
assert not settings.tencent_ocr_secret_id and not settings.tencent_ocr_secret_key
assert (settings.document_provider, settings.diagnosis_provider, settings.variant_provider) == (
    "mock-document-v1", "mock-diagnosis-v1", "mock-variant-v1")
api = "http://127.0.0.1:31010"
status, health = request(api + "/health")
assert status == 200 and health["schema_revision"] == 7
assert request(api + "/internal/bootstrap", {})[0] == 404
assert request(api + "/api/v1/learners")[0] == 401
deadline = time.monotonic() + 150
while True:
    try:
        status, webui_health = request("http://open-webui:8080/health")
        if status == 200:
            break
    except (URLError, TimeoutError, ConnectionError):
        pass
    if time.monotonic() >= deadline:
        raise RuntimeError("isolated Open WebUI health timeout")
    time.sleep(2)
status, version = request("http://open-webui:8080/api/version")
assert status == 200 and version["version"] == "0.12.5"
with Database(settings.db_path).session(write=True) as db:
    for suffix in ("a", "b"):
        db.execute("INSERT OR IGNORE INTO accounts(id,created_at) VALUES (?,?)", ("p0-account-" + suffix, utc_now()))
        db.execute("INSERT OR IGNORE INTO learners(id,display_name,created_at) VALUES (?,?,?)",
                   ("p0-learner-" + suffix, "P0 Synthetic " + suffix.upper(), utc_now()))
        db.execute("INSERT OR IGNORE INTO identity_bindings(id,account_id,provider,issuer,subject,created_at) VALUES (?,?,?,?,?,?)",
                   ("p0-binding-" + suffix, "p0-account-" + suffix, "open-webui", "dd-p0", "p0-subject-" + suffix, utc_now()))
        db.execute("INSERT OR IGNORE INTO learner_access(account_id,learner_id,role,created_at) VALUES (?,?,?,?)",
                   ("p0-account-" + suffix, "p0-learner-" + suffix, "student", utc_now()))
headers = {"X-Adapter-Secret": settings.adapter_secret, "X-Trusted-Provider": "open-webui",
           "X-Trusted-Issuer": "dd-p0", "X-Trusted-Subject": "p0-subject-a", "X-Learner-Id": "p0-learner-a"}
status, learners = request(api + "/api/v1/learners", headers=headers)
assert status == 200 and len(learners["items"]) == 1 and learners["items"][0]["id"] == "p0-learner-a"
cross_status, cross = request(api + "/api/v1/learners", headers={**headers, "X-Learner-Id": "p0-learner-b"})
assert cross_status == 404 and cross["error"]["code"] == "LEARNER_NOT_FOUND"
status, contract = request(api + "/openapi.json")
assert status == 200 and len(contract["paths"]) == 56 and len(contract["components"]["schemas"]) == 20
assert contract == json.loads(Path("/tmp/dd-p0-openapi.json").read_text())
print(json.dumps({"learning_health": health, "open_webui_version": version["version"],
                  "bootstrap_status": 404, "untrusted_status": 401, "cross_learner_status": cross_status,
                  "authorized_learner_count": 1, "openapi_paths": 56, "openapi_schemas": 20,
                  "openapi_matches_snapshot": True,
                  "runtime_dependencies": {name: importlib.metadata.version(name) for name in
                      ("fastapi", "uvicorn", "pydantic", "python-multipart", "Pillow", "PyMuPDF")},
                  "providers": "deterministic mocks only", "tencent_external_calls": False,
                  "real_model_tool_call": "not_executed", "trusted_browser_callback": "not_executed"}))
