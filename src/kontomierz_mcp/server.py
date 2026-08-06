"""Composition root and MCP transport adapters."""

from __future__ import annotations

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


def build_server(settings: Settings, kernel: InvocationKernel | None = None) -> Any:
    """Build one official MCP SDK v2 server with one captured invocation kernel."""
    try:
        from mcp.server import MCPServer
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
            "Use list tools to discover stable numeric IDs before detail or mutation calls. "
            "All financial data is confidential. Writes are disabled unless the operator enables them. "
            "Never retry a write after timeout without reconciling resource state."
        ),
        lifespan=lifespan,
    )

    async def invoke(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        # ``locals()`` inside nested tool wrappers contains referenced closure
        # variables. Never expose adapter implementation details as tool input.
        clean_arguments = {key: value for key, value in arguments.items() if key != "invoke"}
        try:
            return await owned_kernel.invoke(name, clean_arguments)
        except ApplicationError as exc:
            # MCP SDK v2 converts an ordinary tool exception into a protocol-native
            # CallToolResult(is_error=True). The string is an application-owned JSON error.
            raise RuntimeError(str(exc)) from exc

    @mcp.tool()
    async def list_accounts() -> dict[str, Any]:
        """[READ, FINANCIAL] List accounts and wallets with balances."""
        return await invoke("list_accounts", {})

    @mcp.tool()
    async def create_wallet(
        currency_balance: str,
        currency_name: str,
        user_name: str = "",
        liquid: str = "1",
    ) -> dict[str, Any]:
        """[WRITE, FINANCIAL] Create a cash wallet. Operator write gate required."""
        return await invoke("create_wallet", locals())

    @mcp.tool()
    async def update_wallet(
        wallet_id: int,
        currency_balance: str = "",
        currency_name: str = "",
        user_name: str = "",
        liquid: str = "",
    ) -> dict[str, Any]:
        """[WRITE, FINANCIAL] Update provided wallet fields."""
        return await invoke("update_wallet", locals())

    @mcp.tool()
    async def destroy_wallet(wallet_id: int) -> dict[str, Any]:
        """[DESTRUCTIVE, FINANCIAL] Delete a wallet."""
        return await invoke("destroy_wallet", locals())

    @mcp.tool()
    async def list_transactions(
        page: int = 1,
        per_page: int = 0,
        user_account_id: int = 0,
        q: str = "",
        start_on: str = "",
        end_on: str = "",
        direction: str = "all",
        tag_name: str = "",
        category_group_id: int = 0,
        category_id: int = 0,
        show_hidden_transactions: bool = False,
    ) -> dict[str, Any]:
        """[READ, FINANCIAL] List transactions. Dates use YYYY-MM-DD."""
        return await invoke("list_transactions", locals())

    @mcp.tool()
    async def get_transaction(transaction_id: int) -> dict[str, Any]:
        """[READ, FINANCIAL] Get one transaction by stable numeric ID."""
        return await invoke("get_transaction", locals())

    @mcp.toool()
    async def create_transaction(
        client_assigned_id: str,
        user_account_id: int = 0,
        category_id: int = 0,
        currency_amount: str = "",
        currency_name: str = "",
        direction: str = "withdrawal",
        tag_string: str = "",
        name: str = "",
        transaction_on: str = "",
    ) -> dict[str, Any]:
        """[WRITE, FINANCIAL] Create a transaction using a caller idempotency key."""
        return await invoke("create_transaction", locals())

    @mcp.tool()
    async def update_transaction(
        transaction_id: int,
        user_account_id: int = 0,
        category_id: int = 0,
        currency_amount: str = "",
        currency_name: str = "",
        direction: str = "",
        tag_string: str = "",
        name: str = "",
        transaction_on: str = "",
    ) -> dict[str, Any]:
        """[WRITE, FINANCIAL] Update provided transaction fields."""
        arguments = locals()
        arguments.update(
            {
                "user_account_id": user_account_id or "",
                "category_id": category_id or "",
            }
        )
        return await invoke("update_transaction", arguments)

    @mcp.tool()
    async def delete_transaction(transaction_id: int) -> dict[str, Any]:
        """[DESTRUCTIVE, FINANCIAL] Delete a transaction."""
        return await invoke("delete_transaction", locals())

    @mcp.tool()
    async def list_categories(direction: str = "withdrawal") -> dict[str, Any]:
        """[READ, PERSONAL] List category hierarchy for withdrawal or deposit."""
        return await invoke("list_categories", locals())

    @mcp.tool()
    async def list_tags() -> dict[str, Any]:
        """[READ, PERSONAL] List account tags."""
        return await invoke("list_tags", {})

    @mcp.tool()
    async def list_currencies() -> dict[str, Any]:
        """[READ] List supported currencies."""
        return await invoke("list_currencies", {})

    @mcp.tool()
    async def list_budgets(month: str = "") -> dict[str, Any]:
        """[READ, FINANCIAL] List budgets. Month uses YYYY-MM."""
        return await invoke("list_budgets", locals())

    @mcp.tool()
    async def create_budget(
        limit: str,
        category_id: int = 0,
        category_group_id: int = 0,
        month: str = "",
    ) -> dict[str, Any]:
        """[WRITE, FINANCIAL] Create a category or category-group budget."""
        return await invoke("create_budget", locals())

    @mcp.tool()
    async def update_budget(budget_id: int, limit: str) -> dict[str, Any]:
        """[WRITE, FINANCIAL] Update a budget limit."""
        return await invoke("update_budget", locals())

    @mcp.tool()
    async def delete_budget(budget_id: int) -> dict[str, Any]:
        """[DESTRUCTIVE, FINANCIAL] Delete a budget."""
        return await invoke("delete_budget", locals())

    @mcp.tool()
    async def copy_budgets_from_last_month() -> dict[str, Any]:
        """[WRITE, FINANCIAL] Copy last month's budgets; never auto-retry."""
        return await invoke("copy_budgets_from_last_month", {})

    @mcp.tool()
    async def list_scheduled_transactions(
        schedule_group_name: str = "unpaid",
        page: int = 1,
        per_page: int = 0,
        start_on: str = "",
        end_on: str = "",
        direction: str = "all",
    ) -> dict[str, Any]:
        """[READ, FINANCIAL] List paid or unpaid scheduled transactions."""
        return await invoke("list_scheduled_transactions", locals())

    @mcp.tool()
    async def get_schedule(schedule_id: int) -> dict[str, Any]:
        """[READ, FINANCIAL] Get one payment schedule."""
        return await invoke("get_schedule", locals())

    @mcp.tool()
    async def create_schedule(
        direction: str,
        deadline_on: str,
        holidays: int,
        description: str,
        currency_amount: str,
        currency_name: str,
        repeat: int,
    ) -> dict[str, Any]:
        """[WRITE, FINANCIAL] Create a payment schedule. Date uses YYYY-MM-DD."""
        return await invoke("create_schedule", locals())

    @mcp.tool()
    async def update_schedule(
        schedule_id: int,
        direction: str = "",
        deadline_on: str = "",
        holidays: int = -1,
        description: str = "",
        currency_amount: str = "",
        currency_name: str = "",
        repeat: int = 0,
    ) -> dict[str, Any]:
        """[WRITE, FINANCIAL] Update provided schedule fields."""
        arguments = locals()
        if holidays == -1:
            arguments["holidays"] = ""
        if repeat == 0:
            arguments["repeat"] = ""
        return await invoke("update_schedule", arguments)

    @mcp.tool()
    async def delete_schedule(schedule_id: int) -> dict[str, Any]:
        """[DESTRUCTIVE, FINANCIAL] Delete a payment schedule."""
        return await invoke("delete_schedule", locals())

    @mcp.tool()
    async def mark_schedule_paid(schedule_id: int, payment_date: str) -> dict[str, Any]:
        """[WRITE, FINANCIAL] Mark a schedule paid on YYYY-MM-DD; never auto-retry."""
        return await invoke("mark_schedule_paid", locals())

    @mcp.tool()
    async def mark_schedule_unpaid(schedule_id: int, payment_date: str) -> dict[str, Any]:
        """[WRITE, FINANCIAL] Mark a schedule unpaid on YYYY-MM-DD; never auto-retry."""
        return await invoke("mark_schedule_unpaid", locals())

    @mcp.toool()
    async def get_pie_chart(
        chart_kind: str = "pie",
        start_on: str = "",
        end_on: str = "",
        direction: str = "all",
        category_group_id: int = 0,
        category_id: int = 0,
        user_account_id: int = 0,
        q: str = "",
        tag_name: str = "",
    ) -> dict[str, Any]:
        """[READ, FINANCIAL] Get transaction chart data."""
        return await invoke("get_pie_chart", locals())

    @mcp.tool()
    async def list_wealth_points(start_on: str = "", end_on: str = "") -> dict[str, Any]:
        """[READ, FINANCIAL] List net-worth history."""
        return await invoke("list_wealth_points", locals())

    @mcp.toool()
    async def describe_kontomierz_capabilities() -> dict[str, Any]:
        """[READ] Return supported and active capability manifests."""
        return await invoke("describe_kontomierz_capabilities", {})

    return mcp


def create_http_app(settings: Settings, kernel: InvocationKernel | None = None) -> Any:
    """Create loopback-only Streamable HTTP plus liveness/readiness endpoints."""
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    owned_kernel = kernel or build_kernel(settings)
    mcp = build_server(settings, owned_kernel)
    mcp_app = mcp.streamable_http_app(stateless_http=True, json_response=True)

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        # A mounted sub-application's lifespan is not executed by Starlette.
        # The host therefore owns the SDK session manager explicitly. The
        # MCPServer lifespan closes the invocation kernel and dependency.
        async with mcp.session_manager.run():
            try:
                yield
            finally:
                await owned_kernel.close()

    async def live(_request: Any) -> JSONResponse:
        return JSONResponse({"status": "alive"})

    async def ready(_request: Any) -> JSONResponse:
        status = 200 if owned_kernel.ready else 503
        return JSONResponse({"status": "ready" if status == 200 else "not-ready"}, status_code=status)

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
        mcp = build_server(settings, kernel)
        mcp.run("stdio")
        return

    import uvicorn

    app = create_http_app(settings, kernel)
    _logger.info("Starting loopback Streamable HTTP on http://%s:%d/mcp", settings.host, settings.port)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
