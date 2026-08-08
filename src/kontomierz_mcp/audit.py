"""Structured, server-side invocation audit events."""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from typing import TextIO

_AUDIT_LOGGER_NAME = "kontomierz_mcp.audit"
_AUDIT_FAILURE_POLICY = "fail-open-result-preserving"
_HANDLER_MARKER = "_kontomierz_audit_handler"
_logger = logging.getLogger(_AUDIT_LOGGER_NAME)


@dataclass(slots=True)
class InvocationAuditState:
    """Mutable state used to emit exactly one bounded audit event per invocation."""

    request_id: str
    tool_name: str
    started_at: float
    principal: str = "unresolved"
    transport: str = "unresolved"
    authenticated: bool = False
    capability_id: str = "unresolved"
    capability_class: str = "unresolved"
    target_identity: str = "unresolved"
    resource_identity: str = "unresolved"
    argument_digest: str = "unresolved"
    policy_version: str = "unresolved"
    authorization_decision: str = "not-evaluated"
    authorization_reason: str = "not-evaluated"
    operator_gate_decision: str = "not-applicable"
    dependency_state: str = "unknown"
    result_category: str = "INTERNAL_ERROR"
    cancelled: bool = False
    saturated: bool = False
    ambiguous: bool = False

    def document(self) -> dict[str, object]:
        document = asdict(self)
        document.pop("started_at", None)
        document["duration_ms"] = int((time.monotonic() - self.started_at) * 1000)
        document["event"] = "mcp_tool_invocation"
        document["audit_failure_policy"] = _AUDIT_FAILURE_POLICY
        return document


def configure_audit_sink(*, stream: TextIO | None = None, replace: bool = False) -> logging.Logger:
    """Configure an audit-only INFO sink that is independent from application verbosity."""
    logger = logging.getLogger(_AUDIT_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    existing = [handler for handler in logger.handlers if getattr(handler, _HANDLER_MARKER, False)]
    if replace:
        for handler in existing:
            logger.removeHandler(handler)
        existing = []
    if not existing:
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))
        setattr(handler, _HANDLER_MARKER, True)
        logger.addHandler(handler)
    return logger


def _fallback_audit_failure() -> None:
    """Emit a minimal operational signal without changing the invocation result."""
    try:
        sys.stderr.write(
            '{"event":"mcp_audit_emission_failure","policy":"fail-open-result-preserving"}\n'
        )
        sys.stderr.flush()
    except Exception:
        return


def emit_invocation_audit(state: InvocationAuditState) -> None:
    """Emit a stable JSON audit line without credentials or protected response bodies."""
    payload = json.dumps(state.document(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    try:
        configure_audit_sink().info(payload)
    except Exception:
        _fallback_audit_failure()
