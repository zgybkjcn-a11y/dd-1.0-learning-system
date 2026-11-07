from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .secret_files import env_secret


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    attachment_dir: Path
    admin_secret: str = field(repr=False)
    adapter_secret: str = field(repr=False)
    dev_mode: bool
    max_upload_bytes: int = 25 * 1024 * 1024
    challenge_ttl_seconds: int = 300
    scheduler_version: str = "interval-v1"
    document_provider: str = "mock-document-v1"
    tencent_ocr_secret_id: str = field(default="", repr=False)
    tencent_ocr_secret_key: str = field(default="", repr=False)
    tencent_ocr_timeout_seconds: int = 20
    tencent_ocr_use_new_model: bool = True
    tencent_ocr_external_calls_enabled: bool = False
    diagnosis_provider: str = "mock-diagnosis-v1"
    variant_provider: str = "mock-variant-v1"
    export_dir: Path | None = None
    model_endpoint: str = ""
    model_allowed_endpoints: tuple[str, ...] = ()
    model_api_key: str = field(default="", repr=False)
    model_id: str = ""
    model_external_calls_enabled: bool = False
    model_timeout_seconds: int = 15
    model_max_attempts: int = 1
    model_max_input_tokens: int = 16000
    model_max_output_tokens: int = 1000
    model_input_micros_per_million: int = 0
    model_output_micros_per_million: int = 0
    tencent_ocr_cost_micros_per_call: int = 0
    provider_pricing_reference: str = ""
    provider_currency: str = "USD"
    provider_total_budget_micros: int = 0
    provider_daily_budget_micros: int = 0
    provider_max_cost_micros_per_call: int = 0
    provider_max_calls_per_day: int = 0
    provider_max_calls_per_minute: int = 0
    provider_max_inflight: int = 1
    browser_auth_enabled: bool = False
    browser_auth_secret: str = field(default="", repr=False)
    browser_auth_issuer: str = ""
    browser_auth_audience: str = "dd-learning-v1"
    browser_identity_provider: str = "open-webui"
    browser_identity_issuer: str = "open-webui"
    browser_origin: str = ""
    browser_session_ttl_seconds: int = 1800
    shared_learner_context_enabled: bool = False
    public_base_path: str = ""
    family_setup_code: str = field(default="", repr=False)
    textbook_dir: Path | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("LEARNING_DATA_DIR", "./learning_data")).resolve()
        return cls(
            data_dir=data_dir,
            db_path=Path(os.getenv("LEARNING_DB_PATH", str(data_dir / "learning.db"))).resolve(),
            attachment_dir=Path(os.getenv("LEARNING_ATTACHMENT_DIR", str(data_dir / "attachments"))).resolve(),
            admin_secret=env_secret("LEARNING_ADMIN_SECRET"),
            adapter_secret=env_secret("LEARNING_ADAPTER_SECRET"),
            dev_mode=os.getenv("LEARNING_DEV_MODE", "0").lower() in {"1", "true", "yes"},
            max_upload_bytes=int(os.getenv("LEARNING_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))),
            document_provider=os.getenv("LEARNING_DOCUMENT_PROVIDER", "mock-document-v1"),
            tencent_ocr_secret_id=env_secret("TENCENT_OCR_SECRET_ID"),
            tencent_ocr_secret_key=env_secret("TENCENT_OCR_SECRET_KEY"),
            tencent_ocr_timeout_seconds=max(1, min(60, int(os.getenv("TENCENT_OCR_TIMEOUT_SECONDS", "20")))),
            tencent_ocr_use_new_model=os.getenv("TENCENT_OCR_USE_NEW_MODEL", "1").lower() in {"1", "true", "yes"},
            tencent_ocr_external_calls_enabled=os.getenv("TENCENT_OCR_EXTERNAL_CALLS_ENABLED", "0").lower() in {"1", "true", "yes"},
            diagnosis_provider=os.getenv("LEARNING_DIAGNOSIS_PROVIDER", "mock-diagnosis-v1"),
            variant_provider=os.getenv("LEARNING_VARIANT_PROVIDER", "mock-variant-v1"),
            export_dir=Path(os.getenv("LEARNING_EXPORT_DIR", str(data_dir / "exports"))).resolve(),
            model_endpoint=os.getenv("LEARNING_MODEL_ENDPOINT", ""),
            model_allowed_endpoints=tuple(x.strip() for x in os.getenv("LEARNING_MODEL_ALLOWED_ENDPOINTS", "").split(",") if x.strip()),
            model_api_key=env_secret("LEARNING_MODEL_API_KEY"),
            model_id=os.getenv("LEARNING_MODEL_ID", ""),
            model_external_calls_enabled=os.getenv("LEARNING_MODEL_EXTERNAL_CALLS_ENABLED", "0").lower() in {"1", "true", "yes"},
            model_timeout_seconds=int(os.getenv("LEARNING_MODEL_TIMEOUT_SECONDS", "15")),
            model_max_attempts=int(os.getenv("LEARNING_MODEL_MAX_ATTEMPTS", "1")),
            model_max_input_tokens=int(os.getenv("LEARNING_MODEL_MAX_INPUT_TOKENS", "16000")),
            model_max_output_tokens=int(os.getenv("LEARNING_MODEL_MAX_OUTPUT_TOKENS", "1000")),
            model_input_micros_per_million=int(os.getenv("LEARNING_MODEL_INPUT_MICROS_PER_MILLION", "0")),
            model_output_micros_per_million=int(os.getenv("LEARNING_MODEL_OUTPUT_MICROS_PER_MILLION", "0")),
            tencent_ocr_cost_micros_per_call=int(os.getenv("TENCENT_OCR_COST_MICROS_PER_CALL", "0")),
            provider_pricing_reference=os.getenv("LEARNING_PROVIDER_PRICING_REFERENCE", ""),
            provider_currency=os.getenv("LEARNING_PROVIDER_CURRENCY", "USD"),
            provider_total_budget_micros=int(os.getenv("LEARNING_PROVIDER_TOTAL_BUDGET_MICROS", "0")),
            provider_daily_budget_micros=int(os.getenv("LEARNING_PROVIDER_DAILY_BUDGET_MICROS", "0")),
            provider_max_cost_micros_per_call=int(os.getenv("LEARNING_PROVIDER_MAX_COST_MICROS_PER_CALL", "0")),
            provider_max_calls_per_day=int(os.getenv("LEARNING_PROVIDER_MAX_CALLS_PER_DAY", "0")),
            provider_max_calls_per_minute=int(os.getenv("LEARNING_PROVIDER_MAX_CALLS_PER_MINUTE", "0")),
            provider_max_inflight=int(os.getenv("LEARNING_PROVIDER_MAX_INFLIGHT", "1")),
            browser_auth_enabled=os.getenv("LEARNING_BROWSER_AUTH_ENABLED", "0").lower() in {"1", "true", "yes"},
            browser_auth_secret=env_secret("LEARNING_BROWSER_AUTH_SECRET"),
            browser_auth_issuer=os.getenv("LEARNING_BROWSER_AUTH_ISSUER", ""),
            browser_auth_audience=os.getenv("LEARNING_BROWSER_AUTH_AUDIENCE", "dd-learning-v1"),
            browser_identity_provider=os.getenv("LEARNING_BROWSER_IDENTITY_PROVIDER", "open-webui"),
            browser_identity_issuer=os.getenv("LEARNING_BROWSER_IDENTITY_ISSUER", "open-webui"),
            browser_origin=os.getenv("LEARNING_BROWSER_ORIGIN", ""),
            browser_session_ttl_seconds=int(os.getenv("LEARNING_BROWSER_SESSION_TTL_SECONDS", "1800")),
            shared_learner_context_enabled=os.getenv("LEARNING_SHARED_LEARNER_CONTEXT_ENABLED", "0").lower() in {"1", "true", "yes"},
            public_base_path=os.getenv("LEARNING_PUBLIC_BASE_PATH", ""),
            family_setup_code=env_secret("LEARNING_FAMILY_SETUP_CODE"),
            textbook_dir=Path(os.environ["LEARNING_TEXTBOOK_DIR"]).resolve() if os.getenv("LEARNING_TEXTBOOK_DIR") else None,
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.attachment_dir.mkdir(parents=True, exist_ok=True)
        (self.export_dir or (self.data_dir / "exports")).mkdir(parents=True, exist_ok=True)
