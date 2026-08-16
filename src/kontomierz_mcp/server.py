"""Composition root and MCP transport adapters."""

from __future__ import annotations

import inspect
import json
import keyword
import logging
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Annotated, Any

from pydantic import Field

from . import __version__
from .audit import configure_audit_sink
from .boundary_audit import emit_boundary_rejection
from .client import KontomierzClient
from .config import Settings
from .errors import ApplicationError, ErrorCode
from .kernel import InvocationKernel
from .manifests import TOOL_DEFINITIONS
from .mock_backend import MockKontomierzClient
from .operations import build_operations
from .security import BearerPrincipalMiddleware, current_invocation_context

_logger = logging.getLogger(__name__)
_SENSITIVE_HTTP_LOGGERS = ("httpx", "httpcore")
_ALLOWED_GENERATED_ANNOTATIONS = frozenset({"str", "str | None", "int", "int | None", "bool"})


def configure_application_logging(settings: Settings) -> None:
    """Configure app logging without allowing dependency request URLs to expose credentials."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    for logger_name in _SENSITIVE_HTTP_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def build_kernel(settings: Settings, dependency: Any | None = None) -> InvocationKernel:
    settings.validate()
    if dependency is None:
        dependency = (
            MockKontomierzClient()
            if settings.mock_data
            else KontomierzClient(
                api_key=settings.api_key,
                base_url=settings.api_base_url,
                timeout_seconds=settings.api_timeout_seconds,
                body_mode=settings.body_mode,
            )
        )
    return InvocationKernel(settings=settings, operations=build_operations(dependency, settings), dependency=dependency)


def _error_document(error: ApplicationError) -> dict[str, Any]:
    return {"error": error.as_dict()}


def _validate_generated_definition(definition: Any) -> None:
    """Fail closed before repository-owned catalog values enter generated Python source."""
    if not definition.name.isidentifier() or keyword.iskeyword(definition.name):
        raise RuntimeError(f"Invalid governed tool identifier: {definition.name!r}")
    seen: set[str] = set()
    for parameter in definition.parameters:
        if (
            not parameter.name.isidentifier()
            or keyword.iskeyword(parameter.name)
            or parameter.name in seen
            or parameter.annotation not in _ALLOWED_GENERATED_ANNOTATIONS
        ):
            raise RuntimeError(f"Invalid governed parameter for tool {definition.name}: {parameter.name!r}")
        seen.add(parameter.name)


def _close_tool_input_schemas(result: Any) -> None:
    """Force closed tool-input object schemas for SDK and mapping list results."""
    tools = result.get("tools") if isinstance(result, Mapping) else getattr(result, "tools", None)
    if not isinstance(tools, list):
        return

    for tool in tools:
        if isinstance(tool, Mapping):
            input_schema = tool.get("inputSchema")
            if input_schema is None:
                input_schema = tool.get("input_schema")
        else:
            input_schema = getattr(tool, "input_schema", None)
        if isinstance(input_schema, dict):
            input_schema["additionalProperties"] = False


def build_server(
    settings: Settings,
    kernel: InvocationKernel | None = None,
    *,
    owns_kernel: bool = True,
) -> Any:
    """Build one official MCP SDK v2 server from the governed tool catalog."""
    try:
        from mcp.server import MCPServer
        from mcp.types import CallToolResult, TextContent
    except ImportError as exc:  # pragma: no cover - dependency installation failure
        raise RuntimeError("Install the project dependencies to run the MCP transport") from exc

    owned_kernel = kernel or build_kernel(settings)

    @asynccontextmanager
    async def lifespan(_server: Any) -> AsyncIterator[dict[str, InvocationKernel]]:
        try:
            yield {"kernel": owned_kernel}
        finally:
            if owns_kernel:
                await owned_kernel.close()

    def call_tool_result(document: dict[str, Any], *, is_error: bool) -> Any:
        body = document if is_error else document["data"]
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(body, ensure_ascii=False))],
            structured_content=document,
            is_error=is_error,
        )

    allowed_arguments = {
        name: frozenset(parameter.name for parameter in definition.parameters)
        for name, definition in TOOL_DEFINITIONS.items()
    }

    class GovernedToolInputMiddleware:
        """Keep advertised tool schemas and pre-dispatch argument handling fail-closed."""

        async def __call__(self, context: Any, call_next: Any) -> Any:
            if context.method == "tools/call" and isinstance(context.params, Mapping):
                tool_name = context.params.get("name")
                arguments = context.params.get("arguments")
                allowed = allowed_arguments.get(tool_name) if isinstance(tool_name, str) else None
                if allowed is not None and isinstance(arguments, Mapping):
                    for parameter_name in arguments:
                        if not isinstance(parameter_name, str) or parameter_name not in allowed:
                            emit_boundary_rejection(
                                stage="schema",
                                result="INVALID_PARAMETER",
                                route="mcp",
                                authenticated=current_invocation_context() is not None,
                            )
                            error = ApplicationError(
                                ErrorCode.INVALID_PARAMETER,
                                "Tool call contains an unexpected parameter",
                                suggestion="Call tools/list and use only the declared input schema.",
                            )
                            return call_tool_result(_error_document(error), is_error=True)

            result = await call_next(context)
            if context.method == "tools/list":
                _close_tool_input_schemas(result)
            return result

    server_kwargs: dict[str, Any] = {
        "version": __version__,
        "instructions": (
            "Use capability discovery before planning a workflow and list tools before detail or mutation calls. "
            "Financial data is confidential. Writes require the trusted operator gate. "
            "Streamable HTTP requires server-validated Bearer authentication. "
            "Never retry an ambiguous write before reconciling the exact target state."
        ),
        "lifespan": lifespan,
    }
    # The pinned official SDK exposes context middleware. Repository test doubles
    # may intentionally model only the registration/transport surface.
    if "middleware" in inspect.signature(MCPServer).parameters:
        server_kwargs["middleware"] = [GovernedToolInputMiddleware()]
    mcp = MCPServer("kontomierz-mcp", **server_kwargs)

    async def dispatch(name: str, arguments: dict[str, Any]) -> Any:
        try:
            result = await owned_kernel.invoke(name, arguments, context=current_invocation_context())
            return call_tool_result(result, is_error=False)
        except ApplicationError as exc:
            return call_tool_result(_error_document(exc), is_error=True)
        except Exception as exc:
            _logger.error("Unhandled MCP adapter failure tool=%s exception_type=%s", name, type(exc).__name__)
            error = ApplicationError(ErrorCode.INTERNAL_ERROR, "The operation failed unexpectedly")
            return call_tool_result(_error_document(error), is_error=True)

    for definition in TOOL_DEFINITIONS.values():
        _validate_generated_definition(definition)
        namespace: dict[str, Any] = {"_dispatch": dispatch, "Annotated": Annotated, "Field": Field}
        # Catalog identifiers/types are validated against a closed grammar immediately above.
        exec(  # nosec B102
            (
                f"async def {definition.name}({definition.signature}):\n"
                f"    return await _dispatch({definition.name!r}, locals())"
            ),
            namespace,
        )
        function = namespace[definition.name]
        function.__doc__ = definition.description
        function.__module__ = __name__
        function.__kontomierz_definition__ = definition
        mcp.tool()(function)

    return mcp


def create_http_app(settings: Settings, kernel: InvocationKernel | None = None) -> Any:
    """Create loopback Streamable HTTP with public liveness and authenticated readiness."""
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    if not settings.streamable_http:
        raise ValueError("create_http_app requires a Streamable HTTP Settings snapshot")
    settings.validate()

    owned_kernel = kernel or build_kernel(settings)
    mcp = build_server(settings, owned_kernel, owns_kernel=False)
    from mcp.server.transport_security import TransportSecuritySettings

    host_header = f"[{settings.host}]" if ":" in settings.host else settings.host
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[host_header, f"{host_header}:*"],
        allowed_origins=[f"http://{host_header}", f"http://{host_header}:*"],
    )
    mcp_app = mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        max_request_body_size=settings.http_max_request_body_bytes,
        transport_security=transport_security,
        host=settings.host,
    )

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        try:
            async with mcp.session_manager.run():
                yield
        finally:
            await owned_kernel.close()

    async def live(_request: Any) -> JSONResponse:
        return JSONResponse({"status": "alive"})

    async def ready(_request: Any) -> JSONResponse:
        is_ready = await owned_kernel.readiness()
        return JSONResponse(
            {"status": "ready" if is_ready else "not-ready"},
            status_code=200 if is_ready else 503,
        )

    return Starlette(
        routes=[
            Route("/health/live", live, methods=["GET"]),
            Route("/health/ready", ready, methods=["GET"]),
            Mount("/", app=mcp_app),
        ],
        middleware=[
            Middleware(
                BearerPrincipalMiddleware,
                settings=settings,
                public_paths=frozenset({"/health/live"}),
                protected_paths=frozenset({"/mcp", "/health/ready"}),
            )
        ],
        lifespan=lifespan,
    )


def main() -> None:
    settings = Settings.from_env()
    configure_application_logging(settings)
    configure_audit_sink()
    kernel = build_kernel(settings)
    if settings.transport == "stdio":
        build_server(settings, kernel).run("stdio")
        return

    import uvicorn

    app = create_http_app(settings, kernel)
    _logger.info("Starting authenticated loopback Streamable HTTP on http://%s:%d/mcp", settings.host, settings.port)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
