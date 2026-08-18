from __future__ import annotations

import pytest

from kontomierz_mcp.config import Settings
from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.kernel import InvocationKernel
from kontomierz_mcp.security import InvocationContext


class Dependency:
    async def probe(self) -> bool:
        return True

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_kernel_rejects_unauthenticated_context_before_operation() -> None:
    called = False

    async def read() -> list[object]:
        nonlocal called
        called = True
        return []

    settings = Settings(api_key="", mock_data=True)
    kernel = InvocationKernel(settings=settings, operations={"list_accounts": read}, dependency=Dependency())
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke(
            "list_accounts",
            {},
            context=InvocationContext(principal="anonymous", transport="streamable-http", authenticated=False),
        )
    assert captured.value.code is ErrorCode.AUTHENTICATION_FAILED
    assert called is False


@pytest.mark.asyncio
async def test_kernel_fails_closed_if_future_manifest_requires_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from kontomierz_mcp.manifests import TOOL_MANIFESTS

    called = False

    async def write() -> dict[str, bool]:
        nonlocal called
        called = True
        return {"created": True}

    monkeypatch.setitem(
        TOOL_MANIFESTS,
        "create_wallet",
        replace(TOOL_MANIFESTS["create_wallet"], requires_confirmation=True),
    )
    settings = Settings(api_key="", mock_data=True, enable_write_operations=True)
    kernel = InvocationKernel(settings=settings, operations={"create_wallet": write}, dependency=Dependency())
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("create_wallet", {})
    assert captured.value.code is ErrorCode.AUTHORIZATION_FAILED
    assert "approval" in captured.value.message
    assert called is False
