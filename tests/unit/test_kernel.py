from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.kernel import InvocationKernel
from kontomierz_mcp.manifests import TOOL_MANIFESTS


@pytest.mark.asyncio
async def test_read_succeeds_with_correlation_metadata(readonly_kernel) -> None:
    result = await readonly_kernel.invoke("list_accounts", {})
    assert len(result["data"]) == 2
    assert len(result["_meta"]["request_id"]) == 32
    assert result["_meta"]["target"] == "kontomierz-account"
    await readonly_kernel.close()


@pytest.mark.asyncio
async def test_write_gate_is_server_side(readonly_kernel) -> None:
    with pytest.raises(ApplicationError) as raised:
        await readonly_kernel.invoke("create_wallet", {"currency_balance": "1", "currency_name": "PLN"})
    assert raised.value.code == ErrorCode.AUTHORIZATION_FAILED
    await readonly_kernel.close()


@pytest.mark.asyncio
async def test_write_executes_when_operator_enabled(write_kernel) -> None:
    result = await write_kernel.invoke("create_wallet", {"currency_balance": "1", "currency_name": "PLN"})
    assert result["data"]["id"] == 103
    await write_kernel.close()


@pytest.mark.asyncio
async def test_write_timeout_is_ambiguous_and_not_retryable(write_settings, mock_client, monkeypatch) -> None:
    original = TOOL_MANIFESTS["create_wallet"]
    monkeypatch.setitem(TOOL_MANIFESTS, "create_wallet", replace(original, timeout_seconds=0.01))

    def slow_create(**_arguments):
        import time

        time.sleep(0.03)
        return {"id": 1}

    kernel = InvocationKernel(
        settings=write_settings,
        operations={name: (slow_create if name == "create_wallet" else lambda **_: None) for name in TOOL_MANIFESTS},
        dependency=mock_client,
    )
    with pytest.raises(ApplicationError) as raised:
        await kernel.invoke("create_wallet", {"currency_balance": "1", "currency_name": "PLN"})
    assert raised.value.code == ErrorCode.AMBIGUOUS_OUTCOME
    assert raised.value.retryable is False
    await kernel.close()


@pytest.mark.asyncio
async def test_close_is_idempotent_and_closes_dependency(readonly_kernel, mock_client) -> None:
    await readonly_kernel.close()
    await readonly_kernel.close()
    assert mock_client.closed is True
    with pytest.raises(ApplicationError, match="shutting down"):
        await readonly_kernel.invoke("list_accounts", {})
