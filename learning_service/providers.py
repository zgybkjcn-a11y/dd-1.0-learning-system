"""Explicit provider boundaries used by durable learning jobs.

The deterministic provider is intentionally conservative: it creates a
reviewable placeholder and never claims that OCR, subject grading, or a model
call happened. Real providers can implement the same protocol when an
operator supplies credentials, an approved egress policy, and a frozen test
set.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


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


def document_provider(provider_id: str) -> DocumentAnalysisProvider:
    if provider_id in {"mock", "mock-document-v1"}:
        return MockDocumentAnalysisProvider()
    return UnconfiguredProvider(provider_id)


def diagnosis_provider(provider_id: str) -> DiagnosisProvider:
    if provider_id == "mock-diagnosis-v1":
        return MockDiagnosisProvider()
    return UnconfiguredProvider(provider_id)  # type: ignore[return-value]


def variant_provider(provider_id: str) -> VariantProvider:
    if provider_id == "mock-variant-v1":
        return MockVariantProvider()
    return UnconfiguredProvider(provider_id)  # type: ignore[return-value]
