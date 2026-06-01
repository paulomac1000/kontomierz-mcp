"""HTTP client for the Kontomierz.pl REST API.

Covers all documented endpoints. Authenticated via api_key query parameter.
"""

import logging
from typing import Any

import requests

from .tools.constants import API_BASE_URL, API_TIMEOUT, HEADERS

_logger = logging.getLogger(__name__)


class KontomierzClient:
    """Synchronous HTTP client for Kontomierz.pl API."""

    def __init__(self, api_key: str, timeout: int = API_TIMEOUT) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def _params(self, **extra: Any) -> dict[str, Any]:
        params: dict[str, Any] = {"api_key": self._api_key}
        for k, v in extra.items():
            if v is not None:
                params[k] = v
        return params

    def _get(self, path: str, **params: Any) -> Any:
        url = f"{API_BASE_URL}/{path}"
        try:
            resp = requests.get(url, headers=HEADERS, params=self._params(**params), timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException:
            _logger.exception("GET %s failed", url)
            return None

    def _post(self, path: str, data: dict[str, Any] | None = None) -> Any:
        url = f"{API_BASE_URL}/{path}"
        try:
            resp = requests.post(url, headers=HEADERS, params={"api_key": self._api_key}, data=data, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException:
            _logger.exception("POST %s failed", url)
            return None

    def _put(self, path: str, data: dict[str, Any] | None = None) -> bool:
        url = f"{API_BASE_URL}/{path}"
        try:
            resp = requests.put(url, headers=HEADERS, params=self._params(), data=data, timeout=self._timeout)
            resp.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            _logger.exception("PUT %s failed", url)
            return False

    def _delete(self, path: str) -> bool:
        url = f"{API_BASE_URL}/{path}"
        try:
            resp = requests.delete(url, headers=HEADERS, params=self._params(), timeout=self._timeout)
            resp.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            _logger.exception("DELETE %s failed", url)
            return False

    # ------------------------------------------------------------------
    # User Accounts
    # ------------------------------------------------------------------

    def get_user_accounts(self) -> list[dict[str, Any]] | None:
        resp = self._get("user_accounts.json")
        if resp is None:
            return None
        return [item["user_account"] for item in resp]

    def create_wallet(
        self,
        currency_balance: str,
        currency_name: str,
        user_name: str = "",
        liquid: str = "1",
    ) -> dict[str, Any] | None:
        data: dict[str, Any] = {
            "user_account[currency_balance]": currency_balance,
            "user_account[currency_name]": currency_name,
            "user_account[liquid]": liquid,
        }
        if user_name:
            data["user_account[user_name]"] = user_name
        resp = self._post("user_accounts/create_wallet.json", data=data)
        if resp is None:
            return None
        return resp.get("user_account")

    def update_wallet(
        self,
        wallet_id: int,
        currency_balance: str = "",
        currency_name: str = "",
        user_name: str = "",
        liquid: str = "",
    ) -> dict[str, Any] | None:
        data: dict[str, Any] = {}
        if user_name:
            data["user_account[user_name]"] = user_name
        if currency_balance:
            data["user_account[currency_balance]"] = currency_balance
        if currency_name:
            data["user_account[currency_name]"] = currency_name
        if liquid:
            data["user_account[liquid]"] = liquid
        resp = self._post(f"user_accounts/{wallet_id}/update_wallet.json", data=data)
        if resp is None:
            return None
        return resp.get("user_account")

    def destroy_wallet(self, wallet_id: int) -> bool:
        return self._delete(f"user_accounts/{wallet_id}/destroy_wallet.json")

    # ------------------------------------------------------------------
    # Money Transactions
    # ------------------------------------------------------------------

    def get_money_transactions(
        self,
        page: int = 1,
        per_page: int | None = None,
        user_account_id: int | None = None,
        q: str | None = None,
        start_on: str | None = None,
        end_on: str | None = None,
        direction: str | None = None,
        tag_name: str | None = None,
        category_group_id: int | None = None,
        category_id: int | None = None,
        show_hidden_transactions: str | None = None,
    ) -> list[dict[str, Any]] | None:
        resp = self._get(
            "money_transactions.json",
            page=page,
            per_page=per_page,
            user_account_id=user_account_id,
            q=q,
            start_on=start_on,
            end_on=end_on,
            direction=direction,
            tag_name=tag_name,
            category_group_id=category_group_id,
            category_id=category_id,
            show_hidden_transactions=show_hidden_transactions,
        )
        if resp is None:
            return None
        return resp if isinstance(resp, list) else resp.get("money_transactions", resp)

    def get_money_transaction(self, transaction_id: int) -> dict[str, Any] | None:
        resp = self._get(f"money_transactions/{transaction_id}.json")
        if resp is None:
            return None
        return resp.get("money_transaction", resp)

    def create_money_transaction(
        self,
        client_assigned_id: str,
        user_account_id: int | None = None,
        category_id: int | None = None,
        currency_amount: str = "",
        currency_name: str = "",
        direction: str = "withdrawal",
        tag_string: str = "",
        name: str = "",
        transaction_on: str = "",
    ) -> dict[str, Any] | None:
        data: dict[str, Any] = {
            "money_transaction[client_assigned_id]": client_assigned_id,
            "money_transaction[direction]": direction,
        }
        if user_account_id is not None:
            data["money_transaction[user_account_id]"] = user_account_id
        if category_id is not None:
            data["money_transaction[category_id]"] = category_id
        if currency_amount:
            data["money_transaction[currency_amount]"] = currency_amount
        if currency_name:
            data["money_transaction[currency_name]"] = currency_name
        if tag_string:
            data["money_transaction[tag_string]"] = tag_string
        if name:
            data["money_transaction[name]"] = name
        if transaction_on:
            data["money_transaction[transaction_on]"] = transaction_on
        resp = self._post("money_transactions.json", data=data)
        if resp is None:
            return None
        return resp.get("money_transaction", resp)

    def update_money_transaction(
        self,
        transaction_id: int,
        user_account_id: int | None = None,
        category_id: int | None = None,
        currency_amount: str = "",
        currency_name: str = "",
        direction: str = "",
        tag_string: str = "",
        name: str = "",
        transaction_on: str = "",
    ) -> dict[str, Any] | None:
        data: dict[str, Any] = {}
        if user_account_id is not None:
            data["money_transaction[user_account_id]"] = user_account_id
        if category_id is not None:
            data["money_transaction[category_id]"] = category_id
        if currency_amount:
            data["money_transaction[currency_amount]"] = currency_amount
        if currency_name:
            data["money_transaction[currency_name]"] = currency_name
        if direction:
            data["money_transaction[direction]"] = direction
        if tag_string:
            data["money_transaction[tag_string]"] = tag_string
        if name:
            data["money_transaction[name]"] = name
        if transaction_on:
            data["money_transaction[transaction_on]"] = transaction_on
        resp = self._post(f"money_transactions/{transaction_id}.json", data=data)
        if resp is None:
            return None
        return resp.get("money_transaction", resp)

    def delete_money_transaction(self, transaction_id: int) -> bool:
        return self._delete(f"money_transactions/{transaction_id}.json")

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def get_categories(self, direction: str) -> list[dict[str, Any]] | None:
        resp = self._get("categories.json", direction=direction, in_wallet="true")
        if resp is None:
            return None
        return resp.get("category_groups", resp)

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def get_tags(self) -> list[dict[str, Any]] | None:
        resp = self._get("tags.json")
        if resp is None:
            return None
        return resp.get("tags", resp)

    # ------------------------------------------------------------------
    # Budgets
    # ------------------------------------------------------------------

    def get_budgets(self, month_on: str | None = None) -> list[dict[str, Any]] | None:
        resp = self._get("budgets.json", month_on=month_on)
        if resp is None:
            return None
        return resp.get("budgets", resp)

    def create_budget(
        self,
        limit: str,
        category_id: int | None = None,
        category_group_id: int | None = None,
        month_on: str = "",
    ) -> dict[str, Any] | None:
        data: dict[str, Any] = {"budget[limit]": limit}
        if category_id is not None:
            data["budget[category_id]"] = category_id
        if category_group_id is not None:
            data["budget[category_group_id]"] = category_group_id
        if month_on:
            data["budget[month_on]"] = month_on
        resp = self._post("budgets.json", data=data)
        if resp is None:
            return None
        return resp.get("budget", resp)

    def update_budget(self, budget_id: int, limit: str) -> dict[str, Any] | None:
        data: dict[str, Any] = {"budget[limit]": limit}
        resp = self._post(f"budgets/{budget_id}.json", data=data)
        if resp is None:
            return None
        return resp.get("budget", resp)

    def delete_budget(self, budget_id: int) -> bool:
        return self._delete(f"budgets/{budget_id}.json")

    def copy_budgets_from_last_month(self) -> bool:
        resp = self._post("budgets/copy_from_last_to_present_month.json")
        return resp is not None

    # ------------------------------------------------------------------
    # Scheduled Transactions
    # ------------------------------------------------------------------

    def get_scheduled_transactions(
        self,
        schedule_group_name: str,
        page: int = 1,
        per_page: int | None = None,
        start_on: str | None = None,
        end_on: str | None = None,
        direction: str | None = None,
    ) -> list[dict[str, Any]] | None:
        resp = self._get(
            "scheduled_transactions.json",
            schedule_group_name=schedule_group_name,
            page=page,
            per_page=per_page,
            start_on=start_on,
            end_on=end_on,
            direction=direction,
        )
        if resp is None:
            return None
        return resp.get("scheduled_transactions", resp)

    def get_schedule(self, schedule_id: int) -> dict[str, Any] | None:
        resp = self._get(f"schedules/{schedule_id}.json")
        if resp is None:
            return None
        return resp.get("schedule", resp)

    def create_schedule(
        self,
        direction: str,
        deadline_on: str,
        holidays: str,
        description: str,
        currency_amount: str,
        currency_name: str,
        repeat: str,
    ) -> dict[str, Any] | None:
        data: dict[str, Any] = {
            "schedule[direction]": direction,
            "schedule[deadline_on]": deadline_on,
            "schedule[holidays]": holidays,
            "schedule[description]": description,
            "schedule[currency_amount]": currency_amount,
            "schedule[currency_name]": currency_name,
            "schedule[repeat]": repeat,
        }
        resp = self._post("schedules.json", data=data)
        if resp is None:
            return None
        return resp.get("schedule", resp)

    def update_schedule(
        self,
        schedule_id: int,
        direction: str = "",
        deadline_on: str = "",
        holidays: str = "",
        description: str = "",
        currency_amount: str = "",
        currency_name: str = "",
        repeat: str = "",
    ) -> dict[str, Any] | None:
        data: dict[str, Any] = {}
        if direction:
            data["schedule[direction]"] = direction
        if deadline_on:
            data["schedule[deadline_on]"] = deadline_on
        if holidays:
            data["schedule[holidays]"] = holidays
        if description:
            data["schedule[description]"] = description
        if currency_amount:
            data["schedule[currency_amount]"] = currency_amount
        if currency_name:
            data["schedule[currency_name]"] = currency_name
        if repeat:
            data["schedule[repeat]"] = repeat
        resp = self._post(f"schedules/{schedule_id}.json", data=data)
        if resp is None:
            return None
        return resp.get("schedule", resp)

    def delete_schedule(self, schedule_id: int) -> bool:
        return self._delete(f"schedules/{schedule_id}.json")

    def mark_schedule_paid(self, schedule_id: int, date: str) -> bool:
        return self._put(f"schedules/{schedule_id}/mark_as_payed/{date}.json")

    def mark_schedule_unpaid(self, schedule_id: int, date: str) -> bool:
        return self._put(f"schedules/{schedule_id}/mark_as_unpayed/{date}.json")

    # ------------------------------------------------------------------
    # Wealth Points
    # ------------------------------------------------------------------

    def get_wealth_points(self, start_on: str | None = None, end_on: str | None = None) -> list[dict[str, Any]] | None:
        resp = self._get("wealth_points.json", start_on=start_on, end_on=end_on)
        if resp is None:
            return None
        return resp if isinstance(resp, list) else resp.get("wealth_points", resp)

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------

    def get_pie_chart(
        self,
        chart_kind: str = "pie",
        start_on: str | None = None,
        end_on: str | None = None,
        direction: str | None = None,
        category_group_id: int | None = None,
        category_id: int | None = None,
        user_account_id: int | None = None,
        q: str | None = None,
        tag_name: str | None = None,
    ) -> dict[str, Any] | None:
        return self._get(
            "charts/money_transactions.json",
            chart_kind=chart_kind,
            start_on=start_on,
            end_on=end_on,
            direction=direction,
            category_group_id=category_group_id,
            category_id=category_id,
            user_account_id=user_account_id,
            q=q,
            tag_name=tag_name,
        )

    # ------------------------------------------------------------------
    # Currencies
    # ------------------------------------------------------------------

    def get_currencies(self) -> list[dict[str, Any]] | None:
        resp = self._get("currencies.json")
        if resp is None:
            return None
        return resp.get("currencies", resp)
