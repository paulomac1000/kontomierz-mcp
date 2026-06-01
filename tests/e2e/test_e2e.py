"""E2E tests — full REST API pipeline for readonly tools. Skip if server not running."""

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


def _post(tool_name: str, **params: str) -> dict:
    import requests

    resp = requests.post(
        f"{BASE_URL}/api/tools/{tool_name}",
        json={"params": params},
        timeout=15,
    )
    return resp.json()


class TestE2EReadOnly:
    """Full end-to-end pipeline: REST API call -> tool execution -> response validation."""

    def test_list_accounts_pipeline(self) -> None:
        data = _post("list_accounts")
        assert "success" in data
        if data["success"] and data["data"]:
            first = data["data"][0]
            assert "id" in first
            assert "display_name" in first

    def test_list_transactions_pipeline(self) -> None:
        data = _post("list_transactions", page="1")
        assert "success" in data
        if data["success"] and data["data"]:
            txs = data["data"].get("transactions", data["data"])
            if txs:
                assert "description" in txs[0]

    def test_list_categories_pipeline(self) -> None:
        for direction in ("withdrawal", "deposit"):
            data = _post("list_categories", direction=direction)
            assert "success" in data

    def test_list_tags_pipeline(self) -> None:
        data = _post("list_tags")
        assert "success" in data

    def test_list_currencies_pipeline(self) -> None:
        data = _post("list_currencies")
        assert "success" in data

    def test_list_budgets_pipeline(self) -> None:
        data = _post("list_budgets")
        assert "success" in data

    def test_list_scheduled_transactions_pipeline(self) -> None:
        for group in ("unpaid", "paid"):
            data = _post("list_scheduled_transactions", schedule_group_name=group)
            assert "success" in data

    def test_get_pie_chart_pipeline(self) -> None:
        data = _post("get_pie_chart")
        assert "success" in data

    def test_list_wealth_points_pipeline(self) -> None:
        data = _post("list_wealth_points")
        assert "success" in data

    def test_get_transaction_workflow(self) -> None:
        """Get transaction list, then fetch first transaction details."""
        txs = _post("list_transactions", page="1")
        if txs.get("success") and txs.get("data"):
            tx_list = txs["data"].get("transactions", txs["data"])
            if tx_list:
                tx_id = tx_list[0].get("id")
            if tx_id:
                detail = _post("get_transaction", transaction_id=str(tx_id))
                assert "success" in detail

    def test_get_schedule_workflow(self) -> None:
        """Get schedule list, then fetch first schedule details."""
        schedules = _post("list_scheduled_transactions", schedule_group_name="unpaid")
        if schedules.get("success") and schedules.get("data"):
            sched_id = schedules["data"][0].get("schedule_id")
            if sched_id:
                detail = _post("get_schedule", schedule_id=str(sched_id))
                assert "success" in detail


class TestSuccessCriteria:
    """Explicit success/failure criteria for E2E tests."""

    def test_all_readonly_tools_respond_within_timeout(self) -> None:
        import time

        import requests

        for tool_name in ["list_accounts", "list_tags", "list_currencies", "list_categories", "list_budgets"]:
            t0 = time.monotonic()
            try:
                resp = requests.post(
                    f"{BASE_URL}/api/tools/{tool_name}",
                    json={"params": {}},
                    timeout=15,
                )
                elapsed = time.monotonic() - t0
                data = resp.json()
                assert elapsed < 30, f"{tool_name} took {elapsed:.1f}s (exceeds 30s timeout)"
                assert "success" in data
            except requests.exceptions.Timeout:
                pytest.fail(f"{tool_name} timed out after 15s")

    def test_response_format_consistent(self) -> None:
        """Every successful response must have the same contract."""
        for tool_name in ["list_accounts", "list_tags", "list_currencies"]:
            data = _post(tool_name)
            assert isinstance(data, dict)
            if data.get("success") is True:
                assert "data" in data
            elif data.get("success") is False:
                assert "error" in data
