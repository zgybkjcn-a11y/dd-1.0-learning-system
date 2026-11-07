import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from learning_service.db import Database, utc_now
from learning_service.identity_admin import IdentityPlanError, ROOT, apply_identity, plan_identity, validate_manifest
from learning_service.learner_context import select_context


def manifest():
    return {"format": "dd-learning-identities-v1", "initialize_math": True,
            "accounts": [{"id": "account-1"}],
            "learners": [{"id": "learner-1", "display_name": "合成学习者", "timezone": "Asia/Shanghai", "curriculum_id": "math-g7-v1"}],
            "bindings": [{"account_id": "account-1", "provider": "open-webui", "issuer": "synthetic-installation", "subject": "synthetic-webui-id"}],
            "grants": [{"account_id": "account-1", "learner_id": "learner-1", "role": "guardian"}], "revocations": [], "unbinds": []}


def empty():
    return {**manifest(), "initialize_math": False, "accounts": [], "learners": [], "bindings": [], "grants": []}


def apply(m, path):
    plan = plan_identity(m, path, "synthetic-operator")
    return apply_identity(m, path, "synthetic-operator", plan["plan_sha256"])


def test_new_database_plan_has_no_files_and_apply_requires_review(tmp_path):
    path = tmp_path/"new/learning.db"
    plan = plan_identity(manifest(), path, "synthetic-operator")
    assert not path.parent.exists()
    with pytest.raises(IdentityPlanError, match="hash mismatch"):
        apply_identity(manifest(), path, "synthetic-operator", "unreviewed")
    assert not path.parent.exists()
    assert apply_identity(manifest(), path, "synthetic-operator", plan["plan_sha256"])["status"] == "applied"
    db = Database(path)
    with db.session() as conn:
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 11
        assert conn.execute("SELECT role FROM learner_access").fetchone()[0] == "guardian"
        assert conn.execute("SELECT COUNT(*) FROM review_objectives").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0
        audit = json.loads(conn.execute("SELECT metadata_json FROM audit_events").fetchone()[0])
        assert audit["plan_sha256"] == plan["plan_sha256"] and "display_name" not in audit["changes"]["learners"][0]


def test_plan_existing_legacy_database_does_not_migrate_or_change_bytes(tmp_path):
    import shutil
    migrations = tmp_path/"migrations"; migrations.mkdir()
    shutil.copy2(ROOT/"learning_service/migrations/001_initial.sql", migrations/"001_initial.sql")
    db = Database(tmp_path/"learning.db", migrations)
    before = db.path.read_bytes()
    plan_identity(manifest(), db.path, "synthetic-operator")
    assert db.path.read_bytes() == before
    with db.session() as conn:
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 1


@pytest.mark.parametrize("bad", ["role", "timezone", "duplicate", "extra", "provider", "curriculum", "conflict", "identity_conflict", "id"])
def test_strict_manifest_rejects_invalid_or_ambiguous_changes(bad):
    m = manifest()
    if bad == "role": m["grants"][0]["role"] = "owner"
    if bad == "timezone": m["learners"][0]["timezone"] = "Bad/Zone"
    if bad == "duplicate": m["bindings"].append(copy.deepcopy(m["bindings"][0]))
    if bad == "extra": m["bindings"][0]["token"] = "never-allowed"
    if bad == "provider": m["bindings"][0]["provider"] = "untrusted"
    if bad == "curriculum": m["learners"][0]["curriculum_id"] = "other"
    if bad == "conflict": m["revocations"] = [{"account_id": "account-1", "learner_id": "learner-1"}]
    if bad == "identity_conflict": m["unbinds"] = [{k:v for k,v in m["bindings"][0].items() if k != "account_id"}]
    if bad == "id": m["learners"][0]["id"] = "learner:invalid"
    with pytest.raises(IdentityPlanError): validate_manifest(m)


def test_conflict_and_stale_plan_preserve_all_data(tmp_path):
    path = tmp_path/"learning.db"
    apply(manifest(), path)
    m = empty(); m["accounts"] = [{"id": "account-2"}]; m["bindings"] = [{**manifest()["bindings"][0], "account_id": "account-2"}]
    with pytest.raises(IdentityPlanError, match="another account"):
        plan_identity(m, path, "synthetic-operator")
    m = empty(); m["accounts"] = [{"id": "account-2"}]
    plan = plan_identity(m, path, "synthetic-operator")
    db = Database(path)
    with db.session(write=True) as conn:
        conn.execute("UPDATE learners SET display_name='changed' WHERE id='learner-1'")
    with pytest.raises(IdentityPlanError, match="hash mismatch"):
        apply_identity(m, path, "synthetic-operator", plan["plan_sha256"])
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 1


@pytest.mark.parametrize("action", ["revocations", "unbinds", "role_change"])
def test_revocation_unbind_and_role_change_revoke_sessions_context_and_challenges(tmp_path, action):
    path = tmp_path/"learning.db"
    apply(manifest(), path)
    db = Database(path)
    with db.session(write=True) as conn:
        select_context(conn, "account-1", "learner-1", 0)
        conn.execute("INSERT INTO browser_sessions(id,token_hash,csrf_hash,account_id,provider,issuer,subject,learner_id,expires_at,created_at) VALUES ('s','t','c','account-1','open-webui','synthetic-installation','synthetic-webui-id','learner-1','2099-01-01',?)", (utc_now(),))
        conn.execute("INSERT INTO interaction_challenges(id,actor_account_id,learner_id,operation,resource_id,resource_versions_json,nonce_hash,expires_at,created_at) VALUES ('c','account-1','learner-1','x','x','{}','n','2099-01-01',?)", (utc_now(),))
    m = empty()
    if action == "role_change": m["grants"] = [{"account_id": "account-1", "learner_id": "learner-1", "role": "student"}]
    elif action == "revocations": m[action] = [{"account_id": "account-1", "learner_id": "learner-1"}]
    else: m[action] = [{k:v for k,v in manifest()["bindings"][0].items() if k != "account_id"}]
    apply(m, path)
    with db.session() as conn:
        assert conn.execute("SELECT revoked_at FROM browser_sessions").fetchone()[0]
        assert conn.execute("SELECT consumed_at FROM interaction_challenges").fetchone()[0]
        assert tuple(conn.execute("SELECT learner_id,revision FROM account_contexts").fetchone()) == (None, 2)
        assert conn.execute("SELECT COUNT(*) FROM learners").fetchone()[0] == 1


def test_apply_failure_rolls_back_every_change(tmp_path):
    path = tmp_path/"learning.db"
    db = Database(path)
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO knowledge_points(id,curriculum_id,code,title,created_at) VALUES ('kp-math-g7-signed-numbers-v1','math-g7-v1','other','conflict',?)", (utc_now(),))
    plan = plan_identity(manifest(), path, "synthetic-operator")
    with pytest.raises(sqlite3.IntegrityError): apply_identity(manifest(), path, "synthetic-operator", plan["plan_sha256"])
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 0


def test_cli_validate_and_plan_do_not_create_target_and_forbidden_targets_reject(tmp_path):
    source = tmp_path/"manifest.json"; source.write_text(json.dumps(manifest()))
    target = tmp_path/"new/learning.db"
    script = ROOT/"scripts/manage_learning_identities.py"
    for action in ("validate", "plan"):
        r = subprocess.run([sys.executable, str(script), action, "--manifest", str(source), "--database", str(target), "--operator", "synthetic-operator"], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    assert not target.parent.exists()
    for forbidden in (ROOT/"data/new-learning.db", tmp_path/"webui.db", Path("/app/backend/data/learning.db")):
        with pytest.raises(IdentityPlanError): plan_identity(manifest(), forbidden, "operator")
