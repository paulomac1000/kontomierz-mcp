"""Single invocation kernel shared by every public transport."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import __version__
from .config import Settings
from .errors import ApplicationError, ErrorCode
from .manifests import TOOL_MANIFESTS
from .operations import Operation

_logger = logging.getLogger(__name__)


class InvocationKernel:
    """Resolve policy, bound concurrency/deadline, execute, and shape results."""

    def __init__(self, *, settings: Settings, operations: dict[str, Operation], dependency: Any) -> None:
        self._settings = settings
        self._operations = operations
        self._dependency = dependency
        self._executor = ThreadPoolExecutor(max_workers=settings.max_concurrency, thread_name_prefix="kontomierz")
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._closed = False

    @property
    def ready(self) -> bool:
        return not self._closed and len(self._operations) == len(TOOL_MANIFESTS)

    async def invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._closed:
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE, "Server is shutting down", retryable=True)
        manifest = TOOL_MANIFESTS.get(tool_name)
        operation = self._operations.get(tool_name)
        if manifest is None or operation is None:
            raise ApplicationError(ErrorCode.RESOURCE_NOT_FOUND, f"Unknown tool: {tool_name}")
        if manifest.requires_operator_write_gate and not self._settings.enable_write_operations:
            raise ApplicationError(
                ErrorCode.AUTHORIZATION_FAILED,
                "Write operations are disabled by operator policy",
                suggestion=(
                    "Set ENABLE_WRITE_OPERATIONS=1 in the trusted server environment "
                    "after reviewing the target and operation."
                ),
            )

        request_id = uuid.uuid4().hex
        started = time.monotonic()
        loop = asyncio.get_running_loop()
        async with self._semaphore:
            future = loop.run_in_executor(self._executor, lambda: operation(**arguments))
            try:
                data = await asyncio.wait_for(future, timeout=manifest.timeout_seconds)
            except TimeoutError as exc:
                future.cancel()
                error_code = (
                    ErrorCode.AMBIGUOUS_OUTCOME
                    if manifest.side_effects in {"write", "destructive"}
                    else ErrorCode.TIMEOUT
                )
                suggestion = (
                    "Reconcile resource state before any retry."
                    if manifest.side_effects in {"write", "destructive"}
                    else None
                )
                raise ApplicationError(
                    error_code,
                    "The operation exceeded its deadline",
                    retryable=manifest.automatic_retry,
                    suggestion=suggestion,
                ) from exc
            except asyncio.CancelledError:
                future.cancel()
                raise
            except ApplicationError:
                raise
            except Exception as exc:
                _logger.exception("Unhandled operation failure request_id=%s tool=%s", request_id, tool_name)
                raise ApplicationError(ErrorCode.INTERNAL_ERROR, "The operation failed unexpectedly") from exc
        return {
            "data": data,
            "_meta": {
                "request_id": request_id,
                "tool_name": tool_name,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "tool_version": __version__,
                "target": "kontomierz-account",
            },
        }

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=True)
        close = getattr(self._dependency, "close", None)
        if callable(close):
            close()
