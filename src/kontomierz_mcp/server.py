"""Composition root and MCP transport adapters."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from pydantic import Field

from . import __version__
from .client import KontomierzClient
from .config import Settings
from .errors import ApplicationError
from .kernel import InvocationKernel
from .manifests import TOOL_DEFINITIONS
from .mock_backend import MockKontomierzClient
from .operations import build_operations

_logger = logging.getLogger(__name__)


def build_kernel(settings: Settings, dependency: Any | None = None) -> InvocationKernel:
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


def build_server(settings: Settings, kernel: InvocationKernel | None = None) -> Any:
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
            await owned_kernel.close()

    mcp = MCPServer(
        "kontomierz-mcp",
        version=__version__,
        instructions=(
            "Use capability discovery before planning a workflow and list tools before detail or mutation calls. "
            "Financial data is confidential. Writes require the trusted operator gate and consumer confirmation. "
            "Never retry an ambiguous write before reconciling the exact target state."
        ),
        lifespan=lifespan,
    )

    async def dispatch(name: str, arguments: dict[str, Any]) -> Any:
        try:
            result = await owned_kernel.invoke(name, arguments)
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(result["data"], ensure_ascii=False))],
                structured_content=result,
                is_error=False,
            )
        except ApplicationError as exc:
            document = _error_document(exc)
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(document, ensure_ascii=False))],
                structured_content=document,
                is_error=True,
            )

    for definition in TOOL_DEFINITIONS.values():
        namespace: dict[str, Any] = {"_dispatch": dispatch, "Annotated": Annotated, "Field": Field}
        exec(  # nosec B102 - signatures and names are immutable repository-owned catalog values
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
    """Create loopback-only Streamable HTTP plus health endpoints."""
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    owned_kernel = kernel or build_kernel(settings)
    mcp = build_server(settings, owned_kernel)
    mcp_app = mcp.streamable_http_app(stateless_http=True, json_response=True)

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with mcp.session_manager.run():
            try:
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
        lifespan=lifespan,
    )


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    kernel = build_kernel(settings)
    if settings.transport == "stdio":
        build_server(settings, kernel).run("stdio")
        return

    import uvicorn

    app = create_http_app(settings, kernel)
    _logger.info("Starting loopback Streamable HTTP on http://%s:%d/mcp", settings.host, settings.port)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
