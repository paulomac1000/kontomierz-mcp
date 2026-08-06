from __future__ import annotations

import json

import pytest
from mcp import Client

from kontomierz_mcp.config import Settings
from kontomierz_mcp.server import build_server

pytestmark = pytest.mark.sdk


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
