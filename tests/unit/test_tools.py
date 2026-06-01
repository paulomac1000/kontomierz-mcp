"""Unit tests for tool internal functions — zero I/O, direct calls."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kontomierz_mcp.tools.accounts import (
    _do_create_wallet,
    _do_destroy_wallet,
    _do_list_accounts,
    _do_update_wallet,
)
from kontomierz_mcp.tools.budgets import (
    _do_copy_budgets,
    _do_create_budget,
    _do_delete_budget,
    _do_list_budgets,
    _do_update_budget,
)
from kontomierz_mcp.tools.charts_wealth import (
    _do_get_pie_chart,
    _do_get_wealth_points,
)
from kontomierz_mcp.tools.reference import (
    _do_get_categories,
    _do_get_currencies,
    _do_get_tags,
)
from kontomierz_mcp.tools.schedules import (
    _do_create_schedule,
    _do_delete_schedule,
    _do_get_schedule,
    _do_list_scheduled_transactions,
    _do_mark_schedule_paid,
    _do_mark_schedule_unpaid,
    _do_update_schedule,
)
from kontomierz_mcp.tools.transactions import (
    _do_create_transaction,
    _do_delete_transaction,
    _do_get_transaction,
    _do_list_transactions,
    _do_update_transaction,
)
from kontomierz_mcp.validators import ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable write operations for all tests."""
    monkeypatch.setattr(
        "kontomierz_mcp.tools.constants.ENABLE_WRITE_OPERATIONS", True
    )


def _assert_success(result: dict) -> None:
    assert result["success"] is True, f"Expected success, got: {result}"
    assert "data" in result


def _assert_error(result: dict) -> None:
    assert result["success"] is False, f"Expected error, got: {result}"


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

class TestAccounts:
    def test_list_accounts_success(self, mock_client: MagicMock) -> None:
        mock_client.get_user_accounts.return_value = [{"id": 1, "display_name": "Konto"}]
        result = _do_list_accounts(mock_client)
        _assert_success(result)
        assert len(result["data"]) == 1

    def test_list_accounts_api_error(self, mock_client: MagicMock) -> None:
        mock_client.get_user_accounts.return_value = None
        _assert_error(_do_list_accounts(mock_client))

    def test_create_wallet_success(self, mock_client: MagicMock) -> None:
        mock_client.create_wallet.return_value = {"id": 99}
        result = _do_create_wallet(mock_client, "100.00", "PLN")
        _assert_success(result)

    def test_create_wallet_validation(self, mock_client: MagicMock) -> None:
        with pytest.raises(ValidationError):
            _do_create_wallet(mock_client, "", "PLN")

    def test_update_wallet_success(self, mock_client: MagicMock) -> None:
        mock_client.update_wallet.return_value = {"id": 10}
        result = _do_update_wallet(mock_client, 10, user_name="Updated")
        _assert_success(result)

    def test_update_wallet_api_error(self, mock_client: MagicMock) -> None:
        mock_client.update_wallet.return_value = None
        _assert_error(_do_update_wallet(mock_client, 10))

    def test_destroy_wallet_success(self, mock_client: MagicMock) -> None:
        mock_client.destroy_wallet.return_value = True
        result = _do_destroy_wallet(mock_client, 1)
        _assert_success(result)

    def test_destroy_wallet_failure(self, mock_client: MagicMock) -> None:
        mock_client.destroy_wallet.return_value = False
        _assert_error(_do_destroy_wallet(mock_client, 1))


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

class TestTransactions:
    def test_list_success(self, mock_client: MagicMock) -> None:
        mock_client.get_money_transactions.return_value = [{"id": 1}]
        result = _do_list_transactions(mock_client)
        _assert_success(result)

    def test_list_api_error(self, mock_client: MagicMock) -> None:
        mock_client.get_money_transactions.return_value = None
        _assert_error(_do_list_transactions(mock_client))

    def test_get_success(self, mock_client: MagicMock) -> None:
        mock_client.get_money_transaction.return_value = {"id": 5, "description": "Test"}
        result = _do_get_transaction(mock_client, 5)
        _assert_success(result)

    def test_get_api_error(self, mock_client: MagicMock) -> None:
        mock_client.get_money_transaction.return_value = None
        _assert_error(_do_get_transaction(mock_client, 5))

    def test_create_success(self, mock_client: MagicMock) -> None:
        mock_client.create_money_transaction.return_value = {"id": 100}
        result = _do_create_transaction(mock_client, "ts_1", currency_amount="50")
        _assert_success(result)

    def test_create_api_error(self, mock_client: MagicMock) -> None:
        mock_client.create_money_transaction.return_value = None
        _assert_error(_do_create_transaction(mock_client, "ts_1"))

    def test_update_success(self, mock_client: MagicMock) -> None:
        mock_client.update_money_transaction.return_value = {"id": 5}
        result = _do_update_transaction(mock_client, 5, name="Updated")
        _assert_success(result)

    def test_update_api_error(self, mock_client: MagicMock) -> None:
        mock_client.update_money_transaction.return_value = None
        _assert_error(_do_update_transaction(mock_client, 5))

    def test_delete_success(self, mock_client: MagicMock) -> None:
        mock_client.delete_money_transaction.return_value = True
        result = _do_delete_transaction(mock_client, 5)
        _assert_success(result)

    def test_delete_failure(self, mock_client: MagicMock) -> None:
        mock_client.delete_money_transaction.return_value = False
        _assert_error(_do_delete_transaction(mock_client, 5))


# ---------------------------------------------------------------------------
# Categories / Tags / Currencies
# ---------------------------------------------------------------------------

class TestReference:
    def test_categories_success(self, mock_client: MagicMock) -> None:
        mock_client.get_categories.return_value = [{"name": "Zakupy"}]
        result = _do_get_categories(mock_client, "withdrawal")
        _assert_success(result)

    def test_categories_invalid_direction(self, mock_client: MagicMock) -> None:
        with pytest.raises(ValidationError):
            _do_get_categories(mock_client, "invalid")

    def test_categories_api_error(self, mock_client: MagicMock) -> None:
        mock_client.get_categories.return_value = None
        _assert_error(_do_get_categories(mock_client, "withdrawal"))

    def test_tags_success(self, mock_client: MagicMock) -> None:
        mock_client.get_tags.return_value = [{"name": "jedzenie"}]
        _assert_success(_do_get_tags(mock_client))

    def test_tags_api_error(self, mock_client: MagicMock) -> None:
        mock_client.get_tags.return_value = None
        _assert_error(_do_get_tags(mock_client))

    def test_currencies_success(self, mock_client: MagicMock) -> None:
        mock_client.get_currencies.return_value = [{"name": "PLN"}]
        _assert_success(_do_get_currencies(mock_client))

    def test_currencies_api_error(self, mock_client: MagicMock) -> None:
        mock_client.get_currencies.return_value = None
        _assert_error(_do_get_currencies(mock_client))


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

class TestBudgets:
    def test_list_success(self, mock_client: MagicMock) -> None:
        mock_client.get_budgets.return_value = [{"id": 1, "name": "Jedzenie"}]
        result = _do_list_budgets(mock_client, "01-06-2026")
        _assert_success(result)

    def test_list_api_error(self, mock_client: MagicMock) -> None:
        mock_client.get_budgets.return_value = None
        _assert_error(_do_list_budgets(mock_client))

    def test_create_success(self, mock_client: MagicMock) -> None:
        mock_client.create_budget.return_value = {"id": 10}
        result = _do_create_budget(mock_client, "300.00", category_id=5)
        _assert_success(result)

    def test_create_api_error(self, mock_client: MagicMock) -> None:
        mock_client.create_budget.return_value = None
        _assert_error(_do_create_budget(mock_client, "300.00"))

    def test_update_success(self, mock_client: MagicMock) -> None:
        mock_client.update_budget.return_value = {"id": 5, "limit": "700"}
        result = _do_update_budget(mock_client, 5, "700")
        _assert_success(result)

    def test_update_api_error(self, mock_client: MagicMock) -> None:
        mock_client.update_budget.return_value = None
        _assert_error(_do_update_budget(mock_client, 5, "500"))

    def test_delete_success(self, mock_client: MagicMock) -> None:
        mock_client.delete_budget.return_value = True
        _assert_success(_do_delete_budget(mock_client, 5))

    def test_delete_failure(self, mock_client: MagicMock) -> None:
        mock_client.delete_budget.return_value = False
        _assert_error(_do_delete_budget(mock_client, 5))

    def test_copy_success(self, mock_client: MagicMock) -> None:
        mock_client.copy_budgets_from_last_month.return_value = True
        _assert_success(_do_copy_budgets(mock_client))

    def test_copy_failure(self, mock_client: MagicMock) -> None:
        mock_client.copy_budgets_from_last_month.return_value = False
        _assert_error(_do_copy_budgets(mock_client))


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------

class TestSchedules:
    def test_list_success(self, mock_client: MagicMock) -> None:
        mock_client.get_scheduled_transactions.return_value = [{"schedule_id": 1}]
        result = _do_list_scheduled_transactions(mock_client, "unpaid")
        _assert_success(result)

    def test_list_api_error(self, mock_client: MagicMock) -> None:
        mock_client.get_scheduled_transactions.return_value = None
        _assert_error(_do_list_scheduled_transactions(mock_client, "unpaid"))

    def test_get_success(self, mock_client: MagicMock) -> None:
        mock_client.get_schedule.return_value = {"id": 1, "description": "Test"}
        result = _do_get_schedule(mock_client, 1)
        _assert_success(result)

    def test_get_api_error(self, mock_client: MagicMock) -> None:
        mock_client.get_schedule.return_value = None
        _assert_error(_do_get_schedule(mock_client, 1))

    def test_create_success(self, mock_client: MagicMock) -> None:
        mock_client.create_schedule.return_value = {"id": 10}
        result = _do_create_schedule(
            mock_client, "withdrawal", "15-06-2026", "1",
            "Netflix", "49.99", "PLN", "2",
        )
        _assert_success(result)

    def test_create_api_error(self, mock_client: MagicMock) -> None:
        mock_client.create_schedule.return_value = None
        _assert_error(_do_create_schedule(mock_client, "withdrawal", "15-06-2026", "1", "X", "10", "PLN", "1"))

    def test_update_success(self, mock_client: MagicMock) -> None:
        mock_client.update_schedule.return_value = {"id": 1}
        result = _do_update_schedule(mock_client, 1, description="Updated")
        _assert_success(result)

    def test_update_api_error(self, mock_client: MagicMock) -> None:
        mock_client.update_schedule.return_value = None
        _assert_error(_do_update_schedule(mock_client, 1))

    def test_delete_success(self, mock_client: MagicMock) -> None:
        mock_client.delete_schedule.return_value = True
        _assert_success(_do_delete_schedule(mock_client, 1))

    def test_delete_failure(self, mock_client: MagicMock) -> None:
        mock_client.delete_schedule.return_value = False
        _assert_error(_do_delete_schedule(mock_client, 1))

    def test_mark_paid_success(self, mock_client: MagicMock) -> None:
        mock_client.mark_schedule_paid.return_value = True
        result = _do_mark_schedule_paid(mock_client, 1, "10-06-2026")
        _assert_success(result)
        assert result["data"]["paid"] is True

    def test_mark_paid_failure(self, mock_client: MagicMock) -> None:
        mock_client.mark_schedule_paid.return_value = False
        _assert_error(_do_mark_schedule_paid(mock_client, 1, "10-06-2026"))

    def test_mark_unpaid_success(self, mock_client: MagicMock) -> None:
        mock_client.mark_schedule_unpaid.return_value = True
        result = _do_mark_schedule_unpaid(mock_client, 1, "10-06-2026")
        _assert_success(result)

    def test_mark_unpaid_failure(self, mock_client: MagicMock) -> None:
        mock_client.mark_schedule_unpaid.return_value = False
        _assert_error(_do_mark_schedule_unpaid(mock_client, 1, "10-06-2026"))


# ---------------------------------------------------------------------------
# Charts / Wealth
# ---------------------------------------------------------------------------

class TestChartsWealth:
    def test_pie_chart_success(self, mock_client: MagicMock) -> None:
        mock_client.get_pie_chart.return_value = {"type": "spendings", "data": []}
        result = _do_get_pie_chart(mock_client)
        _assert_success(result)

    def test_pie_chart_api_error(self, mock_client: MagicMock) -> None:
        mock_client.get_pie_chart.return_value = None
        _assert_error(_do_get_pie_chart(mock_client))

    def test_wealth_success(self, mock_client: MagicMock) -> None:
        mock_client.get_wealth_points.return_value = [{"id": 1, "amount": "50000"}]
        result = _do_get_wealth_points(mock_client, "01-01-2024", "31-12-2024")
        _assert_success(result)

    def test_wealth_api_error(self, mock_client: MagicMock) -> None:
        mock_client.get_wealth_points.return_value = None
        _assert_error(_do_get_wealth_points(mock_client))


# ---------------------------------------------------------------------------
# Write guard — disabled writes
# ---------------------------------------------------------------------------

class TestWriteGuard:
    def test_create_wallet_disabled(self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("kontomierz_mcp.tools.constants.ENABLE_WRITE_OPERATIONS", False)
        with pytest.raises(ValidationError, match="Write operations are disabled"):
            _do_create_wallet(mock_client, "100", "PLN")

    def test_create_transaction_disabled(self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("kontomierz_mcp.tools.constants.ENABLE_WRITE_OPERATIONS", False)
        with pytest.raises(ValidationError, match="Write operations are disabled"):
            _do_create_transaction(mock_client, "ts_1")
