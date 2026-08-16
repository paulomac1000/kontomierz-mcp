"""Sanitized audit events for transport and SDK rejections before kernel invocation."""

from __future__ import annotations

import json
from typing import Literal

from .audit import configure_audit_sink

BoundaryTransport = Literal["stdio", "streamable-http"]
BoundaryStage = Literal["authentication", "routing", "protocol", "schema"]
BoundaryResult = Literal["HTTP_400", "HTTP_401", "HTTP_404", "INVALID_PARAMETER"]
BoundaryRoute = Literal["mcp", "health-ready", "unknown"]


def emit_boundary_rejection(
    *,
    transport: BoundaryTransport,
    stage: BoundaryStage,
    result: BoundaryResult,
    route: BoundaryRoute,
    authenticated: bool,
) -> None:
    """Emit one constant-shape event without paths, credentials, arguments, or bodies."""
    document = {
        "event": "mcp_boundary_rejection",
        "audit_failure_policy": "fail-open-result-preserving",
        "transport": transport,
        "stage": stage,
        "result": result,
        "route": route,
        "authenticated": authenticated,
    }
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    try:
        configure_audit_sink().info(payload)
    except Exception:
        # Invocation audit owns the stderr fallback. Boundary telemetry must never
        # replace the protocol response or turn a rejected request into a failure.
        return
