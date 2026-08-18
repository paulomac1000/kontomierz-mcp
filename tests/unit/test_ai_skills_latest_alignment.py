from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import pytest

from kontomierz_mcp.client import KontomierzClient
from kontomierz_mcp.errors import ErrorCode, UpstreamError
from kontomierz_mcp.mock_backend import MockKontomierzClient
from kontomierz_mcp.operation_support import date_range, date_value, month


def _client(handler) -> KontomierzClient:
    return KontomierzClient(
        api_key="secret",
        base_url="https://example.test/k4",
        timeout_seconds=1,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def test_domain_date_helpers_preserve_canonical_values() -> None:
    assert date_value("2026-08-01", "transaction_on") == "2026-08-01"
    assert date_range("2026-08-01", "2026-08-31") == ("2026-08-01", "2026-08-31")
    assert month("2026-08") == "2026-08"


@pytest.mark.asyncio
async def test_http_adapter_owns_legacy_date_and_month_wire_conversion() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("budgets.json") and request.method == "GET":
            return httpx.Response(200, json={"budgets": [{"id": 3, "month_on": "01-08-2026"}]})
        if request.url.path.endswith("money_transactions.json"):
            return httpx.Response(
                200,
                json={"money_transaction": {"id": 2, "transaction_on": "01-08-2026"}},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = _client(handler)
    try:
        assert await client.get_budgets("2026-08") == [{"id": 3, "month_on": "2026-08-01"}]
        transaction = await client.create_money_transaction(
            client_assigned_id="alignment-1",
            transaction_on="2026-08-01",
        )
        assert transaction["transaction_on"] == "2026-08-01"
    finally:
        await client._client.aclose()

    assert seen[0].url.params["month_on"] == "01-08-2026"
    form = parse_qs(seen[1].content.decode(), keep_blank_values=True)
    assert form["money_transaction[transaction_on]"] == ["01-08-2026"]


@pytest.mark.asyncio
async def test_http_adapter_rejects_final_status_outside_2xx() -> None:
    client = _client(lambda _request: httpx.Response(199))
    try:
        with pytest.raises(UpstreamError) as captured:
            await client.get_tags()
    finally:
        await client._client.aclose()

    assert captured.value.code is ErrorCode.UPSTREAM_FAILURE
    assert captured.value.details == {"status": 199}


def test_mock_dependency_uses_canonical_dates() -> None:
    backend = MockKontomierzClient()
    assert backend.get_budgets("2026-08")[0]["month_on"] == "2026-08-01"
    assert backend.get_scheduled_transactions(schedule_group_name="unpaid")[0]["transaction_on"] == "2026-09-01"
    assert backend.get_wealth_points("2026-08-01", "2026-08-31")[0]["date_on"] == "2026-08-01"
