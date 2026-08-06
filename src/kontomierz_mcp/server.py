"""Composition root and MCP transport adapters."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from .client import KontomierzClient
from .config import Settings
from .errors import ApplicationError
from .kernel import InvocationKernel
from .mock_backend import MockKontomierzClient
from .operations import build_operations

_logger = logging.getLogger(__name__)

_TOOL_SIGNATURES: dict[str, str] = {
    "list_accounts": "",
    "create_wallet": (
        "currency_balance: str, currency_name: str, user_name: str | None = None, "
        "liquid: str = '1'"
    ),
    "update_wallet": (
        "wallet_id: int, currency_balance: str | None = None, currency_name: str | None = None, "
        "user_name: str | None = None, liquid: str | None = None"
    ),
    "destroy_wallet": "wallet_id: int",
    "list_transactions": (
        "page: int = 1, per_page: int = 0, user_account_id: int | None = None, q: str = '', "
        "start_on: str = '', end_on: str = '', direction: str = 'all', tag_name: str = '', "
        "category_group_id: int | None = None, category_id: int | None = None, "
        "show_hidden_transactions: bool = False"
    ),
    "get_transaction": "transaction_id: int",
    "create_transaction": (
        "client_assigned_id: str, user_account_id: int | None = None, category_id: int | None = None, "
        "currency_amount: str = '', currency_name: str = '', direction: str = 'withdrawal', "
        "tag_string: str = '', name: str = '', transaction_on: str = ''"
    ),
    "update_transaction": (
        "transaction_id: int, user_account_id: int | None = None, category_id: int | None = None, "
        "currency_amount: str | None = None, currency_name: str | None = None, "
        "direction: str | None = None, tag_string: str | None = None, name: str | None = None, "
        "transaction_on: str | None = None"
    ),
    "delete_transaction": "transaction_id: int",
    "list_categories": "direction: str = 'withdrawal'",
    "list_tags": "",
    "list_currencies": "",
    "list_budgets": "month: str = ''",
    "create_budget": (
        "limit: str, category_id: int | None = None, category_group_id: int | None = None, "
        "month: str = ''"
    ),
    "update_budget": "budget_id: int, limit: str",
    "delete_budget": "budget_id: int",
    "copy_budgets_from_last_month": "",
    "list_scheduled_transactions": (
        "schedule_group_name: str = 'unpaid', page: int = 1, per_page: int = 0, "
        "start_on: str = '', end_on: str = '', direction: str = 'all'"
    ),
    "get_schedule": "schedule_id: int",
    "create_schedule": (
        "direction: str, deadline_on: str, holidays: int, description: str, "
        "currency_amount: str, currency_name: str, repeat: int"
    ),
    "update_schedule": (
        "schedule_id: int, direction: str | None = None, deadline_on: str | None = None, "
        "holidays: int | None = None, description: str | None = None, "
        "currency_amount: str | None = None, currency_name: str | None = None, "
        "repeat: int | None = None"
    ),
    "delete_schedule": "schedule_id: int",
    "mark_schedule_paid": "schedule_id: int, payment_date: str",
    "mark_schedule_unpaid": "schedule_id: int, payment_date: str",
    "get_pie_chart": (
        "chart_kind: str = 'pie', start_on: str = '', end_on: str = '', direction: str = 'all', "
        "category_group_id: int | None = None, category_id: int | None = None, "
        "user_account_id: int | None = None, q: str = '', tag_name: str = ''"
    ),
    "list_wealth_points": "start_on: str = '', end_on: str = ''",
    "describe_kontomierz_capabilities": "",
}


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
    """Build one official MCP SDK v2 server with one invocation kernel."""
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
        instructions=(
            "Use list tools to discover stable IDs. Financial data is confidential. "
            "Writes require the operator gate. Reconcile any ambiguous write before retrying."
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

    for name, signature in _TOOL_SIGNATURES.items():
        namespace: dict[str, Any] = {"_dispatch": dispatch}
        exec(  # nosec B102 - signatures are immutable repository constants, never runtime input
            f"async def {name}({signature}):\n    return await _dispatch('{name}', locals())",
            namespace,
        )
        function = namespace[name]
        function.__doc__ = f"Kontomierz tool: {name}."
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
