from contextlib import contextmanager
from dataclasses import replace
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from learning_service.app import create_app
from learning_service.backup import backup_data, restore_data
from learning_service.db import Database, WriteContextChanged, utc_now, write_context
from learning_service.learner_context import select_context
from test_browser_auth import auth_env, login, csrf
from test_learning_service import env


@pytest.fixture
def shared_env(auth_env):
    s, db, _ = auth_env
    s = replace(s, shared_learner_context_enabled=True, public_base_path="/learning")
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO learner_access(account_id,learner_id,role,active,created_at) VALUES ('acct-a','learner-b','guardian',1,?)", (utc_now(),))
    client = TestClient(create_app(s, db), base_url=s.browser_origin)
    assert login(s, client).status_code == 201
    return s, db, client


def choose(s, client, learner, version):
    return client.post("/api/v1/learner-context", json={"learner_id": learner, "expected_revision": version}, headers=csrf(s, client))


def test_shared_selection_cas_no_header_override_and_cross_session_sync(shared_env):
    s, db, client = shared_env
    assert client.get("/api/v1/learner-context").json() == {"learner_id": None, "context_version": 0}
    assert choose(s, client, "learner-a", True).status_code == 409
    assert choose(s, client, "learner-a", 0).json()["context_version"] == 1
    assert choose(s, client, "learner-a", 1).json()["context_version"] == 1
    other = TestClient(client.app, base_url=s.browser_origin)
    assert login(s, other, changes={"jti": "another-jti"}).status_code == 201
    assert other.get("/api/v1/auth/session").json()["learner_id"] == "learner-a"
    assert choose(s, other, "learner-b", 1).json()["context_version"] == 2
    assert choose(s, client, "learner-a", 1).status_code == 409
    assert client.get("/api/v1/learner-context").json() == {"learner_id": "learner-b", "context_version": 2}
    headers = {**csrf(s, client), "X-Learner-Context-Version": "2", "X-Learner-Id": "learner-a", "Idempotency-Key": "synthetic-manual"}
    result = client.post("/api/v1/mistakes/manual", json={"question_text": "synthetic exercise"}, headers=headers)
    assert result.status_code == 201
    with db.session() as conn:
        assert conn.execute("SELECT learner_id FROM mistake_entries").fetchone()[0] == "learner-b"
    assert client.post("/api/v1/mistakes/manual", json={"question_text": "stale"}, headers={**headers, "X-Learner-Context-Version": "1"}).status_code == 409
    assert client.get("/api/v1/mistakes", headers={"X-Learner-Context-Version": "1"}).status_code == 409


def test_switch_invalidates_challenges_and_adapter_cannot_select(shared_env):
    s, db, client = shared_env
    assert choose(s, client, "learner-a", 0).status_code == 200
    h = {**csrf(s, client), "X-Learner-Context-Version": "1", "Idempotency-Key": "synthetic-draft"}
    draft = client.post("/api/v1/learning-drafts", json={"objective_id": "obj-1", "content": {"note": "synthetic"}}, headers=h).json()
    response = client.post(f'/api/v1/learning-drafts/{draft["draft_id"]}/confirmation-challenges', headers=h)
    assert response.status_code == 200
    assert choose(s, client, "learner-b", 1).status_code == 200
    with db.session() as conn:
        assert conn.execute("SELECT consumed_at FROM interaction_challenges").fetchone()[0]
    adapter = TestClient(client.app, base_url=s.browser_origin)
    trusted = {"X-Adapter-Secret": s.adapter_secret, "X-Trusted-Provider": "open-webui", "X-Trusted-Issuer": "open-webui", "X-Trusted-Subject": "subject-a"}
    assert adapter.get("/api/v1/learner-context", headers=trusted).json()["learner_id"] == "learner-b"
    assert adapter.get("/api/v1/mistakes", headers={**trusted, "X-Learner-Id": "learner-a"}).status_code == 409
    assert adapter.post("/api/v1/learner-context", json={"learner_id": "learner-a", "expected_revision": 2}, headers=trusted).status_code == 403


def test_write_transaction_rejects_switch_after_authorization(shared_env, monkeypatch):
    s, db, client = shared_env
    assert choose(s, client, "learner-a", 0).status_code == 200
    original = db.session
    @contextmanager
    def racing_session(write=False):
        if write and write_context.get():
            token = write_context.set(None)
            try:
                with original(write=True) as conn:
                    select_context(conn, "acct-a", "learner-b", 1)
            finally:
                write_context.reset(token)
        with original(write=write) as conn:
            yield conn
    monkeypatch.setattr(db, "session", racing_session)
    response = client.post("/api/v1/mistakes/manual", json={"question_text": "racing exercise"}, headers={**csrf(s, client), "X-Learner-Context-Version": "1", "Idempotency-Key": "synthetic-race"})
    assert response.status_code == 409
    with original() as conn:
        assert conn.execute("SELECT COUNT(*) FROM mistake_entries").fetchone()[0] == 0


def test_migration10_revokes_old_unattributed_sessions(tmp_path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    for sql in (Path(__file__).parents[1]/"learning_service/migrations").glob("*.sql"):
        if int(sql.name[:3]) <= 9:
            shutil.copy2(sql, migrations / sql.name)
    db = Database(tmp_path/"legacy.db", migrations)
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO accounts VALUES ('a',?)", (utc_now(),))
        conn.execute("INSERT INTO browser_sessions(id,token_hash,csrf_hash,account_id,provider,expires_at,created_at) VALUES ('s','t','c','a','open-webui','2099-01-01',?)", (utc_now(),))
    upgraded = Database(db.path)
    with upgraded.session() as conn:
        row = conn.execute("SELECT issuer,subject,revoked_at FROM browser_sessions").fetchone()
        assert row[0] is None and row[1] is None and row[2]
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 11


def test_restore_clears_selected_context_and_old_challenges(shared_env, tmp_path):
    s, db, client = shared_env
    assert choose(s, client, "learner-a", 0).status_code == 200
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO interaction_challenges(id,actor_account_id,learner_id,operation,resource_id,resource_versions_json,nonce_hash,expires_at,created_at) VALUES ('c','acct-a','learner-a','x','x','{}','x','2099-01-01',?)", (utc_now(),))
    backup_data(s.data_dir, tmp_path/"backup")
    restore_data(tmp_path/"backup", tmp_path/"restored")
    restored = Database(tmp_path/"restored/learning.db")
    with restored.session() as conn:
        assert tuple(conn.execute("SELECT learner_id,revision FROM account_contexts").fetchone()) == (None, 2)
        assert conn.execute("SELECT consumed_at FROM interaction_challenges").fetchone()[0]
