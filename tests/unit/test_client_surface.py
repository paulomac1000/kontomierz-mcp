from __future__ import annotations

import httpx
import pytest

from kontomierz_mcp.client import KontomierzClient
from kontomierz_mcp.errors import ErrorCode, UpstreamError


def response_for(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    method = request.method
    if method == "DELETE" or "mark_as_" in path or "copy_from_last" in path:
        return httpx.Response(204)
    if path.endswith("user_accounts.json"):
        return httpx.Response(200, json=[{"user_account": {"id": 1}}])
    if "user_accounts" in path:
        return httpx.Response(200, json={"user_account": {"id": 1}})
    if path.endswith("charts/money_transactions.json"):
        return httpx.Response(200, json={"series": []})
    if path.endswith("money_transactions.json") and method == "GET":
        return httpx.Response(200, json={"money_transactions": [{"id": 2}]})
    if "money_transactions" in path:
        return httpx.Response(200, json={"money_transaction": {"id": 2}})
    if path.endswith("categories.json"):
        return httpx.Response(200, json={"category_groups": []})
    if path.endswith("tags.json"):
        return httpx.Response(200, json={"tags": []})
    if path.endswith("currencies.json"):
        return httpx.Response(200, json={"currencies": [{"name": "PLN"}]})
    if path.endswith("budgets.json") and method == "GET":
        return httpx.Response(200, json={"budgets": [{"id": 3}]})
    if "budgets" in path:
        return httpx.Response(200, json={"budget": {"id": 3}})
    if path.endswith("scheduled_transactions.json"):
        return httpx.Response(200, json={"scheduled_transactions": [{"id": 4}]})
    if "schedules" in path:
        return httpx.Response(200, json={"schedule": {"id": 4}})
    if path.endswith("wealth_points.json"):
        return httpx.Response(200, json={"wealth_points": [{"id": 5}]})
    raise AssertionError(f"Unhandled request: {method} {path}")


def make_surface_client(*, body_mode: str = "json") -> KontomierzClient:
    return KontomierzClient(
        api_key="secret",
        base_url="https://example.test/k4",
        timeout_seconds=1,
        body_mode=body_mode,
        client=httpx.AsyncClient(transport=httpx.MockTransport(response_for)),
    )


@pytest.mark.asyncio
async def test_full_http_adapter_surface() -> None:
    client = make_surface_client()
    assert await client.probe() is True
    assert await client.get_user_accounts() == [{"id": 1}]
    assert await client.create_wallet("0", "PLN", "", "1") == {"id": 1}
    assert await client.update_wallet(1, user_name="") == {"id": 1}
    assert await client.destroy_wallet(1) is True
    assert await client.get_money_transactions(page=1) == [{"id": 2}]
    assert await client.get_money_transaction(2) == {"id": 2}
    assert await client.create_money_transaction(name="") == {"id": 2}
    assert await client.update_money_transaction(2, name="") == {"id": 2}
    assert await client.delete_money_transaction(2) is True
    assert await client.get_categories("withdrawal") == []
    assert await client.get_tags() == []
    assert await client.get_currencies() == [{"name": "PLN"}]
    assert await client.get_budgets("01-08-2026") == [{"id": 3}]
    assert await client.create_budget("10", category_id=1, month_on="01-08-2026") == {"id": 3}
    assert await client.create_budget("10", category_group_id=2) == {"id": 3}
    assert await client.update_budget(3, "20") == {"id": 3}
    assert await client.delete_budget(3) is True
    assert await client.copy_budgets_from_last_month() is True
    assert await client.get_scheduled_transactions(page=1) == [{"id": 4}]
    assert await client.get_schedule(4) == {"id": 4}
    assert await client.create_schedule(description="") == {"id": 4}
    assert await client.update_schedule(4, description="") == {"id": 4}
    assert await client.delete_schedule(4) is True
    assert await client.mark_schedule_paid(4, "01-08-2026") is True
    assert await client.mark_schedule_unpaid(4, "01-08-2026") is True
    assert await client.get_wealth_points() == [{"id": 5}]
    assert await client.get_pie_chart() == {"series": []}
    await client._client.aclose()


@pytest.mark.asyncio
async def test_form_body_mode_is_supported_without_dropping_empty_values() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"money_transaction": {"id": 2}})

    client = KontomierzClient(
        api_key="secret",
        base_url="https://example.test/k4",
        timeout_seconds=1,
        body_mode="form",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await client.update_money_transaction(2, name="")
    assert seen[0].headers["content-type"].startswith("application/x-www-form-urlencoded")
    assert "money_transaction%5Bname%5D=" in seen[0].content.decode()
    await client._client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, ErrorCode.AUTHENTICATION_FAILED),
        (403, ErrorCode.AUTHENTICATION_FAILED),
        (404, ErrorCode.RESOURCE_NOT_FOUND),
        (409, ErrorCode.CONFLICT),
        (422, ErrorCode.CONFLICT),
        (400, ErrorCode.UPSTREAM_FAILURE),
    ],
)
async def test_http_status_mapping(status: int, code: ErrorCode) -> None:
    client = KontomierzClient(
        api_key="secret",
        base_url="https://example.test/k4",
        timeout_seconds=1,
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(status))),
    )
    with pytest.raises(UpstreamError) as captured:
        await client.get_tags()
    assert captured.value.code is code
    await client._client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json", headers={"content-type": "application/json"}),
        httpx.Response(200, json="primitive"),
    ],
)
async def test_invalid_json_shapes_are_rejected(response: httpx.Response) -> None:
    client = KontomierzClient(
        api_key="secret",
        base_url="https://example.test/k4",
        timeout_seconds=1,
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: response)),
    )
    with pytest.raises(UpstreamError) as captured:
        await client.get_tags()
    assert captured.value.code is ErrorCode.UPSTREAM_FAILURE
    await client._client.aclose()


@pytest.mark.asyncio
async def test_owned_async_client_is_closed() -> None:
    client = KontomierzClient(api_key="secret", base_url="https://example.test/k4", timeout_seconds=1)
    await client.close()
    assert client._client.is_closed is True


@pytest.mark.asyncio
async def test_accounts_response_does_not_silently_drop_invalid_items() -> None:
    client = KontomierzClient(
        api_key="secret",
        base_url="https://example.test/k4",
        timeout_seconds=1,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=[{"user_account": []}]))
        ),
    )
    with pytest.raises(UpstreamError):
        await client.get_user_accounts()
    await client._client.aclose()
