"""Smoke tests — verify REST API health and tool response format (Template 12). Skip if server not running."""

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

ALL_TOOLS = [
    "copy_budgets_from_last_month",
    "create_budget",
    "create_schedule",
    "create_transaction",
    "create_wallet",
    "delete_budget",
    "delete_schedule",
    "delete_transaction",
    "describe_kontomierz_capabilities",
    "destroy_wallet",
    "get_pie_chart",
    "get_schedule",
    "get_transaction",
    "list_accounts",
    "list_budgets",
    "list_categories",
    "list_currencies",
    "list_scheduled_transactions",
    "list_tags",
    "list_transactions",
    "list_wealth_points",
    "mark_schedule_paid",
    "mark_schedule_unpaid",
    "update_budget",
    "update_schedule",
    "update_transaction",
    "update_wallet",
]

_REQUIRES_PARAMS = frozenset(
    {
        "create_budget",
        "create_schedule",
        "create_transaction",
        "create_wallet",
        "delete_budget",
        "delete_schedule",
        "delete_transaction",
        "destroy_wallet",
        "get_schedule",
        "get_transaction",
        "mark_schedule_paid",
        "mark_schedule_unpaid",
        "update_budget",
        "update_schedule",
        "update_transaction",
        "update_wallet",
    }
)


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
        assert data["tool_count"] >= 27

    def test_tool_manifest_endpoint(self) -> None:
        import requests

        resp = requests.get(f"{BASE_URL}/api/tools/list_tags/manifest", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk"] == "READ"
        assert data["name"] == "list_tags"


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

    def test_all_tools_return_success_field(self) -> None:
        call_map: dict[str, dict] = {
            "create_budget": {"limit": "100"},
            "create_schedule": {
                "direction": "withdrawal",
                "deadline_on": "01-01-2030",
                "holidays": "0",
                "description": "test",
                "currency_amount": "10",
                "currency_name": "PLN",
                "repeat": "1",
            },
            "create_transaction": {"client_assigned_id": "ts_999"},
            "create_wallet": {"currency_balance": "100", "currency_name": "PLN"},
            "delete_budget": {"budget_id": "1"},
            "delete_schedule": {"schedule_id": "1"},
            "delete_transaction": {"transaction_id": "1"},
            "destroy_wallet": {"wallet_id": "1"},
            "get_schedule": {"schedule_id": "1"},
            "get_transaction": {"transaction_id": "1"},
            "mark_schedule_paid": {"schedule_id": "1", "date": "01-01-2030"},
            "mark_schedule_unpaid": {"schedule_id": "1", "date": "01-01-2030"},
            "update_budget": {"budget_id": "1", "limit": "200"},
            "update_schedule": {"schedule_id": "1"},
            "update_transaction": {"transaction_id": "1"},
            "update_wallet": {"wallet_id": "1"},
        }

        for tool_name in ALL_TOOLS:
            params = call_map.get(tool_name, {})
            data = self._call_safe(tool_name, **params)
            assert data is not None, f"{tool_name}: no response"
            assert "success" in data, f"{tool_name}: missing success field"
            assert isinstance(data["success"], bool), f"{tool_name}: success is not bool"
