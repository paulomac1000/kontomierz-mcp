from __future__ import annotations

import inspect
import json
import sys
from contextlib import asynccontextmanager
from types import ModuleType
from typing import Any, get_type_hints

import httpx
import pytest
from pydantic import create_model

from kontomierz_mcp import __version__
from kontomierz_mcp.config import Settings
from kontomierz_mcp.manifests import TOOL_DEFINITIONS
from kontomierz_mcp.mock_backend import MockKontomierzClient
from kontomierz_mcp.mock_samples import SMOKE_SAMPLES
from kontomierz_mcp.server import build_kernel, build_server, create_http_app

HTTP_TOKEN = "a" * 32


class FakeTextContent:
    def __init__(self, *, type: str, text: str) -> None:
        self.type = type
        self.text = text


class FakeCallToolResult:
    def __init__(
        self,
        *,
        content: list[FakeTextContent],
        structured_content: dict[str, Any],
        is_error: bool,
    ) -> None:
        self.content = content
        self.structured_content = structured_content
        self.is_error = is_error


class FakeTransportSecuritySettings:
    def __init__(
        self,
        *,
        enable_dns_rebinding_protection: bool,
        allowed_hosts: list[str],
        allowed_origins: list[str],
    ) -> None:
        self.enable_dns_rebinding_protection = enable_dns_rebinding_protection
        self.allowed_hosts = allowed_hosts
        self.allowed_origins = allowed_origins


class FakeSessionManager:
    def __init__(self) -> None:
        self.entered = False

    @asynccontextmanager
    async def run(self):
        self.entered = True
        try:
            yield
        finally:
            self.entered = False


class FakeMCPServer:
    last_instance: FakeMCPServer | None = None

    def __init__(self, name: str, *, version: str, instructions: str, lifespan: Any) -> None:
        self.name = name
        self.version = version
        self.instructions = instructions
        self.lifespan = lifespan
        self.tools: dict[str, Any] = {}
        self.session_manager = FakeSessionManager()
        self.run_transport: str | None = None
        self.http_settings: dict[str, Any] | None = None
        FakeMCPServer.last_instance = self

    def tool(self):
        def register(function):
            self.tools[function.__name__] = function
            return function

        return register

    def streamable_http_app(
        self,
        *,
        stateless_http: bool,
        json_response: bool,
        max_request_body_size: int,
        transport_security: FakeTransportSecuritySettings,
        host: str,
    ):
        self.http_settings = {
            "stateless_http": stateless_http,
            "json_response": json_response,
            "max_request_body_size": max_request_body_size,
            "transport_security": transport_security,
            "host": host,
        }

        async def app(scope, receive, send):
            del scope, receive
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        return app

    def run(self, transport: str) -> None:
        self.run_transport = transport


class ProbeCountingDependency(MockKontomierzClient):
    def __init__(self) -> None:
        super().__init__()
        self.probe_calls = 0

    async def probe(self) -> bool:
        self.probe_calls += 1
        return True


def install_fake_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp = ModuleType("mcp")
    mcp_types = ModuleType("mcp.types")
    mcp_server = ModuleType("mcp.server")
    mcp_server.__path__ = []  # type: ignore[attr-defined]
    mcp_transport_security = ModuleType("mcp.server.transport_security")
    mcp_types.TextContent = FakeTextContent
    mcp_types.CallToolResult = FakeCallToolResult
    mcp_server.MCPServer = FakeMCPServer
    mcp_transport_security.TransportSecuritySettings = FakeTransportSecuritySettings
    mcp.types = mcp_types
    mcp.server = mcp_server
    monkeypatch.setitem(sys.modules, "mcp", mcp)
    monkeypatch.setitem(sys.modules, "mcp.types", mcp_types)
    monkeypatch.setitem(sys.modules, "mcp.server", mcp_server)
    monkeypatch.setitem(sys.modules, "mcp.server.transport_security", mcp_transport_security)


@pytest.mark.asyncio
async def test_every_registered_wrapper_delegates_to_the_kernel(
    monkeypatch: pytest.MonkeyPatch,
    write_settings: Settings,
) -> None:
    install_fake_sdk(monkeypatch)

    for tool_name, arguments in SMOKE_SAMPLES.items():
        kernel = build_kernel(write_settings, MockKontomierzClient())
        server = build_server(write_settings, kernel)
        assert set(server.tools) == set(SMOKE_SAMPLES)
        result = await server.tools[tool_name](**arguments)
        assert result.is_error is False
        assert result.structured_content["_meta"]["tool_name"] == tool_name
        assert json.loads(result.content[0].text) == result.structured_content["data"]
        await kernel.close()


@pytest.mark.asyncio
async def test_tool_error_is_an_explicit_stable_call_tool_result(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_sdk(monkeypatch)
    settings = Settings(api_key="", mock_data=True, enable_write_operations=False)
    kernel = build_kernel(settings, MockKontomierzClient())
    server = build_server(settings, kernel)

    result = await server.tools["create_wallet"](currency_balance="1", currency_name="PLN")

    assert result.is_error is True
    assert result.structured_content["error"]["code"] == "AUTHORIZATION_FAILED"
    assert result.structured_content["error"]["retryable"] is False
    assert json.loads(result.content[0].text) == result.structured_content
    assert "secret" not in result.content[0].text.lower()
    await kernel.close()


@pytest.mark.asyncio
async def test_http_health_routes_include_dependency_readiness_and_explicit_transport_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_sdk(monkeypatch)
    settings = Settings(
        api_key="secret",
        mock_data=False,
        transport="http",
        http_auth_token=HTTP_TOKEN,
        http_principal="test-operator",
        http_max_request_body_bytes=2048,
    )
    dependency = ProbeCountingDependency()
    kernel = build_kernel(settings, dependency)
    app = create_http_app(settings, kernel)
    routes = {getattr(route, "path", None): route for route in app.routes}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        live = await client.get("/health/live")
        assert live.status_code == 200
        assert live.json() == {"status": "alive"}

        unauthenticated = await client.get("/health/ready")
        assert unauthenticated.status_code == 401
        assert dependency.probe_calls == 0

        ready = await client.get("/health/ready", headers={"Authorization": f"Bearer {HTTP_TOKEN}"})
        assert ready.status_code == 200
        assert ready.json() == {"status": "ready"}
        assert dependency.probe_calls == 1

    mounted = routes[""].app
    assert mounted is not None
    fake_mcp = FakeMCPServer.last_instance
    assert fake_mcp is not None
    assert fake_mcp.version == __version__
    assert fake_mcp.http_settings is not None
    assert fake_mcp.http_settings["stateless_http"] is True
    assert fake_mcp.http_settings["json_response"] is True
    assert fake_mcp.http_settings["max_request_body_size"] == 2048
    assert fake_mcp.http_settings["host"] == "127.0.0.1"
    transport_security = fake_mcp.http_settings["transport_security"]
    assert transport_security.enable_dns_rebinding_protection is True
    assert transport_security.allowed_hosts == ["127.0.0.1", "127.0.0.1:*"]
    assert transport_security.allowed_origins == ["http://127.0.0.1", "http://127.0.0.1:*"]

    async with app.router.lifespan_context(app):
        assert routes[""].app is not None
    assert dependency.closed is True


def test_registration_uses_governed_names_descriptions_and_signatures(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_sdk(monkeypatch)
    settings = Settings(api_key="", mock_data=True)
    kernel = build_kernel(settings, MockKontomierzClient())
    server = build_server(settings, kernel)

    assert server.version == __version__
    assert set(server.tools) == set(TOOL_DEFINITIONS)
    for name, function in server.tools.items():
        definition = TOOL_DEFINITIONS[name]
        assert function.__doc__ == definition.description
        signature = inspect.signature(function)
        assert tuple(signature.parameters) == tuple(parameter.name for parameter in definition.parameters)
        assert (
            tuple(
                item for item, parameter in signature.parameters.items() if parameter.default is inspect.Parameter.empty
            )
            == definition.required_parameters
        )


def test_generated_annotations_preserve_parameter_descriptions(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_sdk(monkeypatch)
    settings = Settings(api_key="", mock_data=True)
    kernel = build_kernel(settings, MockKontomierzClient())
    server = build_server(settings, kernel)

    for name, function in server.tools.items():
        definition = TOOL_DEFINITIONS[name]
        signature = inspect.signature(function)
        hints = get_type_hints(function, include_extras=True)
        model_fields = {}
        for parameter in definition.parameters:
            default = signature.parameters[parameter.name].default
            if default is inspect.Parameter.empty:
                default = ...
            model_fields[parameter.name] = (hints[parameter.name], default)
        model = create_model(f"{name.title()}Input", **model_fields)
        schema = model.model_json_schema()
        for parameter in definition.parameters:
            assert schema["properties"][parameter.name]["description"] == parameter.description
