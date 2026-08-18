from __future__ import annotations

import io
import json
import logging

import pytest

from kontomierz_mcp.audit import InvocationAuditState, configure_audit_sink
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


@pytest.fixture(autouse=True)
def restore_audit_logger() -> None:
    logger = logging.getLogger("kontomierz_mcp.audit")
    previous_handlers = list(logger.handlers)
    previous_level = logger.level
    previous_propagate = logger.propagate
    try:
        yield
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        for handler in previous_handlers:
            logger.addHandler(handler)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate


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
    result = await kernel.invoke("list_accounts", {})

    assert result["data"] == [{"id": 1}]
    signal = fallback.getvalue()
    assert "mcp_audit_emission_failure" in signal
    assert "fail-open-result-preserving" in signal


def test_audit_document_hashes_oversized_fields_and_validates_categories() -> None:
    state = InvocationAuditState(
        request_id="x" * 1024,
        tool_name="list_accounts",
        started_at=0.0,
        principal="secret-prefix-" + "p" * 4096,
        transport="unexpected-transport",
        capability_class="unexpected-class",
        authorization_decision="unexpected-decision",
        operator_gate_decision="unexpected-gate",
        dependency_state="unexpected-state",
        result_category="unexpected-result",
    )

    document = state.document()

    assert str(document["request_id"]).startswith("sha256:")
    assert str(document["principal"]).startswith("sha256:")
    assert "secret-prefix" not in str(document["principal"])
    assert document["transport"] == "unresolved"
    assert document["capability_class"] == "unresolved"
    assert document["authorization_decision"] == "not-evaluated"
    assert document["operator_gate_decision"] == "not-applicable"
    assert document["dependency_state"] == "unknown"
    assert document["result_category"] == "INTERNAL_ERROR"
    encoded = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert len(encoded) <= 8192


def test_audit_document_never_emits_short_protected_values_verbatim() -> None:
    protected_values = {
        "principal": "Bearer-secret-token",
        "target_identity": "https://private.example/account/123",
        "resource_identity": "raw-account-secret",
        "argument_digest": "raw-argument-body",
        "authorization_reason": "api-key=short-secret",
    }
    state = InvocationAuditState(
        request_id="0" * 32,
        tool_name="list_accounts",
        started_at=0.0,
        transport="streamable-http",
        capability_id="list_accounts",
        capability_class="read",
        policy_version="single-account-resource-v3",
        **protected_values,
    )

    document = state.document()
    encoded = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    for field, raw_value in protected_values.items():
        assert document[field] != raw_value
        assert str(document[field]).startswith("sha256:")
        assert raw_value not in encoded
