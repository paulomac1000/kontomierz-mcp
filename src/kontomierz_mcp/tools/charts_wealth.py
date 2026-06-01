"""Chart and wealth tools — [READ].

@since v1.0.0
"""

from typing import Any

from ..client import KontomierzClient
from ..response import error_dict, invoke_tool


def _do_get_pie_chart(
    client: KontomierzClient,
    chart_kind: str = "pie",
    start_on: str | None = None,
    end_on: str | None = None,
    direction: str | None = None,
    category_group_id: int | None = None,
    category_id: int | None = None,
    user_account_id: int | None = None,
    q: str | None = None,
    tag_name: str | None = None,
) -> dict[str, Any]:
    result = client.get_pie_chart(
        chart_kind=chart_kind,
        start_on=start_on,
        end_on=end_on,
        direction=direction,
        category_group_id=category_group_id,
        category_id=category_id,
        user_account_id=user_account_id,
        q=q,
        tag_name=tag_name,
    )
    if result is None:
        return {"success": False, "error": error_dict("API_ERROR", "Failed to fetch pie chart data.", retryable=True)}
    return {"success": True, "data": result}


def _do_get_wealth_points(
    client: KontomierzClient,
    start_on: str | None = None,
    end_on: str | None = None,
) -> dict[str, Any]:
    result = client.get_wealth_points(start_on, end_on)
    if result is None:
        return {"success": False, "error": error_dict("API_ERROR", "Failed to fetch wealth points.", retryable=True)}
    return {"success": True, "data": result}


def register_charts_wealth_tools(mcp: Any) -> None:

    @mcp.tool()
    async def get_pie_chart(
        chart_kind: str = "pie",
        start_on: str | None = None,
        end_on: str | None = None,
        direction: str | None = None,
        category_group_id: int | None = None,
        category_id: int | None = None,
        user_account_id: int | None = None,
        q: str | None = None,
        tag_name: str | None = None,
    ) -> str:
        """[READ] Get pie chart data for transaction breakdown.

        Args:
            chart_kind: Chart type, currently "pie".
            start_on, end_on: Date range (DD-MM-YYYY).
            direction: "withdrawals" or "deposits".
            category_group_id, category_id: Category filters.
            q: Search query.
            tag_name: Tag filter.

        Returns:
            JSON with chart data (type, data[slices]).
        @since v1.0.0
        """
        return await invoke_tool(
            mcp,
            "get_pie_chart",
            _do_get_pie_chart,
            chart_kind,
            start_on,
            end_on,
            direction,
            category_group_id,
            category_id,
            user_account_id,
            q,
            tag_name,
        )

    @mcp.tool()
    async def list_wealth_points(
        start_on: str | None = None,
        end_on: str | None = None,
    ) -> str:
        """[READ] List net worth history points (one per month).

        Args:
            start_on, end_on: Date range (DD-MM-YYYY).

        Returns:
            JSON with wealth points list (id, date_on, amount, notes).
        @since v1.0.0
        """
        return await invoke_tool(mcp, "list_wealth_points", _do_get_wealth_points, start_on, end_on)
