"""Transport-independent operation catalog."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .config import Settings
from .errors import ApplicationError, ErrorCode
from .manifests import TOOL_DEFINITIONS, TOOL_MANIFESTS
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
        definition = TOOL_DEFINITIONS[name]
        required = frozenset(definition.required_parameters)
        allowed = frozenset(parameter.name for parameter in definition.parameters)

        async def operation(**arguments: Any) -> Any:
            missing = sorted(required - arguments.keys())
            if missing:
                raise ApplicationError(
                    ErrorCode.INVALID_PARAMETER,
                    "Missing required parameter(s): " + ", ".join(missing),
                )
            unexpected = sorted(arguments.keys() - allowed)
            if unexpected:
                raise ApplicationError(
                    ErrorCode.INVALID_PARAMETER,
                    "Unexpected parameter(s): " + ", ".join(unexpected),
                )
            return await dispatch(name, arguments)

        return operation

    return {name: bind(name) for name in TOOL_MANIFESTS}
