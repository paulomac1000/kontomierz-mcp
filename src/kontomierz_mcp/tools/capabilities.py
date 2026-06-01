"""Capability introspection tool — [READ] describe_kontomierz_capabilities (L3+).

Returns the full tool catalog with manifests, supported transports, and schema version.
Zero I/O, instant latency.
"""

from typing import Any

from ..response import invoke_tool
from .constants import TOOL_MANIFESTS


def _do_describe_capabilities(client: Any = None) -> dict[str, Any]:
    return {
        "success": True,
        "data": {
            "schema_version": "1.0.0",
            "supported_transports": ["sse"],
            "tool_count": len(TOOL_MANIFESTS),
            "tools": TOOL_MANIFESTS,
        },
    }


def register_capability_tools(mcp: Any) -> None:

    @mcp.tool()
    async def describe_kontomierz_capabilities() -> str:
        """[READ] Describe all Kontomierz tool capabilities, manifests, supported transports, and schema version.

        Returns:
            JSON with tool catalog, manifests, supported transports, schema_version.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "describe_kontomierz_capabilities", _do_describe_capabilities)
