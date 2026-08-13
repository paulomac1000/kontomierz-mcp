from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import replace

import pytest

from kontomierz_mcp.config import Settings
from kontomierz_mcp.errors import ApplicationError, ErrorCode, UpstreamError
from kontomierz_mcp.kernel import InvocationKernel
from kontomierz_mcp.manifests import TOOL_MANIFESTS


class Dependency:
    def __init__(self) -> None:
        self.available = True
        self.closed = False

    async def probe(self) -> bool:
        return self.available

    async def close(self) -> None:
        self.closed = True


def settings(**overrides):
    values = {
        "api_key": "",
        "mock_data": True,
        "enable_write_operations": True,
        "max_concurrency": 4,
        "readiness_cache_seconds": 1,
        "readiness_timeout_seconds": 1,
    }
    values.update(overrides)
    return Settings(**values)


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(1):
        while not predicate():
            await asyncio.sleep(0)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [ErrorCode.TIMEOUT, ErrorCode.DEPENDENCY_UNAVAILABLE])
async def test_ambiguous_upstream_write_is_normalized(code: ErrorCode) -> None:
    async def write() -> None:
        raise UpstreamError(code, "dependency failed", retryable=True, write_outcome_ambiguous=True)

    kernel = InvocationKernel(settings=settings(), operations={"create_wallet": write}, dependency=Dependency())
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("create_wallet", {})
    error = captured.value
    assert error.code is ErrorCode.AMBIGUOUS_OUTCOME
    assert error.retryable is False
    assert error.suggestion == "Reconcile resource state before any retry."


@pytest.mark.asyncio
async def test_read_dependency_timeout_is_not_ambiguous() -> None:
    async def read() -> None:
        raise UpstreamError(ErrorCode.TIMEOUT, "late", retryable=True)

    kernel = InvocationKernel(settings=settings(), operations={"list_accounts": read}, dependency=Dependency())
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("list_accounts", {})
    assert captured.value.code is ErrorCode.TIMEOUT
    assert captured.value.retryable is True


@pytest.mark.asyncio
async def test_non_concurrent_safe_writes_are_serialized_per_target() -> None:
    active = 0
    maximum = 0
    entered_first = asyncio.Event()
    release = asyncio.Event()

    async def write(limit: str) -> dict[str, str]:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        entered_first.set()
        await release.wait()
        active -= 1
        return {"limit": limit}

    kernel = InvocationKernel(settings=settings(), operations={"update_budget": write}, dependency=Dependency())
    first = asyncio.create_task(kernel.invoke("update_budget", {"limit": "1"}))
    await entered_first.wait()
    second = asyncio.create_task(kernel.invoke("update_budget", {"limit": "2"}))
    await _wait_until(lambda: kernel._admitted_invocations == 2)
    assert maximum == 1
    release.set()
    await asyncio.gather(first, second)
    assert maximum == 1


@pytest.mark.asyncio
async def test_concurrency_limit_applies_to_running_async_operations() -> None:
    active = 0
    maximum = 0
    release = asyncio.Event()

    async def read() -> list[object]:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await release.wait()
        active -= 1
        return []

    kernel = InvocationKernel(
        settings=settings(max_concurrency=2),
        operations={"list_accounts": read},
        dependency=Dependency(),
    )
    tasks = [asyncio.create_task(kernel.invoke("list_accounts", {})) for _ in range(6)]
    await _wait_until(lambda: active == 2)
    assert maximum == 2
    release.set()
    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_started_write_deadline_is_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()

    async def write() -> None:
        started.set()
        await asyncio.sleep(10)

    monkeypatch.setitem(TOOL_MANIFESTS, "create_wallet", replace(TOOL_MANIFESTS["create_wallet"], timeout_ms=20))
    kernel = InvocationKernel(settings=settings(), operations={"create_wallet": write}, dependency=Dependency())
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("create_wallet", {})
    assert started.is_set()
    assert captured.value.code is ErrorCode.AMBIGUOUS_OUTCOME
    assert captured.value.retryable is False


@pytest.mark.asyncio
async def test_started_write_cancellation_is_audited_as_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()
    audits: list[dict[str, object]] = []

    async def write() -> None:
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(
        "kontomierz_mcp.kernel.emit_invocation_audit",
        lambda state: audits.append(state.document()),
    )
    kernel = InvocationKernel(settings=settings(), operations={"create_wallet": write}, dependency=Dependency())
    task = asyncio.create_task(kernel.invoke("create_wallet", {}))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(audits) == 1
    assert audits[0]["result_category"] == ErrorCode.CANCELLED.value
    assert audits[0]["cancelled"] is True
    assert audits[0]["ambiguous"] is True


@pytest.mark.asyncio
async def test_oversized_read_response_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def read() -> dict[str, str]:
        return {"payload": "x" * 2048}

    monkeypatch.setitem(
        TOOL_MANIFESTS,
        "list_accounts",
        replace(TOOL_MANIFESTS["list_accounts"], max_response_bytes=512),
    )
    kernel = InvocationKernel(settings=settings(), operations={"list_accounts": read}, dependency=Dependency())
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("list_accounts", {})
    assert captured.value.code is ErrorCode.UPSTREAM_FAILURE
    assert captured.value.retryable is False
    assert captured.value.details == {"max_response_bytes": 512}


@pytest.mark.asyncio
async def test_oversized_write_response_returns_small_completion_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    async def write() -> dict[str, str]:
        return {"payload": "x" * 2048}

    monkeypatch.setitem(
        TOOL_MANIFESTS,
        "create_wallet",
        replace(TOOL_MANIFESTS["create_wallet"], max_response_bytes=512),
    )
    kernel = InvocationKernel(settings=settings(), operations={"create_wallet": write}, dependency=Dependency())
    result = await kernel.invoke("create_wallet", {})
    assert result["data"] == {
        "completed": True,
        "response_omitted": True,
        "reconciliation_required": True,
    }


@pytest.mark.asyncio
async def test_readiness_checks_and_caches_dependency() -> None:
    dependency = Dependency()
    kernel = InvocationKernel(
        settings=settings(readiness_cache_seconds=30),
        operations={name: (lambda: None) for name in TOOL_MANIFESTS},
        dependency=dependency,
    )
    assert await kernel.readiness() is True
    dependency.available = False
    assert await kernel.readiness() is True
    kernel._readiness_checked_at = time.monotonic() - 31
    assert await kernel.readiness() is False


@pytest.mark.asyncio
async def test_real_dependency_readiness_probes_even_when_monotonic_epoch_is_near_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency = Dependency()
    probe_calls = 0

    async def probe() -> bool:
        nonlocal probe_calls
        probe_calls += 1
        return True

    dependency.probe = probe  # type: ignore[method-assign]
    monkeypatch.setattr(time, "monotonic", lambda: 0.5)
    kernel = InvocationKernel(
        settings=settings(mock_data=False, api_key="secret", readiness_cache_seconds=10),
        operations={name: (lambda: None) for name in TOOL_MANIFESTS},
        dependency=dependency,
    )
    assert kernel.cached_dependency_ready is None
    assert await kernel.readiness() is True
    assert probe_calls == 1


@pytest.mark.asyncio
async def test_close_awaits_async_dependency() -> None:
    dependency = Dependency()
    kernel = InvocationKernel(settings=settings(), operations={}, dependency=dependency)
    await kernel.close()
    assert dependency.closed is True


@pytest.mark.asyncio
async def test_pending_invocation_capacity_is_bounded() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    async def read() -> list[object]:
        entered.set()
        await release.wait()
        return []

    kernel = InvocationKernel(
        settings=settings(max_concurrency=1, max_pending_invocations=2),
        operations={"list_accounts": read},
        dependency=Dependency(),
    )
    first = asyncio.create_task(kernel.invoke("list_accounts", {}))
    await entered.wait()
    second = asyncio.create_task(kernel.invoke("list_accounts", {}))
    await _wait_until(lambda: kernel._admitted_invocations == 2)

    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("list_accounts", {})
    assert captured.value.code is ErrorCode.RATE_LIMITED
    assert captured.value.retryable is True
    assert captured.value.suggestion == "Retry later; the operation did not start."

    release.set()
    await asyncio.gather(first, second)


@pytest.mark.asyncio
async def test_deadline_cancels_async_dependency_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    cancelled = asyncio.Event()

    async def read() -> None:
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    monkeypatch.setitem(TOOL_MANIFESTS, "list_accounts", replace(TOOL_MANIFESTS["list_accounts"], timeout_ms=20))
    kernel = InvocationKernel(settings=settings(), operations={"list_accounts": read}, dependency=Dependency())
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("list_accounts", {})
    assert captured.value.code is ErrorCode.TIMEOUT
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_cached_unavailable_dependency_blocks_io() -> None:
    called = False

    async def read() -> None:
        nonlocal called
        called = True

    kernel = InvocationKernel(
        settings=settings(mock_data=False, api_key="secret"),
        operations={"list_accounts": read},
        dependency=Dependency(),
    )
    kernel._readiness_value = False
    kernel._readiness_checked_at = time.monotonic()
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("list_accounts", {})
    assert captured.value.code is ErrorCode.DEPENDENCY_UNAVAILABLE
    assert called is False
