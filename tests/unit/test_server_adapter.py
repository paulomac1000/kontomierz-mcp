"""Composition-root tests independent of the installed MCP SDK implementation."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from types import ModuleType
from typing import Any

import pytest
from starlette.applications import Starlette

from kontomierz_mcp.config import Settings
from kontomierz_mcp.mock_backend import MockKontomierzClient
from kontomierz_mcp.server import build_kernel, build_server, create_http_app


class FakeSessionManager:
    def __init__(self) -> None:
        self.entered = False

    @asynccontextmanager
    async def run(self):
        self.entered = True
        yield


class FakeMCPServer:
    instances: list["FakeMCPServer"] = []

    def __init__(self, name: str, *, instructions: str, lifespan: Any) -> None:
        self.name = name
        self.instructions = instructions
        self.lifespan = lifespan
        self.tools: dict[str, Any] = {}
        self.session_manager = FakeSessionManager()
        self.__class__.instances.append(self)

    def tool(self):
        def decorate(function: Any) -> Any:
            self.tools[function.__name__] = function
            return function

        return decorate

    def streamable_http_app(self, **_kwargs: Any) -> Starlette:
        return Starlette()


def install_fake_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp_module = ModuleType("mcp")
    server_module = ModuleType("mcp.server")
    server_module.MCPServer = FakeMCPServer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mcp", mcp_module)
    monkeypatch.setitem(sys.modules, "mcp.server", server_module)


@pytest.mark.asyncio
async def test_registration_and_tool_error_use_one_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_sdk(monkeypatch)
    FakeMCPServer.instances.clear()
    settings = Settings(api_key="", mock_data=True, enable_write_operations=False)
    dependency = MockKontomierzClient()
    kernel = build_kernel(settings, dependency)
    server = build_server(settings, kernel)
    assert set(server.tools) == {
        "list_accounts",
        "create_wallet",
        "update_wallet",
        "destroy_wallet",
        "list_transactions",
        "get_transaction",
        "create_transaction",
        "update_transaction",
        "delete_transaction",
        "list_categories",
        "list_tags",
        "list_currencies",
        "list_budgets",
        "create_budget",
        "update_budget",
        "delete_budget",
        "copy_budgets_from_last_month",
        "list_scheduled_transactions",
        "get_schedule",
        "create_schedule",
        "update_schedule",
        "delete_schedule",
        "mark_schedule_paid",
        "mark_schedule_unpaid",
        "get_pie_chart",
        "list_wealth_points",
        "describe_kontomierz_capabilities",
    }
    result = await server.tools["list_accounts"]()
    assert len(result["data"]) == 2
    with pytest.raises(RuntimeError, match="AUTHORIZATION_FAILED"):
        await server.tools["create_wallet"]("1", "PLN")
    async with server.lifespan(server):
        pass
    assert dependency.closed is True


def test_http_app_mounts_sdk_with_host_owned_lifespan(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_sdk(monkeypatch)
    FakeMCPServer.instances.clear()
    settings = Settings(api_key="", mock_data=True, transport="streamable-http")
    app = create_http_app(settings)
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/health/live" in paths
    assert "/health/ready" in paths
    assert "" in paths
    assert FakeMCPServer.instances[-1].session_manager.entered is False


WRAPPER_CASES: dict[str, dict[str, object]] = {
    "list_accounts": {},
    "create_wallet": {"currency_balance": "10", "currency_name": "PLN"},
    "update_wallet": {"wallet_id": 101, "user_name": "Updated"},
    "destroy_wallet": {"wallet_id": 102},
    "list_transactions": {"page": 1, "per_page": 10},
    "get_transaction": {"transaction_id": 1001},
    "create_transaction": {
        "client_assigned_id": "wrapper-1",
        "currency_amount": "10",
        "currency_name": "PLN",
    },
    "update_transaction": {"transaction_id": 1001, "name": "Updated"},
    "delete_transaction": {"transaction_id": 1002},
    "list_categories": {},
    "list_tags": {},
    "list_currencies": {},
    "list_budgets": {},
    "create_budget": {"limit": "100", "category_id": 1},
    "update_budget": {"budget_id": 201, "limit": "200"},
    "delete_budget": {"budget_id": 201},
    "copy_budgets_from_last_month": {},
    "list_scheduled_transactions": {},
    "get_schedule": {"schedule_id": 301},
    "create_schedule": {
        "direction": "withdrawal",
        "deadline_on": "2026-09-01",
        "holidays": 0,
        "description": "Mock",
        "currency_amount": "20",
        "currency_name": "PLN",
        "repeat": 2,
    },
    "update_schedule": {"schedule_id": 301, "description": "Updated"},
    "delete_schedule": {"schedule_id": 301},
    "mark_schedule_paid": {"schedule_id": 301, "payment_date": "2026-08-06"},
    "mark_schedule_unpaid": {"schedule_id": 301, "payment_date": "2026-08-06"},
    "get_pie_chart": {},
    "list_wealth_points": {},
    "describe_kontomierz_capabilities": {},
}


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool_name", "arguments"), WRAPPER_CASES.items())
async def test_every_sdk_wrapper_delegates_to_kernel(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, object],
) -> None:
    install_fake_sdk(monkeypatch)
    settings = Settings(api_key="", mock_data=True, enable_write_operations=True)
    dependency = MockKontomierzClient()
    server = build_server(settings, build_kernel(settings, dependency))
    try:
        result = await server.tools[tool_name](**arguments)
        assert "data" in result
        assert result["_meta"]["tool_name"] == tool_name
    finally:
        async with server.lifespan(server):
            pass
