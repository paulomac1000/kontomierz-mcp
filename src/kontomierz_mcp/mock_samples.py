"""Deterministic arguments for exercising every public tool with mock data."""

from __future__ import annotations

from typing import Any

SMOKE_SAMPLES: dict[str, dict[str, Any]] = {
    "list_accounts": {},
    "create_wallet": {"currency_balance": "0", "currency_name": "PLN", "user_name": "Smoke"},
    "update_wallet": {"wallet_id": 101, "user_name": ""},
    "destroy_wallet": {"wallet_id": 102},
    "list_transactions": {"per_page": 1},
    "get_transaction": {"transaction_id": 1001},
    "create_transaction": {"client_assigned_id": "smoke", "currency_amount": "10", "currency_name": "PLN"},
    "update_transaction": {"transaction_id": 1001, "name": ""},
    "delete_transaction": {"transaction_id": 1002},
    "list_categories": {},
    "list_tags": {},
    "list_currencies": {},
    "list_budgets": {},
    "create_budget": {"limit": "100", "category_id": 11},
    "update_budget": {"budget_id": 201, "limit": "110"},
    "delete_budget": {"budget_id": 201},
    "copy_budgets_from_last_month": {},
    "list_scheduled_transactions": {},
    "get_schedule": {"schedule_id": 301},
    "create_schedule": {
        "direction": "withdrawal",
        "deadline_on": "2026-08-15",
        "holidays": 0,
        "description": "Smoke",
        "currency_amount": "50",
        "currency_name": "PLN",
        "repeat": 1,
    },
    "update_schedule": {"schedule_id": 301, "description": ""},
    "delete_schedule": {"schedule_id": 301},
    "mark_schedule_paid": {"schedule_id": 301, "payment_date": "2026-08-01"},
    "mark_schedule_unpaid": {"schedule_id": 301, "payment_date": "2026-08-01"},
    "get_pie_chart": {},
    "list_wealth_points": {},
    "describe_kontomierz_capabilities": {},
}
