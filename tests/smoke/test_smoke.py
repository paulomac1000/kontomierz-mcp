"""Smoke tests — verify REST API health and tool response format. Skip if server not running."""
from __future__ import annotations

import socket

import pytest

REST_API_PORT = 9102
BASE_URL = f"http://localhost:{REST_API_PORT}"


def _server_running() -> bool:
    try:
        s = socket.create_connection(("localhost", REST_API_PORT), timeout=1)
        s.close()
        return True
    except (TimeoutError, ConnectionRefusedError, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _server_running(),
    reason="MCP server not running. Start with: python -m kontomierz_mcp.server",
)

READONLY_TOOLS = [
    "list_accounts",
    "list_transactions",
    "list_categories",
    "list_tags",
    "list_currencies",
    "list_budgets",
    "list_scheduled_transactions",
    "list_wealth_points",
    "get_pie_chart",
]

TOOLS_WITH_PARAMS = frozenset({
    "get_transaction", "get_schedule",
})


class TestHealthEndpoint:
    def test_health_returns_ok(self) -> None:
        import requests

        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "tool_count" in data

    def test_api_health_returns_ok(self) -> None:
        import requests

        resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_api_tools_lists_tools(self) -> None:
        import requests

        resp = requests.get(f"{BASE_URL}/api/tools", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "tool_count" in data
        assert data["total"] == data["tool_count"]
        assert data["tool_count"] > 0


class TestResponseFormat:
    def _call_safe(self, tool_name: str, **kwargs: str) -> dict | None:
        import requests

        try:
            resp = requests.post(
                f"{BASE_URL}/api/tools/{tool_name}",
                json={"params": kwargs},
                timeout=10,
            )
            return resp.json() if resp.ok else None
        except Exception:
            return None

    def test_all_readonly_tools_return_success_field(self) -> None:
        for tool_name in READONLY_TOOLS:
            data = self._call_safe(tool_name)
            assert data is not None, f"{tool_name}: no response"
            assert "success" in data, f"{tool_name}: missing success field"
            assert isinstance(data["success"], bool), f"{tool_name}: success is not bool"

    def test_list_tools_return_data(self) -> None:
        for tool_name in READONLY_TOOLS:
            data = self._call_safe(tool_name)
            assert data is not None, f"{tool_name}: no response"
            if data["success"]:
                assert "data" in data, f"{tool_name}: missing data on success"
            else:
                assert "error" in data, f"{tool_name}: missing error on failure"
