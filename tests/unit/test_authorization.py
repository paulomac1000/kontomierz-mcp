from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from kontomierz_mcp.authorization import AuthorizationDecision
from kontomierz_mcp.config import Settings
from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.kernel import InvocationKernel
from kontomierz_mcp.security import InvocationContext

TOKEN = "a" * 32


class Dependency:
    async def probe(self) -> bool:
        return True

    async def close(self) -> None:
        return None


def http_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "api_key": "",
        "mock_data": True,
        "transport": "streamable-http",
        "http_auth_token": TOKEN,
        "http_principal": "operator:test",
    }
    values.update(overrides)
    settings = Settings(**values)
    settings.validate()
    return settings


@pytest.mark.asyncio
async def test_http_kernel_without_request_context_fails_closed() -> None:
    called = False

    async def read() -> list[object]:
        nonlocal called
        called = True
        return []

    kernel = InvocationKernel(
        settings=http_settings(),
        operations={"list_accounts": read},
        dependency=Dependency(),
    )
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("list_accounts", {})
    assert captured.value.code is ErrorCode.AUTHENTICATION_FAILED
    assert called is False


@pytest.mark.asyncio
async def test_authenticated_but_unbound_http_principal_is_not_authorized() -> None:
    called = False

    async def read() -> list[object]:
        nonlocal called
        called = True
        return []

    kernel = InvocationKernel(
        settings=http_settings(),
        operations={"list_accounts": read},
        dependency=Dependency(),
    )
    context = InvocationContext.authenticated_http("operator:other")
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("list_accounts", {}, context=context)
    assert captured.value.code is ErrorCode.AUTHORIZATION_FAILED
    assert called is False


@pytest.mark.asyncio
async def test_http_principal_is_read_only_unless_write_capability_is_explicitly_allowed() -> None:
    called = False

    async def write() -> dict[str, bool]:
        nonlocal called
        called = True
        return {"created": True}

    kernel = InvocationKernel(
        settings=http_settings(enable_write_operations=True),
        operations={"create_wallet": write},
        dependency=Dependency(),
    )
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke(
            "create_wallet",
            {},
            context=InvocationContext.authenticated_http("operator:test"),
        )
    assert captured.value.code is ErrorCode.AUTHORIZATION_FAILED
    assert called is False


@pytest.mark.asyncio
async def test_http_write_requires_both_capability_policy_and_operator_gate() -> None:
    called = False

    async def write() -> dict[str, bool]:
        nonlocal called
        called = True
        return {"created": True}

    settings = http_settings(http_allowed_capabilities=("read", "write"), enable_write_operations=False)
    kernel = InvocationKernel(settings=settings, operations={"create_wallet": write}, dependency=Dependency())
    context = InvocationContext.authenticated_http("operator:test")
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("create_wallet", {}, context=context)
    assert captured.value.code is ErrorCode.AUTHORIZATION_FAILED
    assert "operator policy" in captured.value.message
    assert called is False

    enabled = http_settings(http_allowed_capabilities=("read", "write"), enable_write_operations=True)
    enabled_kernel = InvocationKernel(
        settings=enabled,
        operations={"create_wallet": write},
        dependency=Dependency(),
    )
    result = await enabled_kernel.invoke("create_wallet", {}, context=context)
    assert result["data"] == {"created": True}
    assert called is True


@pytest.mark.asyncio
async def test_authorization_is_revalidated_immediately_before_operation_io(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    async def read() -> list[object]:
        nonlocal called
        called = True
        return []

    settings = Settings(api_key="", mock_data=True)
    kernel = InvocationKernel(settings=settings, operations={"list_accounts": read}, dependency=Dependency())

    original = kernel._authorization.revalidate

    def deny_revalidation(*args: Any, **kwargs: Any) -> AuthorizationDecision:
        decision = original(*args, **kwargs)
        return AuthorizationDecision(
            allowed=False,
            reason="test binding changed",
            policy_version=decision.policy_version,
            capability_id=decision.capability_id,
            capability_class=decision.capability_class,
            target_identity=decision.target_identity,
            argument_digest=decision.argument_digest,
        )

    monkeypatch.setattr(kernel._authorization, "revalidate", deny_revalidation)
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("list_accounts", {})
    assert captured.value.code is ErrorCode.AUTHORIZATION_FAILED
    assert called is False


@pytest.mark.asyncio
async def test_stdio_principal_and_policy_decision_are_emitted_to_structured_audit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def read() -> list[dict[str, int]]:
        return [{"id": 1}]

    caplog.set_level(logging.INFO, logger="kontomierz_mcp.audit")
    settings = Settings(api_key="", mock_data=True)
    kernel = InvocationKernel(settings=settings, operations={"list_accounts": read}, dependency=Dependency())
    result = await kernel.invoke("list_accounts", {})

    audit_records = [record for record in caplog.records if record.name == "kontomierz_mcp.audit"]
    assert len(audit_records) == 1
    event = json.loads(audit_records[0].getMessage())
    assert event["event"] == "mcp_tool_invocation"
    assert event["principal"].startswith("local-user:")
    assert event["transport"] == "stdio"
    assert event["authorization_decision"] == "pre-io:allowed"
    assert event["policy_version"] == "single-account-v1"
    assert event["capability_id"] == "list_accounts"
    assert event["capability_class"] == "read"
    assert event["target_identity"] == "kontomierz:mock-account"
    assert event["result_category"] == "SUCCESS"
    assert "principal" not in result["_meta"]
    assert result["_meta"]["target"] == "kontomierz-account"
