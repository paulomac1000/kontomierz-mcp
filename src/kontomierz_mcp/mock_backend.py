"""Deterministic in-memory Kontomierz backend for development and tests.

Response shapes mirror the real Kontomierz API contract verified on 2026-08-08
against a live account (see docs/upstream-api.md).
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from .errors import ApplicationError, ErrorCode


class MockKontomierzClient:
    """Implements the dependency surface without network or real financial data."""

    def __init__(self) -> None:
        self.accounts = [
            {
                "id": 101,
                "iban": "PL00 0000 0000 0000 0000 0000 0000",
                "balance": "1250.50",
                "iban_checksum": "XX",
                "currency_balance": "1250.50",
                "position": 1,
                "plain_iban": None,
                "currency_funds_available": None,
                "display_name": "Mock checking",
                "bank_name": "Portfel",
                "bank_plugin_name": "Wallets",
                "bank_position": 1,
            },
            {
                "id": 102,
                "iban": "PL00 0000 0000 0000 0000 0000 0001",
                "balance": "350.00",
                "iban_checksum": "XX",
                "currency_balance": "350.00",
                "position": 2,
                "plain_iban": None,
                "currency_funds_available": None,
                "display_name": "Mock wallet",
                "bank_name": "Portfel",
                "bank_plugin_name": "Wallets",
                "bank_position": 1,
            },
        ]
        self.transactions = [
            {
                "id": 1001,
                "client_assigned_id": "mock-1001",
                "description": "Mock groceries",
                "currency_amount": "-145.90",
                "currency_name": "PLN",
                "direction": "withdrawal",
                "transaction_on": "2026-08-01",
            },
            {
                "id": 1002,
                "client_assigned_id": "mock-1002",
                "description": "Mock salary",
                "currency_amount": "8500.00",
                "currency_name": "PLN",
                "direction": "deposit",
                "transaction_on": "2026-07-31",
            },
        ]
        self.budgets = [
            {
                "id": 201,
                "kind": "ordinary",
                "name": "Mock groceries",
                "limit": "600.00",
                "amount": "0.0",
                "category_id": 1,
            }
        ]
        self.schedules = [
            {
                "id": 301,
                "description": "Mock rent",
                "currency_amount": "1200.00",
                "currency_name": "PLN",
                "repeat": 2,
                "repeat_description": "co miesiąc",
                "holidays": "0",
                "holidays_description": "nie przesuwaj",
                "next_deadline_on": "2026-09-01",
            }
        ]
        self.closed = False
        self.available = True

    async def close(self) -> None:
        self.closed = True

    async def probe(self) -> bool:
        return self.available and not self.closed

    @staticmethod
    def _next_id(values: list[dict[str, Any]]) -> int:
        return max((int(value["id"]) for value in values), default=0) + 1

    @staticmethod
    def _find(values: list[dict[str, Any]], identifier: int) -> dict[str, Any]:
        for value in values:
            if value.get("id") == identifier:
                return value
        raise ApplicationError(ErrorCode.RESOURCE_NOT_FOUND, f"Resource {identifier} was not found")

    def get_user_accounts(self) -> list[dict[str, Any]]:
        return [deepcopy(account) for account in self.accounts]

    def create_wallet(
        self,
        currency_balance: str,
        currency_name: str,
        user_name: str | None = None,
        liquid: str = "1",
    ) -> dict[str, Any]:
        item = {
            "id": self._next_id(self.accounts),
            "iban": "PL00 0000 0000 0000 0000 0000 0002",
            "balance": currency_balance,
            "iban_checksum": "XX",
            "currency_balance": currency_balance,
            "position": len(self.accounts) + 1,
            "plain_iban": None,
            "currency_funds_available": None,
            "display_name": "Mock wallet" if user_name is None else user_name,
            "bank_name": "Portfel",
            "bank_plugin_name": "Wallets",
            "bank_position": 1,
        }
        self.accounts.append(item)
        return deepcopy(item)

    def update_wallet(self, wallet_id: int, **fields: Any) -> dict[str, Any]:
        item = self._find(self.accounts, wallet_id)
        item.update({key: value for key, value in fields.items() if value is not None})
        return deepcopy(item)

    def destroy_wallet(self, wallet_id: int) -> bool:
        item = self._find(self.accounts, wallet_id)
        self.accounts.remove(item)
        return True

    def get_money_transactions(
        self,
        page: int = 1,
        per_page: int | None = None,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        values = self.transactions
        direction = filters.get("direction")
        if direction and direction != "all":
            normalized = direction.removesuffix("s")
            values = [value for value in values if value.get("direction") == normalized]
        if per_page:
            start = (page - 1) * per_page
            values = values[start : start + per_page]
        return deepcopy(values)

    def get_money_transaction(self, transaction_id: int) -> dict[str, Any]:
        return deepcopy(self._find(self.transactions, transaction_id))

    def create_money_transaction(self, **fields: Any) -> dict[str, Any]:
        assigned = fields.get("client_assigned_id")
        for item in self.transactions:
            if item.get("client_assigned_id") == assigned:
                return deepcopy(item)
        item = {"id": self._next_id(self.transactions), **fields}
        self.transactions.append(item)
        return deepcopy(item)

    def update_money_transaction(self, transaction_id: int, **fields: Any) -> dict[str, Any]:
        item = self._find(self.transactions, transaction_id)
        item.update({key: value for key, value in fields.items() if value is not None})
        return deepcopy(item)

    def delete_money_transaction(self, transaction_id: int) -> bool:
        item = self._find(self.transactions, transaction_id)
        self.transactions.remove(item)
        return True

    def get_categories(self, direction: str) -> list[dict[str, Any]]:
        return [
            {
                "id": 1,
                "name": "Mock group",
                "position": 1,
                "color": "4169E1",
                "categories": [
                    {
                        "category_group_id": 1,
                        "id": 11,
                        "name": "Mock category",
                        "position": 1,
                        "color": "5175e3",
                        "spending": True,
                    }
                ],
            }
        ]

    def get_tags(self) -> list[dict[str, Any]]:
        return [{"name": "mock"}]

    def get_currencies(self) -> list[dict[str, Any]]:
        return [
            {"id": 1, "name": "PLN", "full_name": "Polish złoty", "importance": "major"},
            {"id": 2, "name": "EUR", "full_name": "Euro", "importance": "major"},
            {"id": 3, "name": "USD", "full_name": "US Dollar", "importance": "major"},
        ]

    def get_budgets(self, month_on: str | None = None) -> list[dict[str, Any]]:
        return deepcopy(self.budgets)

    def create_budget(
        self,
        limit: str,
        category_id: int | None = None,
        category_group_id: int | None = None,
        month_on: str = "",
    ) -> dict[str, Any]:
        item = {
            "id": self._next_id(self.budgets),
            "kind": "ordinary",
            "name": "Mock budget",
            "limit": limit,
            "amount": "0.0",
            "month_on": month_on,
        }
        if category_id is not None:
            item["category_id"] = category_id
        if category_group_id is not None:
            item["category_group_id"] = category_group_id
        self.budgets.append(item)
        return deepcopy(item)

    def update_budget(self, budget_id: int, limit: str) -> dict[str, Any]:
        item = self._find(self.budgets, budget_id)
        item["limit"] = limit
        return deepcopy(item)

    def delete_budget(self, budget_id: int) -> bool:
        item = self._find(self.budgets, budget_id)
        self.budgets.remove(item)
        return True

    def copy_budgets_from_last_month(self) -> bool:
        return True

    def get_scheduled_transactions(self, **filters: Any) -> list[dict[str, Any]]:
        paid = filters.get("schedule_group_name") == "paid"
        values = [deepcopy(item) for item in self.schedules if bool(item.get("paid")) is paid]
        page_number = int(filters.get("page", 1))
        per_page = filters.get("per_page")
        if per_page:
            start = (page_number - 1) * int(per_page)
            values = values[start : start + int(per_page)]
        return [
            {
                "schedule_id": item["id"],
                "transaction_on": "01-09-2026",
                "description": item["description"],
                "currency_amount": item["currency_amount"],
                "currency_name": item["currency_name"],
                "paid": "false" if not item.get("paid") else "true",
            }
            for item in values
        ]

    def get_schedule(self, schedule_id: int) -> dict[str, Any]:
        item = self._find(self.schedules, schedule_id)
        return {
            "id": item["id"],
            "next_deadline_on": item.get("next_deadline_on"),
            "description": item["description"],
            "currency_amount": item["currency_amount"],
            "currency_name": item["currency_name"],
            "repeat": item.get("repeat", 1),
            "repeat_description": item.get("repeat_description", "tylko raz"),
            "holidays": item.get("holidays", "0"),
            "holidays_description": item.get("holidays_description", "nie przesuwaj"),
        }

    def create_schedule(self, **fields: Any) -> dict[str, Any]:
        item = {"id": self._next_id(self.schedules), "paid": False, **fields}
        self.schedules.append(item)
        return deepcopy(item)

    def update_schedule(self, schedule_id: int, **fields: Any) -> dict[str, Any]:
        item = self._find(self.schedules, schedule_id)
        item.update({key: value for key, value in fields.items() if value is not None})
        return deepcopy(item)

    def delete_schedule(self, schedule_id: int) -> bool:
        item = self._find(self.schedules, schedule_id)
        self.schedules.remove(item)
        return True

    def mark_schedule_paid(self, schedule_id: int, payment_date: str) -> bool:
        item = self._find(self.schedules, schedule_id)
        item.update({"paid": True, "payment_date": payment_date})
        return True

    def mark_schedule_unpaid(self, schedule_id: int, payment_date: str) -> bool:
        item = self._find(self.schedules, schedule_id)
        item.update({"paid": False, "payment_date": payment_date})
        return True

    def get_wealth_points(self, start_on: str | None = None, end_on: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "id": 1,
                "date_on": date(2026, 8, 1).isoformat(),
                "amount": "50000.00",
                "notes": None,
            }
        ]

    def get_pie_chart(self, **filters: Any) -> dict[str, Any]:
        return {"type": "incomes-vs-spendings", "data": [{"name": "Mock", "y": "145.90"}]}
