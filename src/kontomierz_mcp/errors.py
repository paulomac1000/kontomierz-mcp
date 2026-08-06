"""Application-owned error taxonomy and safe public serialization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    INVALID_PARAMETER = "INVALID_PARAMETER"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    UPSTREAM_FAILURE = "UPSTREAM_FAILURE"
    AMBIGUOUS_OUTCOME = "AMBIGUOUS_OUTCOME"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(slots=True)
class ApplicationError(Exception):
    """A bounded error that may be exposed to an MCP client."""

    code: ErrorCode
    message: str
    retryable: bool = False
    suggestion: str | None = None
    details: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.suggestion:
            result["suggestion"] = self.suggestion
        if self.details:
            result["details"] = self.details
        return result

    def __str__(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, separators=(",", ":"))


@dataclass(slots=True)
class UpstreamError(ApplicationError):
    """A dependency failure with an explicit write-outcome classification."""

    write_outcome_ambiguous: bool = False
