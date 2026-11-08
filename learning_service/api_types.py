"""Shared API identity and errors; importing this module creates no application."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel


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
