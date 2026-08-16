from __future__ import annotations

import pytest
from mcp import Client

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
    server = build_server(Settings(api_key="", mock_data=True, enable_write_operations=False))
    async with Client(server) as client:
        result = await client.call_tool("list_transactions", {"surprise": "ignored"})

    assert result.is_error is True
    assert result.structured_content is not None
    assert result.structured_content["error"]["code"] == "INVALID_PARAMETER"
    assert result.structured_content["error"]["message"] == "Tool call contains an unexpected parameter"


@pytest.mark.asyncio
async def test_official_tool_schemas_forbid_undeclared_properties() -> None:
    server = build_server(Settings(api_key="", mock_data=True, enable_write_operations=False))
    async with Client(server) as client:
        listed = await client.list_tools()

    assert listed.tools
    assert all(tool.input_schema.get("additionalProperties") is False for tool in listed.tools)
