"""Reference tools — [READ] categories, tags, currencies.

@since v1.0.0
"""

from typing import Any

from ..client import KontomierzClient
from ..response import error_dict, invoke_tool
from ..validators import validate_direction


def _do_get_categories(client: KontomierzClient, direction: str) -> dict[str, Any]:
    validate_direction(direction)
    result = client.get_categories(direction)
    if result is None:
        return {"success": False, "error": error_dict("API_ERROR", f"Failed to fetch {direction} categories.", retryable=True)}
    return {"success": True, "data": result}


def _do_get_tags(client: KontomierzClient) -> dict[str, Any]:
    result = client.get_tags()
    if result is None:
        return {"success": False, "error": error_dict("API_ERROR", "Failed to fetch tags.", retryable=True)}
    return {"success": True, "data": result}


def _do_get_currencies(client: KontomierzClient) -> dict[str, Any]:
    result = client.get_currencies()
    if result is None:
        return {"success": False, "error": error_dict("API_ERROR", "Failed to fetch currencies.", retryable=True)}
    return {"success": True, "data": result}


def register_reference_tools(mcp: Any) -> None:

    @mcp.tool()
    async def list_categories(direction: str = "withdrawal") -> str:
        """[READ] List category tree. Direction: withdrawal or deposit.

        Args:
            direction: "withdrawal" (expense categories) or "deposit" (income categories).

        Returns:
            JSON with category tree.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "list_categories", _do_get_categories, direction)

    @mcp.tool()
    async def list_tags() -> str:
        """[READ] List user tags sorted by recent usage.

        Returns:
            JSON with tags list (id, name).
        @since v1.0.0
        """
        return await invoke_tool(mcp, "list_tags", _do_get_tags)

    @mcp.tool()
    async def list_currencies() -> str:
        """[READ] List currency dictionary (major, minor, trivial).

        Returns:
            JSON with currencies list (id, name, importance, full_name).
        @since v1.0.0
        """
        return await invoke_tool(mcp, "list_currencies", _do_get_currencies)
