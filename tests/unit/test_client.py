from __future__ import annotations

from typing import Any

import pytest
import requests

from kontomierz_mcp.client import KontomierzClient
from kontomierz_mcp.errors import ErrorCode, UpstreamError


class Response:
    def __init__(self, status: int = 200, payload: Any = None, headers: dict[str, str] | None = None) -> None:
        self.status_code = status
        self._payload = {} if payload is None else payload
        self.headers = headers or {}

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class Session:
    def __init__(self, response: Response | Exception) -> None:
        self.headers: dict[str, str] = {}
        self.response = response
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, **kwargs: Any) -> Response:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def close(self) -> None:
        self.closed = True


def make_client(response: Response | Exception, *, body_mode: str = "json") -> tuple[KontomierzClient, Session]:
    session = Session(response)
    adapter = KontomierzClient(
        api_key="secret",
        base_url="https://example.invalid/k4",
        timeout_seconds=3,
        body_mode=body_mode,
        session=session,
    )
    return adapter, session


def test_update_endpoints_use_put_and_json() -> None:
    adapter, session = make_client(Response(payload={"money_transaction": {"id": 7}}))
    adapter.update_money_transaction(7, name="updated")
    call = session.calls[0]
    assert call["method"] == "PUT"
    assert call["json"] == {"money_transaction[name]": "updated"}
    assert call["params"] == {"api_key": "secret"}


def test_form_mode_is_explicit_compatibility_path() -> None:
    adapter, session = make_client(Response(payload={"budget": {"id": 3}}), body_mode="form")
    adapter.update_budget(3, "100.00")
    assert session.calls[0]["data"] == {"budget[limit]": "100.00"}


def test_bodiless_mutation_sends_no_fake_payload() -> None:
    adapter, session = make_client(Response(status=204))
    assert adapter.copy_budgets_from_last_month() is True
    assert "json" not in session.calls[0]
    assert "data" not in session.calls[0]


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, ErrorCode.AUTHENTICATION_FAILED, False),
        (404, ErrorCode.RESOURCE_NOT_FOUND, False),
        (429, ErrorCode.RATE_LIMITED, True),
        (503, ErrorCode.DEPENDENCY_UNAVAILABLE, True),
    ],
)
def test_http_status_mapping(status: int, code: ErrorCode, retryable: bool) -> None:
    adapter, _ = make_client(Response(status=status))
    with pytest.raises(UpstreamError) as raised:
        adapter.get_tags()
    assert raised.value.code == code
    assert raised.value.retryable is retryable


def test_network_timeout_is_typed() -> None:
    adapter, _ = make_client(requests.Timeout("late"))
    with pytest.raises(UpstreamError) as raised:
        adapter.get_tags()
    assert raised.value.code == ErrorCode.TIMEOUT


def test_invalid_json_is_typed() -> None:
    adapter, _ = make_client(Response(payload=ValueError("bad json")))
    with pytest.raises(UpstreamError) as raised:
        adapter.get_tags()
    assert raised.value.code == ErrorCode.UPSTREAM_FAILURE


class RoutingSession(Session):
    """Return endpoint-shaped payloads while recording the complete HTTP contract."""

    def __init__(self) -> None:
        super().__init__(Response())

    def request(self, **kwargs: Any) -> Response:
        self.calls.append(kwargs)
        path = kwargs["url"].split("/k4/", 1)[-1]
        method = kwargs["method"]
        if method == "DELETE" or "mark_as_" in path or path.endswith("copy_from_last_to_present_month.json"):
            return Response(status=204)
        if path == "user_accounts.json":
            return Response(payload=[{"user_account": {"id": 1}}])
        if "user_accounts" in path:
            return Response(payload={"user_account": {"id": 1}})
        if path == "money_transactions.json" and method == "GET":
            return Response(payload={"money_transactions": [{"id": 2}]})
        if "money_transactions" in path and not path.startswith("charts/"):
            return Response(payload={"money_transaction": {"id": 2}})
        if path == "categories.json":
            return Response(payload={"category_groups": [{"id": 3}]})
        if path == "tags.json":
            return Response(payload={"tags": [{"id": 4}]})
        if path == "currencies.json":
            return Response(payload={"currencies": [{"id": 5}]})
        if path == "budgets.json" and method == "GET":
            return Response(payload={"budgets": [{"id": 6}]})
        if "budgets" in path:
            return Response(payload={"budget": {"id": 6}})
        if path == "scheduled_transactions.json":
            return Response(payload={"scheduled_transactions": [{"id": 7}]})
        if "schedules" in path:
            return Response(payload={"schedule": {"id": 7}})
        if path == "wealth_points.json":
            return Response(payload={"wealth_points": [{"id": 8}]})
        if path == "charts/money_transactions.json":
            return Response(payload={"chart_kind": "pie", "data": []})
        raise AssertionError(f"Unhandled route: {method} {path}")


def test_complete_endpoint_contract_uses_documented_methods_and_paths() -> None:
    session = RoutingSession()
    adapter = KontomierzClient(
        api_key="secret",
        base_url="https://example.invalid/k4",
        timeout_seconds=3,
        session=session,
    )
    assert adapter.get_user_accounts() == [{"id": 1}]
    adapter.create_wallet("1", "PLN", "Wallet")
    adapter.update_wallet(1, user_name="Updated")
    adapter.destroy_wallet(1)
    adapter.get_money_transactions(page=1)
    adapter.get_money_transaction(2)
    adapter.create_money_transaction(client_assigned_id="id")
    adapter.update_money_transaction(2, name="Updated")
    adapter.delete_money_transaction(2)
    adapter.get_categories("withdrawal")
    adapter.get_tags()
    adapter.get_currencies()
    adapter.get_budgets("01-08-2026")
    adapter.create_budget("100", category_id=3, month_on="01-08-2026")
    adapter.create_budget("100", category_group_id=4)
    adapter.update_budget(6, "200")
    adapter.delete_budget(6)
    adapter.copy_budgets_from_last_month()
    adapter.get_scheduled_transactions(schedule_group_name="unpaid")
    adapter.get_schedule(7)
    adapter.create_schedule(description="Mock")
    adapter.update_schedule(7, description="Updated")
    adapter.delete_schedule(7)
    adapter.mark_schedule_paid(7, "06-08-2026")
    adapter.mark_schedule_unpaid(7, "06-08-2026")
    adapter.get_wealth_points("01-08-2026", "31-08-2026")
    adapter.get_pie_chart(chart_kind="pie")
    adapter.close()

    contracts = {(call["method"], call["url"].split("/k4/", 1)[-1]) for call in session.calls}
    assert ("PUT", "user_accounts/1/update_wallet.json") in contracts
    assert ("PUT", "money_transactions/2.json") in contracts
    assert ("PUT", "budgets/6.json") in contracts
    assert ("PUT", "schedules/7.json") in contracts
    assert session.closed is True


def test_invalid_response_shapes_fail_closed() -> None:
    adapter, _ = make_client(Response(payload="not-json-object"))
    with pytest.raises(UpstreamError):
        adapter.get_tags()
    adapter, _ = make_client(Response(payload={"tags": ["wrong"]}))
    with pytest.raises(UpstreamError):
        adapter.get_tags()
    adapter, _ = make_client(Response(payload={"user_account": []}))
    with pytest.raises(UpstreamError):
        adapter.create_wallet("1", "PLN")
