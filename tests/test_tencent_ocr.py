from __future__ import annotations

import base64
import json

from learning_service.config import Settings
from learning_service.db import Database
from learning_service.provider_http import HTTPResult, HTTPTransport, ResponseTooLarge
from learning_service.provider_usage import UsageLedger
from learning_service.providers import TencentEducationOCRProvider, _tc3_headers


class _FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]


class _SyntheticTransport:
    evidence_mode = "synthetic_http"

    def __init__(self, callback):
        self.callback = callback

    def send(self, request, timeout, limit):
        body = self.callback(request, timeout).read(limit + 1)
        if len(body) > limit:
            raise ResponseTooLarge()
        return HTTPResult(200, body)


def _ledger(tmp_path):
    settings = Settings(tmp_path, tmp_path/"learning.db", tmp_path/"attachments", "admin", "adapter", True,
                        tencent_ocr_cost_micros_per_call=1000, provider_pricing_reference="synthetic-ocr-rates",
                        provider_total_budget_micros=10000, provider_daily_budget_micros=10000,
                        provider_max_cost_micros_per_call=1000, provider_max_calls_per_day=10,
                        provider_max_calls_per_minute=10)
    return UsageLedger(Database(settings.db_path), settings)


def _response_payload() -> bytes:
    corners = [
        {"X": 10, "Y": 20},
        {"X": 110, "Y": 20},
        {"X": 110, "Y": 70},
        {"X": 10, "Y": 70},
    ]
    return json.dumps(
        {
            "Response": {
                "RequestId": "request-123",
                "QuestionInfo": [
                    {
                        "OrgWidth": 1000,
                        "OrgHeight": 1400,
                        # Tencent may return crops here. They must never be persisted.
                        "ImageBase64": "DO-NOT-STORE-IMAGE-SENTINEL",
                        "ResultList": [
                            {
                                "Question": [{"Text": "1 + 1 = ?", "Coord": corners}],
                                "Answer": [{"Text": "2"}],
                                "Coord": [corners],
                                "RightAnswer": "2",
                                "QuestionType": "选择题",
                                "ImageBase64": "DO-NOT-STORE-CROP-SENTINEL",
                            },
                            {
                                "Question": [{"Text": "2 + 2 = ?", "Coord": corners}],
                                "Answer": [{"Text": "3"}],
                                "Coord": corners,
                                "ImageBase64": "DO-NOT-STORE-CROP-SENTINEL-2",
                            },
                        ],
                    }
                ],
            }
        }
    ).encode("utf-8")


def test_placeholder_credentials_and_disabled_egress_never_call_network(monkeypatch):
    calls = []

    def forbidden_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("network must remain disabled")

    monkeypatch.setattr(HTTPTransport, "send", forbidden_urlopen)
    placeholder = TencentEducationOCRProvider(
        "replace-with-tencent-secret-id",
        "replace-with-tencent-secret-key",
        external_calls_enabled=True,
    )
    result = placeholder.analyze_page({"id": "page-1", "image_bytes": b"synthetic"})
    assert result.payload["ocr_status"] == "not_configured"
    assert result.evidence["external_call"] is False

    disabled = TencentEducationOCRProvider(
        "real-looking-id",
        "real-looking-key",
        external_calls_enabled=False,
    )
    result = disabled.analyze_page({"id": "page-2", "image_bytes": b"synthetic"})
    assert result.payload["ocr_status"] == "external_calls_disabled"
    assert result.evidence["external_call"] is False
    assert calls == []


def test_tc3_signature_is_stable_for_fixed_request():
    payload = b'{"ImageBase64":"eA==","UseNewModel":true}'
    headers = _tc3_headers(
        "AKIDEXAMPLE",
        "test-secret-key",
        "QuestionSplitOCR",
        payload,
        timestamp=1700000000,
    )
    assert headers["Authorization"] == (
        "TC3-HMAC-SHA256 Credential=AKIDEXAMPLE/2023-11-14/ocr/tc3_request, "
        "SignedHeaders=content-type;host;x-tc-action, "
        "Signature=13c466ff4f0b74c93e8dea4f7d23041e0789e41d82b966ffce9054471ffc92a9"
    )
    assert headers["X-TC-Action"] == "QuestionSplitOCR"
    assert headers["X-TC-Version"] == "2018-11-19"


def test_synthetic_tencent_response_splits_questions_and_discards_images(monkeypatch, tmp_path):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(_response_payload())

    provider = TencentEducationOCRProvider("secret-id", "secret-key", timeout_seconds=13, external_calls_enabled=True,
                                          ledger=_ledger(tmp_path), transport=_SyntheticTransport(fake_urlopen))
    result = provider.analyze_page({"id": "page-1", "image_bytes": b"x"})

    assert result.status == "needs_review"
    assert result.evidence["external_call"] is False and result.evidence["mode"] == "synthetic_http"
    assert result.payload["ocr_status"] == "recognized"
    assert len(result.payload["questions"]) == 2
    assert [item["question_text"] for item in result.payload["questions"]] == ["1 + 1 = ?", "2 + 2 = ?"]
    assert result.payload["questions"][0]["ocr_regions"] == [
        {"x": 10.0, "y": 20.0, "width": 100.0, "height": 50.0}
    ]
    assert result.payload["questions"][1]["ocr_regions"] == [
        {"x": 10.0, "y": 20.0, "width": 100.0, "height": 50.0}
    ]
    serialized = json.dumps({"payload": result.payload, "evidence": result.evidence})
    assert "DO-NOT-STORE" not in serialized
    assert captured["url"] == "https://ocr.tencentcloudapi.com/"
    assert captured["timeout"] == 13
    assert captured["payload"] == {"ImageBase64": base64.b64encode(b"x").decode("ascii"), "UseNewModel": True}
    assert captured["headers"]["X-tc-action"] == "QuestionSplitOCR"


def test_tencent_api_error_degrades_without_persisting_free_form_message(monkeypatch, tmp_path):
    body = json.dumps(
        {"Response": {"Error": {"Code": "AuthFailure.Test", "Message": "sensitive provider detail"}, "RequestId": "req-1"}}
    ).encode("utf-8")
    provider = TencentEducationOCRProvider("secret-id", "secret-key", external_calls_enabled=True,
                                          ledger=_ledger(tmp_path), transport=_SyntheticTransport(lambda *_args: _FakeResponse(body)))
    result = provider.analyze_page({"id": "page-1", "image_bytes": b"x"})
    assert result.payload["ocr_status"] == "failed"
    assert result.payload["ocr_error_code"] == "AuthFailure.Test"
    assert "sensitive provider detail" not in json.dumps(result.payload)


def test_timeout_and_oversized_response_degrade_safely(monkeypatch, tmp_path):
    ledger = _ledger(tmp_path)

    def timeout(*_args, **_kwargs):
        raise TimeoutError("sensitive timeout details")

    provider = TencentEducationOCRProvider("secret-id", "secret-key", external_calls_enabled=True,
                                          ledger=ledger, transport=_SyntheticTransport(timeout))
    timed_out = provider.analyze_page({"id": "page-1", "image_bytes": b"x"})
    assert timed_out.payload["ocr_error_code"] == "OCR_REQUEST_FAILED"
    assert "sensitive timeout details" not in json.dumps(timed_out.payload)

    provider = TencentEducationOCRProvider("secret-id", "secret-key", external_calls_enabled=True,
                                          ledger=ledger, transport=_SyntheticTransport(lambda *_args: _FakeResponse(b"x" * (6 * 1024 * 1024 + 1))))
    oversized = provider.analyze_page({"id": "page-2", "image_bytes": b"x"})
    assert oversized.payload["ocr_error_code"] == "response_too_large"
    assert oversized.evidence["external_call"] is False
    assert oversized.evidence["mode"] == "synthetic_http"
