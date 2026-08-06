from __future__ import annotations

import inspect
import json
import sys
from contextlib import asynccontextmanager
from types import ModuleType, SimpleNamespace
from typing import Any, get_type_hints

from pydantic import create_model

import pytest

from kontomierz_mcp.config import Settings
from kontomierz_mcp import __version__
from kontomierz_mcp.manifests import TOOL_DEFINITIONS
from kontomierz_mcp.mock_backend import MockKontomierzClient
from kontomierz_mcp.server import build_kernel, build_server, create_http_app
from kontomierz_mcp.mock_samples import SMOKE_SAMPLES


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
    def __init__(self, name: str, *, version: str, instructions: str, lifespan: Any) -> None:
        self.name = name
        self.version = version
        self.instructions = instructions
        self.lifespan = lifespan
        self.tools: dict[str, Any] = {}
        self.session_manager = FakeSessionManager()
        self.run_transport: str | None = None

    def tool(self):
        def register(function):
            self.tools[function.__name__] = function
            return function

        return register

    def streamable_http_app(self, *, stateless_http: bool, json_response: bool):
        assert stateless_http is True
        assert json_response is True

        async def app(scope, receive, send):
            del scope, receive
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        return app

    def run(self, transport: str) -> None:
        self.run_transport = transport


def install_fake_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp = ModuleType("mcp")
    mcp_types = ModuleType("mcp.types")
    mcp_server = ModuleType("mcp.server")
    mcp_types.TextContent = FakeTextContent
    mcp_types.CallToolResult = FakeCallToolResult
    mcp_server.MCPServer = FakeMCPServer
    mcp.types = mcp_types
    mcp.server = mcp_server
    monkeypatch.setitem(sys.modules, "mcp", mcp)
    monkeypatch.setitem(sys.modules, "mcp.types", mcp_types)
    monkeypatch.setitem(sys.modules, "mcp.server", mcp_server)


@pytest.mark.asyncio
async def test_every_registered_wrapper_delegates_to_the_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_sdk(monkeypatch)
    settings = Settings(api_key="", mock_data=True, enable_write_operations=True)

    for tool_name, arguments in SMOKE_SAMPLES.items():
        kernel = build_kernel(settings, MockKontomierzClient())
        server = build_server(settings, kernel)
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
async def test_http_health_routes_include_dependency_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_sdk(monkeypatch)
    settings = Settings(api_key="", mock_data=True, transport="http")
    dependency = MockKontomierzClient()
    kernel = build_kernel(settings, dependency)
    app = create_http_app(settings, kernel)
    routes = {getattr(route, "path", None): route for route in app.routes}

    live = await routes["/health/live"].endpoint(None)
    ready = await routes["/health/ready"].endpoint(None)
    assert live.status_code == 200
    assert json.loads(live.body) == {"status": "alive"}
    assert ready.status_code == 200
    assert json.loads(ready.body) == {"status": "ready"}

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
        assert tuple(
            item for item, parameter in signature.parameters.items()
            if parameter.default is inspect.Parameter.empty
        ) == definition.required_parameters


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
