from __future__ import annotations

import asyncio

import pytest

from kontomierz_mcp.config import Settings
from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.kernel import InvocationKernel


class Dependency:
    def __init__(self) -> None:
        self.closed = False
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1
        self.closed = True


def settings() -> Settings:
    value = Settings(api_key="", mock_data=True, max_concurrency=1, max_pending_invocations=2)
    value.validate()
    return value


@pytest.mark.asyncio
async def test_operation_timeout_error_is_not_misclassified_as_kernel_deadline() -> None:
    async def read() -> None:
        raise TimeoutError("dependency-local-timeout")

    kernel = InvocationKernel(settings=settings(), operations={"list_accounts": read}, dependency=Dependency())
    with pytest.raises(TimeoutError, match="dependency-local-timeout"):
        await kernel.invoke("list_accounts", {})
    await kernel.close()


@pytest.mark.asyncio
async def test_close_stops_new_admissions_and_drains_inflight_before_dependency_close() -> None:
    dependency = Dependency()
    started = asyncio.Event()
    release = asyncio.Event()

    async def read() -> list[object]:
        started.set()
        await release.wait()
        return []

    kernel = InvocationKernel(settings=settings(), operations={"list_accounts": read}, dependency=dependency)
    invocation = asyncio.create_task(kernel.invoke("list_accounts", {}))
    await started.wait()

    closing = asyncio.create_task(kernel.close())
    async with asyncio.timeout(1):
        while not kernel._closed:
            await asyncio.sleep(0)

    assert dependency.closed is False
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("list_accounts", {})
    assert captured.value.code is ErrorCode.DEPENDENCY_UNAVAILABLE

    release.set()
    await invocation
    await closing
    assert dependency.closed is True
    assert dependency.close_calls == 1

    await kernel.close()
    assert dependency.close_calls == 1
