"""Single invocation kernel shared by every public transport."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from . import __version__
from .config import Settings
from .errors import ApplicationError, ErrorCode, UpstreamError
from .manifests import TOOL_MANIFESTS, ToolManifest

Operation = Callable[..., Any | Awaitable[Any]]
_logger = logging.getLogger(__name__)


class InvocationKernel:
    """Resolve policy, bound admission/concurrency, execute, and shape results."""

    def __init__(self, *, settings: Settings, operations: dict[str, Operation], dependency: Any) -> None:
        self._settings = settings
        self._operations = operations
        self._dependency = dependency
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._admission_lock = asyncio.Lock()
        self._admitted_invocations = 0
        self._target_locks: dict[str, asyncio.Lock] = {}
        self._readiness_lock = asyncio.Lock()
        self._readiness_value = False
        self._readiness_checked_at = 0.0
        self._closed = False

    @property
    def structurally_ready(self) -> bool:
        return not self._closed and set(self._operations) == set(TOOL_MANIFESTS)

    async def readiness(self) -> bool:
        """Return cached readiness that includes the mandatory dependency."""
        if not self.structurally_ready:
            return False
        now = time.monotonic()
        if now - self._readiness_checked_at < self._settings.readiness_cache_seconds:
            return self._readiness_value
        async with self._readiness_lock:
            now = time.monotonic()
            if now - self._readiness_checked_at < self._settings.readiness_cache_seconds:
                return self._readiness_value
            probe = getattr(self._dependency, "probe", None)
            if not callable(probe):
                self._readiness_value = False
            else:
                try:
                    value = probe()
                    if inspect.isawaitable(value):
                        value = await asyncio.wait_for(value, timeout=self._settings.readiness_timeout_seconds)
                    self._readiness_value = bool(value)
                except (ApplicationError, TimeoutError):
                    self._readiness_value = False
                except Exception:
                    _logger.exception("Dependency readiness probe failed")
                    self._readiness_value = False
            self._readiness_checked_at = time.monotonic()
            return self._readiness_value

    @asynccontextmanager
    async def _admission_slot(self) -> AsyncIterator[None]:
        async with self._admission_lock:
            if self._admitted_invocations >= self._settings.max_pending_invocations:
                raise ApplicationError(
                    ErrorCode.RATE_LIMITED,
                    "Server invocation capacity is full",
                    retryable=True,
                    suggestion="Retry later; the operation did not start.",
                )
            self._admitted_invocations += 1
        try:
            yield
        finally:
            async with self._admission_lock:
                self._admitted_invocations -= 1

    @asynccontextmanager
    async def _execution_slot(self, manifest: ToolManifest) -> AsyncIterator[None]:
        lock = (
            None
            if manifest.concurrent_safe
            else self._target_locks.setdefault(manifest.target_scope, asyncio.Lock())
        )
        if lock is None:
            async with self._semaphore:
                yield
            return
        async with lock:
            async with self._semaphore:
                yield

    @staticmethod
    async def _run(operation: Operation, arguments: dict[str, Any]) -> Any:
        value = operation(**arguments)
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _normalize_error(manifest: ToolManifest, error: ApplicationError) -> ApplicationError:
        if (
            manifest.side_effects in {"write", "destructive"}
            and isinstance(error, UpstreamError)
            and error.write_outcome_ambiguous
        ):
            return ApplicationError(
                ErrorCode.AMBIGUOUS_OUTCOME,
                "The write may have completed",
                retryable=False,
                suggestion="Reconcile resource state before any retry.",
            )
        if manifest.side_effects in {"write", "destructive"} and error.retryable:
            return ApplicationError(
                error.code,
                error.message,
                retryable=False,
                suggestion=error.suggestion,
                details=error.details,
            )
        return error

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
        started_at = time.monotonic()
        operation_started = False
        async with self._admission_slot():
            try:
                async with asyncio.timeout(manifest.timeout_seconds):
                    async with self._execution_slot(manifest):
                        operation_started = True
                        data = await self._run(operation, arguments)
            except TimeoutError as exc:
                if operation_started and manifest.side_effects in {"write", "destructive"}:
                    raise ApplicationError(
                        ErrorCode.AMBIGUOUS_OUTCOME,
                        "The write may have completed",
                        retryable=False,
                        suggestion="Reconcile resource state before any retry.",
                    ) from exc
                raise ApplicationError(
                    ErrorCode.TIMEOUT,
                    "The operation exceeded its deadline",
                    retryable=False,
                ) from exc
            except asyncio.CancelledError:
                raise
            except ApplicationError as exc:
                raise self._normalize_error(manifest, exc) from exc
            except Exception as exc:
                _logger.exception("Unhandled operation failure request_id=%s tool=%s", request_id, tool_name)
                raise ApplicationError(ErrorCode.INTERNAL_ERROR, "The operation failed unexpectedly") from exc

        return {
            "data": data,
            "_meta": {
                "request_id": request_id,
                "tool_name": tool_name,
                "duration_ms": int((time.monotonic() - started_at) * 1000),
                "tool_version": __version__,
                "target": manifest.target_scope,
            },
        }

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self._dependency, "close", None)
        if callable(close):
            value = close()
            if inspect.isawaitable(value):
                await value
