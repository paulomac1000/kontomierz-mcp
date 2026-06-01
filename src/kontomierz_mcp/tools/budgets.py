"""Budget tools — [READ] list + [WRITE] create/update/copy + [DESTRUCTIVE] delete.

@since v1.0.0
"""

from typing import Any

from ..client import KontomierzClient
from ..response import error_dict, invoke_tool
from ..validators import check_write_enabled, validate_required


def _do_list_budgets(client: KontomierzClient, month_on: str | None = None) -> dict[str, Any]:
    result = client.get_budgets(month_on)
    if result is None:
        return {"success": False, "error": error_dict("API_ERROR", "Failed to fetch budgets.", retryable=True)}
    budgets = result if isinstance(result, list) else []
    return {
        "success": True,
        "data": {
            "budgets": budgets,
            "total": len(budgets),
            "month_on": month_on,
        },
    }


def _do_create_budget(
    client: KontomierzClient,
    limit: str,
    category_id: int | None = None,
    category_group_id: int | None = None,
    month_on: str = "",
) -> dict[str, Any]:
    check_write_enabled()
    validate_required(limit, "limit")
    result = client.create_budget(limit, category_id, category_group_id, month_on)
    if result is None:
        return {
            "success": False,
            "error": error_dict(
                "API_ERROR",
                "Failed to create budget. It may already exist for this category/group in this month.",
                retryable=False,
            ),
        }
    return {"success": True, "data": result}


def _do_update_budget(client: KontomierzClient, budget_id: int, limit: str) -> dict[str, Any]:
    check_write_enabled()
    validate_required(limit, "limit")
    result = client.update_budget(budget_id, limit)
    if result is None:
        return {"success": False, "error": error_dict("API_ERROR", f"Failed to update budget {budget_id}.", retryable=True)}
    return {"success": True, "data": result}


def _do_delete_budget(client: KontomierzClient, budget_id: int) -> dict[str, Any]:
    check_write_enabled()
    if not client.delete_budget(budget_id):
        return {"success": False, "error": error_dict("API_ERROR", f"Failed to delete budget {budget_id}.", retryable=False)}
    return {"success": True, "data": {"deleted": True, "budget_id": budget_id}}


def _do_copy_budgets(client: KontomierzClient) -> dict[str, Any]:
    check_write_enabled()
    if not client.copy_budgets_from_last_month():
        return {"success": False, "error": error_dict("API_ERROR", "Failed to copy budgets from last month.", retryable=True)}
    return {"success": True, "data": {"copied": True}}


def register_budgets_tools(mcp: Any) -> None:

    @mcp.tool()
    async def list_budgets(month_on: str | None = None) -> str:
        """[READ] List budgets for a given month.

        Args:
            month_on: Month in format "01-MM-YYYY". Default: current month.

        Returns:
            JSON with budgets list (id, limit, amount, kind, name, category_id) and pagination metadata.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "list_budgets", _do_list_budgets, month_on)

    @mcp.tool()
    async def create_budget(
        limit: str,
        category_id: int | None = None,
        category_group_id: int | None = None,
        month_on: str = "",
    ) -> str:
        """[WRITE] Create a budget for a category or category group.

        Args:
            limit: Budget amount (string).
            category_id: Category ID (mutually exclusive with category_group_id).
            category_group_id: Category group ID (mutually exclusive with category_id).
            month_on: Month in format "01-MM-YYYY". Default: current month.

        Returns:
            JSON with created budget data or error.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "create_budget", _do_create_budget, limit, category_id, category_group_id, month_on)

    @mcp.tool()
    async def update_budget(budget_id: int, limit: str) -> str:
        """[WRITE] Update a budget limit.

        Args:
            budget_id: Numeric budget ID.
            limit: New budget amount (string).

        Returns:
            JSON with updated budget data or error.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "update_budget", _do_update_budget, budget_id, limit)

    @mcp.tool()
    async def delete_budget(budget_id: int) -> str:
        """[DESTRUCTIVE] Delete a budget.

        Args:
            budget_id: Numeric budget ID to delete.

        Returns:
            JSON with deletion confirmation or error.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "delete_budget", _do_delete_budget, budget_id)

    @mcp.tool()
    async def copy_budgets_from_last_month() -> str:
        """[WRITE] Copy all budgets from last month to the current month. Existing budgets are not overwritten.

        Returns:
            JSON with copy confirmation or error.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "copy_budgets_from_last_month", _do_copy_budgets)
