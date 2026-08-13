from __future__ import annotations

from typing import Any

import pytest

from kontomierz_mcp.config import ConfigurationError, Settings
from kontomierz_mcp.security import BearerPrincipalMiddleware, InvocationContext, current_invocation_context

TOKEN = "a" * 32


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


def test_http_configuration_requires_bounded_authenticated_principal() -> None:
    with pytest.raises(ConfigurationError, match="MCP_HTTP_AUTH_TOKEN"):
        Settings(api_key="", mock_data=True, transport="streamable-http").validate()
    with pytest.raises(ConfigurationError, match="MCP_HTTP_PRINCIPAL"):
        Settings(
            api_key="",
            mock_data=True,
            transport="streamable-http",
            http_auth_token=TOKEN,
        ).validate()


def test_port_must_fit_tcp_range() -> None:
    with pytest.raises(ConfigurationError, match="65535"):
        Settings(api_key="", mock_data=True, port=65_536).validate()


@pytest.mark.asyncio
async def test_bearer_middleware_rejects_missing_wrong_or_duplicate_token_without_entering_app() -> None:
    entered = False

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        del scope, receive, send
        nonlocal entered
        entered = True

    middleware = BearerPrincipalMiddleware(app, http_settings())

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def exercise(headers: list[tuple[bytes, bytes]]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        await middleware({"type": "http", "headers": headers}, receive, send)
        return messages

    cases = (
        [],
        [(b"authorization", b"Bearer wrong")],
        [(b"authorization", b"Basic not-bearer")],
        [(b"authorization", b"Bearer")],
        [(b"authorization", b"Bearer " + b"x" * 1025)],
        [(b"authorization", b"Bearer \xff")],
        [(b"authorization", f"Bearer {TOKEN}".encode()), (b"authorization", f"Bearer {TOKEN}".encode())],
    )
    for headers in cases:
        messages = await exercise(headers)
        assert messages[0]["status"] == 401
        assert entered is False


@pytest.mark.asyncio
@pytest.mark.parametrize("scope_type", ["lifespan", "websocket"])
async def test_bearer_middleware_passes_non_http_scopes_to_wrapped_app(scope_type: str) -> None:
    entered = False

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        del receive, send
        nonlocal entered
        entered = True
        assert scope["type"] == scope_type

    middleware = BearerPrincipalMiddleware(app, http_settings())

    async def receive() -> dict[str, Any]:
        return {"type": "noop"}

    async def send(_message: dict[str, Any]) -> None:
        return None

    await middleware({"type": scope_type}, receive, send)
    assert entered is True


@pytest.mark.asyncio
async def test_bearer_middleware_binds_request_scoped_principal() -> None:
    seen: InvocationContext | None = None

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        del scope, receive
        nonlocal seen
        seen = current_invocation_context()
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = BearerPrincipalMiddleware(app, http_settings())

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    messages: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await middleware(
        {"type": "http", "headers": [(b"authorization", f"Bearer {TOKEN}".encode())]},
        receive,
        send,
    )
    assert messages[0]["status"] == 204
    assert seen == InvocationContext(principal="operator:test", transport="streamable-http", authenticated=True)


@pytest.mark.asyncio
async def test_bearer_middleware_default_protects_every_non_public_path() -> None:
    entered = False

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        del scope, receive, send
        nonlocal entered
        entered = True

    middleware = BearerPrincipalMiddleware(app, http_settings())

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    messages: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await middleware({"type": "http", "path": "/no/such/route", "headers": []}, receive, send)
    assert messages[0]["status"] == 401
    assert entered is False


@pytest.mark.asyncio
async def test_bearer_middleware_rejects_unlisted_paths_before_sdk_app() -> None:
    entered = False

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        del scope, receive, send
        nonlocal entered
        entered = True

    middleware = BearerPrincipalMiddleware(app, http_settings(), protected_paths=frozenset({"/mcp", "/health/ready"}))

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    messages: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await middleware({"type": "http", "path": "/no/such/route", "headers": []}, receive, send)
    assert messages[0]["status"] == 404
    assert messages[0]["headers"] == [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]
    assert entered is False


@pytest.mark.asyncio
async def test_bearer_middleware_still_authenticates_listed_protected_paths() -> None:
    entered = False

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        del scope, receive
        nonlocal entered
        entered = True
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = BearerPrincipalMiddleware(app, http_settings(), protected_paths=frozenset({"/mcp", "/health/ready"}))

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def exercise(headers: list[tuple[bytes, bytes]]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        await middleware({"type": "http", "path": "/health/ready", "headers": headers}, receive, send)
        return messages

    denied = await exercise([])
    assert denied[0]["status"] == 401
    assert entered is False

    allowed = await exercise([(b"authorization", f"Bearer {TOKEN}".encode())])
    assert allowed[0]["status"] == 204
    assert entered is True


def test_stdio_uses_explicit_process_derived_principal() -> None:
    context = InvocationContext.local_stdio()
    assert context.transport == "stdio"
    assert context.authenticated is True
    assert context.principal.startswith("local-process:")
    assert ":uid:" in context.principal or ":pid:" in context.principal
