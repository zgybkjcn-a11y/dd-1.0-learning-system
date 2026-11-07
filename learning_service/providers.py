"""Explicit provider boundaries used by durable learning jobs.

The deterministic provider is intentionally conservative: it creates a
reviewable placeholder and never claims that OCR, subject grading, or a model
call happened. Real providers can implement the same protocol when an
operator supplies credentials, an approved egress policy, and a frozen test
set.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
import time
from http.client import HTTPException
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import Request

from .config import Settings
from .provider_http import HTTPTransport, ResponseTooLarge
from .provider_usage import ProviderLimit, UsageLedger, safe_reference


@dataclass(frozen=True)
class ProviderResult:
    provider_id: str
    status: str
    payload: dict[str, Any]
    evidence: dict[str, Any]


class DocumentAnalysisProvider(Protocol):
    provider_id: str

    def analyze_page(self, page: dict[str, Any]) -> ProviderResult:
        ...


class DiagnosisProvider(Protocol):
    provider_id: str

    def diagnose(self, evidence: dict[str, Any]) -> ProviderResult:
        ...


class VariantProvider(Protocol):
    provider_id: str

    def generate(self, request: dict[str, Any]) -> ProviderResult:
        ...


class MockDocumentAnalysisProvider:
    """A deterministic offline provider for state-machine regression tests."""

    provider_id = "mock-document-v1"

    def analyze_page(self, page: dict[str, Any]) -> ProviderResult:
        return ProviderResult(
            provider_id=self.provider_id,
            status="needs_review",
            payload={
                "page_id": page["id"],
                "page_number": int(page["page_index"]) + 1,
                "text_status": "not_extracted",
                "student_input_status": "not_extracted",
                "objective_id": None,
            },
            evidence={
                "mode": "deterministic_mock",
                "ocr_performed": False,
                "reason": "真实 OCR/视觉提供商未配置",
            },
        )


class UnconfiguredProvider:
    """Provider marker used when a real external provider is requested."""

    def __init__(self, provider_id: str):
        self.provider_id = provider_id

    def analyze_page(self, page: dict[str, Any]) -> ProviderResult:
        return ProviderResult(
            provider_id=self.provider_id,
            status="needs_review",
            payload={
                "page_id": page["id"],
                "page_number": int(page["page_index"]) + 1,
                "text_status": "provider_unavailable",
                "student_input_status": "provider_unavailable",
                "objective_id": None,
            },
            evidence={
                "mode": "unconfigured",
                "ocr_performed": False,
                "reason": "provider 未配置或未获得外发授权",
            },
        )

    def diagnose(self, evidence: dict[str, Any]) -> ProviderResult:
        return ProviderResult(self.provider_id, "needs_review", {"knowledge_point_ids": [], "error_types": ["信息不足"], "needs_clarification": True}, {"mode": "unconfigured", "external_call": False})

    def generate(self, request: dict[str, Any]) -> ProviderResult:
        return ProviderResult(self.provider_id, "needs_review", {"draft": None, "approval_required": True}, {"mode": "unconfigured", "external_call": False})


_TENCENT_OCR_HOST = "ocr.tencentcloudapi.com"
_TENCENT_OCR_ACTION = "QuestionSplitOCR"
_TENCENT_OCR_VERSION = "2018-11-19"
_TENCENT_OCR_MAX_IMAGE_BYTES = 7_500_000  # Base64 must stay within Tencent's 10 MB request limit.
_TENCENT_OCR_MAX_RESPONSE_BYTES = 6 * 1024 * 1024


def _credential_is_configured(value: str) -> bool:
    value = value.strip()
    lowered = value.lower()
    return bool(value) and not any(
        marker in lowered
        for marker in ("placeholder", "replace_me", "replace_with", "replace-with", "your_secret", "<secret", "changeme")
    )


def _tc3_headers(
    secret_id: str,
    secret_key: str,
    action: str,
    payload: bytes,
    timestamp: int | None = None,
) -> dict[str, str]:
    """Build Tencent Cloud TC3-HMAC-SHA256 request headers."""
    timestamp = int(time.time()) if timestamp is None else int(timestamp)
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
    content_type = "application/json; charset=utf-8"
    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{_TENCENT_OCR_HOST}\n"
        f"x-tc-action:{action.lower()}\n"
    )
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload).hexdigest()
    canonical_request = "\n".join(
        ("POST", "/", "", canonical_headers, signed_headers, hashed_payload)
    )
    credential_scope = f"{date}/ocr/tc3_request"
    string_to_sign = "\n".join(
        (
            "TC3-HMAC-SHA256",
            str(timestamp),
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        )
    )

    def sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = sign(secret_date, "ocr")
    secret_signing = sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "Authorization": (
            f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "Content-Type": content_type,
        "Host": _TENCENT_OCR_HOST,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": _TENCENT_OCR_VERSION,
    }


def _recognized_text(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    return "\n".join(
        element["Text"].strip()
        for element in value
        if isinstance(element, dict) and isinstance(element.get("Text"), str) and element["Text"].strip()
    )


def _coordinate_point(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, dict):
        return None
    x, y = value.get("X"), value.get("Y")
    if (
        isinstance(x, (int, float)) and not isinstance(x, bool)
        and isinstance(y, (int, float)) and not isinstance(y, bool)
        and math.isfinite(x) and math.isfinite(y)
        and abs(x) <= 1_000_000 and abs(y) <= 1_000_000
    ):
        return float(x), float(y)
    return None


def _coordinate_box(value: Any) -> dict[str, float] | None:
    """Convert Tencent's four-corner coordinate object to a safe bbox."""
    points: list[tuple[float, float]] = []

    def collect(node: Any) -> None:
        point = _coordinate_point(node)
        if point is not None:
            points.append(point)
            return
        if isinstance(node, dict):
            for child in node.values():
                collect(child)
        elif isinstance(node, list):
            for child in node:
                collect(child)

    collect(value)
    if not points:
        return None
    left = min(point[0] for point in points)
    top = min(point[1] for point in points)
    right = max(point[0] for point in points)
    bottom = max(point[1] for point in points)
    return {
        "x": left,
        "y": top,
        "width": max(0.0, right - left),
        "height": max(0.0, bottom - top),
    }


def _normalized_regions(value: Any) -> list[dict[str, float]]:
    if isinstance(value, dict):
        box = _coordinate_box(value)
        return [box] if box and box["width"] > 0 and box["height"] > 0 else []
    if not isinstance(value, list):
        return []
    # Coord may be four flat corner points for one region or a list of regions.
    # Preserve pixel coordinates as returned; callers mark these as original.
    if value and all(_coordinate_point(element) is not None for element in value):
        box = _coordinate_box(value)
        return [box] if box and box["width"] > 0 and box["height"] > 0 else []
    boxes: list[dict[str, float]] = []
    for element in value:
        box = _coordinate_box(element)
        if box and box["width"] > 0 and box["height"] > 0:
            boxes.append(box)
    return boxes


def _safe_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [element.strip() for element in value if isinstance(element, str) and element.strip()]


def _safe_request_id(value: Any) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
        return value
    return None


def _sanitize_question_info(question_info: Any) -> tuple[list[dict[str, Any]], int | None, int | None]:
    """Keep reviewable OCR fields while dropping image/crop/provider payloads."""
    if isinstance(question_info, list):
        entries = question_info
    elif isinstance(question_info, dict):
        entries = [question_info]
    else:
        return [], None, None
    questions: list[dict[str, Any]] = []
    page_width = page_height = None
    for question_info_item in entries:
        if not isinstance(question_info_item, dict):
            continue
        width = question_info_item.get("OrgWidth", question_info_item.get("Width"))
        height = question_info_item.get("OrgHeight", question_info_item.get("Height"))
        width = int(width) if isinstance(width, (int, float)) and not isinstance(width, bool) and math.isfinite(width) and 0 < width <= 1_000_000 else None
        height = int(height) if isinstance(height, (int, float)) and not isinstance(height, bool) and math.isfinite(height) and 0 < height <= 1_000_000 else None
        page_width = page_width or width
        page_height = page_height or height
        result_list = question_info_item.get("ResultList")
        if not isinstance(result_list, list):
            continue
        for entry in result_list:
            if not isinstance(entry, dict):
                continue
            question_parts = entry.get("Question") if isinstance(entry.get("Question"), list) else []
            answer_parts = entry.get("Answer") if isinstance(entry.get("Answer"), list) else []
            options = entry.get("Option") if isinstance(entry.get("Option"), list) else []
            question_text = _recognized_text(question_parts)
            student_answer = _recognized_text(answer_parts)
            option_text = _recognized_text(options)
            # Preserve recognized question components useful for manual correction.
            components: list[dict[str, Any]] = []
            for field_name in ("Question", "Option", "Answer", "Figure", "Table", "Parse"):
                values = entry.get(field_name) if isinstance(entry.get(field_name), list) else []
                for component in values:
                    if not isinstance(component, dict):
                        continue
                    item: dict[str, Any] = {"kind": field_name.lower()}
                    if isinstance(component.get("Text"), str):
                        item["text"] = component["Text"]
                    if isinstance(component.get("GroupType"), str):
                        item["group_type"] = component["GroupType"]
                    for key in ("Index", "PageIndex"):
                        if isinstance(component.get(key), int):
                            item[key.lower()] = component[key]
                    regions = _normalized_regions(component.get("Coord"))
                    if regions:
                        item["regions"] = regions
                    components.append(item)
            regions = _normalized_regions(entry.get("Coord"))
            if not regions:
                for component in question_parts:
                    if isinstance(component, dict):
                        regions.extend(_normalized_regions(component.get("Coord")))
            questions.append(
                {
                    "question_index": len(questions) + 1,
                    "question_text": question_text,
                    "student_answer": student_answer,
                    "options_text": option_text,
                    "ocr_components": components,
                    "ocr_regions": regions,
                    "right_answer_candidate": (
                        entry.get("RightAnswer")
                        if isinstance(entry.get("RightAnswer"), str)
                        else _safe_text_list(entry.get("RightAnswer")) or None
                    ),
                    "question_type_candidate": entry.get("QuestionType") if isinstance(entry.get("QuestionType"), (str, int)) else None,
                    "subject_candidate": entry.get("Subject") if isinstance(entry.get("Subject"), (str, int)) else None,
                    "knowledge_point_candidates": _safe_text_list(entry.get("KnowledgePoints")),
                    "analysis_candidate": (
                        entry.get("Analysis")
                        if isinstance(entry.get("Analysis"), str)
                        else _safe_text_list(entry.get("Analysis")) or None
                    ),
                    "image_width": width,
                    "image_height": height,
                }
            )
    return questions, page_width, page_height


class TencentEducationOCRProvider:
    """Per-page Tencent education OCR; all outputs remain manual-review candidates."""

    provider_id = "tencent-education-ocr-v1"
    requires_image_bytes = True

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        timeout_seconds: int = 20,
        use_new_model: bool = True,
        external_calls_enabled: bool = False,
        ledger: UsageLedger | None = None,
        transport=None,
    ):
        self._secret_id = secret_id.strip()
        self._secret_key = secret_key.strip()
        self.timeout_seconds = max(1, min(60, int(timeout_seconds)))
        self.use_new_model = bool(use_new_model)
        self.external_calls_enabled = bool(external_calls_enabled)
        self.ledger = ledger
        self.transport = transport or HTTPTransport()

    @property
    def credentials_configured(self) -> bool:
        return all(_credential_is_configured(x) and len(x) <= 4096 and x.isascii()
                   and not any(c.isspace() for c in x) for x in (self._secret_id, self._secret_key))

    @property
    def is_ready(self) -> bool:
        return self.credentials_configured and self.external_calls_enabled

    def analyze_page(self, page: dict[str, Any]) -> ProviderResult:
        if page.get("extraction_format") in {"docx", "xlsx"}:
            return ProviderResult(
                self.provider_id,
                "needs_review",
                {"page_id": page.get("id"), "ocr_status": "local_text_extraction", "questions": []},
                {"mode": "local_office_extraction", "ocr_performed": False, "external_call": False},
            )
        if not self.credentials_configured:
            return ProviderResult(
                self.provider_id,
                "needs_review",
                {"page_id": page.get("id"), "ocr_status": "not_configured", "questions": []},
                {"mode": "unconfigured", "ocr_performed": False, "external_call": False, "reason": "腾讯 OCR 凭据未配置"},
            )
        if not self.external_calls_enabled:
            return ProviderResult(
                self.provider_id,
                "needs_review",
                {"page_id": page.get("id"), "ocr_status": "external_calls_disabled", "questions": []},
                {"mode": "egress_disabled", "ocr_performed": False, "external_call": False, "reason": "腾讯 OCR 外发开关未启用"},
            )
        image_bytes = page.get("image_bytes")
        if not isinstance(image_bytes, bytes) or not image_bytes:
            return self._failed(page, "source_image_unavailable", external_call=False)
        if len(image_bytes) > _TENCENT_OCR_MAX_IMAGE_BYTES:
            return self._failed(page, "image_exceeds_api_limit", external_call=False)
        if self.ledger is None:
            return self._failed(page, "BUDGET_NOT_CONFIGURED", external_call=False)
        try:
            call_id = self.ledger.reserve(self.provider_id, "ocr", _TENCENT_OCR_ACTION,
                                          self.ledger.settings.tencent_ocr_cost_micros_per_call,
                                          self.transport.evidence_mode)
        except ProviderLimit as exc:
            return self._failed(page, exc.code, external_call=False)

        request_payload = json.dumps(
            {
                "ImageBase64": base64.b64encode(image_bytes).decode("ascii"),
                "UseNewModel": self.use_new_model,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        headers = _tc3_headers(self._secret_id, self._secret_key, _TENCENT_OCR_ACTION, request_payload)
        request = Request(f"https://{_TENCENT_OCR_HOST}/", data=request_payload, headers=headers, method="POST")
        started = time.monotonic()
        external_call = self.transport.evidence_mode == "live_http"
        try:
            http_result = self.transport.send(request, self.timeout_seconds, _TENCENT_OCR_MAX_RESPONSE_BYTES)
            response_body = http_result.body
            decoded = json.loads(response_body.decode("utf-8"))
        except ResponseTooLarge:
            self.ledger.finish(call_id, state="unknown", error_code="response_too_large", latency_ms=int((time.monotonic() - started) * 1000))
            return self._failed(page, "response_too_large", external_call=external_call, call_id=call_id)
        except (TimeoutError, URLError, OSError, HTTPException, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            self.ledger.finish(call_id, state="unknown", error_code="OCR_REQUEST_FAILED", latency_ms=int((time.monotonic() - started) * 1000))
            return self._failed(page, "OCR_REQUEST_FAILED", external_call=external_call, call_id=call_id)

        response = decoded.get("Response") if isinstance(decoded, dict) else None
        request_id = _safe_request_id(response.get("RequestId")) if isinstance(response, dict) else None
        api_error = response.get("Error") if isinstance(response, dict) else None
        safe_code = safe_reference(api_error.get("Code")) if isinstance(api_error, dict) else None
        if http_result.status != 200 or isinstance(api_error, dict) or not isinstance(response, dict):
            safe_code = safe_code or (f"TENCENT_HTTP_{http_result.status}" if http_result.status != 200 else "INVALID_PROVIDER_RESPONSE")
            self.ledger.finish(call_id, state="failed", error_code=safe_code, request_id=request_id, latency_ms=int((time.monotonic() - started) * 1000))
            return self._failed(page, safe_code, external_call=external_call, request_id=request_id, call_id=call_id)
        self.ledger.finish(call_id, state="returned", request_id=request_id, latency_ms=int((time.monotonic() - started) * 1000))
        questions, width, height = _sanitize_question_info(response.get("QuestionInfo"))
        request_id = _safe_request_id(response.get("RequestId"))
        return ProviderResult(
            self.provider_id,
            "needs_review",
            {
                "page_id": page.get("id"),
                "ocr_status": "recognized" if questions else "no_questions_detected",
                "questions": questions,
                "image_width": width,
                "image_height": height,
                "ocr_request_id": request_id,
            },
            {
                "mode": self.transport.evidence_mode,
                "api_action": _TENCENT_OCR_ACTION,
                "ocr_performed": external_call,
                "candidate_received": True,
                "external_call": external_call,
                "call_ids": [call_id],
                "billing_status": "invoice_pending" if external_call else "synthetic_no_invoice",
                "review_required": True,
                "request_id": request_id,
                "question_count": len(questions),
            },
        )

    def _failed(self, page: dict[str, Any], code: str, external_call: bool, request_id: str | None = None, call_id: str | None = None) -> ProviderResult:
        return ProviderResult(
            self.provider_id,
            "needs_review",
            {"page_id": page.get("id"), "ocr_status": "failed", "ocr_error_code": code, "questions": []},
            {
                "mode": self.transport.evidence_mode,
                "api_action": _TENCENT_OCR_ACTION,
                "ocr_performed": False,
                "external_call": external_call,
                "review_required": True,
                "error_code": code,
                "request_id": request_id,
                "call_ids": [call_id] if call_id else [],
            },
        )


class MockDiagnosisProvider:
    provider_id = "mock-diagnosis-v1"

    def diagnose(self, evidence: dict[str, Any]) -> ProviderResult:
        return ProviderResult(
            provider_id=self.provider_id,
            status="needs_review",
            payload={"knowledge_point_ids": [], "error_types": ["信息不足"], "needs_clarification": True},
            evidence={"mode": "deterministic_mock", "source_item_id": evidence.get("source_item_id")},
        )


class MockVariantProvider:
    provider_id = "mock-variant-v1"

    def generate(self, request: dict[str, Any]) -> ProviderResult:
        return ProviderResult(
            provider_id=self.provider_id,
            status="needs_review",
            payload={"draft": None, "approval_required": True},
            evidence={"mode": "deterministic_mock", "objective_id": request.get("objective_id")},
        )


def document_provider(provider_id: str, settings: Settings | None = None, ledger: UsageLedger | None = None) -> DocumentAnalysisProvider:
    if provider_id in {"mock", "mock-document-v1"}:
        return MockDocumentAnalysisProvider()
    if provider_id in {"tencent-education-ocr-v1", "tencent-question-split-ocr-v1"}:
        settings = settings or Settings.from_env()
        return TencentEducationOCRProvider(
            settings.tencent_ocr_secret_id,
            settings.tencent_ocr_secret_key,
            settings.tencent_ocr_timeout_seconds,
            settings.tencent_ocr_use_new_model,
            settings.tencent_ocr_external_calls_enabled,
            ledger=ledger,
        )
    return UnconfiguredProvider(provider_id)


def diagnosis_provider(provider_id: str, settings: Settings | None = None, ledger: UsageLedger | None = None) -> DiagnosisProvider:
    if provider_id == "mock-diagnosis-v1":
        return MockDiagnosisProvider()
    if provider_id == "openai-compatible-diagnosis-v1":
        from .model_providers import OpenAICompatibleDiagnosisProvider
        return OpenAICompatibleDiagnosisProvider(settings or Settings.from_env(), ledger)
    return UnconfiguredProvider(provider_id)  # type: ignore[return-value]


def variant_provider(provider_id: str, settings: Settings | None = None, ledger: UsageLedger | None = None) -> VariantProvider:
    if provider_id == "mock-variant-v1":
        return MockVariantProvider()
    if provider_id == "openai-compatible-variant-v1":
        from .model_providers import OpenAICompatibleVariantProvider
        return OpenAICompatibleVariantProvider(settings or Settings.from_env(), ledger)
    return UnconfiguredProvider(provider_id)  # type: ignore[return-value]
