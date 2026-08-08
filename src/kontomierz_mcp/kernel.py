"""Single invocation kernel shared by every public transport."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from importlib import import_module
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from typing import Any

from . import __version__
from .audit import InvocationAuditState, emit_invocation_audit
from .authorization import AuthorizationDecision, AuthorizationPolicy
from .config import Settings
from .errors import ApplicationError, ErrorCode, UpstreamError
from .manifests import TOOL_DEFINITIONS, TOOL_MANIFESTS, ToolManifest, project_manifest
from .security import InvocationContext, current_invocation_context

Operation = Callable[..., Any | Awaitable[Any]]
_logger = logging.getLogger(__name__)
_CAPABILITY_TOOL = "describe_kontomierz_capabilities"


class InvocationKernel:
    """Resolve policy, authenticate, bound concurrency, execute, and shape results."""

    def __init__(self, *, settings: Settings, operations: dict[str, Operation], dependency: Any) -> None:
        self._settings = settings
        self._operations = operations
        self._dependency = dependency
        self._authorization = AuthorizationPolicy(settings)
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._admission_lock = asyncio.Lock()
        self._admitted_invocations = 0
        self._target_locks: dict[str, asyncio.Lock] = {}
        self._readiness_lock = asyncio.Lock()
        self._readiness_value = settings.mock_data
        self._readiness_checked_at = time.monotonic() if settings.mock_data else 0.0
        self._closed = False

    @property
    def structurally_ready(self) -> bool:
        return not self._closed and set(self._operations) == set(TOOL_MANIFESTS)

    @property
    def cached_dependency_ready(self) -> bool | None:
        if self._readiness_checked_at == 0:
            return None
        return self._readiness_value

    async def readiness(self) -> bool:
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
            None if manifest.concurrent_safe else self._target_locks.setdefault(manifest.target_scope, asyncio.Lock())
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
        if error.retryable and not manifest.retryable:
            return ApplicationError(
                error.code,
                error.message,
                retryable=False,
                suggestion=error.suggestion,
                details=error.details,
            )
        return error

    @staticmethod
    def _sdk_identity() -> tuple[str, list[str]]:
        try:
            sdk_version = package_version("mcp")
        except PackageNotFoundError:
            sdk_version = "unavailable"
        try:
            version_module = import_module("mcp.shared.version")
            supported_protocol_versions = getattr(version_module, "SUPPORTED_PROTOCOL_VERSIONS", ())
            protocol_versions = [str(item) for item in supported_protocol_versions]
        except ImportError:
            protocol_versions = []
        return sdk_version, protocol_versions

    def capability_document(self, context: InvocationContext | None = None) -> dict[str, Any]:
        dependency_ready = self.cached_dependency_ready
        projected: dict[str, ToolManifest] = {}
        for name, definition in TOOL_DEFINITIONS.items():
            selected = project_manifest(
                definition.manifest,
                writes_enabled=self._settings.enable_write_operations,
                dependency_ready=dependency_ready,
            )
            if context is not None and not self._authorization.authorize(context, definition.manifest, {}).allowed:
                selected = replace(selected, active_state="disabled")
            projected[name] = selected
        tools = {name: TOOL_DEFINITIONS[name].as_dict(manifest=projected[name]) for name in TOOL_DEFINITIONS}
        active_tools = {name: contract for name, contract in tools.items() if projected[name].active_state == "active"}
        sdk_version, protocol_versions = self._sdk_identity()
        dependency_state = "unknown" if dependency_ready is None else ("ready" if dependency_ready else "unavailable")
        return {
            "schema_version": "3.0.0",
            "server_version": __version__,
            "sdk_family": "mcp-python",
            "sdk_version": sdk_version,
            "protocol_versions": protocol_versions,
            "supported_transports": ["stdio", "streamable-http"],
            "active_transport": "streamable-http" if self._settings.streamable_http else "stdio",
            "profile": "authenticated-http" if self._settings.streamable_http else "local-process-principal",
            "dependency_state": dependency_state,
            "write_operations_enabled": self._settings.enable_write_operations,
            "authorization_policy": "single-account-v1",
            "http_state_mode": "stateless" if self._settings.streamable_http else None,
            "http_allowed_capabilities": (
                list(self._settings.http_allowed_capabilities) if self._settings.streamable_http else None
            ),
            "http_max_request_body_bytes": (
                self._settings.http_max_request_body_bytes if self._settings.streamable_http else None
            ),
            "supported_component_count": len(tools),
            "active_component_count": len(active_tools),
            "tools": tools,
            "active_tools": active_tools,
        }

    async def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        context: InvocationContext | None = None,
    ) -> dict[str, Any]:
        request_id = uuid.uuid4().hex
        started_at = time.monotonic()
        audit = InvocationAuditState(request_id=request_id, tool_name=tool_name, started_at=started_at)
        try:
            result = await self._invoke_authorized(
                tool_name,
                arguments,
                context=context,
                request_id=request_id,
                started_at=started_at,
                audit=audit,
            )
            audit.result_category = "SUCCESS"
            return result
        except asyncio.CancelledError:
            audit.result_category = ErrorCode.CANCELLED.value
            audit.cancelled = True
            raise
        except ApplicationError as exc:
            audit.result_category = exc.code.value
            audit.ambiguous = exc.code is ErrorCode.AMBIGUOUS_OUTCOME
            audit.saturated = exc.code is ErrorCode.RATE_LIMITED and exc.message == "Server invocation capacity is full"
            raise
        finally:
            emit_invocation_audit(audit)

    async def _invoke_authorized(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        context: InvocationContext | None,
        request_id: str,
        started_at: float,
        audit: InvocationAuditState,
    ) -> dict[str, Any]:
        invocation_context = context
        if invocation_context is None:
            invocation_context = (
                InvocationContext.unauthenticated_http()
                if self._settings.streamable_http
                else InvocationContext.local_stdio()
            )
        audit.principal = invocation_context.principal
        audit.transport = invocation_context.transport
        audit.authenticated = invocation_context.authenticated
        audit.dependency_state = (
            "unknown"
            if self.cached_dependency_ready is None
            else ("ready" if self.cached_dependency_ready else "unavailable")
        )
        if not invocation_context.authenticated:
            audit.authorization_decision = "denied"
            audit.authorization_reason = "principal is not authenticated"
            raise ApplicationError(ErrorCode.AUTHENTICATION_FAILED, "Calling principal is not authenticated")
        if self._closed:
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE, "Server is shutting down", retryable=True)

        manifest = TOOL_MANIFESTS.get(tool_name)
        operation = self._operations.get(tool_name)
        if manifest is None or operation is None:
            raise ApplicationError(ErrorCode.RESOURCE_NOT_FOUND, f"Unknown tool: {tool_name}")

        decision = self._authorization.authorize(invocation_context, manifest, arguments)
        self._bind_authorization_audit(audit, decision, phase="initial")
        if not decision.allowed:
            raise ApplicationError(
                ErrorCode.AUTHORIZATION_FAILED,
                "Calling principal is not authorized for this capability",
            )

        projected = project_manifest(
            manifest,
            writes_enabled=self._settings.enable_write_operations,
            dependency_ready=self.cached_dependency_ready,
        )
        if projected.active_state == "unavailable":
            raise ApplicationError(
                ErrorCode.DEPENDENCY_UNAVAILABLE,
                "The configured Kontomierz dependency is not ready",
                retryable=manifest.retryable,
            )
        if manifest.requires_operator_write_gate:
            if not self._settings.enable_write_operations:
                audit.operator_gate_decision = "denied"
                raise ApplicationError(
                    ErrorCode.AUTHORIZATION_FAILED,
                    "Write operations are disabled by operator policy",
                    suggestion=(
                        "Set ENABLE_WRITE_OPERATIONS=1 in the trusted server environment "
                        "after reviewing the target and operation."
                    ),
                )
            audit.operator_gate_decision = "allowed"
        if manifest.requires_confirmation:
            audit.authorization_decision = "denied"
            audit.authorization_reason = "server-verified approval authority is not configured"
            raise ApplicationError(
                ErrorCode.AUTHORIZATION_FAILED,
                "This capability requires a server-verified approval record, but no approval authority is configured",
            )

        operation_started = False
        async with self._admission_slot():
            try:
                async with asyncio.timeout(manifest.timeout_seconds):
                    async with self._execution_slot(manifest):
                        revalidated = self._authorization.revalidate(decision, invocation_context, manifest, arguments)
                        self._bind_authorization_audit(audit, revalidated, phase="pre-io")
                        if not revalidated.allowed:
                            raise ApplicationError(
                                ErrorCode.AUTHORIZATION_FAILED,
                                "Authorization binding changed before operation I/O",
                            )
                        operation_started = True
                        data = (
                            self.capability_document(invocation_context)
                            if tool_name == _CAPABILITY_TOOL
                            else await self._run(operation, arguments)
                        )
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
                    retryable=manifest.retryable,
                    suggestion=(
                        "Retry only within the manifest attempt and deadline bounds." if manifest.retryable else None
                    ),
                ) from exc
            except asyncio.CancelledError:
                raise
            except ApplicationError as exc:
                normalized = self._normalize_error(manifest, exc)
                if normalized is exc:
                    raise
                raise normalized from exc
            except Exception as exc:
                _logger.exception("Unhandled operation failure request_id=%s tool=%s", request_id, tool_name)
                raise ApplicationError(ErrorCode.INTERNAL_ERROR, "The operation failed unexpectedly") from exc

        return {
            "data": data,
            "_meta": {
                "request_id": request_id,
                "tool_name": tool_name,
                "duration_ms": int((time.monotonic() - started_at) * 1000),
                "tool_version": manifest.version,
                "target": manifest.target_scope,
                "transport": invocation_context.transport,
            },
        }

    @staticmethod
    def _bind_authorization_audit(
        audit: InvocationAuditState,
        decision: AuthorizationDecision,
        *,
        phase: str,
    ) -> None:
        audit.capability_id = decision.capability_id
        audit.capability_class = decision.capability_class
        audit.target_identity = decision.target_identity
        audit.argument_digest = decision.argument_digest
        audit.policy_version = decision.policy_version
        audit.authorization_decision = f"{phase}:{'allowed' if decision.allowed else 'denied'}"
        audit.authorization_reason = decision.reason

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self._dependency, "close", None)
        if callable(close):
            value = close()
            if inspect.isawaitable(value):
                await value
