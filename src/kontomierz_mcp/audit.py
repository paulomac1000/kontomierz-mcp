"""Structured, server-side invocation audit events."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from typing import TextIO

from .errors import ErrorCode

_AUDIT_LOGGER_NAME = "kontomierz_mcp.audit"
_AUDIT_FAILURE_POLICY = "fail-open-result-preserving"
_HANDLER_MARKER = "_kontomierz_audit_handler"
_MAX_AUDIT_FIELD_BYTES = 256
_MAX_AUDIT_EVENT_BYTES = 8192
_logger = logging.getLogger(_AUDIT_LOGGER_NAME)

_TRANSPORTS = frozenset({"unresolved", "stdio", "streamable-http"})
_CAPABILITY_CLASSES = frozenset({"unresolved", "read", "write", "destructive"})
_AUTHORIZATION_DECISIONS = frozenset(
    {
        "not-evaluated",
        "denied",
        "initial:allowed",
        "initial:denied",
        "pre-io:allowed",
        "pre-io:denied",
    }
)
_OPERATOR_GATE_DECISIONS = frozenset({"not-applicable", "allowed", "denied"})
_DEPENDENCY_STATES = frozenset({"unknown", "ready", "unavailable"})
_RESULT_CATEGORIES = frozenset({"SUCCESS", *(item.value for item in ErrorCode)})


def _bounded_text(value: object, *, fallback: str = "invalid") -> str:
    """Return bounded text, replacing oversized/unexpected values with a stable digest."""
    if not isinstance(value, str):
        return fallback
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= _MAX_AUDIT_FIELD_BYTES:
        return value
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _category(value: object, allowed: frozenset[str], fallback: str) -> str:
    return value if isinstance(value, str) and value in allowed else fallback


def _canonical_bytes(document: dict[str, object]) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _fallback_audit_failure() -> None:
    """Emit a minimal operational signal without changing the invocation result."""
    try:
        sys.stderr.write('{"event":"mcp_audit_emission_failure","policy":"fail-open-result-preserving"}\n')
        sys.stderr.flush()
    except Exception:
        return


class _AuditStreamHandler(logging.StreamHandler[TextIO]):
    """Dedicated handler that makes sink failures observable without failing the tool call."""

    def handleError(self, record: logging.LogRecord) -> None:
        del record
        _fallback_audit_failure()


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
        """Return a schema-bounded event even if state was accidentally populated with unsafe values."""
        raw = asdict(self)
        raw.pop("started_at", None)
        document: dict[str, object] = {
            "request_id": _bounded_text(raw["request_id"]),
            "tool_name": _bounded_text(raw["tool_name"]),
            "principal": _bounded_text(raw["principal"]),
            "transport": _category(raw["transport"], _TRANSPORTS, "unresolved"),
            "authenticated": bool(raw["authenticated"]),
            "capability_id": _bounded_text(raw["capability_id"]),
            "capability_class": _category(raw["capability_class"], _CAPABILITY_CLASSES, "unresolved"),
            "target_identity": _bounded_text(raw["target_identity"]),
            "resource_identity": _bounded_text(raw["resource_identity"]),
            "argument_digest": _bounded_text(raw["argument_digest"]),
            "policy_version": _bounded_text(raw["policy_version"]),
            "authorization_decision": _category(
                raw["authorization_decision"], _AUTHORIZATION_DECISIONS, "not-evaluated"
            ),
            "authorization_reason": _bounded_text(raw["authorization_reason"]),
            "operator_gate_decision": _category(
                raw["operator_gate_decision"], _OPERATOR_GATE_DECISIONS, "not-applicable"
            ),
            "dependency_state": _category(raw["dependency_state"], _DEPENDENCY_STATES, "unknown"),
            "result_category": _category(raw["result_category"], _RESULT_CATEGORIES, "INTERNAL_ERROR"),
            "cancelled": bool(raw["cancelled"]),
            "saturated": bool(raw["saturated"]),
            "ambiguous": bool(raw["ambiguous"]),
            "duration_ms": max(0, int((time.monotonic() - self.started_at) * 1000)),
            "event": "mcp_tool_invocation",
            "audit_failure_policy": _AUDIT_FAILURE_POLICY,
        }
        encoded = _canonical_bytes(document)
        if len(encoded) <= _MAX_AUDIT_EVENT_BYTES:
            return document

        return {
            "event": "mcp_tool_invocation",
            "audit_failure_policy": _AUDIT_FAILURE_POLICY,
            "request_id": _bounded_text(document["request_id"]),
            "tool_name": _bounded_text(document["tool_name"]),
            "result_category": document["result_category"],
            "duration_ms": document["duration_ms"],
            "cancelled": document["cancelled"],
            "saturated": document["saturated"],
            "ambiguous": document["ambiguous"],
            "event_overflow_sha256": f"sha256:{hashlib.sha256(encoded).hexdigest()}",
        }


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
        handler = _AuditStreamHandler(stream)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))
        setattr(handler, _HANDLER_MARKER, True)
        logger.addHandler(handler)
    return logger


def emit_invocation_audit(state: InvocationAuditState) -> None:
    """Emit a stable JSON audit line without credentials or protected response bodies."""
    payload = _canonical_bytes(state.document()).decode("utf-8")
    try:
        configure_audit_sink().info(payload)
    except Exception:
        _fallback_audit_failure()
