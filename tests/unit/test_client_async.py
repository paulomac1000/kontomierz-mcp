from __future__ import annotations

import httpx
import pytest

from kontomierz_mcp.client import KontomierzClient
from kontomierz_mcp.errors import ErrorCode, UpstreamError


def make_client(handler, *, body_mode: str = "form") -> KontomierzClient:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return KontomierzClient(
        api_key="secret",
        base_url="https://example.test/k4",
        timeout_seconds=1,
        body_mode=body_mode,
        client=client,
    )


@pytest.mark.asyncio
async def test_read_timeout_is_retryable_and_not_write_ambiguous() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("late")

    client = make_client(handler)
    with pytest.raises(UpstreamError) as captured:
        await client.get_user_accounts()
    assert captured.value.code is ErrorCode.TIMEOUT
    assert captured.value.retryable is True
    assert captured.value.write_outcome_ambiguous is False


@pytest.mark.asyncio
async def test_write_timeout_is_ambiguous_and_not_retryable() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("late")

    client = make_client(handler)
    with pytest.raises(UpstreamError) as captured:
        await client.create_wallet("0", "PLN")
    assert captured.value.code is ErrorCode.TIMEOUT
    assert captured.value.retryable is False
    assert captured.value.write_outcome_ambiguous is True


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [httpx.ConnectError("down"), httpx.ReadError("reset")])
async def test_write_transport_error_is_ambiguous(failure: Exception) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise failure

    client = make_client(handler)
    with pytest.raises(UpstreamError) as captured:
        await client.update_budget(1, "10")
    assert captured.value.code is ErrorCode.DEPENDENCY_UNAVAILABLE
    assert captured.value.retryable is False
    assert captured.value.write_outcome_ambiguous is True


@pytest.mark.asyncio
async def test_write_503_is_ambiguous() -> None:
    client = make_client(lambda _request: httpx.Response(503, json={"error": "down"}))
    with pytest.raises(UpstreamError) as captured:
        await client.mark_schedule_paid(1, "01-08-2026")
    assert captured.value.code is ErrorCode.DEPENDENCY_UNAVAILABLE
    assert captured.value.write_outcome_ambiguous is True


@pytest.mark.asyncio
async def test_write_429_is_not_ambiguous_and_preserves_retry_after() -> None:
    client = make_client(lambda _request: httpx.Response(429, headers={"Retry-After": "3"}))
    with pytest.raises(UpstreamError) as captured:
        await client.create_budget("10", category_id=1)
    assert captured.value.code is ErrorCode.RATE_LIMITED
    assert captured.value.retryable is False
    assert captured.value.write_outcome_ambiguous is False
    assert captured.value.details == {"retry_after": "3"}


@pytest.mark.asyncio
async def test_put_uses_form_and_preserves_empty_clear_value() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"user_account": {"id": 1, "user_name": ""}})

    client = make_client(handler)
    result = await client.update_wallet(1, user_name="")
    assert result["user_name"] == ""
    assert seen[0].method == "PUT"
    assert seen[0].headers["content-type"].startswith("application/x-www-form-urlencoded")
    assert "user_account%5Buser_name%5D=" in seen[0].content.decode()


@pytest.mark.asyncio
async def test_explicit_json_body_mode_remains_supported() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"user_account": {"id": 1}})

    client = make_client(handler, body_mode="json")
    await client.update_wallet(1, user_name="x")
    assert seen[0].headers["content-type"].startswith("application/json")
    assert b'"user_account[user_name]":"x"' in seen[0].content


@pytest.mark.asyncio
async def test_empty_schedule_create_requires_explicit_reconciliation() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(201)

    client = make_client(handler)
    result = await client.create_schedule(description="Rent", currency_amount="1.00")
    assert result == {"created": True, "reconciliation_required": True}
    assert [call.method for call in calls] == ["POST"]


@pytest.mark.asyncio
async def test_empty_budget_create_does_not_guess_existing_resource_identity() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(201)

    client = make_client(handler)
    result = await client.create_budget("1.00", category_id=3)
    assert result == {"created": True, "reconciliation_required": True}
    assert [call.method for call in calls] == ["POST"]


@pytest.mark.asyncio
async def test_empty_update_body_is_success_marker() -> None:
    client = make_client(lambda _request: httpx.Response(200))
    result = await client.update_schedule(7, description="x")
    assert result == {"updated": True, "schedule_id": 7}


@pytest.mark.asyncio
async def test_empty_budget_update_is_success_marker() -> None:
    client = make_client(lambda _request: httpx.Response(200))
    result = await client.update_budget(9, "2.00")
    assert result == {"updated": True}


@pytest.mark.asyncio
async def test_empty_transaction_create_is_success_marker() -> None:
    client = make_client(lambda _request: httpx.Response(201))
    result = await client.create_money_transaction(client_assigned_id="x")
    assert result == {"created": True, "reconciliation_required": True}


@pytest.mark.asyncio
async def test_wealth_points_unwrap_per_item_wrapper() -> None:
    client = make_client(
        lambda _request: httpx.Response(
            200,
            json=[{"wealth_point": {"id": 5, "date_on": "2026-08-01", "amount": "1.00", "notes": None}}],
        )
    )
    assert await client.get_wealth_points() == [{"id": 5, "date_on": "2026-08-01", "amount": "1.00", "notes": None}]


@pytest.mark.asyncio
async def test_probe_returns_false_on_dependency_error() -> None:
    client = make_client(lambda _request: httpx.Response(503))
    assert await client.probe() is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"unexpected": {"id": 1}},
        {"user_account": []},
        {"user_account": "wrong"},
    ],
)
async def test_successful_write_with_unusable_response_is_ambiguous(payload: object) -> None:
    client = make_client(lambda _request: httpx.Response(200, json=payload))
    with pytest.raises(UpstreamError) as captured:
        await client.create_wallet("0", "PLN")
    assert captured.value.code is ErrorCode.UPSTREAM_FAILURE
    assert captured.value.retryable is False
    assert captured.value.write_outcome_ambiguous is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "wrapper"),
    [
        (lambda client: client.create_money_transaction(client_assigned_id="x"), "money_transaction"),
        (lambda client: client.update_budget(1, "10"), "budget"),
        (lambda client: client.create_schedule(description="x"), "schedule"),
    ],
)
async def test_every_object_mutation_marks_wrong_wrapper_type_ambiguous(operation, wrapper: str) -> None:
    client = make_client(lambda _request: httpx.Response(200, json={wrapper: []}))
    with pytest.raises(UpstreamError) as captured:
        await operation(client)
    assert captured.value.write_outcome_ambiguous is True
