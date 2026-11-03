from __future__ import annotations

import io
import json
import sqlite3
import asyncio
import shutil
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import fitz
from PIL import Image
from starlette.requests import Request

from learning_service.app import (
    APIError,
    ChallengeRequest,
    ConfirmationRequest,
    AnswerRequest,
    AgentRunRequest,
    AgentStepRequest,
    BatchRequest,
    Context,
    DraftConfirmation,
    DraftRequest,
    ItemPatch,
    PagePatch,
    ReviewDecisionRequest,
    ReviewRequestRequest,
    TestSessionRequest as SessionRequest,
    Settings,
    _page_count,
    _ensure_review_card,
    _scheduled_due,
    create_app,
    run_worker_once,
)
from learning_service.backup import backup_data, restore_data
from learning_service.db import Database, json_dumps, new_id, utc_now
from learning_service.providers import ProviderResult, diagnosis_provider, document_provider, variant_provider


def _request(headers: dict[str, str] | None = None) -> Request:
    raw = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request({"type": "http", "method": "POST", "path": "/", "headers": raw, "query_string": b""})


@pytest.fixture()
def env(tmp_path: Path):
    settings = Settings(tmp_path, tmp_path / "learning.db", tmp_path / "attachments", "admin", "adapter", True)
    db = Database(settings.db_path)
    app = create_app(settings, db)
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO accounts(id,created_at) VALUES (?,?)", ("acct-a", now))
        conn.execute("INSERT INTO accounts(id,created_at) VALUES (?,?)", ("acct-b", now))
        conn.execute("INSERT INTO learners(id,display_name,timezone,curriculum_id,created_at) VALUES (?,?,?,?,?)", ("learner-a", "A", "Asia/Shanghai", "math-g7-v1", now))
        conn.execute("INSERT INTO learners(id,display_name,timezone,curriculum_id,created_at) VALUES (?,?,?,?,?)", ("learner-b", "B", "Asia/Shanghai", "math-g7-v1", now))
        conn.execute("INSERT INTO learner_access(account_id,learner_id,role,created_at) VALUES (?,?,?,?)", ("acct-a", "learner-a", "admin", now))
        conn.execute("INSERT INTO learner_access(account_id,learner_id,role,created_at) VALUES (?,?,?,?)", ("acct-b", "learner-b", "student", now))
        conn.execute("INSERT INTO knowledge_points(id,curriculum_id,code,title,created_at) VALUES (?,?,?,?,?)", ("kp-1", "math-g7-v1", "signed", "有理数", now))
        conn.execute("INSERT INTO review_objectives(id,knowledge_point_id,code,title,created_at) VALUES (?,?,?,?,?)", ("obj-1", "kp-1", "subtract", "减去负数", now))
    return settings, db, app


def _route(app, path: str):
    return next(route.endpoint for route in app.routes if getattr(route, "path", None) == path)


class _AsyncUpload:
    """Avoid Starlette's threadpool-backed UploadFile in direct route tests."""

    def __init__(self, payload: bytes, filename: str, content_type: str):
        self._payload = payload
        self.filename = filename
        self.content_type = content_type

    async def read(self, size: int = -1) -> bytes:
        return self._payload if size < 0 else self._payload[:size]


def test_migration_and_learner_isolation(env, tmp_path: Path):
    _, db, _ = env
    with db.session() as conn:
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 6
        assert conn.execute("SELECT 1 FROM pragma_table_info('source_pages') WHERE name='asset_id'").fetchone() is not None
        assert conn.execute("SELECT 1 FROM pragma_table_info('import_batches') WHERE name='answer_document_id'").fetchone() is not None
        assert conn.execute("SELECT 1 FROM pragma_table_info('question_versions') WHERE name='variant_kind'").fetchone() is not None
        assert conn.execute("SELECT 1 FROM pragma_table_info('question_versions') WHERE name='variant_group'").fetchone() is not None
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_requests'").fetchone() is not None
        assert conn.execute("SELECT COUNT(*) FROM learner_access WHERE account_id='acct-a'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM learner_access WHERE account_id='acct-b'").fetchone()[0] == 1
        assert conn.execute("SELECT 1 FROM learner_access WHERE account_id='acct-a' AND learner_id='learner-b'").fetchone() is None

    legacy_migrations = tmp_path / "legacy-migrations"
    legacy_migrations.mkdir()
    shutil.copy2(Path(__file__).parents[1] / "learning_service/migrations/001_initial.sql", legacy_migrations / "001_initial.sql")
    legacy_db = Database(tmp_path / "legacy.db", legacy_migrations)
    upgraded_db = Database(legacy_db.path)
    with upgraded_db.session() as conn:
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 6
        assert conn.execute("SELECT 1 FROM pragma_table_info('source_pages') WHERE name='asset_id'").fetchone() is not None
        assert conn.execute("SELECT 1 FROM pragma_table_info('import_batches') WHERE name='answer_document_id'").fetchone() is not None
        assert conn.execute("SELECT 1 FROM pragma_table_info('question_versions') WHERE name='variant_kind'").fetchone() is not None
        assert conn.execute("SELECT 1 FROM pragma_table_info('question_versions') WHERE name='variant_group'").fetchone() is not None
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_requests'").fetchone() is not None


def test_migration006_backfills_agent_budget_start_for_legacy_runs(tmp_path: Path):
    legacy_migrations = tmp_path / "legacy-migrations"
    legacy_migrations.mkdir()
    migrations = Path(__file__).parents[1] / "learning_service/migrations"
    for version in range(1, 6):
        source = next(migrations.glob(f"{version:03d}_*.sql"))
        shutil.copy2(source, legacy_migrations / source.name)
    db_path = tmp_path / "legacy-agent.db"
    legacy_db = Database(db_path, legacy_migrations)
    created_at = "2026-11-03T12:34:56+00:00"
    with legacy_db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO learners(id,display_name,created_at) VALUES (?,?,?)",
            ("legacy-learner", "Legacy", created_at),
        )
        conn.execute(
            "INSERT INTO agent_runs(id,learner_id,goal,allowed_actions_json,budget_steps,budget_ms,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            ("legacy-run", "legacy-learner", "backfill", "[]", 1, 100, created_at, created_at),
        )

    upgraded = Database(db_path)
    with upgraded.session() as conn:
        row = conn.execute("SELECT budget_started_at,created_at FROM agent_runs WHERE id='legacy-run'").fetchone()
        assert tuple(row) == (created_at, created_at)


def test_migration_failure_rolls_back_ddl_and_can_be_retried(tmp_path: Path):
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    migration = migration_dir / "005_atomic.sql"
    migration.write_text(
        "CREATE TABLE migration_probe (id INTEGER PRIMARY KEY);\n"
        "ALTER TABLE missing_table ADD COLUMN value TEXT;\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "atomic-migration.db"
    with pytest.raises(sqlite3.OperationalError, match="no such table: missing_table"):
        Database(db_path, migration_dir)

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='migration_probe'").fetchone() is None
        assert conn.execute("SELECT 1 FROM schema_migrations WHERE version=5").fetchone() is None
    finally:
        conn.close()

    migration.write_text("CREATE TABLE migration_probe (id INTEGER PRIMARY KEY);\n", encoding="utf-8")
    upgraded = Database(db_path, migration_dir)
    with upgraded.session() as conn:
        # The isolated fixture contains only migration 005.
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 5
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='migration_probe'").fetchone() is not None


def test_concurrent_fresh_database_migrations_serialize(tmp_path: Path):
    db_path = tmp_path / "concurrent-migration.db"
    code = "from pathlib import Path; import sys; from learning_service.db import Database; Database(Path(sys.argv[1]))"
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(db_path)],
            cwd=Path(__file__).parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(2)
    ]
    results = [process.communicate(timeout=30) + (process.returncode,) for process in processes]
    assert all(return_code == 0 for _, stderr, return_code in results), results
    db = Database(db_path)
    with db.session() as conn:
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 6


def test_ui_exposes_workbench_controls(env):
    _, _, app = env
    response = _route(app, "/ui")()
    html = response.body.decode("utf-8")
    assert response.media_type == "text/html"
    assert "DD-1.0 学习工作区" in html
    assert "创建整卷批次" in html
    assert "候选复核与确认" in html
    assert "确认选中项" in html
    assert "localStorage" in html
    assert "dd-learning-test" in html
    assert "恢复测验" in html
    assert "请求提示" in html
    assert "取消测验" in html
    assert "读取判分" in html
    assert "申请复核" in html
    assert "202 不是最终成绩" in html
    assert "/api/v1/test-sessions/" in html
    assert "/api/v1/attempts/" in html
    assert "'/api/v1/test-items/' + encodeURIComponent(item) + '/submission-challenges', {method: 'POST'}" in html
    assert "answer_key_json" not in html
    assert "replaceChildren" in html
    assert ".innerHTML" not in html


def test_test_session_recovery_returns_attempt_state_without_answer(env):
    settings, db, app = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?)", ("q-recover", "shared", "approved", "obj-1", now))
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,?,?,?,?,?,?)", ("qv-recover", "q-recover", 1, '{"prompt":"恢复用 2+2","hint":"先列算式"}', '{"accepted":["4"]}', "exact-text-v1", "approved", now))
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    session = _route(app, "/api/v1/test-sessions")(SessionRequest(question_version_id="qv-recover"), ctx, db)
    session_id, item_id = session["session_id"], session["items"][0]["test_item_id"]
    read_session = _route(app, "/api/v1/test-sessions/{session_id}")
    initial = read_session(session_id, ctx, db)
    assert initial["answer_key"] is None
    assert initial["items"][0]["prompt"] == "恢复用 2+2"
    assert initial["items"][0]["attempt_id"] is None
    assert "raw_answer" not in json.dumps(initial)
    assert "answer_key_json" not in json.dumps(initial)

    challenge = _route(app, "/api/v1/test-items/{item_id}/submission-challenges")(item_id, ctx, db, settings)
    accepted = _route(app, "/api/v1/test-items/{item_id}/answers")(
        item_id,
        AnswerRequest(challenge_id=challenge["challenge_id"], nonce=challenge["nonce"], raw_answer="4"),
        _request({"Idempotency-Key": "recover-answer"}),
        ctx,
        db,
    )
    recovered = read_session(session_id, ctx, db)
    assert recovered["items"][0]["attempt_id"] == accepted["attempt_id"]
    assert recovered["items"][0]["attempt_status"] == "grading_pending"
    assert recovered["items"][0]["status"] == "grading_pending"
    assert "raw_answer" not in json.dumps(recovered)
    assert "answer_key_json" not in json.dumps(recovered)

    assert run_worker_once(db, settings)["status"] == "succeeded"
    completed = read_session(session_id, ctx, db)
    assert completed["items"][0]["attempt_status"] == "graded"
    assert completed["answer_key"] is None


def test_admin_metrics_are_aggregated_and_privacy_preserving(env):
    settings, db, app = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("asset-metrics", "learner-a", "private", "learner-a/metrics.png", "metrics-hash", "image/png", 1, "source_document", now),
        )
        conn.execute(
            "INSERT INTO source_documents(id,learner_id,asset_id,kind,status,page_count,created_at) VALUES (?,?,?,?,?,?,?)",
            ("doc-metrics", "learner-a", "asset-metrics", "paper", "stored", 1, now),
        )
        conn.execute(
            "INSERT INTO import_batches(id,learner_id,document_ids_json,status,total_pages,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            ("batch-metrics", "learner-a", '["doc-metrics"]', "awaiting_review", 1, now, now),
        )
        conn.execute(
            "INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            ("job-metrics", "learner-a", "document_analysis", "{}", "metrics-key", "queued", now, now),
        )
        conn.execute(
            "INSERT INTO source_pages(id,document_id,page_index,status,failure_code,transform_json) VALUES (?,?,?,?,?,?)",
            ("page-metrics", "doc-metrics", 0, "failed", "PDF_PAGE_RENDER_FAILED", "{}"),
        )
        conn.execute(
            "INSERT INTO import_items(id,batch_id,learner_id,occurrence_id,locator,page_index,content_json,verification_status,status) VALUES (?,?,?,?,?,?,?,?,?)",
            ("item-metrics", "batch-metrics", "learner-a", "metrics-occurrence", "page:1:item:1", 0, '{"raw_answer":"private"}', "needs_review", "needs_review"),
        )
    endpoint = _route(app, "/api/v1/admin/metrics")
    metrics = endpoint(Context(account_id="acct-a", learner_id="learner-a", role="admin"), db)
    assert metrics["jobs"]["by_status"]["queued"] == 1
    assert metrics["jobs"]["oldest_queued_age_seconds"] is not None
    assert metrics["pages"] == {"total": 1, "failed": 1, "failure_ratio": 1.0}
    assert metrics["review"]["pending_items"] == 1
    assert metrics["external_calls"]["tracked"] is False
    assert "learner-a" not in json.dumps(metrics, ensure_ascii=False)
    with pytest.raises(APIError, match="需要管理权限"):
        endpoint(Context(account_id="acct-b", learner_id="learner-b", role="student"), db)


def test_image_and_pdf_decode_failures_are_visible():
    image = Image.new("RGB", (2, 3), "white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    assert _page_count(output.getvalue(), "image/png") == (1, None)
    assert _page_count(b"\x89PNG\r\n\x1a\nnot-an-image", "image/png")[1] == "IMAGE_DECODE_FAILED"
    assert _page_count(b"%PDF-1.4\nnot-a-real-pdf", "application/pdf")[1] == "PDF_DECODE_FAILED"


def test_multipage_pdf_keeps_page_assets_and_page_content_endpoint(env):
    settings, db, app = env
    pdf = fitz.open()
    pdf.new_page(width=120, height=80)
    pdf.new_page(width=160, height=90)
    payload = pdf.tobytes()
    pdf.close()
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    document = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(payload, "pages.pdf", "application/pdf"), "paper", None, ctx, db, settings))
    assert document["page_count"] == 2
    with db.session() as conn:
        pages = conn.execute("SELECT page_index,object_key,asset_id,width,height FROM source_pages WHERE document_id=? ORDER BY page_index", (document["document_id"],)).fetchall()
        assets = conn.execute("SELECT purpose,media_type FROM assets WHERE learner_id=? ORDER BY purpose,object_key", ("learner-a",)).fetchall()
    assert len(pages) == 2
    assert all(row["object_key"] and row["asset_id"] and row["width"] and row["height"] for row in pages)
    assert [row["purpose"] for row in assets] == ["source_document", "source_page", "source_page"]
    # The endpoint is keyed by source page id; fetch that id explicitly for clarity.
    with db.session() as conn:
        page_id = conn.execute("SELECT id FROM source_pages WHERE document_id=? AND page_index=1", (document["document_id"],)).fetchone()[0]
    page_response = _route(app, "/api/v1/source-pages/{page_id}/content")(page_id, ctx, db, settings)
    assert page_response.media_type == "image/png"
    assert Path(page_response.path).is_file()

    backup_dir = settings.data_dir.parent / "pdf-backup"
    manifest = backup_data(settings.data_dir, backup_dir)
    restored_dir = settings.data_dir.parent / "pdf-restored"
    restore_data(backup_dir, restored_dir)
    restored_db = Database(restored_dir / "learning.db")
    with restored_db.session() as conn:
        restored_page = conn.execute("SELECT asset_id,object_key FROM source_pages WHERE id=?", (page_id,)).fetchone()
        assert restored_page["asset_id"]
        assert (restored_dir / "attachments" / restored_page["object_key"]).is_file()
        assert manifest["files"]

    delete_endpoint = _route(app, "/api/v1/admin/deletions")
    assert delete_endpoint({"learner_id": "learner-a"}, ctx, db)["assets_marked"] == 3
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM assets WHERE learner_id='learner-a' AND deleted_at IS NOT NULL").fetchone()[0] == 3
    with pytest.raises(APIError, match="学习者不可访问"):
        _route(app, "/api/v1/source-pages/{page_id}/content")(page_id, ctx, db, settings)


def test_batch_persists_answer_document_reference(env):
    settings, db, app = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)", ("asset-paper", "learner-a", "private", "learner-a/paper.png", "hash-paper", "image/png", 1, "source_document", now))
        conn.execute("INSERT INTO source_documents(id,learner_id,asset_id,kind,status,page_count,created_at) VALUES (?,?,?,?,?,?,?)", ("doc-paper", "learner-a", "asset-paper", "paper", "stored", 1, now))
        conn.execute("INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)", ("asset-answer", "learner-a", "private", "learner-a/answer.png", "hash-answer", "image/png", 1, "source_document", now))
        conn.execute("INSERT INTO source_documents(id,learner_id,asset_id,kind,status,page_count,created_at) VALUES (?,?,?,?,?,?,?)", ("doc-answer", "learner-a", "asset-answer", "answer_key", "stored", 1, now))
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    result = _route(app, "/api/v1/import-batches")(BatchRequest(document_ids=["doc-paper"], answer_document_id="doc-answer"), ctx, db)
    assert result["answer_document_id"] == "doc-answer"
    with db.session() as conn:
        assert conn.execute("SELECT answer_document_id FROM import_batches WHERE id=?", (result["batch_id"],)).fetchone()[0] == "doc-answer"


def test_page_revision_is_atomic_and_invalidates_old_import_state(env):
    settings, db, app = env
    image = Image.new("RGB", (3, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    document = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "page-edit.png", "image/png"), "paper", None, ctx, db, settings))
    with db.session() as conn:
        page = conn.execute("SELECT id,page_index,asset_id,transform_json FROM source_pages WHERE document_id=?", (document["document_id"],)).fetchone()
        original = conn.execute("SELECT object_key FROM assets WHERE id=?", (document["asset_id"],)).fetchone()[0]
    batch = _route(app, "/api/v1/import-batches")(BatchRequest(document_ids=[document["document_id"]]), ctx, db)
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("UPDATE import_batches SET status='awaiting_review' WHERE id=?", (batch["batch_id"],))
        conn.execute(
            "INSERT INTO import_items(id,batch_id,learner_id,occurrence_id,locator,page_index,source_page_id,content_json,teacher_evidence_json,verdict,verification_status,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("page-edit-item", batch["batch_id"], "learner-a", "page-edit-occurrence", "page:1:item:1", 0, page["id"], '{"objective_id":"obj-1"}', '{"teacher":true}', "incorrect", "manual", "ready"),
        )
        conn.execute(
            "INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            ("page-edit-job", "learner-a", "document_analysis", json.dumps({"batch_id": batch["batch_id"]}), "page-edit-job-key", "queued", now, now),
        )
        conn.execute(
            "INSERT INTO import_judgments(id,item_id,revision,verdict,evidence_json,basis_version,verification_status,created_at) VALUES (?,?,?,?,?,?,?,?)",
            ("page-edit-judge", "page-edit-item", 1, "incorrect", '{"teacher":true}', "manual-v1", "manual", now),
        )
    challenge = _route(app, "/api/v1/import-batches/{batch_id}/confirmation-challenges")(
        batch["batch_id"], ChallengeRequest(items=[{"item_id": "page-edit-item", "expected_revision": 1}]), ctx, db, settings
    )
    edited = _route(app, "/api/v1/documents/{document_id}/pages")(
        document["document_id"],
        PagePatch(expected_revision=1, pages=[{"page_id": page["id"], "page_index": 0, "asset_id": page["asset_id"], "rotation": 90}]),
        ctx,
        db,
    )
    assert edited["revision"] == 2
    assert edited["invalidated_batches"] == [batch["batch_id"]]
    with db.session() as conn:
        document_row = conn.execute("SELECT revision FROM source_documents WHERE id=?", (document["document_id"],)).fetchone()
        page_row = conn.execute("SELECT page_index,transform_json FROM source_pages WHERE id=?", (page["id"],)).fetchone()
        batch_row = conn.execute("SELECT status,revision FROM import_batches WHERE id=?", (batch["batch_id"],)).fetchone()
        item_row = conn.execute("SELECT status,verification_status,revision,confirmed_at FROM import_items WHERE id='page-edit-item'").fetchone()
        job_row = conn.execute("SELECT status,error_code FROM jobs WHERE id='page-edit-job'").fetchone()
        assert conn.execute("SELECT object_key FROM assets WHERE id=?", (document["asset_id"],)).fetchone()[0] == original
    assert document_row[0] == 2
    assert page_row[0] == 0 and json.loads(page_row[1])["rotation"] == 90
    assert tuple(batch_row) == ("stale", 2)
    assert tuple(item_row) == ("stale", "needs_review", 2, None)
    assert tuple(job_row) == ("cancelled", "STALE_DOCUMENT_REVISION")
    with pytest.raises(APIError, match="资料页面已修订"):
        _route(app, "/api/v1/import-batches/{batch_id}/confirmations")(
            batch["batch_id"],
            ConfirmationRequest(challenge_id=challenge["challenge_id"], nonce=challenge["nonce"], items=[{"item_id": "page-edit-item", "expected_revision": 1}]),
            _request({"Idempotency-Key": "page-edit-confirm"}),
            ctx,
            db,
        )
    with pytest.raises(APIError) as conflict:
        _route(app, "/api/v1/documents/{document_id}/pages")(
            document["document_id"],
            PagePatch(expected_revision=1, pages=[{"page_id": page["id"], "page_index": 0, "rotation": 0}]),
            ctx,
            db,
        )
    assert conflict.value.code == "REVISION_CONFLICT"


def test_page_revision_rejects_foreign_or_unrelated_assets(env):
    settings, db, app = env
    image = Image.new("RGB", (2, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    first = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "first.png", "image/png"), "paper", None, ctx, db, settings))
    second = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "second.png", "image/png"), "paper", None, ctx, db, settings))
    with db.session() as conn:
        page_id = conn.execute("SELECT id FROM source_pages WHERE document_id=?", (first["document_id"],)).fetchone()[0]
    with pytest.raises(APIError) as unrelated:
        _route(app, "/api/v1/documents/{document_id}/pages")(
            first["document_id"],
            PagePatch(expected_revision=1, pages=[{"page_id": page_id, "page_index": 0, "asset_id": second["asset_id"]}]),
            ctx,
            db,
        )
    assert unrelated.value.code == "PAGE_ASSET_NOT_FOUND"
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)", ("foreign-page-asset", "learner-b", "private", "learner-b/foreign.png", "foreign", "image/png", 1, "source_page", utc_now()))
    with pytest.raises(APIError) as foreign:
        _route(app, "/api/v1/documents/{document_id}/pages")(
            first["document_id"],
            PagePatch(expected_revision=1, pages=[{"page_id": page_id, "page_index": 0, "asset_id": "foreign-page-asset"}]),
            ctx,
            db,
        )
    assert foreign.value.code == "PAGE_ASSET_NOT_FOUND"


def test_attempt_review_requests_are_idempotent_scoped_and_grade_neutral(env):
    settings, db, app = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO accounts(id,created_at) VALUES (?,?)", ("acct-review", now))
        conn.execute("INSERT INTO learner_access(account_id,learner_id,role,created_at) VALUES (?,?,?,?)", ("acct-review", "learner-a", "reviewer", now))
        conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?)", ("q-review", "shared", "approved", "obj-1", now))
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,?,?,?,?,?,?)", ("qv-review", "q-review", 1, '{"prompt":"1+1"}', '{"accepted":["2"]}', "exact-text-v1", "approved", now))
        conn.execute("INSERT INTO test_sessions(id,learner_id,mode,status,created_at) VALUES (?,?,?,?,?)", ("session-review", "learner-a", "independent", "completed", now))
        conn.execute("INSERT INTO test_items(id,session_id,learner_id,question_version_id,status,assistance,presented_at) VALUES (?,?,?,?,?,?,?)", ("item-review", "session-review", "learner-a", "qv-review", "graded", "none", now))
        conn.execute("INSERT INTO attempts(id,test_item_id,learner_id,raw_answer,normalized_answer,submitted_at,assistance,assessment_eligibility,status,idempotency_key) VALUES (?,?,?,?,?,?,?,?,?,?)", ("attempt-review", "item-review", "learner-a", "2", "2", now, "none", 1, "graded", "answer-review"))
        conn.execute("INSERT INTO grade_versions(id,attempt_id,outcome,score,feedback,rubric_version,validator_version,created_at) VALUES (?,?,?,?,?,?,?,?)", ("grade-review", "attempt-review", "correct", 1.0, "正确", "exact-text-v1", "exact-text-v1", now))
    learner = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    request_endpoint = _route(app, "/api/v1/attempts/{attempt_id}/review-requests")
    body = ReviewRequestRequest(reason="批改依据需要复核", details={"page": 1})
    first = request_endpoint("attempt-review", body, _request({"Idempotency-Key": "review-key"}), learner, db)
    assert first["status"] == "requested" and first["grade_unchanged"] is True
    assert request_endpoint("attempt-review", body, _request({"Idempotency-Key": "review-key"}), learner, db) == first
    with pytest.raises(APIError, match="相同幂等键携带了不同内容"):
        request_endpoint("attempt-review", ReviewRequestRequest(reason="不同理由"), _request({"Idempotency-Key": "review-key"}), learner, db)
    with pytest.raises(APIError) as duplicate:
        request_endpoint("attempt-review", body, _request({"Idempotency-Key": "review-key-2"}), learner, db)
    assert duplicate.value.code == "REVIEW_REQUEST_EXISTS"
    with pytest.raises(APIError) as isolated:
        request_endpoint("attempt-review", body, _request({"Idempotency-Key": "other-learner"}), Context(account_id="acct-b", learner_id="learner-b"), db)
    assert isolated.value.code == "ATTEMPT_NOT_FOUND"
    attempt = _route(app, "/api/v1/attempts/{attempt_id}")("attempt-review", learner, db)
    assert attempt["review_requests"][0]["status"] == "requested"
    decision_endpoint = _route(app, "/api/v1/admin/reviews/{review_request_id}/decisions")
    reviewer = Context(account_id="acct-review", learner_id="learner-a", role="reviewer")
    in_review = decision_endpoint(first["review_request_id"], ReviewDecisionRequest(decision="in_review", note="已接单"), reviewer, db)
    assert in_review["status"] == "in_review" and in_review["grade_unchanged"] is True
    with pytest.raises(APIError, match="需要复核权限"):
        decision_endpoint(first["review_request_id"], ReviewDecisionRequest(decision="resolve"), Context(account_id="acct-b", learner_id="learner-a", role="student"), db)
    resolved = decision_endpoint(first["review_request_id"], ReviewDecisionRequest(decision="resolve", note="依据不足，保留原分"), reviewer, db)
    assert resolved["status"] == "resolved" and resolved["grade_unchanged"] is True
    with db.session() as conn:
        assert tuple(conn.execute("SELECT score,outcome FROM grade_versions WHERE attempt_id='attempt-review'").fetchone()) == (1.0, "correct")
    with pytest.raises(APIError) as closed:
        decision_endpoint(first["review_request_id"], ReviewDecisionRequest(decision="dismiss"), reviewer, db)
    assert closed.value.code == "REVIEW_REQUEST_CLOSED"


def test_review_request_backup_delete_and_restore_lifecycle(env, tmp_path: Path):
    settings, db, app = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?)", ("q-review-lifecycle", "shared", "approved", "obj-1", now))
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,?,?,?,?,?,?)", ("qv-review-lifecycle", "q-review-lifecycle", 1, '{\"prompt\":\"1+1\"}', '{\"accepted\":[\"2\"]}', "exact-text-v1", "approved", now))
        conn.execute("INSERT INTO test_sessions(id,learner_id,mode,status,created_at) VALUES (?,?,?,?,?)", ("session-review-lifecycle", "learner-a", "independent", "completed", now))
        conn.execute("INSERT INTO test_items(id,session_id,learner_id,question_version_id,status,assistance,presented_at) VALUES (?,?,?,?,?,?,?)", ("item-review-lifecycle", "session-review-lifecycle", "learner-a", "qv-review-lifecycle", "graded", "none", now))
        conn.execute("INSERT INTO attempts(id,test_item_id,learner_id,raw_answer,normalized_answer,submitted_at,assistance,assessment_eligibility,status,idempotency_key) VALUES (?,?,?,?,?,?,?,?,?,?)", ("attempt-review-lifecycle", "item-review-lifecycle", "learner-a", "2", "2", now, "none", 1, "graded", "answer-review-lifecycle"))
        conn.execute("INSERT INTO grade_versions(id,attempt_id,outcome,score,feedback,rubric_version,validator_version,created_at) VALUES (?,?,?,?,?,?,?,?)", ("grade-review-lifecycle", "attempt-review-lifecycle", "correct", 1.0, "正确", "exact-text-v1", "exact-text-v1", now))

    learner = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    review = _route(app, "/api/v1/attempts/{attempt_id}/review-requests")(
        "attempt-review-lifecycle",
        ReviewRequestRequest(reason="恢复链路复核", details={"source": "lifecycle-test"}),
        _request({"Idempotency-Key": "review-lifecycle"}),
        learner,
        db,
    )
    backup_dir = tmp_path / "review-backup"
    backup_data(settings.data_dir, backup_dir)
    restored_dir = tmp_path / "review-restored"
    restore_data(backup_dir, restored_dir)
    restored = Database(restored_dir / "learning.db")
    with restored.session() as conn:
        row = conn.execute("SELECT status,reason FROM review_requests WHERE id=?", (review["review_request_id"],)).fetchone()
        assert tuple(row) == ("requested", "恢复链路复核")

    deleted = _route(app, "/api/v1/admin/deletions")({"learner_id": "learner-a"}, learner, db, settings)
    assert deleted["status"] == "completed"
    with db.session() as conn:
        assert conn.execute("SELECT status FROM review_requests WHERE id=?", (review["review_request_id"],)).fetchone()[0] == "cancelled"
        assert conn.execute("SELECT cleanup_state FROM deletion_records WHERE resource_type='review_request' AND resource_id=?", (review["review_request_id"],)).fetchone()[0] == "completed"

    deleted_backup = tmp_path / "review-deleted-backup"
    backup_data(settings.data_dir, deleted_backup)
    deleted_restore = tmp_path / "review-deleted-restore"
    restore_data(deleted_backup, deleted_restore)
    replayed = Database(deleted_restore / "learning.db")
    with replayed.session() as conn:
        assert conn.execute("SELECT status FROM review_requests WHERE id=?", (review["review_request_id"],)).fetchone()[0] == "cancelled"


def test_confirmation_challenge_consumption_and_replay(env):
    settings, db, app = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)", ("asset-1", "learner-a", "private", "learner-a/a.png", "hash", "image/png", 1, "source_document", now))
        conn.execute("INSERT INTO source_documents(id,learner_id,asset_id,kind,status,page_count,created_at) VALUES (?,?,?,?,?,?,?)", ("doc-1", "learner-a", "asset-1", "paper", "stored", 1, now))
        conn.execute("INSERT INTO source_pages(id,document_id,page_index,status,object_key,transform_json) VALUES (?,?,?,?,?,?)", ("page-1", "doc-1", 0, "processed", "learner-a/a.png", "{}"))
        conn.execute("INSERT INTO import_batches(id,learner_id,document_ids_json,status,total_pages,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", ("batch-1", "learner-a", '["doc-1"]', "awaiting_review", 1, now, now))
        conn.execute("INSERT INTO import_items(id,batch_id,learner_id,occurrence_id,locator,page_index,source_page_id,content_json,teacher_evidence_json,verdict,verification_status,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("item-1", "batch-1", "learner-a", "occ-1", "page:1:item:1", 0, "page-1", '{"objective_id":"obj-1"}', '{"teacher":true}', "incorrect", "manual", "ready"))
        conn.execute("INSERT INTO import_judgments(id,item_id,revision,verdict,evidence_json,basis_version,verification_status,created_at) VALUES (?,?,?,?,?,?,?,?)", ("judge-1", "item-1", 1, "incorrect", '{"teacher":true}', "manual-v1", "manual", now))
    ctx = __import__("learning_service.app", fromlist=["Context"]).Context(account_id="acct-a", learner_id="learner-a", role="admin")
    challenge_endpoint = _route(app, "/api/v1/import-batches/{batch_id}/confirmation-challenges")
    with pytest.raises(APIError) as stale_revision:
        challenge_endpoint(
            "batch-1",
            ChallengeRequest(items=[{"item_id": "item-1", "expected_revision": 1}], expected_batch_revision=2),
            ctx,
            db,
            settings,
        )
    assert stale_revision.value.code == "REVISION_CONFLICT"
    challenge = challenge_endpoint("batch-1", ChallengeRequest(items=[{"item_id": "item-1", "expected_revision": 1}]), ctx, db, settings)
    assert challenge["nonce"]
    confirm_endpoint = _route(app, "/api/v1/import-batches/{batch_id}/confirmations")
    body = ConfirmationRequest(challenge_id=challenge["challenge_id"], nonce=challenge["nonce"], items=[{"item_id": "item-1", "expected_revision": 1}])
    result = confirm_endpoint("batch-1", body, _request({"Idempotency-Key": "confirm-1"}), ctx, db)
    assert result["confirmed_count"] == 1
    assert "nonce" not in result and "raw_answer" not in result and "answers" not in result
    assert confirm_endpoint("batch-1", body, _request({"Idempotency-Key": "confirm-1"}), ctx, db) == {**result}
    with pytest.raises(APIError, match="相同幂等键携带了不同内容"):
        confirm_endpoint(
            "batch-1",
            body.model_copy(update={"items": [{"item_id": "item-1", "expected_revision": 2}]}),
            _request({"Idempotency-Key": "confirm-1"}),
            ctx,
            db,
        )
    with pytest.raises(APIError, match="交互挑战已经消费"):
        confirm_endpoint("batch-1", body.model_copy(update={"challenge_id": challenge["challenge_id"]}), _request({"Idempotency-Key": "confirm-2"}), ctx, db)
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM mistake_sources WHERE learner_id='learner-a'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM mistake_sources WHERE learner_id='learner-b'").fetchone()[0] == 0
    with pytest.raises(APIError, match="已完成批次不能再次确认"):
        challenge_endpoint("batch-1", ChallengeRequest(items=[{"item_id": "item-1", "expected_revision": 1}]), ctx, db, settings)
    with pytest.raises(APIError, match="已确认候选题不能直接修改"):
        _route(app, "/api/v1/import-items/{item_id}")(
            "item-1",
            ItemPatch(expected_revision=1, verdict="incorrect", evidence={"teacher": True}),
            ctx,
            db,
        )


def test_import_confirmation_requires_unique_current_manual_judgments(env):
    settings, db, app = env
    now = utc_now()
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO import_batches(id,learner_id,document_ids_json,status,total_pages,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", ("batch-review", "learner-a", "[]", "awaiting_review", 1, now, now))
        rows = [
            ("item-auto", "needs_review", "incorrect", '{"mark":"auto"}', False),
            ("item-correct", "manual", "correct", '{"mark":"correct"}', True),
        ("item-empty-evidence", "manual", "undetermined", "{}", True),
            ("item-empty", "manual", "incorrect", "{}", True),
            ("item-mismatch", "manual", "incorrect", '{"mark":"item"}', True),
        ]
        for item_id, verification, verdict, evidence, with_judgment in rows:
            conn.execute(
                "INSERT INTO import_items(id,batch_id,learner_id,occurrence_id,locator,page_index,content_json,teacher_evidence_json,verdict,verification_status,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (item_id, "batch-review", "learner-a", item_id, "page:1:item:1", 0, '{"objective_id":"obj-1"}', evidence, verdict, verification, "ready"),
            )
            if with_judgment:
                judgment_evidence = '{"mark":"different"}' if item_id == "item-mismatch" else evidence
                conn.execute(
                    "INSERT INTO import_judgments(id,item_id,revision,verdict,evidence_json,basis_version,verification_status,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (f"judge-{item_id}", item_id, 1, verdict, judgment_evidence, "manual-v1", "manual", now),
                )

    challenge = _route(app, "/api/v1/import-batches/{batch_id}/confirmation-challenges")
    endpoint = lambda item_id, revision=1: challenge("batch-review", ChallengeRequest(items=[{"item_id": item_id, "expected_revision": revision}]), ctx, db, settings)
    for item_id, expected_code in [
        ("item-auto", "MANUAL_REVIEW_REQUIRED"),
        ("item-empty-evidence", "EVIDENCE_REQUIRED"),
        ("item-empty", "EVIDENCE_REQUIRED"),
        ("item-mismatch", "MANUAL_JUDGMENT_REQUIRED"),
    ]:
        with pytest.raises(APIError) as error:
            endpoint(item_id)
        assert error.value.code == expected_code

    with pytest.raises(APIError) as duplicate:
        challenge(
            "batch-review",
            ChallengeRequest(items=[{"item_id": "item-auto", "expected_revision": 1}, {"item_id": "item-auto", "expected_revision": 1}]),
            ctx,
            db,
            settings,
        )
    assert duplicate.value.code == "DUPLICATE_ITEM"
    with pytest.raises(APIError) as invalid_revision:
        challenge("batch-review", ChallengeRequest(items=[{"item_id": "item-auto", "expected_revision": 0}]), ctx, db, settings)
    assert invalid_revision.value.code == "INVALID_ITEM_REVISION"


def test_import_confirmation_accepts_all_five_manual_verdicts_but_only_records_mistakes(env):
    settings, db, app = env
    now = utc_now()
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    verdicts = ["correct", "incorrect", "partial", "unanswered", "undetermined"]
    with db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO import_batches(id,learner_id,document_ids_json,status,total_pages,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            ("batch-five-verdicts", "learner-a", "[]", "awaiting_review", 1, now, now),
        )
        for index, verdict in enumerate(verdicts):
            item_id = f"item-{verdict}"
            evidence = json.dumps({"teacher_mark": verdict})
            conn.execute(
                "INSERT INTO import_items(id,batch_id,learner_id,occurrence_id,locator,page_index,content_json,teacher_evidence_json,verdict,verification_status,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (item_id, "batch-five-verdicts", "learner-a", f"occ-{verdict}", f"page:1:item:{index + 1}", 0, '{"objective_id":"obj-1"}', evidence, verdict, "manual", "ready"),
            )
            conn.execute(
                "INSERT INTO import_judgments(id,item_id,revision,verdict,evidence_json,basis_version,verification_status,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (f"judge-{verdict}", item_id, 1, verdict, evidence, "manual-v1", "manual", now),
            )

    challenge_endpoint = _route(app, "/api/v1/import-batches/{batch_id}/confirmation-challenges")
    confirm_endpoint = _route(app, "/api/v1/import-batches/{batch_id}/confirmations")
    for index, verdict in enumerate(verdicts):
        selection = [{"item_id": f"item-{verdict}", "expected_revision": 1}]
        challenge = challenge_endpoint("batch-five-verdicts", ChallengeRequest(items=selection), ctx, db, settings)
        result = confirm_endpoint(
            "batch-five-verdicts",
            ConfirmationRequest(challenge_id=challenge["challenge_id"], nonce=challenge["nonce"], items=selection),
            _request({"Idempotency-Key": f"confirm-{verdict}"}),
            ctx,
            db,
        )
        assert result["confirmed_count"] == 1
        assert result["status"] == ("completed" if index == len(verdicts) - 1 else "partial")

    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM import_items WHERE batch_id='batch-five-verdicts' AND status='confirmed'").fetchone()[0] == 5
        assert conn.execute("SELECT COUNT(*) FROM mistake_sources WHERE learner_id='learner-a'").fetchone()[0] == 2
        mistake_verdicts = {
            row[0]
            for row in conn.execute(
                "SELECT i.verdict FROM mistake_sources s JOIN import_items i ON i.id=s.item_id WHERE s.learner_id='learner-a'"
            ).fetchall()
        }
    assert mistake_verdicts == {"incorrect", "partial"}


def test_invalidated_manual_candidate_does_not_consume_import_challenge(env):
    settings, db, app = env
    now = utc_now()
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO import_batches(id,learner_id,document_ids_json,status,total_pages,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", ("batch-race", "learner-a", "[]", "awaiting_review", 1, now, now))
        conn.execute(
            "INSERT INTO import_items(id,batch_id,learner_id,occurrence_id,locator,page_index,content_json,teacher_evidence_json,verdict,verification_status,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("item-race", "batch-race", "learner-a", "occ-race", "page:1:item:1", 0, '{"objective_id":"obj-1"}', '{"teacher":true}', "incorrect", "manual", "ready"),
        )
        conn.execute("INSERT INTO import_judgments(id,item_id,revision,verdict,evidence_json,basis_version,verification_status,created_at) VALUES (?,?,?,?,?,?,?,?)", ("judge-race", "item-race", 1, "incorrect", '{"teacher":true}', "manual-v1", "manual", now))

    selection = [{"item_id": "item-race", "expected_revision": 1}]
    challenge = _route(app, "/api/v1/import-batches/{batch_id}/confirmation-challenges")("batch-race", ChallengeRequest(items=selection), ctx, db, settings)
    with db.session(write=True) as conn:
        conn.execute("UPDATE import_judgments SET verification_status='needs_review' WHERE id='judge-race'")
    body = ConfirmationRequest(challenge_id=challenge["challenge_id"], nonce=challenge["nonce"], items=selection)
    with pytest.raises(APIError) as error:
        _route(app, "/api/v1/import-batches/{batch_id}/confirmations")(
            "batch-race", body, _request({"Idempotency-Key": "race-key"}), ctx, db
        )
    assert error.value.code == "MANUAL_JUDGMENT_REQUIRED"
    with db.session() as conn:
        assert conn.execute("SELECT consumed_at FROM interaction_challenges WHERE id=?", (challenge["challenge_id"],)).fetchone()[0] is None


def test_worker_analysis_and_idempotent_source(env):
    settings, db, _ = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)", ("asset-2", "learner-a", "private", "learner-a/a.png", "hash", "image/png", 1, "source_document", now))
        conn.execute("INSERT INTO source_documents(id,learner_id,asset_id,kind,status,page_count,created_at) VALUES (?,?,?,?,?,?,?)", ("doc-2", "learner-a", "asset-2", "paper", "stored", 1, now))
        conn.execute("INSERT INTO source_pages(id,document_id,page_index,status,object_key,transform_json) VALUES (?,?,?,?,?,?)", ("page-2", "doc-2", 0, "queued", "learner-a/a.png", "{}"))
        conn.execute("INSERT INTO import_batches(id,learner_id,document_ids_json,status,total_pages,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", ("batch-2", "learner-a", '["doc-2"]', "processing", 1, now, now))
        conn.execute("INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", ("job-2", "learner-a", "document_analysis", '{"batch_id":"batch-2","revision":1}', "analysis-2", "queued", now, now))
    assert run_worker_once(db, settings)["status"] == "succeeded"
    assert run_worker_once(db, settings)["status"] == "idle"
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM import_items WHERE batch_id='batch-2'").fetchone()[0] == 1
        assert conn.execute("SELECT status FROM source_pages WHERE id='page-2'").fetchone()[0] == "processed"
        content = json.loads(conn.execute("SELECT content_json FROM import_items WHERE batch_id='batch-2'").fetchone()[0])
    assert content["provider_id"] == "mock-document-v1"
    assert content["provider_status"] == "needs_review"
    assert content["provider_evidence"]["ocr_performed"] is False


def test_expired_claim_is_recovered_after_worker_process_interruption(env):
    settings, db, _ = env
    now = utc_now()
    expired = (datetime.now(timezone.utc) - timedelta(seconds=5)).replace(microsecond=0).isoformat()
    with db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("asset-crash-recovery", "learner-a", "private", "learner-a/crash.png", "crash-hash", "image/png", 1, "source_document", now),
        )
        conn.execute(
            "INSERT INTO source_documents(id,learner_id,asset_id,kind,status,page_count,created_at) VALUES (?,?,?,?,?,?,?)",
            ("doc-crash-recovery", "learner-a", "asset-crash-recovery", "paper", "stored", 1, now),
        )
        conn.execute(
            "INSERT INTO source_pages(id,document_id,page_index,status,object_key,transform_json) VALUES (?,?,?,?,?,?)",
            ("page-crash-recovery", "doc-crash-recovery", 0, "queued", "learner-a/crash.png", "{}"),
        )
        conn.execute(
            "INSERT INTO import_batches(id,learner_id,document_ids_json,status,total_pages,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            ("batch-crash-recovery", "learner-a", '["doc-crash-recovery"]', "processing", 1, now, now),
        )
        # This is the durable state left by a process that died immediately
        # after claiming the job and before applying any business writes.
        conn.execute(
            "INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,lease_token,lease_until,attempts,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("job-crash-recovery", "learner-a", "document_analysis", '{"batch_id":"batch-crash-recovery","revision":1}', "crash-recovery-key", "running", "dead-process-token", expired, 1, now, now),
        )

    result = run_worker_once(db, settings)
    assert result["status"] == "succeeded"
    with db.session() as conn:
        job = conn.execute("SELECT status,attempts,lease_token FROM jobs WHERE id='job-crash-recovery'").fetchone()
        assert tuple(job) == ("succeeded", 2, None)
        assert conn.execute("SELECT COUNT(*) FROM import_items WHERE batch_id='batch-crash-recovery'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM source_regions WHERE source_page_id='page-crash-recovery'").fetchone()[0] == 1
        assert conn.execute("SELECT status FROM source_pages WHERE id='page-crash-recovery'").fetchone()[0] == "processed"


def test_worker_process_kill_rolls_back_business_transaction_and_recovers(env, tmp_path: Path):
    """Kill a real worker process while its provider call is in flight."""
    settings, db, _ = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("asset-process-kill", "learner-a", "private", "learner-a/process-kill.png", "process-kill-hash", "image/png", 1, "source_document", now),
        )
        conn.execute(
            "INSERT INTO source_documents(id,learner_id,asset_id,kind,status,page_count,created_at) VALUES (?,?,?,?,?,?,?)",
            ("doc-process-kill", "learner-a", "asset-process-kill", "paper", "stored", 1, now),
        )
        conn.execute(
            "INSERT INTO source_pages(id,document_id,page_index,status,object_key,transform_json) VALUES (?,?,?,?,?,?)",
            ("page-process-kill", "doc-process-kill", 0, "queued", "learner-a/process-kill.png", "{}"),
        )
        conn.execute(
            "INSERT INTO import_batches(id,learner_id,document_ids_json,status,total_pages,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            ("batch-process-kill", "learner-a", '["doc-process-kill"]', "processing", 1, now, now),
        )
        conn.execute(
            "INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            ("job-process-kill", "learner-a", "document_analysis", '{"batch_id":"batch-process-kill","revision":1}', "process-kill-key", "queued", now, now),
        )

    marker = tmp_path / "provider-entered"
    root = Path(__file__).parents[1]
    child_code = f"""
import time
from pathlib import Path
from learning_service import app as runtime
from learning_service.app import Settings, run_worker_once
from learning_service.db import Database
marker = Path({str(marker)!r})
class BlockingProvider:
    provider_id = "process-kill-provider"
    def analyze_page(self, page):
        marker.write_text("entered", encoding="utf-8")
        time.sleep(30)
runtime.document_provider = lambda _provider_id: BlockingProvider()
settings = Settings(Path({str(settings.data_dir)!r}), Path({str(settings.db_path)!r}), Path({str(settings.attachment_dir)!r}), "admin", "adapter", True)
run_worker_once(Database(settings.db_path), settings)
"""
    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(root), child_env.get("PYTHONPATH", "")]))
    child = subprocess.Popen([sys.executable, "-c", child_code], cwd=root, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 8
        while not marker.exists() and time.monotonic() < deadline:
            if child.poll() is not None:
                break
            time.sleep(0.05)
        assert marker.exists(), child.communicate(timeout=2)[1]
        with db.session() as conn:
            claim = conn.execute("SELECT status,attempts FROM jobs WHERE id='job-process-kill'").fetchone()
            assert tuple(claim) == ("running", 1)
        child.kill()
        child.wait(timeout=5)
        assert child.returncode == -9
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)

    expired = (datetime.now(timezone.utc) - timedelta(seconds=5)).replace(microsecond=0).isoformat()
    with db.session(write=True) as conn:
        conn.execute("UPDATE jobs SET lease_until=? WHERE id='job-process-kill'", (expired,))
    assert run_worker_once(db, settings)["status"] == "succeeded"
    with db.session() as conn:
        job = conn.execute("SELECT status,attempts,lease_token FROM jobs WHERE id='job-process-kill'").fetchone()
        assert tuple(job) == ("succeeded", 2, None)
        assert conn.execute("SELECT status FROM source_pages WHERE id='page-process-kill'").fetchone()[0] == "processed"
        assert conn.execute("SELECT COUNT(*) FROM import_items WHERE batch_id='batch-process-kill'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM source_regions WHERE source_page_id='page-process-kill'").fetchone()[0] == 1


def test_sqlite_writer_process_kill_recovers_wal_and_discards_uncommitted_write(env, tmp_path: Path):
    """An OS-killed SQLite writer must leave the database usable and atomic."""
    settings, db, _ = env
    with db.session(write=True) as conn:
        conn.execute("CREATE TABLE crash_probe(id TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO crash_probe(id,value) VALUES ('committed','before-crash')")

    marker = tmp_path / "sqlite-write-open"
    root = Path(__file__).parents[1]
    child_code = f"""
import sqlite3
import time
from pathlib import Path
conn = sqlite3.connect({str(settings.db_path)!r}, timeout=5, isolation_level=None)
conn.execute("PRAGMA busy_timeout=5000")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("BEGIN IMMEDIATE")
conn.execute("INSERT INTO crash_probe(id,value) VALUES ('uncommitted','must-rollback')")
Path({str(marker)!r}).write_text("transaction-open", encoding="utf-8")
time.sleep(60)
"""
    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(root), child_env.get("PYTHONPATH", "")]))
    child = subprocess.Popen([sys.executable, "-c", child_code], cwd=root, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 8
        while not marker.exists() and time.monotonic() < deadline:
            if child.poll() is not None:
                break
            time.sleep(0.05)
        assert marker.exists(), child.communicate(timeout=2)[1]
        child.kill()
        child.wait(timeout=5)
        assert child.returncode == -9
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)

    # Reopening through the production connection setup exercises WAL recovery,
    # then a new committed write proves that the stale writer lock was released.
    with db.session(write=True) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT value FROM crash_probe WHERE id='committed'").fetchone()[0] == "before-crash"
        assert conn.execute("SELECT COUNT(*) FROM crash_probe WHERE id='uncommitted'").fetchone()[0] == 0
        conn.execute("INSERT INTO crash_probe(id,value) VALUES ('after-recovery','writable')")
    with db.session() as conn:
        assert conn.execute("SELECT value FROM crash_probe WHERE id='after-recovery'").fetchone()[0] == "writable"


def test_worker_provider_call_does_not_hold_sqlite_writer_lock(env, monkeypatch):
    """A provider may use a separate SQLite connection while analyzing a page."""
    settings, db, _ = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("asset-provider-lock", "learner-a", "private", "learner-a/provider-lock.png", "provider-lock-hash", "image/png", 1, "source_document", now),
        )
        conn.execute(
            "INSERT INTO source_documents(id,learner_id,asset_id,kind,status,page_count,created_at) VALUES (?,?,?,?,?,?,?)",
            ("doc-provider-lock", "learner-a", "asset-provider-lock", "paper", "stored", 1, now),
        )
        conn.execute(
            "INSERT INTO source_pages(id,document_id,page_index,status,object_key,transform_json) VALUES (?,?,?,?,?,?)",
            ("page-provider-lock", "doc-provider-lock", 0, "queued", "learner-a/provider-lock.png", "{}"),
        )
        conn.execute(
            "INSERT INTO import_batches(id,learner_id,document_ids_json,status,total_pages,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            ("batch-provider-lock", "learner-a", '["doc-provider-lock"]', "processing", 1, now, now),
        )
        conn.execute(
            "INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            ("job-provider-lock", "learner-a", "document_analysis", '{"batch_id":"batch-provider-lock","revision":1}', "provider-lock-key", "queued", now, now),
        )

    class SeparateConnectionProvider:
        provider_id = "separate-connection-provider"

        def analyze_page(self, page):
            # This write is deliberately made from a second connection. It
            # would fail with SQLITE_BUSY if the worker held BEGIN IMMEDIATE
            # across the provider call.
            with sqlite3.connect(settings.db_path, timeout=0.2, isolation_level=None) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "INSERT INTO audit_events(id,account_id,learner_id,operation,resource_type,resource_id,result,metadata_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    ("provider-lock-audit", "acct-a", "learner-a", "provider_probe", "source_page", page["id"], "accepted", "{}", utc_now()),
                )
                conn.commit()
            return ProviderResult(
                provider_id=self.provider_id,
                status="needs_review",
                payload={"page_id": page["id"]},
                evidence={"mode": "separate_connection_probe"},
            )

    monkeypatch.setattr("learning_service.app.document_provider", lambda _: SeparateConnectionProvider())
    result = run_worker_once(db, settings)
    assert result["status"] == "succeeded"
    with db.session() as conn:
        assert conn.execute("SELECT result FROM audit_events WHERE id='provider-lock-audit'").fetchone()[0] == "accepted"
        assert conn.execute("SELECT status FROM source_pages WHERE id='page-provider-lock'").fetchone()[0] == "processed"
        assert conn.execute("SELECT COUNT(*) FROM import_items WHERE batch_id='batch-provider-lock'").fetchone()[0] == 1


def test_worker_provider_failure_rolls_back_page_and_candidate_writes(env, monkeypatch):
    settings, db, _ = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)", ("asset-provider-failure", "learner-a", "private", "learner-a/provider-failure.png", "hash", "image/png", 1, "source_document", now))
        conn.execute("INSERT INTO source_documents(id,learner_id,asset_id,kind,status,page_count,created_at) VALUES (?,?,?,?,?,?,?)", ("doc-provider-failure", "learner-a", "asset-provider-failure", "paper", "stored", 1, now))
        conn.execute("INSERT INTO source_pages(id,document_id,page_index,status,object_key,transform_json) VALUES (?,?,?,?,?,?)", ("page-provider-failure", "doc-provider-failure", 0, "queued", "learner-a/provider-failure.png", "{}"))
        conn.execute("INSERT INTO import_batches(id,learner_id,document_ids_json,status,total_pages,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", ("batch-provider-failure", "learner-a", '["doc-provider-failure"]', "processing", 1, now, now))
        conn.execute("INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", ("job-provider-failure", "learner-a", "document_analysis", '{"batch_id":"batch-provider-failure","revision":1}', "analysis-provider-failure", "queued", now, now))

    class ExplodingProvider:
        provider_id = "test-provider-failure"

        def analyze_page(self, page):
            raise RuntimeError("injected provider failure")

    monkeypatch.setattr("learning_service.app.document_provider", lambda _: ExplodingProvider())
    result = run_worker_once(db, settings)
    assert result == {"status": "failed", "job_id": "job-provider-failure", "error": "WORKER_ERROR"}
    with db.session() as conn:
        page = conn.execute("SELECT status FROM source_pages WHERE id='page-provider-failure'").fetchone()
        batch = conn.execute("SELECT status,processed_pages,failed_pages FROM import_batches WHERE id='batch-provider-failure'").fetchone()
        job = conn.execute("SELECT status,error_code,lease_token,result_json FROM jobs WHERE id='job-provider-failure'").fetchone()
        assert page["status"] == "queued"
        assert tuple(batch) == ("processing", 0, 0)
        assert tuple(job[:3]) == ("failed", "WORKER_ERROR", None)
        assert json.loads(job["result_json"])["message"] == "RuntimeError"
        assert conn.execute("SELECT COUNT(*) FROM import_items WHERE batch_id='batch-provider-failure'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM source_regions WHERE source_page_id='page-provider-failure'").fetchone()[0] == 0


def test_upload_database_failure_removes_written_attachment(env, monkeypatch):
    settings, db, app = env
    pdf = fitz.open()
    pdf.new_page(width=120, height=80)
    pdf.new_page(width=160, height=90)
    payload = pdf.tobytes()
    pdf.close()
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    original_session = db.session

    @contextmanager
    def fail_write_commit(write=False):
        with original_session(write=write) as conn:
            yield conn
            if write:
                raise sqlite3.OperationalError("injected database commit failure")

    monkeypatch.setattr(db, "session", fail_write_commit)
    with pytest.raises(sqlite3.OperationalError, match="injected database commit failure"):
        asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(payload, "db-failure.pdf", "application/pdf"), "paper", None, ctx, db, settings))
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM source_documents WHERE learner_id='learner-a'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM assets WHERE learner_id='learner-a'").fetchone()[0] == 0
    assert not [path for path in settings.attachment_dir.rglob("*") if path.is_file()]


def test_pdf_page_render_failure_is_visible_without_tmp_artifact(env, monkeypatch):
    settings, db, app = env
    pdf = fitz.open()
    pdf.new_page(width=120, height=80)
    pdf.new_page(width=160, height=90)
    payload = pdf.tobytes()
    pdf.close()
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    original_replace = Path.replace

    def fail_page_replace(path: Path, target: Path, *args, **kwargs):
        if path.name.endswith(".png.tmp") and str(path).startswith(str(settings.attachment_dir)):
            raise OSError("injected page render failure")
        return original_replace(path, target, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", fail_page_replace)
    document = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(payload, "page-failure.pdf", "application/pdf"), "paper", None, ctx, db, settings))
    with db.session() as conn:
        pages = conn.execute("SELECT status,failure_code,object_key FROM source_pages WHERE document_id=? ORDER BY page_index", (document["document_id"],)).fetchall()
    assert [tuple(page) for page in pages] == [("failed", "PDF_PAGE_RENDER_FAILED", None), ("failed", "PDF_PAGE_RENDER_FAILED", None)]
    assert not [path for path in settings.attachment_dir.rglob("*.tmp") if path.is_file()]


def test_grade_worker_preserves_raw_answer_and_applies_schedule_once(env):
    settings, db, _ = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?)", ("q-1", "shared", "approved", "obj-1", now))
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,?,?,?,?,?,?)", ("qv-1", "q-1", 1, '{"prompt":"-3-(-5)"}', '{"accepted":["2"]}', "exact-text-v1", "approved", now))
        conn.execute("INSERT INTO review_cards(id,learner_id,knowledge_point_id,objective_id,state,stage,due_at,timezone_snapshot,scheduler_version,revision,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("card-1", "learner-a", "kp-1", "obj-1", "review", 0, "2000-01-01T00:00:00+00:00", "Asia/Shanghai", "interval-v1", 1, now, now))
        conn.execute("INSERT INTO test_sessions(id,learner_id,mode,status,created_at) VALUES (?,?,?,?,?)", ("session-1", "learner-a", "independent", "active", now))
        conn.execute("INSERT INTO test_items(id,session_id,learner_id,question_version_id,card_id,cycle_id,reserved_revision,status,assistance,presented_at) VALUES (?,?,?,?,?,?,?,?,?,?)", ("ti-1", "session-1", "learner-a", "qv-1", "card-1", "cycle-1", 1, "grading_pending", "none", now))
        conn.execute("INSERT INTO attempts(id,test_item_id,learner_id,raw_answer,submitted_at,assistance,assessment_eligibility,status,idempotency_key) VALUES (?,?,?,?,?,?,?,?,?)", ("attempt-1", "ti-1", "learner-a", " 2 ", now, "none", 1, "grading_pending", "answer-1"))
        conn.execute("INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", ("job-grade-1", "learner-a", "grade_attempt", '{"attempt_id":"attempt-1"}', "grade-attempt-1", "queued", now, now))
    result = run_worker_once(db, settings)
    assert result["status"] == "succeeded"
    assert result["result"]["outcome"] == "correct"
    assert run_worker_once(db, settings)["status"] == "idle"
    with db.session() as conn:
        attempt = conn.execute("SELECT raw_answer,normalized_answer,status FROM attempts WHERE id='attempt-1'").fetchone()
        card = conn.execute("SELECT stage,state,revision FROM review_cards WHERE id='card-1'").fetchone()
        assert tuple(attempt) == (" 2 ", "2", "graded")
        assert tuple(card) == (1, "review", 2)
        assert conn.execute("SELECT COUNT(*) FROM review_events WHERE card_id='card-1'").fetchone()[0] == 1


def _seed_stage5_gate_fixture(db, *, recent_exposure: str | None = None, current_mode: str = "independent"):
    """Create historical independent evidence for a stage-five maintenance check."""
    with db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO review_cards(id,learner_id,knowledge_point_id,objective_id,state,stage,due_at,timezone_snapshot,scheduler_version,revision,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("card-stage5", "learner-a", "kp-1", "obj-1", "review", 5, "2026-12-31T00:00:00+00:00", "Asia/Shanghai", "interval-v1", 1, "2026-11-01T00:00:00+00:00", "2026-11-01T00:00:00+00:00"),
        )
        for index, (day, variant_group) in enumerate((("2026-10-01", "variant-a"), ("2026-10-10", "variant-b"), ("2026-10-20", "variant-a")), 1):
            question_id = f"q-stage5-{index}"
            version_id = f"qv-stage5-{index}"
            session_id = f"session-stage5-{index}"
            item_id = f"item-stage5-{index}"
            attempt_id = f"attempt-stage5-{index}"
            submitted = f"{day}T02:00:00+00:00"
            conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?)", (question_id, "shared", "approved", "obj-1", submitted))
            conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,variant_kind,variant_group,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (version_id, question_id, 1, '{"prompt":"stage5"}', '{"accepted":["ok"]}', "exact-text-v1", "approved", "variant", variant_group, submitted))
            conn.execute("INSERT INTO test_sessions(id,learner_id,mode,status,created_at) VALUES (?,?,?,?,?)", (session_id, "learner-a", "independent", "completed", submitted))
            conn.execute("INSERT INTO test_items(id,session_id,learner_id,question_version_id,status,assistance,presented_at) VALUES (?,?,?,?,?,?,?)", (item_id, session_id, "learner-a", version_id, "graded", "none", submitted))
            conn.execute("INSERT INTO attempts(id,test_item_id,learner_id,raw_answer,normalized_answer,submitted_at,assistance,assessment_eligibility,status,idempotency_key) VALUES (?,?,?,?,?,?,?,?,?,?)", (attempt_id, item_id, "learner-a", "ok", "ok", submitted, "none", 1, "graded", f"key-{index}"))
            conn.execute("INSERT INTO grade_versions(id,attempt_id,outcome,score,feedback,rubric_version,validator_version,created_at) VALUES (?,?,?,?,?,?,?,?)", (f"grade-stage5-{index}", attempt_id, "correct", 1.0, "ok", "exact-text-v1", "exact-text-v1", submitted))
        current_question = "q-stage5-current"
        current_version = "qv-stage5-current"
        conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?)", (current_question, "shared", "approved", "obj-1", "2026-12-31T02:00:00+00:00"))
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,variant_kind,variant_group,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (current_version, current_question, 1, '{"prompt":"stage5 current"}', '{"accepted":["ok"]}', "exact-text-v1", "approved", "base", None, "2026-12-31T02:00:00+00:00"))
        conn.execute("INSERT INTO test_sessions(id,learner_id,mode,status,created_at) VALUES (?,?,?,?,?)", ("session-stage5-current", "learner-a", current_mode, "active", "2026-12-31T02:00:00+00:00"))
        conn.execute("INSERT INTO test_items(id,session_id,learner_id,question_version_id,card_id,cycle_id,reserved_revision,status,assistance,presented_at) VALUES (?,?,?,?,?,?,?,?,?,?)", ("item-stage5-current", "session-stage5-current", "learner-a", current_version, "card-stage5", "cycle-stage5", 1, "grading_pending", "none", "2026-12-31T02:00:00+00:00"))
        conn.execute("INSERT INTO attempts(id,test_item_id,learner_id,raw_answer,submitted_at,assistance,assessment_eligibility,status,idempotency_key) VALUES (?,?,?,?,?,?,?,?,?)", ("attempt-stage5-current", "item-stage5-current", "learner-a", "ok", "2026-12-31T02:00:00+00:00", "none", 1, "grading_pending", "key-current"))
        conn.execute("INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", ("job-stage5-current", "learner-a", "grade_attempt", '{"attempt_id":"attempt-stage5-current"}', "job-key-current", "queued", "2026-12-31T02:00:00+00:00", "2026-12-31T02:00:00+00:00"))
        if recent_exposure:
            conn.execute("INSERT INTO learning_events(id,learner_id,objective_id,event_type,source,assistance,accepted_at,metadata_json) VALUES (?,?,?,?,?,?,?,?)", ("event-stage5-recent", "learner-a", "obj-1", "new_learning", "trusted_learning_input", "none", recent_exposure, "{}"))


def test_stage5_requires_maintenance_gate_and_current_attempt_is_not_exposure(env):
    settings, db, _ = env
    _seed_stage5_gate_fixture(db)
    result = run_worker_once(db, settings)
    assert result["status"] == "succeeded"
    assert result["result"]["maintenance_eligibility"]["eligible"] is True
    with db.session() as conn:
        card = conn.execute("SELECT state,stage,due_at FROM review_cards WHERE id='card-stage5'").fetchone()
    assert tuple(card) == ("maintenance", 5, "2027-01-30T00:00:00+00:00")


def test_stage5_recent_exposure_keeps_card_in_review(env):
    settings, db, _ = env
    _seed_stage5_gate_fixture(db, recent_exposure="2026-12-15T02:00:00+00:00")
    result = run_worker_once(db, settings)
    assert result["status"] == "succeeded"
    gate = result["result"]["maintenance_eligibility"]
    assert gate["eligible"] is False
    assert gate["exposure_gap_days"] < 30
    with db.session() as conn:
        card = conn.execute("SELECT state,stage,due_at FROM review_cards WHERE id='card-stage5'").fetchone()
    assert tuple(card) == ("review", 5, "2027-01-30T00:00:00+00:00")


def test_stage5_practice_answer_does_not_count_as_maintenance_evidence(env):
    settings, db, _ = env
    _seed_stage5_gate_fixture(db, current_mode="practice")
    result = run_worker_once(db, settings)
    assert result["status"] == "succeeded"
    gate = result["result"]["maintenance_eligibility"]
    assert gate["eligible"] is False
    with db.session() as conn:
        card = conn.execute("SELECT state,stage FROM review_cards WHERE id='card-stage5'").fetchone()
    assert tuple(card) == ("review", 5)


def test_static_number_line_parameters_are_exact_and_bounded(env):
    settings, db, app = env
    from learning_service.app import Context, VisualJobRequest

    with db.session(write=True) as conn:
        conn.execute("INSERT INTO visual_templates(id,version,template_id,parameter_schema_json,approval,created_at) VALUES (?,?,?,?,?,?)", ("template-1", "1.0.0", "signed_number_subtraction", '{}', "approved", utc_now()))
    endpoint = _route(app, "/api/v1/visual-jobs")
    result = endpoint(VisualJobRequest(template_id="signed_number_subtraction", parameters={"start": -3, "subtrahend": -5}), Context(account_id="acct-a", learner_id="learner-a"), db)
    assert result["spec"]["computed"]["result"] == 2
    assert result["spec"]["computed"]["direction"] == "right"
    with pytest.raises(APIError, match="超出数轴模板范围"):
        endpoint(VisualJobRequest(template_id="signed_number_subtraction", parameters={"start": 101, "subtrahend": 1}), Context(account_id="acct-a", learner_id="learner-a"), db)


def test_backup_restore_keeps_database_and_private_asset(tmp_path: Path, env):
    settings, db, _ = env
    settings.attachment_dir.mkdir(parents=True, exist_ok=True)
    private_file = settings.attachment_dir / "learner-a" / "asset.bin"
    private_file.parent.mkdir(parents=True, exist_ok=True)
    private_file.write_bytes(b"synthetic-private-asset")
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)", ("asset-backup", "learner-a", "private", "learner-a/asset.bin", "hash", "application/octet-stream", 23, "source_document", utc_now()))
    backup_dir = tmp_path / "backup"
    manifest = backup_data(settings.data_dir, backup_dir)
    assert manifest["format"] == "dd-learning-backup-v1"
    restore_dir = tmp_path / "restored"
    restore_data(backup_dir, restore_dir)
    restored = Database(restore_dir / "learning.db")
    with restored.session() as conn:
        assert conn.execute("SELECT learner_id FROM assets WHERE id='asset-backup'").fetchone()[0] == "learner-a"
    assert (restore_dir / "attachments/learner-a/asset.bin").read_bytes() == b"synthetic-private-asset"


def test_restore_rejects_manifest_drift_checksum_tampering_and_nonempty_target(tmp_path: Path, env):
    settings, _, _ = env
    backup_dir = tmp_path / "integrity-backup"
    backup_data(settings.data_dir, backup_dir)

    extra = backup_dir / "unexpected.bin"
    extra.write_bytes(b"not in the manifest")
    with pytest.raises(ValueError, match="manifest file list mismatch"):
        restore_data(backup_dir, tmp_path / "extra-restore")
    extra.unlink()

    (backup_dir / "learning.db").write_bytes((backup_dir / "learning.db").read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="backup checksum mismatch: learning.db"):
        restore_data(backup_dir, tmp_path / "checksum-restore")

    clean_backup = tmp_path / "clean-backup"
    backup_data(settings.data_dir, clean_backup)
    nonempty = tmp_path / "nonempty-target"
    nonempty.mkdir()
    (nonempty / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError, match="restore target is not empty"):
        restore_data(clean_backup, nonempty)


def test_admin_export_is_local_audited_artifact_and_delete_cleans_files(env):
    settings, db, app = env
    image = Image.new("RGB", (2, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    document = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "export.png", "image/png"), "paper", None, ctx, db, settings))
    with db.session() as conn:
        object_key = conn.execute("SELECT object_key FROM assets WHERE id=?", (document["asset_id"],)).fetchone()[0]
    source_path = settings.attachment_dir / object_key
    assert source_path.is_file()
    export = _route(app, "/api/v1/admin/exports")({"learner_id": "learner-a"}, ctx, db)
    assert export["status"] == "completed"
    artifact = (settings.export_dir or settings.data_dir / "exports") / "learner-a" / f"{export['export_id']}.json"
    assert artifact.is_file()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["format"] == "dd-learning-export-v1"
    assert payload["documents"][0]["id"] == document["document_id"]
    assert "admin_secret" not in artifact.read_text(encoding="utf-8")
    downloaded = _route(app, "/api/v1/admin/exports/{export_id}")(export["export_id"], ctx, db)
    assert Path(downloaded.path) == artifact

    deleted = _route(app, "/api/v1/admin/deletions")({"learner_id": "learner-a"}, ctx, db)
    assert deleted["status"] == "completed"
    assert deleted["assets_deleted"] == 1
    assert not source_path.exists()
    with db.session() as conn:
        asset = conn.execute("SELECT deleted_at FROM assets WHERE id=?", (document["asset_id"],)).fetchone()
        record = conn.execute("SELECT cleanup_state FROM deletion_records WHERE resource_id=?", (document["asset_id"],)).fetchone()
        page_status = conn.execute("SELECT status FROM source_pages WHERE document_id=?", (document["document_id"],)).fetchone()[0]
    assert asset["deleted_at"] is not None
    assert record["cleanup_state"] == "completed"
    assert page_status == "deleted"
    with pytest.raises(APIError, match="学习者不可访问"):
        _route(app, "/api/v1/documents/{document_id}")(document["document_id"], ctx, db)


def test_export_write_failure_cleans_partial_artifact_and_is_retryable(env, monkeypatch):
    settings, db, app = env
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    export_root = settings.export_dir or (settings.data_dir / "exports")
    original_replace = Path.replace

    def fail_export_replace(path: Path, target: Path, *args, **kwargs):
        if path.suffix == ".tmp" and str(path).startswith(str(export_root)):
            raise OSError("injected export replace failure")
        return original_replace(path, target, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", fail_export_replace)
    with pytest.raises(APIError, match="导出失败，可重试") as error:
        _route(app, "/api/v1/admin/exports")({"learner_id": "learner-a"}, ctx, db)
    assert error.value.code == "EXPORT_FAILED"
    with db.session() as conn:
        failed = conn.execute("SELECT id,artifact_key,status,error_code FROM export_jobs ORDER BY created_at DESC LIMIT 1").fetchone()
    assert tuple(failed[2:]) == ("failed", "OSError")
    failed_target = export_root / failed["artifact_key"]
    assert not failed_target.exists()
    assert not failed_target.with_suffix(failed_target.suffix + ".tmp").exists()
    with pytest.raises(APIError, match="导出尚未完成"):
        _route(app, "/api/v1/admin/exports/{export_id}")(failed["id"], ctx, db)

    monkeypatch.setattr(Path, "replace", original_replace)
    retry = _route(app, "/api/v1/admin/exports")({"learner_id": "learner-a"}, ctx, db)
    assert retry["status"] == "completed"
    assert (export_root / "learner-a" / f"{retry['export_id']}.json").is_file()


def test_delete_records_and_cleans_derived_learning_resources(env):
    settings, db, app = env
    image = Image.new("RGB", (2, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    document = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "lifecycle.png", "image/png"), "paper", None, ctx, db, settings))
    batch = _route(app, "/api/v1/import-batches")(BatchRequest(document_ids=[document["document_id"]]), ctx, db)
    analysis = _route(app, "/api/v1/import-batches/{batch_id}/analysis")(batch["batch_id"], _request({"Idempotency-Key": "lifecycle-analysis"}), ctx, db)
    assert run_worker_once(db, settings)["status"] == "succeeded"
    item = _route(app, "/api/v1/import-batches/{batch_id}/items")(batch["batch_id"], ctx, db)["items"][0]
    _route(app, "/api/v1/import-items/{item_id}")(item["id"], ItemPatch(expected_revision=1, verdict="incorrect", evidence={"teacher_mark": "x"}, objective_id="obj-1"), ctx, db)
    challenge = _route(app, "/api/v1/import-batches/{batch_id}/confirmation-challenges")(
        batch["batch_id"], ChallengeRequest(items=[{"item_id": item["id"], "expected_revision": 2}]), ctx, db, settings
    )
    _route(app, "/api/v1/import-batches/{batch_id}/confirmations")(
        batch["batch_id"],
        ConfirmationRequest(challenge_id=challenge["challenge_id"], nonce=challenge["nonce"], items=[{"item_id": item["id"], "expected_revision": 2}]),
        _request({"Idempotency-Key": "lifecycle-confirm"}),
        ctx,
        db,
    )
    with db.session() as conn:
        mistake_id = conn.execute("SELECT id FROM mistake_entries WHERE learner_id='learner-a'").fetchone()[0]
    diagnosis = _route(app, "/api/v1/mistakes/{mistake_id}/diagnoses")(mistake_id, __import__("learning_service.app", fromlist=["DiagnosisRequest"]).DiagnosisRequest(), ctx, db, settings)
    draft = _route(app, "/api/v1/learning-drafts")(DraftRequest(objective_id="obj-1", content={"answer": "-3"}), ctx, db)
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO visual_templates(id,version,template_id,parameter_schema_json,approval,created_at) VALUES (?,?,?,?,?,?)", ("template-lifecycle", "1.0.0", "signed_number_subtraction", '{}', "approved", utc_now()))
    visual = _route(app, "/api/v1/visual-jobs")(__import__("learning_service.app", fromlist=["VisualJobRequest"]).VisualJobRequest(template_id="signed_number_subtraction", parameters={"start": 2, "subtrahend": -3}), ctx, db)
    export = _route(app, "/api/v1/admin/exports")({"learner_id": "learner-a"}, ctx, db)
    export_path = (settings.export_dir or settings.data_dir / "exports") / "learner-a" / f"{export['export_id']}.json"
    assert export_path.is_file()

    deleted = _route(app, "/api/v1/admin/deletions")({"learner_id": "learner-a"}, ctx, db)
    assert deleted["status"] == "completed"
    assert deleted["resources_marked"] >= 5
    assert not export_path.exists()
    with db.session() as conn:
        rows = conn.execute("SELECT resource_type,cleanup_state FROM deletion_records WHERE learner_id='learner-a'").fetchall()
        states = {row["resource_type"]: row["cleanup_state"] for row in rows}
        assert states["asset"] == "completed"
        assert states["diagnosis"] == "completed"
        assert states["learning_draft"] == "completed"
        assert states["visual_asset"] == "completed"
        assert states["export_artifact"] == "completed"
        assert conn.execute("SELECT status FROM diagnoses WHERE id=?", (diagnosis["diagnosis_id"],)).fetchone()[0] == "deleted"
        assert conn.execute("SELECT status FROM learning_drafts WHERE id=?", (draft["draft_id"],)).fetchone()[0] == "deleted"
        assert conn.execute("SELECT approval FROM visual_assets WHERE id=?", (visual["asset_id"],)).fetchone()[0] == "retracted"
        assert conn.execute("SELECT status FROM export_jobs WHERE id=?", (export["export_id"],)).fetchone()[0] == "cancelled"
        assert conn.execute("SELECT active FROM learners WHERE id='learner-a'").fetchone()[0] == 0
    assert analysis["job_id"]


def test_provider_boundaries_are_explicit_and_variant_stays_reviewable(env):
    settings, db, app = env
    page = {"id": "page-1", "page_index": 0}
    document_result = document_provider("mock-document-v1").analyze_page(page)
    assert document_result.status == "needs_review"
    assert document_result.evidence["ocr_performed"] is False
    diagnosis_result = diagnosis_provider("mock-diagnosis-v1").diagnose({"source_item_id": "item-1"})
    assert diagnosis_result.status == "needs_review"
    variant_result = variant_provider("mock-variant-v1").generate({"objective_id": "obj-1"})
    assert variant_result.status == "needs_review"

    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    job = _route(app, "/api/v1/variant-jobs")({"objective_id": "obj-1"}, ctx, db)
    run = run_worker_once(db, settings)
    assert run["status"] == "succeeded"
    assert run["job_id"] == job["job_id"]
    assert run["result"]["status"] == "needs_review"
    assert run["result"]["external_call"] is False
    assert run["result"]["evidence"]["mode"] == "deterministic_mock"


def test_restore_replays_deletion_tombstones(tmp_path: Path, env):
    settings, db, _ = env
    settings.attachment_dir.mkdir(parents=True, exist_ok=True)
    path = settings.attachment_dir / "learner-a" / "stale.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"stale")
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)", ("asset-tombstone", "learner-a", "private", "learner-a/stale.bin", "stale", "application/octet-stream", 5, "source_document", now))
        conn.execute("INSERT INTO deletion_records(id,learner_id,resource_type,resource_id,policy_version,created_at,cleanup_state,object_key) VALUES (?,?,?,?,?,?,?,?)", ("del-tombstone", "learner-a", "asset", "asset-tombstone", "lifecycle-v1", now, "pending", "learner-a/stale.bin"))
    backup_dir = tmp_path / "tombstone-backup"
    backup_data(settings.data_dir, backup_dir)
    restore_dir = tmp_path / "tombstone-restored"
    restore_data(backup_dir, restore_dir)
    assert not (restore_dir / "attachments/learner-a/stale.bin").exists()
    restored = Database(restore_dir / "learning.db")
    with restored.session() as conn:
        assert conn.execute("SELECT deleted_at FROM assets WHERE id='asset-tombstone'").fetchone()[0] is not None
        assert conn.execute("SELECT cleanup_state FROM deletion_records WHERE id='del-tombstone'").fetchone()[0] == "completed"


def test_restore_migrates_legacy_tombstone_schema_before_replay(tmp_path: Path):
    legacy_migrations = tmp_path / "legacy-migrations"
    legacy_migrations.mkdir()
    shutil.copy2(Path(__file__).parents[1] / "learning_service/migrations/001_initial.sql", legacy_migrations / "001_initial.sql")
    source = tmp_path / "legacy-source"
    source.mkdir()
    legacy_db = Database(source / "learning.db", legacy_migrations)
    stale = source / "attachments" / "learner-a" / "legacy.bin"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"legacy")
    now = utc_now()
    with legacy_db.session(write=True) as conn:
        conn.execute("INSERT INTO accounts(id,created_at) VALUES (?,?)", ("acct-a", now))
        conn.execute("INSERT INTO learners(id,display_name,created_at) VALUES (?,?,?)", ("learner-a", "Legacy", now))
        conn.execute("INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)", ("legacy-asset", "learner-a", "private", "learner-a/legacy.bin", "legacy", "application/octet-stream", 6, "source_document", now))
        conn.execute("INSERT INTO deletion_records(id,learner_id,resource_type,resource_id,policy_version,created_at) VALUES (?,?,?,?,?,?)", ("legacy-deletion", "learner-a", "asset", "legacy-asset", "lifecycle-v1", now))
    backup_dir = tmp_path / "legacy-backup"
    backup_data(source, backup_dir)
    restored_dir = tmp_path / "legacy-restored"
    restore_data(backup_dir, restored_dir)
    assert not (restored_dir / "attachments/learner-a/legacy.bin").exists()
    restored = Database(restored_dir / "learning.db")
    with restored.session() as conn:
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 6
        assert conn.execute("SELECT deleted_at FROM assets WHERE id='legacy-asset'").fetchone()[0] is not None
        assert conn.execute("SELECT cleanup_state FROM deletion_records WHERE id='legacy-deletion'").fetchone()[0] == "completed"


def test_delete_cleanup_failure_keeps_resource_private_and_records_error(env, monkeypatch):
    settings, db, app = env
    image = Image.new("RGB", (2, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    document = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "failure.png", "image/png"), "paper", None, ctx, db, settings))
    with db.session() as conn:
        object_key = conn.execute("SELECT object_key FROM assets WHERE id=?", (document["asset_id"],)).fetchone()[0]
    source_path = settings.attachment_dir / object_key
    original_unlink = Path.unlink

    def fail_source_unlink(path: Path, *args, **kwargs):
        if path == source_path:
            raise OSError("injected cleanup failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_source_unlink)
    deleted = _route(app, "/api/v1/admin/deletions")({"learner_id": "learner-a"}, ctx, db)
    assert deleted["status"] == "partial"
    assert deleted["assets_marked"] == 1
    assert deleted["assets_deleted"] == 0
    assert deleted["assets_failed"] == 1
    assert source_path.exists()
    with db.session() as conn:
        row = conn.execute("SELECT cleanup_state,error_code FROM deletion_records WHERE resource_id=?", (document["asset_id"],)).fetchone()
        assert tuple(row) == ("failed", "OSError")
        assert conn.execute("SELECT deleted_at FROM assets WHERE id=?", (document["asset_id"],)).fetchone()[0] is not None
    with pytest.raises(APIError, match="学习者不可访问"):
        _route(app, "/api/v1/documents/{document_id}")(document["document_id"], ctx, db)


def test_direct_full_upload_analysis_review_chain(env):
    settings, db, app = env
    image = Image.new("RGB", (2, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    upload = _AsyncUpload(data.getvalue(), "paper.png", "image/png")
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    upload_endpoint = _route(app, "/api/v1/documents")
    document = asyncio.run(upload_endpoint(upload, "paper", None, ctx, db, settings))
    batch_endpoint = _route(app, "/api/v1/import-batches")
    batch = batch_endpoint(__import__("learning_service.app", fromlist=["BatchRequest"]).BatchRequest(document_ids=[document["document_id"]]), ctx, db)
    analysis_endpoint = _route(app, "/api/v1/import-batches/{batch_id}/analysis")
    analysis = analysis_endpoint(batch["batch_id"], _request(), ctx, db)
    assert analysis["status"] == "queued"
    assert run_worker_once(db, settings)["status"] == "succeeded"
    items = _route(app, "/api/v1/import-batches/{batch_id}/items")(batch["batch_id"], ctx, db)["items"]
    assert len(items) == 1 and items[0]["status"] == "needs_review"
    patch = _route(app, "/api/v1/import-items/{item_id}")(items[0]["id"], __import__("learning_service.app", fromlist=["ItemPatch"]).ItemPatch(expected_revision=1, verdict="incorrect", evidence={"teacher_mark": "cross"}, objective_id="obj-1"), ctx, db)
    assert patch["revision"] == 2
    with pytest.raises(APIError, match="候选题已更新"):
        _route(app, "/api/v1/import-items/{item_id}")(items[0]["id"], __import__("learning_service.app", fromlist=["ItemPatch"]).ItemPatch(expected_revision=1, verdict="incorrect", evidence={"teacher_mark": "cross"}, objective_id="obj-1"), ctx, db)


def test_analysis_retry_is_revision_scoped_and_idempotent(env):
    settings, db, app = env
    image = Image.new("RGB", (2, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    document = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "retry.png", "image/png"), "paper", None, ctx, db, settings))
    batch = _route(app, "/api/v1/import-batches")(BatchRequest(document_ids=[document["document_id"]]), ctx, db)
    analysis = _route(app, "/api/v1/import-batches/{batch_id}/analysis")
    first = analysis(batch["batch_id"], _request({"Idempotency-Key": "analysis-key"}), ctx, db)
    assert analysis(batch["batch_id"], _request({"Idempotency-Key": "analysis-key"}), ctx, db) == first
    assert run_worker_once(db, settings)["status"] == "succeeded"
    items = _route(app, "/api/v1/import-batches/{batch_id}/items")(batch["batch_id"], ctx, db)["items"]
    _route(app, "/api/v1/import-items/{item_id}")(items[0]["id"], ItemPatch(expected_revision=1, verdict="incorrect", evidence={"teacher_mark": "cross"}, objective_id="obj-1"), ctx, db)
    second = analysis(batch["batch_id"], _request({"Idempotency-Key": "analysis-key"}), ctx, db)
    assert second["job_id"] != first["job_id"]


def test_cross_learner_document_and_missing_confirmation_key_are_rejected(env):
    settings, db, app = env
    image = Image.new("RGB", (2, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    owner = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    document = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "private.png", "image/png"), "paper", None, owner, db, settings))
    with pytest.raises(APIError) as error:
        _route(app, "/api/v1/documents/{document_id}")(document["document_id"], Context(account_id="acct-b", learner_id="learner-b"), db)
    assert error.value.code == "RESOURCE_NOT_FOUND"

    batch = _route(app, "/api/v1/import-batches")(BatchRequest(document_ids=[document["document_id"]]), owner, db)
    challenge = _route(app, "/api/v1/import-batches/{batch_id}/confirmation-challenges")
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO import_items(id,batch_id,learner_id,occurrence_id,locator,page_index,content_json,teacher_evidence_json,verdict,verification_status,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("item-key", batch["batch_id"], "learner-a", "occ-key", "page:1:item:1", 0, '{"objective_id":"obj-1"}', '{"mark":"x"}', "incorrect", "manual", "ready"))
        conn.execute("INSERT INTO import_judgments(id,item_id,revision,verdict,evidence_json,basis_version,verification_status,created_at) VALUES (?,?,?,?,?,?,?,?)", ("judge-key", "item-key", 1, "incorrect", '{"mark":"x"}', "manual-v1", "manual", utc_now()))
    token = challenge(batch["batch_id"], ChallengeRequest(items=[{"item_id": "item-key", "expected_revision": 1}]), owner, db, settings)
    with pytest.raises(APIError) as error:
        _route(app, "/api/v1/import-batches/{batch_id}/confirmations")(
            batch["batch_id"],
            ConfirmationRequest(challenge_id=token["challenge_id"], nonce=token["nonce"], items=[{"item_id": "item-key", "expected_revision": 1}]),
            _request(),
            owner,
            db,
        )
    assert error.value.code == "IDEMPOTENCY_REQUIRED"


def test_cancelled_session_rejects_submission(env):
    settings, db, app = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?)", ("q-cancel", "shared", "approved", "obj-1", now))
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,?,?,?,?,?,?)", ("qv-cancel", "q-cancel", 1, '{"prompt":"1+1"}', '{"accepted":["2"]}', "exact-text-v1", "approved", now))
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    session = _route(app, "/api/v1/test-sessions")(SessionRequest(question_version_id="qv-cancel"), ctx, db)
    _route(app, "/api/v1/test-sessions/{session_id}/cancel")(session["session_id"], ctx, db)
    with pytest.raises(APIError) as error:
        _route(app, "/api/v1/test-items/{item_id}/submission-challenges")(session["items"][0]["test_item_id"], ctx, db, settings)
    assert error.value.code == "TEST_ITEM_NOT_FOUND"


def test_hint_submission_does_not_count_as_independent(env):
    settings, db, app = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?)", ("q-hint", "shared", "approved", "obj-1", now))
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,?,?,?,?,?,?)", ("qv-hint", "q-hint", 1, '{"prompt":"1+1","hint":"先列算式"}', '{"accepted":["2"]}', "exact-text-v1", "approved", now))
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    session = _route(app, "/api/v1/test-sessions")(SessionRequest(question_version_id="qv-hint", mode="independent"), ctx, db)
    item_id = session["items"][0]["test_item_id"]
    hint = _route(app, "/api/v1/test-items/{item_id}/hints")(item_id, ctx, db)
    assert hint["assistance"] == "hint"
    challenge = _route(app, "/api/v1/test-items/{item_id}/submission-challenges")(item_id, ctx, db, settings)
    answer = _route(app, "/api/v1/test-items/{item_id}/answers")(item_id, AnswerRequest(challenge_id=challenge["challenge_id"], nonce=challenge["nonce"], raw_answer="2"), _request({"Idempotency-Key": "hint-answer"}), ctx, db)
    assert answer["assessment_eligibility"] is False
    assert run_worker_once(db, settings)["status"] == "succeeded"
    with db.session() as conn:
        row = conn.execute("SELECT raw_answer,assessment_eligibility FROM attempts WHERE id=?", (answer["attempt_id"],)).fetchone()
        assert tuple(row) == ("2", 0)
        assert conn.execute("SELECT COUNT(*) FROM review_events").fetchone()[0] == 0


def test_challenge_expiry_and_actor_binding(env):
    settings, db, app = env
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    draft = _route(app, "/api/v1/learning-drafts")(DraftRequest(objective_id="obj-1", content={"source": "test"}), ctx, db)
    expired = Settings(settings.data_dir, settings.db_path, settings.attachment_dir, settings.admin_secret, settings.adapter_secret, settings.dev_mode, challenge_ttl_seconds=0)
    challenge = _route(app, "/api/v1/learning-drafts/{draft_id}/confirmation-challenges")(draft["draft_id"], ctx, db, expired)
    with pytest.raises(APIError) as error:
        _route(app, "/api/v1/learning-drafts/{draft_id}/confirmations")(
            draft["draft_id"],
            DraftConfirmation(challenge_id=challenge["challenge_id"], nonce=challenge["nonce"]),
            _request({"Idempotency-Key": "expired-draft"}),
            ctx,
            db,
            settings,
        )
    assert error.value.code == "CHALLENGE_EXPIRED"

    with db.session(write=True) as conn:
        conn.execute("INSERT INTO learner_access(account_id,learner_id,role,created_at) VALUES (?,?,?,?)", ("acct-b", "learner-a", "student", utc_now()))
    challenge = _route(app, "/api/v1/learning-drafts/{draft_id}/confirmation-challenges")(draft["draft_id"], ctx, db, settings)
    other_actor = Context(account_id="acct-b", learner_id="learner-a", role="student")
    with pytest.raises(APIError) as error:
        _route(app, "/api/v1/learning-drafts/{draft_id}/confirmations")(
            draft["draft_id"],
            DraftConfirmation(challenge_id=challenge["challenge_id"], nonce=challenge["nonce"]),
            _request({"Idempotency-Key": "wrong-actor"}),
            other_actor,
            db,
            settings,
        )
    assert error.value.code == "CHALLENGE_INVALID"


def test_learning_draft_confirmation_is_idempotent_and_preserves_raw_content(env):
    settings, db, app = env
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    draft = _route(app, "/api/v1/learning-drafts")(DraftRequest(objective_id="obj-1", content={"answer": "-3 - (-5)"}), ctx, db)
    challenge = _route(app, "/api/v1/learning-drafts/{draft_id}/confirmation-challenges")(draft["draft_id"], ctx, db, settings)
    endpoint = _route(app, "/api/v1/learning-drafts/{draft_id}/confirmations")
    body = DraftConfirmation(challenge_id=challenge["challenge_id"], nonce=challenge["nonce"], raw_content={"answer": "-3 - (-5)"})
    request = _request({"Idempotency-Key": "draft-confirm-1"})
    result = endpoint(draft["draft_id"], body, request, ctx, db, settings)
    assert result["status"] == "confirmed"
    assert endpoint(draft["draft_id"], body, request, ctx, db, settings) == result
    with pytest.raises(APIError, match="相同幂等键携带了不同内容"):
        endpoint(draft["draft_id"], body.model_copy(update={"raw_content": {"answer": "9"}}), request, ctx, db, settings)
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM learning_events WHERE learner_id='learner-a' AND event_type='new_learning'").fetchone()[0] == 1
        metadata = conn.execute("SELECT metadata_json FROM learning_events WHERE learner_id='learner-a' AND event_type='new_learning'").fetchone()[0]
        assert json.loads(metadata) == {"content": {"answer": "-3 - (-5)"}}


def test_learning_draft_rejects_client_content_replacement_without_consuming_challenge(env):
    settings, db, app = env
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    draft = _route(app, "/api/v1/learning-drafts")(DraftRequest(objective_id="obj-1", content={"answer": "2"}), ctx, db)
    challenge = _route(app, "/api/v1/learning-drafts/{draft_id}/confirmation-challenges")(draft["draft_id"], ctx, db, settings)
    endpoint = _route(app, "/api/v1/learning-drafts/{draft_id}/confirmations")
    with pytest.raises(APIError, match="确认内容与服务端学习草稿不一致"):
        endpoint(draft["draft_id"], DraftConfirmation(challenge_id=challenge["challenge_id"], nonce=challenge["nonce"], raw_content={"answer": "9"}), _request({"Idempotency-Key": "draft-mismatch"}), ctx, db, settings)
    with db.session() as conn:
        assert conn.execute("SELECT consumed_at FROM interaction_challenges WHERE id=?", (challenge["challenge_id"],)).fetchone()[0] is None


def test_trusted_tool_read_endpoints_are_learner_scoped_and_never_expose_answer_key(env):
    settings, db, app = env
    learner_a = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    learner_b = Context(account_id="acct-b", learner_id="learner-b", role="student")
    draft = _route(app, "/api/v1/learning-drafts")(
        DraftRequest(objective_id="obj-1", content={"answer": "student original"}), learner_a, db
    )
    get_draft = _route(app, "/api/v1/learning-drafts/{draft_id}")
    draft_view = get_draft(draft["draft_id"], learner_a, db)
    assert draft_view["id"] == draft["draft_id"]
    assert draft_view["revision"] == 1
    assert draft_view["content"] == {"answer": "student original"}
    assert draft_view["status"] == "draft"
    with pytest.raises(APIError) as cross_learner_draft:
        get_draft(draft["draft_id"], learner_b, db)
    assert cross_learner_draft.value.code == "DRAFT_NOT_FOUND"

    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO questions(id,learner_id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?,?)",
            ("question-secure", "learner-a", "private", "approved", "obj-1", now),
        )
        conn.execute(
            "INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,?,?,?,?,?,?)",
            ("question-secure-v1", "question-secure", 1, '{"prompt":"2+2=?"}', '{"accepted":["4"],"explanation":"secret key"}', "exact-text-v1", "approved", now),
        )
    session = _route(app, "/api/v1/test-sessions")(
        SessionRequest(question_version_id="question-secure-v1"), learner_a, db
    )
    test_item_id = session["items"][0]["test_item_id"]
    get_test_item = _route(app, "/api/v1/test-items/{item_id}")
    item = get_test_item(test_item_id, learner_a, db)
    assert item["prompt"] == "2+2=?"
    assert "answer_key" not in item and "accepted" not in json.dumps(item) and "secret key" not in json.dumps(item)
    with pytest.raises(APIError) as cross_learner_item:
        get_test_item(test_item_id, learner_b, db)
    assert cross_learner_item.value.code == "TEST_ITEM_NOT_FOUND"


def test_cancelled_job_and_stale_worker_result_are_not_success(env):
    settings, db, app = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", ("job-cancel", "learner-a", "document_analysis", '{"batch_id":"missing"}', "cancel-key", "queued", now, now))
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    result = _route(app, "/api/v1/jobs/{job_id}/cancel")("job-cancel", ctx, db)
    assert result == {"job_id": "job-cancel", "status": "cancelled"}
    assert run_worker_once(db, settings)["status"] == "idle"

    with db.session(write=True) as conn:
        conn.execute("INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,lease_token,lease_until,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", ("job-stale", "learner-a", "document_analysis", '{"batch_id":"missing"}', "stale-key", "cancelled", None, None, now, now))
        job = conn.execute("SELECT * FROM jobs WHERE id='job-stale'").fetchone()
    from learning_service.app import _process_analysis
    with pytest.raises(APIError) as error:
        _process_analysis(db, job, "old-token")
    assert error.value.code == "STALE_LEASE"


def test_cancelled_import_batch_stops_analysis_and_retains_source(env):
    settings, db, app = env
    image = Image.new("RGB", (2, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    document = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "cancel.png", "image/png"), "paper", None, ctx, db, settings))
    batch = _route(app, "/api/v1/import-batches")(BatchRequest(document_ids=[document["document_id"]]), ctx, db)
    analysis = _route(app, "/api/v1/import-batches/{batch_id}/analysis")(batch["batch_id"], _request({"Idempotency-Key": "cancel-analysis"}), ctx, db)
    cancelled = _route(app, "/api/v1/import-batches/{batch_id}/cancel")(batch["batch_id"], ctx, db)
    assert cancelled["status"] == "cancelled"
    assert analysis["job_id"] in cancelled["cancelled_jobs"]
    assert run_worker_once(db, settings)["status"] == "idle"
    assert _route(app, "/api/v1/import-batches/{batch_id}/analysis")(
        batch["batch_id"], _request({"Idempotency-Key": "cancel-analysis"}), ctx, db
    ) == analysis
    with pytest.raises(APIError, match="已取消批次不能继续分析"):
        _route(app, "/api/v1/import-batches/{batch_id}/analysis")(
            batch["batch_id"], _request({"Idempotency-Key": "cancel-analysis-retry"}), ctx, db
        )
    with pytest.raises(APIError, match="已取消批次不能确认"):
        _route(app, "/api/v1/import-batches/{batch_id}/confirmation-challenges")(
            batch["batch_id"], ChallengeRequest(items=[{"item_id": "missing", "expected_revision": 1}]), ctx, db, settings
        )
    with db.session() as conn:
        assert conn.execute("SELECT status FROM import_batches WHERE id=?", (batch["batch_id"],)).fetchone()[0] == "cancelled"
        assert conn.execute("SELECT status FROM source_documents WHERE id=?", (document["document_id"],)).fetchone()[0] == "stored"
        assert conn.execute("SELECT status FROM source_pages WHERE document_id=?", (document["document_id"],)).fetchone()[0] == "cancelled"


def test_analysis_worker_rejects_stale_batch_revision(env):
    settings, db, app = env
    image = Image.new("RGB", (2, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    document = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "stale.png", "image/png"), "paper", None, ctx, db, settings))
    batch = _route(app, "/api/v1/import-batches")(BatchRequest(document_ids=[document["document_id"]]), ctx, db)
    analysis = _route(app, "/api/v1/import-batches/{batch_id}/analysis")(
        batch["batch_id"], _request({"Idempotency-Key": "stale-analysis"}), ctx, db
    )
    with db.session(write=True) as conn:
        conn.execute("UPDATE import_batches SET revision=revision+1 WHERE id=?", (batch["batch_id"],))
    result = run_worker_once(db, settings)
    assert result == {"status": "failed", "job_id": analysis["job_id"], "error": "STALE_BATCH_REVISION"}
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM import_items WHERE batch_id=?", (batch["batch_id"],)).fetchone()[0] == 0
        row = conn.execute("SELECT status,error_code FROM jobs WHERE id=?", (analysis["job_id"],)).fetchone()
        assert tuple(row) == ("failed", "STALE_BATCH_REVISION")


def test_scheduler_uses_card_timezone_and_0800_local(env):
    settings, db, _ = env
    assert _scheduled_due("2026-11-02T23:30:00+00:00", 1, "Asia/Shanghai") == "2026-11-04T00:00:00+00:00"
    with db.session(write=True) as conn:
        conn.execute("UPDATE learners SET timezone='America/New_York' WHERE id='learner-a'")
        card_id = _ensure_review_card(conn, "learner-a", "obj-1", settings, "2026-11-02T23:30:00+00:00")
        card = conn.execute("SELECT timezone_snapshot,due_at,stage,state FROM review_cards WHERE id=?", (card_id,)).fetchone()
    assert tuple(card) == ("America/New_York", "2026-11-03T13:00:00+00:00", 0, "review")


def test_agent_allowlist_and_step_budget(env):
    _, db, app = env
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    with pytest.raises(APIError) as error:
        _route(app, "/api/v1/agent-runs")(AgentRunRequest(goal="bad", allowed_actions=["approve_grade"]), ctx, db)
    assert error.value.code == "AGENT_ACTION_FORBIDDEN"
    run = _route(app, "/api/v1/agent-runs")(AgentRunRequest(goal="review", allowed_actions=["get_review_tasks"], budget_steps=1), ctx, db)
    first = _route(app, "/api/v1/agent-runs/{run_id}/steps")(run["run_id"], AgentStepRequest(action="get_review_tasks"), ctx, db)
    assert first["status"] == "running"
    with pytest.raises(APIError) as error:
        _route(app, "/api/v1/agent-runs/{run_id}/steps")(run["run_id"], AgentStepRequest(action="get_review_tasks"), ctx, db)
    assert error.value.code == "AGENT_BUDGET_EXCEEDED"


def test_agent_trusted_interaction_is_ui_handoff_only(env):
    _, db, app = env
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    run = _route(app, "/api/v1/agent-runs")(AgentRunRequest(goal="answer", allowed_actions=["start_trusted_interaction"]), ctx, db)
    handoff = _route(app, "/api/v1/agent-runs/{run_id}/steps")(
        run["run_id"],
        AgentStepRequest(action="start_trusted_interaction", input={"operation": "submit_answer", "resource_id": "item-1"}),
        ctx,
        db,
    )
    assert handoff["result"] == {
        "status": "requires_trusted_ui",
        "operation": "submit_answer",
        "resource_id": "item-1",
        "ui_only": True,
    }
    assert "nonce" not in json.dumps(handoff, ensure_ascii=False)
    with pytest.raises(APIError) as error:
        _route(app, "/api/v1/agent-runs/{run_id}/steps")(
            run["run_id"],
            AgentStepRequest(action="start_trusted_interaction", input={"operation": "confirm_import", "resource_id": "batch-1"}),
            ctx,
            db,
        )
    assert error.value.code == "INTERACTION_REQUEST_INVALID"

    alias = _route(app, "/api/v1/agent-runs")(AgentRunRequest(goal="learn", allowed_actions=["start_trusted_interaction"]), ctx, db)
    alias_handoff = _route(app, "/api/v1/agent-runs/{run_id}/steps")(
        alias["run_id"],
        AgentStepRequest(
            action="start_trusted_interaction",
            input={"operation": "confirm_draft_interactively", "resource_id": "draft-1"},
        ),
        ctx,
        db,
    )
    assert alias_handoff["result"] == {
        "status": "requires_trusted_ui",
        "operation": "confirm_draft_interactively",
        "resource_id": "draft-1",
        "ui_only": True,
    }


def test_agent_actions_execute_scoped_reads_and_durable_requests(env):
    settings, db, app = env
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO visual_templates(id,version,template_id,parameter_schema_json,approval,created_at) VALUES (?,?,?,?,?,?)",
            ("agent-template", "1.0.0", "signed_number_subtraction", "{}", "approved", now),
        )
        conn.execute(
            "INSERT INTO mistake_entries(id,learner_id,objective_id,status,diagnosis_status,created_at) VALUES (?,?,?,?,?,?)",
            ("mistake-agent", "learner-a", "obj-1", "active", "draft", now),
        )

    def run(action: str, input_data: dict, budget: int = 8):
        created = _route(app, "/api/v1/agent-runs")(
            AgentRunRequest(goal="agent-test", allowed_actions=[action], budget_steps=budget), ctx, db
        )
        return _route(app, "/api/v1/agent-runs/{run_id}/steps")(
            created["run_id"], AgentStepRequest(action=action, input=input_data), ctx, db
        )

    visual = run("request_visual", {"parameters": {"start": -3, "subtrahend": -5}})
    assert visual["result"]["status"] == "ready"
    assert visual["result"]["spec"]["computed"]["result"] == 2
    mistakes = run("get_mistakes", {})
    assert mistakes["result"]["items"][0]["id"] == "mistake-agent"
    progress = run("get_progress", {})
    assert progress["result"]["learner_id"] == "learner-a"

    diagnosis = run("request_diagnosis", {"mistake_id": "mistake-agent"})
    assert diagnosis["result"]["status"] == "queued"
    diagnosis_job = run_worker_once(db, settings)
    assert diagnosis_job["status"] == "succeeded"
    assert diagnosis_job["result"]["status"] == "needs_review"
    with db.session() as conn:
        assert conn.execute("SELECT diagnosis_status FROM mistake_entries WHERE id='mistake-agent'").fetchone()[0] == "needs_review"
        assert conn.execute("SELECT COUNT(*) FROM diagnoses WHERE mistake_id='mistake-agent'").fetchone()[0] == 1

    variant = run("request_variant", {"objective_id": "obj-1"})
    assert variant["result"]["status"] == "queued"
    variant_job = run_worker_once(db, settings)
    assert variant_job["status"] == "succeeded"
    assert variant_job["result"]["status"] == "needs_review"


def test_agent_document_analysis_action_queues_scoped_batch_and_worker(env):
    settings, db, app = env
    image = Image.new("RGB", (2, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    document = asyncio.run(
        _route(app, "/api/v1/documents")(
            _AsyncUpload(data.getvalue(), "agent-analysis.png", "image/png"),
            "paper",
            None,
            ctx,
            db,
            settings,
        )
    )
    batch = _route(app, "/api/v1/import-batches")(
        BatchRequest(document_ids=[document["document_id"]]), ctx, db
    )
    created = _route(app, "/api/v1/agent-runs")(
        AgentRunRequest(goal="analyze", allowed_actions=["request_document_analysis"]), ctx, db
    )
    queued = _route(app, "/api/v1/agent-runs/{run_id}/steps")(
        created["run_id"],
        AgentStepRequest(
            action="request_document_analysis",
            input={"batch_id": batch["batch_id"]},
        ),
        ctx,
        db,
    )
    assert queued["result"]["status"] == "queued"
    assert queued["result"]["batch_id"] == batch["batch_id"]
    with db.session() as conn:
        job = conn.execute(
            "SELECT kind,learner_id,status,input_json FROM jobs WHERE id=?",
            (queued["result"]["job_id"],),
        ).fetchone()
        assert tuple(job[:3]) == ("document_analysis", "learner-a", "queued")
        assert json.loads(job["input_json"])["revision"] == 1

    processed = run_worker_once(db, settings)
    assert processed["status"] == "succeeded"
    assert processed["result"]["batch_id"] == batch["batch_id"]
    assert processed["result"]["status"] == "awaiting_review"
    items = _route(app, "/api/v1/import-batches/{batch_id}/items")(batch["batch_id"], ctx, db)["items"]
    assert len(items) == 1
    assert items[0]["status"] == "needs_review"


def test_diagnosis_worker_does_not_persist_after_lease_is_stolen(env, monkeypatch):
    settings, db, _ = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO mistake_entries(id,learner_id,objective_id,status,diagnosis_status,created_at) VALUES (?,?,?,?,?,?)",
            ("mistake-stale-diagnosis", "learner-a", "obj-1", "active", "draft", now),
        )
        conn.execute(
            "INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                "job-stale-diagnosis",
                "learner-a",
                "diagnosis",
                '{"mistake_id":"mistake-stale-diagnosis"}',
                "stale-diagnosis-key",
                "queued",
                now,
                now,
            ),
        )

    class LeaseStealingProvider:
        provider_id = "lease-stealing-diagnosis"

        def diagnose(self, evidence):
            with db.session(write=True) as conn:
                conn.execute(
                    "UPDATE jobs SET lease_token='stolen-by-another-worker' WHERE id='job-stale-diagnosis'"
                )
            return ProviderResult(
                provider_id=self.provider_id,
                status="needs_review",
                payload={"knowledge_point_ids": [], "error_types": ["信息不足"]},
                evidence={"mode": "lease-steal-probe"},
            )

    monkeypatch.setattr("learning_service.app.diagnosis_provider", lambda _: LeaseStealingProvider())
    result = run_worker_once(db, settings)
    assert result == {"status": "stale", "job_id": "job-stale-diagnosis", "error": "STALE_LEASE"}
    with db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM diagnoses WHERE mistake_id='mistake-stale-diagnosis'").fetchone()[0] == 0
        assert conn.execute("SELECT diagnosis_status FROM mistake_entries WHERE id='mistake-stale-diagnosis'").fetchone()[0] == "draft"


def test_agent_hint_and_attempt_actions_preserve_service_boundaries(env):
    settings, db, app = env
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?)", ("q-agent", "shared", "approved", "obj-1", now))
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,?,?,?,?,?,?)", ("qv-agent", "q-agent", 1, '{"prompt":"1+1","hint":"先列算式"}', '{"accepted":["2"]}', "exact-text-v1", "approved", now))
    session = _route(app, "/api/v1/test-sessions")(SessionRequest(question_version_id="qv-agent"), ctx, db)
    item_id = session["items"][0]["test_item_id"]

    created = _route(app, "/api/v1/agent-runs")(AgentRunRequest(goal="hint", allowed_actions=["request_hint"]), ctx, db)
    hint = _route(app, "/api/v1/agent-runs/{run_id}/steps")(
        created["run_id"], AgentStepRequest(action="request_hint", input={"test_item_id": item_id}), ctx, db
    )
    assert hint["result"] == {"test_item_id": item_id, "assistance": "hint", "hint": "先列算式"}

    challenge = _route(app, "/api/v1/test-items/{item_id}/submission-challenges")(item_id, ctx, db, settings)
    answer = _route(app, "/api/v1/test-items/{item_id}/answers")(
        item_id,
        AnswerRequest(challenge_id=challenge["challenge_id"], nonce=challenge["nonce"], raw_answer="2"),
        _request({"Idempotency-Key": "agent-attempt"}),
        ctx,
        db,
    )
    created = _route(app, "/api/v1/agent-runs")(AgentRunRequest(goal="attempt", allowed_actions=["get_attempt"]), ctx, db)
    attempt = _route(app, "/api/v1/agent-runs/{run_id}/steps")(
        created["run_id"], AgentStepRequest(action="get_attempt", input={"attempt_id": answer["attempt_id"]}), ctx, db
    )
    assert attempt["result"]["id"] == answer["attempt_id"]
    assert attempt["result"]["assessment_eligibility"] == 0


def test_page_revision_can_requeue_analysis_with_a_new_revision_item(env):
    settings, db, app = env
    image = Image.new("RGB", (2, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    document = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "revision.png", "image/png"), "paper", None, ctx, db, settings))
    batch = _route(app, "/api/v1/import-batches")(BatchRequest(document_ids=[document["document_id"]]), ctx, db)
    first_request = _route(app, "/api/v1/import-batches/{batch_id}/analysis")(
        batch["batch_id"], _request({"Idempotency-Key": "revision-one"}), ctx, db
    )
    assert run_worker_once(db, settings)["status"] == "succeeded"
    with db.session() as conn:
        first_item = conn.execute("SELECT id FROM import_items WHERE batch_id=?", (batch["batch_id"],)).fetchone()[0]
        page = conn.execute("SELECT id,asset_id FROM source_pages WHERE document_id=?", (document["document_id"],)).fetchone()
    edited = _route(app, "/api/v1/documents/{document_id}/pages")(
        document["document_id"],
        PagePatch(expected_revision=1, pages=[{"page_id": page["id"], "page_index": 0, "asset_id": page["asset_id"], "rotation": 90}]),
        ctx,
        db,
    )
    assert edited["revision"] == 2
    second_request = _route(app, "/api/v1/import-batches/{batch_id}/analysis")(
        batch["batch_id"], _request({"Idempotency-Key": "revision-two"}), ctx, db
    )
    with db.session() as conn:
        queued = conn.execute("SELECT input_json,status FROM jobs WHERE id=?", (second_request["job_id"],)).fetchone()
        assert json.loads(queued["input_json"])["revision"] == 2
        assert queued["status"] == "queued"
    processed = run_worker_once(db, settings)
    assert processed["status"] == "succeeded"
    with db.session() as conn:
        items = conn.execute("SELECT id,occurrence_id,status FROM import_items WHERE batch_id=? ORDER BY id", (batch["batch_id"],)).fetchall()
    assert len(items) == 2
    assert first_item not in {row["id"] for row in items if row["status"] != "stale"}
    assert any(row["status"] == "stale" for row in items)
    assert any(row["status"] == "needs_review" and row["occurrence_id"].endswith(":2") for row in items)


def test_upload_rejects_learner_path_traversal_and_deleted_documents_cannot_form_batch(env):
    settings, db, app = env
    now = utc_now()
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO learners(id,display_name,timezone,curriculum_id,created_at) VALUES (?,?,?,?,?)", ("../outside", "Bad", "Asia/Shanghai", "math-g7-v1", now))
        conn.execute("INSERT INTO learner_access(account_id,learner_id,role,created_at) VALUES (?,?,?,?)", ("acct-a", "../outside", "admin", now))
    bad_ctx = Context(account_id="acct-a", learner_id="../outside", role="admin")
    image = Image.new("RGB", (2, 2), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    with pytest.raises(APIError) as traversal:
        asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "safe.png", "image/png"), "paper", None, bad_ctx, db, settings))
    assert traversal.value.code == "INVALID_STORAGE_ID"
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    document = asyncio.run(_route(app, "/api/v1/documents")(_AsyncUpload(data.getvalue(), "deleted.png", "image/png"), "paper", None, ctx, db, settings))
    with db.session(write=True) as conn:
        conn.execute("UPDATE source_documents SET status='deleted' WHERE id=?", (document["document_id"],))
    with pytest.raises(APIError) as deleted:
        _route(app, "/api/v1/import-batches")(BatchRequest(document_ids=[document["document_id"]]), ctx, db)
    assert deleted.value.code == "DOCUMENT_NOT_FOUND"


def test_agent_budget_is_cumulative_across_steps(env, monkeypatch):
    _, db, app = env
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    elapsed = iter((0, 50, 101))
    monkeypatch.setattr("learning_service.app._elapsed_budget_ms", lambda _started_at: next(elapsed))
    run = _route(app, "/api/v1/agent-runs")(
        AgentRunRequest(goal="budget", allowed_actions=["get_review_tasks"], budget_steps=3, budget_ms=100), ctx, db
    )
    first = _route(app, "/api/v1/agent-runs/{run_id}/steps")(
        run["run_id"], AgentStepRequest(action="get_review_tasks"), ctx, db
    )
    assert first["status"] == "running"
    second = _route(app, "/api/v1/agent-runs/{run_id}/steps")(
        run["run_id"], AgentStepRequest(action="get_review_tasks"), ctx, db
    )
    assert second["status"] == "stopped"
    assert second["stop_reason"] == "time_budget"
    with db.session() as conn:
        assert tuple(conn.execute("SELECT status,stop_reason FROM agent_runs WHERE id=?", (run["run_id"],)).fetchone()) == ("stopped", "time_budget")


def test_variant_source_is_approved_scoped_and_objective_consistent(env):
    _, db, app = env
    now = utc_now()
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO questions(id,learner_id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?,?)", ("q-approved", None, "shared", "approved", "obj-1", now))
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,?,?,?,?,?,?)", ("qv-approved", "q-approved", 1, '{}', '{}', "exact-text-v1", "approved", now))
        conn.execute("INSERT INTO questions(id,learner_id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?,?)", ("q-draft", None, "shared", "draft", "obj-1", now))
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,?,?,?,?,?,?)", ("qv-draft", "q-draft", 1, '{}', '{}', "exact-text-v1", "approved", now))
    endpoint = _route(app, "/api/v1/variant-jobs")
    queued = endpoint({"objective_id": "obj-1", "source_question_version_id": "qv-approved"}, ctx, db)
    assert queued["status"] == "queued"
    with pytest.raises(APIError) as draft:
        endpoint({"objective_id": "obj-1", "source_question_version_id": "qv-draft"}, ctx, db)
    assert draft.value.code == "SOURCE_QUESTION_NOT_APPROVED"
    with pytest.raises(APIError) as missing:
        endpoint({"objective_id": "obj-1", "source_question_version_id": "missing"}, ctx, db)
    assert missing.value.code == "SOURCE_QUESTION_NOT_FOUND"


def test_objective_scope_requires_matching_curriculum(env):
    _, db, app = env
    now = utc_now()
    ctx = Context(account_id="acct-a", learner_id="learner-a", role="admin")
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO knowledge_points(id,curriculum_id,code,title,created_at) VALUES (?,?,?,?,?)", ("kp-other", "science-g8-v1", "matter", "物质", now))
        conn.execute("INSERT INTO review_objectives(id,knowledge_point_id,code,title,created_at) VALUES (?,?,?,?,?)", ("obj-other", "kp-other", "atoms", "原子", now))
    with pytest.raises(APIError) as draft:
        _route(app, "/api/v1/learning-drafts")(DraftRequest(objective_id="obj-other", content={}), ctx, db)
    assert draft.value.code == "OBJECTIVE_SCOPE_MISMATCH"
    with pytest.raises(APIError) as visual:
        _route(app, "/api/v1/visual-jobs")(__import__("learning_service.app", fromlist=["VisualJobRequest"]).VisualJobRequest(template_id="signed_number_subtraction", parameters={"start": 1, "subtrahend": 1}, objective_id="obj-other"), ctx, db)
    assert visual.value.code == "OBJECTIVE_SCOPE_MISMATCH"
