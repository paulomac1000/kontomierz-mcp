"""Execute every tool through the real invocation kernel on synthetic data."""

from __future__ import annotations

import asyncio

from kontomierz_mcp.config import Settings
from kontomierz_mcp.manifests import TOOL_MANIFESTS
from kontomierz_mcp.mock_backend import MockKontomierzClient
from kontomierz_mcp.server import build_kernel

CASES = {
    "list_accounts": {},
    "create_wallet": {"currency_balance": "10", "currency_name": "PLN"},
    "update_wallet": {"wallet_id": 101, "user_name": "Updated"},
    "destroy_wallet": {"wallet_id": 102},
    "list_transactions": {"page": 1, "per_page": 10},
    "get_transaction": {"transaction_id": 1001},
    "create_transaction": {"client_assigned_id": "smoke-1", "currency_amount": "10", "currency_name": "PLN"},
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
    "create_schedule": {"direction": "withdrawal", "deadline_on": "2026-09-01", "holidays": 0, "description": "Mock", "currency_amount": "20", "currency_name": "PLN", "repeat": 2},
    "update_schedule": {"schedule_id": 301, "description": "Updated"},
    "delete_schedule": {"schedule_id": 301},
    "mark_schedule_paid": {"schedule_id": 301, "payment_date": "2026-08-06"},
    "mark_schedule_unpaid": {"schedule_id": 301, "payment_date": "2026-08-06"},
    "get_pie_chart": {},
    "list_wealth_points": {},
    "describe_kontomierz_capabilities": {},
}


async def main() -> None:
    assert set(CASES) == set(TOOL_MANIFESTS)
    settings = Settings(api_key="", mock_data=True, enable_write_operations=True)
    for name, arguments in CASES.items():
        kernel = build_kernel(settings, MockKontomierzClient())
        result = await kernel.invoke(name, arguments)
        assert "data" in result and "_meta" in result, name
        await kernel.close()
    print(f"mock smoke passed for {len(CASES)} tools")


if __name__ == "__main__":
    asyncio.run(main())
