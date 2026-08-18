from __future__ import annotations

import io
import json
import logging
from dataclasses import replace
from typing import Any

import pytest

from kontomierz_mcp.audit import configure_audit_sink
from kontomierz_mcp.authorization import AuthorizationDecision, AuthorizationPolicy
from kontomierz_mcp.config import ConfigurationError, Settings
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


def test_http_destructive_class_requires_narrow_allowlists() -> None:
    with pytest.raises(ConfigurationError, match="destructive"):
        http_settings(http_allowed_capabilities=("read", "destructive"))


@pytest.mark.asyncio
async def test_http_destructive_requires_exact_capability_and_resource_allowlists() -> None:
    called: list[int] = []

    async def destroy_wallet(wallet_id: int) -> dict[str, int]:
        called.append(wallet_id)
        return {"deleted": wallet_id}

    settings = http_settings(
        http_allowed_capabilities=("read", "destructive"),
        http_allowed_destructive_capabilities=("destroy_wallet",),
        http_allowed_destructive_resources=("wallet:123",),
        enable_write_operations=True,
    )
    kernel = InvocationKernel(settings=settings, operations={"destroy_wallet": destroy_wallet}, dependency=Dependency())
    context = InvocationContext.authenticated_http("operator:test")

    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("destroy_wallet", {"wallet_id": 124}, context=context)
    assert captured.value.code is ErrorCode.AUTHORIZATION_FAILED
    assert "not explicitly allowlisted" in captured.value.message
    assert called == []

    document = kernel.capability_document(context)
    assert document["tools"]["destroy_wallet"]["manifest"]["active_state"] == "active"

    result = await kernel.invoke("destroy_wallet", {"wallet_id": 123}, context=context)
    assert result["data"] == {"deleted": 123}
    assert called == [123]


@pytest.mark.asyncio
async def test_stdio_destructive_requires_exact_capability_and_resource_allowlists() -> None:
    called: list[int] = []

    async def destroy_wallet(wallet_id: int) -> dict[str, int]:
        called.append(wallet_id)
        return {"deleted": wallet_id}

    denied_settings = Settings(api_key="", mock_data=True, enable_write_operations=True)
    denied_kernel = InvocationKernel(
        settings=denied_settings,
        operations={"destroy_wallet": destroy_wallet},
        dependency=Dependency(),
    )
    with pytest.raises(ApplicationError) as captured:
        await denied_kernel.invoke("destroy_wallet", {"wallet_id": 123})
    assert captured.value.code is ErrorCode.AUTHORIZATION_FAILED
    assert called == []

    allowed_settings = Settings(
        api_key="",
        mock_data=True,
        enable_write_operations=True,
        stdio_allowed_destructive_capabilities=("destroy_wallet",),
        stdio_allowed_destructive_resources=("wallet:123",),
    )
    allowed_settings.validate()
    allowed_kernel = InvocationKernel(
        settings=allowed_settings,
        operations={"destroy_wallet": destroy_wallet},
        dependency=Dependency(),
    )
    with pytest.raises(ApplicationError) as wrong_resource:
        await allowed_kernel.invoke("destroy_wallet", {"wallet_id": 124})
    assert wrong_resource.value.code is ErrorCode.AUTHORIZATION_FAILED
    assert called == []

    result = await allowed_kernel.invoke("destroy_wallet", {"wallet_id": 123})
    assert result["data"] == {"deleted": 123}
    assert called == [123]


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
            resource_identity=decision.resource_identity,
            argument_digest=decision.argument_digest,
        )

    monkeypatch.setattr(kernel._authorization, "revalidate", deny_revalidation)
    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("list_accounts", {})
    assert captured.value.code is ErrorCode.AUTHORIZATION_FAILED
    assert called is False


@pytest.mark.asyncio
async def test_stdio_principal_and_policy_decision_are_emitted_to_structured_audit() -> None:
    async def read() -> list[dict[str, int]]:
        return [{"id": 1}]

    stream = io.StringIO()
    configure_audit_sink(stream=stream, replace=True)
    root = logging.getLogger()
    previous_level = root.level
    root.setLevel(logging.WARNING)
    try:
        settings = Settings(api_key="", mock_data=True, log_level="WARNING")
        kernel = InvocationKernel(settings=settings, operations={"list_accounts": read}, dependency=Dependency())
        result = await kernel.invoke("list_accounts", {})
    finally:
        root.setLevel(previous_level)

    audit_lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    assert len(audit_lines) == 1
    event = json.loads(audit_lines[0])
    assert event["event"] == "mcp_tool_invocation"
    assert event["principal"].startswith("local-process:")
    assert event["transport"] == "stdio"
    assert event["authorization_decision"] == "pre-io:allowed"
    assert event["policy_version"] == "single-account-resource-v3"
    assert event["capability_id"] == "list_accounts"
    assert event["capability_class"] == "read"
    assert event["target_identity"] == "kontomierz:mock-account"
    assert event["resource_identity"] == "account:collection"
    assert event["audit_failure_policy"] == "fail-open-result-preserving"
    assert event["result_category"] == "SUCCESS"
    assert "principal" not in result["_meta"]
    assert "target" not in result["_meta"]
    assert result["_meta"]["target_scope"] == "kontomierz-account"
    assert result["_meta"]["target_ref"].startswith("target:sha256:")


def test_every_governed_tool_has_an_explicit_resource_binding() -> None:
    from kontomierz_mcp import authorization
    from kontomierz_mcp.manifests import TOOL_MANIFESTS

    assert set(authorization._RESOURCE_BINDINGS) == set(TOOL_MANIFESTS)


def test_future_tool_without_resource_binding_fails_closed() -> None:
    from kontomierz_mcp.manifests import TOOL_MANIFESTS

    manifest = replace(TOOL_MANIFESTS["list_accounts"], name="future_unmapped_tool")
    policy = AuthorizationPolicy(Settings(api_key="", mock_data=True))
    context = InvocationContext.local_stdio()

    decision = policy.authorize(context, manifest, {})
    assert decision.allowed is False
    assert decision.reason == "capability has no governed resource binding"
    assert policy.capability_allowed(context, manifest) is False


@pytest.mark.asyncio
async def test_capability_class_denial_names_the_disabled_class() -> None:
    async def delete_budget(budget_id: int) -> dict[str, int]:
        return {"deleted": budget_id}

    settings = http_settings(
        http_allowed_capabilities=("read", "write"),
        enable_write_operations=True,
    )
    kernel = InvocationKernel(settings=settings, operations={"delete_budget": delete_budget}, dependency=Dependency())
    context = InvocationContext.authenticated_http("operator:test")

    with pytest.raises(ApplicationError) as captured:
        await kernel.invoke("delete_budget", {"budget_id": 201}, context=context)
    assert captured.value.code is ErrorCode.AUTHORIZATION_FAILED
    assert "capability class destructive is not allowed for the HTTP principal" in captured.value.message
