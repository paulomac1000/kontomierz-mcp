"""Structured, server-side invocation audit events."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass
from typing import TextIO

from .errors import ErrorCode
from .manifests import TOOL_MANIFESTS

_AUDIT_LOGGER_NAME = "kontomierz_mcp.audit"
_AUDIT_FAILURE_POLICY = "fail-open-result-preserving"
_HANDLER_MARKER = "_kontomierz_audit_handler"
_MAX_AUDIT_FIELD_BYTES = 256
_MAX_AUDIT_EVENT_BYTES = 8192
_REDACTED = "redacted"
_logger = logging.getLogger(_AUDIT_LOGGER_NAME)

_TRANSPORTS = frozenset({"unresolved", "stdio", "streamable-http"})
_CAPABILITY_CLASSES = frozenset({"unresolved", "read", "write", "destructive"})
_TOOL_IDS = frozenset({"unresolved", *TOOL_MANIFESTS})
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
_AUTHORIZATION_REASONS = frozenset(
    {
        "not-evaluated",
        "principal is not authenticated",
        "capability has no governed resource binding",
        "principal transport does not match the active deployment transport",
        "HTTP principal is not bound to this deployment",
        "capability class read is not allowed for the HTTP principal",
        "capability class write is not allowed for the HTTP principal",
        "capability class destructive is not allowed for the HTTP principal",
        "destructive capability is not explicitly allowlisted for the HTTP principal",
        "principal and exact capability are authorized",
        "stdio principal is not process-derived",
        "destructive capability is not explicitly allowlisted for the stdio principal",
        "local process principal and exact capability are authorized",
        "destructive resource is not explicitly allowlisted for the HTTP principal",
        "destructive resource is not explicitly allowlisted for the stdio principal",
        "principal, capability, target, and exact resource are authorized",
        "authorization binding changed before I/O",
        "server-verified approval authority is not configured",
    }
)
_OPERATOR_GATE_DECISIONS = frozenset({"not-applicable", "allowed", "denied"})
_DEPENDENCY_STATES = frozenset({"unknown", "ready", "unavailable"})
_RESULT_CATEGORIES = frozenset({"SUCCESS", *(item.value for item in ErrorCode)})
_REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")
_LOCAL_PRINCIPAL = re.compile(r"^local-process:(?:uid|pid):[0-9]+$")
_ARGUMENT_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_POLICY_VERSION = re.compile(r"^single-account-resource-v[0-9]+$")
_RESOURCE_IDENTITY = re.compile(
    r"^(?:server:catalog|"
    r"(?:account|wallet|transaction|category|tag|currency|budget|schedule|chart|wealth|capability):"
    r"(?:collection|new|unresolved|[1-9][0-9]*)|"
    r"transaction:new:client-assigned-sha256:[0-9a-f]{16})$"
)
_SAFE_TARGET_IDENTITIES = frozenset({"unresolved", "kontomierz:mock-account", "kontomierz-mcp:local-process"})


def _bounded_text(value: object, *, fallback: str = "invalid") -> str:
    """Return bounded text, replacing oversized/unexpected values with a stable digest."""
    if not isinstance(value, str):
        return fallback
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= _MAX_AUDIT_FIELD_BYTES:
        return value
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _digest_text(value: object, *, fallback: str = _REDACTED) -> str:
    """Return only a digest for arbitrary text so no protected prefix survives."""
    if not isinstance(value, str):
        return fallback
    return f"sha256:{hashlib.sha256(value.encode('utf-8', errors='replace')).hexdigest()}"


def _allowlisted(value: object, allowed: frozenset[str], *, fallback: str = _REDACTED) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    return _digest_text(value, fallback=fallback)


def _pattern_or_digest(value: object, pattern: re.Pattern[str], *, fallback: str = _REDACTED) -> str:
    if isinstance(value, str) and pattern.fullmatch(value):
        return value
    return _digest_text(value, fallback=fallback)


def _safe_principal(value: object) -> str:
    if value in {"unresolved", "unbound-http-principal"}:
        return str(value)
    if isinstance(value, str) and _LOCAL_PRINCIPAL.fullmatch(value):
        return value
    return _digest_text(value)


def _safe_target_identity(value: object) -> str:
    return _allowlisted(value, _SAFE_TARGET_IDENTITIES)


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
        request_id = raw["request_id"]
        request_id_text = (
            request_id
            if isinstance(request_id, str) and _REQUEST_ID.fullmatch(request_id)
            else _digest_text(request_id)
        )
        document: dict[str, object] = {
            "request_id": request_id_text,
            "tool_name": _allowlisted(raw["tool_name"], _TOOL_IDS),
            "principal": _safe_principal(raw["principal"]),
            "transport": _category(raw["transport"], _TRANSPORTS, "unresolved"),
            "authenticated": bool(raw["authenticated"]),
            "capability_id": _allowlisted(raw["capability_id"], _TOOL_IDS),
            "capability_class": _category(raw["capability_class"], _CAPABILITY_CLASSES, "unresolved"),
            "target_identity": _safe_target_identity(raw["target_identity"]),
            "resource_identity": _pattern_or_digest(raw["resource_identity"], _RESOURCE_IDENTITY),
            "argument_digest": (
                "unresolved"
                if raw["argument_digest"] == "unresolved"
                else _pattern_or_digest(raw["argument_digest"], _ARGUMENT_DIGEST)
            ),
            "policy_version": (
                "unresolved"
                if raw["policy_version"] == "unresolved"
                else _pattern_or_digest(raw["policy_version"], _POLICY_VERSION)
            ),
            "authorization_decision": _category(
                raw["authorization_decision"], _AUTHORIZATION_DECISIONS, "not-evaluated"
            ),
            "authorization_reason": _allowlisted(raw["authorization_reason"], _AUTHORIZATION_REASONS),
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
