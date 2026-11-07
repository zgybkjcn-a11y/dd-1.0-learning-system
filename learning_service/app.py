from __future__ import annotations

import hashlib
import html
import inspect
import json
import mimetypes
import re
import secrets
import shutil
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from starlette.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from .config import Settings
from .practice import metadata as practice_metadata, learner_guidance, grade_numeric
from .math_references import query_reference as query_math_reference, ReferenceError
from .study_support import query_support as query_study_support
from .study_ui import STYLE as STUDY_STYLE, PANEL as STUDY_PANEL, SCRIPT as STUDY_SCRIPT
from .db import Database, WriteContextChanged, write_context, json_dumps, json_loads, new_id, utc_now
from .providers import TencentEducationOCRProvider, diagnosis_provider, document_provider, variant_provider
from .provider_usage import ProviderLimit, UsageLedger
from .browser_auth import AuthError, BrowserSessions, CSRF_COOKIE, SESSION_COOKIE
from .learner_context import ContextConflict, read_context, select_context
from .variant_review import VariantReviewRequest, VariantRevokeRequest, fingerprint as variant_fingerprint, checked_draft, publish as publish_variant, review_audit
from .textbooks import (catalogue as textbook_catalogue, subject_catalogue as textbook_subjects, search_scope as textbook_search_scope,
                        page_scope as textbook_page_scope, render_page as render_textbook_page,
                        practice_scope as textbook_practice_scope, learning_scope as textbook_learning_scope)


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


class ManualMistakeRequest(BaseModel):
    question_text: str = Field(min_length=1, max_length=20000)
    student_answer: str | None = Field(default=None, max_length=10000)
    correct_answer: str | None = Field(default=None, max_length=10000)
    objective_id: str | None = None
    note: str | None = Field(default=None, max_length=5000)


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
    textbook_book_id: str | None = None
    textbook_chapter_id: str | None = None


class AnswerRequest(BaseModel):
    challenge_id: str
    nonce: str
    raw_answer: str = Field(min_length=1, max_length=10000)


class DiagnosisRequest(BaseModel):
    model_id: str = "mock-diagnosis-v1"
    prompt_version: str = "diagnose-v1"


class ProviderControlRequest(BaseModel):
    paused: bool = Field(strict=True)


class ProviderReconciliationRequest(BaseModel):
    cost_micros: int = Field(ge=0, le=10**15, strict=True)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    billing_reference: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)


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


_OFFICE_MIME_ALIASES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    },
}


def _zip_member(zfile: zipfile.ZipFile, name: str, limit: int = 8 * 1024 * 1024) -> bytes:
    """Read one OOXML member with a decompressed-size guard."""
    info = zfile.getinfo(name)
    if info.file_size > limit:
        raise ValueError("OOXML member exceeds the extraction limit")
    return zfile.read(name)


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _extract_docx_pages(data: bytes) -> list[dict[str, Any]]:
    with zipfile.ZipFile(__import__("io").BytesIO(data)) as zfile:
        names = set(zfile.namelist())
        if "word/document.xml" not in names or "[Content_Types].xml" not in names:
            raise ValueError("not a DOCX package")
        root = ET.fromstring(_zip_member(zfile, "word/document.xml"))
    paragraphs: list[str] = []
    for paragraph in root.iter():
        if _xml_local_name(paragraph.tag) != "p":
            continue
        text = "".join((node.text or "") for node in paragraph.iter() if _xml_local_name(node.tag) in {"t", "tab"})
        if text.strip():
            paragraphs.append(text.strip())
    return [{"text": "\n".join(paragraphs), "format": "docx"}]


def _xlsx_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join((node.text or "") for node in cell.iter() if _xml_local_name(node.tag) == "t")
    value_node = next((node for node in cell if _xml_local_name(node.tag) == "v"), None)
    value = value_node.text if value_node is not None and value_node.text is not None else ""
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return value
    if cell_type == "b":
        return "是" if value == "1" else "否"
    return value


def _xlsx_column_index(reference: str) -> int:
    letters = "".join(character for character in reference.split(" ", 1)[0] if character.isalpha())
    index = 0
    for character in letters.upper():
        index = index * 26 + ord(character) - ord("A") + 1
    return max(index - 1, 0)


def _extract_xlsx_pages(data: bytes) -> list[dict[str, Any]]:
    with zipfile.ZipFile(__import__("io").BytesIO(data)) as zfile:
        names = set(zfile.namelist())
        if "xl/workbook.xml" not in names or "[Content_Types].xml" not in names:
            raise ValueError("not an XLSX package")
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            shared_root = ET.fromstring(_zip_member(zfile, "xl/sharedStrings.xml"))
            for item in shared_root.iter():
                if _xml_local_name(item.tag) != "si":
                    continue
                shared_strings.append("".join((node.text or "") for node in item.iter() if _xml_local_name(node.tag) == "t"))
        worksheet_names = sorted(
            name for name in names
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        if not worksheet_names:
            raise ValueError("XLSX contains no worksheets")
        pages: list[dict[str, Any]] = []
        for sheet_number, name in enumerate(worksheet_names, 1):
            root = ET.fromstring(_zip_member(zfile, name))
            rows: list[str] = []
            for row in (node for node in root.iter() if _xml_local_name(node.tag) == "row"):
                cells: dict[int, str] = {}
                for cell in (node for node in row if _xml_local_name(node.tag) == "c"):
                    cells[_xlsx_column_index(cell.attrib.get("r", "A1"))] = _xlsx_cell_value(cell, shared_strings)
                if cells:
                    width = max(cells) + 1
                    rows.append("\t".join(cells.get(index, "") for index in range(width)).rstrip("\t"))
            pages.append({"text": f"工作表 {sheet_number}\n" + "\n".join(rows), "format": "xlsx"})
    return pages


def _office_pages(data: bytes, media_type: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        if media_type in _OFFICE_MIME_ALIASES:
            pages = _extract_docx_pages(data) if media_type.endswith("wordprocessingml.document") else _extract_xlsx_pages(data)
            return pages, None
    except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile, KeyError):
        return [{"text": None, "format": None}], "DOCX_PARSE_FAILED" if media_type.endswith("wordprocessingml.document") else "XLSX_PARSE_FAILED"
    return [], None


def _detect_media_type(data: bytes, filename: str, supplied: str) -> str | None:
    if data.startswith(b"%PDF"):
        actual = "application/pdf"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        actual = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        actual = "image/jpeg"
    elif data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(__import__("io").BytesIO(data)) as zfile:
                names = set(zfile.namelist())
            if "word/document.xml" in names:
                actual = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif "xl/workbook.xml" in names:
                actual = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            else:
                actual = None
        except (OSError, zipfile.BadZipFile):
            actual = None
    else:
        actual = None
    if not actual:
        return None
    supplied = (supplied or mimetypes.guess_type(filename or "")[0] or "").split(";", 1)[0].strip().lower()
    aliases = _OFFICE_MIME_ALIASES.get(actual, {actual})
    if supplied and supplied not in aliases and not (actual in {"application/pdf", "image/png", "image/jpeg"} and supplied == "application/octet-stream"):
        return None
    return actual


def _page_count(data: bytes, media_type: str) -> tuple[int, str | None]:
    if media_type in _OFFICE_MIME_ALIASES:
        pages, error = _office_pages(data, media_type)
        return max(len(pages), 1), error
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
        "variant_reviews": _export_rows(conn, "variant_reviews", learner_id),
        "variant_revocations": _export_rows(conn, "variant_revocations", learner_id),
        "variant_jobs": [dict(row) for row in conn.execute("SELECT * FROM jobs WHERE learner_id=? AND kind='variant_generation'", (learner_id,))],
        "private_questions": _export_rows(conn, "questions", learner_id),
        "private_question_versions": [dict(row) for row in conn.execute("SELECT v.* FROM question_versions v JOIN questions q ON q.id=v.question_id WHERE q.learner_id=?", (learner_id,))],
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
    [hidden] { display: none !important; }
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
    .game-only { display: none; }
    .family-game { --accent: #087c71; --accent-soft: #e5f7ed; --ink: #24394b; --paper: #fffdf7; --hero: #daf4eb; max-width: 1180px; padding: 24px 28px 48px; color: var(--ink); background: #f5f3ea; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; }
    html:has(.family-game) { background: #f5f3ea; }
    .family-game[data-grade="7"] { --accent: #6250c6; --accent-soft: #eeeafb; --hero: #282349; --paper: #fefcff; }
    .family-game .game-only { display: block; }
    .family-game [hidden] { display: none !important; }
    .family-game header { position: relative; border: 0; padding: 0; margin-bottom: 22px; background: transparent; }
    .family-game header > h1, .family-game header > p:not(#contextStatus), .family-game header > .grid, .family-game header > nav.row { display: none; }
    .family-game header > .row { position: absolute; top: 8px; right: 0; }
    .family-game header > .row > * { flex: none; }
    .family-game #loadLearners { font-size: 12px; color: #657582; padding: 8px 12px; border-color: #dce2dd; background: transparent; }
    .family-game #contextStatus:empty, .family-game #gameNotice:empty { display: none; }
    .family-game #contextStatus, .family-game #gameNotice { border-radius: 12px; padding: 12px; background: #fff0cf; color: #745521; font-size: 14px; }
    .family-game .game-brand { display: flex; gap: 12px; align-items: center; margin-bottom: 23px; }
    .game-brand .brand-symbol { width: 42px; height: 42px; display: grid; place-items: center; color: #fff; background: #1d8978; border-radius: 15px; box-shadow: 0 4px 0 #d5e7d8; }
    .brand-symbol svg { width: 28px; height: 28px; }
    .brand-title { font-size: 20px; font-weight: 850; letter-spacing: 1px; }
    .brand-note { color: #8b968f; font-size: 11px; letter-spacing: 2px; margin-top: 2px; }
    .family-game .profile-heading { font-size: 12px; color: #73816e; margin: 0 0 9px; font-weight: 650; }
    .family-game .profile-choices { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .family-game .profile-card { min-height: 76px; display: flex; gap: 13px; align-items: center; padding: 13px 17px; text-align: left; background: #fffefb; border: 2px solid #e3e6db; border-radius: 18px; color: #425563; transition: border-color .18s, transform .18s, box-shadow .18s; }
    .family-game .profile-card:hover { transform: translateY(-2px); border-color: #a9cbb6; }
    .family-game .profile-card[aria-pressed="true"] { border-color: var(--accent); box-shadow: 0 4px 0 color-mix(in srgb, var(--accent) 13%, transparent); background: var(--accent-soft); }
    .profile-avatar { flex: 0 0 42px; height: 42px; display: grid; place-items: center; border-radius: 14px; background: #fff0c7; color: #b47222; font-size: 24px; }
    .profile-card[data-grade="7"] .profile-avatar { background: #eee7ff; color: #6851c7; }
    .profile-card strong { display: block; font-size: 15px; font-weight: 800; }
    .profile-card small { display: block; font-size: 11px; color: #788575; margin-top: 5px; }
    .profile-check { margin-left: auto; font-size: 16px; opacity: 0; }
    .profile-card[aria-pressed="true"] .profile-check { opacity: 1; color: var(--accent); }
    .family-game .game-nav { display: flex; gap: 6px; margin: 19px 0 0; border-bottom: 1px solid #dde2d5; padding-bottom: 9px; }
    .game-nav a { display: inline-flex; gap: 7px; align-items: center; color: #71816d; padding: 10px 17px; text-decoration: none; font-weight: 750; font-size: 13px; border-radius: 12px; }
    .game-nav a[aria-current="page"] { color: var(--accent); background: var(--accent-soft); }
    .family-game main > section { border: 0; border-radius: 24px; padding: 25px 27px; background: var(--paper); box-shadow: 0 3px 0 #e8eadf; margin-bottom: 20px; }
    .family-game #gameHero { position: relative; overflow: hidden; min-height: 310px; padding: 32px; background: var(--hero); box-shadow: 0 5px 0 #c9e5d9; }
    .family-game[data-grade="7"] #gameHero { color: #fff; box-shadow: 0 5px 0 #d8d1f0; }
    .family-game #gameHero::before { content: ""; position: absolute; inset: 0; background-image: radial-gradient(#ffffff65 1px, transparent 1px); background-size: 23px 23px; opacity: .65; pointer-events: none; }
    .hero-copy { position: relative; z-index: 1; max-width: 61%; }
    .hero-badge { display: inline-flex; border-radius: 99px; background: #ffffff95; color: #316854; padding: 6px 12px; font-size: 11px; font-weight: 750; letter-spacing: .8px; }
    .family-game[data-grade="7"] .hero-badge { color: #d3c6ff; background: #ffffff12; border: 1px solid #7a6ca957; }
    .family-game #heroTitle { font-size: clamp(27px, 3.6vw, 40px); line-height: 1.3; letter-spacing: 1px; margin: 15px 0 10px; }
    .hero-description { font-size: 13px; color: #557c6a; line-height: 1.85; max-width: 380px; margin: 0 0 20px; }
    .family-game[data-grade="7"] .hero-description { color: #c4bfdc; }
    .family-game .hero-actions { display: flex; gap: 10px; flex-wrap: wrap; }
    .family-game button.game-primary { background: var(--accent); color: white; border: 0; border-radius: 13px; padding: 13px 20px; font-weight: 800; box-shadow: 0 4px 0 #075f5750; }
    .family-game[data-grade="7"] #startAdventure { background: #dded8c; color: #353546; box-shadow: 0 4px 0 #17102f; }
    .family-game .hero-secondary { color: var(--accent); background: #ffffffa8; border: 0; border-radius: 13px; padding: 13px 16px; font-size: 12px; font-weight: 750; }
    .family-game[data-grade="7"] .hero-secondary { color: #e3ddf7; background: #ffffff10; }
    .hero-stats { display: flex; gap: 23px; margin-top: 24px; }
    .hero-stats strong { display: block; font-size: 24px; font-weight: 850; line-height: 1; }
    .hero-stats span { display: block; font-size: 10px; color: #5b7c6e; margin-top: 6px; }
    .family-game[data-grade="7"] .hero-stats span { color: #bbb2d8; }
    .hero-art { position: absolute; right: 16px; top: 14px; width: 36%; height: 280px; pointer-events: none; }
    .hero-art svg { width: 100%; height: 100%; }
    .senior-scene { display: none; }
    .family-game[data-grade="7"] .junior-scene { display: none; }
    .family-game[data-grade="7"] .senior-scene { display: block; }
    .family-game .section-heading { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 15px; }
    .family-game .section-heading h2 { margin: 0; font-size: 19px; font-weight: 850; letter-spacing: .4px; }
    .section-eyebrow { display: block; font-size: 10px; color: #9ba497; font-weight: 750; letter-spacing: 2px; margin-bottom: 5px; }
    .section-caption { font-size: 11px; color: #8a9786; }
    .family-game #todaySection > h2, .family-game #todaySection > h3, .family-game #progress { display: none; }
    .family-game #loadToday { display: none; }
    .chapter-picker { margin: 18px 0; }
    .chapter-options { display: flex; flex-wrap: wrap; gap: 10px; margin: 12px 0; }
    .family-game .chapter-option { flex: 1 1 180px; display: grid; gap: 6px; text-align: left; padding: 16px 18px; border: 2px solid #e2e8da; border-radius: 16px; color: #425645; background: #fffef8; }
    .family-game .chapter-option[aria-pressed="true"] { border-color: var(--accent); background: #edf5e3; box-shadow: 0 3px 0 #d5e2c6; }
    .family-game[data-grade="7"] .chapter-option[aria-pressed="true"] { background: #f1ecfa; box-shadow: 0 3px 0 #ded5ef; }
    .chapter-option strong { font-size: 15px; }
    .chapter-option small, .chapter-note { font-size: 12px; color: #64745f; line-height: 1.6; }
    .chapter-note { margin: 8px 0; }
    .chapter-heading { font-size: 16px; margin: 18px 0 4px; }
    .family-game #changeChapter { border: 0; background: transparent; color: #627958; padding: 8px 0; font-size: 12px; }
    .family-game .practice-picker { margin: 12px 0 18px; border: 1px solid #e2e6db; border-radius: 12px; padding: 10px 14px; }
    .practice-picker > summary { cursor: pointer; font-size: 13px; font-weight: 650; color: #57634e; padding: 4px 0; }
    .family-game #practiceChoices { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
    .family-game button.challenge-card { display: flex; align-items: center; gap: 10px; text-align: left; min-height: 48px; background: #f7f8f2; border: 1px solid #e2e7dc; border-radius: 10px; color: #344f40; padding: 10px 12px; }
    .family-game button.challenge-card:hover { background: #edf3e5; border-color: var(--accent); }
    .challenge-number { flex: 0 0 26px; height: 26px; display: grid; place-items: center; border-radius: 50%; background: #e7edde; color: #567345; font-size: 12px; }
    .challenge-card strong { font-size: 13px; font-weight: 600; }
    .challenge-arrow { margin-left: auto; color: #718467; }
    .family-game .family-review { margin: 16px 0; padding: 14px; border-radius: 12px; background: #fff6e6; }
    .family-review h3 { margin: 0 0 8px; font-size: 14px; }
    .family-game #today { font-size: 12px; margin: 0; }
    .family-game #testSection > h2, .family-game #testSection > p:not(.game-only), .family-game #testSection > details, .family-game #debugSection { display: none; }
    .family-game #testSection { max-width: 830px; margin-left: auto; margin-right: auto; padding: 29px; }
    .family-game #testPrompt { text-align: center; font-size: clamp(28px, 4vw, 44px); font-weight: 850; color: #253b4d; letter-spacing: 1px; padding: 39px 18px; margin: 15px 0 19px; background: #f5f6ed; border: 1px dashed #dfe6d3; border-radius: 21px; min-height: 133px; }
    .family-game #testPrompt.word-problem { font-size: clamp(20px, 2.5vw, 27px); line-height: 1.85; text-align: left; letter-spacing: 0; padding: 24px; white-space: pre-wrap; overflow-wrap: anywhere; }
    .family-game #solutionText { white-space: pre-wrap; line-height: 1.8; }
    .family-game #questionCredit { font-size: 11px; line-height: 1.6; }
    .family-game[data-grade="7"] #testPrompt { background: #f3effa; border-color: #ded5f1; }
    .family-game #testSection .row { align-items: center; gap: 10px; }
    .family-game #testSection .row > label { flex: 1 1 220px; color: #829079; font-size: 12px; }
    .family-game #answer { font-size: 23px; text-align: center; border-radius: 13px; border: 2px solid #d6e2c9; padding: 12px; width: 100%; color: #334e42; background: #fffef8; }
    .family-game #submitAnswer { flex: 0 1 170px; align-self: end; margin-bottom: 8px; padding: 16px 19px; background: var(--accent); border-color: var(--accent); border-radius: 13px; color: #fff; font-weight: 850; }
    .family-game #restoreTest, .family-game #refreshTest, .family-game #refreshAttempt { display: none; }
    .family-game #requestHint, .family-game #cancelTest, .family-game #requestReview { flex: none; border: 0; background: transparent; font-size: 11px; color: #8c9b82; padding: 7px 0; }
    .family-game #testStatus { text-align: center; font-size: 12px; color: #7f8f78; margin-top: 9px; }
    .family-game #gameHint { margin-top: 15px; border-radius: 13px; background: #fff1cd; padding: 14px; font-size: 13px; color: #806632; }
    .family-game .game-feedback { border-radius: 18px; background: #e9f4dd; padding: 19px 22px; margin-top: 18px; }
    .family-game .game-feedback[data-outcome="incorrect"] { background: #fff1de; }
    .game-feedback h3 { margin: 0 0 6px; font-size: 18px; }
    .game-feedback p { font-size: 12px; margin: 0 0 15px; color: #718466; }
    .family-game .practice-empty { text-align: center; font-size: 12px; color: #889b80; margin-bottom: 15px; }
    .family-game #mistakeSection > h2, .family-game #mistakeSection > .row, .family-game #mistakeSection > p { display: none; }
    .family-game .notebook-layout { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, .85fr); gap: 25px; }
    .family-game .notebook-intro { font-size: 12px; color: #85947d; margin: 0 0 18px; }
    .family-game .review-fields label { font-size: 11px; color: #83917c; margin: 0 0 12px; gap: 6px; }
    .family-game .review-fields input, .family-game .review-fields textarea, .family-game .review-fields select { padding: 11px 12px; border-color: #e0e6d8; border-radius: 12px; color: #485a44; font-size: 13px; background: #fffef8; }
    .family-game .review-fields textarea { resize: vertical; }
    .family-game .notebook-answer-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .family-game #manualObjectiveStatus { font-size: 10px; line-height: 1.6; }
    .family-game #saveManualMistake { width: 100%; border: 0; border-radius: 12px; background: var(--accent); padding: 13px; font-weight: 800; color: #fff; }
    .family-game #manualStatus { font-size: 12px; color: #738969; }
    .family-game .notebook-shelf { border-left: 1px solid #e7ebdf; padding-left: 24px; }
    .notebook-shelf h3 { font-size: 14px; margin: 0 0 15px; }
    .family-game #mistakes { margin: 0; font-size: 13px; color: #8b9981; }
    .family-game #mistakes .review-card { background: #f4f7ed; border: 0; border-radius: 16px; margin-bottom: 11px; padding: 15px; }
    .family-game #mistakes .review-card > p { color: #4f6546; font-weight: 750; font-size: 14px; margin: 0 0 12px; }
    .family-game #mistakes .review-card button { font-size: 10px; border: 0; padding: 4px 0; color: var(--accent); background: transparent; }
    .family-game[data-view="home"] #testSection, .family-game[data-view="home"] #mistakeSection,
    .family-game[data-view="practice"] #gameHero, .family-game[data-view="practice"] #todaySection, .family-game[data-view="practice"] #mistakeSection,
    .family-game[data-view="notebook"] #gameHero, .family-game[data-view="notebook"] #todaySection, .family-game[data-view="notebook"] #testSection { display: none; }
    .family-game button:focus-visible, .family-game a:focus-visible, .family-game input:focus-visible, .family-game textarea:focus-visible, .family-game select:focus-visible { outline: 3px solid #e9b843; outline-offset: 3px; }
    .family-game input:focus, .family-game textarea:focus, .family-game select:focus { border-color: var(--accent); }
    .family-game button:disabled { cursor: default; opacity: .5; }
    .family-game .game-footer { text-align: center; margin-top: 25px; font-size: 10px; color: #a0aa97; letter-spacing: 1px; }
    @media (max-width: 760px) {
      .family-game { padding: 18px 15px 30px; }
      .family-game #gameHero { padding: 25px; }
      .family-game #practiceChoices { grid-template-columns: minmax(0, 1fr); }
      .hero-copy { max-width: 69%; }
      .hero-art { width: 33%; right: 0; top: 43px; height: 205px; }
      .family-game .notebook-layout { grid-template-columns: minmax(0, 1fr); }
      .family-game .notebook-shelf { border-left: 0; border-top: 1px solid #e7ebdf; padding: 20px 0 0; }
    }
    @media (max-width: 460px) {
      .brand-title { font-size: 17px; }
      .brand-note { font-size: 9px; letter-spacing: 1px; }
      .family-game .profile-choices { gap: 8px; }
      .family-game .profile-card { gap: 8px; padding: 12px 9px; min-height: 73px; border-radius: 15px; }
      .profile-avatar { flex-basis: 30px; height: 33px; font-size: 21px; border-radius: 10px; }
      .profile-card strong { font-size: 12px; }
      .profile-card small { font-size: 9px; line-height: 1.5; }
      .profile-check { display: none; }
      .game-nav a { flex: 1; justify-content: center; padding: 9px 6px; font-size: 11px; }
      .family-game main > section { padding: 20px 18px; border-radius: 20px; }
      .family-game #gameHero { min-height: 310px; padding: 24px 21px; }
      .hero-copy { max-width: 100%; }
      .hero-badge { max-width: 78%; font-size: 9px; }
      .family-game #heroTitle { font-size: 27px; max-width: 73%; margin-top: 14px; }
      .hero-description { max-width: 72%; font-size: 11px; }
      .hero-art { width: 29%; right: 4px; top: 16px; height: 155px; opacity: .95; }
      .family-game .hero-actions { gap: 8px; }
      .family-game button.game-primary { padding: 12px 15px; font-size: 12px; }
      .family-game .hero-secondary { padding: 12px; font-size: 11px; }
      .hero-stats { gap: 22px; margin-top: 21px; }
      .hero-stats strong { font-size: 21px; }
      .section-caption { display: none; }
      .family-game .section-heading h2 { font-size: 17px; }
      .family-game #testSection { padding: 22px 18px; }
      .family-game #testPrompt { padding: 30px 9px; font-size: 29px; }
      .family-game #testSection .row > label { flex-basis: 100%; }
      .family-game #submitAnswer { flex-basis: 100%; margin-bottom: 8px; }
    }
    .textbook-page-preview { margin-top: 14px; }
    .textbook-page-image { display: block; width: 100%; max-width: 780px; height: auto; margin: 0 auto; border: 1px solid #e2e7ed; border-radius: 8px; background: white; }
    .textbook-page-link { display: inline-block; margin-top: 14px; padding: 10px 14px; border: 1px solid currentColor; border-radius: 10px; color: #135c70; font-weight: 600; text-decoration: none; }
    .textbook-page-link:hover { text-decoration: underline; }
    .textbook-result-tools { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; align-items: center; margin-left: auto; min-width: 0; }
    .textbook-result-tools[hidden] { display: none; }
    .textbook-result-tools span { font-size: 12px; white-space: nowrap; }
    .textbook-page-summary { cursor: pointer; padding: 8px 0; }
    .textbook-page-summary:focus-visible { outline: 2px solid #135c70; outline-offset: 4px; }
    .textbook-page-meta { display: inline; font-size: 12px; color: #526779; }
    .textbook-page-title { display: block; margin: 8px 0; font-size: 16px; }
    .textbook-fold-state { color: #135c70; font-size: 13px; font-weight: 600; }
    .textbook-page-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 14px; }
    .textbook-page-actions .textbook-page-link { margin-top: 0; }
    .textbook-reader { margin-top: 20px; border: 1px solid #dce3eb; border-radius: 14px; padding: 12px; }
    .textbook-reader > summary, .textbook-contents > summary { cursor: pointer; padding: 8px; font-weight: 700; }
    .textbook-reader-layout { display: grid; grid-template-columns: clamp(136px, 13vw, 168px) minmax(0, 1fr); gap: 12px; margin-top: 12px; }
    .textbook-contents { max-height: 75vh; overflow: auto; background: #f3f5f8; border-radius: 10px; }
    #textbookToc { display: grid; gap: 6px; padding: 8px; }
    #textbookToc button { text-align: left; padding: 10px; font-size: 12px; border-radius: 8px; }
    #textbookToc button[aria-current="true"] { color: #39266d; background: #e9e2fb; border-color: #7962bb; }
    .textbook-stage { min-width: 0; }
    .reader-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 8px; background: #f1f4f8; border-radius: 10px; font-size: 13px; }
    .reader-toolbar button { flex-shrink: 0; white-space: nowrap; padding: 8px; }
    #textbookPageRange { white-space: nowrap; }
    .reader-toolbar label { display: flex; align-items: center; gap: 4px; margin: 0; }
    #textbookPageInput { width: 65px; }
    .textbook-page-viewport { max-height: 78vh; overflow: auto; background: #e9edf2; border-radius: 10px; padding: 10px; }
    .textbook-page-image { cursor: zoom-in; }
    .textbook-stage .textbook-page-image { max-width: none; }
    #textbookZoom { width: 94vw; max-width: 1500px; height: 94vh; border: 0; border-radius: 14px; padding: 12px; }
    #textbookZoom::backdrop { background: #16202bd9; }
    #textbookZoom[open] { display: flex; flex-direction: column; }
    #textbookZoom .zoom-controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    #textbookZoomViewport { flex: 1; min-height: 0; overflow: auto; background: #e6eaf0; margin-top: 10px; }
    #textbookZoomImage { display: block; height: auto; margin: auto; max-width: none; }
    @media (max-width: 760px) { .textbook-reader-layout { grid-template-columns: minmax(0, 1fr); } .textbook-contents { max-height: 240px; } .textbook-reader { padding: 8px; } .reader-toolbar button { padding: 8px; } }
    /* STUDY_SUPPORT_STYLE */
    @media (prefers-reduced-motion: reduce) { .family-game * { transition: none !important; scroll-behavior: auto !important; } }
  </style>
</head>
<body>
  <header>
    <div class="game-brand game-only"><div class="brand-symbol" aria-hidden="true"><svg viewBox="0 0 40 40"><path d="M20 4l4.7 10.8L36 20l-11.3 4.7L20 36l-4.7-11.3L4 20l11.3-5.2z" fill="currentColor"/><circle cx="20" cy="20" r="5" fill="#1d8978"/></svg></div><div><div class="brand-title">学习探险队</div><div class="brand-note">LEARNING ADVENTURE · 每一步，都算数</div></div></div>
    <h1>DD-1.0 学习工作区</h1>
    <p class="muted">上传资料后先复核，再保存到错题本。今日任务可直接进入测验，刷新后可恢复进度。</p>
    <div class="grid">
      <label>账号 ID <input id="account" autocomplete="off" placeholder="开发模式账号"></label>
      <label>学习者 ID <input id="learner" autocomplete="off" placeholder="当前学习者"></label>
    </div>
    <nav class="row" aria-label="学习导航"><a href="/">返回聊天</a><a href="#todaySection">今日任务</a><a href="#uploadSection">上传资料</a><a href="#mistakeSection">错题本</a><a href="#testSection">测验</a><a href="#variantSection">变式审核</a></nav>
    <p id="contextStatus" class="status" role="status"></p>
    <button id="reloadContext" class="secondary" hidden>刷新学习者状态</button>
    <div class="row"><button id="loadLearners" class="secondary">读取学习者</button><button id="loadHealth" class="secondary">读取服务状态</button></div>
    <div class="game-only"><p class="profile-heading">选择今天的冒险档案</p><div id="profileChoices" class="profile-choices"></div></div>
    <nav class="game-nav game-only" aria-label="冒险导航"><a href="#todaySection" data-game-view="home" aria-current="page">⌂ 冒险首页</a><a href="#testSection" data-game-view="practice">✧ 挑战答题</a><a href="#mistakeSection" data-game-view="notebook">▣ 错题收藏</a></nav>
    <p id="gameNotice" class="game-only status" role="status"></p>
  </header>
  <main>
    <section id="gameHero" class="game-only">
      <div class="hero-copy"><span id="heroBadge" class="hero-badge">新的数学冒险，准备出发</span><h1 id="heroTitle">今天，探索一点新东西。</h1><p id="heroDescription" class="hero-description">选好你的档案，挑一道小挑战。一步一步，把不会的变成会的。</p><div class="hero-actions"><button id="startAdventure" class="game-primary" disabled>开始今日挑战 ↗</button><button id="quickNotebook" class="hero-secondary">收藏一道错题</button></div><div class="hero-stats"><div><strong id="heroGraded">—</strong><span>完成练习</span></div><div><strong id="heroIndependent">—</strong><span>独立作答</span></div><div><strong id="heroMistakes">—</strong><span>错题收藏</span></div></div></div>
      <div class="hero-art" aria-hidden="true">
        <svg class="junior-scene" viewBox="0 0 330 285"><ellipse cx="166" cy="255" rx="117" ry="16" fill="#a8d9bc" opacity=".55"/><path d="M59 194Q167 141 271 194L240 230Q171 259 84 229Z" fill="#73b997"/><path d="M59 194Q157 153 271 194Q190 220 59 194Z" fill="#a5d787"/><path d="M104 221l12 25 37 17 49-2 30-24 8-17" fill="#82a790"/><path d="M96 198l23-25m104 25l-17-20" stroke="#d0eaa6" stroke-width="7" stroke-linecap="round"/><rect x="234" y="125" width="5" height="60" rx="2" fill="#6e8b79"/><path d="M239 125l35 9-35 11Z" fill="#ffa970"/><path d="M159 183l-24 20m59-20l25 21" stroke="#b77e30" stroke-width="11" stroke-linecap="round"/><path d="M137 146l-20-8m82 8l20-15" stroke="#d6963d" stroke-width="13" stroke-linecap="round"/><rect x="130" y="91" width="73" height="106" rx="35" fill="#f6bd59"/><path d="M131 133h72v16h-72Z" fill="#facd76"/><ellipse cx="150" cy="126" rx="5" ry="7" fill="#594c39"/><ellipse cx="183" cy="126" rx="5" ry="7" fill="#594c39"/><path d="M151 145q16 15 31 0" stroke="#865830" stroke-width="4" fill="none" stroke-linecap="round"/><path d="M143 94l-8-13 15-5 10 14m26 4l10-16 12 7-10 12" fill="#82a76d"/><rect x="157" y="165" width="20" height="18" rx="5" fill="#fdf2cf"/><text x="162" y="179" fill="#ad7f37" font-size="15" font-weight="bold">+</text><circle cx="90" cy="87" r="30" fill="#ffffffa8"/><text x="76" y="95" fill="#609d83" font-size="25" font-weight="bold">×</text><circle cx="247" cy="69" r="23" fill="#fff0b9"/><text x="238" y="77" fill="#bf9544" font-size="25">7</text><path d="M222 108l6 7-6 7-6-7Z" fill="#70b9ac"/><path d="M71 135l5 6-5 6-5-6Z" fill="#f3b66c"/><path d="M178 51l3-7 3 7 7 3-7 3-3 7-3-7-7-3Z" fill="#f9f1ce"/></svg>
        <svg class="senior-scene" viewBox="0 0 330 285"><circle cx="189" cy="129" r="96" fill="#7160ad" opacity=".18"/><circle cx="189" cy="129" r="77" fill="none" stroke="#8d78be" stroke-dasharray="3 8" opacity=".5"/><ellipse cx="172" cy="191" rx="136" ry="28" fill="none" stroke="#7a62a9" stroke-width="2" transform="rotate(-24 172 191)"/><circle cx="162" cy="177" r="70" fill="#7660b8"/><path d="M103 169q74-41 123-4m-124 36q58-15 114 11" stroke="#9078c5" stroke-width="10" fill="none"/><g transform="rotate(22 182 105)"><path d="M161 80l-22 29 18 20m46-50l23 32-21 16" fill="#f2ac8b"/><path d="M163 58q19-37 38 0l6 62h-50Z" fill="#eeefce"/><path d="M171 31q11-17 22 0l7 24h-35Z" fill="#d7ec8d"/><circle cx="182" cy="77" r="13" fill="#6ba8b7"/><circle cx="182" cy="77" r="8" fill="#badbe4"/><path d="M165 121l17 32 18-32Z" fill="#f5be75"/><path d="M172 122l10 20 10-20Z" fill="#fff1b7"/></g><circle cx="77" cy="69" r="19" fill="#b7b3dc"/><path d="M47 78q33-20 60-6" stroke="#dedbf0" stroke-width="5" fill="none"/><path d="M249 71l4-9 4 9 9 4-9 4-4 9-4-9-9-4Z" fill="#deeaa4"/><path d="M247 221l3-6 3 6 6 3-6 3-3 6-3-6-6-3Z" fill="#ddcbef"/><circle cx="60" cy="199" r="3" fill="#ddd4ec"/><circle cx="288" cy="140" r="3" fill="#c8d79c"/><circle cx="221" cy="31" r="2" fill="#e9e2f2"/><text x="122" y="242" fill="#b9a4db" font-size="16" font-weight="bold">− (−) = +</text></svg>
      </div>
    </section>
    <section id="todaySection">
      <div class="section-heading game-only"><div><span class="section-eyebrow">CHOOSE YOUR ADVENTURE</span><h2>选好课本，开始冒险</h2></div><span id="challengeCount" class="section-caption">先选择你的档案</span></div>
      <div class="chapter-picker game-only" id="textbookMap">
        <div class="row"><label>学科 <select id="textbookSubject" disabled></select></label><label>课本 <select id="textbookBook" disabled></select></label><label>单元 / 章节（可选）<select id="textbookChapter" disabled></select></label></div>
        <p class="chapter-note">不选章节，就在整本书范围内学习；选择章节后，阅读与挑战同步切换。</p>
        <p class="chapter-note" id="textbookEdition">人教新版教材 · 选择档案后查看</p><p id="textbookSubjectNote" class="chapter-note"></p>
        <details><summary id="chapterPickerLabel">浏览本册全部章节</summary><div id="chapterChoices" class="chapter-options" role="group" aria-labelledby="chapterPickerLabel"></div></details>
        <h3 id="selectedChapterTitle" class="chapter-heading" aria-live="polite">先选择你的档案</h3>
        <p id="scopeAvailability" class="chapter-note" role="status"></p>
        <div class="row game-only"><label>挑战难度 <select id="homeDifficulty"><option value="auto">自动进阶（推荐）</option><option value="easy">简单</option><option value="normal">正常</option><option value="hard">困难</option></select></label><span id="homeDifficultyNote" class="chapter-note"></span></div>
        <div class="row"><button id="scopeChallenge" class="game-primary" disabled>开始挑战 ↗</button><button id="textbookSearch" class="secondary" disabled>阅读整本书</button><button id="studySupportOpen" class="secondary" type="button" disabled>打开理解工坊</button></div>
        <!-- STUDY_SUPPORT_PANEL -->
        <div id="familyReview" class="family-review game-only" hidden><h3>到期复习</h3></div>
        <details id="practicePicker" class="practice-picker game-only" hidden><summary id="practicePickerSummary">自己挑一道题</summary></details>
        <details id="textbookReader" class="textbook-reader"><summary>教材阅读 · 展开 / 收起</summary>
          <div class="textbook-reader-layout">
            <details id="textbookContents" class="textbook-contents" open><summary>本册目录</summary><nav id="textbookToc" aria-label="教材目录"></nav></details>
            <div class="textbook-stage">
              <div class="reader-toolbar"><button id="textbookPrev" type="button">上一页</button><span id="textbookPageRange" aria-live="polite"></span><button id="textbookNext" type="button">下一页</button><label>跳至 <input id="textbookPageInput" type="number" min="1" aria-label="书内页码"></label><button id="textbookJump" type="button">跳转</button><div id="textbookResultTools" class="textbook-result-tools" hidden><span id="textbookResultCount"></span><button id="textbookExpandAll" type="button">展开本页</button><button id="textbookCollapseAll" type="button">收起本页</button></div></div>
              <div class="row"><label>查找内容（可选）<input id="textbookQuery" maxlength="160" placeholder="例如：有理数减法"></label><button id="textbookFind" type="button">查找</button><button id="textbookBrowse" type="button">返回顺序阅读</button></div>
              <p id="textbookStatus" class="chapter-note" role="status"></p>
              <div id="textbookPager" hidden></div><div id="textbookResults" class="textbook-page-viewport"></div>
            </div>
          </div>
        </details>
      </div>
      <h2>今日任务</h2>
      <button id="loadToday" class="secondary">刷新今日任务</button>
      <div id="today" class="review-list muted">选择学习者后可查看到期任务。</div>
      <div id="progress" class="status muted"></div>
      <h3>选一道练习</h3>
      <div id="practiceChoices" class="review-list muted">选择学习者后，显示适合当前年级的练习。</div>
    </section>
    <section id="uploadSection">
      <h2>上传与分析</h2>
      <div class="row">
        <label>资料类型 <select id="kind"><option value="paper">试卷</option><option value="homework">作业</option><option value="answer_key">参考答案</option></select></label>
        <label>文件（照片/PDF/Word/Excel；支持 .docx、.xlsx） <input id="file" type="file" accept="application/pdf,image/png,image/jpeg,.docx,.xlsx,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" multiple></label>
        <button id="upload">上传资料</button>
      </div>
      <div id="documents" class="document-list muted">尚未上传资料。</div>
      <div class="row"><label>当前文档 ID <input id="document" readonly></label><label>参考答案资料（可选） <select id="answerDocument"><option value="">不关联</option></select></label><button id="makeBatch" class="secondary">创建整卷批次</button><button id="analyze" class="secondary">请求分析</button><button id="cancelBatch" class="secondary">取消批次</button></div>
      <p id="uploadStatus" class="status" role="status"></p>
    </section>
    <section id="importSection">
      <h2>候选复核与确认</h2>
      <div class="row"><label>批次 ID <input id="batch" autocomplete="off"></label><button id="refreshItems" class="secondary">读取页状态与候选</button><button id="confirm" disabled>确认选中项</button></div>
      <div id="pageSummary" class="page-summary muted">尚未读取批次页面。</div>
      <div id="items" class="status muted">尚未读取候选。</div>
    </section>
    <section id="mistakeSection">
      <div class="section-heading game-only"><div><span class="section-eyebrow">MY DISCOVERY BOOK</span><h2>错题收藏夹</h2></div><span class="section-caption">不会的，也值得收藏</span></div>
      <h2>错题、诊断与复习</h2>
      <div class="row"><button id="loadMistakes" class="secondary">读取错题本</button><button id="loadReview" class="secondary">读取到期复习</button></div>
      <p class="muted">输入题干后自动匹配已有知识目标，可手动修改；未匹配时可先保存，暂不创建复习卡。</p>
      <div class="notebook-layout"><div class="review-fields">
        <p class="notebook-intro game-only">记下今天想弄懂的一题，给下次的自己留个线索。</p>
        <label>题干 <textarea id="manualQuestion" rows="3" maxlength="20000" placeholder="输入错题题干（必填）"></textarea></label>
        <div class="notebook-answer-pair"><label>学生作答 <textarea id="manualStudentAnswer" rows="2" maxlength="10000" placeholder="可留空"></textarea></label>
        <label>正确答案 <textarea id="manualCorrectAnswer" rows="2" maxlength="10000" placeholder="可留空"></textarea></label></div>
        <label>知识目标（可选） <select id="manualObjective"><option value="">暂不分类</option></select><small id="manualObjectiveStatus" class="muted" role="status"></small></label>
        <label>备注 <textarea id="manualNote" rows="2" maxlength="5000" placeholder="例如错因、老师提示"></textarea></label>
        <button id="saveManualMistake">手动加入错题本</button>
        <p id="manualStatus" class="status" role="status"></p>
      </div><div class="notebook-shelf"><h3 class="game-only">我的收藏</h3>
      <div id="mistakes" class="status muted">尚未读取错题。</div></div></div>
      <div class="row"><label>错题 ID <input id="mistake" autocomplete="off"></label><button id="diagnose" class="secondary">请求待复核诊断</button></div>
    </section>
    <section id="testSection">
      <div class="section-heading game-only"><div><span class="section-eyebrow">ONE QUESTION, ONE STEP</span><h2 id="challengeTitle">小挑战，轮到你啦</h2><p id="practiceChapter" class="chapter-note"></p></div><button id="changeChapter" type="button">换个单元 ↗</button></div>
      <div class="row game-only"><label>下一题难度 <select id="practiceDifficulty"><option value="auto">自动进阶（推荐）</option><option value="easy">简单</option><option value="normal">正常</option><option value="hard">困难</option></select></label><span id="practiceDifficultyNote" class="chapter-note" role="status"></span></div>
      <p id="questionBadge" class="chapter-note game-only"></p><p id="questionCredit" class="chapter-note game-only"></p>
      <div id="gamePracticeEmpty" class="practice-empty game-only"><p>准备好了？从一道小题开始。</p><button id="practiceStart" class="game-primary" disabled>来一题 ↗</button></div>
      <h2>数学练习</h2>
      <p class="muted">从今日任务中选一道题，填写答案后提交。刷新页面可恢复当前练习。</p>
      <details><summary>练习编号（排查问题时使用）</summary>
      <div class="row"><label>题目版本 ID <input id="questionVersion" autocomplete="off"></label><label>复习卡 ID（可选） <input id="card" autocomplete="off"></label><button id="startTest">开始测验</button></div>
      <div class="row"><label>测验会话 ID <input id="session" autocomplete="off"></label><label>作答项 ID <input id="testItem" autocomplete="off"></label><label>Attempt ID <input id="attempt" autocomplete="off"></label></div>
      </details>
      <div class="row"><button id="restoreTest" class="secondary">恢复测验</button><button id="refreshTest" class="secondary">读取状态</button><button id="requestHint" class="secondary">请求提示</button><button id="cancelTest" class="secondary">取消测验</button></div>
      <div id="testPrompt" class="status muted">题面将在开始或恢复测验后显示。</div>
      <div class="row"><label>原始作答 <input id="answer" autocomplete="off"></label><button id="submitAnswer" class="secondary">提交并等待判分</button><button id="refreshAttempt" class="secondary">读取判分</button><button id="requestReview" class="secondary">申请复核</button></div>
      <div id="testStatus" class="status muted">尚未开始测验。</div>
      <div id="gameHint" class="game-only" hidden></div>
      <div id="gameFeedback" class="game-feedback game-only" hidden><h3 id="feedbackTitle"></h3><p id="feedbackText"></p><details id="solutionDetails" hidden><summary>看看解题过程</summary><p id="solutionText"></p></details><p id="roundProgress" role="status"></p><div class="row"><button id="nextChallenge" class="game-primary">继续挑战 →</button><button id="restartRound" class="secondary" hidden>再练一轮</button></div></div>
    </section>
    <section id="variantSection">
      <h2>人工变式审核</h2>
      <p class="muted">审核人核对母题、题干和答案后批准。批准版本仅供当前学习者使用；撤销保留已用成绩。</p>
      <div class="row"><label>知识目标 ID <input id="variantObjective" autocomplete="off"></label><label>已批准母题版本 ID <input id="variantSource" autocomplete="off"></label><button id="createVariant" class="secondary">生成待审核草稿</button><button id="loadVariants" class="secondary">读取审核任务</button></div>
      <div id="variantJobs" class="review-list"></div>
      <div id="variantDetail" class="review-fields"></div>
    </section>
    <section id="debugSection"><details>
      <summary>操作详情</summary>
      <h2>结果</h2>
      <pre id="output" class="status" aria-live="polite">等待操作。</pre>
    </details></section>
  </main>
  <p class="game-footer game-only">不用一次学会所有。今天前进一小步，就很棒。</p>
  <dialog id="textbookZoom" aria-label="教材原页放大"><div class="zoom-controls"><strong id="textbookZoomTitle"></strong><button id="textbookZoomOut" type="button" aria-label="缩小">−</button><span id="textbookZoomLevel">100%</span><button id="textbookZoomIn" type="button" aria-label="放大">＋</button><button id="textbookZoomReset" type="button">适应宽度</button><button id="textbookZoomClose" type="button">关闭</button></div><div id="textbookZoomViewport"><img id="textbookZoomImage" alt=""></div></dialog>
  <script>
    const $ = (id) => document.getElementById(id);
    const browserSessionMode = false;
    const familyGameMode = false;
    let textbookBooks = [], textbookSubjects = [], textbookGeneration = 0, textbookObjectUrls = [];
    const publicBasePath = "";
    let serverContextMode = false, contextVersion = 0, contextEpoch = 0;
    let manualObjectives = [], manualObjectiveChosen = false;
    let gameLearners = [], gameChoices = [], gameStarting = false, gameSubmitting = false;
    let gameCatalog = [], gameObjectives = [], gameTasks = [], gameBook = '', gameChapter = '', gameChangingChapter = false;
    let gameGraded = 0, gameMistakes = 0, gameItemStatus = '', gameRefreshGeneration = 0;
    const gameUpdatedAttempts = new Set();
    let gameCompletedChoices = new Set();
    let gameDifficulty = 'auto', gameGuidance = {}, gameLoadingChoices = false;
    const difficultyNames = {easy:'简单',normal:'正常',hard:'困难'};
    const pendingRequests = new Set();
    class StaleContextError extends Error {}
    const workspaceStorage = browserSessionMode ? sessionStorage : localStorage;
    const parseSaved = (key) => { try { return JSON.parse(workspaceStorage.getItem(key) || '{}'); } catch (_) { return {}; } };
    function clearWorkspace(message = '', purge = true) {
      contextEpoch += 1;
      pendingRequests.forEach((controller) => controller.abort()); pendingRequests.clear();
      importRefreshGeneration += 1; releaseSourceObjectUrls();
      if (purge) {
        for (const storage of [localStorage, sessionStorage]) {
          Object.keys(storage).filter((key) => key.startsWith('dd-learning-test') || key.startsWith('dd-learning-import') || key.startsWith('dd-learning-chapter:')).forEach((key) => storage.removeItem(key));
        }
      }
      uploadedDocuments = []; savedTest = {};
      document.querySelectorAll('main input, main textarea').forEach((field) => { field.value = ''; });
      ['documents','items','pageSummary','mistakes','testPrompt','testStatus','output','uploadStatus','manualStatus','today','progress','practiceChoices','variantJobs','variantDetail'].forEach((id) => { if ($(id)) $(id).replaceChildren(); });
      $('manualObjective').replaceChildren(new Option('暂不分类', ''));
      manualObjectives = []; manualObjectiveChosen = false;
      $('manualObjectiveStatus').textContent = '';
      $('answerDocument').replaceChildren(new Option('不关联', ''));
      $('confirm').disabled = true;
      document.querySelector('main').inert = true;
      $('contextStatus').textContent = message;
      if (message.includes('登录')) { $('account').value = ''; $('learner').value = ''; }
      $('reloadContext').hidden = !message;
      if (familyGameMode) {
        resetGameWorkspace(message);
        if ($('gameLoginLink')) $('gameLoginLink').hidden = !message.includes('登录');
      }
    }
    $('reloadContext').onclick = () => window.location.reload();
    const serviceUrl = (path) => publicBasePath + path;
    const saved = browserSessionMode ? {} : JSON.parse(localStorage.getItem('dd-learning-context') || '{}');
    let savedTest = browserSessionMode ? {} : JSON.parse(localStorage.getItem('dd-learning-test') || '{}');
    let uploadedDocuments = [];
    let sourceObjectUrls = [];
    let sourceRenderGeneration = 0;
    let importRefreshGeneration = 0;
    $('account').value = browserSessionMode ? '' : (saved.account || '');
    $('learner').value = browserSessionMode ? '' : (saved.learner || '');
    const contextNamespace = () => encodeURIComponent(location.origin + publicBasePath) + ':' + encodeURIComponent($('account').value.trim()) + ':' + encodeURIComponent($('learner').value.trim()) + ':' + contextVersion;
    const testStateKey = () => browserSessionMode ? 'dd-learning-test:' + contextNamespace() : 'dd-learning-test';
    const chapterStateKey = () => 'dd-learning-chapter:' + contextNamespace();
    const importStateKey = () => 'dd-learning-import:' + (browserSessionMode ? contextNamespace() : encodeURIComponent($('account').value.trim()) + ':' + encodeURIComponent($('learner').value.trim()));
    // STUDY_SUPPORT_SCRIPT
    function saveImportState() {
      const state = {documents: uploadedDocuments, batchId: $('batch').value.trim()};
      workspaceStorage.setItem(importStateKey(), JSON.stringify(state));
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
        const state = parseSaved(importStateKey());
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
      if (!browserSessionMode) localStorage.setItem('dd-learning-context', JSON.stringify({account, learner}));
      const h = {'Accept': 'application/json'};
      if (account && !browserSessionMode) h['X-Account-Id'] = account;
      if (learner && !serverContextMode) h['X-Learner-Id'] = learner;
      if (serverContextMode) h['X-Learner-Context-Version'] = String(contextVersion);
      if (browserSessionMode) {
        const csrf = document.cookie.split('; ').find((part) => part.startsWith('__Host-dd_learning_csrf='));
        if (csrf) h['X-CSRF-Token'] = decodeURIComponent(csrf.split('=')[1]);
      }
      return h;
    }
    async function fetchScoped(path, options = {}, binary = false) {
      const epoch = contextEpoch, namespace = contextNamespace();
      const controller = new AbortController(); pendingRequests.add(controller);
      try {
        const response = await fetch(serviceUrl(path), {...options, cache: 'no-store', signal: controller.signal,
          headers: Object.assign(contextHeaders(), options.headers || {})});
        const body = binary && response.ok ? await response.blob() : await response.text();
        if (epoch !== contextEpoch || namespace !== contextNamespace()) throw new StaleContextError();
        let data = body;
        if (!(binary && response.ok)) { try { data = JSON.parse(body); } catch (_) {} }
        if (!response.ok) {
          if (response.status === 401 || data.error?.code === 'LEARNER_CONTEXT_CHANGED') {
            clearWorkspace(response.status === 401 ? '登录状态已失效，请重新登录。' : '学习者已变化，请刷新工作台后重试。');
            throw new StaleContextError();
          }
          throw new Error(typeof data === 'string' ? data : (data.error?.message || '操作未成功'));
        }
        return data;
      } catch (error) {
        if (epoch !== contextEpoch || error.name === 'AbortError') throw new StaleContextError();
        throw error;
      } finally { pendingRequests.delete(controller); }
    }
    const call = (path, options = {}) => fetchScoped(path, options);
    function show(value) {
      $('output').textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
      if (familyGameMode) $('gameNotice').textContent = typeof value === 'string' ? value : '';
    }
    function setStatus(value) { $('uploadStatus').textContent = typeof value === 'string' ? value : JSON.stringify(value); }
    function testStatus(value) { $('testStatus').textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2); }
    function setGameView(view, navigate = true) {
      if (!familyGameMode) return;
      if (!$('learner').value && view !== 'home') { $('gameNotice').textContent = '先选一个冒险档案，我们就出发。'; return; }
      document.body.dataset.view = view;
      document.querySelectorAll('[data-game-view]').forEach((link) => {
        if (link.dataset.gameView === view) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
      });
      if (navigate) history.replaceState(null, '', {home:'#todaySection', practice:'#testSection', notebook:'#mistakeSection'}[view]);
      if (view === 'notebook') $('loadMistakes').onclick();
    }
    function updateGameTheme() {
      if (!familyGameMode) return;
      const selected = gameLearners.find((item) => item.id === $('learner').value);
      const senior = selected?.curriculum_id === 'math-g7-v1';
      document.body.dataset.grade = senior ? '7' : '2';
      document.querySelectorAll('.profile-card').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.learner === selected?.id)));
      $('heroBadge').textContent = selected ? (senior ? '七年级 · 星球探索计划' : '二年级 · 数字森林探险') : '新的数学冒险，准备出发';
      $('heroTitle').textContent = selected ? (senior ? '下一站，突破你的解题边界。' : '去数字森林，收集新本领。') : '今天，探索一点新东西。';
      $('heroDescription').textContent = selected ? (senior ? '从生活问题起航。读懂条件，理清关系，再一步步算出答案。' : '购物、分礼物、排座位，生活里藏着好多数学小秘密。挑一关试试！') : '选好你的档案，挑一道小挑战。一步一步，把不会的变成会的。';
      $('challengeTitle').textContent = senior ? '星球挑战，等你解锁思路' : '小挑战，轮到你啦';
    }
    function resetGameWorkspace(message = '') {
      gameRefreshGeneration += 1;
      resetStudySupport(); $('studySupportOpen').disabled = true;
      releaseTextbookPages(); textbookBooks = []; textbookSubjects = [];
      $('textbookSubject').replaceChildren(); $('textbookSubject').disabled = true; $('textbookSubjectNote').textContent = '';
      $('textbookBook').replaceChildren(); $('textbookChapter').replaceChildren(); $('textbookResults').replaceChildren();
      $('textbookBook').disabled = true; $('textbookChapter').disabled = true; $('textbookSearch').disabled = true;
      $('textbookQuery').value = ''; $('textbookStatus').textContent = ''; $('textbookEdition').textContent = '人教新版教材 · 选择档案后查看';
      gameChoices = []; gameGraded = 0; gameMistakes = 0; gameItemStatus = '';
      gameCatalog = []; gameObjectives = []; gameTasks = []; gameBook = ''; gameChapter = ''; gameChangingChapter = false;
      $('chapterChoices').replaceChildren(); $('selectedChapterTitle').textContent = '先选择你的档案'; $('practiceChapter').textContent = '';
      gameStarting = false; gameSubmitting = false; gameUpdatedAttempts.clear();
      gameCompletedChoices.clear(); gameDifficulty = 'auto'; gameGuidance = {}; gameLoadingChoices = false; $('questionBadge').textContent = ''; $('questionCredit').replaceChildren(); $('solutionDetails').hidden = true; $('roundProgress').textContent = ''; $('restartRound').hidden = true;
      ['heroGraded','heroIndependent','heroMistakes'].forEach((id) => { $(id).textContent = '—'; });
      $('challengeCount').textContent = '选择档案后，冒险地图就会出现';
      $('startAdventure').disabled = true; $('practiceStart').disabled = true;
      $('gameHint').textContent = ''; $('gameHint').hidden = true;
      $('gameFeedback').hidden = true; $('gamePracticeEmpty').hidden = false;
      $('gameNotice').textContent = message;
      $('practicePicker').hidden = true; $('practicePicker').open = false; $('familyReview').hidden = true;
      setGameView('home', false); updateGameTheme(); updateGameAnswerControls();
    }
    function renderGameProfiles(items) {
      if (!familyGameMode) return;
      gameLearners = items;
      const target = $('profileChoices'); target.replaceChildren();
      [...items].sort((a, b) => a.curriculum_id.localeCompare(b.curriculum_id)).forEach((item) => {
        const senior = item.curriculum_id === 'math-g7-v1';
        const button = document.createElement('button'); button.className = 'profile-card'; button.type = 'button';
        button.dataset.grade = senior ? '7' : '2'; button.dataset.learner = item.id;
        button.setAttribute('aria-label', '选择' + item.display_name); button.setAttribute('aria-pressed', 'false');
        const avatar = document.createElement('span'); avatar.className = 'profile-avatar'; avatar.textContent = senior ? '✧' : '✿'; avatar.setAttribute('aria-hidden', 'true');
        const label = document.createElement('span');
        const title = document.createElement('strong'); title.textContent = item.display_name;
        const caption = document.createElement('small'); caption.textContent = senior ? '星球探索 · 生活数学' : '数字森林 · 生活数学';
        label.append(title, caption);
        const check = document.createElement('span'); check.className = 'profile-check'; check.textContent = '✓'; check.setAttribute('aria-hidden', 'true');
        button.append(avatar, label, check);
        button.onclick = async () => {
          if ($('learner').value === item.id) return;
          target.querySelectorAll('button').forEach((other) => { other.disabled = true; });
          $('learner').value = item.id;
          try { await $('learner').onchange(); } finally { target.querySelectorAll('button').forEach((other) => { other.disabled = false; }); }
        };
        target.append(button);
      });
      updateGameTheme();
    }
    function updateGameAnswerControls() {
      if (!familyGameMode) return;
      const active = Boolean($('testItem').value) && ['reserved','presented'].includes(gameItemStatus);
      $('gamePracticeEmpty').hidden = Boolean($('testItem').value);
      $('answer').disabled = !active || gameSubmitting;
      $('submitAnswer').disabled = !active || gameSubmitting;
      $('requestHint').hidden = !active;
      $('cancelTest').hidden = !active;
      $('requestReview').hidden = !$('attempt').value;
      $('submitAnswer').textContent = gameSubmitting ? '正在提交…' : '提交答案 →';
      updateChapterControls();
    }
    async function launchGameChoice(choice, cardId = '') {
      if (!choice || gameStarting || gameChangingChapter || gameSubmitting || gameItemStatus === 'grading_pending') return;
      if (!gameChoices.some((item) => item.question_version_id === choice.question_version_id)) return;
      if (['reserved','presented'].includes(gameItemStatus) && !window.confirm('当前题还没有作答，要换一道挑战吗？')) return;
      $('questionVersion').value = choice.question_version_id; $('card').value = cardId;
      setGameView('practice');
      await $('startTest').onclick();
    }
    function difficultyGuidance() { return gameGuidance[gameBook + '|' + gameChapter] || {difficulty:'easy', reason:'先从简单题开始；同一难度连续独立答对 4 道不同题后，尝试下一档。'}; }
    function selectedDifficulty() { return gameDifficulty === 'auto' ? difficultyGuidance().difficulty : gameDifficulty; }
    function roundChoices() {
      return gameChoices.some((choice) => choice.practice) ? gameChoices.filter((choice) => choice.practice?.difficulty === selectedDifficulty()) : gameChoices;
    }
    function gameNextChoice() {
      return roundChoices().find((choice) => !gameCompletedChoices.has(choice.question_version_id)) || null;
    }
    function saveGameRound() {
      workspaceStorage.setItem(chapterStateKey(), JSON.stringify({bookId:gameBook, chapterId:gameChapter, difficulty:gameDifficulty, completedIds:[...gameCompletedChoices]}));
    }
    function restartGameRound() {
      if (gameStarting || gameSubmitting || gameChangingChapter || gameLoadingChoices || ['reserved','presented','grading_pending'].includes(gameItemStatus)) return;
      roundChoices().forEach((choice) => gameCompletedChoices.delete(choice.question_version_id));
      saveGameRound();
      launchGameChoice(gameNextChoice());
    }
    function continueGameRound() {
      if (gameLoadingChoices) return;
      const next = gameNextChoice();
      if (next) launchGameChoice(next);
      else $('changeChapter').onclick();
    }
    function syncDifficulty() {
      $('homeDifficulty').value = gameDifficulty; $('practiceDifficulty').value = gameDifficulty;
      const label = difficultyNames[selectedDifficulty()];
      const message = gameChoices.some((c) => c.practice) ? (gameDifficulty === 'auto' ? '下一题：' + label + '。' + difficultyGuidance().reason : '下一题使用' + label + '难度。') : '此范围暂时只有起步题，尚未配置三档题。';
      $('homeDifficultyNote').textContent = message; $('practiceDifficultyNote').textContent = message;
    }
    function renderQuestionMeta() {
      if (!familyGameMode) return;
      const info = gameCatalog.find((c) => c.question_version_id === $('questionVersion').value)?.practice;
      $('testPrompt').classList.toggle('word-problem', Boolean(info));
      $('questionBadge').textContent = info ? difficultyNames[info.difficulty] + ' · ' + info.title + (info.extension ? ' · 思维拓展' : '') : '';
      const credit = $('questionCredit'); credit.replaceChildren();
      if (info?.source.kind === 'adapted') {
        credit.append(document.createTextNode('题目改编自 '));
        const link = document.createElement('a'); link.href = info.source.url; link.textContent = 'cn-math-taxonomy'; link.target = '_blank'; link.rel = 'noopener noreferrer'; credit.append(link);
        credit.append(document.createTextNode(' · ' + info.source.attribution + ' · '));
        const license = document.createElement('a'); license.href = info.source.license_url; license.textContent = info.source.license; license.target = '_blank'; license.rel = 'noopener noreferrer'; credit.append(license);
      }
    }
    function gameChapterTitle(id) {
      return (gameObjectives.find((item) => item.id === id)?.title || '数学练习').replace('理解减去负数的运算方向', '有理数 · 减去负数');
    }
    function selectedBook() { return textbookBooks.find((book) => book.id === gameBook); }
    function scopeTitle() { const book = selectedBook(); return book ? book.title + ' · ' + (book.chapters.find((c) => c.id === gameChapter)?.title || '整本书') : '先选择课本'; }
    function choicesInScope(bookId, chapterId = '') {
      return gameCatalog.filter((choice) => choice.textbook_scope?.book_id === bookId && (!chapterId || choice.textbook_scope.chapter_id === chapterId));
    }
    function updateChapterControls() {
      const busy = gameLoadingChoices || gameStarting || gameSubmitting || gameChangingChapter || gameItemStatus === 'grading_pending' || (Boolean($('testItem').value) && !gameItemStatus);
      $('chapterChoices').querySelectorAll('button').forEach((button) => { button.disabled = Boolean(busy); });
      $('textbookToc').querySelectorAll('button').forEach((button) => { button.disabled = Boolean(busy); });
      for (const id of ['textbookSubject','textbookBook','textbookChapter']) $(id).disabled = !textbookBooks.length || Boolean(busy);
      const active = $('testItem').value && ['reserved','presented','grading_pending'].includes(gameItemStatus);
      const eligible = roundChoices();
      const remaining = eligible.filter((choice) => !gameCompletedChoices.has(choice.question_version_id)).length;
      const completed = eligible.length - remaining, exhausted = eligible.length > 0 && !remaining;
      syncDifficulty();
      for (const id of ['homeDifficulty','practiceDifficulty']) $(id).disabled = Boolean(busy);
      $('startAdventure').disabled = (!roundChoices().length && !active) || Boolean(busy);
      $('scopeChallenge').disabled = !roundChoices().length || Boolean(busy);
      $('practiceStart').disabled = !roundChoices().length || Boolean(busy);
      const current = gameCatalog.find((choice) => choice.question_version_id === $('questionVersion').value);
      $('practiceChapter').textContent = current && !current.textbook_scope ? '此前的数学起步练习 · ' + gameChapterTitle(current.objective_id) : scopeTitle();
      $('startAdventure').textContent = active ? '继续当前挑战 ↗' : exhausted ? '本轮已完成 · 再练一轮' : gameChoices.length ? '开始所选范围挑战 ↗' : '所选范围暂未配题';
      $('scopeChallenge').textContent = active ? '继续当前挑战 ↗' : exhausted ? '本轮已完成 · 再练一轮' : gameChoices.length ? '开始挑战 · 剩余 ' + remaining + ' 题 ↗' : '暂未配题';
      $('practiceStart').textContent = exhausted ? '再练一轮' : '来一题 ↗';
      if (gameItemStatus === 'graded') {
        $('nextChallenge').textContent = remaining ? '继续出题 · ' + (gameChoices.some((c) => c.practice) ? difficultyNames[selectedDifficulty()] + ' · ' : '') + '剩余 ' + remaining + ' 题 →' : '选择其他章节 →';
        $('nextChallenge').onclick = continueGameRound;
        $('nextChallenge').disabled = Boolean(busy) || !textbookBooks.length;
        $('restartRound').hidden = !exhausted; $('restartRound').disabled = Boolean(busy);
        $('roundProgress').textContent = exhausted ? `本轮已完成 ${completed} / ${eligible.length} 道。本档已练完，可以换个难度、选择其他章节，或主动再练一轮。` : eligible.length ? `本轮已完成 ${completed} / ${eligible.length} 道（当前难度）。` : '当前难度暂未配题，请选择其他难度。';
      } else { $('restartRound').hidden = true; $('roundProgress').textContent = ''; }
    }
    function renderGameChapters() {
      gameChoices = choicesInScope(gameBook, gameChapter);
      const book = selectedBook(), target = $('chapterChoices'); target.replaceChildren();
      const chapters = book ? [{id:'', title:'整本书 · 不限章节'}, ...book.chapters] : [];
      chapters.forEach((chapter) => {
        const count = choicesInScope(gameBook, chapter.id).length;
        const button = document.createElement('button'); button.type = 'button'; button.className = 'chapter-option';
        button.dataset.chapter = chapter.id; button.setAttribute('aria-pressed', String(chapter.id === gameChapter));
        const title = document.createElement('strong'); title.textContent = chapter.title;
        const detail = document.createElement('small'); detail.textContent = count ? count + ' 道题 · 可挑战' : '可阅读 · 暂未配题';
        button.append(title, detail); button.onclick = () => selectLearningScope(gameBook, chapter.id); target.append(button);
      });
      $('selectedChapterTitle').textContent = scopeTitle();
      $('challengeCount').textContent = `${book?.chapters.length || 0} 个章节 · 当前 ${gameChoices.length} 道题`;
      $('scopeAvailability').textContent = gameChoices.length ? `当前范围有 ${gameChoices.length} 道题，按所选难度出题，尚未覆盖全部知识点。` : '所选范围暂未配题，可以先阅读教材。';
      $('gamePracticeEmpty').querySelector('p').textContent = gameChoices.length ? '准备好了？从所选范围的一道题开始。' : '所选范围暂未配题，请返回首页阅读教材或选择其他范围。';
      renderPracticeChoices(gameChoices, gameObjectives);
      renderReviewTasks(gameTasks.filter((task) => gameChoices.some((choice) => choice.objective_id === task.objective_id)), gameChoices);
      renderReaderToc(); updateChapterControls();
    }
    async function selectLearningScope(bookId, chapterId = '', openReader = false) {
      if (gameStarting || gameSubmitting || gameChangingChapter || gameItemStatus === 'grading_pending') { syncScopeSelectors(); return; }
      const book = textbookBooks.find((b) => b.id === bookId);
      if (!book || (chapterId && !book.chapters.some((c) => c.id === chapterId))) { syncScopeSelectors(); return; }
      if (bookId === gameBook && chapterId === gameChapter) { if (openReader) loadTextbookResults(); return; }
      const unfinished = ['reserved','presented'].includes(gameItemStatus);
      if (unfinished && !window.confirm('切换学习范围会跳过当前未完成的题目，继续吗？')) { syncScopeSelectors(); return; }
      const epoch = contextEpoch;
      gameChangingChapter = true; updateChapterControls();
      try {
        if (unfinished) await call('/api/v1/test-sessions/' + encodeURIComponent($('session').value) + '/cancel', {method:'POST'});
        if (epoch !== contextEpoch) return;
        workspaceStorage.removeItem(testStateKey()); savedTest = {};
        ['questionVersion','card','session','testItem','attempt','answer'].forEach((id) => { $(id).value = ''; });
        $('testPrompt').textContent = ''; testStatus(''); $('gameFeedback').hidden = true; $('gameHint').hidden = true;
        gameItemStatus = ''; gameBook = bookId; gameChapter = chapterId;
        saveGameRound();
        $('practicePicker').open = false;
        $('textbookQuery').value = ''; releaseTextbookPages(); syncScopeSelectors(); renderGameChapters(); updateGameAnswerControls(); show('');
        if (openReader || $('textbookReader').open) loadTextbookResults();
      } catch (error) { if (!(error instanceof StaleContextError)) { syncScopeSelectors(); show(error.message); } }
      finally { if (epoch === contextEpoch) { gameChangingChapter = false; updateChapterControls(); } }
    }
    function renderGameFeedback(data) {
      if (!familyGameMode) return;
      const finished = data.status === 'graded';
      if (finished && $('questionVersion').value) { gameCompletedChoices.add($('questionVersion').value); saveGameRound(); }
      gameItemStatus = finished ? 'graded' : 'grading_pending'; updateGameAnswerControls();
      $('gameFeedback').hidden = !finished;
      if (!finished) return;
      $('gameFeedback').dataset.outcome = data.outcome || 'undetermined';
      $('feedbackTitle').textContent = {correct:'答对了！又前进了一步 ✦', incorrect:'这道题，值得再研究一下', partial:'已经找到一部分思路了', undetermined:'这题请家长一起看看'}[data.outcome] || '作答已保存';
      $('feedbackText').textContent = data.outcome === 'correct' ? '这道题已完成，记住刚才的解题思路。' : data.outcome === 'incorrect' ? '先别着急。可以把题目记进错题收藏，再和家长一起找出原因。' : '你的作答已经保存，可以请家长一起核对。';
      $('solutionDetails').hidden = !gameCatalog.find((c) => c.question_version_id === $('questionVersion').value)?.practice;
      $('solutionText').textContent = data.feedback || '';
      if (!gameUpdatedAttempts.has(data.id)) {
        gameUpdatedAttempts.add(data.id); $('loadToday').onclick();
      }
    }
    if (familyGameMode) {
      $('practicePicker').append($('practiceChoices')); $('familyReview').append($('today'));
      document.querySelectorAll('[data-game-view]').forEach((link) => { link.onclick = (event) => { event.preventDefault(); setGameView(link.dataset.gameView); if (link.dataset.gameView === 'home' && $('learner').value) $('loadToday').onclick(); }; });
      $('quickNotebook').onclick = () => setGameView('notebook');
      $('changeChapter').onclick = () => { setGameView('home'); $('textbookMap').scrollIntoView({block:'start'}); $('loadToday').onclick(); };
      $('startAdventure').onclick = () => {
        if ($('testItem').value && ['reserved','presented','grading_pending'].includes(gameItemStatus)) { setGameView('practice'); return; }
        if (gameNextChoice()) launchGameChoice(gameNextChoice()); else restartGameRound();
      };
      $('practiceStart').onclick = $('startAdventure').onclick;
      $('scopeChallenge').onclick = $('startAdventure').onclick;
      $('nextChallenge').onclick = continueGameRound;
      $('restartRound').onclick = restartGameRound;
      for (const id of ['homeDifficulty','practiceDifficulty']) $(id).onchange = () => { gameDifficulty = $(id).value; saveGameRound(); updateChapterControls(); };
      $('answer').placeholder = '在这里写下你的答案';
      $('answer').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.isComposing && !$('submitAnswer').disabled) { event.preventDefault(); $('submitAnswer').onclick(); } });
      $('saveManualMistake').textContent = '加入我的错题收藏 ＋';
      $('requestHint').textContent = '需要一点提示'; $('cancelTest').textContent = '先跳过这题';
      $('requestReview').textContent = '请家长复核';
      const answerLabel = $('answer').parentElement;
      answerLabel.firstChild.textContent = '我的答案 ';
      resetGameWorkspace();
    }
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
      const content = item.content || {};
      if (content.extraction_format && typeof content.document_text === 'string') {
        const caption = document.createElement('figcaption'); caption.textContent = `原文结构化提取 · ${content.extraction_format.toUpperCase()} · 第 ${Number(item.page_index) + 1} 部分`;
        const text = document.createElement('pre'); text.textContent = content.document_text || '文档未提取到可显示文本。';
        target.replaceChildren(caption, text);
        return;
      }
      try {
        const blob = await fetchScoped('/api/v1/source-pages/' + encodeURIComponent(pageId) + '/content', {}, true);
        const url = URL.createObjectURL(blob);
        if (generation !== sourceRenderGeneration) { URL.revokeObjectURL(url); return; }
        sourceObjectUrls.push(url);
        const image = document.createElement('img'); image.src = url; image.alt = `来源原卷，第 ${Number(item.page_index) + 1} 页`;
        const caption = document.createElement('figcaption'); caption.textContent = `原卷第 ${Number(item.page_index) + 1} 页 · ${item.locator || '未分题'} · ${pageId}`;
        target.replaceChildren(image, caption);
      } catch (error) { if (error instanceof StaleContextError) return; target.textContent = error.message; }
    }
    function saveTestState(extra = {}) {
      const state = Object.assign({
        account: savedTest.account || $('account').value.trim(), learner: savedTest.learner || $('learner').value.trim(),
        questionVersionId: $('questionVersion').value.trim(), cardId: $('card').value.trim(),
        sessionId: $('session').value.trim(), testItemId: $('testItem').value.trim(), attemptId: $('attempt').value.trim()
      }, extra);
      workspaceStorage.setItem(testStateKey(), JSON.stringify(state));
      savedTest = state;
    }
    function renderTest(data) {
      const item = (data.items || [])[0] || data;
      if (item.prompt !== undefined) $('testPrompt').textContent = item.prompt || '题面为空。';
      if (familyGameMode) { $('solutionDetails').open = false; $('solutionDetails').hidden = true; renderQuestionMeta(); }
      if (item.test_item_id) $('testItem').value = item.test_item_id;
      if (data.session_id) $('session').value = data.session_id;
      if (familyGameMode) { gameItemStatus = item.status || 'presented'; $('gameFeedback').hidden = true; $('gameHint').hidden = true; $('answer').value = ''; updateGameAnswerControls(); }
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
        if (familyGameMode) {
          gameItemStatus = item.status; renderQuestionMeta(); updateGameAnswerControls();
          testStatus(item.status === 'cancelled' ? '这道挑战已跳过，可以再选一题。' : item.attempt_id ? '正在找回你的判分结果…' : '题目已准备好，按自己的节奏来。');
        } else testStatus(`会话 ${data.session.status} · 题项 ${item.status} · 辅助 ${item.assistance || 'none'}${item.attempt_status ? ` · 判分 ${item.attempt_status}` : ''}`);
      }
      saveTestState(); show(data);
      if ($('attempt').value) await refreshAttempt();
      return data;
    }
    async function refreshAttempt(retry = 0) {
      const epoch = contextEpoch;
      const attemptId = $('attempt').value.trim();
      if (!attemptId) throw new Error('提交后才有 Attempt ID');
      const data = await call('/api/v1/attempts/' + encodeURIComponent(attemptId));
      const outcome = data.outcome ? ` · ${{correct:'答对了',incorrect:'再想一想',needs_review:'请家长复核'}[data.outcome] || data.outcome}` : '';
      testStatus(`${data.status === 'graded' ? '已完成' : '正在判分'}${outcome}`);
      saveTestState(); show(data);
      if (familyGameMode) renderGameFeedback(data);
      if (data.status === 'grading_pending' && retry < 4) {
        await new Promise((resolve) => setTimeout(resolve, 700));
        if (epoch !== contextEpoch) throw new StaleContextError();
        return refreshAttempt(retry + 1);
      }
      if (familyGameMode && data.status === 'grading_pending' && retry === 4) {
        $('gameFeedback').hidden = false; $('gameFeedback').dataset.outcome = 'pending';
        $('feedbackTitle').textContent = '还在核对答案，请稍等'; $('feedbackText').textContent = '你的作答已保存。点击下方按钮查看最新结果。';
        $('nextChallenge').textContent = '查看判分结果'; $('nextChallenge').disabled = false; $('nextChallenge').onclick = () => $('refreshAttempt').onclick();
      } else if (familyGameMode && data.status === 'graded') {
        updateChapterControls();
      }
      return data;
    }
    $('loadHealth').onclick = async () => { try { show(await call('/health')); } catch (e) { if (e instanceof StaleContextError) return; show(e.message); } };
    $('loadLearners').onclick = async () => { try { show(await call('/api/v1/learners')); } catch (e) { if (e instanceof StaleContextError) return; show(e.message); } };
    if (!browserSessionMode) {
      const changed = () => { clearWorkspace(); restoreImportState(); restoreCurrentTest(); document.querySelector('main').inert = false; };
      $('account').addEventListener('change', changed); $('learner').addEventListener('change', changed);
    }
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
      } catch (e) { if (e instanceof StaleContextError) return; renderDocuments(); setStatus(`上传中断，已成功的文件仍保留在列表。${e.message}`); }
    };
    $('makeBatch').onclick = async () => {
      const selected = uploadedDocuments.filter((doc) => doc.kind !== 'answer_key' && doc.selected !== false).map((doc) => doc.document_id);
      if (!selected.length) { setStatus('请至少选择一份试卷或作业资料'); return; }
      if (selected.length > 20) { setStatus('单批最多选择 20 份资料'); return; }
      const body = {document_ids: selected}; if ($('answerDocument').value) body.answer_document_id = $('answerDocument').value;
      try { const data = await call('/api/v1/import-batches', {method: 'POST', headers: {'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID()}, body: JSON.stringify(body)}); $('batch').value = data.batch_id; saveImportState(); setStatus(data); show(data); }
      catch (e) { if (e instanceof StaleContextError) return; setStatus(e.message); }
    };
    $('analyze').onclick = async () => {
      try { const data = await call('/api/v1/import-batches/' + encodeURIComponent($('batch').value) + '/analysis', {method: 'POST', headers: {'Idempotency-Key': 'ui-analysis-' + $('batch').value}}); setStatus(data); show(data); }
      catch (e) { if (e instanceof StaleContextError) return; setStatus(e.message); }
    };
    $('cancelBatch').onclick = async () => {
      try { const data = await call('/api/v1/import-batches/' + encodeURIComponent($('batch').value) + '/cancel', {method: 'POST'}); setStatus(data); show(data); }
      catch (e) { if (e instanceof StaleContextError) return; setStatus(e.message); }
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
            statusLine.textContent = content.extraction_format
              ? `已从 ${content.extraction_format.toUpperCase()} 提取文档文本；请在下方人工整理具体错题题干、学生作答和知识目标，再填写错误判定与复核证据。`
              : `题干：${content.question_text || content.question || content.text_status || '未提取'}；学生作答：${item.raw_answer || content.student_answer || content.student_input_status || '未提取'}；教师批改：${content.teacher_mark || '未提供'}`;
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
              const epoch = contextEpoch;
              try {
                let parsedEvidence = {};
                const rawEvidence = evidence.value.trim();
                if (rawEvidence) { try { parsedEvidence = JSON.parse(rawEvidence); } catch (_) { parsedEvidence = {note: rawEvidence}; } }
                const result = await call('/api/v1/import-items/' + encodeURIComponent(item.id), {
                  method: 'PATCH', headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({expected_revision: Number(checkbox.dataset.revision), raw_answer: rawAnswer.value, content: {...content, question_text: questionText.value, objective_id: objective.value.trim() || null}, verdict: verdict.value, evidence: parsedEvidence, objective_id: objective.value.trim() || null})
                });
                await $('refreshItems').onclick(); if (epoch === contextEpoch) show(result);
              } catch (e) { if (e instanceof StaleContextError) return; show(e.message); }
            };
            fields.append(save); layout.append(fields); card.append(layout); container.append(card);
            renderSourcePreview(item, preview);
          });
        }
        show(data);
      } catch (e) { if (e instanceof StaleContextError) return;
        if (generation !== importRefreshGeneration || account !== $('account').value.trim() || learner !== $('learner').value.trim()) return;
        $('items').textContent = e.message; $('pageSummary').textContent = e.message;
      }
    };
    $('loadMistakes').onclick = async () => {
      try { const data = await call('/api/v1/mistakes'); renderMistakes(data); show(data); }
      catch (e) { if (e instanceof StaleContextError) return; $('mistakes').textContent = e.message; }
    };
    function matchManualObjective(question) {
      const text = question.normalize('NFKC').replace(/[−–]/g, '-').replace(/[×✕]/g, '*')
        .replace(/乘以|乘/g, '*').replace(/加上|加/g, '+').replace(/减去|减/g, '-').replace(/\\s/g, '')
        .replace(/([0-9])x(?=[0-9])/gi, '$1*');
      const expressions = (text.match(/[-A-Za-z0-9()+*\\/.^%÷]+/g) || [])
        .filter((part) => /[+*\\/÷^%]|[0-9)]-/.test(part));
      if (expressions.length !== 1) return null;
      const match = expressions[0].match(/^(\\(-?[0-9]+\\)|-?[0-9]+)([+*-])(\\(-?[0-9]+\\)|-?[0-9]+)$/);
      if (!match) return null;
      const left = Number(match[1].replace(/[()]/g, '')), right = Number(match[3].replace(/[()]/g, ''));
      if (!Number.isSafeInteger(left) || !Number.isSafeInteger(right)) return null;
      let accepts;
      if (match[2] === '-' && right < 0) accepts = (item) => item.title.includes('减去负数');
      else if (match[2] === '*' && left >= 1 && left <= 9 && right >= 1 && right <= 9) accepts = (item) => item.title === '表内乘法';
      else if (['+', '-'].includes(match[2]) && left >= 0 && left <= 100 && right >= 0 && right <= 100) {
        const result = match[2] === '+' ? left + right : left - right;
        if (result < 0 || result > 100) return null;
        accepts = (item) => item.title === '100以内加减法';
      } else return null;
      const matches = manualObjectives.filter(accepts);
      return matches.length === 1 ? matches[0] : null;
    }
    function updateManualObjective() {
      if (manualObjectiveChosen) return;
      const question = $('manualQuestion').value.trim();
      const matched = question ? matchManualObjective(question) : null;
      $('manualObjective').value = matched?.id || '';
      $('manualObjectiveStatus').textContent = matched ? '已自动匹配：' + matched.title + '，可手动修改。'
        : question ? '暂未匹配，可手动选择或先保存。' : '';
    }
    $('manualQuestion').addEventListener('input', updateManualObjective);
    $('manualObjective').addEventListener('change', () => {
      manualObjectiveChosen = true;
      $('manualObjectiveStatus').textContent = $('manualObjective').value ? '已采用你选择的知识目标。' : '已选择暂不分类。';
    });
    $('saveManualMistake').onclick = async () => {
      const question = $('manualQuestion').value.trim();
      if (!question) { $('manualStatus').textContent = '请先填写题干'; return; }
      const body = {
        question_text: question,
        student_answer: $('manualStudentAnswer').value.trim() || null,
        correct_answer: $('manualCorrectAnswer').value.trim() || null,
        objective_id: $('manualObjective').value.trim() || null,
        note: $('manualNote').value.trim() || null
      };
      try {
        const result = await call('/api/v1/mistakes/manual', {method: 'POST', headers: {'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID()}, body: JSON.stringify(body)});
        $('mistake').value = result.mistake_id;
        ['manualQuestion', 'manualStudentAnswer', 'manualCorrectAnswer', 'manualObjective', 'manualNote'].forEach((id) => { $(id).value = ''; });
        manualObjectiveChosen = false; updateManualObjective();
        $('uploadStatus').textContent = result.review_card_id ? '已加入错题本并创建复习卡。' : '已加入错题本；选择知识目标后可创建复习卡。';
        $('manualStatus').textContent = '已保存到当前学习档案的错题本。';
        show(result);
        await $('loadMistakes').onclick();
      } catch (e) { if (e instanceof StaleContextError) return; $('manualStatus').textContent = e.message; }
    };
    function renderMistakes(data) {
      const container = $('mistakes'); container.replaceChildren();
      const items = familyGameMode ? (data.items || []).filter((item) => item.status !== 'deleted') : (data.items || []);
      if (familyGameMode) { gameMistakes = items.length; $('heroMistakes').textContent = String(gameMistakes); }
      if (!items.length) { container.textContent = familyGameMode ? '收藏夹还是空的。遇到想弄懂的题，就把它留下来吧。' : '错题本暂无记录。'; return; }
      items.forEach((item) => {
        const row = document.createElement('article'); row.className = 'review-card';
        const content = item.content || {};
        const title = document.createElement('p'); title.textContent = content.question_text || content.question || '待整理题干';
        const button = document.createElement('button'); button.className = 'secondary'; button.textContent = '查看错题详情';
        const details = document.createElement('div'); details.hidden = true;
        if (familyGameMode && item.objective_title) { const goal = document.createElement('p'); goal.textContent = '知识目标：' + item.objective_title; details.append(goal); }
        for (const [key, label] of [['student_answer','当时的答案'],['correct_answer','参考答案'],['note','备注']]) {
          if (content[key]) { const line = document.createElement('p'); line.textContent = label + '：' + content[key]; details.append(line); }
        }
        button.onclick = () => { $('mistake').value = item.id; details.hidden = !details.hidden; button.textContent = details.hidden ? '查看错题详情' : '收起详情'; };
        row.append(title, button, details); container.append(row);
      });
    }
    function renderPracticeChoices(items, objectives) {
      const practice = $('practiceChoices'); practice.replaceChildren();
      if (familyGameMode) {
        $('practicePicker').hidden = !items.length;
        $('practicePickerSummary').textContent = '自己挑一道题 · ' + items.length + ' 道';
      }
      if (!items.length) practice.textContent = '所选范围暂未配题，可以先阅读教材。';
      const counts = {};
      items.forEach((choice, choiceIndex) => {
        const title = objectives.find((item) => item.id === choice.objective_id)?.title || '数学练习';
        counts[choice.objective_id] = (counts[choice.objective_id] || 0) + 1;
        const button = document.createElement('button'); button.className = 'secondary';
        if (familyGameMode) {
          button.className = 'challenge-card';
          const number = document.createElement('span'); number.className = 'challenge-number'; number.textContent = String(choiceIndex + 1);
          const heading = document.createElement('strong'); heading.textContent = choice.practice ? difficultyNames[choice.practice.difficulty] + ' · ' + choice.practice.title : title.replace('理解减去负数的运算方向', '减去负数的秘密');
          if (gameCompletedChoices.has(choice.question_version_id)) heading.textContent += ' · 本轮已做';
          const arrow = document.createElement('span'); arrow.className = 'challenge-arrow'; arrow.textContent = '↗'; arrow.setAttribute('aria-hidden','true');
          button.append(number, heading, arrow); button.onclick = () => launchGameChoice(choice);
        } else {
          button.textContent = title + ' · 第' + counts[choice.objective_id] + '题';
          button.onclick = () => { $('questionVersion').value = choice.question_version_id; $('card').value = ''; $('startTest').onclick(); $('testSection').scrollIntoView(); };
        }
        practice.append(button);
      });
    }
    function renderReviewTasks(items, choices) {
      const container = $('today'); container.replaceChildren();
      if (familyGameMode) $('familyReview').hidden = !items.length;
      if (!items.length) container.textContent = familyGameMode ? '所选范围暂无到期复习。' : '今天暂无到期复习；可选择已审核题目进行练习。';
      items.forEach((task) => {
        const row = document.createElement('article'); row.className = 'review-card';
        const title = document.createElement('h3'); title.textContent = task.title || '到期复习'; row.append(title);
        const available = choices.filter((choice) => !task.objective_id || choice.objective_id === task.objective_id);
        if (!available.length) row.append(document.createTextNode('此目标尚无可投放的审核题目。'));
        available.forEach((choice, index) => {
          const button = document.createElement('button'); button.className = 'secondary'; button.textContent = `开始${task.id ? '复习' : '测验'} ${index + 1}`;
          button.onclick = () => {
            if (familyGameMode) { launchGameChoice(choice, task.id || ''); return; }
            $('questionVersion').value = choice.question_version_id; $('card').value = task.id || ''; $('startTest').onclick(); $('testSection').scrollIntoView();
          };
          row.append(button);
        }); container.append(row);
      });
    }
    function releaseTextbookPages() {
      textbookGeneration += 1;
      textbookObjectUrls.forEach((url) => URL.revokeObjectURL(url)); textbookObjectUrls = [];
      if ($('textbookZoom').open) $('textbookZoom').close();
      $('textbookResults').replaceChildren();
      $('textbookResultTools').hidden = true; $('textbookResultCount').textContent = '';
      $('textbookPager').hidden = true;
    }
    $('textbookExpandAll').onclick = () => { $('textbookResults').querySelectorAll('details').forEach((card) => { card.open = true; }); };
    $('textbookCollapseAll').onclick = () => { $('textbookResults').querySelectorAll('details').forEach((card) => { card.open = false; }); $('textbookResultTools').scrollIntoView({block:'nearest'}); };
    async function renderTextbookPage(item, target, epoch, generation) {
      const current = () => epoch === contextEpoch && generation === textbookGeneration;
      if (!current()) return;
      target.textContent = '正在加载教材原页…';
      try {
        if (!new RegExp('^/api/v1/textbooks/(chinese|math|english|ethics|history|geography|physics|chemistry|biology)-g[27]-(upper|lower)/pages/[1-9][0-9]{0,2}/image$').test(item.page_image_path)) throw new Error('invalid page');
        const blob = await fetchScoped(item.page_image_path, {}, true);
        if (!current()) return;
        if (blob.type !== 'image/png') throw new Error('invalid image');
        const url = URL.createObjectURL(blob); textbookObjectUrls.push(url);
        const image = document.createElement('img'); image.src = url;
        image.alt = item.book_title + '第 ' + item.printed_page + ' 页原图，含完整公式与图形';
        image.className = 'textbook-page-image'; image.tabIndex = 0; image.setAttribute('role', 'button');
        image.setAttribute('aria-label', '点击放大第 ' + item.printed_page + ' 页');
        image.onclick = () => openTextbookZoom(url, item);
        image.onkeydown = (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openTextbookZoom(url, item); } };
        await image.decode();
        if (!current()) return;
        const link = document.createElement('a'); link.textContent = '放大查看第 ' + item.printed_page + ' 页原图 ↗';
        link.href = url; link.className = 'textbook-page-link'; link.onclick = (event) => { event.preventDefault(); openTextbookZoom(url, item); };
        const close = document.createElement('button'); close.type = 'button'; close.className = 'secondary textbook-close-page'; close.textContent = '收起本页';
        close.onclick = () => { const card = target.closest('details'); card.open = false; card.querySelector('summary').focus({preventScroll:true}); card.querySelector('summary').scrollIntoView({block:'nearest'}); };
        const actions = document.createElement('div'); actions.className = 'textbook-page-actions'; actions.append(link, close);
        target.replaceChildren(image, actions);
      } catch (error) {
        if (error instanceof StaleContextError || !current()) return;
        const message = document.createElement('p'); message.textContent = '教材原页暂未加载成功，请重试。';
        const retry = document.createElement('button'); retry.className = 'secondary'; retry.textContent = '重新加载原页';
        retry.onclick = () => renderTextbookPage(item, target, epoch, generation);
        target.replaceChildren(message, retry);
      }
    }
    let readerOffset = 0, readerHits = null, readerHitIndex = 0, zoomScale = 100;
    function openTextbookZoom(url, item) {
      $('textbookZoomImage').src = url; $('textbookZoomImage').alt = item.content_title;
      $('textbookZoomTitle').textContent = '第 ' + item.printed_page + ' 页 · ' + item.content_title;
      zoomScale = 100; setTextbookZoom(); $('textbookZoom').showModal();
      $('textbookZoomViewport').scrollTo(0,0); $('textbookZoomClose').focus();
    }
    function setTextbookZoom() { $('textbookZoomImage').style.width = zoomScale + '%'; $('textbookZoomLevel').textContent = zoomScale + '%'; }
    $('textbookZoomIn').onclick = () => { zoomScale = Math.min(300, zoomScale + 25); setTextbookZoom(); };
    $('textbookZoomOut').onclick = () => { zoomScale = Math.max(50, zoomScale - 25); setTextbookZoom(); };
    $('textbookZoomReset').onclick = () => { zoomScale = 100; setTextbookZoom(); };
    $('textbookZoomClose').onclick = () => $('textbookZoom').close();
    $('textbookZoom').addEventListener('close', () => $('textbookZoomImage').removeAttribute('src'));
    function syncScopeSelectors() {
      const book = selectedBook();
      $('textbookSubject').value = book?.subject || 'math';
      $('textbookBook').replaceChildren();
      textbookBooks.filter((b) => b.subject === $('textbookSubject').value).forEach((b) => $('textbookBook').add(new Option(b.title, b.id)));
      $('textbookBook').value = gameBook;
      $('textbookChapter').replaceChildren(new Option('整本书（不限章节）', ''));
      (book?.chapters || []).forEach((chapter) => $('textbookChapter').add(new Option(chapter.title, chapter.id)));
      $('textbookChapter').value = gameChapter;
      const subject = textbookSubjects.find((item) => item.id === book?.subject);
      $('textbookEdition').textContent = book ? book.edition + (subject?.notice ? ' · ' + subject.notice : '') : '暂无教材';
      $('textbookSearch').disabled = !book;
      $('studySupportOpen').disabled = !book;
      $('textbookSearch').textContent = gameChapter ? '阅读本章' : '阅读整本书';
      $('textbookQuery').placeholder = {math:'例如：有理数减法',chinese:'例如：课文、古诗',english:'例如：family',geography:'例如：地图、气候'}[book?.subject] || '输入想找的内容';
      $('textbookStatus').textContent = '';
      syncStudySupport();
    }
    function renderReaderToc() {
      const target = $('textbookToc'); target.replaceChildren();
      const book = selectedBook();
      (book ? [{id:'',title:'整本书 · 从头阅读'}, ...book.chapters] : []).forEach((chapter) => {
        const button = document.createElement('button'); button.type = 'button'; button.dataset.chapter = chapter.id;
        button.textContent = chapter.title + (chapter.printed_page ? ' · 第 ' + chapter.printed_page + ' 页' : '');
        button.setAttribute('aria-current', String(chapter.id === gameChapter));
        button.onclick = () => { selectLearningScope(gameBook, chapter.id, true); if (innerWidth <= 760) $('textbookContents').open = false; };
        target.append(button);
      });
    }
    async function loadTextbooks() {
      const epoch = contextEpoch, generation = ++textbookGeneration;
      try {
        const data = await call('/api/v1/textbooks');
        if (epoch !== contextEpoch || generation !== textbookGeneration) return;
        textbookBooks = data.items || []; textbookSubjects = data.subjects || [];
        $('textbookSubject').replaceChildren();
        textbookSubjects.forEach((subject) => $('textbookSubject').add(new Option(subject.title, subject.id)));
        $('textbookSubjectNote').textContent = data.grade_notice || '';
        const savedScope = parseSaved(chapterStateKey());
        const current = gameCatalog.find((choice) => choice.question_version_id === $('questionVersion').value);
        gameBook = savedScope.bookId || current?.textbook_scope?.book_id || textbookBooks.find((b) => b.subject === 'math')?.id || textbookBooks[0]?.id || '';
        if (!selectedBook()) gameBook = textbookBooks[0]?.id || '';
        gameChapter = savedScope.bookId ? (savedScope.chapterId || '') : (current?.textbook_scope?.chapter_id || '');
        if (!selectedBook()?.chapters.some((c) => c.id === gameChapter)) gameChapter = '';
        if (current?.textbook_scope && (current.textbook_scope.book_id !== gameBook || (gameChapter && current.textbook_scope.chapter_id !== gameChapter))) {
          gameBook = current.textbook_scope.book_id; gameChapter = current.textbook_scope.chapter_id;
        }
        syncScopeSelectors(); renderGameChapters();
        $('textbookContents').open = innerWidth > 760;
      } catch (error) { if (!(error instanceof StaleContextError) && epoch === contextEpoch) $('textbookStatus').textContent = '课本暂时没有连接上，请稍后刷新。'; }
    }
    $('textbookSubject').onchange = () => { const book = textbookBooks.find((b) => b.subject === $('textbookSubject').value); syncScopeSelectors(); if (book) selectLearningScope(book.id); };
    $('textbookBook').onchange = () => { const id = $('textbookBook').value; syncScopeSelectors(); selectLearningScope(id); };
    $('textbookChapter').onchange = () => { const id = $('textbookChapter').value; syncScopeSelectors(); selectLearningScope(gameBook, id); };
    $('textbookSearch').onclick = () => { $('textbookQuery').value = ''; loadTextbookResults(); };
    $('textbookFind').onclick = () => loadTextbookResults();
    $('textbookQuery').onkeydown = (event) => { if (event.key === 'Enter' && !event.isComposing) loadTextbookResults(); };
    $('textbookQuery').oninput = () => {
      releaseTextbookPages(); readerHits = null;
      $('textbookPrev').disabled = true; $('textbookNext').disabled = true;
      $('textbookStatus').textContent = '点击“查找”，在所选范围内寻找内容。';
    };
    $('textbookBrowse').onclick = () => { $('textbookQuery').value = ''; loadTextbookResults(); };
    function readerRange() { const book = selectedBook(); const chapter = book?.chapters.find((c) => c.id === gameChapter); return {start:chapter?.printed_page || book?.chapters[0].printed_page || 1, end:chapter ? chapter.printed_page + chapter.page_end - chapter.page_start : book ? book.chapters.at(-1).printed_page + book.chapters.at(-1).page_end - book.chapters.at(-1).page_start : 1}; }
    $('textbookJump').onclick = () => {
      const value = Number($('textbookPageInput').value), range = readerRange();
      if (!Number.isInteger(value) || value < range.start || value > range.end) { $('textbookStatus').textContent = `请输入 ${range.start}～${range.end} 之间的书内页码。`; return; }
      $('textbookQuery').value = ''; loadTextbookResults(value - range.start);
    };
    $('textbookPageInput').onkeydown = (event) => { if (event.key === 'Enter') $('textbookJump').onclick(); };
    function showReaderPage(item, epoch, generation) {
      const card = document.createElement('details'); card.className = 'review-card textbook-page'; card.dataset.page = item.printed_page; card.open = true;
      const summary = document.createElement('summary'); summary.className = 'textbook-page-summary';
      const title = document.createElement('strong'); title.className = 'textbook-page-title'; title.textContent = '第 ' + item.printed_page + ' 页 · ' + (item.content_title || '本页教材内容');
      summary.append(title); const preview = document.createElement('div'); preview.className = 'textbook-page-preview';
      card.append(summary, preview); $('textbookResults').replaceChildren(card); $('textbookResults').scrollTop = 0;
      $('textbookResultTools').hidden = false;
      $('textbookPageInput').value = item.printed_page;
      $('textbookPageRange').textContent = '第 ' + item.printed_page + ' 页';
      renderTextbookPage(item, preview, epoch, generation);
    }
    async function loadTextbookResults(pageOffset = 0, hitIndex = null) {
      if (!selectedBook()) return;
      releaseTextbookPages(); $('textbookReader').open = true;
      const epoch = contextEpoch, generation = textbookGeneration;
      $('textbookStatus').textContent = '正在翻课本…';
      $('textbookPrev').disabled = true; $('textbookNext').disabled = true;
      $('textbookPageInput').disabled = true; $('textbookJump').disabled = true;
      const range = readerRange(); $('textbookPageInput').min = range.start; $('textbookPageInput').max = range.end;
      try {
        let result;
        if (hitIndex !== null && readerHits) result = readerHits;
        else {
          result = await call('/api/v1/textbooks/search', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({book_id:gameBook, chapter_id:gameChapter, query:$('textbookQuery').value, page_offset:pageOffset})});
        }
        if (epoch !== contextEpoch || generation !== textbookGeneration) return;
        const items = (result.items || []).slice().sort((a,b) => a.printed_page - b.printed_page);
        const browse = result.mode === 'browse'; readerOffset = pageOffset; readerHitIndex = hitIndex ?? 0; readerHits = browse ? null : result;
        $('textbookStatus').textContent = items.length ? (browse ? '按页阅读 · 点击原图可放大。' : '匹配页 · 点击原图可放大。') + '仅供阅读，不作为标准答案。' : '所选范围暂未找到相关内容，可以换个关键词。';
        $('textbookResultCount').textContent = browse ? '当前范围共 ' + result.total_pages + ' 页' : `找到 ${items.length} 个相关页 · ${readerHitIndex + 1} / ${items.length}`;
        if (!items.length) return;
        showReaderPage(items[browse ? 0 : readerHitIndex], epoch, generation);
        $('textbookPrev').textContent = browse ? '上一页' : '上个匹配'; $('textbookNext').textContent = browse ? '下一页' : '下个匹配';
        $('textbookPrev').disabled = browse ? pageOffset <= 0 : readerHitIndex <= 0;
        $('textbookNext').disabled = browse ? pageOffset + 1 >= result.total_pages : readerHitIndex + 1 >= items.length;
        $('textbookPrev').onclick = () => loadTextbookResults(browse ? pageOffset - 1 : 0, browse ? null : readerHitIndex - 1);
        $('textbookNext').onclick = () => loadTextbookResults(browse ? pageOffset + 1 : 0, browse ? null : readerHitIndex + 1);
      } catch (error) { if (!(error instanceof StaleContextError) && epoch === contextEpoch && generation === textbookGeneration) $('textbookStatus').textContent = '课本暂时没有连接上，请稍后再试。'; }
      finally { if (epoch === contextEpoch && generation === textbookGeneration) { $('textbookPageInput').disabled = false; $('textbookJump').disabled = false; } }
    }
    $('loadToday').onclick = async () => {
      const generation = ++gameRefreshGeneration, epoch = contextEpoch;
      if (familyGameMode) { gameLoadingChoices = true; updateChapterControls(); }
      try {
        const [tasks, progress, choices] = await Promise.all([call('/api/v1/review-tasks'), call('/api/v1/progress'), call('/api/v1/question-choices')]);
        if (epoch !== contextEpoch || generation !== gameRefreshGeneration) return;
        const objectives = choices.objectives || [];
        manualObjectives = objectives;
        const selectedObjective = $('manualObjective').value;
        $('manualObjective').replaceChildren(new Option('暂不分类', ''));
        objectives.forEach((item) => $('manualObjective').add(new Option(item.title, item.id)));
        if (objectives.some((item) => item.id === selectedObjective)) $('manualObjective').value = selectedObjective;
        else if (selectedObjective) manualObjectiveChosen = false;
        updateManualObjective();
        $('progress').textContent = `已判分 ${progress.attempts.graded || 0} 次 · 独立作答 ${progress.attempts.independent || 0} 次`;
        if (!familyGameMode) { renderPracticeChoices(choices.items, objectives); renderReviewTasks(tasks.items, choices.items); }
        if (familyGameMode) {
          gameCatalog = choices.items; gameObjectives = objectives; gameTasks = tasks.items; gameGuidance = choices.practice_guidance || {}; renderQuestionMeta();

          gameGraded = progress.attempts.graded || 0;
          $('heroGraded').textContent = String(gameGraded); $('heroIndependent').textContent = String(progress.attempts.independent || 0);
          if (textbookBooks.length) renderGameChapters(); else await loadTextbooks();
        }
      } catch (e) { if (!(e instanceof StaleContextError)) { $('today').textContent = '暂未加载学习进度，请稍后返回首页重试。'; if (familyGameMode) $('familyReview').hidden = false; } }
      finally { if (familyGameMode && epoch === contextEpoch && generation === gameRefreshGeneration) { gameLoadingChoices = false; updateChapterControls(); } }
    };
    $('loadReview').onclick = async () => {
      try { const data = await call('/api/v1/review-tasks'); $('mistakes').textContent = JSON.stringify(data, null, 2); show(data); }
      catch (e) { if (e instanceof StaleContextError) return; $('mistakes').textContent = e.message; }
    };
    $('diagnose').onclick = async () => {
      try { const data = await call('/api/v1/mistakes/' + encodeURIComponent($('mistake').value) + '/diagnoses', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})}); show(data); }
      catch (e) { if (e instanceof StaleContextError) return; show(e.message); }
    };
    $('startTest').onclick = async () => {
      if (familyGameMode && gameStarting) return;
      const epoch = contextEpoch;
      if (familyGameMode) { gameStarting = true; updateChapterControls(); $('nextChallenge').disabled = true; }
      try {
        const card = $('card').value.trim(); const body = {question_version_id: $('questionVersion').value, mode: 'independent'};
        if (card) body.card_id = card;
        if (familyGameMode) { body.textbook_book_id = gameBook; body.textbook_chapter_id = gameChapter || null; }
        const data = await call('/api/v1/test-sessions', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
        $('attempt').value = ''; renderTest(data); testStatus(familyGameMode ? '慢慢想，准备好就写下答案。' : '题面已发放，答案未发送到客户端。');
        if (familyGameMode) { setGameView('practice'); $('answer').focus({preventScroll:true}); }
      } catch (e) { if (e instanceof StaleContextError) return; testStatus(e.message); }
      finally {
        if (familyGameMode && epoch === contextEpoch) { gameStarting = false; updateChapterControls(); }
      }
    };
    $('restoreTest').onclick = async () => {
      try {
        const account = $('account').value.trim(), learner = $('learner').value.trim();
        if (savedTest.account && (savedTest.account !== account || savedTest.learner !== learner)) throw new Error('保存的测验属于其他学习者，请先输入匹配身份');
        if (!savedTest.sessionId) throw new Error('没有可恢复的测验会话');
        $('session').value = savedTest.sessionId; $('testItem').value = savedTest.testItemId || '';
        $('attempt').value = savedTest.attemptId || '';
        await refreshTestState();
      } catch (e) { if (e instanceof StaleContextError) return; testStatus(e.message); }
    };
    $('refreshTest').onclick = async () => { try { await refreshTestState(); } catch (e) { if (e instanceof StaleContextError) return; testStatus(e.message); } };
    $('requestHint').onclick = async () => {
      try {
        const context = ensureTestContext();
        const data = await call('/api/v1/test-items/' + encodeURIComponent(context.item) + '/hints', {method: 'POST'});
        testStatus('已记录提示暴露，当前作答不计入独立证据。'); show(data); await refreshTestState();
        if (familyGameMode) { $('gameHint').textContent = data.hint + '（本题将记为提示后练习）'; $('gameHint').hidden = false; }
      } catch (e) { if (e instanceof StaleContextError) return; testStatus(e.message); }
    };
    $('cancelTest').onclick = async () => {
      try {
        const session = $('session').value.trim(); if (!session) throw new Error('请先开始或恢复测验');
        const data = await call('/api/v1/test-sessions/' + encodeURIComponent(session) + '/cancel', {method: 'POST'});
        testStatus('测验已取消，未提交题项不会产生判分。'); show(data); await refreshTestState();
        if (familyGameMode) { setGameView('home'); $('loadToday').onclick(); }
      } catch (e) { if (e instanceof StaleContextError) return; testStatus(e.message); }
    };
    $('submitAnswer').onclick = async () => {
      if (familyGameMode && gameSubmitting) return;
      const epoch = contextEpoch;
      try {
        const rawAnswer = $('answer').value;
        const item = $('testItem').value.trim(); if (!item || !rawAnswer) throw new Error('请填写作答项和原始作答');
        if (familyGameMode) { gameSubmitting = true; updateGameAnswerControls(); }
        const challenge = await call('/api/v1/test-items/' + encodeURIComponent(item) + '/submission-challenges', {method: 'POST'});
        const data = await call('/api/v1/test-items/' + encodeURIComponent(item) + '/answers', {method: 'POST', headers: {'Content-Type': 'application/json', 'Idempotency-Key': 'ui-answer-' + crypto.randomUUID()}, body: JSON.stringify({challenge_id: challenge.challenge_id, nonce: challenge.nonce, raw_answer: rawAnswer})});
        $('answer').value = ''; $('attempt').value = data.attempt_id || ''; saveTestState(); testStatus(familyGameMode ? '收到你的答案啦，正在核对…' : '已提交，等待服务端判分；202 不是最终成绩。'); show(data);
        if (familyGameMode) { gameItemStatus = 'grading_pending'; updateGameAnswerControls(); }
        if ($('attempt').value) await refreshAttempt();
      } catch (e) { if (e instanceof StaleContextError) return; testStatus(e.message); }
      finally { if (familyGameMode && epoch === contextEpoch) { gameSubmitting = false; updateGameAnswerControls(); } }
    };
    $('refreshAttempt').onclick = async () => { try { await refreshAttempt(); } catch (e) { if (e instanceof StaleContextError) return; testStatus(e.message); } };
    $('requestReview').onclick = async () => {
      const epoch = contextEpoch;
      try {
        const attempt = $('attempt').value.trim(); if (!attempt) throw new Error('请先提交作答并读取 Attempt ID');
        const reason = window.prompt('请输入复核原因'); if (!reason) return;
        const data = await call('/api/v1/attempts/' + encodeURIComponent(attempt) + '/review-requests', {method: 'POST', headers: {'Content-Type': 'application/json', 'Idempotency-Key': 'ui-review-' + crypto.randomUUID()}, body: JSON.stringify({reason, details: {source: 'learning-workbench'}})});
        await refreshAttempt(); if (epoch !== contextEpoch) return; testStatus('复核申请已提交，成绩不会被客户端直接修改。'); show(data);
      } catch (e) { if (e instanceof StaleContextError) return; testStatus(e.message); }
    };
    $('confirm').onclick = async () => {
      const epoch = contextEpoch;
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
        await $('refreshItems').onclick(); if (epoch === contextEpoch) show(result);
      } catch (e) { if (e instanceof StaleContextError) return; show(e.message); }
    };
    $('createVariant').onclick = async () => {
      try { const result = await call('/api/v1/variant-jobs', {method:'POST', headers:{'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()}, body:JSON.stringify({objective_id:$('variantObjective').value, source_question_version_id:$('variantSource').value})});
        show(result); await $('loadVariants').onclick();
      } catch (e) { if (!(e instanceof StaleContextError)) show(e.message); }
    };
    $('loadVariants').onclick = async () => {
      try { const result = await call('/api/v1/admin/variant-jobs');
        $('variantJobs').replaceChildren();
        if (!result.items.length) $('variantJobs').textContent = '暂无变式审核任务。';
        result.items.forEach((job) => {
          const button = document.createElement('button'); button.className = 'secondary';
          button.textContent = `${job.id} · ${job.revocation_id ? '已撤销' : job.decision || job.status}`;
          button.onclick = () => loadVariantDetail(job.id); $('variantJobs').append(button);
        });
      } catch (e) { if (!(e instanceof StaleContextError)) $('variantJobs').textContent = e.message; }
    };
    async function loadVariantDetail(jobId) {
      try {
        const detail = await call('/api/v1/admin/variant-jobs/' + encodeURIComponent(jobId));
        const container = $('variantDetail'); container.replaceChildren();
        const pre = document.createElement('pre'); pre.textContent = JSON.stringify(detail.result, null, 2);
        const note = document.createElement('textarea'); note.rows = 3; note.maxLength = 4000; note.placeholder = '人工审核说明（必填）';
        const label = document.createElement('label'); label.append(document.createTextNode('审核说明'), note);
        container.append(pre, label);
        if (!detail.source_current) container.append(document.createTextNode('母题、范围或草稿校验未通过，可拒绝并重新生成。'));
        for (const decision of (detail.review ? (detail.review.decision === 'approve' && !detail.revocation ? ['revoke'] : []) : ['approve','reject'])) {
          const button = document.createElement('button'); button.className = 'secondary'; button.textContent = {approve:'批准并冻结版本',reject:'拒绝草稿',revoke:'撤销投放'}[decision];
          button.disabled = decision === 'approve' && (!detail.source_current || detail.status !== 'succeeded');
          // Retain the same key across network retries of this exact payload.
          const keys = new Map();
          button.onclick = async () => {
            if (!note.value.trim()) { show('请填写人工审核说明'); return; }
            if (!window.confirm(button.textContent + '？')) return;
            const body = decision === 'revoke' ? {note:note.value.trim()} : {decision,result_fingerprint:detail.result_fingerprint,note:note.value.trim()};
            const serialized = JSON.stringify(body); if (!keys.has(serialized)) keys.set(serialized,crypto.randomUUID());
            button.disabled = true;
            try {
              const path = decision === 'revoke' ? '/api/v1/admin/variant-reviews/' + encodeURIComponent(detail.review.id) + '/revoke' : '/api/v1/admin/variant-jobs/' + encodeURIComponent(jobId) + '/review';
              const result = await call(path,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':keys.get(serialized)},body:serialized});
              show(result); await loadVariantDetail(jobId); await $('loadToday').onclick();
            } catch (e) { if (!(e instanceof StaleContextError)) { show(e.message); button.disabled = false; } }
          }; container.append(button);
        }
      } catch (e) { if (!(e instanceof StaleContextError)) show(e.message); }
    }
    function restoreCurrentTest() {
      if (browserSessionMode) savedTest = parseSaved(testStateKey());
      if (familyGameMode) { const scope = parseSaved(chapterStateKey()); gameBook = scope.bookId || ''; gameChapter = scope.chapterId || ''; gameDifficulty = ['auto','easy','normal','hard'].includes(scope.difficulty) ? scope.difficulty : 'auto'; gameCompletedChoices = new Set(Array.isArray(scope.completedIds) ? scope.completedIds.filter((id) => typeof id === 'string') : []); }
      [['questionVersion','questionVersionId'],['card','cardId'],['session','sessionId'],['testItem','testItemId'],['attempt','attemptId']].forEach(([field,key]) => { $(field).value = savedTest[key] || ''; });
      $('testPrompt').textContent = ''; $('mistakes').textContent = ''; show('');
      if (savedTest.sessionId && savedTest.account === $('account').value.trim() && savedTest.learner === $('learner').value.trim()) $('restoreTest').onclick();
    }
    async function initializeBrowserSession() {
      document.querySelector('main').inert = true;
      try {
        const session = await call('/api/v1/auth/session');
        serverContextMode = session.server_context_mode === true;
        contextVersion = session.context_version || 0;
        $('account').value = session.account_id;
        const learners = await call('/api/v1/learners');
        $('learner').replaceChildren(new Option('选择学习者', ''));
        learners.items.forEach((item) => $('learner').add(new Option(item.display_name, item.id)));
        const previousNamespace = workspaceStorage.getItem('dd-learning-active-context');
        const refreshRole = () => { const role = learners.items.find((item) => item.id === $('learner').value)?.role; $('variantSection').hidden = !['admin','reviewer'].includes(role); };
        $('learner').value = session.learner_id || (!serverContextMode && learners.items.length === 1 ? learners.items[0].id : '');
        renderGameProfiles(learners.items);
        $('learner').onchange = async () => {
          const chosen = $('learner').value;
          clearWorkspace();
          try {
            if (serverContextMode || chosen) {
              const selected = await call('/api/v1/learner-context', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({learner_id:chosen || null, expected_revision:contextVersion})});
              if (serverContextMode) contextVersion = selected.context_version;
            }
            workspaceStorage.setItem('dd-learning-active-context', contextNamespace());
            restoreImportState(); restoreCurrentTest();
            document.querySelector('main').inert = !chosen;
            refreshRole(); if (chosen) $('loadToday').onclick();
            if (familyGameMode) { updateGameTheme(); setGameView('home'); if (chosen) $('loadMistakes').onclick(); }
          } catch (e) { if (e instanceof StaleContextError) return; show(e.message); }
        };
        if (previousNamespace && previousNamespace !== contextNamespace()) clearWorkspace();
        workspaceStorage.setItem('dd-learning-active-context', contextNamespace());
        restoreImportState(); restoreCurrentTest();
        document.querySelector('main').inert = !$('learner').value;
        refreshRole(); if ($('learner').value) $('loadToday').onclick();
        if (familyGameMode) {
          updateGameTheme();
          setGameView(location.hash === '#mistakeSection' ? 'notebook' : location.hash === '#testSection' ? 'practice' : 'home', false);
          if ($('learner').value) $('loadMistakes').onclick();
        }
        $('loadLearners').textContent = '退出登录';
        $('loadLearners').onclick = async () => { try { clearWorkspace(); await call('/api/v1/auth/logout', {method:'POST'}); if (familyGameMode) window.location.assign(serviceUrl('/auth/login')); else window.location.reload(); } catch (e) { if (e instanceof StaleContextError) return; show(e.message); } };
      } catch (e) { if (e instanceof StaleContextError) return; show(e.message); $('loadLearners').disabled = true; }
    }
    window.addEventListener('pageshow', (event) => { if (event.persisted) window.location.reload(); });
    window.addEventListener('pagehide', () => clearWorkspace('', false));
    document.addEventListener('visibilitychange', async () => {
      if (!browserSessionMode || document.hidden || !$('account').value) return;
      try { const current = await call('/api/v1/auth/session');
        if (current.account_id !== $('account').value || current.learner_id !== ($('learner').value || null) || current.context_version !== contextVersion) clearWorkspace('学习者或账号已变化，请刷新工作台。');
      } catch (e) { if (!(e instanceof StaleContextError)) clearWorkspace('无法确认登录状态，请刷新工作台。'); }
    });
    $('loadHealth').onclick();
    if (browserSessionMode) initializeBrowserSession();
    else { restoreImportState(); restoreCurrentTest(); }
  </script>
</body>
</html>"""


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    if settings.public_base_path and not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", settings.public_base_path):
        raise ValueError("invalid public base path")
    settings.ensure_dirs()
    db = database or Database(settings.db_path)

    app = FastAPI(title="DD-1.0 Learning Service", version="0.1.0", docs_url="/docs")
    app.state.settings = settings
    app.state.db = db
    browser_sessions = BrowserSessions(settings, db)

    @app.exception_handler(AuthError)
    async def auth_error_handler(_: Request, exc: AuthError):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": "登录或会话校验未通过", "retryable": False}}, headers={"Cache-Control": "no-store"})

    @app.exception_handler(WriteContextChanged)
    async def write_context_error_handler(_: Request, exc: WriteContextChanged):
        return JSONResponse(status_code=409, content={"error": {"code": "LEARNER_CONTEXT_CHANGED", "message": "学习者已变化，请刷新工作台后重试", "retryable": False}}, headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def fence_context_writes(request: Request, call_next):
        fence = None
        if (settings.shared_learner_context_enabled and request.method not in {"GET", "HEAD", "OPTIONS"}
                and request.url.path.startswith("/api/v1/")
                and request.url.path not in {"/api/v1/learner-context", "/api/v1/auth/session", "/api/v1/auth/logout"}):
            account_id = None
            if settings.browser_auth_enabled and request.cookies.get(SESSION_COOKIE):
                try:
                    session = await run_in_threadpool(browser_sessions.authenticate, request)
                    account_id = session["account_id"]
                except AuthError as exc:
                    return await auth_error_handler(request, exc)
            elif settings.adapter_secret and secrets.compare_digest(request.headers.get("X-Adapter-Secret", ""), settings.adapter_secret):
                with db.session() as conn:
                    binding = conn.execute("SELECT account_id FROM identity_bindings WHERE provider=? AND issuer=? AND subject=?",
                                           (request.headers.get("X-Trusted-Provider", "local"), request.headers.get("X-Trusted-Issuer", "learning-service"), request.headers.get("X-Trusted-Subject", ""))).fetchone()
                account_id = binding["account_id"] if binding else None
            if account_id:
                with db.session() as conn:
                    current = read_context(conn, account_id)
                if current["learner_id"]:
                    # get_context validates the client version; the transaction
                    # fence then detects switches/revocations after that check.
                    fence = (db.path.resolve(), account_id, current["learner_id"], current["context_version"])
        token = write_context.set(fence)
        try:
            return await call_next(request)
        finally:
            write_context.reset(token)

    @app.middleware("http")
    async def private_no_store(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith('/api/v1/') or request.url.path == '/ui':
            response.headers['Cache-Control'] = 'no-store'
        return response

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
        def shared_selection(account_id: str, fallback: str | None, browser: bool) -> str | None:
            if not settings.shared_learner_context_enabled:
                return fallback
            with db.session() as conn:
                current = read_context(conn, account_id)
            selected = current["learner_id"]
            if not browser and fallback and fallback != selected:
                raise APIError(409, "LEARNER_CONTEXT_CHANGED", "请重新确认当前学习者")
            if request.url.path in {"/api/v1/learners", "/api/v1/learner-context"}:
                return None
            if selected and (browser or request.headers.get("X-Learner-Context-Version") is not None or request.method not in {"GET", "HEAD", "OPTIONS"}):
                supplied = request.headers.get("X-Learner-Context-Version", "")
                if supplied != str(current["context_version"]):
                    raise APIError(409, "LEARNER_CONTEXT_CHANGED", "学习者已变化，请刷新工作台后重试")
            return selected
        if settings.browser_auth_enabled and request.cookies.get(SESSION_COOKIE):
            session = browser_sessions.authenticate(request)
            learner_id = shared_selection(session["account_id"], request.headers.get("X-Learner-Id") or session["learner_id"], True)
            role = "student"
            if learner_id:
                with db.session() as conn:
                    access = conn.execute("SELECT la.role FROM learner_access la JOIN learners l ON l.id=la.learner_id WHERE la.account_id=? AND la.learner_id=? AND la.active=1 AND l.active=1", (session["account_id"], learner_id)).fetchone()
                if not access:
                    raise APIError(404, "LEARNER_NOT_FOUND", "学习者不可访问")
                role = access["role"]
            return Context(account_id=session["account_id"], learner_id=learner_id, role=role, provider=session["provider"])
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
            if settings.shared_learner_context_enabled:
                # Resolve outside this read connection; never hold a writer while waiting.
                learner_id = shared_selection(account_id, learner_id, False)
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
                "SELECT la.role FROM learner_access la JOIN learners l ON l.id=la.learner_id WHERE la.account_id=? AND la.learner_id=? AND la.active=1 AND l.active=1",
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
            "SELECT la.role FROM learner_access la JOIN learners l ON l.id=la.learner_id WHERE la.account_id=? AND la.learner_id=? AND la.active=1 AND l.active=1",
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
            "external_calls": UsageLedger(db, app.state.settings).summary(),
        }

    @app.post("/api/v1/admin/provider-control")
    def provider_control(body: ProviderControlRequest, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        require_admin(ctx)
        UsageLedger(db, app.state.settings).set_paused(body.paused)
        audit(db, ctx, "provider_control", "provider", None, "paused" if body.paused else "resumed")
        return {"paused": body.paused}

    @app.get("/api/v1/admin/provider-calls")
    def list_provider_calls(ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        require_admin(ctx)
        with db.session() as conn:
            # Pending records first: an operator can reconcile the oldest
            # holds even if a worker lost its resource/result acknowledgement.
            rows = conn.execute("SELECT * FROM provider_calls ORDER BY (state='reconciled'),created_at,id LIMIT 100").fetchall()
        return {"items": [dict(row) for row in rows], "limit": 100, "contains_student_payload": False}

    @app.post("/api/v1/admin/provider-calls/{call_id}/reconcile")
    def reconcile_provider_call(call_id: str, body: ProviderReconciliationRequest, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        require_admin(ctx)
        try:
            result = UsageLedger(db, app.state.settings).reconcile(call_id, body.cost_micros, body.currency, body.billing_reference, body.request_id)
        except ProviderLimit as exc:
            raise APIError(404 if exc.code == "CALL_NOT_FOUND" else 409, exc.code, "费用对账被拒绝")
        audit(db, ctx, "provider_reconcile", "provider_call", call_id, "accepted")
        return result

    @app.get("/ui", response_class=HTMLResponse)
    def ui():
        content = _UI_HTML
        content = content.replace('/* STUDY_SUPPORT_STYLE */', STUDY_STYLE)
        content = content.replace('<!-- STUDY_SUPPORT_PANEL -->', STUDY_PANEL)
        content = content.replace('// STUDY_SUPPORT_SCRIPT', STUDY_SCRIPT)
        content = content.replace('const publicBasePath = "";', 'const publicBasePath = ' + json.dumps(settings.public_base_path) + ';')
        if app.state.settings.browser_auth_enabled:
            content = content.replace('const browserSessionMode = false;', 'const browserSessionMode = true;')
            content = content.replace('账号 ID <input id="account" autocomplete="off" placeholder="开发模式账号">', '已登录账号 <input id="account" readonly>')
            content = content.replace('学习者 ID <input id="learner" autocomplete="off" placeholder="当前学习者">', '学习者 <select id="learner"><option value="">请先登录</option></select>')
            content = content.replace('<h1>DD-1.0 学习工作区</h1>', '<h1>DD-1.0 学习工作区</h1><p><a href="' + html.escape(settings.public_base_path + '/auth/login', quote=True) + '">登录学习工作区</a></p>')
        if settings.family_setup_code:
            content = content.replace('const familyGameMode = false;', 'const familyGameMode = true;')
            content = content.replace('<body>', '<body class="family-game" data-grade="2" data-view="home">')
            content = content.replace('<title>DD-1.0 学习工作区</title>', '<title>学习探险队 · 家庭学习</title>')
            content = content.replace('<button id="reloadContext"', '<a class="game-only" href="' + html.escape(settings.public_base_path + '/auth/login', quote=True) + '" id="gameLoginLink" hidden>重新登录学习工作区</a><button id="reloadContext"')
            content = content.replace('上传资料后先复核，再保存到错题本。今日任务可直接进入测验，刷新后可恢复进度。', '选择七年级或二年级档案，开始练习，也可以手动记下错题。')
            content = content.replace('<h2>错题、诊断与复习</h2>', '<h2>错题本与复习</h2>')
            for section in ('uploadSection', 'importSection', 'variantSection'):
                content = content.replace('<section id="' + section + '">', '<section id="' + section + '" hidden>')
            content = content.replace('<a href="#uploadSection">上传资料</a>', '').replace('<a href="#variantSection">变式审核</a>', '')
            content = content.replace('<div class="row"><label>错题 ID', '<div class="row" hidden><label>错题 ID')
            content = content.replace('<button id="loadHealth"', '<button hidden id="loadHealth"')
        return HTMLResponse(content, headers={"Cache-Control": "no-store"})

    @app.post("/api/v1/auth/session", status_code=201)
    def exchange_browser_session(request: Request):
        token, csrf, expires = browser_sessions.exchange(request)
        response = JSONResponse({"status": "authenticated", "expires_at": expires}, status_code=201, headers={"Cache-Control": "no-store"})
        response.set_cookie(SESSION_COOKIE, token, max_age=settings.browser_session_ttl_seconds, secure=True, httponly=True, samesite="strict", path="/")
        response.set_cookie(CSRF_COOKIE, csrf, max_age=settings.browser_session_ttl_seconds, secure=True, httponly=False, samesite="strict", path="/")
        return response

    @app.get("/api/v1/auth/session")
    def get_browser_session(request: Request):
        session = browser_sessions.authenticate(request)
        with db.session() as conn:
            current = read_context(conn, session["account_id"])
        return JSONResponse({"account_id": session["account_id"], "learner_id": current["learner_id"] if settings.shared_learner_context_enabled else session["learner_id"],
                             "expires_at": session["expires_at"], "context_version": current["context_version"], "server_context_mode": settings.shared_learner_context_enabled,
                             "identity": {"provider": session["provider"], "issuer": session["issuer"], "subject": session["subject"]}}, headers={"Cache-Control": "no-store"})

    @app.post("/api/v1/auth/logout")
    def logout_browser_session(request: Request):
        browser_sessions.logout(request)
        response = JSONResponse({"status": "logged_out"}, headers={"Cache-Control": "no-store"})
        response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict")
        response.delete_cookie(CSRF_COOKIE, path="/", secure=True, samesite="strict")
        return response

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

    @app.get("/api/v1/learner-context")
    def get_learner_context(ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        with db.session() as conn:
            return read_context(conn, ctx.account_id)

    @app.post("/api/v1/learner-context")
    def learner_context(body: dict[str, Any], request: Request, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        if settings.shared_learner_context_enabled and not request.cookies.get(SESSION_COOKIE):
            raise APIError(403, "TRUSTED_BROWSER_REQUIRED", "请在受信工作台选择学习者")
        learner_id = body.get("learner_id")
        if not (settings.shared_learner_context_enabled and "learner_id" in body and learner_id is None) and (not isinstance(learner_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", learner_id)):
            raise APIError(422, "LEARNER_REQUIRED", "需要 learner_id")
        session = browser_sessions.authenticate(request) if app.state.settings.browser_auth_enabled and request.cookies.get(SESSION_COOKIE) else None
        with db.session(write=True) as conn:
            if learner_id is not None:
                ensure_access(conn, ctx.account_id, learner_id)
            if settings.shared_learner_context_enabled:
                try:
                    return select_context(conn, ctx.account_id, learner_id, body.get("expected_revision"))
                except ContextConflict:
                    raise APIError(409, "LEARNER_CONTEXT_CHANGED", "学习者上下文已变化，请刷新后重试")
            if session:
                conn.execute("UPDATE browser_sessions SET learner_id=? WHERE id=? AND revoked_at IS NULL", (learner_id, session["id"]))
            conn.execute("UPDATE interaction_challenges SET consumed_at=? WHERE actor_account_id=? AND consumed_at IS NULL", (utc_now(), ctx.account_id))
        return {"learner_id": learner_id, "context_version": new_id("context")}

    @app.post("/api/v1/documents", status_code=201)
    async def upload_document(file: UploadFile = File(...), kind: str = "paper", completed_date: str | None = None, ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        learner_id = learner_for(ctx, db=db)
        if kind not in {"paper", "homework", "answer_key"}:
            raise APIError(422, "INVALID_DOCUMENT_KIND", "资料类型不支持")
        supplied_media_type = (file.content_type or mimetypes.guess_type(file.filename or "")[0] or "").lower()
        data = await file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise APIError(413, "UPLOAD_TOO_LARGE", "文件超过大小限制")
        media_type = _detect_media_type(data, file.filename or "", supplied_media_type)
        if media_type is None:
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
            elif media_type in _OFFICE_MIME_ALIASES:
                page_assets, office_error = _office_pages(data, media_type)
                decode_error = decode_error or office_error
                page_assets = page_assets or [{"text": None, "format": None}]
                if office_error:
                    page_assets = [
                        {
                            **page,
                            "object_key": object_key,
                            "media_type": media_type,
                            "byte_size": 0,
                            "failure_code": office_error,
                        }
                        for page in page_assets
                    ]
                else:
                    page_assets = [
                        {
                            **page,
                            "object_key": object_key,
                            "media_type": media_type,
                            "byte_size": len(data),
                            "failure_code": None,
                        }
                        for page in page_assets
                    ]
            elif decode_error:
                page_assets = [{"object_key": None, "media_type": media_type, "byte_size": 0, "width": None, "height": None, "failure_code": decode_error} for _ in range(pages)]
            else:
                page_assets = [{"object_key": object_key, "media_type": media_type, "byte_size": len(data), "width": None, "height": None, "failure_code": None, "text": None, "format": None}]
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
                    conn.execute(
                        "INSERT INTO source_pages(id,document_id,page_index,status,object_key,asset_id,failure_code,width,height,transform_json,extracted_text,extraction_format) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            new_id("page"), document_id, index,
                            "failed" if page.get("failure_code") else "queued",
                            page.get("object_key"),
                            page_asset_id,
                            page.get("failure_code"), page.get("width"), page.get("height"),
                            json_dumps({"rotation": 0}), page.get("text"), page.get("format"),
                        ),
                    )
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
                item_content = json_loads(item["content_json"], {})
                evidence = json_loads(item["teacher_evidence_json"], {})
                objective_id = item_content.get("objective_id")
                if not objective_id:
                    objective = conn.execute("SELECT id FROM review_objectives ORDER BY created_at LIMIT 1").fetchone()
                    objective_id = objective["id"] if objective else None
                judgment = conn.execute("SELECT id FROM import_judgments WHERE item_id=? AND revision=? AND verification_status='manual' AND verdict=? ORDER BY created_at DESC LIMIT 1", (item_id, expected_revision, item["verdict"])).fetchone()
                # reviewed_import_candidates guarantees a matching judgment and evidence.
                if item["verdict"] in {"incorrect", "partial"} and objective_id:
                    entry = conn.execute("SELECT * FROM mistake_entries WHERE learner_id=? AND objective_id=? AND status='active' ORDER BY created_at LIMIT 1", (learner_id, objective_id)).fetchone()
                    if not entry:
                        entry_id = new_id("mistake")
                        mistake_content = {
                            **item_content,
                            "objective_id": objective_id,
                            "student_answer": item["raw_answer"] if item["raw_answer"] is not None else item_content.get("student_answer"),
                            "verdict": item["verdict"],
                            "teacher_evidence": evidence,
                        }
                        conn.execute("INSERT INTO mistake_entries(id,learner_id,objective_id,status,diagnosis_status,created_at,content_json) VALUES (?,?,?,?,?,?,?)", (entry_id, learner_id, objective_id, "active", "draft", utc_now(), json_dumps(mistake_content)))
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

    @app.post("/api/v1/mistakes/manual", status_code=201)
    def create_manual_mistake(body: ManualMistakeRequest, request: Request, ctx: Context = Depends(get_context), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        learner_id = learner_for(ctx, db=db)
        key = request.headers.get("Idempotency-Key")
        if not key:
            raise APIError(422, "IDEMPOTENCY_REQUIRED", "手动录入必须带 Idempotency-Key")
        question_text = body.question_text.strip()
        if not question_text:
            raise APIError(422, "QUESTION_REQUIRED", "题干不能为空")
        content = {
            "question_text": question_text,
            "student_answer": body.student_answer.strip() if body.student_answer and body.student_answer.strip() else None,
            "correct_answer": body.correct_answer.strip() if body.correct_answer and body.correct_answer.strip() else None,
            "note": body.note.strip() if body.note and body.note.strip() else None,
        }
        objective_id = body.objective_id.strip() if body.objective_id and body.objective_id.strip() else None
        request_body = {**body.model_dump(), "question_text": question_text, "objective_id": objective_id}
        with db.session(write=True) as conn:
            prior = idempotent_result(conn, ctx, learner_id, "create_manual_mistake", learner_id, key, request_body)
            if prior:
                return prior
            if objective_id:
                objective_for_learner(conn, learner_id, objective_id)
            mistake_id = new_id("mistake")
            now = utc_now()
            conn.execute(
                "INSERT INTO mistake_entries(id,learner_id,objective_id,status,diagnosis_status,created_at,content_json) VALUES (?,?,?,?,?,?,?)",
                (mistake_id, learner_id, objective_id, "active", "draft", now, json_dumps(content)),
            )
            conn.execute(
                "INSERT INTO mistake_sources(id,entry_id,learner_id,source_kind,occurrence_id,item_locator,active,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (new_id("source"), mistake_id, learner_id, "manual", new_id("manual"), "manual-entry", 1, now),
            )
            review_card_id = _ensure_review_card(conn, learner_id, objective_id, settings) if objective_id else None
            result = {
                "mistake_id": mistake_id,
                "status": "active",
                "objective_id": objective_id,
                "review_card_id": review_card_id,
                "source_kind": "manual",
            }
            save_idempotent(conn, ctx, learner_id, "create_manual_mistake", learner_id, key, request_body, result)
        audit(db, ctx, "create_manual_mistake", "mistake", mistake_id, "accepted", {"source_kind": "manual", "has_objective": bool(objective_id)})
        return result

    @app.get("/api/v1/mistakes")
    def list_mistakes(ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            rows = conn.execute(
                "SELECT m.*,o.code AS objective_code,o.title AS objective_title FROM mistake_entries m LEFT JOIN review_objectives o ON o.id=m.objective_id WHERE m.learner_id=? ORDER BY m.created_at DESC",
                (learner_id,),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["content"] = json_loads(item.pop("content_json", "{}"), {})
            items.append(item)
        return {"items": items, "next_cursor": None}

    @app.get("/api/v1/mistakes/{mistake_id}")
    def get_mistake(mistake_id: str, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            entry = conn.execute("SELECT * FROM mistake_entries WHERE id=? AND learner_id=?", (mistake_id, learner_id)).fetchone()
            if not entry:
                raise APIError(404, "MISTAKE_NOT_FOUND", "错题不存在")
            sources = conn.execute(
                "SELECT s.id,s.source_kind,s.occurrence_id,s.item_locator,s.item_id,s.attempt_id,s.active,s.created_at,"
                "i.raw_answer,i.content_json AS item_content_json,i.verdict,i.teacher_evidence_json,"
                "j.id AS import_judgment_id,j.revision AS judgment_revision "
                "FROM mistake_sources s "
                "LEFT JOIN import_items i ON i.id=s.item_id AND i.learner_id=s.learner_id "
                "LEFT JOIN import_judgments j ON j.id=s.import_judgment_id "
                "WHERE s.entry_id=? AND s.learner_id=? ORDER BY s.created_at",
                (mistake_id, learner_id),
            ).fetchall()
            review_card = None
            if entry["objective_id"]:
                review_card = conn.execute(
                    "SELECT id,objective_id,state,stage,due_at,active,revision,timezone_snapshot,scheduler_version FROM review_cards WHERE learner_id=? AND objective_id=? AND active=1 ORDER BY created_at LIMIT 1",
                    (learner_id, entry["objective_id"]),
                ).fetchone()
            diagnoses = conn.execute("SELECT id,status,model_id,prompt_version,evidence_json,output_json,created_at FROM diagnoses WHERE mistake_id=? ORDER BY created_at DESC", (mistake_id,)).fetchall()
        mistake = dict(entry)
        mistake["content"] = json_loads(mistake.pop("content_json", "{}"), {})
        source_items = []
        for row in sources:
            source = dict(row)
            source["content"] = json_loads(source.pop("item_content_json", "{}"), {})
            source["evidence"] = json_loads(source.pop("teacher_evidence_json", "{}"), {})
            source_items.append(source)
        return {"mistake": mistake, "sources": source_items, "review_card": dict(review_card) if review_card else None, "diagnoses": [{**dict(row), "evidence": json_loads(row["evidence_json"], {}), "output": json_loads(row["output_json"], {})} for row in diagnoses]}

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
            evidence = _diagnosis_snapshot(conn, mistake_id, learner_id)
        provider_result = _provider_for_settings(diagnosis_provider, settings.diagnosis_provider, settings, db).diagnose(evidence)
        output = _diagnosis_output(provider_result)
        with db.session(write=True) as conn:
            if _diagnosis_snapshot(conn, mistake_id, learner_id)["snapshot_hash"] != evidence["snapshot_hash"]:
                raise APIError(409, "STALE_DIAGNOSIS_EVIDENCE", "诊断证据已变化，请重新请求")
            evidence.update({"provider_id": provider_result.provider_id, "provider_status": provider_result.status,
                             "provider_evidence": provider_result.evidence, "external_call": provider_result.evidence.get("external_call", False)})
            diagnosis_id = new_id("diagnosis")
            conn.execute("INSERT INTO diagnoses(id,mistake_id,evidence_json,output_json,model_id,prompt_version,status,created_at) VALUES (?,?,?,?,?,?,?,?)", (diagnosis_id, mistake_id, json_dumps(evidence), json_dumps(output), provider_result.evidence.get("model_id", provider_result.provider_id), provider_result.evidence.get("prompt_version", "diagnose-v1"), "needs_review", utc_now()))
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
            objective_for_learner(conn, learner_id, question["objective_id"])
            if body.textbook_book_id is not None or body.textbook_chapter_id is not None:
                curriculum = conn.execute('SELECT curriculum_id FROM learners WHERE id=?', (learner_id,)).fetchone()[0]
                try:
                    book, chapter = textbook_learning_scope(curriculum, body.textbook_book_id, body.textbook_chapter_id)
                except ValueError:
                    raise APIError(422, 'TEXTBOOK_SCOPE_INVALID', '请选择当前年级的课本，章节可不选')
                placement = textbook_practice_scope(body.question_version_id)
                if not placement or placement['book_id'] != book['id'] or (chapter['id'] and placement['chapter_id'] != chapter['id']):
                    raise APIError(422, 'QUESTION_OUTSIDE_TEXTBOOK_SCOPE', '这道题不在所选课本或章节范围内')
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
    def variant_job(body: dict[str, Any], ctx: Context = Depends(get_context), db: Database = Depends(get_db), request: Request = None):
        learner_id = learner_for(ctx, db=db)
        objective_id = body.get("objective_id")
        if not objective_id:
            raise APIError(422, "OBJECTIVE_REQUIRED", "需要 objective_id")
        with db.session(write=True) as conn:
            source_question_version_id = body.get("source_question_version_id")
            if source_question_version_id is not None and not isinstance(source_question_version_id, str):
                raise APIError(422, "VARIANT_REQUEST_INVALID", "source_question_version_id 必须是字符串")
            validate_variant_source(conn, learner_id, objective_id, source_question_version_id)
            payload = {"objective_id": objective_id, "source_question_version_id": source_question_version_id or None}
            key = request.headers.get('Idempotency-Key') if request else None
            if key is not None and (not key.strip() or len(key) > 128):
                raise APIError(422, 'IDEMPOTENCY_REQUIRED', '变式请求幂等键无效')
            if key:
                prior = idempotent_result(conn, ctx, learner_id, 'request_variant', objective_id, key, payload)
                if prior:
                    return prior
            job_key = f"variant-request:{ctx.account_id}:{learner_id}:{objective_id}:{_hash(key)}" if key else f"variant:{learner_id}:{objective_id}:{source_question_version_id or 'none'}"
            job_id = enqueue(conn, learner_id, 'variant_generation', payload, job_key)
            status = conn.execute('SELECT status FROM jobs WHERE id=?', (job_id,)).fetchone()[0]
            result = {'job_id': job_id, 'status': status, 'approval_required': True}
            if key:
                save_idempotent(conn, ctx, learner_id, 'request_variant', objective_id, key, payload, result)
        return result

    def read_study_reference(request, ctx, db, settings, allowed, reader):
        pairs = request.query_params.multi_items()
        if any(key not in allowed for key, _ in pairs) or len({key for key, _ in pairs}) != len(pairs):
            raise APIError(422, "MATH_REFERENCE_SCOPE_INVALID", "知识参考查询参数无效")
        learner_id = learner_for(ctx, db=db)
        def selection():
            with db.session() as conn:
                return read_context(conn, ctx.account_id)
        pinned = selection() if settings.shared_learner_context_enabled else None
        if pinned and (pinned["learner_id"] != learner_id
                       or request.headers.get("X-Learner-Context-Version") != str(pinned["context_version"])):
            raise APIError(409, "LEARNER_CONTEXT_CHANGED", "学习者已变化，请刷新工作台后重试")
        try:
            with db.session() as conn:
                curriculum = conn.execute('SELECT curriculum_id FROM learners WHERE id=?', (learner_id,)).fetchone()[0]
                result = reader(conn, learner_id, curriculum, settings.textbook_dir)
        except ReferenceError as exc:
            raise APIError(exc.status, exc.code, exc.message) from None
        if pinned and selection() != pinned:
            raise APIError(409, "LEARNER_CONTEXT_CHANGED", "学习者已变化，请刷新工作台后重试")
        learner_for(ctx, db=db)  # Recheck access after filesystem/metadata reads.
        return result

    @app.get("/api/v1/math-references")
    def math_references(request: Request, book_id: str = "", chapter_id: str = "",
                        question_version_id: str = "", concept_id: str = "",
                        ctx: Context = Depends(get_context), db: Database = Depends(get_db),
                        settings: Settings = Depends(get_settings)):
        """Read reviewed metadata for the authenticated, server-selected learner."""
        return read_study_reference(request, ctx, db, settings,
                                    {"book_id", "chapter_id", "question_version_id", "concept_id"},
                                    lambda conn, learner, curriculum, directory:
                                        query_math_reference(conn, learner, curriculum, directory, book_id=book_id,
                                                             chapter_id=chapter_id, question_version_id=question_version_id,
                                                             concept_id=concept_id))

    @app.get("/api/v1/study-support")
    def study_support(request: Request, subject: str = "", book_id: str = "", chapter_id: str = "",
                      ctx: Context = Depends(get_context), db: Database = Depends(get_db),
                      settings: Settings = Depends(get_settings)):
        """Local reading prompts and Markdown/Mermaid artifacts for current subjects."""
        return read_study_reference(request, ctx, db, settings, {"subject", "book_id", "chapter_id"},
                                    lambda conn, learner, curriculum, directory:
                                        query_study_support(conn, learner, curriculum, directory,
                                                            subject=subject, book_id=book_id, chapter_id=chapter_id))

    @app.get("/api/v1/textbooks")
    def textbooks(ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            curriculum = conn.execute('SELECT curriculum_id FROM learners WHERE id=?', (learner_id,)).fetchone()[0]
        return {'items': textbook_catalogue(curriculum), 'subjects': textbook_subjects(curriculum),
                'grade_notice': '二年级英语按学校安排暂未开设。' if curriculum=='math-g2-v1' else
                                '七年级开设以上七门学科；物理从八年级、化学从九年级开始。' if curriculum=='math-g7-v1' else ''}

    @app.post("/api/v1/textbooks/search")
    def textbook_search(body: dict[str, Any], ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            curriculum = conn.execute('SELECT curriculum_id FROM learners WHERE id=?', (learner_id,)).fetchone()[0]
        try:
            return textbook_search_scope(curriculum, body)
        except ValueError:
            raise APIError(422, 'TEXTBOOK_SCOPE_INVALID', '请选择当前年级的课本，章节可不选，检索词最多160字')

    @app.get("/api/v1/textbooks/{book_id}/pages/{printed_page}/image", response_class=Response,
             responses={200: {"content": {"image/png": {}}}})
    def textbook_page_image(book_id: str, printed_page: int, ctx: Context = Depends(get_context),
                            db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            curriculum = conn.execute('SELECT curriculum_id FROM learners WHERE id=?', (learner_id,)).fetchone()[0]
        try:
            book, pdf_page = textbook_page_scope(curriculum, book_id, printed_page)
        except ValueError:
            raise APIError(404, 'TEXTBOOK_PAGE_NOT_FOUND', '当前年级没有这一教材页')
        try:
            content = render_textbook_page(settings.textbook_dir, book['id'], pdf_page)
        except (OSError, ValueError, RuntimeError):
            raise APIError(503, 'TEXTBOOK_PAGE_UNAVAILABLE', '教材原页暂时不可用，请稍后重试', True)
        return Response(content, media_type='image/png', headers={'X-Content-Type-Options': 'nosniff'})

    @app.get("/api/v1/question-choices")
    def question_choices(objective_id: str | None = None, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            if objective_id:
                objective_for_learner(conn, learner_id, objective_id)
            rows = conn.execute(
                "SELECT v.id AS question_version_id,v.version,v.variant_kind,q.objective_id "
                "FROM question_versions v JOIN questions q ON q.id=v.question_id "
                "JOIN review_objectives o ON o.id=q.objective_id JOIN knowledge_points k ON k.id=o.knowledge_point_id "
                "JOIN learners l ON l.id=? AND l.curriculum_id=k.curriculum_id "
                "WHERE v.approval='approved' AND q.approval='approved' AND (q.visibility='shared' OR q.learner_id=?) "
                "AND (? IS NULL OR q.objective_id=?) ORDER BY v.created_at,v.id",
                (learner_id, learner_id, objective_id, objective_id)).fetchall()
            objectives = conn.execute(
                "SELECT o.id,o.title FROM review_objectives o JOIN knowledge_points k ON k.id=o.knowledge_point_id "
                "JOIN learners l ON l.curriculum_id=k.curriculum_id WHERE l.id=? ORDER BY o.id", (learner_id,)).fetchall()
            practice_guidance = learner_guidance(conn, learner_id)
        return {"items": [{**dict(row), 'textbook_scope': textbook_practice_scope(row['question_version_id']), 'practice': practice_metadata(row['question_version_id'])} for row in rows],
                "objectives": [dict(row) for row in objectives], "practice_guidance": practice_guidance}

    def reviewer_context(request: Request, ctx: Context, db: Database) -> str:
        if ctx.role not in {'reviewer', 'admin'}:
            raise APIError(403, 'FORBIDDEN', '需要人工审核权限')
        if settings.browser_auth_enabled and not request.cookies.get(SESSION_COOKIE):
            raise APIError(403, 'TRUSTED_BROWSER_REQUIRED', '请在受信工作台进行人工审核')
        return learner_for(ctx, db=db)

    def review_job(conn, job_id: str, learner_id: str, account_id: str):
        ensure_access(conn, account_id, learner_id, {'reviewer', 'admin'})
        row = conn.execute("SELECT * FROM jobs WHERE id=? AND learner_id=? AND kind='variant_generation'", (job_id, learner_id)).fetchone()
        if not row:
            raise APIError(404, 'VARIANT_JOB_NOT_FOUND', '变式任务不存在')
        return row

    @app.get('/api/v1/admin/variant-jobs')
    def list_variant_reviews(request: Request, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = reviewer_context(request, ctx, db)
        with db.session() as conn:
            ensure_access(conn, ctx.account_id, learner_id, {'reviewer', 'admin'})
            rows = conn.execute("SELECT j.id,j.status,j.created_at,r.id AS review_id,r.decision,r.question_version_id,x.id AS revocation_id "
                "FROM jobs j LEFT JOIN variant_reviews r ON r.job_id=j.id LEFT JOIN variant_revocations x ON x.review_id=r.id "
                "WHERE j.learner_id=? AND j.kind='variant_generation' ORDER BY j.created_at DESC LIMIT 100", (learner_id,)).fetchall()
        return {'items': [dict(row) for row in rows]}

    @app.get('/api/v1/admin/variant-jobs/{job_id}')
    def variant_review_detail(job_id: str, request: Request, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = reviewer_context(request, ctx, db)
        with db.session() as conn:
            job = review_job(conn, job_id, learner_id, ctx.account_id)
            review = conn.execute('SELECT * FROM variant_reviews WHERE job_id=?', (job_id,)).fetchone()
            revocation = conn.execute('SELECT * FROM variant_revocations WHERE review_id=?', (review['id'],)).fetchone() if review else None
            source_current = True
            try:
                current = _variant_snapshot(conn, learner_id, json_loads(job['input_json'], {}))
                checked_draft(current, json_loads(job['result_json'], {}))
            except (APIError, ValueError, TypeError, AttributeError):
                source_current = False
        return {'job_id': job_id, 'status': job['status'], 'result_fingerprint': variant_fingerprint(job),
                'result': json_loads(job['result_json'], {}), 'source_current': source_current,
                'review': dict(review) if review else None, 'revocation': dict(revocation) if revocation else None}

    @app.post('/api/v1/admin/variant-jobs/{job_id}/review')
    def review_variant(job_id: str, body: VariantReviewRequest, request: Request, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = reviewer_context(request, ctx, db)
        key = request.headers.get('Idempotency-Key', '')
        if not key.strip() or len(key) > 128:
            raise APIError(422, 'IDEMPOTENCY_REQUIRED', '人工审核必须带幂等键')
        payload = body.model_dump()
        with db.session(write=True) as conn:
            job = review_job(conn, job_id, learner_id, ctx.account_id)
            prior = idempotent_result(conn, ctx, learner_id, 'review_variant', job_id, key, payload)
            if prior:
                return prior
            if conn.execute('SELECT 1 FROM variant_reviews WHERE job_id=?', (job_id,)).fetchone():
                raise APIError(409, 'VARIANT_ALREADY_REVIEWED', '任务已有冻结审核记录')
            if job['status'] != 'succeeded':
                raise APIError(409, 'VARIANT_NOT_READY', '变式任务尚未成功或已取消')
            if variant_fingerprint(job) != body.result_fingerprint:
                raise APIError(409, 'VARIANT_RESULT_CHANGED', '候选指纹已变化，请重新读取')
            source_request = json_loads(job['input_json'], {})
            objective_id = source_request.get('objective_id')
            objective_for_learner(conn, learner_id, objective_id)
            if body.decision == 'approve':
                snapshot = _variant_snapshot(conn, learner_id, source_request)
                try:
                    draft = checked_draft(snapshot, json_loads(job['result_json'], {}))
                except (ValueError, TypeError, AttributeError):
                    raise APIError(409, 'VARIANT_DRAFT_INVALID', '候选、母题或整数域需重新复核')
                result = publish_variant(conn, job, draft, ctx.account_id, body.note, body.result_fingerprint)
            else:
                review_id = new_id('variant_review')
                conn.execute('INSERT INTO variant_reviews(id,job_id,learner_id,objective_id,source_question_version_id,result_fingerprint,decision,note,reviewed_by_account_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (review_id, job_id, learner_id, objective_id, source_request.get('source_question_version_id'), body.result_fingerprint, 'reject', body.note, ctx.account_id, utc_now()))
                result = {'review_id': review_id, 'job_id': job_id, 'status': 'rejected', 'question_version_id': None}
            save_idempotent(conn, ctx, learner_id, 'review_variant', job_id, key, payload, result)
            review_audit(conn, ctx.account_id, learner_id, 'review_variant', result['review_id'], {'decision': body.decision, 'result_fingerprint': body.result_fingerprint, 'question_version_id': result['question_version_id']})
        return result

    @app.post('/api/v1/admin/variant-reviews/{review_id}/revoke')
    def revoke_variant(review_id: str, body: VariantRevokeRequest, request: Request, ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = reviewer_context(request, ctx, db)
        key = request.headers.get('Idempotency-Key', '')
        if not key.strip() or len(key) > 128:
            raise APIError(422, 'IDEMPOTENCY_REQUIRED', '撤销必须带幂等键')
        payload = body.model_dump()
        with db.session(write=True) as conn:
            ensure_access(conn, ctx.account_id, learner_id, {'reviewer', 'admin'})
            review = conn.execute("SELECT * FROM variant_reviews WHERE id=? AND learner_id=? AND decision='approve'", (review_id, learner_id)).fetchone()
            if not review:
                raise APIError(404, 'VARIANT_REVIEW_NOT_FOUND', '批准记录不存在')
            prior = idempotent_result(conn, ctx, learner_id, 'revoke_variant', review_id, key, payload)
            if prior:
                return prior
            if conn.execute('SELECT 1 FROM variant_revocations WHERE review_id=?', (review_id,)).fetchone():
                raise APIError(409, 'VARIANT_ALREADY_REVOKED', '版本已经撤销')
            now, version_id, revocation_id = utc_now(), review['question_version_id'], new_id('variant_revoke')
            conn.execute('INSERT INTO variant_revocations(id,review_id,learner_id,revoked_by_account_id,note,created_at) VALUES (?,?,?,?,?,?)', (revocation_id, review_id, learner_id, ctx.account_id, body.note, now))
            conn.execute("UPDATE question_versions SET approval='retracted' WHERE id=?", (version_id,))
            conn.execute("UPDATE questions SET approval='retracted' WHERE id=(SELECT question_id FROM question_versions WHERE id=?)", (version_id,))
            conn.execute("UPDATE interaction_challenges SET consumed_at=COALESCE(consumed_at,?) WHERE resource_id IN (SELECT id FROM test_items WHERE question_version_id=? AND status IN ('reserved','presented'))", (now, version_id))
            conn.execute("UPDATE test_items SET status='invalidated' WHERE question_version_id=? AND status IN ('reserved','presented')", (version_id,))
            conn.execute("UPDATE test_sessions SET status='cancelled',completed_at=? WHERE id IN (SELECT session_id FROM test_items WHERE question_version_id=? AND status='invalidated') AND NOT EXISTS (SELECT 1 FROM test_items WHERE session_id=test_sessions.id AND status NOT IN ('graded','cancelled','invalidated'))", (now, version_id))
            result = {'review_id': review_id, 'revocation_id': revocation_id, 'status': 'revoked', 'question_version_id': version_id, 'prior_grades_unchanged': True}
            save_idempotent(conn, ctx, learner_id, 'revoke_variant', review_id, key, payload, result)
            review_audit(conn, ctx.account_id, learner_id, 'revoke_variant', review_id, {'question_version_id': version_id, 'prior_grades_unchanged': True})
        return result

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
        return {**{k:v for k,v in dict(row).items() if k != "result_json"}, "result": ({"status": "needs_review", "approval_required": True} if row["kind"] == "variant_generation" else json_loads(row["result_json"], None))}

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
                "variant_review": "SELECT id FROM variant_reviews WHERE learner_id=?",
                "private_question": "SELECT id FROM questions WHERE learner_id=?",
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
            conn.execute("UPDATE questions SET approval='retracted' WHERE learner_id=?", (learner_id,))
            conn.execute("UPDATE question_versions SET approval='retracted' WHERE question_id IN (SELECT id FROM questions WHERE learner_id=?)", (learner_id,))
            conn.execute("UPDATE jobs SET status='cancelled',lease_token=NULL,lease_until=NULL,error_code='DATA_DELETED' WHERE learner_id=? AND status IN ('queued','running')", (learner_id,))
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
            result = _process_variant(db, job, token, settings)
        else:
            result = {"status": "skipped", "reason": "unsupported_job_kind"}
        with db.session(write=True) as conn:
            if job["kind"] == "variant_generation":
                current = _variant_snapshot(conn, job["learner_id"], json_loads(job["input_json"], {}))
                if current["snapshot_hash"] != result["source_snapshot_hash"]:
                    raise APIError(409, "STALE_VARIANT_SOURCE", "变式来源已变化，拒绝迟到结果")
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
    diagnosis_id = "diagnosis_job_" + _hash(job["id"])[:32]
    with db.session() as conn:
        if not conn.execute("SELECT 1 FROM jobs WHERE id=? AND status='running' AND lease_token=?", (job["id"], token)).fetchone():
            raise APIError(409, "STALE_LEASE", "任务租约已失效")
        evidence = _diagnosis_snapshot(conn, mistake_id, job["learner_id"])
        previous = conn.execute("SELECT id,output_json FROM diagnoses WHERE id=? AND mistake_id=?", (diagnosis_id, mistake_id)).fetchone()
        if previous:
            previous_output = json_loads(previous["output_json"], {})
            return {"mistake_id": mistake_id, "diagnosis_id": diagnosis_id, "status": "needs_review",
                    "provider_id": previous_output.get("provider_id"), "review_required": True}

    provider_result = _provider_for_settings(diagnosis_provider, settings.diagnosis_provider, settings, db).diagnose(evidence)
    output = _diagnosis_output(provider_result)
    with db.session(write=True) as conn:
        if not conn.execute("SELECT 1 FROM jobs WHERE id=? AND status='running' AND lease_token=?", (job["id"], token)).fetchone():
            raise APIError(409, "STALE_LEASE", "任务租约已失效")
        if _diagnosis_snapshot(conn, mistake_id, job["learner_id"])["snapshot_hash"] != evidence["snapshot_hash"]:
            raise APIError(409, "STALE_DIAGNOSIS_EVIDENCE", "诊断证据已变化，请重新请求")
        evidence.update({"provider_id": provider_result.provider_id, "provider_status": provider_result.status,
                         "provider_evidence": provider_result.evidence, "external_call": provider_result.evidence.get("external_call", False)})
        conn.execute(
            "INSERT INTO diagnoses(id,mistake_id,evidence_json,output_json,model_id,prompt_version,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (diagnosis_id, mistake_id, json_dumps(evidence), json_dumps(output), provider_result.evidence.get("model_id", provider_result.provider_id), provider_result.evidence.get("prompt_version", "diagnose-v1"), "needs_review", utc_now()),
        )
        conn.execute("UPDATE mistake_entries SET diagnosis_status='needs_review' WHERE id=?", (mistake_id,))
    return {"mistake_id": mistake_id, "diagnosis_id": diagnosis_id, "status": "needs_review", "provider_id": provider_result.provider_id, "review_required": True}


def _diagnosis_snapshot(conn: sqlite3.Connection, mistake_id: str, learner_id: str) -> dict[str, Any]:
    entry = conn.execute(
        "SELECT m.* FROM mistake_entries m JOIN learners l ON l.id=m.learner_id WHERE m.id=? AND m.learner_id=? AND m.status='active' AND l.active=1",
        (mistake_id, learner_id),
    ).fetchone()
    if not entry:
        raise APIError(404, "MISTAKE_NOT_FOUND", "错题不存在或已撤回")
    content = json_loads(entry["content_json"], {})
    content = content if isinstance(content, dict) else {}
    sources = conn.execute(
        "SELECT ms.id,ms.item_id,ms.attempt_id,i.revision,i.status AS item_status,i.raw_answer,i.content_json AS item_content,"
        "i.teacher_evidence_json,a.raw_answer AS attempt_answer,a.status AS attempt_status,qv.content_json AS question_content "
        "FROM mistake_sources ms LEFT JOIN import_items i ON i.id=ms.item_id AND i.learner_id=ms.learner_id "
        "LEFT JOIN attempts a ON a.id=ms.attempt_id AND a.learner_id=ms.learner_id "
        "LEFT JOIN test_items ti ON ti.id=a.test_item_id AND ti.learner_id=ms.learner_id "
        "LEFT JOIN question_versions qv ON qv.id=ti.question_version_id "
        "WHERE ms.entry_id=? AND ms.learner_id=? AND ms.active=1 ORDER BY ms.created_at DESC,ms.id",
        (mistake_id, learner_id),
    ).fetchall()
    fields = {key: content[key] for key in ("question_text", "student_answer", "student_steps", "correct_answer", "teacher_feedback")
              if isinstance(content.get(key), str) and content[key].strip()}
    source_metadata = []
    for index, source in enumerate(sources):
        source_metadata.append({"source_id": source["id"], "item_id": source["item_id"], "attempt_id": source["attempt_id"],
                                "revision": source["revision"], "item_status": source["item_status"], "attempt_status": source["attempt_status"],
                                "content_hash": _request_hash([source["item_content"], source["question_content"], source["raw_answer"], source["attempt_answer"], source["teacher_evidence_json"]])})
        if index:
            continue
        item_content = json_loads(source["item_content"], {})
        question_content = json_loads(source["question_content"], {})
        for key in fields.keys() | {"question_text", "student_answer", "student_steps", "correct_answer", "teacher_feedback"}:
            value = item_content.get(key) if isinstance(item_content, dict) else None
            if isinstance(value, str) and value.strip():
                fields[key] = value
        if isinstance(question_content, dict) and isinstance(question_content.get("prompt"), str):
            fields.setdefault("question_text", question_content["prompt"])
        raw_answer = source["raw_answer"] if source["raw_answer"] is not None else source["attempt_answer"]
        if isinstance(raw_answer, str) and raw_answer.strip():
            fields["student_answer"] = raw_answer
    knowledge_point_ids = []
    if entry["objective_id"]:
        objective = conn.execute(
            "SELECT o.knowledge_point_id FROM review_objectives o JOIN knowledge_points k ON k.id=o.knowledge_point_id "
            "JOIN learners l ON l.curriculum_id=k.curriculum_id WHERE o.id=? AND l.id=?", (entry["objective_id"], learner_id),
        ).fetchone()
        if not objective:
            raise APIError(403, "OBJECTIVE_SCOPE_MISMATCH", "诊断目标不属于当前学习者课程")
        knowledge_point_ids = [objective[0]]
    evidence = {"source_item_id": sources[0]["item_id"] if sources else None, "sources": source_metadata,
                "knowledge_point_ids": knowledge_point_ids, "evidence_fields": [{"ref_id": key, "text": fields[key]} for key in sorted(fields)],
                "requires_review": True, "external_call": False, "mistake_content_hash": _request_hash(content)}
    evidence["snapshot_hash"] = _request_hash(evidence)
    return evidence


def _diagnosis_output(provider_result) -> dict[str, Any]:
    # Add conservative defaults without replacing validated provider evidence.
    return {"evidence_steps": [], "hypotheses": [{"text": "需要补充学生步骤后再判断", "basis": "原始证据不足"}],
            "remedy_notes": "请补充解题步骤。", **provider_result.payload,
            "diagnosis_status": "needs_review", "provider_id": provider_result.provider_id}


def _variant_snapshot(conn: sqlite3.Connection, learner_id: str, request: dict[str, Any]) -> dict[str, Any]:
    objective_id = request.get("objective_id")
    objective = conn.execute(
        "SELECT o.id FROM review_objectives o JOIN knowledge_points k ON k.id=o.knowledge_point_id "
        "JOIN learners l ON l.curriculum_id=k.curriculum_id WHERE o.id=? AND l.id=? AND l.active=1", (objective_id, learner_id),
    ).fetchone()
    if not objective:
        raise APIError(403, "OBJECTIVE_SCOPE_MISMATCH", "变式目标不属于当前学习者课程")
    source_id = request.get("source_question_version_id")
    result = {"objective_id": objective_id, "source_question_version_id": source_id}
    if source_id:
        source = conn.execute(
            "SELECT qv.*,q.objective_id,q.visibility,q.learner_id,q.approval AS question_approval "
            "FROM question_versions qv JOIN questions q ON q.id=qv.question_id WHERE qv.id=?", (source_id,),
        ).fetchone()
        if not source or (source["visibility"] != "shared" and source["learner_id"] != learner_id):
            raise APIError(404, "SOURCE_QUESTION_NOT_FOUND", "来源题目不可访问")
        if source["approval"] != "approved" or source["question_approval"] != "approved":
            raise APIError(409, "SOURCE_QUESTION_NOT_APPROVED", "来源题目尚未审核")
        if source["objective_id"] != objective_id:
            raise APIError(409, "SOURCE_OBJECTIVE_MISMATCH", "来源题目不属于请求目标")
        content = json_loads(source["content_json"], {})
        if isinstance(content, dict):
            result.update({"template_id": content.get("template_id"), "parameters": content.get("parameters"),
                           "domain": content.get("domain", "integers"), "unit": content.get("unit")})
        result["source_content_hash"] = _request_hash(dict(source))
    result["snapshot_hash"] = _request_hash(result)
    return result


def _process_variant(db: Database, job: sqlite3.Row, token: str, settings: Settings) -> dict[str, Any]:
    with db.session() as conn:
        if not conn.execute("SELECT 1 FROM jobs WHERE id=? AND status='running' AND lease_token=?", (job["id"], token)).fetchone():
            raise APIError(409, "STALE_LEASE", "任务租约已失效")
        snapshot = _variant_snapshot(conn, job["learner_id"], json_loads(job["input_json"], {}))
    provider_result = _provider_for_settings(variant_provider, settings.variant_provider, settings, db).generate(snapshot)
    return {"status": "needs_review", "provider_id": provider_result.provider_id,
            "external_call": provider_result.evidence.get("external_call", False), "payload": provider_result.payload,
            "evidence": provider_result.evidence, "approval_required": True,
            "source_snapshot_hash": snapshot["snapshot_hash"], "reason": "变式仅保存为候选，仍需人工审核"}


def _provider_for_settings(factory, provider_id: str, settings: Settings, db: Database):
    """Pass durable controls to providers; preserve existing one-argument test factories."""
    args = (provider_id, settings, UsageLedger(db, settings))
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return factory(*args)
    for length in (3, 2, 1):
        try:
            signature.bind(*args[:length])
        except TypeError:
            continue
        return factory(*args[:length])
    raise TypeError("invalid provider factory signature")


def _process_analysis(db: Database, job: sqlite3.Row, token: str, settings: Settings | None = None) -> dict[str, Any]:
    payload = json_loads(job["input_json"], {})
    batch_id = payload["batch_id"]
    settings = settings or Settings.from_env()
    provider = _provider_for_settings(document_provider, settings.document_provider, settings, db)
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
        provider_page = dict(page)
        if isinstance(provider, TencentEducationOCRProvider):
            if page["extraction_format"] in {"docx", "xlsx"}:
                # Office OOXML text is extracted locally; never transmit the
                # document container to the OCR provider.
                provider_page["image_bytes"] = None
            elif provider.is_ready and page["object_key"]:
                try:
                    provider_page["image_bytes"] = _contained_path(settings.attachment_dir, page["object_key"]).read_bytes()
                except OSError:
                    provider_page["image_bytes"] = None
        provider_result = provider.analyze_page(provider_page)
        content = {"provider_id": provider_result.provider_id, "provider_status": provider_result.status, "provider_evidence": provider_result.evidence}
        if page["extraction_format"] in {"docx", "xlsx"}:
            content.update({
                "text_status": "extracted",
                "extraction_format": page["extraction_format"],
                "document_text": page["extracted_text"] or "",
            })
            candidates = [("page:1", content)]
        elif isinstance(provider, TencentEducationOCRProvider):
            questions = provider_result.payload.get("questions", [])
            if questions:
                candidates = []
                for question_index, question in enumerate(questions, 1):
                    candidate_content = {
                        **content,
                        "ocr_status": provider_result.payload.get("ocr_status"),
                        "image_width": question.get("image_width") or provider_result.payload.get("image_width"),
                        "image_height": question.get("image_height") or provider_result.payload.get("image_height"),
                        "ocr_request_id": provider_result.payload.get("ocr_request_id"),
                        "question_text": question.get("question_text", ""),
                        "student_answer": question.get("student_answer", ""),
                        "options_text": question.get("options_text", ""),
                        "question_count_on_page": len(questions),
                        "question_index_on_page": question_index,
                        "question_candidates": [question],
                        "ocr_regions": question.get("ocr_regions", []),
                        "text_status": "recognized" if question.get("question_text") else "not_extracted",
                        "student_input_status": "recognized" if question.get("student_answer") else "not_extracted",
                        "candidate_review_required": True,
                    }
                    candidates.append((f"page:{page['page_index'] + 1}:question:{question_index}", candidate_content))
            else:
                content.update(
                    {
                        **provider_result.payload,
                        "question_text": "",
                        "student_answer": "",
                        "text_status": "provider_unavailable" if provider_result.payload.get("ocr_status") in {"not_configured", "failed"} else "not_extracted",
                        "student_input_status": "not_extracted",
                        "candidate_review_required": True,
                    }
                )
                candidates = [(f"page:{page['page_index'] + 1}:item:1", content)]
        else:
            content.update(provider_result.payload)
            candidates = [(f"page:{page['page_index'] + 1}:item:1", content)]
        # Revision is part of the occurrence identity. A page edit retains the
        # old candidate for audit, but a new analysis must create a new item.
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
            for locator, candidate_content in candidates:
                occurrence = f"{batch_id}:{page['id']}:{expected_revision}:{locator}"
                if conn.execute("SELECT 1 FROM import_items WHERE batch_id=? AND occurrence_id=?", (batch_id, occurrence)).fetchone():
                    continue
                item_id = new_id("item")
                conn.execute(
                    "INSERT INTO import_items(id,batch_id,learner_id,occurrence_id,locator,page_index,source_page_id,content_json,verdict,verification_status,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (item_id, batch_id, learner_id, occurrence, locator, page["page_index"], page["id"], json_dumps(candidate_content), "undetermined", "needs_review", "needs_review"),
                )
                regions = candidate_content.get("ocr_regions") if isinstance(candidate_content, dict) else None
                if isinstance(regions, list) and regions:
                    for bbox in regions:
                        if not isinstance(bbox, dict) or not all(isinstance(bbox.get(key), (int, float)) for key in ("x", "y", "width", "height")):
                            continue
                        conn.execute(
                            "INSERT INTO source_regions(id,item_id,source_page_id,region_type,bbox_json,coordinate_space) VALUES (?,?,?,?,?,?)",
                            (new_id("region"), item_id, page["id"], "question", json_dumps(bbox), "original"),
                        )
                else:
                    conn.execute(
                        "INSERT INTO source_regions(id,item_id,source_page_id,region_type,bbox_json,coordinate_space) VALUES (?,?,?,?,?,?)",
                        (new_id("region"), item_id, page["id"], "page", json_dumps({"x": 0, "y": 0, "width": 1, "height": 1}), "normalized"),
                    )
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
        if row["validator_version"] == "numeric-answer-v1":
            outcome = grade_numeric(row["raw_answer"], answer_key)
            feedback = answer_key.get("explanation", "")
        grade_id = new_id("grade")
        conn.execute("INSERT INTO grade_versions(id,attempt_id,outcome,score,feedback,rubric_version,validator_version,created_at) VALUES (?,?,?,?,?,?,?,?)", (grade_id, attempt_id, outcome, 1.0 if outcome == "correct" else 0.0 if outcome == "incorrect" else None, feedback, "numeric-answer-v1" if row["validator_version"] == "numeric-answer-v1" else "exact-text-v1", row["validator_version"], utc_now()))
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
