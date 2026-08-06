"""Official SDK in-memory conformance.

TODO(real-system-agent): add a second test that starts the exact built wheel over
loopback Streamable HTTP and exercises it with a real Client URL. The in-memory
case below runs whenever MCP SDK v2 is installed; this execution environment's
package mirror does not currently provide it.
"""

from __future__ import annotations

import pytest

mcp = pytest.importorskip("mcp", reason="official MCP SDK v2 is unavailable in this execution environment")

from mcp import Client  # type: ignore[attr-defined]  # noqa: E402

from kontomierz_mcp.config import Settings  # noqa: E402
from kontomierz_mcp.mock_backend import MockKontomierzClient  # noqa: E402
from kontomierz_mcp.server import build_kernel, build_server  # noqa: E402


@pytest.mark.sdk
@pytest.mark.asyncio
async def test_official_client_lists_invokes_and_reports_tool_error() -> None:
    settings = Settings(api_key="", mock_data=True, enable_write_operations=False)
    server = build_server(settings, build_kernel(settings, MockKontomierzClient()))
    async with Client(server) as client:
        listing = await client.list_tools()
        names = {tool.name for tool in listing.tools}
        assert len(names) == 27
        assert "list_accounts" in names
        success = await client.call_tool("list_accounts", {})
        assert success.is_error is False
        denied = await client.call_tool(
            "create_wallet",
            {"currency_balance": "1.00", "currency_name": "PLN"},
        )
        assert denied.is_error is True
