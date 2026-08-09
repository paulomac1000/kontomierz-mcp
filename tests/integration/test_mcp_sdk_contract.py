from __future__ import annotations

import json

import pytest
from mcp import Client

from kontomierz_mcp.config import Settings
from kontomierz_mcp.manifests import TOOL_DEFINITIONS
from kontomierz_mcp.server import build_server

pytestmark = pytest.mark.sdk


def _input_schema(tool) -> dict[str, object]:
    schema = getattr(tool, "inputSchema", None)
    if schema is None:
        schema = tool.input_schema
    return schema


@pytest.mark.asyncio
async def test_official_in_memory_discovery_matches_governed_catalog() -> None:
    settings = Settings(api_key="", mock_data=True, enable_write_operations=False)
    server = build_server(settings)
    async with Client(server) as client:
        listing = await client.list_tools()

    discovered = {tool.name: tool for tool in listing.tools}
    assert set(discovered) == set(TOOL_DEFINITIONS)
    for name, definition in TOOL_DEFINITIONS.items():
        tool = discovered[name]
        assert tool.description == definition.description
        schema = _input_schema(tool)
        properties = schema.get("properties", {})
        assert set(properties) == {parameter.name for parameter in definition.parameters}
        assert tuple(schema.get("required", ())) == definition.required_parameters
        for parameter in definition.parameters:
            assert properties[parameter.name]["description"] == parameter.description
            if not parameter.required and "default" in properties[parameter.name]:
                assert properties[parameter.name]["default"] == parameter.default


@pytest.mark.asyncio
async def test_official_in_memory_capability_document_has_full_active_state() -> None:
    settings = Settings(api_key="", mock_data=True, enable_write_operations=False)
    server = build_server(settings)
    async with Client(server) as client:
        result = await client.call_tool("describe_kontomierz_capabilities", {})

    assert result.is_error is False
    document = result.structured_content["data"]
    assert document["schema_version"] == "3.0.0"
    assert document["supported_component_count"] == 27
    assert set(document["tools"]) == set(TOOL_DEFINITIONS)
    assert document["tools"]["create_wallet"]["manifest"]["active_state"] == "disabled"
    assert document["tools"]["list_accounts"]["manifest"]["active_state"] == "active"
    assert document["profile"] == "local-process-principal"
    assert document["authorization_policy"] == "single-account-resource-v3"
    assert document["tools"]["destroy_wallet"]["manifest"]["active_state"] == "disabled"


@pytest.mark.asyncio
async def test_official_in_memory_client_reads_structured_error() -> None:
    settings = Settings(api_key="", mock_data=True, enable_write_operations=False)
    server = build_server(settings)
    async with Client(server) as client:
        result = await client.call_tool(
            "create_wallet",
            {"currency_balance": "1", "currency_name": "PLN"},
        )
    assert result.is_error is True
    assert result.structured_content is not None
    error = result.structured_content["error"]
    assert error["code"] == "AUTHORIZATION_FAILED"
    assert error["retryable"] is False
    text = result.content[0].text
    assert json.loads(text) == result.structured_content
    assert "secret" not in text.lower()
