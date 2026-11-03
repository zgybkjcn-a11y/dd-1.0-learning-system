from __future__ import annotations

import hashlib
import html
import json
import mimetypes
import secrets
import shutil
import sqlite3
from datetime import datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from .config import Settings
from .db import Database, json_dumps, json_loads, new_id, utc_now
from .providers import diagnosis_provider, document_provider, variant_provider


INTERVALS = [1, 2, 4, 7, 15, 30]
DEFAULT_TIMEZONE = "Asia/Shanghai"
ALLOWED_AGENT_ACTIONS = {
    "list_learners", "get_review_tasks", "get_mistakes", "request_document_analysis",
    "request_diagnosis", "request_variant", "request_hint", "request_visual",
    "get_attempt", "get_progress", "start_trusted_interaction",
}
FORBIDDEN_AGENT_ACTIONS = {
    "confirm_import", "submit_answer", "approve_grade", "change_stage",
    "change_role", "export_data", "delete_data",
}


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, retryable: bool = False, details: Any = None):
        self.status = status
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details


class Context(BaseModel):
    account_id: str
    learner_id: str | None = None
    role: str = "student"
    provider: str = "local"


class BootstrapRequest(BaseModel):
    provider: str = "local"
    issuer: str = "learning-dev"
    subject: str
    display_name: str
    timezone: str = "Asia/Shanghai"
    learner_id: str | None = None
    account_id: str | None = None
    role: str = "student"


class BatchRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1, max_length=20)
    answer_document_id: str | None = None


class ItemPatch(BaseModel):
    expected_revision: int
    raw_answer: str | None = None
    content: dict[str, Any] | None = None
    verdict: str | None = None
    evidence: dict[str, Any] | None = None
    objective_id: str | None = None


class PagePatch(BaseModel):
    """Complete replacement for a document's ordered page projection.

    The original uploaded document asset is immutable.  ``asset_id`` may point
    only at an existing, non-deleted page asset owned by the same learner; a
    replacement upload remains a separate document upload operation.
    """

    expected_revision: int = Field(ge=1)
    pages: list[dict[str, Any]] = Field(min_length=1, max_length=500)


class ReviewRequestRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    details: dict[str, Any] = Field(default_factory=dict)


class ReviewDecisionRequest(BaseModel):
    decision: str = Field(min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=2000)


class ChallengeRequest(BaseModel):
    items: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    expected_batch_revision: int | None = Field(default=None, ge=1)


class ConfirmationRequest(BaseModel):
    challenge_id: str
    nonce: str
    items: list[dict[str, Any]] = Field(min_length=1, max_length=100)


class DraftRequest(BaseModel):
    objective_id: str
    content: dict[str, Any] = Field(default_factory=dict)


class DraftConfirmation(BaseModel):
    challenge_id: str
    nonce: str
    # Optional client echo. The persisted draft remains the server-side source of truth.
    raw_content: dict[str, Any] | None = None


class TestSessionRequest(BaseModel):
    question_version_id: str
    mode: str = "independent"
    card_id: str | None = None


class AnswerRequest(BaseModel):
    challenge_id: str
    nonce: str
    raw_answer: str = Field(min_length=1, max_length=10000)


class DiagnosisRequest(BaseModel):
    model_id: str = "mock-diagnosis-v1"
    prompt_version: str = "diagnose-v1"


class VisualJobRequest(BaseModel):
    template_id: str
    template_version: str = "1.0.0"
    objective_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    purpose: str = "teach"


class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=500)
    allowed_actions: list[str] = Field(default_factory=lambda: ["get_review_tasks"])
    budget_steps: int = Field(default=8, ge=1, le=32)
    budget_ms: int = Field(default=15000, ge=100, le=120000)


class AgentStepRequest(BaseModel):
    action: str
    input: dict[str, Any] = Field(default_factory=dict)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _elapsed_budget_ms(started_at: str) -> int:
    """Compute durable wall-clock budget consumption across requests/processes."""
    try:
        started = _parse_iso(started_at)
    except (TypeError, ValueError):
        return 0
    return max(0, int((datetime.now(timezone.utc) - started).total_seconds() * 1000))


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _request_hash(value: Any) -> str:
    return _hash(json_dumps(value))


def _normalize_answer(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise APIError(422, "INVALID_TIMEZONE", "学习者时区不支持")


def _scheduled_due(accepted_at: str, days: int, timezone_name: str) -> str:
    """Return the next due instant at 08:00 in the card's timezone."""
    zone = _zone(timezone_name)
    local_date = _parse_iso(accepted_at).astimezone(zone).date() + timedelta(days=days)
    due_local = datetime.combine(local_date, datetime_time(8, 0), tzinfo=zone)
    return due_local.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _natural_day(value: str | datetime | None, timezone_name: str) -> Any:
    """Convert a stored instant to the card's local calendar day."""
    if not value:
        return None
    parsed = value if isinstance(value, datetime) else _parse_iso(str(value))
    return parsed.astimezone(_zone(timezone_name)).date()


def _maintenance_gate(
    conn: sqlite3.Connection,
    card: sqlite3.Row,
    current_attempt: sqlite3.Row,
    current_outcome: str,
) -> dict[str, Any]:
    """Evaluate the evidence required before a stage-five card enters maintenance."""
    timezone_name = card["timezone_snapshot"] or DEFAULT_TIMEZONE
    objective_id = card["objective_id"]
    submitted_at = current_attempt["submitted_at"]
    current_day = _natural_day(submitted_at, timezone_name)
    passed_days: set[Any] = set()
    approved_variants: set[str] = set()

    history = conn.execute(
        """
        SELECT a.id, a.submitted_at, a.assistance AS attempt_assistance,
               ti.id AS item_id, ti.assistance AS item_assistance,
               ts.mode AS session_mode,
               qv.id AS question_version_id, qv.variant_kind, qv.variant_group,
               q.approval AS question_approval, qv.approval AS version_approval,
               gv.outcome
        FROM attempts a
        JOIN test_items ti ON ti.id=a.test_item_id
        JOIN test_sessions ts ON ts.id=ti.session_id
        JOIN question_versions qv ON qv.id=ti.question_version_id
        JOIN questions q ON q.id=qv.question_id
        JOIN grade_versions gv ON gv.attempt_id=a.id
        WHERE a.learner_id=? AND q.objective_id=? AND a.id<>?
          AND a.submitted_at<? AND a.assessment_eligibility=1
          AND a.assistance='none' AND ti.assistance='none'
          AND ts.mode='independent' AND gv.outcome='correct' AND q.approval='approved'
          AND qv.approval='approved'
        """,
        (current_attempt["learner_id"], objective_id, current_attempt["id"], submitted_at),
    ).fetchall()
    for event in history:
        day = _natural_day(event["submitted_at"], timezone_name)
        if day is not None:
            passed_days.add(day)
        if event["variant_kind"] != "base":
            approved_variants.add(event["variant_group"] or event["question_version_id"])

    if (
        current_outcome == "correct"
        and current_attempt["assessment_eligibility"]
        and current_attempt["assistance"] == "none"
        and current_attempt["item_assistance"] == "none"
        and current_attempt["question_approval"] == "approved"
        and current_attempt["version_approval"] == "approved"
        and current_attempt["session_mode"] == "independent"
    ):
        if current_day is not None:
            passed_days.add(current_day)
        if current_attempt["variant_kind"] != "base":
            approved_variants.add(current_attempt["variant_group"] or current_attempt["question_version_id"])

    exposures: list[Any] = []
    exposure_events = conn.execute(
        """
        SELECT accepted_at FROM learning_events
        WHERE learner_id=? AND objective_id=? AND accepted_at<?
        """,
        (current_attempt["learner_id"], objective_id, submitted_at),
    ).fetchall()
    exposures.extend(row["accepted_at"] for row in exposure_events)
    practice_exposures = conn.execute(
        """
        SELECT ti.presented_at
        FROM test_items ti
        JOIN question_versions qv ON qv.id=ti.question_version_id
        JOIN questions q ON q.id=qv.question_id
        WHERE ti.learner_id=? AND q.objective_id=? AND ti.id<>?
          AND ti.presented_at IS NOT NULL AND ti.presented_at<?
        """,
        (current_attempt["learner_id"], objective_id, current_attempt["test_item_id"], submitted_at),
    ).fetchall()
    exposures.extend(row["presented_at"] for row in practice_exposures)
    media_exposures = conn.execute(
        """
        SELECT COALESCE(observed_at, issued_at) AS exposed_at
        FROM media_events
        WHERE learner_id=? AND objective_id=? AND COALESCE(observed_at, issued_at)<?
        """,
        (current_attempt["learner_id"], objective_id, submitted_at),
    ).fetchall()
    exposures.extend(row["exposed_at"] for row in media_exposures)
    if card["last_exposure_at"] and card["last_exposure_at"] < submitted_at:
        exposures.append(card["last_exposure_at"])

    exposure_days = sorted(
        {day for value in exposures if (day := _natural_day(value, timezone_name)) is not None}
    )
    last_exposure_day = exposure_days[-1] if exposure_days else None
    exposure_gap_days = (current_day - last_exposure_day).days if current_day and last_exposure_day else None
    due = _parse_iso(submitted_at) >= _parse_iso(card["due_at"])
    eligible = bool(
        card["stage"] == 5
        and card["state"] == "review"
        and due
        and len(passed_days) >= 3
        and len(approved_variants) >= 2
        and exposure_gap_days is not None
        and exposure_gap_days >= 30
        and current_attempt["session_mode"] == "independent"
    )
    return {
        "eligible": eligible,
        "due": due,
        "passed_natural_days": len(passed_days),
        "passed_days": [day.isoformat() for day in sorted(passed_days)],
        "approved_variant_count": len(approved_variants),
        "approved_variants": sorted(approved_variants),
        "last_exposure_day": last_exposure_day.isoformat() if last_exposure_day else None,
        "exposure_gap_days": exposure_gap_days,
        "exposure_days": [day.isoformat() for day in exposure_days],
    }


def _safe_filename(name: str) -> str:
    name = Path(name or "upload.bin").name
    return "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in name)[:120] or "upload.bin"


def _contained_path(root: Path, object_key: str) -> Path:
    """Resolve a stored key under its managed root, rejecting traversal."""
    root = root.resolve()
    target = (root / object_key).resolve()
    if target == root or root not in target.parents:
        raise APIError(500, "INVALID_OBJECT_KEY", "存储对象路径无效")
    return target


def _storage_component(value: str, label: str) -> str:
    """Validate a generated storage path component before joining it."""
    if not isinstance(value, str) or not value or value in {".", ".."} or "/" in value or "\\" in value or "\x00" in value:
        raise APIError(422, "INVALID_STORAGE_ID", f"{label} 不能用于存储路径")
    return value


def _page_count(data: bytes, media_type: str) -> tuple[int, str | None]:
    if media_type != "application/pdf":
        try:
            from PIL import Image  # type: ignore
            from io import BytesIO
            with Image.open(BytesIO(data)) as image:
                image.verify()
            return 1, None
        except Exception:
            return 1, "IMAGE_DECODE_FAILED"
    try:
        import fitz  # type: ignore
        doc = fitz.open(stream=data, filetype="pdf")
        count = len(doc)
        doc.close()
        return count, None
    except Exception:
        # A PDF-shaped upload is retained for review, but its page cannot be silently marked processed.
        return 1, "PDF_DECODE_FAILED"


def _render_pdf_pages(data: bytes, attachment_dir: Path, learner_id: str, asset_id: str) -> list[dict[str, Any]]:
    """Render each PDF page into a private derivative for page-level review."""
    import fitz  # type: ignore

    pages: list[dict[str, Any]] = []
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        for index in range(len(doc)):
            object_key = f"{_storage_component(learner_id, 'learner_id')}/{_storage_component(asset_id, 'asset_id')}/page-{index + 1}.png"
            target = _contained_path(attachment_dir, object_key)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".tmp")
            try:
                pixmap = doc[index].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                tmp.write_bytes(pixmap.tobytes("png"))
                tmp.replace(target)
                pages.append({"object_key": object_key, "media_type": "image/png", "byte_size": target.stat().st_size, "width": pixmap.width, "height": pixmap.height, "failure_code": None})
            except Exception:  # noqa: BLE001 - preserve a visible per-page failure.
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
                pages.append({"object_key": None, "media_type": "image/png", "byte_size": 0, "width": None, "height": None, "failure_code": "PDF_PAGE_RENDER_FAILED"})
    finally:
        doc.close()
    return pages


def _ensure_review_card(conn: sqlite3.Connection, learner_id: str, objective_id: str, settings: Settings, accepted_at: str | None = None) -> str:
    row = conn.execute("SELECT id FROM review_cards WHERE learner_id=? AND objective_id=?", (learner_id, objective_id)).fetchone()
    if row:
        return row["id"]
    objective = conn.execute(
        "SELECT o.knowledge_point_id,k.curriculum_id,l.curriculum_id AS learner_curriculum "
        "FROM review_objectives o JOIN knowledge_points k ON k.id=o.knowledge_point_id "
        "JOIN learners l ON l.id=? WHERE o.id=?",
        (learner_id, objective_id),
    ).fetchone()
    if not objective:
        raise APIError(404, "OBJECTIVE_NOT_FOUND", "目标不存在")
    if objective["curriculum_id"] != objective["learner_curriculum"]:
        raise APIError(403, "OBJECTIVE_SCOPE_MISMATCH", "目标不属于当前学习者课程")
    learner = conn.execute("SELECT timezone FROM learners WHERE id=?", (learner_id,)).fetchone()
    timezone_name = learner["timezone"] if learner and learner["timezone"] else DEFAULT_TIMEZONE
    now = accepted_at or utc_now()
    due = _scheduled_due(now, 1, timezone_name)
    card_id = new_id("card")
    conn.execute(
        "INSERT INTO review_cards(id,learner_id,knowledge_point_id,objective_id,state,stage,due_at,timezone_snapshot,scheduler_version,revision,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (card_id, learner_id, objective["knowledge_point_id"], objective_id, "review", 0, due, timezone_name, settings.scheduler_version, 1, now, now),
    )
    return card_id


def _export_rows(conn: sqlite3.Connection, table: str, learner_id: str, column: str = "learner_id") -> list[dict[str, Any]]:
    """Return learner-scoped rows without exporting credentials or raw secrets."""
    rows = conn.execute(f"SELECT * FROM {table} WHERE {column}=?", (learner_id,)).fetchall()
    return [dict(row) for row in rows]


def _learner_export(conn: sqlite3.Connection, learner_id: str, account_id: str, export_id: str) -> dict[str, Any]:
    learner = conn.execute("SELECT id,display_name,timezone,curriculum_id,active,created_at FROM learners WHERE id=?", (learner_id,)).fetchone()
    if not learner:
        raise APIError(404, "LEARNER_NOT_FOUND", "学习者不存在")
    documents = _export_rows(conn, "source_documents", learner_id)
    document_ids = [row["id"] for row in documents]
    pages: list[dict[str, Any]] = []
    if document_ids:
        placeholders = ",".join("?" * len(document_ids))
        pages = [dict(row) for row in conn.execute(f"SELECT * FROM source_pages WHERE document_id IN ({placeholders}) ORDER BY document_id,page_index", document_ids).fetchall()]
    batches = _export_rows(conn, "import_batches", learner_id)
    items = _export_rows(conn, "import_items", learner_id)
    judgments = []
    if items:
        ids = [row["id"] for row in items]
        placeholders = ",".join("?" * len(ids))
        judgments = [dict(row) for row in conn.execute(f"SELECT * FROM import_judgments WHERE item_id IN ({placeholders}) ORDER BY created_at", ids).fetchall()]
    mistakes = _export_rows(conn, "mistake_entries", learner_id)
    mistake_ids = [row["id"] for row in mistakes]
    sources = _export_rows(conn, "mistake_sources", learner_id)
    diagnoses = []
    if mistake_ids:
        placeholders = ",".join("?" * len(mistake_ids))
        diagnoses = [dict(row) for row in conn.execute(f"SELECT * FROM diagnoses WHERE mistake_id IN ({placeholders}) ORDER BY created_at", mistake_ids).fetchall()]
    export = {
        "format": "dd-learning-export-v1",
        "export_id": export_id,
        "created_at": utc_now(),
        "requested_by_account_id": account_id,
        "learner": dict(learner),
        "documents": documents,
        "source_pages": pages,
        "import_batches": batches,
        "import_items": items,
        "import_judgments": judgments,
        "mistakes": mistakes,
        "mistake_sources": sources,
        "diagnoses": diagnoses,
        "learning_drafts": _export_rows(conn, "learning_drafts", learner_id),
        "learning_events": _export_rows(conn, "learning_events", learner_id),
        "review_cards": _export_rows(conn, "review_cards", learner_id),
        "test_sessions": _export_rows(conn, "test_sessions", learner_id),
        "test_items": _export_rows(conn, "test_items", learner_id),
        "attempts": _export_rows(conn, "attempts", learner_id),
        "review_requests": _export_rows(conn, "review_requests", learner_id),
        "audit_events": _export_rows(conn, "audit_events", learner_id),
    }
    # Assets are metadata only; the artifact never contains file bytes or secrets.
    export["assets"] = _export_rows(conn, "assets", learner_id)
    return export


_UI_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <link rel="icon" href="data:,">
  <title>DD-1.0 学习工作区</title>
  <style>
    :root { color-scheme: light; font: 16px/1.45 system-ui, sans-serif; }
    *, *::before, *::after { box-sizing: border-box; }
    body { max-width: 1120px; margin: 0 auto; padding: 1rem; color: #17202a; background: #f7f9fb; }
    header, section { min-width: 0; background: white; border: 1px solid #d7dde5; border-radius: 6px; padding: 1rem; margin: 0 0 1rem; }
    h1, h2 { margin: 0 0 .65rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }
    label { min-width: 0; display: grid; gap: .25rem; margin: .5rem 0; }
    input, select, textarea, button { min-width: 0; max-width: 100%; font: inherit; padding: .5rem; border: 1px solid #aeb8c4; border-radius: 4px; }
    button { cursor: pointer; background: #164e63; color: white; border-color: #164e63; }
    button.secondary { background: white; color: #164e63; }
    button:disabled { cursor: wait; opacity: .55; }
    .row { display: flex; flex-wrap: wrap; gap: .5rem; align-items: end; }
    .row > * { min-width: 0; flex: 1 1 12rem; }
    .status { min-height: 1.5rem; white-space: pre-wrap; overflow-wrap: anywhere; word-break: break-word; }
    table { width: 100%; border-collapse: collapse; margin-top: .75rem; }
    th, td { text-align: left; vertical-align: top; border-top: 1px solid #e3e7ec; padding: .55rem .35rem; }
    code, pre { white-space: pre-wrap; overflow-wrap: anywhere; }
    .muted { color: #536273; }
    .document-list, .review-list { display: grid; gap: .75rem; margin-top: .75rem; }
    .document-row, .review-card { min-width: 0; border: 1px solid #d7dde5; border-radius: 5px; padding: .75rem; background: #fff; }
    .document-row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: .5rem; align-items: center; }
    .document-row > * { min-width: 0; }
    .document-row div { overflow-wrap: anywhere; word-break: break-word; }
    .document-row label { display: flex; align-items: center; gap: .5rem; margin: 0; }
    .review-card h3 { margin: 0 0 .5rem; font-size: 1.05rem; }
    .review-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: .75rem; align-items: start; }
    .source-preview { min-width: 0; border: 1px solid #d7dde5; background: #f2f5f7; padding: .5rem; }
    .source-preview img { display: block; width: 100%; max-height: 70vh; object-fit: contain; }
    .source-preview figcaption { overflow-wrap: anywhere; color: #536273; font-size: .9rem; }
    .page-summary { padding: .5rem; background: #f2f5f7; overflow-wrap: anywhere; }
    .review-fields { min-width: 0; }
    .review-fields textarea { width: 100%; }
    @media (max-width: 640px) {
      body { width: 100%; padding: .5rem; }
      header, section { padding: .75rem; }
      .row { align-items: stretch; }
      .row > * { flex-basis: 100%; }
      .review-grid { grid-template-columns: minmax(0, 1fr); }
      .document-row { grid-template-columns: auto minmax(0, 1fr); }
      .document-row > button { grid-column: 2; }
    }
  </style>
</head>
<body>
  <header>
    <h1>DD-1.0 学习工作区</h1>
    <p class="muted">服务端状态、原始资料和可信确认保持分离。刷新页面后可继续查看同一批次。</p>
    <div class="grid">
      <label>账号 ID <input id="account" autocomplete="off" placeholder="开发模式账号"></label>
      <label>学习者 ID <input id="learner" autocomplete="off" placeholder="当前学习者"></label>
    </div>
    <div class="row"><button id="loadLearners" class="secondary">读取学习者</button><button id="loadHealth" class="secondary">读取服务状态</button></div>
  </header>
  <main>
    <section>
      <h2>上传与分析</h2>
      <div class="row">
        <label>资料类型 <select id="kind"><option value="paper">试卷</option><option value="homework">作业</option><option value="answer_key">参考答案</option></select></label>
        <label>文件（可多选照片，PDF 按整卷上传） <input id="file" type="file" accept="application/pdf,image/png,image/jpeg" multiple></label>
        <button id="upload">上传资料</button>
      </div>
      <div id="documents" class="document-list muted">尚未上传资料。</div>
      <div class="row"><label>当前文档 ID <input id="document" readonly></label><label>参考答案资料（可选） <select id="answerDocument"><option value="">不关联</option></select></label><button id="makeBatch" class="secondary">创建整卷批次</button><button id="analyze" class="secondary">请求分析</button><button id="cancelBatch" class="secondary">取消批次</button></div>
      <p id="uploadStatus" class="status" role="status"></p>
    </section>
    <section>
      <h2>候选复核与确认</h2>
      <div class="row"><label>批次 ID <input id="batch" autocomplete="off"></label><button id="refreshItems" class="secondary">读取页状态与候选</button><button id="confirm" disabled>确认选中项</button></div>
      <div id="pageSummary" class="page-summary muted">尚未读取批次页面。</div>
      <div id="items" class="status muted">尚未读取候选。</div>
    </section>
    <section>
      <h2>错题、诊断与复习</h2>
      <div class="row"><button id="loadMistakes" class="secondary">读取错题本</button><button id="loadReview" class="secondary">读取到期复习</button></div>
      <div class="row"><label>错题 ID <input id="mistake" autocomplete="off"></label><button id="diagnose" class="secondary">请求待复核诊断</button></div>
      <div id="mistakes" class="status muted">尚未读取错题。</div>
    </section>
    <section>
      <h2>独立变式测验</h2>
      <p class="muted">输入已审核题目版本；题目答案只在服务端判分。</p>
      <div class="row"><label>题目版本 ID <input id="questionVersion" autocomplete="off"></label><label>复习卡 ID（可选） <input id="card" autocomplete="off"></label><button id="startTest">开始测验</button></div>
      <div class="row"><label>测验会话 ID <input id="session" autocomplete="off"></label><label>作答项 ID <input id="testItem" autocomplete="off"></label><label>Attempt ID <input id="attempt" autocomplete="off"></label></div>
      <div class="row"><button id="restoreTest" class="secondary">恢复测验</button><button id="refreshTest" class="secondary">读取状态</button><button id="requestHint" class="secondary">请求提示</button><button id="cancelTest" class="secondary">取消测验</button></div>
      <div id="testPrompt" class="status muted">题面将在开始或恢复测验后显示。</div>
      <div class="row"><label>原始作答 <input id="answer" autocomplete="off"></label><button id="submitAnswer" class="secondary">提交并等待判分</button><button id="refreshAttempt" class="secondary">读取判分</button><button id="requestReview" class="secondary">申请复核</button></div>
      <div id="testStatus" class="status muted">尚未开始测验。</div>
    </section>
    <section>
      <h2>结果</h2>
      <pre id="output" class="status" aria-live="polite">等待操作。</pre>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const saved = JSON.parse(localStorage.getItem('dd-learning-context') || '{}');
    let savedTest = JSON.parse(localStorage.getItem('dd-learning-test') || '{}');
    let uploadedDocuments = [];
    let sourceObjectUrls = [];
    let sourceRenderGeneration = 0;
    let importRefreshGeneration = 0;
    $('account').value = saved.account || '';
    $('learner').value = saved.learner || '';
    const importStateKey = () => 'dd-learning-import:' + encodeURIComponent($('account').value.trim()) + ':' + encodeURIComponent($('learner').value.trim());
    function saveImportState() {
      const state = {documents: uploadedDocuments, batchId: $('batch').value.trim()};
      localStorage.setItem(importStateKey(), JSON.stringify(state));
    }
    function restoreImportState() {
      importRefreshGeneration += 1;
      releaseSourceObjectUrls();
      $('batch').value = ''; $('document').value = '';
      $('pageSummary').textContent = '尚未读取批次页面。';
      $('items').textContent = '尚未读取候选。';
      $('items').className = 'status muted';
      $('confirm').disabled = true;
      try {
        const state = JSON.parse(localStorage.getItem(importStateKey()) || '{}');
        uploadedDocuments = Array.isArray(state.documents) ? state.documents.filter((doc) => doc && doc.document_id) : [];
        if (state.batchId) $('batch').value = state.batchId;
      } catch (_) { uploadedDocuments = []; }
      renderDocuments();
    }
    if (savedTest.questionVersionId) $('questionVersion').value = savedTest.questionVersionId;
    if (savedTest.cardId) $('card').value = savedTest.cardId;
    if (savedTest.sessionId) $('session').value = savedTest.sessionId;
    if (savedTest.testItemId) $('testItem').value = savedTest.testItemId;
    if (savedTest.attemptId) $('attempt').value = savedTest.attemptId;
    function contextHeaders() {
      const account = $('account').value.trim(), learner = $('learner').value.trim();
      localStorage.setItem('dd-learning-context', JSON.stringify({account, learner}));
      const h = {'Accept': 'application/json'};
      if (account) h['X-Account-Id'] = account;
      if (learner) h['X-Learner-Id'] = learner;
      return h;
    }
    async function call(path, options = {}) {
      options.headers = Object.assign(contextHeaders(), options.headers || {});
      const response = await fetch(path, options);
      const text = await response.text();
      let data; try { data = JSON.parse(text); } catch (_) { data = text; }
      if (!response.ok) throw new Error(typeof data === 'string' ? data : (data.error?.message || JSON.stringify(data)));
      return data;
    }
    function show(value) { $('output').textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2); }
    function setStatus(value) { $('uploadStatus').textContent = typeof value === 'string' ? value : JSON.stringify(value); }
    function testStatus(value) { $('testStatus').textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2); }
    function renderDocuments() {
      const container = $('documents'); container.replaceChildren();
      const answerSelect = $('answerDocument');
      const currentAnswer = answerSelect.value;
      answerSelect.replaceChildren(new Option('不关联', ''));
      uploadedDocuments.filter((doc) => doc.kind === 'answer_key').forEach((doc) => answerSelect.add(new Option(`${doc.filename} · ${doc.page_count} 页`, doc.document_id)));
      if (uploadedDocuments.some((doc) => doc.document_id === currentAnswer && doc.kind === 'answer_key')) answerSelect.value = currentAnswer;
      if (!uploadedDocuments.length) { container.textContent = '尚未上传资料。'; return; }
      uploadedDocuments.forEach((doc) => {
        const row = document.createElement('div'); row.className = 'document-row';
        const label = document.createElement('label');
        const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.dataset.document = doc.document_id;
        checkbox.checked = doc.kind !== 'answer_key' && doc.selected !== false;
        checkbox.disabled = doc.kind === 'answer_key';
        checkbox.onchange = () => { doc.selected = checkbox.checked; saveImportState(); };
        label.append(checkbox, document.createTextNode(doc.kind === 'answer_key' ? '参考答案' : '加入批次'));
        const info = document.createElement('div');
        const title = document.createElement('strong'); title.textContent = doc.filename || doc.document_id;
        const detail = document.createElement('div'); detail.className = 'muted'; detail.textContent = `${doc.kind} · ${doc.page_count} 页 · ${doc.document_id}`;
        info.append(title, detail);
        const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'secondary'; remove.textContent = '从工作区移除';
        remove.onclick = () => { uploadedDocuments = uploadedDocuments.filter((entry) => entry.document_id !== doc.document_id); if ($('document').value === doc.document_id) $('document').value = ''; renderDocuments(); saveImportState(); };
        row.append(label, info, remove); container.append(row);
      });
      saveImportState();
    }
    function releaseSourceObjectUrls() {
      sourceRenderGeneration += 1;
      sourceObjectUrls.forEach((url) => URL.revokeObjectURL(url)); sourceObjectUrls = [];
    }
    async function renderSourcePreview(item, target, generation = sourceRenderGeneration) {
      const pageId = item.source_page_id;
      if (!pageId) { target.textContent = '候选没有来源页关联，不能确认来源。'; return; }
      try {
        const response = await fetch('/api/v1/source-pages/' + encodeURIComponent(pageId) + '/content', {headers: contextHeaders()});
        if (!response.ok) throw new Error(response.status === 404 ? '原页不可用或无权访问' : `原页读取失败（HTTP ${response.status}）`);
        const blob = await response.blob(); const url = URL.createObjectURL(blob);
        if (generation !== sourceRenderGeneration) { URL.revokeObjectURL(url); return; }
        sourceObjectUrls.push(url);
        const image = document.createElement('img'); image.src = url; image.alt = `来源原卷，第 ${Number(item.page_index) + 1} 页`;
        const caption = document.createElement('figcaption'); caption.textContent = `原卷第 ${Number(item.page_index) + 1} 页 · ${item.locator || '未分题'} · ${pageId}`;
        target.replaceChildren(image, caption);
      } catch (error) { target.textContent = error.message; }
    }
    function saveTestState(extra = {}) {
      const state = Object.assign({
        account: savedTest.account || $('account').value.trim(), learner: savedTest.learner || $('learner').value.trim(),
        questionVersionId: $('questionVersion').value.trim(), cardId: $('card').value.trim(),
        sessionId: $('session').value.trim(), testItemId: $('testItem').value.trim(), attemptId: $('attempt').value.trim()
      }, extra);
      localStorage.setItem('dd-learning-test', JSON.stringify(state));
      savedTest = state;
    }
    function renderTest(data) {
      const item = (data.items || [])[0] || data;
      if (item.prompt !== undefined) $('testPrompt').textContent = item.prompt || '题面为空。';
      if (item.test_item_id) $('testItem').value = item.test_item_id;
      if (data.session_id) $('session').value = data.session_id;
      saveTestState({account: $('account').value.trim(), learner: $('learner').value.trim()});
      show(data);
    }
    function ensureTestContext() {
      if (!$('session').value.trim() || !$('testItem').value.trim()) {
        throw new Error('请先开始或恢复测验');
      }
      if (savedTest.sessionId === $('session').value.trim() && (savedTest.account !== $('account').value.trim() || savedTest.learner !== $('learner').value.trim())) {
        throw new Error('当前学习者与已保存测验不匹配');
      }
      return {session: $('session').value.trim(), item: $('testItem').value.trim()};
    }
    async function refreshTestState() {
      const context = ensureTestContext();
      const data = await call('/api/v1/test-sessions/' + encodeURIComponent(context.session));
      const item = (data.items || []).find((entry) => entry.test_item_id === context.item) || (data.items || [])[0];
      if (item) {
        $('testItem').value = item.test_item_id;
        $('questionVersion').value = item.question_version_id || $('questionVersion').value;
        if (item.attempt_id) $('attempt').value = item.attempt_id;
        $('testPrompt').textContent = item.prompt || '题面不可用。';
        testStatus(`会话 ${data.session.status} · 题项 ${item.status} · 辅助 ${item.assistance || 'none'}${item.attempt_status ? ` · 判分 ${item.attempt_status}` : ''}`);
      }
      saveTestState(); show(data);
      if ($('attempt').value) await refreshAttempt();
      return data;
    }
    async function refreshAttempt(retry = 0) {
      const attemptId = $('attempt').value.trim();
      if (!attemptId) throw new Error('提交后才有 Attempt ID');
      const data = await call('/api/v1/attempts/' + encodeURIComponent(attemptId));
      const outcome = data.outcome ? ` · 结果 ${data.outcome}` : '';
      testStatus(`判分状态 ${data.status || 'unknown'}${outcome}`);
      saveTestState(); show(data);
      if (data.status === 'grading_pending' && retry < 4) {
        await new Promise((resolve) => setTimeout(resolve, 700));
        return refreshAttempt(retry + 1);
      }
      return data;
    }
    $('loadHealth').onclick = async () => { try { show(await call('/health')); } catch (e) { show(e.message); } };
    $('loadLearners').onclick = async () => { try { show(await call('/api/v1/learners')); } catch (e) { show(e.message); } };
    $('account').addEventListener('change', restoreImportState);
    $('learner').addEventListener('change', restoreImportState);
    $('upload').onclick = async () => {
      const files = [...$('file').files]; if (!files.length) { setStatus('请选择文件'); return; }
      const kind = $('kind').value;
      try {
        const uploaded = [];
        for (const file of files) {
          const form = new FormData(); form.append('file', file); form.append('kind', kind);
          const data = await call('/api/v1/documents', {method: 'POST', body: form});
          const entry = {document_id: data.document_id, filename: file.name, kind, page_count: data.page_count, media_type: data.media_type, failure_code: data.failure_code, selected: kind !== 'answer_key'};
          uploadedDocuments.push(entry); uploaded.push(entry); $('document').value = data.document_id;
        }
        renderDocuments(); $('file').value = '';
        setStatus(`${uploaded.length} 份资料已保存；逐页处理与识别仍需通过批次状态确认。`); show({uploaded});
      } catch (e) { renderDocuments(); setStatus(`上传中断，已成功的文件仍保留在列表。${e.message}`); }
    };
    $('makeBatch').onclick = async () => {
      const selected = uploadedDocuments.filter((doc) => doc.kind !== 'answer_key' && doc.selected !== false).map((doc) => doc.document_id);
      if (!selected.length) { setStatus('请至少选择一份试卷或作业资料'); return; }
      if (selected.length > 20) { setStatus('单批最多选择 20 份资料'); return; }
      const body = {document_ids: selected}; if ($('answerDocument').value) body.answer_document_id = $('answerDocument').value;
      try { const data = await call('/api/v1/import-batches', {method: 'POST', headers: {'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID()}, body: JSON.stringify(body)}); $('batch').value = data.batch_id; saveImportState(); setStatus(data); show(data); }
      catch (e) { setStatus(e.message); }
    };
    $('analyze').onclick = async () => {
      try { const data = await call('/api/v1/import-batches/' + encodeURIComponent($('batch').value) + '/analysis', {method: 'POST', headers: {'Idempotency-Key': 'ui-analysis-' + $('batch').value}}); setStatus(data); show(data); }
      catch (e) { setStatus(e.message); }
    };
    $('cancelBatch').onclick = async () => {
      try { const data = await call('/api/v1/import-batches/' + encodeURIComponent($('batch').value) + '/cancel', {method: 'POST'}); setStatus(data); show(data); }
      catch (e) { setStatus(e.message); }
    };
    $('refreshItems').onclick = async () => {
      const generation = ++importRefreshGeneration;
      const account = $('account').value.trim(), learner = $('learner').value.trim();
      try {
        const batchId = encodeURIComponent($('batch').value);
        const [data, batch] = await Promise.all([
          call('/api/v1/import-batches/' + batchId + '/items'),
          call('/api/v1/import-batches/' + batchId)
        ]);
        if (generation !== importRefreshGeneration || account !== $('account').value.trim() || learner !== $('learner').value.trim()) return;
        const summary = $('pageSummary'); summary.replaceChildren();
        const heading = document.createElement('strong'); heading.textContent = `批次 ${batch.status} · 页面 ${batch.processed_pages}/${batch.total_pages} 已处理 · ${batch.failed_pages} 页失败 · ${batch.items.total} 个候选`;
        summary.append(heading);
        const docMap = new Map(uploadedDocuments.map((doc) => [doc.document_id, doc.filename]));
        (batch.pages || []).forEach((page) => {
          const line = document.createElement('div');
          const issue = page.failure_code ? ` · 失败：${page.failure_code}` : '';
          line.textContent = `${docMap.get(page.document_id) || page.document_id} · 第 ${Number(page.page_index) + 1} 页 · ${page.status}${issue}`;
          summary.append(line);
        });
        const items = data.items || []; $('confirm').disabled = !items.length;
        releaseSourceObjectUrls();
        const container = $('items'); container.replaceChildren(); container.className = 'review-list';
        if (!items.length) {
          container.textContent = batch.failed_pages ? '没有候选；失败页面已列出，不能视为识别完成。' : '暂无候选。';
        } else {
          items.forEach((item, index) => {
            const card = document.createElement('article'); card.className = 'review-card';
            const title = document.createElement('h3'); title.textContent = `第 ${index + 1} 项 · ${item.locator || '未分题'} · ${item.status} · ${item.verdict} · ${item.verification_status}`;
            card.append(title);
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.dataset.item = String(item.id);
            checkbox.dataset.revision = String(item.revision);
            checkbox.disabled = ['confirmed', 'stale', 'cancelled'].includes(item.status) || !['incorrect', 'partial'].includes(item.verdict);
            const selectLabel = document.createElement('label'); selectLabel.append(checkbox, document.createTextNode('选择此项进行可信确认')); card.append(selectLabel);
            const layout = document.createElement('div'); layout.className = 'review-grid';
            const preview = document.createElement('figure'); preview.className = 'source-preview'; preview.textContent = '正在读取授权范围内的来源原页…';
            layout.append(preview);
            const fields = document.createElement('div'); fields.className = 'review-fields';
            const content = item.content || {};
            const statusLine = document.createElement('p'); statusLine.className = 'muted';
            statusLine.textContent = `题干：${content.question_text || content.question || content.text_status || '未提取'}；学生作答：${item.raw_answer || content.student_answer || content.student_input_status || '未提取'}；教师批改：${content.teacher_mark || '未提供'}`;
            fields.append(statusLine);
            const questionText = document.createElement('textarea'); questionText.rows = 3; questionText.placeholder = '人工校正题干转写（不得补写原卷中没有的内容）'; questionText.value = content.question_text || content.question || '';
            const questionLabel = document.createElement('label'); questionLabel.append(document.createTextNode('题干转写校正'), questionText); fields.append(questionLabel);
            const rawAnswer = document.createElement('textarea'); rawAnswer.rows = 2; rawAnswer.placeholder = '人工校正学生原始作答；不确定时留空'; rawAnswer.value = item.raw_answer || content.student_answer || '';
            const answerLabel = document.createElement('label'); answerLabel.append(document.createTextNode('学生原始作答校正'), rawAnswer); fields.append(answerLabel);
            const verdict = document.createElement('select');
            verdict.dataset.verdict = String(item.id);
            ['correct', 'incorrect', 'partial', 'unanswered', 'undetermined'].forEach((value) => {
              const option = document.createElement('option'); option.value = value; option.textContent = value;
              if (value === item.verdict) option.selected = true;
              verdict.append(option);
            });
            verdict.disabled = item.status === 'confirmed';
            verdict.onchange = () => { checkbox.disabled = ['confirmed', 'stale', 'cancelled'].includes(item.status) || !['incorrect', 'partial'].includes(verdict.value); if (checkbox.disabled) checkbox.checked = false; };
            const verdictLabel = document.createElement('label'); verdictLabel.append(document.createTextNode('人工判定'), verdict); fields.append(verdictLabel);
            const objective = document.createElement('input');
            objective.dataset.objective = String(item.id);
            objective.placeholder = '目标 ID（可选）';
            objective.value = item.content?.objective_id || '';
            objective.disabled = item.status === 'confirmed';
            const objectiveLabel = document.createElement('label'); objectiveLabel.append(document.createTextNode('目标 ID'), objective); fields.append(objectiveLabel);
            const evidence = document.createElement('textarea');
            evidence.dataset.evidence = String(item.id);
            evidence.rows = 2;
            evidence.placeholder = '复核证据';
            evidence.value = JSON.stringify(item.teacher_evidence || {});
            evidence.disabled = item.status === 'confirmed';
            const evidenceLabel = document.createElement('label'); evidenceLabel.append(document.createTextNode('人工复核证据'), evidence); fields.append(evidenceLabel);
            const save = document.createElement('button');
            save.type = 'button'; save.className = 'secondary'; save.textContent = '保存复核';
            save.disabled = ['confirmed', 'stale', 'cancelled'].includes(item.status);
            save.onclick = async () => {
              try {
                let parsedEvidence = {};
                const rawEvidence = evidence.value.trim();
                if (rawEvidence) { try { parsedEvidence = JSON.parse(rawEvidence); } catch (_) { parsedEvidence = {note: rawEvidence}; } }
                const result = await call('/api/v1/import-items/' + encodeURIComponent(item.id), {
                  method: 'PATCH', headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({expected_revision: Number(checkbox.dataset.revision), raw_answer: rawAnswer.value, content: {...content, question_text: questionText.value, objective_id: objective.value.trim() || null}, verdict: verdict.value, evidence: parsedEvidence, objective_id: objective.value.trim() || null})
                });
                await $('refreshItems').onclick(); show(result);
              } catch (e) { show(e.message); }
            };
            fields.append(save); layout.append(fields); card.append(layout); container.append(card);
            renderSourcePreview(item, preview);
          });
        }
        show(data);
      } catch (e) {
        if (generation !== importRefreshGeneration || account !== $('account').value.trim() || learner !== $('learner').value.trim()) return;
        $('items').textContent = e.message; $('pageSummary').textContent = e.message;
      }
    };
    $('loadMistakes').onclick = async () => {
      try { const data = await call('/api/v1/mistakes'); $('mistakes').textContent = JSON.stringify(data, null, 2); show(data); }
      catch (e) { $('mistakes').textContent = e.message; }
    };
    $('loadReview').onclick = async () => {
      try { const data = await call('/api/v1/review-tasks'); $('mistakes').textContent = JSON.stringify(data, null, 2); show(data); }
      catch (e) { $('mistakes').textContent = e.message; }
    };
    $('diagnose').onclick = async () => {
      try { const data = await call('/api/v1/mistakes/' + encodeURIComponent($('mistake').value) + '/diagnoses', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})}); show(data); }
      catch (e) { show(e.message); }
    };
    $('startTest').onclick = async () => {
      try {
        const card = $('card').value.trim(); const body = {question_version_id: $('questionVersion').value, mode: 'independent'};
        if (card) body.card_id = card;
        const data = await call('/api/v1/test-sessions', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
        $('attempt').value = ''; renderTest(data); testStatus('题面已发放，答案未发送到客户端。');
      } catch (e) { testStatus(e.message); }
    };
    $('restoreTest').onclick = async () => {
      try {
        const account = $('account').value.trim(), learner = $('learner').value.trim();
        if (savedTest.account && (savedTest.account !== account || savedTest.learner !== learner)) throw new Error('保存的测验属于其他学习者，请先输入匹配身份');
        if (!savedTest.sessionId) throw new Error('没有可恢复的测验会话');
        $('session').value = savedTest.sessionId; $('testItem').value = savedTest.testItemId || '';
        $('attempt').value = savedTest.attemptId || '';
        await refreshTestState();
      } catch (e) { testStatus(e.message); }
    };
    $('refreshTest').onclick = async () => { try { await refreshTestState(); } catch (e) { testStatus(e.message); } };
    $('requestHint').onclick = async () => {
      try {
        const context = ensureTestContext();
        const data = await call('/api/v1/test-items/' + encodeURIComponent(context.item) + '/hints', {method: 'POST'});
        testStatus('已记录提示暴露，当前作答不计入独立证据。'); show(data); await refreshTestState();
      } catch (e) { testStatus(e.message); }
    };
    $('cancelTest').onclick = async () => {
      try {
        const session = $('session').value.trim(); if (!session) throw new Error('请先开始或恢复测验');
        const data = await call('/api/v1/test-sessions/' + encodeURIComponent(session) + '/cancel', {method: 'POST'});
        testStatus('测验已取消，未提交题项不会产生判分。'); show(data); await refreshTestState();
      } catch (e) { testStatus(e.message); }
    };
    $('submitAnswer').onclick = async () => {
      try {
        const item = $('testItem').value.trim(); if (!item || !$('answer').value) throw new Error('请填写作答项和原始作答');
        const challenge = await call('/api/v1/test-items/' + encodeURIComponent(item) + '/submission-challenges', {method: 'POST'});
        const data = await call('/api/v1/test-items/' + encodeURIComponent(item) + '/answers', {method: 'POST', headers: {'Content-Type': 'application/json', 'Idempotency-Key': 'ui-answer-' + crypto.randomUUID()}, body: JSON.stringify({challenge_id: challenge.challenge_id, nonce: challenge.nonce, raw_answer: $('answer').value})});
        $('attempt').value = data.attempt_id || ''; saveTestState(); testStatus('已提交，等待服务端判分；202 不是最终成绩。'); show(data);
        if ($('attempt').value) await refreshAttempt();
      } catch (e) { testStatus(e.message); }
    };
    $('refreshAttempt').onclick = async () => { try { await refreshAttempt(); } catch (e) { testStatus(e.message); } };
    $('requestReview').onclick = async () => {
      try {
        const attempt = $('attempt').value.trim(); if (!attempt) throw new Error('请先提交作答并读取 Attempt ID');
        const reason = window.prompt('请输入复核原因'); if (!reason) return;
        const data = await call('/api/v1/attempts/' + encodeURIComponent(attempt) + '/review-requests', {method: 'POST', headers: {'Content-Type': 'application/json', 'Idempotency-Key': 'ui-review-' + crypto.randomUUID()}, body: JSON.stringify({reason, details: {source: 'learning-workbench'}})});
        await refreshAttempt(); testStatus('复核申请已提交，成绩不会被客户端直接修改。'); show(data);
      } catch (e) { testStatus(e.message); }
    };
    $('confirm').onclick = async () => {
      const selected = [...document.querySelectorAll('[data-item]:checked')];
      if (!selected.length) { show('请选择待确认项目'); return; }
      try {
        const items = selected.map((box) => ({item_id: box.dataset.item, expected_revision: Number(box.dataset.revision)}));
        const summary = selected.map((box) => {
          const card = box.closest('.review-card'); return card?.querySelector('h3')?.textContent || box.dataset.item;
        }).join('；');
        if (!window.confirm(`请再次核对以下已选候选与右侧人工证据，再进行批量入库：\n${summary}`)) return;
        const challenge = await call('/api/v1/import-batches/' + encodeURIComponent($('batch').value) + '/confirmation-challenges', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({items})});
        const result = await call('/api/v1/import-batches/' + encodeURIComponent($('batch').value) + '/confirmations', {method: 'POST', headers: {'Content-Type': 'application/json', 'Idempotency-Key': 'ui-confirm-' + crypto.randomUUID()}, body: JSON.stringify({challenge_id: challenge.challenge_id, nonce: challenge.nonce, items})});
        await $('refreshItems').onclick(); show(result);
      } catch (e) { show(e.message); }
    };
    $('loadHealth').onclick();
    restoreImportState();
    if (savedTest.sessionId && savedTest.account === ($('account').value.trim()) && savedTest.learner === ($('learner').value.trim())) {
      $('restoreTest').onclick();
    }
  </script>
</body>
</html>"""


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_dirs()
    db = database or Database(settings.db_path)

    app = FastAPI(title="DD-1.0 Learning Service", version="0.1.0", docs_url="/docs")
    app.state.settings = settings
    app.state.db = db

    @app.exception_handler(APIError)
    async def api_error_handler(_: Request, exc: APIError):
        payload = {"error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable}}
        if exc.details is not None:
            payload["error"]["details"] = exc.details
        return __import__("fastapi").responses.JSONResponse(status_code=exc.status, content=payload)

    @app.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException):
        return __import__("fastapi").responses.JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "retryable": False}},
        )

    def get_settings() -> Settings:
        return app.state.settings

    def get_db() -> Database:
        return app.state.db

    def admin_secret(request: Request, settings: Settings = Depends(get_settings)) -> None:
        supplied = request.headers.get("X-Admin-Secret", "")
        if not settings.dev_mode or not settings.admin_secret or not secrets.compare_digest(supplied, settings.admin_secret):
            raise APIError(404, "NOT_FOUND", "资源不存在")

    def get_context(request: Request, settings: Settings = Depends(get_settings), db: Database = Depends(get_db)) -> Context:
        adapter_secret = request.headers.get("X-Adapter-Secret", "")
        if settings.adapter_secret:
            if not secrets.compare_digest(adapter_secret, settings.adapter_secret):
                raise APIError(401, "UNTRUSTED_CONTEXT", "缺少受信适配器上下文")
        elif not settings.dev_mode:
            raise APIError(503, "ADAPTER_NOT_CONFIGURED", "受信适配器尚未配置", True)

        account_id = request.headers.get("X-Account-Id") if settings.dev_mode else None
        provider = request.headers.get("X-Trusted-Provider", "local")
        issuer = request.headers.get("X-Trusted-Issuer", "learning-service")
        subject = request.headers.get("X-Trusted-Subject")
        with db.session() as conn:
            if not account_id:
                if not subject:
                    raise APIError(401, "UNTRUSTED_IDENTITY", "缺少受信身份")
                row = conn.execute(
                    "SELECT account_id FROM identity_bindings WHERE provider=? AND issuer=? AND subject=?",
                    (provider, issuer, subject),
                ).fetchone()
                if not row:
                    raise APIError(401, "UNKNOWN_IDENTITY", "身份未绑定")
                account_id = row["account_id"]
            if not conn.execute("SELECT 1 FROM accounts WHERE id=?", (account_id,)).fetchone():
                raise APIError(401, "UNKNOWN_ACCOUNT", "账号不存在")
            learner_id = request.headers.get("X-Learner-Id")
            role = "student"
            if learner_id:
                access = conn.execute(
                    "SELECT role FROM learner_access WHERE account_id=? AND learner_id=? AND active=1",
                    (account_id, learner_id),
                ).fetchone()
                if not access:
                    raise APIError(404, "LEARNER_NOT_FOUND", "学习者不可访问")
                role = access["role"]
        return Context(account_id=account_id, learner_id=learner_id, role=role, provider=provider)

    def learner_for(ctx: Context, requested: str | None = None, db: Database = Depends(get_db)) -> str:
        learner_id = requested or ctx.learner_id
        if not learner_id:
            raise APIError(409, "LEARNER_CONTEXT_REQUIRED", "请先选择当前学习者")
        with db.session() as conn:
            row = conn.execute(
                "SELECT role FROM learner_access WHERE account_id=? AND learner_id=? AND active=1",
                (ctx.account_id, learner_id),
            ).fetchone()
        if not row:
            raise APIError(404, "LEARNER_NOT_FOUND", "学习者不可访问")
        return learner_id

    def objective_for_learner(conn: sqlite3.Connection, learner_id: str, objective_id: str) -> sqlite3.Row:
        """Resolve an objective only when its curriculum belongs to the learner."""
        row = conn.execute(
            "SELECT o.id,o.knowledge_point_id,k.curriculum_id,l.curriculum_id AS learner_curriculum "
            "FROM review_objectives o JOIN knowledge_points k ON k.id=o.knowledge_point_id "
            "JOIN learners l ON l.id=? WHERE o.id=?",
            (learner_id, objective_id),
        ).fetchone()
        if not row:
            raise APIError(404, "OBJECTIVE_NOT_FOUND", "目标不存在")
        if row["curriculum_id"] != row["learner_curriculum"]:
            raise APIError(403, "OBJECTIVE_SCOPE_MISMATCH", "目标不属于当前学习者课程")
        return row

    def validate_variant_source(
        conn: sqlite3.Connection,
        learner_id: str,
        objective_id: str,
        source_question_version_id: str | None,
    ) -> None:
        objective_for_learner(conn, learner_id, objective_id)
        if source_question_version_id in (None, ""):
            return
        row = conn.execute(
            "SELECT qv.id,qv.approval AS version_approval,q.approval AS question_approval, "
            "q.objective_id,q.visibility,q.learner_id "
            "FROM question_versions qv JOIN questions q ON q.id=qv.question_id "
            "WHERE qv.id=?",
            (source_question_version_id,),
        ).fetchone()
        if not row:
            raise APIError(404, "SOURCE_QUESTION_NOT_FOUND", "来源题目版本不存在")
        if row["question_approval"] != "approved" or row["version_approval"] != "approved":
            raise APIError(409, "SOURCE_QUESTION_NOT_APPROVED", "来源题目或版本尚未审核")
        if row["objective_id"] != objective_id:
            raise APIError(409, "SOURCE_OBJECTIVE_MISMATCH", "来源题目不属于请求目标")
        if row["visibility"] != "shared" and row["learner_id"] != learner_id:
            raise APIError(404, "SOURCE_QUESTION_NOT_FOUND", "来源题目不可访问")

    def require_admin(ctx: Context) -> None:
        if ctx.role != "admin":
            raise APIError(403, "FORBIDDEN", "需要管理权限")

    def audit(db: Database, ctx: Context | None, operation: str, resource_type: str, resource_id: str | None, result: str, metadata: Any = None) -> None:
        with db.session(write=True) as conn:
            conn.execute(
                "INSERT INTO audit_events(id,account_id,learner_id,operation,resource_type,resource_id,result,metadata_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (new_id("audit"), ctx.account_id if ctx else None, ctx.learner_id if ctx else None, operation, resource_type, resource_id, result, json_dumps(metadata or {}), utc_now()),
            )

    def ensure_access(conn, account_id: str, learner_id: str, roles: set[str] | None = None) -> sqlite3.Row:
        row = conn.execute(
            "SELECT role FROM learner_access WHERE account_id=? AND learner_id=? AND active=1",
            (account_id, learner_id),
        ).fetchone()
        if not row or (roles and row["role"] not in roles):
            raise APIError(404, "RESOURCE_NOT_FOUND", "资源不存在")
        return row

    def challenge_response(conn, ctx: Context, learner_id: str, operation: str, resource_id: str, versions: dict[str, Any], settings: Settings) -> dict[str, Any]:
        nonce = secrets.token_urlsafe(32)
        challenge_id = new_id("challenge")
        expires = (datetime.now(timezone.utc) + timedelta(seconds=settings.challenge_ttl_seconds)).replace(microsecond=0).isoformat()
        conn.execute(
            "INSERT INTO interaction_challenges(id,actor_account_id,learner_id,operation,resource_id,resource_versions_json,nonce_hash,expires_at,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (challenge_id, ctx.account_id, learner_id, operation, resource_id, json_dumps(versions), _hash(nonce), expires, utc_now()),
        )
        return {"challenge_id": challenge_id, "nonce": nonce, "expires_at": expires, "operation": operation, "resource_id": resource_id, "resource_versions": versions}

    def consume_challenge(conn, ctx: Context, learner_id: str, operation: str, resource_id: str, challenge_id: str, nonce: str, versions: dict[str, Any]) -> None:
        row = conn.execute(
            "SELECT * FROM interaction_challenges WHERE id=? AND actor_account_id=? AND learner_id=? AND operation=? AND resource_id=?",
            (challenge_id, ctx.account_id, learner_id, operation, resource_id),
        ).fetchone()
        if not row:
            raise APIError(410, "CHALLENGE_INVALID", "交互挑战无效或已过期")
        if row["consumed_at"]:
            raise APIError(409, "CHALLENGE_REPLAY", "交互挑战已经消费")
        if _parse_iso(row["expires_at"]) <= datetime.now(timezone.utc):
            raise APIError(410, "CHALLENGE_EXPIRED", "交互挑战已过期")
        if not secrets.compare_digest(row["nonce_hash"], _hash(nonce)):
            raise APIError(410, "CHALLENGE_INVALID", "交互挑战无效")
        if json_loads(row["resource_versions_json"], {}) != versions:
            raise APIError(409, "REVISION_CONFLICT", "资源版本已变化，请刷新")
        conn.execute("UPDATE interaction_challenges SET consumed_at=? WHERE id=? AND consumed_at IS NULL", (utc_now(), challenge_id))

    def reviewed_import_candidates(
        conn: sqlite3.Connection,
        batch_id: str,
        learner_id: str,
        candidates: list[dict[str, Any]],
    ) -> tuple[dict[str, int], dict[str, sqlite3.Row]]:
        """Validate the exact manually reviewed candidate set before issuing/using a challenge."""
        requested: dict[str, int] = {}
        rows: dict[str, sqlite3.Row] = {}
        for candidate in candidates:
            item_id = candidate.get("item_id")
            revision = candidate.get("expected_revision")
            if not isinstance(item_id, str) or not item_id.strip():
                raise APIError(422, "INVALID_ITEM_ID", "候选题 ID 无效")
            if type(revision) is not int or revision < 1:
                raise APIError(422, "INVALID_ITEM_REVISION", "候选题 revision 必须是正整数")
            if item_id in requested:
                raise APIError(422, "DUPLICATE_ITEM", "批量确认不能重复选择同一候选题")
            requested[item_id] = revision
        for item_id, revision in requested.items():
            item = conn.execute(
                "SELECT * FROM import_items WHERE id=? AND batch_id=? AND learner_id=?",
                (item_id, batch_id, learner_id),
            ).fetchone()
            if not item:
                raise APIError(409, "REVISION_CONFLICT", "候选题不存在或已更新")
            if item["revision"] != revision:
                raise APIError(409, "REVISION_CONFLICT", "候选题已更新")
            if item["status"] != "ready":
                raise APIError(409, "ITEM_NOT_READY", "候选题尚未准备好或已处理")
            if item["verification_status"] != "manual":
                raise APIError(409, "MANUAL_REVIEW_REQUIRED", "候选题必须先完成教师人工复核")
            if item["verdict"] not in {"correct", "incorrect", "partial", "unanswered", "undetermined"}:
                raise APIError(409, "INVALID_VERDICT", "候选题必须保留五类受支持的人工判定之一")

            evidence = json_loads(item["teacher_evidence_json"], {})
            if not isinstance(evidence, dict) or not evidence:
                raise APIError(409, "EVIDENCE_REQUIRED", "人工复核必须保留非空教师证据")
            judgment = conn.execute(
                "SELECT verdict,evidence_json,verification_status FROM import_judgments WHERE item_id=? AND revision=? ORDER BY created_at DESC LIMIT 1",
                (item_id, revision),
            ).fetchone()
            judgment_evidence = json_loads(judgment["evidence_json"], {}) if judgment else None
            if (
                not judgment
                or judgment["verification_status"] != "manual"
                or judgment["verdict"] != item["verdict"]
                or judgment_evidence != evidence
            ):
                raise APIError(409, "MANUAL_JUDGMENT_REQUIRED", "当前 revision 缺少与候选一致的人工裁决记录")
            rows[item_id] = item

        return requested, rows

    def idempotent_result(conn, ctx: Context, learner_id: str, operation: str, resource_id: str, key: str | None, body: Any) -> dict[str, Any] | None:
        if not key:
            return None
        row = conn.execute(
            "SELECT request_hash,result_json FROM idempotency_records WHERE account_id=? AND learner_id=? AND operation=? AND resource_id=? AND idem_key=?",
            (ctx.account_id, learner_id, operation, resource_id, key),
        ).fetchone()
        if not row:
            return None
        if row["request_hash"] != _request_hash(body):
            raise APIError(409, "IDEMPOTENCY_CONFLICT", "相同幂等键携带了不同内容")
        return json_loads(row["result_json"], {})

    def save_idempotent(conn, ctx: Context, learner_id: str, operation: str, resource_id: str, key: str | None, body: Any, result: dict[str, Any]) -> None:
        if key:
            conn.execute(
                "INSERT INTO idempotency_records(id,account_id,learner_id,operation,resource_id,idem_key,request_hash,result_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (new_id("idem"), ctx.account_id, learner_id, operation, resource_id, key, _request_hash(body), json_dumps(result), utc_now()),
            )

    def enqueue(conn, learner_id: str | None, kind: str, input_data: Any, key: str) -> str:
        row = conn.execute("SELECT id FROM jobs WHERE idempotency_key=?", (key,)).fetchone()
        if row:
            return row["id"]
        job_id = new_id("job")
        now = utc_now()
        conn.execute(
            "INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (job_id, learner_id, kind, json_dumps(input_data), key, "queued", now, now),
        )
        return job_id

    @app.get("/health")
    def health(db: Database = Depends(get_db)):
        with db.session() as conn:
            revision = conn.execute("SELECT COALESCE(MAX(version),0) AS v FROM schema_migrations").fetchone()["v"]
        return {"status": "ok", "service": "learning-api", "schema_revision": revision, "version": "0.1.0"}

    @app.get("/api/v1/admin/metrics")
    def admin_metrics(ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        """Return privacy-preserving operational aggregates for an administrator.

        This endpoint intentionally exposes no learner identifiers, payloads, or
        attachment metadata.  It is for queue/recovery support and complements
        the public liveness probe without turning health checks into a data API.
        """
        require_admin(ctx)
        now = datetime.now(timezone.utc)
        now_iso = now.replace(microsecond=0).isoformat()

        def age_seconds(value: str | None) -> int | None:
            if not value:
                return None
            try:
                return max(0, int((now - _parse_iso(value)).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                return None

        with db.session() as conn:
            jobs_by_status = {
                row["status"]: row["count"]
                for row in conn.execute("SELECT status,COUNT(*) AS count FROM jobs GROUP BY status").fetchall()
            }
            jobs_by_kind = {
                row["kind"]: row["count"]
                for row in conn.execute("SELECT kind,COUNT(*) AS count FROM jobs GROUP BY kind").fetchall()
            }
            oldest_queued = conn.execute("SELECT MIN(created_at) AS created_at FROM jobs WHERE status='queued'").fetchone()["created_at"]
            page_totals = conn.execute(
                "SELECT COUNT(*) AS total, SUM(CASE WHEN status='failed' OR failure_code IS NOT NULL THEN 1 ELSE 0 END) AS failed FROM source_pages"
            ).fetchone()
            review_items = conn.execute(
                "SELECT COUNT(*) AS count FROM import_items WHERE status IN ('extracted','needs_review','ready') AND verification_status='needs_review'"
            ).fetchone()["count"]
            review_batches = conn.execute(
                "SELECT COUNT(*) AS count FROM import_batches WHERE status IN ('draft','processing','awaiting_review','partial_failed')"
            ).fetchone()["count"]
            pending_deletions = conn.execute(
                "SELECT COUNT(*) AS count FROM deletion_records WHERE cleanup_state IN ('pending','failed')"
            ).fetchone()["count"]
            stale_leases = conn.execute(
                "SELECT COUNT(*) AS count FROM jobs WHERE status='running' AND lease_until IS NOT NULL AND lease_until<?",
                (now_iso,),
            ).fetchone()["count"]
            idempotency_records = conn.execute("SELECT COUNT(*) AS count FROM idempotency_records").fetchone()["count"]
            page_total = page_totals["total"] or 0
            page_failed = page_totals["failed"] or 0

        return {
            "status": "ok",
            "generated_at": now_iso,
            "jobs": {
                "by_status": jobs_by_status,
                "by_kind": jobs_by_kind,
                "oldest_queued_age_seconds": age_seconds(oldest_queued),
                "expired_running_leases": stale_leases,
            },
            "pages": {
                "total": page_total,
                "failed": page_failed,
                "failure_ratio": round(page_failed / page_total, 6) if page_total else 0.0,
            },
            "review": {"pending_items": review_items, "pending_batches": review_batches},
            "lifecycle": {"pending_deletions": pending_deletions},
            "idempotency": {"records": idempotency_records},
            "external_calls": {"tracked": False, "reason": "provider cost metadata is not configured"},
        }

    @app.get("/ui", response_class=HTMLResponse)
    def ui():
        return HTMLResponse(_UI_HTML)

    @app.post("/internal/bootstrap")
    def bootstrap(body: BootstrapRequest, _: None = Depends(admin_secret), db: Database = Depends(get_db)):
        now = utc_now()
        account_id = body.account_id or new_id("acct")
        learner_id = body.learner_id or new_id("learner")
        kp_id = new_id("kp")
        objective_id = new_id("objective")
        with db.session(write=True) as conn:
            conn.execute("INSERT OR IGNORE INTO accounts(id,created_at) VALUES (?,?)", (account_id, now))
            conn.execute(
                "INSERT OR IGNORE INTO identity_bindings(id,account_id,provider,issuer,subject,created_at) VALUES (?,?,?,?,?,?)",
                (new_id("identity"), account_id, body.provider, body.issuer, body.subject, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO learners(id,display_name,timezone,curriculum_id,created_at) VALUES (?,?,?,?,?)",
                (learner_id, body.display_name, body.timezone, "math-g7-v1", now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO learner_access(account_id,learner_id,role,active,created_at) VALUES (?,?,?,?,?)",
                (account_id, learner_id, body.role, 1, now),
            )
            existing_kp = conn.execute("SELECT id FROM knowledge_points WHERE curriculum_id='math-g7-v1' AND code='signed-numbers' ").fetchone()
            kp_id = existing_kp["id"] if existing_kp else kp_id
            if not existing_kp:
                conn.execute("INSERT INTO knowledge_points(id,curriculum_id,code,title,created_at) VALUES (?,?,?,?,?)", (kp_id, "math-g7-v1", "signed-numbers", "有理数与数轴", now))
            existing_obj = conn.execute("SELECT id FROM review_objectives WHERE knowledge_point_id=? AND code='subtract-negative'", (kp_id,)).fetchone()
            objective_id = existing_obj["id"] if existing_obj else objective_id
            if not existing_obj:
                conn.execute("INSERT INTO review_objectives(id,knowledge_point_id,code,title,created_at) VALUES (?,?,?,?,?)", (objective_id, kp_id, "subtract-negative", "理解减去负数的运算方向", now))
            template = conn.execute("SELECT 1 FROM visual_templates WHERE template_id='signed_number_subtraction' AND version='1.0.0'").fetchone()
            if not template:
                conn.execute("INSERT INTO visual_templates(id,version,template_id,parameter_schema_json,approval,created_at) VALUES (?,?,?,?,?,?)", (new_id("template"), "1.0.0", "signed_number_subtraction", json_dumps({"start": {"type": "integer", "min": -100, "max": 100}, "subtrahend": {"type": "integer", "min": -100, "max": 100}}), "approved", now))
        return {"account_id": account_id, "learner_id": learner_id, "knowledge_point_id": kp_id, "objective_id": objective_id}

    @app.post("/internal/questions")
    def seed_question(body: dict[str, Any], _: None = Depends(admin_secret), db: Database = Depends(get_db)):
        objective_id = body.get("objective_id")
        if not objective_id or not body.get("prompt"):
            raise APIError(422, "INVALID_QUESTION", "需要 objective_id 和 prompt")
        variant_kind = body.get("variant_kind", "base")
        if variant_kind not in {"base", "variant"}:
            raise APIError(422, "INVALID_VARIANT_KIND", "variant_kind 只能是 base 或 variant")
        variant_group = body.get("variant_group")
        if variant_kind == "variant" and variant_group is not None and not isinstance(variant_group, str):
            raise APIError(422, "INVALID_VARIANT_GROUP", "variant_group 必须是字符串")
        question_id, version_id = new_id("question"), new_id("qv")
        with db.session(write=True) as conn:
            if not conn.execute("SELECT 1 FROM review_objectives WHERE id=?", (objective_id,)).fetchone():
                raise APIError(404, "OBJECTIVE_NOT_FOUND", "目标不存在")
            conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?)", (question_id, "shared", "approved", objective_id, utc_now()))
            content = {"prompt": body["prompt"], "input_type": body.get("input_type", "text"), "hint": body.get("hint", "先写出你采用的运算方向。"), "alternative_text": body.get("alternative_text", body["prompt"])}
            answer_key = {"accepted": [str(x) for x in body.get("accepted", [])], "outcome": body.get("outcome", "correct")}
            conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,variant_kind,variant_group,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (version_id, question_id, 1, json_dumps(content), json_dumps(answer_key), "exact-text-v1", "approved", variant_kind, variant_group, utc_now()))
        return {"question_id": question_id, "question_version_id": version_id, "objective_id": objective_id}

    @app.get("/api/v1/learners")
    def learners(ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        with db.session() as conn:
            rows = conn.execute("SELECT l.id,l.display_name,l.timezone,l.curriculum_id,la.role FROM learners l JOIN learner_access la ON la.learner_id=l.id WHERE la.account_id=? AND la.active=1 AND l.active=1 ORDER BY l.display_name", (ctx.account_id,)).fetchall()
        return {"items": [dict(row) for row in rows], "next_cursor": None}

    @app.post("/api/v1/learner-context")
    def learner_context(body: dict[str, str], request: Request, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = body.get("learner_id")
        if not learner_id:
            raise APIError(422, "LEARNER_REQUIRED", "需要 learner_id")
        with db.session(write=True) as conn:
            ensure_access(conn, ctx.account_id, learner_id)
            conn.execute("UPDATE interaction_challenges SET consumed_at=? WHERE actor_account_id=? AND consumed_at IS NULL", (utc_now(), ctx.account_id))
        return {"learner_id": learner_id, "context_version": new_id("context")}

    @app.post("/api/v1/documents", status_code=201)
    async def upload_document(file: UploadFile = File(...), kind: str = "paper", completed_date: str | None = None, ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        learner_id = learner_for(ctx, db=db)
        if kind not in {"paper", "homework", "answer_key"}:
            raise APIError(422, "INVALID_DOCUMENT_KIND", "资料类型不支持")
        media_type = (file.content_type or mimetypes.guess_type(file.filename or "")[0] or "").lower()
        data = await file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise APIError(413, "UPLOAD_TOO_LARGE", "文件超过大小限制")
        actual = "application/pdf" if data.startswith(b"%PDF") else "image/png" if data.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if data.startswith(b"\xff\xd8\xff") else None
        if actual is None or actual != media_type:
            raise APIError(415, "UNSUPPORTED_MEDIA", "文件类型与内容不匹配")
        digest = hashlib.sha256(data).hexdigest()
        document_id, asset_id = new_id("doc"), new_id("asset")
        object_key = f"{_storage_component(learner_id, 'learner_id')}/{_storage_component(asset_id, 'asset_id')}-{_safe_filename(file.filename or 'upload.bin')}"
        target = _contained_path(settings.attachment_dir, object_key)
        created_paths = [target]
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(target)
            pages, decode_error = _page_count(data, media_type)
            if media_type == "application/pdf" and not decode_error:
                page_assets = _render_pdf_pages(data, settings.attachment_dir, learner_id, asset_id)
                created_paths.extend(_contained_path(settings.attachment_dir, page["object_key"]) for page in page_assets if page["object_key"])
            elif decode_error:
                page_assets = [{"object_key": None, "media_type": media_type, "byte_size": 0, "width": None, "height": None, "failure_code": decode_error} for _ in range(pages)]
            else:
                page_assets = [{"object_key": object_key, "media_type": media_type, "byte_size": len(data), "width": None, "height": None, "failure_code": None}]
            with db.session(write=True) as conn:
                conn.execute("INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)", (asset_id, learner_id, "private", object_key, digest, media_type, len(data), "source_document", utc_now()))
                conn.execute("INSERT INTO source_documents(id,learner_id,asset_id,kind,status,page_count,completed_date,created_at) VALUES (?,?,?,?,?,?,?,?)", (document_id, learner_id, asset_id, kind, "stored", pages, completed_date, utc_now()))
                for index in range(pages):
                    page = page_assets[index]
                    page_asset_id = asset_id
                    if page["object_key"] and media_type == "application/pdf":
                        page_asset_id = new_id("asset")
                        page_bytes = _contained_path(settings.attachment_dir, page["object_key"]).read_bytes()
                        conn.execute("INSERT INTO assets(id,learner_id,visibility,object_key,sha256,media_type,byte_size,purpose,created_at) VALUES (?,?,?,?,?,?,?,?,?)", (page_asset_id, learner_id, "private", page["object_key"], hashlib.sha256(page_bytes).hexdigest(), page["media_type"], page["byte_size"], "source_page", utc_now()))
                    conn.execute("INSERT INTO source_pages(id,document_id,page_index,status,object_key,asset_id,failure_code,width,height,transform_json) VALUES (?,?,?,?,?,?,?,?,?,?)", (new_id("page"), document_id, index, "failed" if page["failure_code"] else "queued", page["object_key"], page_asset_id if page["object_key"] else None, page["failure_code"], page["width"], page["height"], json_dumps({"rotation": 0})))
        except Exception:
            for path in reversed(created_paths):
                for partial in (path.with_suffix(path.suffix + ".tmp"), path):
                    try:
                        partial.unlink(missing_ok=True)
                    except OSError:
                        pass
            raise
        return {"document_id": document_id, "asset_id": asset_id, "sha256": digest, "media_type": media_type, "page_count": pages, "failure_code": decode_error}

    @app.get("/api/v1/documents/{document_id}")
    def get_document(document_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            doc = conn.execute("SELECT d.*,a.sha256,a.media_type,a.byte_size FROM source_documents d JOIN assets a ON a.id=d.asset_id WHERE d.id=? AND d.learner_id=? AND a.deleted_at IS NULL", (document_id, learner_id)).fetchone()
            if not doc:
                raise APIError(404, "RESOURCE_NOT_FOUND", "资料不存在")
            pages = conn.execute("SELECT id,page_index,status,asset_id,failure_code,width,height,transform_json FROM source_pages WHERE document_id=? ORDER BY page_index", (document_id,)).fetchall()
        return {"document": dict(doc), "pages": [dict(row) for row in pages]}

    @app.patch("/api/v1/documents/{document_id}/pages")
    def patch_document_pages(document_id: str, body: PagePatch, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        """Update the versioned page projection while retaining the upload.

        A page edit is deliberately a whole-list replacement.  This avoids
        partial reordering races and makes the document revision a single
        compare-and-swap boundary for UI and worker callers.
        """
        learner_id = learner_for(ctx, db=db)
        if len({str(page.get("page_id")) for page in body.pages}) != len(body.pages):
            raise APIError(422, "DUPLICATE_PAGE", "页面列表包含重复或缺失 page_id")
        parsed: list[dict[str, Any]] = []
        with db.session(write=True) as conn:
            document = conn.execute(
                "SELECT d.*,a.id AS original_asset_id,a.deleted_at AS original_deleted_at "
                "FROM source_documents d JOIN assets a ON a.id=d.asset_id "
                "WHERE d.id=? AND d.learner_id=? AND d.status <> 'deleted' AND a.deleted_at IS NULL",
                (document_id, learner_id),
            ).fetchone()
            if not document:
                raise APIError(404, "DOCUMENT_NOT_FOUND", "资料不存在")
            if document["revision"] != body.expected_revision:
                raise APIError(409, "REVISION_CONFLICT", "资料版本已更新")
            current = conn.execute(
                "SELECT * FROM source_pages WHERE document_id=? ORDER BY page_index",
                (document_id,),
            ).fetchall()
            expected_ids = {row["id"] for row in current}
            supplied_ids = {str(page.get("page_id")) for page in body.pages}
            if supplied_ids != expected_ids or len(body.pages) != len(current):
                raise APIError(422, "PAGE_SET_MISMATCH", "必须提交该资料的完整页面集合")
            indexes: set[int] = set()
            for page in body.pages:
                page_id = str(page.get("page_id"))
                try:
                    page_index = int(page["page_index"])
                    rotation = int(page.get("rotation", 0))
                except (KeyError, TypeError, ValueError):
                    raise APIError(422, "INVALID_PAGE_TRANSFORM", "页面序号和旋转角度无效")
                if page_index < 0 or page_index >= len(current) or page_index in indexes:
                    raise APIError(422, "INVALID_PAGE_ORDER", "页面序号必须从 0 连续且不重复")
                if rotation not in {0, 90, 180, 270}:
                    raise APIError(422, "INVALID_PAGE_ROTATION", "旋转角度只能是 0、90、180 或 270")
                indexes.add(page_index)
                row = next(item for item in current if item["id"] == page_id)
                asset_id = page.get("asset_id", row["asset_id"])
                asset = None
                if asset_id is not None:
                    asset = conn.execute(
                        "SELECT id,object_key,learner_id,purpose,deleted_at FROM assets WHERE id=?",
                        (str(asset_id),),
                    ).fetchone()
                    if (
                        not asset
                        or asset["learner_id"] != learner_id
                        or asset["deleted_at"] is not None
                        or asset["purpose"] not in {"source_page", "source_document"}
                        or (asset["purpose"] == "source_document" and asset["id"] != document["original_asset_id"])
                    ):
                        raise APIError(404, "PAGE_ASSET_NOT_FOUND", "派生页面附件不可访问")
                transform = json_loads(row["transform_json"], {})
                if not isinstance(transform, dict):
                    transform = {}
                transform["rotation"] = rotation
                parsed.append({
                    "id": page_id,
                    "page_index": page_index,
                    "asset_id": asset["id"] if asset else None,
                    "object_key": asset["object_key"] if asset else None,
                    "transform_json": json_dumps(transform),
                    "status": "queued" if asset else "failed",
                    "failure_code": None if asset else (row["failure_code"] or "PAGE_ASSET_MISSING"),
                })
            if indexes != set(range(len(current))):
                raise APIError(422, "INVALID_PAGE_ORDER", "页面序号必须从 0 连续且不重复")
            # Avoid UNIQUE(document_id, page_index) collisions while swapping.
            conn.execute("UPDATE source_pages SET page_index=page_index+1000000 WHERE document_id=?", (document_id,))
            for page in parsed:
                conn.execute(
                    "UPDATE source_pages SET page_index=?,status=?,object_key=?,asset_id=?,failure_code=?,transform_json=? WHERE id=? AND document_id=?",
                    (page["page_index"], page["status"], page["object_key"], page["asset_id"], page["failure_code"], page["transform_json"], page["id"], document_id),
                )
            new_revision = document["revision"] + 1
            conn.execute("UPDATE source_documents SET revision=? WHERE id=?", (new_revision, document_id))
            # Any recognition or confirmation projection that references this
            # document must be rebuilt against the new page revision.  Keep
            # old rows for audit/source history, but make them non-confirmable.
            batches = conn.execute(
                "SELECT id FROM import_batches WHERE learner_id=? AND EXISTS (SELECT 1 FROM json_each(import_batches.document_ids_json) WHERE value=?)",
                (learner_id, document_id),
            ).fetchall()
            now = utc_now()
            for batch in batches:
                batch_id = batch["id"]
                conn.execute(
                    "UPDATE import_batches SET status='stale',revision=revision+1,processed_pages=0,failed_pages=0,updated_at=? WHERE id=?",
                    (now, batch_id),
                )
                conn.execute(
                    "UPDATE import_items SET status='stale',verification_status='needs_review',revision=revision+1,confirmed_at=NULL WHERE batch_id=?",
                    (batch_id,),
                )
                conn.execute(
                    "UPDATE jobs SET status='cancelled',error_code='STALE_DOCUMENT_REVISION',lease_token=NULL,lease_until=NULL,updated_at=? WHERE kind='document_analysis' AND status IN ('queued','running') AND json_extract(input_json,'$.batch_id')=?",
                    (now, batch_id),
                )
        audit(db, ctx, "patch_document_pages", "source_document", document_id, "accepted", {"revision": body.expected_revision + 1, "page_count": len(parsed)})
        return {"document_id": document_id, "revision": body.expected_revision + 1, "pages": parsed, "invalidated_batches": [batch["id"] for batch in batches]}

    @app.get("/api/v1/source-pages/{page_id}/content")
    def download_source_page(page_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            row = conn.execute("SELECT p.object_key,a.media_type FROM source_pages p JOIN source_documents d ON d.id=p.document_id JOIN assets a ON a.id=p.asset_id WHERE p.id=? AND d.learner_id=? AND a.learner_id=? AND a.deleted_at IS NULL", (page_id, learner_id, learner_id)).fetchone()
        if not row or not row["object_key"]:
            raise APIError(404, "SOURCE_PAGE_NOT_FOUND", "页面附件不存在")
        target = _contained_path(settings.attachment_dir, row["object_key"])
        if not target.is_file():
            raise APIError(503, "ASSET_UNAVAILABLE", "页面附件不可用", True)
        return FileResponse(target, media_type=row["media_type"], filename=Path(row["object_key"]).name)

    @app.post("/api/v1/import-batches", status_code=201)
    def create_batch(body: BatchRequest, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        document_ids = list(dict.fromkeys(body.document_ids))
        with db.session(write=True) as conn:
            placeholders = ",".join("?" for _ in document_ids)
            rows = conn.execute(
                f"SELECT d.id,d.page_count FROM source_documents d "
                f"JOIN assets a ON a.id=d.asset_id "
                f"WHERE d.learner_id=? AND d.status <> 'deleted' AND a.deleted_at IS NULL "
                f"AND d.id IN ({placeholders})",
                [learner_id, *document_ids],
            ).fetchall()
            if len(rows) != len(document_ids):
                raise APIError(404, "DOCUMENT_NOT_FOUND", "资料不存在")
            if body.answer_document_id and not conn.execute(
                "SELECT 1 FROM source_documents d JOIN assets a ON a.id=d.asset_id "
                "WHERE d.id=? AND d.learner_id=? AND d.kind='answer_key' "
                "AND d.status <> 'deleted' AND a.deleted_at IS NULL",
                (body.answer_document_id, learner_id),
            ).fetchone():
                raise APIError(404, "ANSWER_DOCUMENT_NOT_FOUND", "参考答案资料不存在")
            batch_id, now = new_id("batch"), utc_now()
            total = sum(row["page_count"] for row in rows)
            conn.execute("INSERT INTO import_batches(id,learner_id,document_ids_json,answer_document_id,status,total_pages,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", (batch_id, learner_id, json_dumps(document_ids), body.answer_document_id, "draft", total, now, now))
        return {"batch_id": batch_id, "status": "draft", "total_pages": total, "answer_document_id": body.answer_document_id}

    @app.post("/api/v1/import-batches/{batch_id}/analysis", status_code=202)
    def request_analysis(batch_id: str, request: Request, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        raw_key = request.headers.get("Idempotency-Key") or "default"
        with db.session(write=True) as conn:
            batch = conn.execute("SELECT * FROM import_batches WHERE id=? AND learner_id=?", (batch_id, learner_id)).fetchone()
            if not batch:
                raise APIError(404, "BATCH_NOT_FOUND", "批次不存在")
            # An exact retry must recover the accepted operation even if the
            # batch was cancelled or completed after the original request.
            idem_key = f"{raw_key}:revision:{batch['revision']}"
            request_body = {"batch_revision": batch["revision"]}
            prior = idempotent_result(conn, ctx, learner_id, "request_analysis", batch_id, idem_key, request_body)
            if prior:
                return prior
            if batch["status"] == "cancelled":
                raise APIError(409, "BATCH_CANCELLED", "已取消批次不能继续分析")
            if batch["status"] == "completed":
                raise APIError(409, "BATCH_ALREADY_COMPLETED", "已完成批次不能再次分析")
            # Scope retries to the batch revision so a rerun after a manual
            # correction cannot silently return the prior revision's job.
            job_id = enqueue(
                conn,
                learner_id,
                "document_analysis",
                {"batch_id": batch_id, "revision": batch["revision"]},
                f"analysis:{ctx.account_id}:{learner_id}:{batch_id}:{idem_key}",
            )
            conn.execute("UPDATE import_batches SET status='processing',updated_at=? WHERE id=? AND status IN ('draft','processing','partial_failed','stale')", (utc_now(), batch_id))
            result = {"request_id": new_id("request"), "run_id": new_id("run"), "job_id": job_id, "status": "queued"}
            save_idempotent(conn, ctx, learner_id, "request_analysis", batch_id, idem_key, request_body, result)
            return result

    @app.get("/api/v1/import-batches/{batch_id}")
    def get_batch(batch_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            batch = conn.execute("SELECT * FROM import_batches WHERE id=? AND learner_id=?", (batch_id, learner_id)).fetchone()
            if not batch:
                raise APIError(404, "BATCH_NOT_FOUND", "批次不存在")
            items = conn.execute("SELECT verdict,status,verification_status,revision FROM import_items WHERE batch_id=?", (batch_id,)).fetchall()
            pages = conn.execute("SELECT p.id,p.document_id,p.page_index,p.status,p.failure_code FROM source_pages p JOIN source_documents d ON d.id=p.document_id WHERE d.learner_id=? AND d.id IN (SELECT value FROM json_each((SELECT document_ids_json FROM import_batches WHERE id=?))) ORDER BY p.document_id,p.page_index", (learner_id, batch_id)).fetchall()
        result = dict(batch)
        result["document_ids"] = json_loads(result.pop("document_ids_json"), [])
        result["items"] = {"total": len(items), "by_verdict": {v: sum(1 for row in items if row["verdict"] == v) for v in ("correct", "incorrect", "partial", "unanswered", "undetermined")}}
        result["pages"] = [dict(row) for row in pages]
        return result

    @app.get("/api/v1/import-batches/{batch_id}/items")
    def get_batch_items(batch_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            if not conn.execute("SELECT 1 FROM import_batches WHERE id=? AND learner_id=?", (batch_id, learner_id)).fetchone():
                raise APIError(404, "BATCH_NOT_FOUND", "批次不存在")
            rows = conn.execute("SELECT * FROM import_items WHERE batch_id=? AND learner_id=? ORDER BY page_index,locator", (batch_id, learner_id)).fetchall()
        return {"items": [{**dict(row), "content": json_loads(row["content_json"], {}), "teacher_evidence": json_loads(row["teacher_evidence_json"], {})} for row in rows], "next_cursor": None}

    @app.post("/api/v1/import-batches/{batch_id}/cancel")
    def cancel_import_batch(batch_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        """Stop future analysis while retaining the original upload and page history."""
        learner_id = learner_for(ctx, db=db)
        cancelled_jobs: list[str] = []
        with db.session(write=True) as conn:
            batch = conn.execute("SELECT * FROM import_batches WHERE id=? AND learner_id=?", (batch_id, learner_id)).fetchone()
            if not batch:
                raise APIError(404, "BATCH_NOT_FOUND", "批次不存在")
            if batch["status"] == "cancelled":
                return {"batch_id": batch_id, "status": "cancelled", "cancelled_jobs": []}
            if batch["status"] == "completed":
                raise APIError(409, "BATCH_ALREADY_COMPLETED", "已完成批次不能取消")
            conn.execute("UPDATE source_pages SET status='cancelled' WHERE document_id IN (SELECT value FROM json_each(?)) AND status IN ('queued','processing')", (batch["document_ids_json"],))
            jobs = conn.execute("SELECT id,input_json,status FROM jobs WHERE learner_id=? AND kind='document_analysis' AND status IN ('queued','running')", (learner_id,)).fetchall()
            for job in jobs:
                if json_loads(job["input_json"], {}).get("batch_id") != batch_id:
                    continue
                conn.execute("UPDATE jobs SET status='cancelled',error_code='CANCELLED',lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=? AND status IN ('queued','running')", (utc_now(), job["id"]))
                cancelled_jobs.append(job["id"])
            conn.execute("UPDATE import_batches SET status='cancelled',updated_at=? WHERE id=?", (utc_now(), batch_id))
        audit(db, ctx, "cancel_import_batch", "import_batch", batch_id, "accepted", {"cancelled_jobs": cancelled_jobs})
        return {"batch_id": batch_id, "status": "cancelled", "cancelled_jobs": cancelled_jobs}

    @app.patch("/api/v1/import-items/{item_id}")
    def patch_item(item_id: str, body: ItemPatch, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        allowed_verdicts = {"correct", "incorrect", "partial", "unanswered", "undetermined"}
        if body.verdict and body.verdict not in allowed_verdicts:
            raise APIError(422, "INVALID_VERDICT", "判定类型不支持")
        with db.session(write=True) as conn:
            item = conn.execute("SELECT * FROM import_items WHERE id=? AND learner_id=?", (item_id, learner_id)).fetchone()
            if not item:
                raise APIError(404, "ITEM_NOT_FOUND", "候选题不存在")
            if item["status"] == "confirmed":
                raise APIError(409, "ITEM_ALREADY_CONFIRMED", "已确认候选题不能直接修改")
            if item["revision"] != body.expected_revision:
                raise APIError(409, "REVISION_CONFLICT", "候选题已更新")
            verdict = body.verdict or item["verdict"]
            evidence = body.evidence if body.evidence is not None else json_loads(item["teacher_evidence_json"], {})
            if verdict != "undetermined" and not evidence:
                raise APIError(422, "EVIDENCE_REQUIRED", "已判定项目必须有可追溯证据")
            content = body.content if body.content is not None else json_loads(item["content_json"], {})
            if body.objective_id:
                objective_for_learner(conn, learner_id, body.objective_id)
                content["objective_id"] = body.objective_id
            revision = item["revision"] + 1
            conn.execute("UPDATE import_items SET raw_answer=?,content_json=?,teacher_evidence_json=?,verdict=?,verification_status=?,status='ready',revision=? WHERE id=?", (body.raw_answer if body.raw_answer is not None else item["raw_answer"], json_dumps(content), json_dumps(evidence), verdict, "manual" if body.verdict else item["verification_status"], revision, item_id))
            conn.execute("INSERT INTO import_judgments(id,item_id,revision,verdict,evidence_json,basis_version,verification_status,created_at) VALUES (?,?,?,?,?,?,?,?)", (new_id("judgment"), item_id, revision, verdict, json_dumps(evidence), "manual-v1", "manual", utc_now()))
            conn.execute("UPDATE import_batches SET revision=revision+1,updated_at=? WHERE id=?", (utc_now(), item["batch_id"]))
        return {"item_id": item_id, "revision": revision, "verdict": verdict, "verification_status": "manual" if body.verdict else item["verification_status"]}

    @app.post("/api/v1/import-batches/{batch_id}/confirmation-challenges")
    def import_challenge(batch_id: str, body: ChallengeRequest, ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        learner_id = learner_for(ctx, db=db)
        with db.session(write=True) as conn:
            batch = conn.execute("SELECT revision,status FROM import_batches WHERE id=? AND learner_id=?", (batch_id, learner_id)).fetchone()
            if not batch:
                raise APIError(404, "BATCH_NOT_FOUND", "批次不存在")
            if batch["status"] == "cancelled":
                raise APIError(409, "BATCH_CANCELLED", "已取消批次不能确认")
            if batch["status"] == "stale":
                raise APIError(409, "BATCH_STALE", "资料页面已修订，请重新分析并复核")
            if batch["status"] == "completed":
                raise APIError(409, "BATCH_ALREADY_COMPLETED", "已完成批次不能再次确认")
            if body.expected_batch_revision is not None and batch["revision"] != body.expected_batch_revision:
                raise APIError(409, "REVISION_CONFLICT", "批次已更新，请重新读取并复核")
            requested, _ = reviewed_import_candidates(conn, batch_id, learner_id, body.items)
            versions = {"batch_revision": batch["revision"], "items": requested}
            return challenge_response(conn, ctx, learner_id, "confirm_import", batch_id, versions, settings)

    @app.post("/api/v1/import-batches/{batch_id}/confirmations", status_code=202)
    def confirm_import(batch_id: str, body: ConfirmationRequest, request: Request, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        key = request.headers.get("Idempotency-Key")
        if not key:
            raise APIError(422, "IDEMPOTENCY_REQUIRED", "批量确认必须带 Idempotency-Key")
        with db.session(write=True) as conn:
            prior = idempotent_result(conn, ctx, learner_id, "confirm_import", batch_id, key, body.model_dump())
            if prior:
                return prior
            batch = conn.execute("SELECT * FROM import_batches WHERE id=? AND learner_id=?", (batch_id, learner_id)).fetchone()
            if not batch:
                raise APIError(404, "BATCH_NOT_FOUND", "批次不存在")
            if batch["status"] == "cancelled":
                challenge = conn.execute(
                    "SELECT consumed_at FROM interaction_challenges WHERE id=? AND actor_account_id=? AND learner_id=? AND operation='confirm_import' AND resource_id=?",
                    (body.challenge_id, ctx.account_id, learner_id, batch_id),
                ).fetchone()
                if challenge and challenge["consumed_at"]:
                    raise APIError(409, "CHALLENGE_REPLAY", "交互挑战已经消费")
                raise APIError(409, "BATCH_CANCELLED", "已取消批次不能确认")
            if batch["status"] == "stale":
                raise APIError(409, "BATCH_STALE", "资料页面已修订，请重新分析并复核")
            if batch["status"] == "completed":
                challenge = conn.execute(
                    "SELECT consumed_at FROM interaction_challenges WHERE id=? AND actor_account_id=? AND learner_id=? AND operation='confirm_import' AND resource_id=?",
                    (body.challenge_id, ctx.account_id, learner_id, batch_id),
                ).fetchone()
                if challenge and challenge["consumed_at"]:
                    raise APIError(409, "CHALLENGE_REPLAY", "交互挑战已经消费")
                raise APIError(409, "BATCH_ALREADY_COMPLETED", "已完成批次不能再次确认")
            requested, reviewed_rows = reviewed_import_candidates(conn, batch_id, learner_id, body.items)
            versions = {"batch_revision": batch["revision"], "items": requested}
            consume_challenge(conn, ctx, learner_id, "confirm_import", batch_id, body.challenge_id, body.nonce, versions)
            operation_id = new_id("operation")
            confirmed = 0
            for item_id, expected_revision in requested.items():
                item = reviewed_rows[item_id]
                objective_id = json_loads(item["content_json"], {}).get("objective_id")
                if not objective_id:
                    objective = conn.execute("SELECT id FROM review_objectives ORDER BY created_at LIMIT 1").fetchone()
                    objective_id = objective["id"] if objective else None
                judgment = conn.execute("SELECT id FROM import_judgments WHERE item_id=? AND revision=? AND verification_status='manual' AND verdict=? ORDER BY created_at DESC LIMIT 1", (item_id, expected_revision, item["verdict"])).fetchone()
                # reviewed_import_candidates guarantees a matching judgment and evidence.
                if item["verdict"] in {"incorrect", "partial"} and objective_id:
                    entry = conn.execute("SELECT * FROM mistake_entries WHERE learner_id=? AND objective_id=? AND status='active' ORDER BY created_at LIMIT 1", (learner_id, objective_id)).fetchone()
                    if not entry:
                        entry_id = new_id("mistake")
                        conn.execute("INSERT INTO mistake_entries(id,learner_id,objective_id,status,diagnosis_status,created_at) VALUES (?,?,?,?,?,?)", (entry_id, learner_id, objective_id, "active", "draft", utc_now()))
                    else:
                        entry_id = entry["id"]
                    conn.execute("INSERT OR IGNORE INTO mistake_sources(id,entry_id,learner_id,source_kind,occurrence_id,item_locator,item_id,import_judgment_id,active,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (new_id("source"), entry_id, learner_id, "uploaded_work", item["occurrence_id"], item["locator"], item_id, judgment["id"] if judgment else None, 1, utc_now()))
                    _ensure_review_card(conn, learner_id, objective_id, settings=get_settings())
                conn.execute("UPDATE import_items SET status='confirmed',confirmed_at=? WHERE id=?", (utc_now(), item_id))
                confirmed += 1
            complete = conn.execute("SELECT COUNT(*) AS c FROM import_items WHERE batch_id=? AND status NOT IN ('confirmed','ignored','stale')", (batch_id,)).fetchone()["c"] == 0 and batch["failed_pages"] == 0
            status = "completed" if complete else batch["status"]
            result = {"request_id": new_id("request"), "operation_id": operation_id, "status": "completed" if complete else "partial", "selected_count": len(requested), "confirmed_count": confirmed, "failed": []}
            conn.execute("INSERT INTO batch_operations(id,batch_id,learner_id,status,selected_json,result_json,created_at,completed_at) VALUES (?,?,?,?,?,?,?,?)", (operation_id, batch_id, learner_id, result["status"], json_dumps(requested), json_dumps(result), utc_now(), utc_now()))
            conn.execute("UPDATE import_batches SET status=?,updated_at=? WHERE id=?", (status, utc_now(), batch_id))
            save_idempotent(conn, ctx, learner_id, "confirm_import", batch_id, key, body.model_dump(), result)
        audit(db, ctx, "confirm_import", "import_batch", batch_id, "accepted", {"confirmed_count": confirmed})
        return result

    @app.get("/api/v1/operations/{operation_id}")
    def get_operation(operation_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            row = conn.execute("SELECT * FROM batch_operations WHERE id=? AND learner_id=?", (operation_id, learner_id)).fetchone()
        if not row:
            raise APIError(404, "OPERATION_NOT_FOUND", "操作不存在")
        return {**dict(row), "selected": json_loads(row["selected_json"], {}), "result": json_loads(row["result_json"], {})}

    @app.get("/api/v1/mistakes")
    def list_mistakes(ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            rows = conn.execute(
                "SELECT m.*,o.code AS objective_code,o.title AS objective_title FROM mistake_entries m LEFT JOIN review_objectives o ON o.id=m.objective_id WHERE m.learner_id=? ORDER BY m.created_at DESC",
                (learner_id,),
            ).fetchall()
        return {"items": [dict(row) for row in rows], "next_cursor": None}

    @app.get("/api/v1/mistakes/{mistake_id}")
    def get_mistake(mistake_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            entry = conn.execute("SELECT * FROM mistake_entries WHERE id=? AND learner_id=?", (mistake_id, learner_id)).fetchone()
            if not entry:
                raise APIError(404, "MISTAKE_NOT_FOUND", "错题不存在")
            sources = conn.execute("SELECT id,source_kind,occurrence_id,item_locator,item_id,attempt_id,active,created_at FROM mistake_sources WHERE entry_id=? AND learner_id=? ORDER BY created_at", (mistake_id, learner_id)).fetchall()
            diagnoses = conn.execute("SELECT id,status,model_id,prompt_version,evidence_json,output_json,created_at FROM diagnoses WHERE mistake_id=? ORDER BY created_at DESC", (mistake_id,)).fetchall()
        return {"mistake": dict(entry), "sources": [dict(row) for row in sources], "diagnoses": [{**dict(row), "evidence": json_loads(row["evidence_json"], {}), "output": json_loads(row["output_json"], {})} for row in diagnoses]}

    @app.post("/api/v1/mistakes/{mistake_id}/retractions")
    def retract_mistake(mistake_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session(write=True) as conn:
            entry = conn.execute("SELECT id FROM mistake_entries WHERE id=? AND learner_id=?", (mistake_id, learner_id)).fetchone()
            if not entry:
                raise APIError(404, "MISTAKE_NOT_FOUND", "错题不存在")
            conn.execute("UPDATE mistake_entries SET status='retracted',archived_at=? WHERE id=?", (utc_now(), mistake_id))
            conn.execute("UPDATE mistake_sources SET active=0 WHERE entry_id=?", (mistake_id,))
        audit(db, ctx, "retract_mistake", "mistake", mistake_id, "accepted")
        return {"mistake_id": mistake_id, "status": "retracted"}

    @app.post("/api/v1/learning-drafts", status_code=201)
    def create_learning_draft(body: DraftRequest, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session(write=True) as conn:
            objective_for_learner(conn, learner_id, body.objective_id)
            draft_id = new_id("draft")
            conn.execute("INSERT INTO learning_drafts(id,learner_id,objective_id,content_json,created_at) VALUES (?,?,?,?,?)", (draft_id, learner_id, body.objective_id, json_dumps(body.content), utc_now()))
        return {"draft_id": draft_id, "revision": 1, "status": "draft"}

    @app.get("/api/v1/learning-drafts/{draft_id}")
    def get_learning_draft(draft_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        """Return the learner-scoped draft that a trusted UI is about to confirm."""
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            draft = conn.execute(
                "SELECT id,objective_id,content_json,revision,status,created_at FROM learning_drafts WHERE id=? AND learner_id=?",
                (draft_id, learner_id),
            ).fetchone()
        if not draft:
            raise APIError(404, "DRAFT_NOT_FOUND", "学习记录不存在")
        result = dict(draft)
        result["content"] = json_loads(result.pop("content_json"), {})
        return result

    @app.post("/api/v1/learning-drafts/{draft_id}/confirmation-challenges")
    def draft_challenge(draft_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        learner_id = learner_for(ctx, db=db)
        with db.session(write=True) as conn:
            draft = conn.execute("SELECT * FROM learning_drafts WHERE id=? AND learner_id=?", (draft_id, learner_id)).fetchone()
            if not draft:
                raise APIError(404, "DRAFT_NOT_FOUND", "学习记录不存在")
            return challenge_response(conn, ctx, learner_id, "confirm_learning", draft_id, {"revision": draft["revision"]}, settings)

    @app.post("/api/v1/learning-drafts/{draft_id}/confirmations")
    def confirm_draft(draft_id: str, body: DraftConfirmation, request: Request = None, ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        learner_id = learner_for(ctx, db=db)
        key = request.headers.get("Idempotency-Key") if request else None
        if not key:
            raise APIError(422, "IDEMPOTENCY_REQUIRED", "学习记录确认必须带 Idempotency-Key")
        with db.session(write=True) as conn:
            prior = idempotent_result(conn, ctx, learner_id, "confirm_learning", draft_id, key, body.model_dump())
            if prior:
                return prior
            draft = conn.execute("SELECT * FROM learning_drafts WHERE id=? AND learner_id=?", (draft_id, learner_id)).fetchone()
            if not draft:
                raise APIError(404, "DRAFT_NOT_FOUND", "学习记录不存在")
            draft_content = json_loads(draft["content_json"], {})
            if body.raw_content is not None and body.raw_content != draft_content:
                raise APIError(409, "DRAFT_CONTENT_MISMATCH", "确认内容与服务端学习草稿不一致")
            consume_challenge(conn, ctx, learner_id, "confirm_learning", draft_id, body.challenge_id, body.nonce, {"revision": draft["revision"]})
            if draft["status"] == "confirmed":
                return {"draft_id": draft_id, "status": "confirmed", "idempotent": True}
            now = utc_now()
            conn.execute("UPDATE learning_drafts SET status='confirmed' WHERE id=?", (draft_id,))
            conn.execute("INSERT INTO learning_events(id,learner_id,objective_id,event_type,source,assistance,accepted_at,metadata_json) VALUES (?,?,?,?,?,?,?,?)", (new_id("event"), learner_id, draft["objective_id"], "new_learning", "trusted_learning_input", "none", now, json_dumps({"content": draft_content})))
            card_id = _ensure_review_card(conn, learner_id, draft["objective_id"], settings, now)
            result = {"draft_id": draft_id, "status": "confirmed", "card_id": card_id}
            save_idempotent(conn, ctx, learner_id, "confirm_learning", draft_id, key, body.model_dump(), result)
        return result

    @app.post("/api/v1/mistakes/{mistake_id}/diagnoses", status_code=202)
    def request_diagnosis(mistake_id: str, body: DiagnosisRequest, ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        learner_id = learner_for(ctx, db=db)
        if not isinstance(settings, Settings):
            settings = app.state.settings
        # Provider/OCR/model work must not run while SQLite holds its writer
        # lock.  Read the minimal, learner-scoped evidence first, call the
        # provider outside the transaction, then atomically persist the
        # reviewable result after rechecking the resource.
        with db.session() as conn:
            entry = conn.execute("SELECT * FROM mistake_entries WHERE id=? AND learner_id=?", (mistake_id, learner_id)).fetchone()
            if not entry:
                raise APIError(404, "MISTAKE_NOT_FOUND", "错题不存在")
            source = conn.execute("SELECT item_id FROM mistake_sources WHERE entry_id=? AND active=1 ORDER BY created_at LIMIT 1", (mistake_id,)).fetchone()
            evidence = {"source_item_id": source["item_id"] if source else None, "requires_review": True, "external_call": False}
        provider_result = diagnosis_provider(settings.diagnosis_provider).diagnose(evidence)
        evidence.update({"provider_id": provider_result.provider_id, "provider_status": provider_result.status, "provider_evidence": provider_result.evidence})
        output = {**provider_result.payload, "evidence_steps": [], "hypotheses": [{"text": "需要补充学生步骤后再判断", "basis": "原始证据不足"}], "remedy_notes": "请补充解题步骤。", "diagnosis_status": provider_result.status, "provider_id": provider_result.provider_id}
        with db.session(write=True) as conn:
            if not conn.execute("SELECT 1 FROM mistake_entries WHERE id=? AND learner_id=?", (mistake_id, learner_id)).fetchone():
                raise APIError(404, "MISTAKE_NOT_FOUND", "错题不存在")
            diagnosis_id = new_id("diagnosis")
            conn.execute("INSERT INTO diagnoses(id,mistake_id,evidence_json,output_json,model_id,prompt_version,status,created_at) VALUES (?,?,?,?,?,?,?,?)", (diagnosis_id, mistake_id, json_dumps(evidence), json_dumps(output), body.model_id, body.prompt_version, "needs_review", utc_now()))
            conn.execute("UPDATE mistake_entries SET diagnosis_status='needs_review' WHERE id=?", (mistake_id,))
        return {"diagnosis_id": diagnosis_id, "job_id": None, "status": "needs_review"}

    @app.get("/api/v1/diagnoses/{diagnosis_id}")
    def get_diagnosis(diagnosis_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            row = conn.execute("SELECT d.* FROM diagnoses d JOIN mistake_entries m ON m.id=d.mistake_id WHERE d.id=? AND m.learner_id=?", (diagnosis_id, learner_id)).fetchone()
        if not row:
            raise APIError(404, "DIAGNOSIS_NOT_FOUND", "诊断不存在")
        return {**dict(row), "evidence": json_loads(row["evidence_json"], {}), "output": json_loads(row["output_json"], {})}

    @app.get("/api/v1/review-tasks")
    def review_tasks(ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        now = utc_now()
        with db.session() as conn:
            rows = conn.execute("SELECT c.*,o.code,o.title FROM review_cards c JOIN review_objectives o ON o.id=c.objective_id WHERE c.learner_id=? AND c.active=1 AND c.due_at<=? ORDER BY CASE c.state WHEN 'relearning' THEN 0 WHEN 'review' THEN 1 ELSE 2 END,c.due_at", (learner_id, now)).fetchall()
        return {"items": [dict(row) for row in rows], "as_of": now, "budget": {"max_items": 8, "suggested_minutes": 20}, "next_cursor": None}

    @app.get("/api/v1/progress")
    def progress(ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            cards = conn.execute("SELECT state,stage,COUNT(*) AS count FROM review_cards WHERE learner_id=? AND active=1 GROUP BY state,stage", (learner_id,)).fetchall()
            attempts = conn.execute("SELECT COUNT(*) AS total,SUM(CASE WHEN assessment_eligibility=1 THEN 1 ELSE 0 END) AS independent,SUM(CASE WHEN status='graded' THEN 1 ELSE 0 END) AS graded FROM attempts WHERE learner_id=?", (learner_id,)).fetchone()
        return {"learner_id": learner_id, "cards": [dict(row) for row in cards], "attempts": dict(attempts), "evidence_note": "仅可信服务端判分且无辅助的结果计入独立证据。"}

    @app.post("/api/v1/test-sessions", status_code=201)
    def create_test_session(body: TestSessionRequest, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        if body.mode not in {"independent", "practice"}:
            raise APIError(422, "INVALID_TEST_MODE", "测验模式不支持")
        with db.session(write=True) as conn:
            question = conn.execute("SELECT qv.*,q.objective_id,q.approval AS question_approval,q.visibility,q.learner_id AS owner_id FROM question_versions qv JOIN questions q ON q.id=qv.question_id WHERE qv.id=? AND qv.approval='approved' AND q.approval='approved'", (body.question_version_id,)).fetchone()
            if not question or (question["visibility"] == "private" and question["owner_id"] != learner_id):
                raise APIError(404, "QUESTION_NOT_FOUND", "题目不存在")
            card = None
            if body.card_id:
                card = conn.execute("SELECT * FROM review_cards WHERE id=? AND learner_id=? AND active=1", (body.card_id, learner_id)).fetchone()
                if not card:
                    raise APIError(404, "CARD_NOT_FOUND", "复习卡不存在")
                if body.mode == "independent" and _parse_iso(card["due_at"]) > datetime.now(timezone.utc):
                    raise APIError(409, "CARD_NOT_DUE", "该复习卡尚未到期")
                if conn.execute("SELECT 1 FROM test_items WHERE card_id=? AND status IN ('reserved','presented','grading_pending')", (body.card_id,)).fetchone():
                    raise APIError(409, "CARD_ALREADY_RESERVED", "该复习卡已有进行中的测验")
            session_id, item_id, cycle_id = new_id("session"), new_id("test_item"), new_id("cycle") if card else None
            conn.execute("INSERT INTO test_sessions(id,learner_id,mode,status,created_at) VALUES (?,?,?,?,?)", (session_id, learner_id, body.mode, "active", utc_now()))
            conn.execute("INSERT INTO test_items(id,session_id,learner_id,question_version_id,card_id,cycle_id,reserved_revision,status,presented_at) VALUES (?,?,?,?,?,?,?,?,?)", (item_id, session_id, learner_id, body.question_version_id, card["id"] if card else None, cycle_id, card["revision"] if card else None, "presented", utc_now()))
            content = json_loads(question["content_json"], {})
        return {"session_id": session_id, "items": [{"test_item_id": item_id, "question_version_id": body.question_version_id, "prompt": content.get("prompt", ""), "input_type": content.get("input_type", "text"), "status": "presented"}], "answer_key": None}

    @app.get("/api/v1/test-sessions/{session_id}")
    def get_test_session(session_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            session = conn.execute("SELECT * FROM test_sessions WHERE id=? AND learner_id=?", (session_id, learner_id)).fetchone()
            if not session:
                raise APIError(404, "SESSION_NOT_FOUND", "测验不存在")
            rows = conn.execute(
                "SELECT ti.*,qv.content_json,a.id AS attempt_id,a.status AS attempt_status "
                "FROM test_items ti JOIN question_versions qv ON qv.id=ti.question_version_id "
                "LEFT JOIN attempts a ON a.test_item_id=ti.id AND a.learner_id=ti.learner_id "
                "WHERE ti.session_id=?",
                (session_id,),
            ).fetchall()
        return {"session": dict(session), "items": [{"test_item_id": row["id"], "question_version_id": row["question_version_id"], "prompt": json_loads(row["content_json"], {}).get("prompt", ""), "status": row["status"], "assistance": row["assistance"], "attempt_id": row["attempt_id"], "attempt_status": row["attempt_status"]} for row in rows], "answer_key": None}

    @app.post("/api/v1/test-sessions/{session_id}/cancel")
    def cancel_session(session_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session(write=True) as conn:
            session = conn.execute("SELECT id FROM test_sessions WHERE id=? AND learner_id=?", (session_id, learner_id)).fetchone()
            if not session:
                raise APIError(404, "SESSION_NOT_FOUND", "测验不存在")
            conn.execute("UPDATE test_items SET status='cancelled' WHERE session_id=? AND status IN ('reserved','presented')", (session_id,))
            conn.execute("UPDATE test_sessions SET status='cancelled' WHERE id=?", (session_id,))
        return {"session_id": session_id, "status": "cancelled"}

    @app.post("/api/v1/test-items/{item_id}/hints")
    def request_hint(item_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session(write=True) as conn:
            row = conn.execute("SELECT ti.*,qv.content_json,q.objective_id FROM test_items ti JOIN question_versions qv ON qv.id=ti.question_version_id JOIN questions q ON q.id=qv.question_id WHERE ti.id=? AND ti.learner_id=?", (item_id, learner_id)).fetchone()
            if not row or row["status"] not in {"reserved", "presented"}:
                raise APIError(404, "TEST_ITEM_NOT_FOUND", "测验题项不存在")
            conn.execute("UPDATE test_items SET assistance='hint',status='presented' WHERE id=?", (item_id,))
            conn.execute("INSERT INTO learning_events(id,learner_id,objective_id,event_type,source,assistance,accepted_at,metadata_json) VALUES (?,?,?,?,?,?,?,?)", (new_id("event"), learner_id, row["objective_id"], "hint_exposed", "test", "hint", utc_now(), json_dumps({"test_item_id": item_id})))
            hint = json_loads(row["content_json"], {}).get("hint", "请先说明每一步代表什么，再计算终点。")
        return {"test_item_id": item_id, "assistance": "hint", "hint": hint}

    @app.post("/api/v1/test-items/{item_id}/submission-challenges")
    def submission_challenge(item_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        learner_id = learner_for(ctx, db=db)
        with db.session(write=True) as conn:
            item = conn.execute("SELECT ti.*,ts.mode AS session_mode FROM test_items ti JOIN test_sessions ts ON ts.id=ti.session_id WHERE ti.id=? AND ti.learner_id=? AND ti.status IN ('reserved','presented')", (item_id, learner_id)).fetchone()
            if not item:
                raise APIError(404, "TEST_ITEM_NOT_FOUND", "测验题项不存在")
            versions = {"question_version_id": item["question_version_id"], "card_id": item["card_id"], "reserved_revision": item["reserved_revision"]}
            return challenge_response(conn, ctx, learner_id, "submit_answer", item_id, versions, settings)

    @app.get("/api/v1/test-items/{item_id}")
    def get_test_item(item_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        """Return only frozen test presentation data; never expose the answer key."""
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            row = conn.execute(
                "SELECT ti.id,ti.question_version_id,ti.status,ti.assistance,ti.session_id,"
                "qv.content_json,q.objective_id,ts.mode AS session_mode "
                "FROM test_items ti "
                "JOIN question_versions qv ON qv.id=ti.question_version_id "
                "JOIN questions q ON q.id=qv.question_id "
                "JOIN test_sessions ts ON ts.id=ti.session_id "
                "WHERE ti.id=? AND ti.learner_id=?",
                (item_id, learner_id),
            ).fetchone()
        if not row or row["status"] not in {"reserved", "presented"}:
            raise APIError(404, "TEST_ITEM_NOT_FOUND", "测验题项不存在")
        content = json_loads(row["content_json"], {})
        return {
            "test_item_id": row["id"],
            "question_version_id": row["question_version_id"],
            "prompt": content.get("prompt", ""),
            "input_type": content.get("input_type", "text"),
            "status": row["status"],
            "assistance": row["assistance"],
            "session_mode": row["session_mode"],
            "objective_id": row["objective_id"],
        }

    @app.post("/api/v1/test-items/{item_id}/answers", status_code=202)
    def submit_answer(item_id: str, body: AnswerRequest, request: Request, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        key = request.headers.get("Idempotency-Key")
        if not key:
            raise APIError(422, "IDEMPOTENCY_REQUIRED", "答案提交必须带 Idempotency-Key")
        with db.session(write=True) as conn:
            prior = idempotent_result(conn, ctx, learner_id, "submit_answer", item_id, key, body.model_dump())
            if prior:
                return prior
            item = conn.execute("SELECT ti.*,ts.mode AS session_mode FROM test_items ti JOIN test_sessions ts ON ts.id=ti.session_id WHERE ti.id=? AND ti.learner_id=? AND ti.status IN ('reserved','presented')", (item_id, learner_id)).fetchone()
            if not item:
                existing = conn.execute("SELECT id,status FROM attempts WHERE test_item_id=?", (item_id,)).fetchone()
                if existing:
                    return {"attempt_id": existing["id"], "status": existing["status"], "idempotent": True}
                raise APIError(404, "TEST_ITEM_NOT_FOUND", "测验题项不存在")
            versions = {"question_version_id": item["question_version_id"], "card_id": item["card_id"], "reserved_revision": item["reserved_revision"]}
            consume_challenge(conn, ctx, learner_id, "submit_answer", item_id, body.challenge_id, body.nonce, versions)
            attempt_id = new_id("attempt")
            now = utc_now()
            eligible = item["assistance"] == "none" and item["session_mode"] == "independent"
            conn.execute("INSERT INTO attempts(id,test_item_id,learner_id,raw_answer,submitted_at,assistance,assessment_eligibility,status,idempotency_key) VALUES (?,?,?,?,?,?,?,?,?)", (attempt_id, item_id, learner_id, body.raw_answer, now, item["assistance"], 1 if eligible else 0, "grading_pending", key))
            conn.execute("UPDATE test_items SET status='grading_pending' WHERE id=?", (item_id,))
            job_id = enqueue(conn, learner_id, "grade_attempt", {"attempt_id": attempt_id}, f"grade:{attempt_id}")
            result = {"attempt_id": attempt_id, "job_id": job_id, "status": "grading_pending", "assessment_eligibility": eligible}
            save_idempotent(conn, ctx, learner_id, "submit_answer", item_id, key, body.model_dump(), result)
        return result

    @app.get("/api/v1/attempts/{attempt_id}")
    def get_attempt(attempt_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            row = conn.execute("SELECT a.id,a.test_item_id,a.submitted_at,a.assistance,a.assessment_eligibility,a.status,g.outcome,g.score,g.feedback,g.created_at AS graded_at,ti.cycle_id,ti.card_id FROM attempts a JOIN test_items ti ON ti.id=a.test_item_id LEFT JOIN grade_versions g ON g.attempt_id=a.id WHERE a.id=? AND a.learner_id=? ORDER BY g.created_at DESC LIMIT 1", (attempt_id, learner_id)).fetchone()
            requests = conn.execute("SELECT id,status,reason,details_json,resolution_json,created_at,updated_at FROM review_requests WHERE attempt_id=? AND learner_id=?", (attempt_id, learner_id)).fetchall()
        if not row:
            raise APIError(404, "ATTEMPT_NOT_FOUND", "作答不存在")
        result = dict(row)
        result["review_requests"] = [
            {**dict(request), "details": json_loads(request["details_json"], {}), "resolution": json_loads(request["resolution_json"], {})}
            for request in requests
        ]
        return result

    @app.post("/api/v1/attempts/{attempt_id}/review-requests", status_code=202)
    def request_attempt_review(attempt_id: str, body: ReviewRequestRequest, request: Request, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        """Create one learner-scoped review request without changing a grade."""
        learner_id = learner_for(ctx, db=db)
        key = request.headers.get("Idempotency-Key")
        if not key:
            raise APIError(422, "IDEMPOTENCY_REQUIRED", "复核申请必须带 Idempotency-Key")
        payload = body.model_dump()
        with db.session(write=True) as conn:
            prior = idempotent_result(conn, ctx, learner_id, "request_attempt_review", attempt_id, key, payload)
            if prior:
                return prior
            attempt = conn.execute(
                "SELECT id,status FROM attempts WHERE id=? AND learner_id=?",
                (attempt_id, learner_id),
            ).fetchone()
            if not attempt:
                raise APIError(404, "ATTEMPT_NOT_FOUND", "作答不存在")
            existing = conn.execute(
                "SELECT id,status FROM review_requests WHERE attempt_id=? AND learner_id=?",
                (attempt_id, learner_id),
            ).fetchone()
            if existing:
                raise APIError(409, "REVIEW_REQUEST_EXISTS", "该作答已有复核申请")
            now = utc_now()
            review_id = new_id("review")
            conn.execute(
                "INSERT INTO review_requests(id,attempt_id,learner_id,requested_by_account_id,reason,details_json,status,resolution_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (review_id, attempt_id, learner_id, ctx.account_id, body.reason, json_dumps(body.details), "requested", "{}", now, now),
            )
            result = {
                "review_request_id": review_id,
                "attempt_id": attempt_id,
                "status": "requested",
                "grade_unchanged": True,
            }
            save_idempotent(conn, ctx, learner_id, "request_attempt_review", attempt_id, key, payload, result)
        audit(db, ctx, "request_attempt_review", "review_request", review_id, "accepted", {"grade_changed": False})
        return result

    @app.post("/api/v1/admin/reviews/{review_request_id}/decisions", status_code=202)
    def decide_review_request(review_request_id: str, body: ReviewDecisionRequest, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        """Record a scoped review decision; score changes require a separate,
        versioned grade operation and are intentionally not implicit here."""
        if ctx.role not in {"admin", "reviewer"}:
            raise APIError(403, "FORBIDDEN", "需要复核权限")
        decisions = {"resolve": "resolved", "approve": "resolved", "dismiss": "dismissed", "reject": "dismissed", "in_review": "in_review"}
        status = decisions.get(body.decision)
        if not status:
            raise APIError(422, "INVALID_REVIEW_DECISION", "复核裁决只能是 resolve、dismiss、in_review")
        with db.session(write=True) as conn:
            review = conn.execute("SELECT * FROM review_requests WHERE id=?", (review_request_id,)).fetchone()
            if not review:
                raise APIError(404, "REVIEW_REQUEST_NOT_FOUND", "复核申请不存在")
            ensure_access(conn, ctx.account_id, review["learner_id"], {"admin", "reviewer"})
            if review["status"] in {"resolved", "dismissed", "cancelled"} and status != review["status"]:
                raise APIError(409, "REVIEW_REQUEST_CLOSED", "复核申请已经关闭")
            now = utc_now()
            resolution = {"decision": body.decision, "note": body.note, "decided_by_account_id": ctx.account_id, "grade_unchanged": True}
            conn.execute("UPDATE review_requests SET status=?,resolution_json=?,updated_at=? WHERE id=?", (status, json_dumps(resolution), now, review_request_id))
        audit(db, ctx, "decide_review_request", "review_request", review_request_id, "accepted", {"status": status, "grade_changed": False})
        return {"review_request_id": review_request_id, "status": status, "grade_unchanged": True, "resolution": resolution}

    @app.post("/api/v1/visual-jobs", status_code=202)
    def create_visual_job(body: VisualJobRequest, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        # Resolve the learner scope first so an inaccessible objective never
        # receives a misleading template-registry error.
        if body.objective_id:
            with db.session() as conn:
                objective_for_learner(conn, learner_id, body.objective_id)
        if body.template_id != "signed_number_subtraction":
            raise APIError(422, "TEMPLATE_NOT_AVAILABLE", "V1 只接入已审核数轴模板")
        try:
            start = int(body.parameters["start"])
            subtrahend = int(body.parameters["subtrahend"])
        except (KeyError, TypeError, ValueError):
            raise APIError(422, "INVALID_TEMPLATE_PARAMETERS", "数轴模板需要整数 start 和 subtrahend")
        if not (-100 <= start <= 100 and -100 <= subtrahend <= 100):
            raise APIError(422, "INVALID_TEMPLATE_PARAMETERS", "参数超出数轴模板范围")
        with db.session(write=True) as conn:
            template = conn.execute("SELECT * FROM visual_templates WHERE template_id=? AND version=? AND approval='approved'", (body.template_id, body.template_version)).fetchone()
            if not template:
                raise APIError(422, "TEMPLATE_NOT_APPROVED", "模板版本未审核")
            result = start - subtrahend
            spec = {"schema_version": "visual-spec-v1", "template_id": body.template_id, "template_version": body.template_version, "knowledge_point_id": None, "review_objective_id": body.objective_id, "purpose": body.purpose, "parameters": {"start": start, "subtrahend": subtrahend}, "computed": {"result": result, "direction": "right" if subtrahend < 0 else "left", "steps": abs(subtrahend)}, "steps": ["predict", "transform", "move", "compare", "explain"], "hint_level": "worked_example", "alternative_text": f"从 {start} 出发，减去 {subtrahend}，终点为 {result}。"}
            asset_id = new_id("visual")
            conn.execute("INSERT INTO visual_assets(id,learner_id,template_id,template_version,spec_json,visibility,approval,created_at) VALUES (?,?,?,?,?,?,?,?)", (asset_id, learner_id, body.template_id, body.template_version, json_dumps(spec), "private", "approved", utc_now()))
        return {"asset_id": asset_id, "job_id": None, "status": "ready", "static_fallback": True, "spec": spec}

    @app.get("/api/v1/visual-assets/{asset_id}")
    def get_visual_asset(asset_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            row = conn.execute("SELECT * FROM visual_assets WHERE id=? AND approval='approved' AND (learner_id=? OR visibility='shared')", (asset_id, learner_id)).fetchone()
        if not row:
            raise APIError(404, "ASSET_NOT_FOUND", "教学素材不存在")
        return {"asset_id": asset_id, "template_id": row["template_id"], "template_version": row["template_version"], "spec": json_loads(row["spec_json"], {}), "static_fallback": True}

    @app.post("/api/v1/visual-assets/{asset_id}/issues")
    def issue_visual_asset(asset_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session(write=True) as conn:
            row = conn.execute("SELECT * FROM visual_assets WHERE id=? AND learner_id=? AND approval='approved'", (asset_id, learner_id)).fetchone()
            if not row:
                raise APIError(404, "ASSET_NOT_FOUND", "教学素材不存在")
            spec = json_loads(row["spec_json"], {})
            event_id = new_id("media")
            objective_id = spec.get("review_objective_id")
            conn.execute("INSERT INTO media_events(id,learner_id,objective_id,asset_id,kind,issued_at) VALUES (?,?,?,?,?,?)", (event_id, learner_id, objective_id, asset_id, "issued", utc_now()))
        return {"asset_id": asset_id, "media_event_id": event_id, "spec": spec, "status": "issued"}

    @app.post("/api/v1/variant-jobs", status_code=202)
    def variant_job(body: dict[str, Any], ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        objective_id = body.get("objective_id")
        if not objective_id:
            raise APIError(422, "OBJECTIVE_REQUIRED", "需要 objective_id")
        with db.session(write=True) as conn:
            source_question_version_id = body.get("source_question_version_id")
            if source_question_version_id is not None and not isinstance(source_question_version_id, str):
                raise APIError(422, "VARIANT_REQUEST_INVALID", "source_question_version_id 必须是字符串")
            validate_variant_source(conn, learner_id, objective_id, source_question_version_id)
            job_id = enqueue(conn, learner_id, "variant_generation", {"objective_id": objective_id, "source_question_version_id": source_question_version_id or None}, f"variant:{learner_id}:{objective_id}:{source_question_version_id or 'none'}")
        return {"job_id": job_id, "status": "queued", "approval_required": True}

    @app.post("/api/v1/agent-runs", status_code=201)
    def create_agent_run(body: AgentRunRequest, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        if any(action in FORBIDDEN_AGENT_ACTIONS or action not in ALLOWED_AGENT_ACTIONS for action in body.allowed_actions):
            raise APIError(403, "AGENT_ACTION_FORBIDDEN", "Agent 动作不在允许清单")
        run_id = new_id("agent")
        # Keep the durable budget start at sub-second precision. Business
        # timestamps use second precision, but truncation could consume a
        # short budget before the first step reaches this endpoint.
        started_at = datetime.now(timezone.utc).isoformat()
        with db.session(write=True) as conn:
            conn.execute("INSERT INTO agent_runs(id,learner_id,goal,allowed_actions_json,budget_steps,budget_ms,budget_started_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (run_id, learner_id, body.goal, json_dumps(body.allowed_actions), body.budget_steps, body.budget_ms, started_at, started_at, started_at))
        return {"run_id": run_id, "status": "running", "allowed_actions": body.allowed_actions, "budget_steps": body.budget_steps, "budget_ms": body.budget_ms}

    @app.post("/api/v1/agent-runs/{run_id}/steps")
    def agent_step(run_id: str, body: AgentStepRequest, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session(write=True) as conn:
            run = conn.execute("SELECT * FROM agent_runs WHERE id=? AND learner_id=?", (run_id, learner_id)).fetchone()
            if not run:
                raise APIError(404, "AGENT_RUN_NOT_FOUND", "Agent 运行不存在")
            if run["status"] != "running":
                raise APIError(409, "AGENT_RUN_STOPPED", "Agent 运行已停止")
            elapsed_ms = _elapsed_budget_ms(run["budget_started_at"] or run["created_at"])
            if elapsed_ms >= run["budget_ms"]:
                conn.execute("UPDATE agent_runs SET status='stopped',stop_reason='time_budget',updated_at=? WHERE id=?", (utc_now(), run_id))
                return {"status": "stopped", "stop_reason": "time_budget", "elapsed_ms": elapsed_ms}
            actions = set(json_loads(run["allowed_actions_json"], []))
            if body.action in FORBIDDEN_AGENT_ACTIONS or body.action not in actions:
                raise APIError(403, "AGENT_ACTION_FORBIDDEN", "Agent 动作不在允许清单")
            count = conn.execute("SELECT COUNT(*) AS c FROM agent_steps WHERE run_id=?", (run_id,)).fetchone()["c"]
            if count >= run["budget_steps"]:
                conn.execute("UPDATE agent_runs SET status='stopped',stop_reason='step_budget',updated_at=? WHERE id=?", (utc_now(), run_id))
                raise APIError(429, "AGENT_BUDGET_EXCEEDED", "Agent 步数预算已用尽")
            result: dict[str, Any]
            if body.action == "list_learners":
                rows = conn.execute("SELECT l.id,l.display_name FROM learners l JOIN learner_access a ON a.learner_id=l.id WHERE a.account_id=? AND a.active=1", (ctx.account_id,)).fetchall()
                result = {"items": [dict(row) for row in rows]}
            elif body.action == "get_review_tasks":
                rows = conn.execute("SELECT id,objective_id,state,stage,due_at FROM review_cards WHERE learner_id=? AND active=1 AND due_at<=?", (learner_id, utc_now())).fetchall()
                result = {"items": [dict(row) for row in rows]}
            elif body.action == "get_mistakes":
                rows = conn.execute(
                    "SELECT m.*,o.code AS objective_code,o.title AS objective_title "
                    "FROM mistake_entries m LEFT JOIN review_objectives o ON o.id=m.objective_id "
                    "WHERE m.learner_id=? ORDER BY m.created_at DESC",
                    (learner_id,),
                ).fetchall()
                result = {"items": [dict(row) for row in rows], "next_cursor": None}
            elif body.action == "request_document_analysis":
                batch_id = body.input.get("batch_id")
                if not isinstance(batch_id, str) or not batch_id:
                    raise APIError(422, "BATCH_REQUIRED", "request_document_analysis 需要 batch_id")
                batch = conn.execute("SELECT * FROM import_batches WHERE id=? AND learner_id=?", (batch_id, learner_id)).fetchone()
                if not batch:
                    raise APIError(404, "BATCH_NOT_FOUND", "批次不存在")
                if batch["status"] == "cancelled":
                    raise APIError(409, "BATCH_CANCELLED", "已取消批次不能继续分析")
                if batch["status"] == "completed":
                    raise APIError(409, "BATCH_ALREADY_COMPLETED", "已完成批次不能再次分析")
                request_key = f"agent-analysis:{run_id}:{count}:revision:{batch['revision']}"
                job_id = enqueue(
                    conn,
                    learner_id,
                    "document_analysis",
                    {"batch_id": batch_id, "revision": batch["revision"]},
                    request_key,
                )
                conn.execute(
                    "UPDATE import_batches SET status='processing',updated_at=? "
                    "WHERE id=? AND status IN ('draft','processing','partial_failed','stale')",
                    (utc_now(), batch_id),
                )
                result = {"batch_id": batch_id, "job_id": job_id, "status": "queued", "revision": batch["revision"]}
            elif body.action == "request_diagnosis":
                mistake_id = body.input.get("mistake_id")
                if not isinstance(mistake_id, str) or not mistake_id:
                    raise APIError(422, "MISTAKE_REQUIRED", "request_diagnosis 需要 mistake_id")
                if not conn.execute("SELECT 1 FROM mistake_entries WHERE id=? AND learner_id=?", (mistake_id, learner_id)).fetchone():
                    raise APIError(404, "MISTAKE_NOT_FOUND", "错题不存在")
                model_id = body.input.get("model_id", "mock-diagnosis-v1")
                prompt_version = body.input.get("prompt_version", "diagnose-v1")
                if not isinstance(model_id, str) or not isinstance(prompt_version, str):
                    raise APIError(422, "DIAGNOSIS_REQUEST_INVALID", "诊断参数无效")
                job_id = enqueue(
                    conn,
                    learner_id,
                    "diagnosis",
                    {"mistake_id": mistake_id, "model_id": model_id, "prompt_version": prompt_version},
                    f"agent-diagnosis:{run_id}:{count}:{mistake_id}",
                )
                result = {"mistake_id": mistake_id, "job_id": job_id, "status": "queued", "review_required": True}
            elif body.action == "request_variant":
                objective_id = body.input.get("objective_id")
                if not isinstance(objective_id, str) or not objective_id:
                    raise APIError(422, "OBJECTIVE_REQUIRED", "request_variant 需要 objective_id")
                source_question_version_id = body.input.get("source_question_version_id")
                if source_question_version_id is not None and not isinstance(source_question_version_id, str):
                    raise APIError(422, "VARIANT_REQUEST_INVALID", "source_question_version_id 必须是字符串")
                validate_variant_source(conn, learner_id, objective_id, source_question_version_id)
                job_id = enqueue(
                    conn,
                    learner_id,
                    "variant_generation",
                    {"objective_id": objective_id, "source_question_version_id": source_question_version_id},
                    f"agent-variant:{run_id}:{count}:{objective_id}:{source_question_version_id or 'none'}",
                )
                result = {"objective_id": objective_id, "job_id": job_id, "status": "queued", "approval_required": True}
            elif body.action == "request_hint":
                test_item_id = body.input.get("test_item_id")
                if not isinstance(test_item_id, str) or not test_item_id:
                    raise APIError(422, "TEST_ITEM_REQUIRED", "request_hint 需要 test_item_id")
                row = conn.execute(
                    "SELECT ti.*,qv.content_json,q.objective_id FROM test_items ti "
                    "JOIN question_versions qv ON qv.id=ti.question_version_id "
                    "JOIN questions q ON q.id=qv.question_id "
                    "WHERE ti.id=? AND ti.learner_id=?",
                    (test_item_id, learner_id),
                ).fetchone()
                if not row or row["status"] not in {"reserved", "presented"}:
                    raise APIError(404, "TEST_ITEM_NOT_FOUND", "测验题项不存在")
                conn.execute("UPDATE test_items SET assistance='hint',status='presented' WHERE id=?", (test_item_id,))
                conn.execute(
                    "INSERT INTO learning_events(id,learner_id,objective_id,event_type,source,assistance,accepted_at,metadata_json) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (new_id("event"), learner_id, row["objective_id"], "hint_exposed", "test", "hint", utc_now(), json_dumps({"test_item_id": test_item_id, "agent_run_id": run_id})),
                )
                hint = json_loads(row["content_json"], {}).get("hint", "请先说明每一步代表什么，再计算终点。")
                result = {"test_item_id": test_item_id, "assistance": "hint", "hint": hint}
            elif body.action == "request_visual":
                template_id = body.input.get("template_id", "signed_number_subtraction")
                template_version = body.input.get("template_version", "1.0.0")
                parameters = body.input.get("parameters", {})
                objective_id = body.input.get("objective_id")
                if template_id != "signed_number_subtraction" or not isinstance(parameters, dict):
                    raise APIError(422, "INVALID_TEMPLATE_PARAMETERS", "V1 只接入已审核数轴模板")
                if objective_id is not None:
                    if not isinstance(objective_id, str):
                        raise APIError(404, "OBJECTIVE_NOT_FOUND", "目标不存在")
                    objective_for_learner(conn, learner_id, objective_id)
                try:
                    start = int(parameters["start"])
                    subtrahend = int(parameters["subtrahend"])
                except (KeyError, TypeError, ValueError):
                    raise APIError(422, "INVALID_TEMPLATE_PARAMETERS", "数轴模板需要整数 start 和 subtrahend")
                if not (-100 <= start <= 100 and -100 <= subtrahend <= 100):
                    raise APIError(422, "INVALID_TEMPLATE_PARAMETERS", "参数超出数轴模板范围")
                template = conn.execute(
                    "SELECT 1 FROM visual_templates WHERE template_id=? AND version=? AND approval='approved'",
                    (template_id, template_version),
                ).fetchone()
                if not template:
                    raise APIError(422, "TEMPLATE_NOT_APPROVED", "模板版本未审核")
                result_value = start - subtrahend
                spec = {
                    "schema_version": "visual-spec-v1",
                    "template_id": template_id,
                    "template_version": template_version,
                    "knowledge_point_id": None,
                    "review_objective_id": objective_id,
                    "purpose": body.input.get("purpose", "teach"),
                    "parameters": {"start": start, "subtrahend": subtrahend},
                    "computed": {"result": result_value, "direction": "right" if subtrahend < 0 else "left", "steps": abs(subtrahend)},
                    "steps": ["predict", "transform", "move", "compare", "explain"],
                    "hint_level": "worked_example",
                    "alternative_text": f"从 {start} 出发，减去 {subtrahend}，终点为 {result_value}。",
                }
                asset_id = new_id("visual")
                conn.execute(
                    "INSERT INTO visual_assets(id,learner_id,template_id,template_version,spec_json,visibility,approval,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (asset_id, learner_id, template_id, template_version, json_dumps(spec), "private", "approved", utc_now()),
                )
                result = {"asset_id": asset_id, "job_id": None, "status": "ready", "static_fallback": True, "spec": spec}
            elif body.action == "get_attempt":
                attempt_id = body.input.get("attempt_id")
                if not isinstance(attempt_id, str) or not attempt_id:
                    raise APIError(422, "ATTEMPT_REQUIRED", "get_attempt 需要 attempt_id")
                row = conn.execute(
                    "SELECT a.id,a.test_item_id,a.submitted_at,a.assistance,a.assessment_eligibility,a.status,"
                    "g.outcome,g.score,g.feedback,g.created_at AS graded_at,ti.cycle_id,ti.card_id "
                    "FROM attempts a JOIN test_items ti ON ti.id=a.test_item_id "
                    "LEFT JOIN grade_versions g ON g.attempt_id=a.id "
                    "WHERE a.id=? AND a.learner_id=? ORDER BY g.created_at DESC LIMIT 1",
                    (attempt_id, learner_id),
                ).fetchone()
                if not row:
                    raise APIError(404, "ATTEMPT_NOT_FOUND", "作答不存在")
                result = dict(row)
            elif body.action == "get_progress":
                cards = conn.execute("SELECT state,stage,COUNT(*) AS count FROM review_cards WHERE learner_id=? AND active=1 GROUP BY state,stage", (learner_id,)).fetchall()
                attempts = conn.execute("SELECT COUNT(*) AS total,SUM(CASE WHEN assessment_eligibility=1 THEN 1 ELSE 0 END) AS independent,SUM(CASE WHEN status='graded' THEN 1 ELSE 0 END) AS graded FROM attempts WHERE learner_id=?", (learner_id,)).fetchone()
                result = {"learner_id": learner_id, "cards": [dict(row) for row in cards], "attempts": dict(attempts), "evidence_note": "仅可信服务端判分且无辅助的结果计入独立证据。"}
            elif body.action == "start_trusted_interaction":
                operation = body.input.get("operation")
                resource_id = body.input.get("resource_id")
                if (
                    operation not in {"confirm_import", "confirm_learning", "confirm_draft_interactively", "submit_answer"}
                    or not isinstance(resource_id, str)
                    or not resource_id
                    or (operation == "confirm_import" and not isinstance(body.input.get("items"), list))
                ):
                    raise APIError(422, "INTERACTION_REQUEST_INVALID", "可信交互需要受支持的 operation 和 resource_id")
                # The agent can ask the adapter to open a trusted UI handoff,
                # but it never receives a nonce and cannot consume a challenge.
                result = {
                    "status": "requires_trusted_ui",
                    "operation": operation,
                    "resource_id": resource_id,
                    "ui_only": True,
                }
            else:
                raise APIError(501, "AGENT_ACTION_NOT_IMPLEMENTED", "允许清单中的 Agent 动作尚未实现")
            step_id = new_id("agent_step")
            conn.execute("INSERT INTO agent_steps(id,run_id,step_index,action,input_json,result_json,created_at) VALUES (?,?,?,?,?,?,?)", (step_id, run_id, count, body.action, json_dumps(body.input), json_dumps(result), utc_now()))
            elapsed_ms = _elapsed_budget_ms(run["budget_started_at"] or run["created_at"])
            if elapsed_ms >= run["budget_ms"]:
                conn.execute("UPDATE agent_runs SET status='stopped',stop_reason='time_budget',updated_at=? WHERE id=?", (utc_now(), run_id))
                return {"step_id": step_id, "status": "stopped", "stop_reason": "time_budget", "elapsed_ms": elapsed_ms, "result": result}
        return {"step_id": step_id, "status": "running", "result": result}

    @app.get("/api/v1/agent-runs/{run_id}")
    def get_agent_run(run_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            run = conn.execute("SELECT * FROM agent_runs WHERE id=? AND learner_id=?", (run_id, learner_id)).fetchone()
            if not run:
                raise APIError(404, "AGENT_RUN_NOT_FOUND", "Agent 运行不存在")
            steps = conn.execute("SELECT * FROM agent_steps WHERE run_id=? ORDER BY step_index", (run_id,)).fetchall()
        return {"run": {**dict(run), "allowed_actions": json_loads(run["allowed_actions_json"], [])}, "steps": [{**dict(row), "input": json_loads(row["input_json"], {}), "result": json_loads(row["result_json"], {})} for row in steps]}

    @app.get("/api/v1/jobs/{job_id}")
    def get_job(job_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            row = conn.execute("SELECT id,kind,status,attempts,error_code,result_json,created_at,updated_at FROM jobs WHERE id=? AND (learner_id=? OR learner_id IS NULL)", (job_id, learner_id)).fetchone()
        if not row:
            raise APIError(404, "JOB_NOT_FOUND", "任务不存在")
        return {**dict(row), "result": json_loads(row["result_json"], None)}

    @app.post("/api/v1/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        """Cancel queued/running work; a late worker result cannot commit after this transition."""
        learner_id = learner_for(ctx, db=db)
        with db.session(write=True) as conn:
            row = conn.execute("SELECT status FROM jobs WHERE id=? AND learner_id=?", (job_id, learner_id)).fetchone()
            if not row:
                raise APIError(404, "JOB_NOT_FOUND", "任务不存在")
            if row["status"] in {"succeeded", "failed", "cancelled"}:
                return {"job_id": job_id, "status": row["status"], "idempotent": True}
            conn.execute("UPDATE jobs SET status='cancelled',error_code='CANCELLED',lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=? AND learner_id=? AND status IN ('queued','running')", (utc_now(), job_id, learner_id))
        return {"job_id": job_id, "status": "cancelled"}

    @app.post("/internal/jobs/run-once")
    def run_job(_: None = Depends(admin_secret), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        return run_worker_once(db, settings)

    @app.get("/api/v1/assets/{asset_id}")
    def download_asset(asset_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            row = conn.execute("SELECT * FROM assets WHERE id=? AND (learner_id=? OR visibility='shared') AND deleted_at IS NULL", (asset_id, learner_id)).fetchone()
        if not row:
            raise APIError(404, "ASSET_NOT_FOUND", "附件不存在")
        target = _contained_path(settings.attachment_dir, row["object_key"])
        if not target.is_file():
            raise APIError(503, "ASSET_UNAVAILABLE", "附件存储不可用", True)
        return FileResponse(target, media_type=row["media_type"], filename=Path(row["object_key"]).name)

    @app.post("/api/v1/admin/exports", status_code=202)
    def export_data(body: dict[str, Any], ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        require_admin(ctx)
        if not isinstance(settings, Settings):  # direct route tests bypass FastAPI dependency injection
            settings = app.state.settings
        learner_id = body.get("learner_id")
        if not learner_id:
            raise APIError(422, "LEARNER_REQUIRED", "需要 learner_id")
        export_id = new_id("export")
        export_dir = settings.export_dir or (settings.data_dir / "exports")
        object_key = f"{learner_id}/{export_id}.json"
        target = export_dir / object_key
        temporary = target.with_suffix(target.suffix + ".tmp")
        with db.session(write=True) as conn:
            ensure_access(conn, ctx.account_id, learner_id, {"admin", "guardian"})
            snapshot = _learner_export(conn, learner_id, ctx.account_id, export_id)
            conn.execute("INSERT INTO export_jobs(id,learner_id,requested_by_account_id,scope_json,status,artifact_key,created_at) VALUES (?,?,?,?,?,?,?)", (export_id, learner_id, ctx.account_id, json_dumps({"learner_id": learner_id}), "queued", object_key, utc_now()))
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            encoded = (json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
            temporary.write_bytes(encoded)
            temporary.replace(target)
            digest = hashlib.sha256(encoded).hexdigest()
            with db.session(write=True) as conn:
                conn.execute("UPDATE export_jobs SET status='completed',artifact_sha256=?,artifact_byte_size=?,completed_at=? WHERE id=?", (digest, len(encoded), utc_now(), export_id))
            audit(db, ctx, "export_data", "export", export_id, "accepted", {"learner_id": learner_id, "external_delivery": False})
            return {"export_id": export_id, "status": "completed", "learner_id": learner_id, "artifact_size": len(encoded), "sha256": digest, "download_path": f"/api/v1/admin/exports/{export_id}", "external_delivery": False}
        except Exception as exc:  # noqa: BLE001 - persist a recoverable export failure.
            for partial in (temporary, target):
                try:
                    partial.unlink(missing_ok=True)
                except OSError:
                    pass
            with db.session(write=True) as conn:
                conn.execute("UPDATE export_jobs SET status='failed',error_code=?,completed_at=? WHERE id=?", (type(exc).__name__, utc_now(), export_id))
            audit(db, ctx, "export_data", "export", export_id, "failed", {"learner_id": learner_id, "error": type(exc).__name__})
            raise APIError(503, "EXPORT_FAILED", "导出失败，可重试", True)

    @app.get("/api/v1/admin/exports/{export_id}")
    def download_export(export_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        require_admin(ctx)
        if not isinstance(settings, Settings):
            settings = app.state.settings
        with db.session() as conn:
            row = conn.execute("SELECT * FROM export_jobs WHERE id=?", (export_id,)).fetchone()
            if not row:
                raise APIError(404, "EXPORT_NOT_FOUND", "导出不存在")
            ensure_access(conn, ctx.account_id, row["learner_id"], {"admin", "guardian"})
        if row["status"] != "completed" or not row["artifact_key"]:
            raise APIError(409, "EXPORT_NOT_READY", "导出尚未完成")
        target = _contained_path(settings.export_dir or (settings.data_dir / "exports"), row["artifact_key"])
        if not target.is_file():
            raise APIError(503, "EXPORT_UNAVAILABLE", "导出文件不可用", True)
        return FileResponse(target, media_type="application/json", filename=f"{export_id}.json")

    @app.post("/api/v1/admin/deletions", status_code=202)
    def delete_data(body: dict[str, Any], ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        require_admin(ctx)
        if not isinstance(settings, Settings):  # direct route tests bypass FastAPI dependency injection
            settings = app.state.settings
        learner_id = body.get("learner_id")
        if not learner_id:
            raise APIError(422, "LEARNER_REQUIRED", "需要 learner_id")
        deleted = failed = 0
        cleanup_records: list[sqlite3.Row] = []
        asset_records: list[sqlite3.Row] = []
        with db.session(write=True) as conn:
            ensure_access(conn, ctx.account_id, learner_id, {"admin", "guardian"})
            live = conn.execute("SELECT id,object_key FROM assets WHERE learner_id=? AND deleted_at IS NULL", (learner_id,)).fetchall()
            now = utc_now()
            for row in live:
                conn.execute("UPDATE assets SET deleted_at=? WHERE id=?", (now, row["id"]))
                conn.execute("INSERT OR IGNORE INTO deletion_records(id,learner_id,resource_type,resource_id,policy_version,created_at,cleanup_state,object_key,deleted_at) VALUES (?,?,?,?,?,?,?,?,?)", (new_id("deletion"), learner_id, "asset", row["id"], "lifecycle-v1", now, "pending", row["object_key"], now))
            # A learner deletion is a data-lifecycle operation, not only an
            # attachment unlink. Keep tombstones for every learner-scoped
            # record so stale backups cannot make derived state visible again.
            resource_queries = {
                "diagnosis": "SELECT id FROM diagnoses WHERE mistake_id IN (SELECT id FROM mistake_entries WHERE learner_id=?)",
                "review_request": "SELECT id FROM review_requests WHERE learner_id=?",
                "learning_draft": "SELECT id FROM learning_drafts WHERE learner_id=?",
                "visual_asset": "SELECT id FROM visual_assets WHERE learner_id=?",
                "mistake": "SELECT id FROM mistake_entries WHERE learner_id=?",
                "review_card": "SELECT id FROM review_cards WHERE learner_id=?",
                "test_session": "SELECT id FROM test_sessions WHERE learner_id=?",
                "attempt": "SELECT id FROM attempts WHERE learner_id=?",
            }
            for resource_type, query in resource_queries.items():
                for resource in conn.execute(query, (learner_id,)).fetchall():
                    conn.execute(
                        "INSERT OR IGNORE INTO deletion_records(id,learner_id,resource_type,resource_id,policy_version,created_at,cleanup_state,deleted_at) VALUES (?,?,?,?,?,?,?,?)",
                        (new_id("deletion"), learner_id, resource_type, resource["id"], "lifecycle-v1", now, "pending", now),
                    )
            for export in conn.execute("SELECT id,artifact_key FROM export_jobs WHERE learner_id=?", (learner_id,)).fetchall():
                conn.execute(
                    "INSERT OR IGNORE INTO deletion_records(id,learner_id,resource_type,resource_id,policy_version,created_at,cleanup_state,object_key,deleted_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (new_id("deletion"), learner_id, "export_artifact", export["id"], "lifecycle-v1", now, "pending", export["artifact_key"], now),
                )
            cleanup_records = conn.execute(
                "SELECT * FROM deletion_records WHERE learner_id=? AND cleanup_state IN ('pending','failed') ORDER BY created_at",
                (learner_id,),
            ).fetchall()
            asset_records = [row for row in cleanup_records if row["resource_type"] == "asset"]
            conn.execute("UPDATE source_documents SET status='deleted' WHERE learner_id=?", (learner_id,))
            conn.execute("UPDATE source_pages SET status='deleted' WHERE document_id IN (SELECT id FROM source_documents WHERE learner_id=?)", (learner_id,))
            conn.execute("UPDATE visual_assets SET approval='retracted' WHERE learner_id=? AND approval='approved'", (learner_id,))
            conn.execute("UPDATE mistake_entries SET status='deleted',archived_at=COALESCE(archived_at,?) WHERE learner_id=?", (now, learner_id))
            conn.execute("UPDATE diagnoses SET status='deleted' WHERE mistake_id IN (SELECT id FROM mistake_entries WHERE learner_id=?)", (learner_id,))
            conn.execute("UPDATE learning_drafts SET status='deleted' WHERE learner_id=?", (learner_id,))
            conn.execute("UPDATE review_cards SET active=0,updated_at=? WHERE learner_id=?", (now, learner_id))
            conn.execute("UPDATE test_items SET status='cancelled' WHERE learner_id=? AND status IN ('reserved','presented','grading_pending')", (learner_id,))
            conn.execute("UPDATE test_sessions SET status='deleted',completed_at=COALESCE(completed_at,?) WHERE learner_id=?", (now, learner_id))
            conn.execute("UPDATE attempts SET status='deleted' WHERE learner_id=?", (learner_id,))
            conn.execute("UPDATE review_requests SET status='cancelled',updated_at=? WHERE learner_id=? AND status NOT IN ('resolved','dismissed','cancelled')", (now, learner_id))
            conn.execute("UPDATE export_jobs SET status='cancelled',error_code='DATA_DELETED',completed_at=COALESCE(completed_at,?) WHERE learner_id=? AND status <> 'cancelled'", (now, learner_id))
            conn.execute("UPDATE learner_access SET active=0 WHERE learner_id=?", (learner_id,))
            conn.execute("UPDATE learners SET active=0 WHERE id=?", (learner_id,))
        # Files are removed after the tombstone transaction. A failed unlink is
        # recorded and never makes the asset or export visible again.
        for row in cleanup_records:
            try:
                if row["object_key"]:
                    root = settings.export_dir or (settings.data_dir / "exports") if row["resource_type"] == "export_artifact" else settings.attachment_dir
                    _contained_path(root, row["object_key"]).unlink(missing_ok=True)
                state, error = "completed", None
                if row["resource_type"] == "asset":
                    deleted += 1
            except (OSError, APIError) as exc:
                state, error = "failed", type(exc).__name__
                if row["resource_type"] == "asset":
                    failed += 1
            with db.session(write=True) as conn:
                conn.execute("UPDATE deletion_records SET cleanup_state=?,error_code=? WHERE resource_type=? AND resource_id=?", (state, error, row["resource_type"], row["resource_id"]))
        audit(db, ctx, "delete_data", "learner", learner_id, "accepted" if not failed else "partial", {"assets_marked": len(live), "assets_deleted": deleted, "assets_failed": failed, "resources_marked": len(cleanup_records)})
        return {"status": "completed" if not failed else "partial", "learner_id": learner_id, "assets_marked": len(live), "assets_deleted": deleted, "assets_failed": failed, "resources_marked": len(cleanup_records), "backup_replay_required": True}

    return app


def run_worker_once(db: Database, settings: Settings) -> dict[str, Any]:
    """Claim one durable job and apply its result with lease checks."""
    now = datetime.now(timezone.utc)
    now_iso = now.replace(microsecond=0).isoformat()
    lease_until = (now + timedelta(seconds=60)).replace(microsecond=0).isoformat()
    token = secrets.token_urlsafe(24)
    with db.session(write=True) as conn:
        job = conn.execute("SELECT * FROM jobs WHERE status='queued' OR (status='running' AND lease_until<?) ORDER BY created_at LIMIT 1", (now_iso,)).fetchone()
        if not job:
            return {"status": "idle"}
        claimed = conn.execute("UPDATE jobs SET status='running',lease_token=?,lease_until=?,attempts=attempts+1,updated_at=? WHERE id=? AND (status='queued' OR (status='running' AND lease_until<?))", (token, lease_until, now_iso, job["id"], now_iso)).rowcount
        if not claimed:
            return {"status": "busy"}
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
    try:
        if job["kind"] == "document_analysis":
            result = _process_analysis(db, job, token, settings)
        elif job["kind"] == "grade_attempt":
            result = _process_grade(db, job, token, settings)
        elif job["kind"] == "diagnosis":
            result = _process_diagnosis(db, job, token, settings)
        elif job["kind"] == "variant_generation":
            provider_result = variant_provider(settings.variant_provider).generate(json_loads(job["input_json"], {}))
            result = {"status": provider_result.status, "provider_id": provider_result.provider_id, "external_call": False, "payload": provider_result.payload, "evidence": provider_result.evidence, "reason": "模型/人工审核提供商尚未配置，保留为候选"}
        else:
            result = {"status": "skipped", "reason": "unsupported_job_kind"}
        with db.session(write=True) as conn:
            updated = conn.execute("UPDATE jobs SET status='succeeded',result_json=?,lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=? AND status='running' AND lease_token=?", (json_dumps(result), utc_now(), job["id"], token)).rowcount
            if not updated:
                return {"status": "stale", "job_id": job["id"]}
        return {"status": "succeeded", "job_id": job["id"], "result": result}
    except APIError as exc:
        with db.session(write=True) as conn:
            updated = conn.execute("UPDATE jobs SET status='failed',error_code=?,result_json=?,lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=? AND lease_token=?", (exc.code, json_dumps({"message": exc.message}), utc_now(), job["id"], token)).rowcount
        if not updated:
            return {"status": "stale", "job_id": job["id"], "error": exc.code}
        return {"status": "failed", "job_id": job["id"], "error": exc.code}
    except Exception as exc:  # noqa: BLE001 - worker records unexpected provider/storage failures.
        with db.session(write=True) as conn:
            updated = conn.execute("UPDATE jobs SET status='failed',error_code='WORKER_ERROR',result_json=?,lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=? AND lease_token=?", (json_dumps({"message": type(exc).__name__}), utc_now(), job["id"], token)).rowcount
        if not updated:
            return {"status": "stale", "job_id": job["id"], "error": "WORKER_ERROR"}
        return {"status": "failed", "job_id": job["id"], "error": "WORKER_ERROR"}


def _process_diagnosis(db: Database, job: sqlite3.Row, token: str, settings: Settings) -> dict[str, Any]:
    """Run diagnosis outside a SQLite writer transaction and persist reviewable output."""
    payload = json_loads(job["input_json"], {})
    mistake_id = payload.get("mistake_id")
    if not isinstance(mistake_id, str) or not mistake_id:
        raise APIError(422, "MISTAKE_REQUIRED", "诊断任务缺少 mistake_id")
    with db.session() as conn:
        if not conn.execute("SELECT 1 FROM jobs WHERE id=? AND status='running' AND lease_token=?", (job["id"], token)).fetchone():
            raise APIError(409, "STALE_LEASE", "任务租约已失效")
        entry = conn.execute("SELECT id FROM mistake_entries WHERE id=? AND learner_id=?", (mistake_id, job["learner_id"])).fetchone()
        if not entry:
            raise APIError(404, "MISTAKE_NOT_FOUND", "错题不存在")
        source = conn.execute("SELECT item_id FROM mistake_sources WHERE entry_id=? AND active=1 ORDER BY created_at LIMIT 1", (mistake_id,)).fetchone()
        evidence = {"source_item_id": source["item_id"] if source else None, "requires_review": True, "external_call": False}

    provider_result = diagnosis_provider(settings.diagnosis_provider).diagnose(evidence)
    evidence.update({"provider_id": provider_result.provider_id, "provider_status": provider_result.status, "provider_evidence": provider_result.evidence})
    output = {
        **provider_result.payload,
        "evidence_steps": [],
        "hypotheses": [{"text": "需要补充学生步骤后再判断", "basis": "原始证据不足"}],
        "remedy_notes": "请补充解题步骤。",
        "diagnosis_status": provider_result.status,
        "provider_id": provider_result.provider_id,
    }
    with db.session(write=True) as conn:
        if not conn.execute("SELECT 1 FROM jobs WHERE id=? AND status='running' AND lease_token=?", (job["id"], token)).fetchone():
            raise APIError(409, "STALE_LEASE", "任务租约已失效")
        if not conn.execute("SELECT 1 FROM mistake_entries WHERE id=? AND learner_id=?", (mistake_id, job["learner_id"])).fetchone():
            raise APIError(404, "MISTAKE_NOT_FOUND", "错题不存在")
        diagnosis_id = new_id("diagnosis")
        conn.execute(
            "INSERT INTO diagnoses(id,mistake_id,evidence_json,output_json,model_id,prompt_version,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (diagnosis_id, mistake_id, json_dumps(evidence), json_dumps(output), payload.get("model_id", "mock-diagnosis-v1"), payload.get("prompt_version", "diagnose-v1"), "needs_review", utc_now()),
        )
        conn.execute("UPDATE mistake_entries SET diagnosis_status='needs_review' WHERE id=?", (mistake_id,))
    return {"mistake_id": mistake_id, "diagnosis_id": diagnosis_id, "status": "needs_review", "provider_id": provider_result.provider_id, "review_required": True}


def _process_analysis(db: Database, job: sqlite3.Row, token: str, settings: Settings | None = None) -> dict[str, Any]:
    payload = json_loads(job["input_json"], {})
    batch_id = payload["batch_id"]
    settings = settings or Settings.from_env()
    provider = document_provider(settings.document_provider)
    # Validate the durable claim and snapshot the page list in a short read
    # transaction. Provider/OCR work below deliberately happens outside any
    # SQLite transaction; each result is applied in its own short write
    # transaction with the lease and batch revision checked again.
    with db.session() as conn:
        if not conn.execute("SELECT 1 FROM jobs WHERE id=? AND status='running' AND lease_token=?", (job["id"], token)).fetchone():
            raise APIError(409, "STALE_LEASE", "任务租约已失效")
        batch = conn.execute("SELECT * FROM import_batches WHERE id=?", (batch_id,)).fetchone()
        if not batch:
            raise APIError(404, "BATCH_NOT_FOUND", "批次不存在")
        expected_revision = payload.get("revision")
        if batch["status"] == "cancelled":
            raise APIError(409, "BATCH_CANCELLED", "批次已取消，拒绝迟到分析结果")
        if expected_revision != batch["revision"]:
            raise APIError(409, "STALE_BATCH_REVISION", "分析任务对应的批次版本已过期")
        if job["learner_id"] != batch["learner_id"]:
            raise APIError(403, "JOB_SCOPE_MISMATCH", "分析任务与批次学习者不匹配")
        document_ids = json_loads(batch["document_ids_json"], [])
        placeholders = ",".join("?" * len(document_ids))
        pages = conn.execute(f"SELECT p.*,d.learner_id FROM source_pages p JOIN source_documents d ON d.id=p.document_id WHERE p.document_id IN ({placeholders}) ORDER BY p.document_id,p.page_index", document_ids).fetchall()
        expected_revision = batch["revision"]
        learner_id = batch["learner_id"]

    for page in pages:
        if page["status"] == "failed":
            continue
        # A prior committed page result is authoritative. This also makes a
        # retry after a worker interruption idempotent without another call.
        if page["status"] == "processed":
            continue
        provider_result = provider.analyze_page(dict(page))
        content = {**provider_result.payload, "provider_id": provider_result.provider_id, "provider_status": provider_result.status, "provider_evidence": provider_result.evidence}
        # Revision is part of the occurrence identity. A page edit retains the
        # old candidate for audit, but a new analysis must create a new item.
        occurrence = f"{batch_id}:{page['id']}:{expected_revision}"
        with db.session(write=True) as conn:
            if not conn.execute("SELECT 1 FROM jobs WHERE id=? AND status='running' AND lease_token=?", (job["id"], token)).fetchone():
                raise APIError(409, "STALE_LEASE", "任务租约已失效")
            current_batch = conn.execute("SELECT * FROM import_batches WHERE id=?", (batch_id,)).fetchone()
            if not current_batch:
                raise APIError(404, "BATCH_NOT_FOUND", "批次不存在")
            if current_batch["status"] == "cancelled":
                raise APIError(409, "BATCH_CANCELLED", "批次已取消，拒绝迟到分析结果")
            if current_batch["revision"] != expected_revision:
                raise APIError(409, "STALE_BATCH_REVISION", "分析任务对应的批次版本已过期")
            current_page = conn.execute("SELECT status FROM source_pages WHERE id=?", (page["id"],)).fetchone()
            if not current_page or current_page["status"] == "failed":
                continue
            if current_page["status"] == "processed":
                continue
            if not conn.execute("SELECT 1 FROM import_items WHERE batch_id=? AND occurrence_id=?", (batch_id, occurrence)).fetchone():
                item_id = new_id("item")
                conn.execute("INSERT INTO import_items(id,batch_id,learner_id,occurrence_id,locator,page_index,source_page_id,content_json,verdict,verification_status,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (item_id, batch_id, learner_id, occurrence, f"page:{page['page_index'] + 1}:item:1", page["page_index"], page["id"], json_dumps(content), "undetermined", "needs_review", "needs_review"))
                conn.execute("INSERT INTO source_regions(id,item_id,source_page_id,region_type,bbox_json) VALUES (?,?,?,?,?)", (new_id("region"), item_id, page["id"], "page", json_dumps({"x": 0, "y": 0, "width": 1, "height": 1})))
            conn.execute("UPDATE source_pages SET status='processed' WHERE id=?", (page["id"],))

    with db.session(write=True) as conn:
        if not conn.execute("SELECT 1 FROM jobs WHERE id=? AND status='running' AND lease_token=?", (job["id"], token)).fetchone():
            raise APIError(409, "STALE_LEASE", "任务租约已失效")
        counts = conn.execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN status='processed' THEN 1 ELSE 0 END) AS processed, SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed FROM source_pages WHERE document_id IN (SELECT value FROM json_each((SELECT document_ids_json FROM import_batches WHERE id=?)))",
            (batch_id,),
        ).fetchone()
        processed = int(counts["processed"] or 0)
        failed = int(counts["failed"] or 0)
        status = "partial_failed" if failed else "awaiting_review"
        conn.execute("UPDATE import_batches SET status=?,processed_pages=?,failed_pages=?,updated_at=? WHERE id=?", (status, processed, failed, utc_now(), batch_id))
    return {"batch_id": batch_id, "status": status, "processed_pages": processed, "failed_pages": failed}


def _process_grade(db: Database, job: sqlite3.Row, token: str, settings: Settings) -> dict[str, Any]:
    payload = json_loads(job["input_json"], {})
    attempt_id = payload["attempt_id"]
    with db.session(write=True) as conn:
        if not conn.execute("SELECT 1 FROM jobs WHERE id=? AND status='running' AND lease_token=?", (job["id"], token)).fetchone():
            raise APIError(409, "STALE_LEASE", "任务租约已失效")
        row = conn.execute("SELECT a.*,ti.id AS item_id,ti.card_id,ti.cycle_id,ti.reserved_revision,ti.session_id,ti.assistance AS item_assistance,ts.mode AS session_mode,qv.id AS question_version_id,qv.answer_key_json,qv.validator_version,qv.variant_kind,qv.variant_group,qv.approval AS version_approval,q.approval AS question_approval,q.objective_id FROM attempts a JOIN test_items ti ON ti.id=a.test_item_id JOIN test_sessions ts ON ts.id=ti.session_id JOIN question_versions qv ON qv.id=ti.question_version_id JOIN questions q ON q.id=qv.question_id WHERE a.id=?", (attempt_id,)).fetchone()
        if not row:
            raise APIError(404, "ATTEMPT_NOT_FOUND", "作答不存在")
        existing = conn.execute("SELECT * FROM grade_versions WHERE attempt_id=? ORDER BY created_at DESC LIMIT 1", (attempt_id,)).fetchone()
        if existing:
            return {"attempt_id": attempt_id, "status": "already_graded", "outcome": existing["outcome"]}
        answer_key = json_loads(row["answer_key_json"], {})
        accepted = {_normalize_answer(str(value)) for value in answer_key.get("accepted", [])}
        normalized = _normalize_answer(row["raw_answer"])
        outcome = "correct" if normalized in accepted and accepted else "incorrect" if accepted else "undetermined"
        if answer_key.get("outcome") in {"partial", "undetermined"}:
            outcome = answer_key["outcome"]
        feedback = "服务端校验通过。" if outcome == "correct" else "这次答案未通过校验，保留为再学习证据。" if outcome == "incorrect" else "题目需要人工复核，暂不改变复习阶段。"
        grade_id = new_id("grade")
        conn.execute("INSERT INTO grade_versions(id,attempt_id,outcome,score,feedback,rubric_version,validator_version,created_at) VALUES (?,?,?,?,?,?,?,?)", (grade_id, attempt_id, outcome, 1.0 if outcome == "correct" else 0.0 if outcome == "incorrect" else None, feedback, "exact-text-v1", row["validator_version"], utc_now()))
        conn.execute("UPDATE attempts SET normalized_answer=?,status='graded' WHERE id=?", (normalized, attempt_id))
        conn.execute("UPDATE test_items SET status='graded' WHERE id=?", (row["item_id"],))
        conn.execute("UPDATE test_sessions SET status='completed',completed_at=? WHERE id=? AND NOT EXISTS (SELECT 1 FROM test_items WHERE session_id=? AND status NOT IN ('graded','cancelled','invalidated'))", (utc_now(), row["session_id"], row["session_id"]))
        scheduled = False
        maintenance_eligibility = None
        # Practice answers never advance a card, but a stage-five attempt still
        # returns an explicit gate result so callers can distinguish an
        # ineligible practice answer from a missing evaluation.
        if (
            row["card_id"]
            and row["session_mode"] != "independent"
            and row["assessment_eligibility"]
            and outcome in {"correct", "incorrect"}
        ):
            practice_card = conn.execute("SELECT * FROM review_cards WHERE id=?", (row["card_id"],)).fetchone()
            if practice_card and practice_card["stage"] == 5:
                maintenance_eligibility = _maintenance_gate(conn, practice_card, row, outcome)
        if row["card_id"] and row["session_mode"] == "independent" and row["assessment_eligibility"] and outcome in {"correct", "incorrect"}:
            card = conn.execute("SELECT * FROM review_cards WHERE id=?", (row["card_id"],)).fetchone()
            prior = conn.execute("SELECT 1 FROM review_events WHERE card_id=? AND cycle_id=? AND event_type='initial'", (row["card_id"], row["cycle_id"])).fetchone()
            if card and not prior and card["revision"] == row["reserved_revision"]:
                before = {"state": card["state"], "stage": card["stage"], "due_at": card["due_at"], "revision": card["revision"]}
                if outcome == "incorrect":
                    state, stage, days = "relearning", 0, 1
                elif card["state"] == "maintenance":
                    state, stage, days = "maintenance", 5, 30
                elif card["stage"] < 5:
                    state, stage, days = "review", card["stage"] + 1, INTERVALS[card["stage"] + 1]
                else:
                    maintenance_eligibility = _maintenance_gate(conn, card, row, outcome)
                    if maintenance_eligibility["eligible"]:
                        state, stage, days = "maintenance", 5, 30
                    else:
                        state, stage, days = "review", 5, 30
                due = _scheduled_due(row["submitted_at"], days, card["timezone_snapshot"] or DEFAULT_TIMEZONE)
                after = {"state": state, "stage": stage, "due_at": due, "revision": card["revision"] + 1}
                if maintenance_eligibility is not None:
                    after["maintenance_eligibility"] = maintenance_eligibility
                conn.execute("UPDATE review_cards SET state=?,stage=?,due_at=?,revision=revision+1,last_exposure_at=?,updated_at=? WHERE id=? AND revision=?", (state, stage, due, row["submitted_at"], utc_now(), row["card_id"], row["reserved_revision"]))
                conn.execute("INSERT INTO review_events(id,card_id,cycle_id,attempt_id,grade_version_id,event_type,before_json,after_json,scheduler_version,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (new_id("review_event"), row["card_id"], row["cycle_id"], attempt_id, grade_id, "initial", json_dumps(before), json_dumps(after), settings.scheduler_version, utc_now()))
                scheduled = True
        conn.execute("INSERT INTO learning_events(id,learner_id,objective_id,event_type,source,assistance,accepted_at,metadata_json) VALUES (?,?,?,?,?,?,?,?)", (new_id("event"), row["learner_id"], row["objective_id"], "graded_attempt", "test", row["assistance"], utc_now(), json_dumps({"attempt_id": attempt_id, "outcome": outcome, "scheduled": scheduled, "maintenance_eligibility": maintenance_eligibility})))
    return {"attempt_id": attempt_id, "status": "graded", "outcome": outcome, "scheduled": scheduled, "maintenance_eligibility": maintenance_eligibility}


app = create_app()


if __name__ == "__main__":
    import os
    import uvicorn
    uvicorn.run(
        "learning_service.app:app",
        host=os.environ.get("LEARNING_HOST", "0.0.0.0"),
        port=int(os.environ.get("LEARNING_PORT", "31010")),
        reload=False,
    )
