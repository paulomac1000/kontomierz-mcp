"""Unit tests for KontomierzClient — all 26 API endpoints, zero I/O."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from kontomierz_mcp.client import KontomierzClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> KontomierzClient:
    """Client with fake credentials (no real I/O)."""
    return KontomierzClient(
        api_key="test_key_12345",
        username="test@example.com",
        password="secret123",
        timeout=10,
    )


def _mock_response(json_data: Any, status_code: int = 200) -> MagicMock:
    """Build a requests.Response mock with .json() and .raise_for_status()."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    if 200 <= status_code < 300:
        resp.raise_for_status = MagicMock()
    else:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(f"{status_code}")
    return resp


def _assert_auth(kwargs: dict) -> None:
    """Verify that BasicAuth and api_key are present in request kwargs."""
    assert kwargs["auth"].username == "test@example.com"
    assert kwargs["auth"].password == "secret123"
    assert kwargs["params"]["api_key"] == "test_key_12345"


# ---------------------------------------------------------------------------
# get_user_accounts
# ---------------------------------------------------------------------------

class TestGetUserAccounts:
    def test_success(self, client: KontomierzClient) -> None:
        payload = [
            {"user_account": {"id": 1, "display_name": "Konto A", "currency_name": "PLN"}},
            {"user_account": {"id": 2, "display_name": "Portfel B", "currency_name": "EUR"}},
        ]
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)) as mock_get:
            result = client.get_user_accounts()

        assert result is not None
        assert len(result) == 2
        assert result[0]["display_name"] == "Konto A"
        assert result[1]["display_name"] == "Portfel B"
        _assert_auth(mock_get.call_args.kwargs)

    def test_api_error_returns_none(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.get_user_accounts() is None


# ---------------------------------------------------------------------------
# create_wallet
# ---------------------------------------------------------------------------

class TestCreateWallet:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"user_account": {"id": 99, "display_name": "My Wallet"}}
        with patch("kontomierz_mcp.client.requests.post", return_value=_mock_response(payload)) as mock_post:
            result = client.create_wallet("100.00", "PLN", user_name="My Wallet")

        assert result is not None
        assert result["id"] == 99
        data = mock_post.call_args.kwargs["data"]
        assert data["user_account[currency_balance]"] == "100.00"
        assert data["user_account[currency_name]"] == "PLN"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.post", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.create_wallet("100.00", "PLN") is None


# ---------------------------------------------------------------------------
# update_wallet
# ---------------------------------------------------------------------------

class TestUpdateWallet:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"user_account": {"id": 10, "display_name": "Updated"}}
        with patch("kontomierz_mcp.client.requests.post", return_value=_mock_response(payload)):
            result = client.update_wallet(10, user_name="Updated", currency_balance="200.00")

        assert result is not None
        assert result["display_name"] == "Updated"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.post", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.update_wallet(10) is None


# ---------------------------------------------------------------------------
# destroy_wallet
# ---------------------------------------------------------------------------

class TestDestroyWallet:
    def test_success(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.delete", return_value=_mock_response({})):
            assert client.destroy_wallet(1) is True

    def test_failure(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.delete", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.destroy_wallet(1) is False


# ---------------------------------------------------------------------------
# get_money_transactions
# ---------------------------------------------------------------------------

class TestGetMoneyTransactions:
    RESPONSE = [
        {"id": 1, "description": "Zakupy spozywcze", "currency_amount": "-45.90"},
        {"id": 2, "description": "Wynagrodzenie", "currency_amount": "5000.00"},
    ]

    def test_success_list(self, client: KontomierzClient) -> None:
        payload = {"money_transactions": self.RESPONSE}
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)):
            result = client.get_money_transactions(page=1, per_page=50, direction="all")

        assert result is not None
        assert len(result) == 2
        assert result[0]["description"] == "Zakupy spozywcze"

    def test_with_filters(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response({"money_transactions": []})) as mock_get:
            client.get_money_transactions(
                start_on="01-01-2024", end_on="31-01-2024",
                direction="withdrawals", tag_name="jedzenie", category_group_id=5,
                q="mleko", show_hidden_transactions="true",
            )

        params = mock_get.call_args.kwargs["params"]
        assert params["start_on"] == "01-01-2024"
        assert params["direction"] == "withdrawals"
        assert params["tag_name"] == "jedzenie"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.get_money_transactions() is None


# ---------------------------------------------------------------------------
# get_money_transaction (singular)
# ---------------------------------------------------------------------------

class TestGetMoneyTransaction:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"money_transaction": {"id": 5, "description": "Kawa"}}
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)):
            result = client.get_money_transaction(5)

        assert result is not None
        assert result["description"] == "Kawa"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.get_money_transaction(5) is None


# ---------------------------------------------------------------------------
# create_money_transaction
# ---------------------------------------------------------------------------

class TestCreateMoneyTransaction:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"money_transaction": {"id": 100, "description": "Nowy wydatek"}}
        with patch("kontomierz_mcp.client.requests.post", return_value=_mock_response(payload)) as mock_post:
            result = client.create_money_transaction(
                client_assigned_id="ts_123",
                currency_amount="99.99",
                currency_name="PLN",
                direction="withdrawal",
                name="Nowy wydatek",
                transaction_on="15-06-2026",
            )

        assert result is not None
        assert result["id"] == 100
        data = mock_post.call_args.kwargs["data"]
        assert data["money_transaction[client_assigned_id]"] == "ts_123"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.post", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.create_money_transaction("ts_123") is None


# ---------------------------------------------------------------------------
# update_money_transaction
# ---------------------------------------------------------------------------

class TestUpdateMoneyTransaction:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"money_transaction": {"id": 5, "description": "Updated"}}
        with patch("kontomierz_mcp.client.requests.post", return_value=_mock_response(payload)):
            result = client.update_money_transaction(5, name="Updated")

        assert result is not None
        assert result["description"] == "Updated"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.post", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.update_money_transaction(5) is None


# ---------------------------------------------------------------------------
# delete_money_transaction
# ---------------------------------------------------------------------------

class TestDeleteMoneyTransaction:
    def test_success(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.delete", return_value=_mock_response({})):
            assert client.delete_money_transaction(5) is True

    def test_failure(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.delete", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.delete_money_transaction(5) is False


# ---------------------------------------------------------------------------
# get_categories
# ---------------------------------------------------------------------------

class TestGetCategories:
    def test_success_withdrawal(self, client: KontomierzClient) -> None:
        payload = {"categories": [{"id": 1, "name": "Zakupy", "children": []}]}
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)):
            result = client.get_categories("withdrawal")

        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "Zakupy"

    def test_success_deposit(self, client: KontomierzClient) -> None:
        payload = {"categories": [{"id": 2, "name": "Wyplata"}]}
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)):
            result = client.get_categories("deposit")
        assert result is not None
        assert result[0]["name"] == "Wyplata"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.get_categories("withdrawal") is None


# ---------------------------------------------------------------------------
# get_tags
# ---------------------------------------------------------------------------

class TestGetTags:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"tags": [{"id": 1, "name": "jedzenie"}, {"id": 2, "name": "zdrowie"}]}
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)):
            result = client.get_tags()

        assert result is not None
        assert len(result) == 2

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.get_tags() is None


# ---------------------------------------------------------------------------
# get_budgets
# ---------------------------------------------------------------------------

class TestGetBudgets:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"budgets": [{"id": 1, "name": "Jedzenie", "limit": "500.00", "amount": "200.00"}]}
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)):
            result = client.get_budgets("01-06-2026")

        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "Jedzenie"

    def test_no_month_on(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response({"budgets": []})) as mock_get:
            client.get_budgets()

        params = mock_get.call_args.kwargs["params"]
        assert params.get("month_on") is None

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.get_budgets() is None


# ---------------------------------------------------------------------------
# create_budget
# ---------------------------------------------------------------------------

class TestCreateBudget:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"budget": {"id": 10, "limit": "300.00"}}
        with patch("kontomierz_mcp.client.requests.post", return_value=_mock_response(payload)) as mock_post:
            result = client.create_budget("300.00", category_id=5)

        assert result is not None
        assert result["id"] == 10
        data = mock_post.call_args.kwargs["data"]
        assert data["budget[limit]"] == "300.00"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.post", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.create_budget("300.00") is None


# ---------------------------------------------------------------------------
# update_budget
# ---------------------------------------------------------------------------

class TestUpdateBudget:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"budget": {"id": 5, "limit": "700.00"}}
        with patch("kontomierz_mcp.client.requests.post", return_value=_mock_response(payload)):
            result = client.update_budget(5, "700.00")

        assert result is not None
        assert result["limit"] == "700.00"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.post", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.update_budget(5, "500.00") is None


# ---------------------------------------------------------------------------
# delete_budget
# ---------------------------------------------------------------------------

class TestDeleteBudget:
    def test_success(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.delete", return_value=_mock_response({})):
            assert client.delete_budget(5) is True

    def test_failure(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.delete", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.delete_budget(5) is False


# ---------------------------------------------------------------------------
# copy_budgets_from_last_month
# ---------------------------------------------------------------------------

class TestCopyBudgets:
    def test_success(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.post", return_value=_mock_response({"status": "ok"})):
            assert client.copy_budgets_from_last_month() is True

    def test_failure(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.post", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.copy_budgets_from_last_month() is False


# ---------------------------------------------------------------------------
# get_scheduled_transactions
# ---------------------------------------------------------------------------

class TestGetScheduledTransactions:
    def test_success_unpaid(self, client: KontomierzClient) -> None:
        payload = {"scheduled_transactions": [
            {"schedule_id": 1, "description": "Czynsz", "currency_amount": "-1200.00"}
        ]}
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)):
            result = client.get_scheduled_transactions("unpaid")

        assert result is not None
        assert len(result) == 1
        assert result[0]["description"] == "Czynsz"

    def test_success_paid(self, client: KontomierzClient) -> None:
        payload = {"scheduled_transactions": []}
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)):
            result = client.get_scheduled_transactions("paid")
        assert result == []

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.get_scheduled_transactions("unpaid") is None


# ---------------------------------------------------------------------------
# get_schedule (singular)
# ---------------------------------------------------------------------------

class TestGetSchedule:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"schedule": {"id": 1, "description": "Czynsz", "next-deadline-on": "10-06-2026"}}
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)):
            result = client.get_schedule(1)

        assert result is not None
        assert result["description"] == "Czynsz"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.get_schedule(1) is None


# ---------------------------------------------------------------------------
# create_schedule
# ---------------------------------------------------------------------------

class TestCreateSchedule:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"schedule": {"id": 10, "description": "Abonament Netflix"}}
        with patch("kontomierz_mcp.client.requests.post", return_value=_mock_response(payload)) as mock_post:
            result = client.create_schedule(
                direction="withdrawal", deadline_on="15-06-2026", holidays="1",
                description="Abonament Netflix", currency_amount="49.99",
                currency_name="PLN", repeat="2",
            )

        assert result is not None
        assert result["description"] == "Abonament Netflix"
        data = mock_post.call_args.kwargs["data"]
        assert data["schedule[repeat]"] == "2"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.post", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.create_schedule("withdrawal", "15-06-2026", "1", "Test", "10", "PLN", "1") is None


# ---------------------------------------------------------------------------
# update_schedule
# ---------------------------------------------------------------------------

class TestUpdateSchedule:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"schedule": {"id": 1, "description": "Updated"}}
        with patch("kontomierz_mcp.client.requests.post", return_value=_mock_response(payload)):
            result = client.update_schedule(1, description="Updated")

        assert result is not None
        assert result["description"] == "Updated"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.post", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.update_schedule(1) is None


# ---------------------------------------------------------------------------
# delete_schedule
# ---------------------------------------------------------------------------

class TestDeleteSchedule:
    def test_success(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.delete", return_value=_mock_response({})):
            assert client.delete_schedule(1) is True

    def test_failure(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.delete", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.delete_schedule(1) is False


# ---------------------------------------------------------------------------
# mark_schedule_paid / unpaid
# ---------------------------------------------------------------------------

class TestMarkSchedulePaid:
    def test_success(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.put", return_value=_mock_response({})):
            assert client.mark_schedule_paid(1, "10-06-2026") is True

    def test_failure(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.put", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.mark_schedule_paid(1, "10-06-2026") is False


class TestMarkScheduleUnpaid:
    def test_success(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.put", return_value=_mock_response({})):
            assert client.mark_schedule_unpaid(1, "10-06-2026") is True

    def test_failure(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.put", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.mark_schedule_unpaid(1, "10-06-2026") is False


# ---------------------------------------------------------------------------
# get_wealth_points
# ---------------------------------------------------------------------------

class TestGetWealthPoints:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"wealth_points": [
            {"id": 1, "date-on": "01-06-2026", "amount": "50000.00"},
        ]}
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)):
            result = client.get_wealth_points("01-01-2024", "31-12-2024")

        assert result is not None
        assert len(result) == 1
        assert result[0]["amount"] == "50000.00"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.get_wealth_points() is None


# ---------------------------------------------------------------------------
# get_pie_chart
# ---------------------------------------------------------------------------

class TestGetPieChart:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {
            "type": "spendings-in-category-groups",
            "data": [{"name": "Zakupy", "y": 500.00, "color": "#ff0000"}],
        }
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)):
            result = client.get_pie_chart(chart_kind="pie", direction="withdrawals")

        assert result is not None
        assert result["type"] == "spendings-in-category-groups"
        assert len(result["data"]) == 1

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.get_pie_chart() is None


# ---------------------------------------------------------------------------
# get_currencies
# ---------------------------------------------------------------------------

class TestGetCurrencies:
    def test_success(self, client: KontomierzClient) -> None:
        payload = {"currencies": [
            {"id": 1, "name": "PLN", "importance": "major"},
            {"id": 2, "name": "EUR", "importance": "major"},
        ]}
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response(payload)):
            result = client.get_currencies()

        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "PLN"

    def test_api_error(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", side_effect=requests.exceptions.ConnectionError("no net")):
            assert client.get_currencies() is None


# ---------------------------------------------------------------------------
# Rate-limit / 401 / 422 error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_401_returns_none(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", return_value=_mock_response({}, 401)):
            assert client.get_user_accounts() is None

    def test_422_returns_none(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.post", return_value=_mock_response({}, 422)):
            assert client.create_wallet("w", "PLN") is None

    def test_timeout(self, client: KontomierzClient) -> None:
        with patch("kontomierz_mcp.client.requests.get", side_effect=requests.exceptions.Timeout("too slow")):
            assert client.get_user_accounts() is None
