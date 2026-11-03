from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    attachment_dir: Path
    admin_secret: str
    adapter_secret: str
    dev_mode: bool
    max_upload_bytes: int = 25 * 1024 * 1024
    challenge_ttl_seconds: int = 300
    scheduler_version: str = "interval-v1"
    document_provider: str = "mock-document-v1"
    diagnosis_provider: str = "mock-diagnosis-v1"
    variant_provider: str = "mock-variant-v1"
    export_dir: Path | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("LEARNING_DATA_DIR", "./learning_data")).resolve()
        return cls(
            data_dir=data_dir,
            db_path=Path(os.getenv("LEARNING_DB_PATH", str(data_dir / "learning.db"))).resolve(),
            attachment_dir=Path(os.getenv("LEARNING_ATTACHMENT_DIR", str(data_dir / "attachments"))).resolve(),
            admin_secret=os.getenv("LEARNING_ADMIN_SECRET", ""),
            adapter_secret=os.getenv("LEARNING_ADAPTER_SECRET", ""),
            dev_mode=os.getenv("LEARNING_DEV_MODE", "0").lower() in {"1", "true", "yes"},
            max_upload_bytes=int(os.getenv("LEARNING_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))),
            document_provider=os.getenv("LEARNING_DOCUMENT_PROVIDER", "mock-document-v1"),
            diagnosis_provider=os.getenv("LEARNING_DIAGNOSIS_PROVIDER", "mock-diagnosis-v1"),
            variant_provider=os.getenv("LEARNING_VARIANT_PROVIDER", "mock-variant-v1"),
            export_dir=Path(os.getenv("LEARNING_EXPORT_DIR", str(data_dir / "exports"))).resolve(),
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.attachment_dir.mkdir(parents=True, exist_ok=True)
        (self.export_dir or (self.data_dir / "exports")).mkdir(parents=True, exist_ok=True)
