from __future__ import annotations

import io
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from kontomierz_mcp.audit import configure_audit_sink
from kontomierz_mcp.config import Settings
from kontomierz_mcp.security import BearerPrincipalMiddleware

HTTP_TOKEN = "a" * 32


async def _invoke(
    middleware: BearerPrincipalMiddleware,
    *,
    path: str,
    authorization: str | None = None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode("ascii")))
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 9101),
        "http_version": "1.1",
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await middleware(scope, receive, send)  # type: ignore[arg-type]
    return messages


def _settings() -> Settings:
    return Settings.from_env(
        {
            "KONTOMIERZ_MOCK_DATA": "1",
            "MCP_TRANSPORT": "streamable-http",
            "MCP_HTTP_AUTH_TOKEN": HTTP_TOKEN,
            "MCP_HTTP_PRINCIPAL": "operator:test",
        },
        env_file=None,
    )


@pytest.mark.asyncio
async def test_unauthenticated_mcp_rejection_emits_sanitized_boundary_audit() -> None:
    stream = io.StringIO()
    logger = logging.getLogger("kontomierz_mcp.audit")
    previous_handlers = list(logger.handlers)
    previous_level = logger.level
    previous_propagate = logger.propagate
    configure_audit_sink(stream=stream, replace=True)

    async def inner(_scope: Any, _receive: Any, _send: Any) -> None:
        raise AssertionError("unauthenticated request must not reach inner app")

    middleware = BearerPrincipalMiddleware(
        inner,
        _settings(),
        public_paths=frozenset({"/health/live"}),
        protected_paths=frozenset({"/mcp", "/health/ready"}),
    )
    try:
        messages = await _invoke(middleware, path="/mcp")
        event = json.loads(stream.getvalue().strip())
    finally:
        logger.handlers[:] = previous_handlers
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate

    assert messages[0]["status"] == 401
    assert event == {
        "audit_failure_policy": "fail-open-result-preserving",
        "authenticated": False,
        "event": "mcp_boundary_rejection",
        "result": "HTTP_401",
        "route": "mcp",
        "stage": "authentication",
        "transport": "streamable-http",
    }


@pytest.mark.asyncio
async def test_unknown_route_and_authenticated_protocol_400_are_audited_without_raw_request_data() -> None:
    stream = io.StringIO()
    logger = logging.getLogger("kontomierz_mcp.audit")
    previous_handlers = list(logger.handlers)
    previous_level = logger.level
    previous_propagate = logger.propagate
    configure_audit_sink(stream=stream, replace=True)

    async def inner(_scope: Any, _receive: Any, send: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        await send({"type": "http.response.start", "status": 400, "headers": []})
        await send({"type": "http.response.body", "body": b"malformed and protected"})

    middleware = BearerPrincipalMiddleware(
        inner,
        _settings(),
        public_paths=frozenset({"/health/live"}),
        protected_paths=frozenset({"/mcp", "/health/ready"}),
    )
    try:
        unknown = await _invoke(middleware, path="/private-secret-path")
        malformed = await _invoke(middleware, path="/mcp", authorization=f"Bearer {HTTP_TOKEN}")
        events = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    finally:
        logger.handlers[:] = previous_handlers
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate

    assert unknown[0]["status"] == 404
    assert malformed[0]["status"] == 400
    assert [(event["stage"], event["result"], event["route"]) for event in events] == [
        ("routing", "HTTP_404", "unknown"),
        ("protocol", "HTTP_400", "mcp"),
    ]
    serialized = stream.getvalue()
    assert "/private-secret-path" not in serialized
    assert HTTP_TOKEN not in serialized
    assert "malformed and protected" not in serialized
