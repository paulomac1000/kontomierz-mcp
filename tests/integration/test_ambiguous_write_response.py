from __future__ import annotations

import httpx
import pytest

from kontomierz_mcp.client import KontomierzClient
from kontomierz_mcp.config import Settings
from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.server import build_kernel


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unusable_success_response_after_write_reaches_protocol_as_ambiguous() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"user_account": []})
    )
    async_client = httpx.AsyncClient(transport=transport)
    dependency = KontomierzClient(
        api_key="secret",
        base_url="https://example.test/k4",
        timeout_seconds=1,
        client=async_client,
    )
    settings = Settings(api_key="secret", enable_write_operations=True)
    kernel = build_kernel(settings, dependency)

    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke(
            "create_wallet",
            {"currency_balance": "0", "currency_name": "PLN"},
        )

    assert captured.value.code is ErrorCode.AMBIGUOUS_OUTCOME
    assert captured.value.retryable is False
    assert captured.value.suggestion == "Reconcile resource state before any retry."
    await async_client.aclose()
