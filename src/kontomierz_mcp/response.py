"""Response formatting helpers for all MCP tools — Canonical Template 4/4a/4b/4c."""

import contextvars
import json
import logging
import re
import threading
import time
import uuid
from collections import defaultdict
from typing import Any

from .tools.constants import TOOLS_VERSION

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_invocation_counts: dict[str, int] = defaultdict(int)
_counter_lock = threading.Lock()

_SENSITIVE_PATTERNS = [
    (r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer <REDACTED>"),
    (r"api_key=[^\s&]+", "api_key=<REDACTED>"),
    (
        r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        "<IP_REDACTED>",
    ),
    (r"KONTOMIERZ_API_KEY[=:]\s*[^\s]+", "KONTOMIERZ_API_KEY=<REDACTED>"),
]


def sanitize_log_line(line: str) -> str:
    for pattern, replacement in _SENSITIVE_PATTERNS:
        line = re.sub(pattern, replacement, line, flags=re.IGNORECASE)
    return line


def sanitize_response_data(data: object) -> object:
    """Recursively sanitize sensitive data from response payloads (Template 4b)."""
    if isinstance(data, str):
        return sanitize_log_line(data)
    if isinstance(data, dict):
        return {k: sanitize_response_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_response_data(item) for item in data]
    return data


class RequestIdFilter(logging.Filter):
    """Inject request_id into every log record (Template 4a)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get("-")
        return True


class SanitizingFormatter(logging.Formatter):
    """Sanitize sensitive data from log output (Template 4a)."""

    def format(self, record: logging.LogRecord) -> str:
        return sanitize_log_line(super().format(record))


def set_request_id(value: str) -> None:
    _request_id.set(value)


def get_request_id() -> str:
    return _request_id.get()


def start_tool_context() -> str:
    rid = str(uuid.uuid4())
    _request_id.set(rid)
    return rid


def record_invocation(tool_name: str) -> None:
    with _counter_lock:
        _invocation_counts[tool_name] += 1


def get_invocation_counts() -> dict[str, int]:
    with _counter_lock:
        return dict(_invocation_counts)


def build_meta(tool_name: str, start_time: float) -> dict[str, Any]:
    record_invocation(tool_name)
    return {
        "request_id": get_request_id(),
        "duration_ms": int((time.monotonic() - start_time) * 1000),
        "tool_version": TOOLS_VERSION,
    }


def success_response(data: Any, _meta: dict[str, Any] | None = None) -> str:
    response: dict[str, Any] = {"success": True, "data": sanitize_response_data(data)}
    if _meta is not None:
        response["_meta"] = _meta
    return json.dumps(response)


def error_response(message: str) -> str:
    return json.dumps({"success": False, "error": message})


def error_dict(
    code: str = "INTERNAL_ERROR",
    message: str = "An unexpected error occurred.",
    retryable: bool = False,
    suggestion: str | None = None,
    available_names: list[str] | None = None,
) -> dict[str, Any]:
    """Return a structured error dict for internal function composition (pre-serialization)."""
    err: dict[str, Any] = {"code": code, "message": message, "retryable": retryable}
    if suggestion:
        err["suggestion"] = suggestion
    if available_names:
        err["available_names"] = available_names[:50]
    return err


def error_extended(
    code: str,
    message: str,
    retryable: bool = False,
    suggestion: str | None = None,
    available_names: list[str] | None = None,
) -> str:
    """Return a serialized structured error JSON string."""
    return json.dumps({"success": False, "error": error_dict(code, message, retryable, suggestion, available_names)})


async def invoke_tool(
    mcp: Any,
    tool_name: str,
    do_fn: Any,
    *args: Any,
    **kwargs: Any,
) -> str:
    """Unified tool wrapper — replaces boilerplate in every registration function.

    Handles both plain-string and structured-dict error formats from _do_* functions.
    """
    import asyncio
    import json as _json

    t0 = time.monotonic()
    start_tool_context()
    try:
        try:
            ctx = mcp.get_context()
            client = ctx.request_context.lifespan_context["client"]
        except (AttributeError, TypeError, KeyError):
            lifespan = getattr(mcp, "_lifespan_data", None) or {}
            client = lifespan.get("client")
            if client is None:
                return error_extended("INTERNAL_ERROR", "Client not initialized in lifespan context.", retryable=False)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, do_fn, client, *args, **kwargs)
        meta = build_meta(tool_name, t0)

        if result["success"]:
            return success_response(result["data"], _meta=meta)

        err = result.get("error", "Unknown error")
        if isinstance(err, str):
            return error_extended("API_ERROR", err, retryable=True, suggestion="Check Kontomierz API availability and retry.")
        if isinstance(err, dict):
            response = {"success": False, "error": err, "_meta": meta}
            return _json.dumps(response)
        return error_extended("INTERNAL_ERROR", str(err), retryable=False)

    except Exception as exc:
        return error_extended("INTERNAL_ERROR", str(exc), retryable=False)
