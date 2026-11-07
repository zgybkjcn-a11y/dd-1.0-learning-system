"""Reviewed local identity administration; never opens Open WebUI data."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .db import Database, json_dumps, new_id, utc_now
from .learner_context import invalidate_context


ROOT = Path(__file__).resolve().parents[1]
TABLES = ("schema_migrations", "accounts", "learners", "identity_bindings", "learner_access",
          "account_contexts", "knowledge_points", "review_objectives", "visual_templates")
ROWS = {"accounts": {"id"}, "learners": {"id", "display_name", "timezone", "curriculum_id"},
        "bindings": {"account_id", "provider", "issuer", "subject"},
        "grants": {"account_id", "learner_id", "role"},
        "revocations": {"account_id", "learner_id"}, "unbinds": {"provider", "issuer", "subject"}}
ROLES = {"student", "guardian", "reviewer", "admin"}


class IdentityPlanError(ValueError):
    pass


def reference(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value) is not None


def validate_manifest(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {"format", "initialize_math", *ROWS} or value["format"] != "dd-learning-identities-v1" or type(value["initialize_math"]) is not bool:
        raise IdentityPlanError("invalid manifest fields or format")
    for name, fields in ROWS.items():
        if not isinstance(value[name], list) or len(value[name]) > 1000:
            raise IdentityPlanError("invalid manifest collection")
        seen = set()
        for row in value[name]:
            if not isinstance(row, dict) or set(row) != fields:
                raise IdentityPlanError("invalid fields in " + name)
            for key, item in row.items():
                if key == "display_name":
                    if not isinstance(item, str) or not 1 <= len(item.strip()) <= 100 or any(ord(c) < 32 for c in item):
                        raise IdentityPlanError("invalid learner display name")
                elif key == "timezone":
                    try:
                        if not isinstance(item, str) or len(item) > 100:
                            raise ValueError()
                        ZoneInfo(item)
                    except (ValueError, ZoneInfoNotFoundError):
                        raise IdentityPlanError("invalid learner timezone")
                elif key in {"id", "account_id", "learner_id"} and (not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", item)):
                    raise IdentityPlanError("invalid account or learner id")
                elif not reference(item):
                    raise IdentityPlanError("invalid manifest reference")
            if "provider" in row and row["provider"] != "open-webui":
                raise IdentityPlanError("only open-webui installation identities are supported")
            if "role" in row and row["role"] not in ROLES:
                raise IdentityPlanError("invalid access role")
            if "curriculum_id" in row and row["curriculum_id"] not in {"math-g7-v1", "math-g2-v1"}:
                raise IdentityPlanError("unsupported curriculum")
            identity = tuple(row[k] for k in ("provider", "issuer", "subject")) if "subject" in row else tuple(row[k] for k in ("account_id", "learner_id")) if "role" in row or name == "revocations" else row["id"]
            if identity in seen:
                raise IdentityPlanError("duplicate " + name)
            seen.add(identity)
    if ({(r["account_id"], r["learner_id"]) for r in value["grants"]}
            & {(r["account_id"], r["learner_id"]) for r in value["revocations"]}):
        raise IdentityPlanError("grant/revocation conflict")
    if ({(r["provider"], r["issuer"], r["subject"]) for r in value["bindings"]}
            & {(r["provider"], r["issuer"], r["subject"]) for r in value["unbinds"]}):
        raise IdentityPlanError("binding/unbind conflict")
    # Sort all records so the reviewed hash is independent of input ordering.
    return {"format": value["format"], "initialize_math": value["initialize_math"],
            **{name: sorted(value[name], key=json_dumps) for name in ROWS}}


def target_path(path: Path) -> Path:
    absolute = path.absolute()
    if absolute.is_symlink() or any(p.is_symlink() for p in absolute.parents):
        raise IdentityPlanError("database symlinks are forbidden")
    path = absolute.resolve()
    protected = (ROOT / "data", Path("/app/backend/data"))
    if (path.suffix != ".db" or path.name in {"webui.db", "webui.sqlite"}
            or any(path.is_relative_to(p) for p in protected)):
        raise IdentityPlanError("use an explicit Learning database outside WebUI data")
    return path


def _snapshot(conn) -> dict:
    result = {}
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if tables and not {"accounts", "learners", "identity_bindings", "learner_access", "schema_migrations"}.issubset(tables):
        raise IdentityPlanError("target is not a Learning database")
    for table in TABLES:
        result[table] = sorted([dict(r) for r in conn.execute("SELECT * FROM " + table)], key=json_dumps) if table in tables else []
    return result


def _validate_state(manifest, state):
    accounts = {r["id"] for r in state["accounts"]} | {r["id"] for r in manifest["accounts"]}
    learners = {r["id"]: r for r in state["learners"]}
    for row in manifest["learners"]:
        if row["id"] in learners and any(learners[row["id"]][k] != row[k] for k in row):
            raise IdentityPlanError("existing learner differs; use a separate reviewed update")
        learners.setdefault(row["id"], row)
    bindings = {(r["provider"], r["issuer"], r["subject"]): r["account_id"] for r in state["identity_bindings"]}
    for row in manifest["bindings"]:
        key = (row["provider"], row["issuer"], row["subject"])
        if row["account_id"] not in accounts:
            raise IdentityPlanError("binding account does not exist")
        if key in bindings and bindings[key] != row["account_id"]:
            raise IdentityPlanError("identity is already bound to another account")
    for row in manifest["grants"] + manifest["revocations"]:
        if row["account_id"] not in accounts or row["learner_id"] not in learners:
            raise IdentityPlanError("access references a missing account or learner")
    for row in manifest["grants"]:
        if learners[row["learner_id"]].get("active", 1) != 1:
            raise IdentityPlanError("cannot grant access to an inactive learner")
    for row in manifest["unbinds"]:
        if (row["provider"], row["issuer"], row["subject"]) not in bindings:
            raise IdentityPlanError("cannot unbind a missing identity")


def _plan(manifest, path, operator, state):
    _validate_state(manifest, state)
    state_hash = hashlib.sha256(json_dumps(state).encode()).hexdigest()
    content = {"manifest": manifest, "database": str(path), "operator": operator, "state_sha256": state_hash}
    return {"format": "dd-learning-identity-plan-v1", "database": str(path), "operator": operator,
            "state_sha256": state_hash, "plan_sha256": hashlib.sha256(json_dumps(content).encode()).hexdigest(),
            "operations": {k: len(manifest[k]) for k in ROWS}, "initialize_math": manifest["initialize_math"],
            "verification_boundary": "local plan; no changes or production identity acceptance"}


def plan_identity(manifest, database: Path, operator: str) -> dict:
    manifest, path = validate_manifest(manifest), target_path(database)
    if not reference(operator):
        raise IdentityPlanError("explicit operator reference required")
    if path.exists():
        # No Database construction: no directories, migrations, or WAL negotiation.
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN")
            state = _snapshot(conn)
        finally:
            conn.close()
    else:
        state = {table: [] for table in TABLES}
    return _plan(manifest, path, operator, state)


def _initialize_math(conn):
    now = utc_now()
    kp = conn.execute("SELECT id FROM knowledge_points WHERE curriculum_id='math-g7-v1' AND code='signed-numbers'").fetchone()
    kp_id = kp["id"] if kp else "kp-math-g7-signed-numbers-v1"
    if not kp:
        conn.execute("INSERT INTO knowledge_points(id,curriculum_id,code,title,created_at) VALUES (?,?,?,?,?)", (kp_id, "math-g7-v1", "signed-numbers", "有理数与数轴", now))
    objective = conn.execute("SELECT 1 FROM review_objectives WHERE knowledge_point_id=? AND code='subtract-negative'", (kp_id,)).fetchone()
    if not objective:
        conn.execute("INSERT INTO review_objectives(id,knowledge_point_id,code,title,created_at) VALUES (?,?,?,?,?)", ("objective-math-g7-subtract-negative-v1", kp_id, "subtract-negative", "理解减去负数的运算方向", now))
    if not conn.execute("SELECT 1 FROM visual_templates WHERE template_id='signed_number_subtraction' AND version='1.0.0'").fetchone():
        conn.execute("INSERT INTO visual_templates(id,version,template_id,parameter_schema_json,approval,created_at) VALUES (?,?,?,?,?,?)",
                     ("template-signed-subtraction-v1", "1.0.0", "signed_number_subtraction", json_dumps({"start": {"type": "integer", "min": -100, "max": 100}, "subtrahend": {"type": "integer", "min": -100, "max": 100}}), "approved", now))
    if conn.execute("SELECT 1 FROM learners WHERE curriculum_id='math-g2-v1'").fetchone():
        for code, title in (("add-subtract-100", "100以内加减法"), ("multiplication", "表内乘法")):
            kp = conn.execute("SELECT id FROM knowledge_points WHERE curriculum_id='math-g2-v1' AND code=?", (code,)).fetchone()
            kp_id = kp["id"] if kp else "kp-math-g2-" + code
            if not kp:
                conn.execute("INSERT INTO knowledge_points(id,curriculum_id,code,title,created_at) VALUES (?,?,?,?,?)", (kp_id, "math-g2-v1", code, title, now))
            if not conn.execute("SELECT 1 FROM review_objectives WHERE knowledge_point_id=? AND code=?", (kp_id, code)).fetchone():
                conn.execute("INSERT INTO review_objectives(id,knowledge_point_id,code,title,created_at) VALUES (?,?,?,?,?)", ("objective-math-g2-" + code, kp_id, code, title, now))


def apply_identity(manifest, database: Path, operator: str, reviewed_sha256: str) -> dict:
    manifest, path = validate_manifest(manifest), target_path(database)
    # Preflight before creating directories or any new SQLite file.
    preflight = plan_identity(manifest, path, operator)
    if reviewed_sha256 != preflight["plan_sha256"]:
        raise IdentityPlanError("reviewed plan hash mismatch; create and review a new plan")
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        locked = _plan(manifest, path, operator, _snapshot(conn))
        if reviewed_sha256 != locked["plan_sha256"]:
            raise IdentityPlanError("database changed since review")
        # Migrations and administration share one transaction. A failure rolls
        # back DDL, bindings, grants and audit evidence together.
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL)")
        for migration in sorted((ROOT / "learning_service/migrations").glob("*.sql")):
            version = int(migration.name.split("_", 1)[0])
            if not conn.execute("SELECT 1 FROM schema_migrations WHERE version=?", (version,)).fetchone():
                Database._execute_migration(conn, migration.read_text())
                conn.execute("INSERT INTO schema_migrations VALUES (?,?)", (version, utc_now()))
        now, invalidated = utc_now(), set()
        for row in manifest["accounts"]:
            conn.execute("INSERT OR IGNORE INTO accounts(id,created_at) VALUES (?,?)", (row["id"], now))
        for row in manifest["learners"]:
            conn.execute("INSERT OR IGNORE INTO learners(id,display_name,timezone,curriculum_id,created_at) VALUES (?,?,?,?,?)", (row["id"], row["display_name"], row["timezone"], row["curriculum_id"], now))
        for row in manifest["bindings"]:
            conn.execute("INSERT OR IGNORE INTO identity_bindings(id,account_id,provider,issuer,subject,created_at) VALUES (?,?,?,?,?,?)", (new_id("binding"), row["account_id"], row["provider"], row["issuer"], row["subject"], now))
        for row in manifest["grants"]:
            prior = conn.execute("SELECT role,active FROM learner_access WHERE account_id=? AND learner_id=?", (row["account_id"], row["learner_id"])).fetchone()
            if prior and (prior["role"] != row["role"] or prior["active"] != 1):
                invalidated.add(row["account_id"])
            conn.execute("INSERT INTO learner_access(account_id,learner_id,role,active,created_at) VALUES (?,?,?,1,?) ON CONFLICT(account_id,learner_id) DO UPDATE SET role=excluded.role,active=1", (row["account_id"], row["learner_id"], row["role"], now))
        for row in manifest["revocations"]:
            conn.execute("UPDATE learner_access SET active=0 WHERE account_id=? AND learner_id=?", (row["account_id"], row["learner_id"]))
            invalidated.add(row["account_id"])
        for row in manifest["unbinds"]:
            account = conn.execute("SELECT account_id FROM identity_bindings WHERE provider=? AND issuer=? AND subject=?", (row["provider"], row["issuer"], row["subject"])).fetchone()
            conn.execute("DELETE FROM identity_bindings WHERE provider=? AND issuer=? AND subject=?", (row["provider"], row["issuer"], row["subject"]))
            invalidated.add(account["account_id"])
        for account in invalidated:
            invalidate_context(conn, account)
        if manifest["initialize_math"]:
            _initialize_math(conn)
        conn.execute("INSERT INTO audit_events(id,account_id,operation,resource_type,resource_id,result,metadata_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
                     (new_id("audit"), operator, "identity_manifest_apply", "identity_plan", reviewed_sha256, "applied", json_dumps({"plan_sha256": reviewed_sha256, "state_sha256": locked["state_sha256"], "operations": locked["operations"], "initialize_math": manifest["initialize_math"], "invalidated_accounts": sorted(invalidated), "changes": {k: [{f: v for f, v in r.items() if f != "display_name"} for r in manifest[k]] for k in ROWS}}), now))
        conn.commit()
        return {"status": "applied", "plan_sha256": reviewed_sha256, "operations": locked["operations"], "invalidated_accounts": sorted(invalidated)}
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
