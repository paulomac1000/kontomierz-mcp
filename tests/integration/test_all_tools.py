"""Integration tests — register tools on mock FastMCP and call them directly.

Tool wrappers capture `mcp` from closure, so mock_mcp.get_context() must work.
Tests verify the full pipeline: registration → invocation → response format.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from kontomierz_mcp.tools.accounts import register_accounts_tools
from kontomierz_mcp.tools.budgets import register_budgets_tools
from kontomierz_mcp.tools.charts_wealth import register_charts_wealth_tools
from kontomierz_mcp.tools.reference import register_reference_tools
from kontomierz_mcp.tools.schedules import register_schedules_tools
from kontomierz_mcp.tools.transactions import register_transactions_tools

# Anonymized real-world data fixtures
REAL_ACCOUNTS = [
    {"id": 101, "display_name": "Konto główne", "bank_name": "Bank A", "currency_name": "PLN", "currency_balance": "12500.50"},
    {"id": 102, "display_name": "Portfel", "bank_name": "Wallets", "currency_name": "PLN", "currency_balance": "350.00", "is_default_wallet": True},
]
REAL_TRANSACTIONS = [
    {"id": 1001, "description": "Biedronka", "currency_amount": "-145.90", "currency_name": "PLN"},
    {"id": 1002, "description": "Wynagrodzenie", "currency_amount": "8500.00", "currency_name": "PLN"},
]
REAL_CATEGORIES = [{"id": 1, "name": "Spożywcze"}]
REAL_TAGS = [{"id": 1, "name": "jedzenie"}, {"id": 2, "name": "subskrypcje"}]
REAL_CURRENCIES = [{"id": 1, "name": "PLN", "importance": "major"}]
REAL_BUDGETS = [{"id": 1, "name": "Jedzenie", "limit": "600.00", "amount": "145.90"}]
REAL_SCHEDULED = [{"schedule_id": 1, "description": "Czynsz", "currency_amount": "-1200.00"}]
REAL_SCHEDULE_DETAIL = {"id": 1, "description": "Czynsz", "repeat": "2"}
REAL_WEALTH = [{"id": 1, "amount": "50000.00"}]
REAL_PIE_CHART = {"type": "spendings", "data": []}


@pytest.fixture(autouse=True)
def _enable_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kontomierz_mcp.tools.constants.ENABLE_WRITE_OPERATIONS", True)


def _build_mock_mcp(client: MagicMock) -> MagicMock:
    """Create a mock FastMCP with working tool() decorator and lifespan context."""
    mcp = MagicMock()
    mcp._tools = {}

    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"client": client}
    mcp.get_context.return_value = ctx

    def tool_decorator(*args, **kwargs):
        def wrapper(func):
            tool_name = kwargs.get("name", func.__name__)
            mcp._tools[tool_name] = func
            return func
        if len(args) == 1 and callable(args[0]) and not kwargs:
            mcp._tools[args[0].__name__] = args[0]
            return args[0]
        return wrapper

    mcp.tool = tool_decorator
    mcp.get_tool = lambda name: mcp._tools.get(name)
    return mcp


async def _invoke(fn, **kwargs):
    """Call an async tool wrapper and parse the JSON result."""
    result_str = await fn(**kwargs)
    return json.loads(result_str)


# ---------------------------------------------------------------------------
# Read-Only Tools
# ---------------------------------------------------------------------------

class TestReadOnlyTools:
    @pytest.mark.asyncio
    async def test_list_accounts(self) -> None:
        client = MagicMock()
        client.get_user_accounts.return_value = REAL_ACCOUNTS
        mcp = _build_mock_mcp(client)
        register_accounts_tools(mcp)

        data = await _invoke(mcp.get_tool("list_accounts"))
        assert data["success"] is True
        assert len(data["data"]) == 2

    @pytest.mark.asyncio
    async def test_list_transactions(self) -> None:
        client = MagicMock()
        client.get_money_transactions.return_value = REAL_TRANSACTIONS
        mcp = _build_mock_mcp(client)
        register_transactions_tools(mcp)

        data = await _invoke(mcp.get_tool("list_transactions"), page=1)
        assert data["success"] is True
        assert len(data["data"]["transactions"]) == 2
        assert data["data"]["page"] == 1
        assert data["data"]["has_more"] is True

    @pytest.mark.asyncio
    async def test_get_transaction(self) -> None:
        client = MagicMock()
        client.get_money_transaction.return_value = REAL_TRANSACTIONS[0]
        mcp = _build_mock_mcp(client)
        register_transactions_tools(mcp)

        data = await _invoke(mcp.get_tool("get_transaction"), transaction_id=1001)
        assert data["success"] is True
        assert "Biedronka" in data["data"]["description"]

    @pytest.mark.asyncio
    async def test_list_categories(self) -> None:
        client = MagicMock()
        client.get_categories.return_value = REAL_CATEGORIES
        mcp = _build_mock_mcp(client)
        register_reference_tools(mcp)

        data = await _invoke(mcp.get_tool("list_categories"), direction="withdrawal")
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_list_tags(self) -> None:
        client = MagicMock()
        client.get_tags.return_value = REAL_TAGS
        mcp = _build_mock_mcp(client)
        register_reference_tools(mcp)

        data = await _invoke(mcp.get_tool("list_tags"))
        assert data["success"] is True
        assert len(data["data"]) == 2

    @pytest.mark.asyncio
    async def test_list_currencies(self) -> None:
        client = MagicMock()
        client.get_currencies.return_value = REAL_CURRENCIES
        mcp = _build_mock_mcp(client)
        register_reference_tools(mcp)

        data = await _invoke(mcp.get_tool("list_currencies"))
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_list_budgets(self) -> None:
        client = MagicMock()
        client.get_budgets.return_value = REAL_BUDGETS
        mcp = _build_mock_mcp(client)
        register_budgets_tools(mcp)

        data = await _invoke(mcp.get_tool("list_budgets"))
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_list_scheduled(self) -> None:
        client = MagicMock()
        client.get_scheduled_transactions.return_value = REAL_SCHEDULED
        mcp = _build_mock_mcp(client)
        register_schedules_tools(mcp)

        data = await _invoke(mcp.get_tool("list_scheduled_transactions"), schedule_group_name="unpaid")
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_get_schedule(self) -> None:
        client = MagicMock()
        client.get_schedule.return_value = REAL_SCHEDULE_DETAIL
        mcp = _build_mock_mcp(client)
        register_schedules_tools(mcp)

        data = await _invoke(mcp.get_tool("get_schedule"), schedule_id=1)
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_get_pie_chart(self) -> None:
        client = MagicMock()
        client.get_pie_chart.return_value = REAL_PIE_CHART
        mcp = _build_mock_mcp(client)
        register_charts_wealth_tools(mcp)

        data = await _invoke(mcp.get_tool("get_pie_chart"))
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_list_wealth_points(self) -> None:
        client = MagicMock()
        client.get_wealth_points.return_value = REAL_WEALTH
        mcp = _build_mock_mcp(client)
        register_charts_wealth_tools(mcp)

        data = await _invoke(mcp.get_tool("list_wealth_points"))
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_empty_result_is_success(self) -> None:
        client = MagicMock()
        client.get_tags.return_value = []
        mcp = _build_mock_mcp(client)
        register_reference_tools(mcp)

        data = await _invoke(mcp.get_tool("list_tags"))
        assert data["success"] is True
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_api_failure(self) -> None:
        client = MagicMock()
        client.get_user_accounts.return_value = None
        mcp = _build_mock_mcp(client)
        register_accounts_tools(mcp)

        data = await _invoke(mcp.get_tool("list_accounts"))
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_exception_handler(self) -> None:
        client = MagicMock()
        client.get_tags.side_effect = RuntimeError("boom")
        mcp = _build_mock_mcp(client)
        register_reference_tools(mcp)

        data = await _invoke(mcp.get_tool("list_tags"))
        assert data["success"] is False


# ---------------------------------------------------------------------------
# Write Tools
# ---------------------------------------------------------------------------

class TestWriteTools:
    @pytest.mark.asyncio
    async def test_create_wallet(self) -> None:
        client = MagicMock()
        client.create_wallet.return_value = {"id": 99}
        mcp = _build_mock_mcp(client)
        register_accounts_tools(mcp)

        data = await _invoke(mcp.get_tool("create_wallet"), currency_balance="100.00", currency_name="PLN")
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_mark_schedule_paid(self) -> None:
        client = MagicMock()
        client.mark_schedule_paid.return_value = True
        mcp = _build_mock_mcp(client)
        register_schedules_tools(mcp)

        data = await _invoke(mcp.get_tool("mark_schedule_paid"), schedule_id=1, date="10-06-2026")
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_copy_budgets(self) -> None:
        client = MagicMock()
        client.copy_budgets_from_last_month.return_value = True
        mcp = _build_mock_mcp(client)
        register_budgets_tools(mcp)

        data = await _invoke(mcp.get_tool("copy_budgets_from_last_month"))
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_destroy_wallet(self) -> None:
        client = MagicMock()
        client.destroy_wallet.return_value = True
        mcp = _build_mock_mcp(client)
        register_accounts_tools(mcp)

        data = await _invoke(mcp.get_tool("destroy_wallet"), wallet_id=1)
        assert data["success"] is True
