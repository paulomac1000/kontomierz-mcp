"""Transport-independent operation catalog."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .config import Settings
from .errors import ApplicationError, ErrorCode
from .manifests import TOOL_MANIFESTS
from .operation_primary import PRIMARY_NAMES, dispatch_primary
from .operation_secondary import dispatch_secondary

Operation = Callable[..., Awaitable[Any]]


def build_operations(client: Any, settings: Settings) -> dict[str, Operation]:
    """Bind validated operations to one dependency port."""

    async def dispatch(name: str, arguments: dict[str, Any]) -> Any:
        try:
            if name in PRIMARY_NAMES:
                return await dispatch_primary(name, arguments, client)
            return await dispatch_secondary(name, arguments, client, settings)
        except KeyError as exc:
            raise ApplicationError(ErrorCode.RESOURCE_NOT_FOUND, f"Unknown tool: {name}") from exc

    def bind(name: str) -> Operation:
        async def operation(**arguments: Any) -> Any:
            return await dispatch(name, arguments)

        return operation

    return {name: bind(name) for name in TOOL_MANIFESTS}
