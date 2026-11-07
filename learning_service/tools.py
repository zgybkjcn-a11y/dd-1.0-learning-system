"""
title: DD-1.0 Learning Adapter
author: DD-1.0
description: Thin adapter for the isolated DD-1.0 learning service.
required_open_webui_version: 0.12.5
version: 1.2.0

Thin Open WebUI Tools adapter.

The adapter exposes read/request actions and can start a trusted UI challenge.
It never submits a confirmation or a final answer; those remain explicit
service endpoints consumed by the trusted UI callback.
"""

from __future__ import annotations

import json
import os
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from inspect import isawaitable
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from pydantic import BaseModel


TRUSTED_UI_TIMEOUT_SECONDS = 120


class Tools:
    """Open WebUI-compatible adapter for the isolated learning API."""

    class Valves(BaseModel):
        """Operator-managed connection settings injected by Open WebUI."""

        DD_LEARNING_BASE_URL: str = "http://learning-api:31010"
        DD_LEARNING_ADAPTER_SECRET: str = ""
        DD_TRUSTED_PROVIDER: str = "open-webui"
        DD_TRUSTED_ISSUER: str = "open-webui"
        DD_TRUSTED_SUBJECT: str = ""
        DD_SHARED_LEARNER_CONTEXT: bool = True
        DD_WORKBENCH_URL: str = "https://172.19.116.53/learning/ui"

    class UserValves(BaseModel):
        """Optional per-user learner context set by the trusted host UI."""

        DD_LEARNER_ID: str = ""

    def __init__(self) -> None:
        # Open WebUI replaces this instance after loading administrator valves.
        # Environment values keep isolated local execution deterministic.
        self.valves = self.Valves(
            DD_LEARNING_BASE_URL=os.getenv("DD_LEARNING_BASE_URL", "http://learning-api:31010"),
            DD_LEARNING_ADAPTER_SECRET=os.getenv("DD_LEARNING_ADAPTER_SECRET", ""),
            DD_TRUSTED_PROVIDER=os.getenv("DD_TRUSTED_PROVIDER", "open-webui"),
            DD_TRUSTED_ISSUER=os.getenv("DD_TRUSTED_ISSUER", "open-webui"),
            DD_TRUSTED_SUBJECT=os.getenv("DD_TRUSTED_SUBJECT", ""),
            DD_WORKBENCH_URL=os.getenv("DD_WORKBENCH_URL", "https://172.19.116.53/learning/ui"),
            DD_SHARED_LEARNER_CONTEXT=os.getenv("DD_SHARED_LEARNER_CONTEXT", "true").lower() == "true",
        )
        self.account_id = os.getenv("DD_ACCOUNT_ID", "")
        self.learner_id = os.getenv("DD_LEARNER_ID", "")

    @staticmethod
    def _user_subject(user: dict[str, Any] | None) -> str:
        """Use only the server-injected Open WebUI user id as the subject."""
        if not isinstance(user, dict):
            return ""
        value = user.get("id") or user.get("user_id")
        return str(value).strip() if value is not None else ""

    @staticmethod
    def _user_learner_id(user: dict[str, Any] | None) -> str:
        if not isinstance(user, dict):
            return ""
        user_valves = user.get("valves")
        value = (
            user_valves.get("DD_LEARNER_ID")
            if isinstance(user_valves, dict)
            else getattr(user_valves, "DD_LEARNER_ID", "")
        )
        return str(value).strip() if value is not None else ""

    def _headers(self, user: dict[str, Any] | None = None) -> dict[str, str]:
        valves = self.valves
        headers = {"Accept": "application/json"}
        if valves.DD_LEARNING_ADAPTER_SECRET:
            headers["X-Adapter-Secret"] = valves.DD_LEARNING_ADAPTER_SECRET
        if self.account_id:
            headers["X-Account-Id"] = self.account_id
        learner_id = self._user_learner_id(user) or self.learner_id
        if learner_id and not valves.DD_SHARED_LEARNER_CONTEXT:
            headers["X-Learner-Id"] = learner_id
        headers.update({"X-Trusted-Provider": valves.DD_TRUSTED_PROVIDER, "X-Trusted-Issuer": valves.DD_TRUSTED_ISSUER})
        subject = self._user_subject(user) or valves.DD_TRUSTED_SUBJECT
        if subject:
            headers["X-Trusted-Subject"] = subject
        return headers

    @staticmethod
    def _segment(value: str) -> str:
        """Encode a service-owned resource identifier as one URL path segment."""
        return quote(str(value), safe="")

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        user: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> str:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = self._headers(user)
        if extra_headers:
            headers.update(extra_headers)
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(f"{str(self.valves.DD_LEARNING_BASE_URL).rstrip('/')}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310 - URL is operator configuration.
                return response.read().decode("utf-8")
        except HTTPError as exc:
            # Preserve structured API errors (for example 404/409) so the
            # caller can distinguish a rejected operation from an outage.
            try:
                response_body = exc.read().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                response_body = ""
            if response_body:
                try:
                    json.loads(response_body)
                except json.JSONDecodeError:
                    response_body = json.dumps(
                        {
                            "error": {
                                "code": "LEARNING_SERVICE_HTTP_ERROR",
                                "status": exc.code,
                                "message": response_body[:500],
                            }
                        },
                        ensure_ascii=False,
                    )
                return response_body
            return json.dumps(
                {"error": {"code": "LEARNING_SERVICE_HTTP_ERROR", "status": exc.code}},
                ensure_ascii=False,
            )
        except (URLError, TimeoutError) as exc:
            status = getattr(exc, "code", "unavailable")
            return json.dumps({"error": {"code": "LEARNING_SERVICE_UNAVAILABLE", "status": status}}, ensure_ascii=False)

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        user: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            response = json.loads(self._request(method, path, payload, user, extra_headers))
        except (TypeError, json.JSONDecodeError):
            return {"error": {"code": "LEARNING_SERVICE_INVALID_RESPONSE"}}
        if not isinstance(response, dict):
            return {"error": {"code": "LEARNING_SERVICE_INVALID_RESPONSE"}}
        return response

    @staticmethod
    def _interaction_error(code: str) -> str:
        return json.dumps({"error": {"code": code}}, ensure_ascii=False)

    @staticmethod
    def _is_service_error(response: dict[str, Any]) -> bool:
        return isinstance(response.get("error"), dict)

    @classmethod
    def _safe_service_error(cls, response: dict[str, Any]) -> str:
        if cls._is_service_error(response):
            code = response["error"].get("code")
            if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code):
                return cls._interaction_error(code)
        return cls._interaction_error("LEARNING_SERVICE_INVALID_RESPONSE")

    def _context_headers(self, user: dict[str, Any] | None) -> dict[str, Any]:
        """Pin one host identity and server selection for an entire operation."""
        headers = self._headers(user)
        if not self.valves.DD_SHARED_LEARNER_CONTEXT:
            return {"headers": headers}
        # UserValves are a consistency check, never a selection instruction.
        headers.pop("X-Learner-Id", None)
        selected = self._request_json("GET", "/api/v1/learner-context", user=user, extra_headers=headers)
        if self._is_service_error(selected):
            return selected
        learner, version = selected.get("learner_id"), selected.get("context_version")
        if not isinstance(learner, str) or not learner:
            return {"error": {"code": "LEARNER_CONTEXT_REQUIRED"}}
        if type(version) is not int or version < 1:
            return {"error": {"code": "LEARNING_SERVICE_INVALID_RESPONSE"}}
        configured = self._user_learner_id(user) or self.learner_id
        if configured and configured != learner:
            return {"error": {"code": "LEARNER_CONTEXT_CHANGED"}}
        headers.update({"X-Learner-Id": learner, "X-Learner-Context-Version": str(version)})
        return {"headers": headers}

    def _with_link(self, result: str) -> str:
        data = json.loads(result)
        # A fixed deployment input; never derive model-visible links from a
        # request, provider response, resource id, or arbitrary Host header.
        if self.valves.DD_WORKBENCH_URL == "https://172.19.116.53/learning/ui":
            data["workbench_url"] = self.valves.DD_WORKBENCH_URL
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def _fields(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
        if not isinstance(row, dict):
            return {}
        return {key: value for key in fields if key in row
                and (value := row[key]) is not None
                and (type(value) in {int, bool} or isinstance(value, str) and len(value) <= 160)}

    def _project(self, response: dict[str, Any], kind: str) -> str:
        if self._is_service_error(response):
            return self._with_link(self._safe_service_error(response))
        fields = {
            "review": ("id", "objective_id", "state", "stage", "due_at"),
            "mistakes": ("id", "objective_id", "status", "diagnosis_status"),
            "attempt": ("id", "status", "outcome", "assessment_eligibility"),
            "request": ("job_id", "diagnosis_id", "asset_id", "status", "approval_required", "static_fallback", "assistance"),
        }
        if kind == "math_reference":
            return self._project_reference(response)
        if kind == "study_support":
            return self._project_study_support(response)
        if kind == "learners":
            result = {"learner_count": len(response.get("items", [])), "selection_in_workbench": True}
        elif kind in {"review", "mistakes"}:
            result = {"items": [self._fields(row, fields[kind]) for row in response.get("items", [])[:100]]}
        elif kind == "progress":
            result = {"cards": [self._fields(row, ("state", "stage", "count")) for row in response.get("cards", [])[:100]],
                      "attempts": self._fields(response.get("attempts"), ("total", "independent", "graded"))}
        else:
            result = self._fields(response, fields[kind])
        return self._with_link(json.dumps(result, ensure_ascii=False))

    def _project_reference(self, response: dict[str, Any]) -> str:
        """Bound every nested metadata field; never forward service payloads."""
        def rows(value, limit):
            return value[:limit] if isinstance(value, list) else []
        def node(value):
            result = self._fields(value, ("id", "title", "explanation", "location_status",
                                          "depth", "from_concept", "strength", "rationale"))
            if not isinstance(value, dict):
                return result
            result.update(reference_only=True, eligible_as_grading_basis=False)
            result["checks"] = [s for s in rows(value.get("checks"), 4) if isinstance(s, str) and len(s) <= 160]
            result["pages"] = []
            for page in rows(value.get("pages"), 8):
                projected = self._fields(page, ("book_id", "chapter_id", "chapter_title", "printed_page",
                                                "pdf_page", "pdf_sha256", "label", "scope_relation"))
                book, number = projected.get("book_id"), projected.get("printed_page")
                if book not in {"math-g2-upper", "math-g7-upper"} or type(number) is not int or not 1 <= number <= 194:
                    continue
                # Do not relay an arbitrary service-supplied URL or path.
                projected["page_image_path"] = f"/api/v1/textbooks/{book}/pages/{number}/image"
                result["pages"].append(projected)
            return result
        result = self._fields(response, ("reference_version", "reference_sha256", "mapping_status",
                                         "mapped_question_count", "question_version_id", "mapping_role",
                                         "diagnosis_status", "notice"))
        result.update(reference_only=True, eligible_as_grading_basis=False, teacher_reviewed=False, mastery_claim=None)
        result["scope"] = self._fields(response.get("scope"), ("book_id", "grade", "semester", "edition", "pdf_sha256", "chapter_id"))
        result["provenance"] = self._fields(response.get("provenance"), ("structure_reference", "commit", "graph_license", "question_license"))
        result["concepts"] = [node(n) for n in rows(response.get("concepts"), 18)]
        result["prerequisites"] = [node(n) for n in rows(response.get("prerequisites"), 6)]
        result["questions"] = []
        for question in rows(response.get("questions"), 20):
            if not isinstance(question, dict):
                continue
            projected = self._fields(question, ("question_version_id", "title", "difficulty", "book_id", "chapter_id", "mapping_role"))
            projected["source"] = self._fields(question.get("source"), ("kind", "repository", "commit", "id", "attribution",
                                                                        "license", "changes", "upstream_teacher_reviewed"))
            result["questions"].append(projected)
        return self._with_link(json.dumps(result, ensure_ascii=False))

    def _reference_action(self, parameters, user):
        if any(type(value) is not str or (value and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value))
               for value in parameters.values()):
            return self._with_link(self._interaction_error("MATH_REFERENCE_SCOPE_INVALID"))
        query = urlencode({key: value for key, value in parameters.items() if value})
        path = "/api/v1/math-references" + ("?" + query if query else "")
        return self._action("GET", path, "math_reference", user=user)

    def _project_study_support(self, response):
        result = self._fields(response, ("support_version", "mapping_status", "mapped_question_count", "diagram_role", "notice"))
        result.update(reference_only=True, eligible_as_grading_basis=False, teacher_reviewed=False, mastery_claim=None)
        result["scope"] = self._fields(response.get("scope"), ("book_id", "grade", "subject", "subject_title", "title",
                                                               "semester", "edition", "chapter_id", "chapter_title"))
        steps = response.get("study_steps")
        result["study_steps"] = [self._fields(step, ("title", "prompt")) for step in steps[:4]] if isinstance(steps, list) else []
        result["provenance"] = self._fields(response.get("provenance"), ("scenario_document", "scenario_commit", "implementation"))
        # Artifacts are service-authored text, not HTML or executable code.
        # No raw upstream/provider fields enter this projection.
        for key,limit in (("diagram_mermaid", 4000), ("lesson_markdown", 12000)):
            value = response.get(key)
            if isinstance(value, str) and len(value) <= limit:
                result[key] = value
        return self._with_link(json.dumps(result, ensure_ascii=False))

    def _action(self, method, path, kind, payload=None, user=None) -> str:
        selected = self._context_headers(user)
        if self._is_service_error(selected):
            return self._with_link(self._safe_service_error(selected))
        response = self._request_json(method, path, payload, user, selected["headers"])
        changed = self._check_context(user, selected["headers"])
        return self._project(changed or response, kind)

    def _check_context(self, user, pinned_headers):
        if "X-Learner-Context-Version" not in pinned_headers:
            return None
        current = self._request_json("GET", "/api/v1/learner-context", user=user, extra_headers=pinned_headers)
        if self._is_service_error(current):
            return current
        if (current.get("learner_id") != pinned_headers["X-Learner-Id"]
                or str(current.get("context_version")) != pinned_headers["X-Learner-Context-Version"]):
            return {"error": {"code": "LEARNER_CONTEXT_CHANGED"}}
        return None

    @staticmethod
    async def _call_trusted_ui(
        callback: Callable[[dict[str, Any]], Any] | None,
        event: dict[str, Any],
    ) -> tuple[bool, Any]:
        if not callable(callback):
            return False, None
        try:
            result = callback(event)
            if isawaitable(result):
                result = await asyncio.wait_for(result, timeout=TRUSTED_UI_TIMEOUT_SECONDS)
            return True, result
        except Exception:
            return False, None

    async def _request_json_async(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        user: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="dd-learning-tool") as executor:
            return await loop.run_in_executor(
                executor,
                self._request_json,
                method,
                path,
                payload,
                user,
                extra_headers,
            )

    def list_learners(self, __user__: dict[str, Any] | None = None) -> str:
        return self._project(self._request_json("GET", "/api/v1/learners", user=__user__), "learners")

    def get_review_tasks(self, __user__: dict[str, Any] | None = None) -> str:
        return self._action("GET", "/api/v1/review-tasks", "review", user=__user__)

    def get_mistakes(self, __user__: dict[str, Any] | None = None) -> str:
        return self._action("GET", "/api/v1/mistakes", "mistakes", user=__user__)

    def get_progress(self, __user__: dict[str, Any] | None = None) -> str:
        return self._action("GET", "/api/v1/progress", "progress", user=__user__)

    def get_math_scope(self, book_id: str = "", chapter_id: str = "", __user__: dict[str, Any] | None = None) -> str:
        """List reviewed concept references in the current learner's math book; chapter is optional.

        Empty book selects the current grade's upper book. These references do
        not establish mastery, diagnose mistakes, generate or grade questions.
        """
        return self._reference_action({"book_id": book_id, "chapter_id": chapter_id}, __user__)

    def get_study_support(self, subject: str = "", book_id: str = "", chapter_id: str = "",
                          __user__: dict[str, Any] | None = None) -> str:
        """Get locally authored reading prompts and study-card Markdown for the current grade's subject.

        Supports math, chinese, english, ethics, history, geography and biology
        when present in the learner's catalogue. Nonmath output is a reading
        scaffold, not verified subject answers or a mastery assessment.
        """
        parameters = {"subject": subject, "book_id": book_id, "chapter_id": chapter_id}
        if any(type(value) is not str or (value and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value))
               for value in parameters.values()):
            return self._with_link(self._interaction_error("STUDY_SUPPORT_SCOPE_INVALID"))
        query = urlencode({key: value for key,value in parameters.items() if value})
        path = "/api/v1/study-support" + ("?" + query if query else "")
        return self._action("GET", path, "study_support", user=__user__)

    def get_math_question_reference(self, question_version_id: str, book_id: str = "", chapter_id: str = "",
                                    __user__: dict[str, Any] | None = None) -> str:
        """Recall an approved question's local concepts, prior foundations and original-page locations.

        Use a service-owned question version id. Output contains no question
        prompt or answer key; view and answer the question in the workbench.
        """
        if not question_version_id:
            return self._with_link(self._interaction_error("MATH_REFERENCE_SCOPE_INVALID"))
        return self._reference_action({"book_id": book_id, "chapter_id": chapter_id,
                                       "question_version_id": question_version_id}, __user__)

    def get_math_concept_reference(self, concept_id: str, book_id: str = "", chapter_id: str = "",
                                   __user__: dict[str, Any] | None = None) -> str:
        """Read one mapped concept's local explanation, possible checks and bounded prerequisite references.

        Use a concept id from get_math_scope. Possible checks are reflection
        prompts; they are not confirmed causes of a student's mistake.
        """
        if not concept_id:
            return self._with_link(self._interaction_error("MATH_REFERENCE_SCOPE_INVALID"))
        return self._reference_action({"book_id": book_id, "chapter_id": chapter_id, "concept_id": concept_id}, __user__)

    def get_attempt(self, attempt_id: str, __user__: dict[str, Any] | None = None) -> str:
        return self._action("GET", f"/api/v1/attempts/{self._segment(attempt_id)}", "attempt", user=__user__)

    def request_document_analysis(self, batch_id: str, __user__: dict[str, Any] | None = None) -> str:
        return self._action("POST", f"/api/v1/import-batches/{self._segment(batch_id)}/analysis", "request", user=__user__)

    def request_diagnosis(self, mistake_id: str, __user__: dict[str, Any] | None = None) -> str:
        return self._action("POST", f"/api/v1/mistakes/{self._segment(mistake_id)}/diagnoses", "request", {}, user=__user__)

    def request_variant(
        self,
        objective_id: str,
        source_question_version_id: str = "",
        __user__: dict[str, Any] | None = None,
    ) -> str:
        payload = {"objective_id": objective_id}
        if source_question_version_id:
            payload["source_question_version_id"] = source_question_version_id
        return self._action("POST", "/api/v1/variant-jobs", "request", payload, user=__user__)

    def request_hint(self, test_item_id: str, __user__: dict[str, Any] | None = None) -> str:
        return self._action("POST", f"/api/v1/test-items/{self._segment(test_item_id)}/hints", "request", user=__user__)

    def request_visual(
        self,
        start: int,
        subtrahend: int,
        objective_id: str = "",
        __user__: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {"template_id": "signed_number_subtraction", "parameters": {"start": start, "subtrahend": subtrahend}, "purpose": "teach"}
        if objective_id:
            payload["objective_id"] = objective_id
        return self._action("POST", "/api/v1/visual-jobs", "request", payload, user=__user__)

    async def start_trusted_interaction(
        self,
        operation: str,
        resource_id: str,
        items: list[dict[str, Any]] | None = None,
        __user__: dict[str, Any] | None = None,
        __event_call__: Callable[[dict[str, Any]], Any] | None = None,
    ) -> str:
        """Ask the trusted native UI to confirm or answer for the current learner."""
        return self._with_link(await self._start_trusted_interaction(
            operation, resource_id, items, __user__, __event_call__))

    async def _start_trusted_interaction(
        self,
        operation: str,
        resource_id: str,
        items: list[dict[str, Any]] | None = None,
        __user__: dict[str, Any] | None = None,
        __event_call__: Callable[[dict[str, Any]], Any] | None = None,
    ) -> str:
        """Use Open WebUI's trusted native callback for final confirmations and answers."""
        allowed = {
            "confirm_import",
            "confirm_learning",
            "confirm_draft_interactively",
            "submit_answer",
        }
        if operation not in allowed:
            return json.dumps(
                {"error": {"code": "INTERACTION_OPERATION_FORBIDDEN", "message": "可信交互操作不在允许清单"}},
                ensure_ascii=False,
            )
        if not isinstance(resource_id, str) or not resource_id.strip():
            return json.dumps(
                {"error": {"code": "INTERACTION_RESOURCE_REQUIRED", "message": "可信交互缺少资源标识"}},
                ensure_ascii=False,
            )
        if not callable(__event_call__):
            return self._interaction_error("TRUSTED_UI_CALLBACK_REQUIRED")

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="dd-learning-context") as executor:
            selected_context = await loop.run_in_executor(executor, self._context_headers, __user__)
        if self._is_service_error(selected_context):
            return self._safe_service_error(selected_context)
        pinned_headers = selected_context["headers"]

        async def scoped_request(method, path, payload=None, user=None, extra_headers=None):
            response = await self._request_json_async(method, path, payload, user,
                                                     {**pinned_headers, **(extra_headers or {})})
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="dd-learning-context") as executor:
                changed = await loop.run_in_executor(executor, self._check_context, user, pinned_headers)
            return changed or response

        operation = "confirm_learning" if operation == "confirm_draft_interactively" else operation
        resource_path = self._segment(resource_id)
        selected: list[dict[str, Any]] = []
        confirmation_message = ""

        if operation == "confirm_import":
            if not isinstance(items, list) or not items or len(items) > 100:
                return self._interaction_error("TRUSTED_UI_INPUT_INVALID")
            selected_by_id: dict[str, int] = {}
            for candidate in items:
                if not isinstance(candidate, dict):
                    return self._interaction_error("TRUSTED_UI_INPUT_INVALID")
                item_id = candidate.get("item_id")
                revision = candidate.get("expected_revision")
                if not isinstance(item_id, str) or not item_id.strip() or type(revision) is not int or revision < 1:
                    return self._interaction_error("TRUSTED_UI_INPUT_INVALID")
                if item_id in selected_by_id:
                    return self._interaction_error("TRUSTED_UI_INPUT_INVALID")
                selected_by_id[item_id] = revision

            batch_snapshot = await scoped_request(
                "GET", f"/api/v1/import-batches/{resource_path}", user=__user__
            )
            if self._is_service_error(batch_snapshot):
                return self._safe_service_error(batch_snapshot)
            if (
                not isinstance(batch_snapshot.get("revision"), int)
                or batch_snapshot.get("status") not in {"awaiting_review", "partial_failed"}
                or batch_snapshot.get("failed_pages", 0) != 0
            ):
                return self._interaction_error("TRUSTED_UI_RESOURCE_NOT_REVIEWED")
            response = await scoped_request(
                "GET", f"/api/v1/import-batches/{resource_path}/items", user=__user__
            )
            if self._is_service_error(response):
                return self._safe_service_error(response)
            rows = response.get("items")
            if not isinstance(rows, list):
                return self._interaction_error("LEARNING_SERVICE_INVALID_RESPONSE")
            by_id = {row.get("id"): row for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)}
            for item_id, revision in selected_by_id.items():
                row = by_id.get(item_id)
                if not row or type(row.get("revision")) is not int or row["revision"] != revision:
                    return self._interaction_error("TRUSTED_UI_RESOURCE_CHANGED")
                if row.get("status") != "ready" or row.get("verification_status") != "manual":
                    return self._interaction_error("TRUSTED_UI_RESOURCE_NOT_REVIEWED")
                selected.append({"item_id": item_id, "expected_revision": revision})
            confirmation_message = "请核对以下候选题及原作答、判定证据；确认后将按当前版本写入学习记录：\n\n" + "\n\n".join(
                self._format_import_item(by_id[item_id]) for item_id in selected_by_id
            )
        elif operation == "confirm_learning":
            response = await scoped_request(
                "GET", f"/api/v1/learning-drafts/{resource_path}", user=__user__
            )
            if self._is_service_error(response):
                return self._safe_service_error(response)
            content = response.get("content")
            if not isinstance(content, dict) or response.get("id") != resource_id:
                return self._interaction_error("LEARNING_SERVICE_INVALID_RESPONSE")
            confirmation_message = "请确认将以下学习记录保存到当前学习者的复习计划：\n\n" + json.dumps(
                content, ensure_ascii=False, indent=2
            )
        else:
            response = await scoped_request(
                "GET", f"/api/v1/test-items/{resource_path}", user=__user__
            )
            if self._is_service_error(response):
                return self._safe_service_error(response)
            if response.get("test_item_id") != resource_id or not isinstance(response.get("prompt"), str):
                return self._interaction_error("LEARNING_SERVICE_INVALID_RESPONSE")
            answer_available, answer = await self._call_trusted_ui(
                __event_call__,
                {
                    "type": "input",
                    "data": {
                        "title": "提交测验答案",
                        "message": response["prompt"],
                        "placeholder": "输入你的答案",
                        "tool_call": True,
                        "timeout_ms": TRUSTED_UI_TIMEOUT_SECONDS * 1000,
                    },
                },
            )
            if (
                not answer_available
                or isinstance(answer, dict) and "error" in answer
                or answer is None
                or answer is False
            ):
                return self._interaction_error("TRUSTED_UI_NOT_CONFIRMED")
            if not isinstance(answer, str) or not answer.strip() or len(answer) > 10000:
                return self._interaction_error("TRUSTED_UI_INPUT_INVALID")
            challenge = await scoped_request(
                "POST", f"/api/v1/test-items/{resource_path}/submission-challenges", user=__user__
            )
            if self._is_service_error(challenge):
                return self._safe_service_error(challenge)
            if not self._valid_challenge(challenge, "submit_answer", resource_id):
                return self._interaction_error("LEARNING_SERVICE_INVALID_RESPONSE")
            submitted = await scoped_request(
                "POST",
                f"/api/v1/test-items/{resource_path}/answers",
                {"challenge_id": challenge["challenge_id"], "nonce": challenge["nonce"], "raw_answer": answer},
                user=__user__,
                extra_headers={"Idempotency-Key": uuid4().hex},
            )
            if self._is_service_error(submitted):
                return self._safe_service_error(submitted)
            if not isinstance(submitted.get("attempt_id"), str) or not isinstance(submitted.get("status"), str):
                return self._interaction_error("LEARNING_SERVICE_INVALID_RESPONSE")
            return json.dumps(
                {
                    "status": submitted["status"],
                    "attempt_id": submitted["attempt_id"],
                    "assessment_eligibility": submitted.get("assessment_eligibility") is True,
                },
                ensure_ascii=False,
            )

        event_available, decision = await self._call_trusted_ui(
            __event_call__,
            {
                "type": "confirmation",
                "data": {
                    "title": "确认学习操作",
                    "message": confirmation_message,
                    "confirm_label": "确认",
                    "cancel_label": "取消",
                    "tool_call": True,
                    "timeout_ms": TRUSTED_UI_TIMEOUT_SECONDS * 1000,
                },
            },
        )
        if not event_available or decision is not True:
            return self._interaction_error("TRUSTED_UI_NOT_CONFIRMED")

        if operation == "confirm_import":
            challenge_payload = {"items": selected}
            challenge_payload["expected_batch_revision"] = batch_snapshot["revision"]
            challenge_path = f"/api/v1/import-batches/{resource_path}/confirmation-challenges"
            submit_path = f"/api/v1/import-batches/{resource_path}/confirmations"
            submit_payload_key = "items"
        else:
            challenge_payload = None
            challenge_path = f"/api/v1/learning-drafts/{resource_path}/confirmation-challenges"
            submit_path = f"/api/v1/learning-drafts/{resource_path}/confirmations"
            submit_payload_key = "raw_content"

        challenge = await scoped_request(
            "POST", challenge_path, challenge_payload, user=__user__
        )
        if self._is_service_error(challenge):
            return self._safe_service_error(challenge)
        if not self._valid_challenge(challenge, operation, resource_id):
            return self._interaction_error("LEARNING_SERVICE_INVALID_RESPONSE")
        payload: dict[str, Any] = {
            "challenge_id": challenge["challenge_id"],
            "nonce": challenge["nonce"],
        }
        if operation == "confirm_import":
            payload[submit_payload_key] = selected
        else:
            payload[submit_payload_key] = response["content"]
        submitted = await scoped_request(
            "POST",
            submit_path,
            payload,
            user=__user__,
            extra_headers={"Idempotency-Key": uuid4().hex},
        )
        if self._is_service_error(submitted):
            return self._safe_service_error(submitted)
        if operation == "confirm_import":
            if not isinstance(submitted.get("status"), str) or type(submitted.get("confirmed_count")) is not int:
                return self._interaction_error("LEARNING_SERVICE_INVALID_RESPONSE")
            safe_result = {
                "status": submitted["status"],
                "selected_count": len(selected),
                "confirmed_count": submitted["confirmed_count"],
            }
        else:
            if submitted.get("status") != "confirmed" or not isinstance(submitted.get("draft_id"), str):
                return self._interaction_error("LEARNING_SERVICE_INVALID_RESPONSE")
            safe_result = {"status": "confirmed", "draft_id": submitted["draft_id"]}
            if isinstance(submitted.get("card_id"), str):
                safe_result["card_id"] = submitted["card_id"]
        return json.dumps(safe_result, ensure_ascii=False)

    @staticmethod
    def _valid_challenge(response: dict[str, Any], operation: str, resource_id: str) -> bool:
        return (
            response.get("operation") == operation
            and response.get("resource_id") == resource_id
            and isinstance(response.get("challenge_id"), str)
            and bool(response["challenge_id"])
            and isinstance(response.get("nonce"), str)
            and bool(response["nonce"])
        )

    @staticmethod
    def _format_import_item(item: dict[str, Any]) -> str:
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        evidence = item.get("teacher_evidence") if isinstance(item.get("teacher_evidence"), dict) else {}
        return "\n".join(
            (
                f"题号/位置：{item.get('locator', '未标注')}",
                f"题目：{content.get('prompt', content.get('question', '（无识别题面）'))}",
                f"学生原作答：{item.get('raw_answer') or '（空白）'}",
                f"判定：{item.get('verdict', 'undetermined')}",
                "判定证据：" + json.dumps(evidence, ensure_ascii=False),
                f"修订版本：{item.get('revision')}",
            )
        )
