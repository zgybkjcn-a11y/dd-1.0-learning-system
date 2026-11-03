"""
title: DD-1.0 Learning Adapter
author: DD-1.0
description: Thin adapter for the isolated DD-1.0 learning service.
required_open_webui_version: 0.12.5
version: 1.0.0

Thin Open WebUI Tools adapter.

The adapter exposes read/request actions and can start a trusted UI challenge.
It never submits a confirmation or a final answer; those remain explicit
service endpoints consumed by the trusted UI callback.
"""

from __future__ import annotations

import json
import os
import asyncio
from inspect import isawaitable
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
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
        if learner_id:
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
            if isinstance(code, str) and code:
                return cls._interaction_error(code)
        return cls._interaction_error("LEARNING_SERVICE_INVALID_RESPONSE")

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
        return await asyncio.to_thread(self._request_json, method, path, payload, user, extra_headers)

    def list_learners(self, __user__: dict[str, Any] | None = None) -> str:
        return self._request("GET", "/api/v1/learners", user=__user__)

    def get_review_tasks(self, __user__: dict[str, Any] | None = None) -> str:
        return self._request("GET", "/api/v1/review-tasks", user=__user__)

    def get_mistakes(self, __user__: dict[str, Any] | None = None) -> str:
        return self._request("GET", "/api/v1/mistakes", user=__user__)

    def get_progress(self, __user__: dict[str, Any] | None = None) -> str:
        return self._request("GET", "/api/v1/progress", user=__user__)

    def get_attempt(self, attempt_id: str, __user__: dict[str, Any] | None = None) -> str:
        return self._request("GET", f"/api/v1/attempts/{self._segment(attempt_id)}", user=__user__)

    def request_document_analysis(self, batch_id: str, __user__: dict[str, Any] | None = None) -> str:
        return self._request("POST", f"/api/v1/import-batches/{self._segment(batch_id)}/analysis", user=__user__)

    def request_diagnosis(self, mistake_id: str, __user__: dict[str, Any] | None = None) -> str:
        return self._request("POST", f"/api/v1/mistakes/{self._segment(mistake_id)}/diagnoses", {}, user=__user__)

    def request_variant(
        self,
        objective_id: str,
        source_question_version_id: str = "",
        __user__: dict[str, Any] | None = None,
    ) -> str:
        payload = {"objective_id": objective_id}
        if source_question_version_id:
            payload["source_question_version_id"] = source_question_version_id
        return self._request("POST", "/api/v1/variant-jobs", payload, user=__user__)

    def request_hint(self, test_item_id: str, __user__: dict[str, Any] | None = None) -> str:
        return self._request("POST", f"/api/v1/test-items/{self._segment(test_item_id)}/hints", user=__user__)

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
        return self._request("POST", "/api/v1/visual-jobs", payload, user=__user__)

    async def start_trusted_interaction(
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

            batch_snapshot = await self._request_json_async(
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
            response = await self._request_json_async(
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
            response = await self._request_json_async(
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
            response = await self._request_json_async(
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
            challenge = await self._request_json_async(
                "POST", f"/api/v1/test-items/{resource_path}/submission-challenges", user=__user__
            )
            if self._is_service_error(challenge):
                return self._safe_service_error(challenge)
            if not self._valid_challenge(challenge, "submit_answer", resource_id):
                return self._interaction_error("LEARNING_SERVICE_INVALID_RESPONSE")
            submitted = await self._request_json_async(
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

        challenge = await self._request_json_async(
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
        submitted = await self._request_json_async(
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
