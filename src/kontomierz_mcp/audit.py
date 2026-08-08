"""Structured, server-side invocation audit events."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass

_logger = logging.getLogger("kontomierz_mcp.audit")


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
        return document


def emit_invocation_audit(state: InvocationAuditState) -> None:
    """Emit a stable JSON audit line without credentials or protected response bodies."""
    _logger.info(json.dumps(state.document(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
