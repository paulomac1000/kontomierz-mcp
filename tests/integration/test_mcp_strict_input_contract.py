from __future__ import annotations

import io
import json
import logging

import pytest
from mcp import Client

from kontomierz_mcp.audit import configure_audit_sink
from kontomierz_mcp.config import Settings
from kontomierz_mcp.server import build_server

pytestmark = pytest.mark.sdk


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {"page": "1"},
        {"page": True},
        {"user_account_id": "1"},
        {"q": 123},
        {"show_hidden_transactions": "false"},
        {"show_hidden_transactions": 1},
    ],
)
async def test_official_client_rejects_scalar_type_coercion(arguments: dict[str, object]) -> None:
    server = build_server(Settings(api_key="", mock_data=True, enable_write_operations=False))
    async with Client(server) as client:
        result = await client.call_tool("list_transactions", arguments)

    assert result.is_error is True


@pytest.mark.asyncio
async def test_sdk_scalar_validation_failure_emits_pre_dispatch_audit() -> None:
    stream = io.StringIO()
    logger = logging.getLogger("kontomierz_mcp.audit")
    previous_handlers = list(logger.handlers)
    previous_level = logger.level
    previous_propagate = logger.propagate
    configure_audit_sink(stream=stream, replace=True)
    server = build_server(Settings(api_key="", mock_data=True, enable_write_operations=False))
    try:
        async with Client(server) as client:
            result = await client.call_tool("list_transactions", {"page": "1"})
        events = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    finally:
        logger.handlers[:] = previous_handlers
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate

    assert result.is_error is True
    principal = events[0].pop("principal")
    assert principal is not None and principal.startswith("local-process:")
    assert events == [
        {
            "audit_failure_policy": "fail-open-result-preserving",
            "authenticated": True,
            "event": "mcp_boundary_rejection",
            "result": "INVALID_PARAMETER",
            "route": "mcp",
            "stage": "schema",
            "transport": "stdio",
        }
    ]


@pytest.mark.asyncio
async def test_official_client_rejects_explicit_zero_optional_id() -> None:
    server = build_server(Settings(api_key="", mock_data=True, enable_write_operations=False))
    async with Client(server) as client:
        result = await client.call_tool("list_transactions", {"user_account_id": 0})

    assert result.is_error is True
    assert result.structured_content is not None
    assert result.structured_content["error"]["code"] == "INVALID_PARAMETER"
    assert result.structured_content["error"]["message"] == "user_account_id must be a positive integer"


@pytest.mark.asyncio
async def test_official_client_rejects_unknown_tool_arguments_before_sdk_drops_them() -> None:
    stream = io.StringIO()
    logger = logging.getLogger("kontomierz_mcp.audit")
    previous_handlers = list(logger.handlers)
    previous_level = logger.level
    previous_propagate = logger.propagate
    configure_audit_sink(stream=stream, replace=True)
    server = build_server(Settings(api_key="", mock_data=True, enable_write_operations=False))
    try:
        async with Client(server) as client:
            result = await client.call_tool("list_transactions", {"surprise": "ignored"})
        events = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    finally:
        logger.handlers[:] = previous_handlers
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate

    assert result.is_error is True
    assert result.structured_content is not None
    assert result.structured_content["error"]["code"] == "INVALID_PARAMETER"
    assert result.structured_content["error"]["message"] == "Tool call contains an unexpected parameter"
    principal = events[0].pop("principal")
    assert principal is not None and principal.startswith("local-process:")
    assert events == [
        {
            "audit_failure_policy": "fail-open-result-preserving",
            "authenticated": True,
            "event": "mcp_boundary_rejection",
            "result": "INVALID_PARAMETER",
            "route": "mcp",
            "stage": "schema",
            "transport": "stdio",
        }
    ]


@pytest.mark.asyncio
async def test_official_tool_schemas_forbid_undeclared_properties() -> None:
    server = build_server(Settings(api_key="", mock_data=True, enable_write_operations=False))
    async with Client(server) as client:
        listed = await client.list_tools()

    assert listed.tools
    assert all(tool.input_schema.get("additionalProperties") is False for tool in listed.tools)
