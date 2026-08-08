from __future__ import annotations

import io
import json
import logging

import pytest

from kontomierz_mcp.audit import configure_audit_sink
from kontomierz_mcp.config import Settings
from kontomierz_mcp.kernel import InvocationKernel


class Dependency:
    async def probe(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class BrokenAuditStream(io.StringIO):
    def write(self, _value: str) -> int:
        raise OSError("audit sink unavailable")

    def flush(self) -> None:
        raise OSError("audit sink unavailable")


@pytest.mark.asyncio
@pytest.mark.parametrize("application_level", [logging.WARNING, logging.ERROR, logging.CRITICAL])
async def test_audit_is_independent_from_application_log_verbosity(application_level: int) -> None:
    async def read() -> list[dict[str, int]]:
        return [{"id": 1}]

    stream = io.StringIO()
    configure_audit_sink(stream=stream, replace=True)
    root = logging.getLogger()
    previous_level = root.level
    root.setLevel(application_level)
    try:
        kernel = InvocationKernel(
            settings=Settings(api_key="", mock_data=True, log_level=logging.getLevelName(application_level)),
            operations={"list_accounts": read},
            dependency=Dependency(),
        )
        result = await kernel.invoke("list_accounts", {})
    finally:
        root.setLevel(previous_level)

    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "mcp_tool_invocation"
    assert event["resource_identity"] == "account:collection"
    assert event["audit_failure_policy"] == "fail-open-result-preserving"
    assert event["result_category"] == "SUCCESS"
    assert result["data"] == [{"id": 1}]


@pytest.mark.asyncio
async def test_audit_sink_failure_is_observable_without_changing_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    fallback = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fallback)
    configure_audit_sink(stream=BrokenAuditStream(), replace=True)

    async def read() -> list[dict[str, int]]:
        return [{"id": 1}]

    kernel = InvocationKernel(
        settings=Settings(api_key="", mock_data=True),
        operations={"list_accounts": read},
        dependency=Dependency(),
    )
    try:
        result = await kernel.invoke("list_accounts", {})
    finally:
        configure_audit_sink(stream=io.StringIO(), replace=True)

    assert result["data"] == [{"id": 1}]
    signal = fallback.getvalue()
    assert "mcp_audit_emission_failure" in signal
    assert "fail-open-result-preserving" in signal
