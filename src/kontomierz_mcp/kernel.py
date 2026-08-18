"""Single invocation kernel shared by every public transport."""

from __future__ import annotations

import asyncio
import inspect
import json
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
from .authorization import AUTHORIZATION_POLICY_VERSION, AuthorizationDecision, AuthorizationPolicy
from .config import Settings
from .errors import ApplicationError, ErrorCode, UpstreamError
from .manifests import TOOL_DEFINITIONS, TOOL_MANIFESTS, ToolManifest, project_manifest
from .security import InvocationContext

Operation = Callable[..., Any | Awaitable[Any]]
_logger = logging.getLogger(__name__)
_CAPABILITY_TOOL = "describe_kontomierz_capabilities"
_CAPACITY_FULL_MESSAGE = "Server invocation capacity is full"
_SHUTDOWN_GRACE_SECONDS = 1.0


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
        self._drained = asyncio.Event()
        self._drained.set()
        self._close_lock = asyncio.Lock()
        self._dependency_closed = False
        self._target_locks: dict[str, asyncio.Lock] = {}
        self._readiness_lock = asyncio.Lock()
        self._readiness_value = settings.mock_data
        self._readiness_checked_at: float | None = time.monotonic() if settings.mock_data else None
        self._closed = False

    @property
    def structurally_ready(self) -> bool:
        return not self._closed and set(self._operations) == set(TOOL_MANIFESTS)

    @property
    def cached_dependency_ready(self) -> bool | None:
        if self._readiness_checked_at is None:
            return None
        return self._readiness_value

    async def readiness(self) -> bool:
        if not self.structurally_ready:
            return False
        now = time.monotonic()
        checked_at = self._readiness_checked_at
        if checked_at is not None and now - checked_at < self._settings.readiness_cache_seconds:
            return self._readiness_value
        async with self._readiness_lock:
            now = time.monotonic()
            checked_at = self._readiness_checked_at
            if checked_at is not None and now - checked_at < self._settings.readiness_cache_seconds:
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
            if self._closed:
                raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE, "Server is shutting down", retryable=True)
            if self._admitted_invocations >= self._settings.max_pending_invocations:
                raise ApplicationError(
                    ErrorCode.RATE_LIMITED,
                    _CAPACITY_FULL_MESSAGE,
                    retryable=True,
                    suggestion="Retry later; the operation did not start.",
                )
            self._admitted_invocations += 1
            self._drained.clear()
        try:
            yield
        finally:
            async with self._admission_lock:
                self._admitted_invocations -= 1
                if self._admitted_invocations == 0:
                    self._drained.set()

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
    def _encoded_size(document: dict[str, Any]) -> int:
        try:
            encoded = json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ApplicationError(ErrorCode.INTERNAL_ERROR, "Tool returned a non-serializable result") from exc
        return len(encoded)

    @classmethod
    def _bounded_result(
        cls,
        manifest: ToolManifest,
        data: Any,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        result = {"data": data, "_meta": metadata}
        if cls._encoded_size(result) <= manifest.max_response_bytes:
            return result

        if manifest.side_effects in {"write", "destructive"}:
            reduced = {
                "data": {
                    "completed": True,
                    "response_omitted": True,
                    "reconciliation_required": True,
                },
                "_meta": metadata,
            }
            if cls._encoded_size(reduced) <= manifest.max_response_bytes:
                return reduced

        raise ApplicationError(
            ErrorCode.UPSTREAM_FAILURE,
            "Tool response exceeds the configured safe output bound",
            retryable=False,
            suggestion="Narrow filters or use pagination before retrying when the tool supports them.",
            details={"max_response_bytes": manifest.max_response_bytes},
        )

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

    def capability_document(self, context: InvocationContext | None = None, *, verbose: bool = True) -> dict[str, Any]:
        dependency_ready = self.cached_dependency_ready
        projected: dict[str, ToolManifest] = {}
        for name, definition in TOOL_DEFINITIONS.items():
            selected = project_manifest(
                definition.manifest,
                writes_enabled=self._settings.enable_write_operations,
                dependency_ready=dependency_ready,
            )
            if context is not None and not self._authorization.capability_allowed(context, definition.manifest):
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
            "authorization_policy": AUTHORIZATION_POLICY_VERSION,
            "http_state_mode": "stateless" if self._settings.streamable_http else None,
            "http_allowed_capabilities": (
                list(self._settings.http_allowed_capabilities) if self._settings.streamable_http else None
            ),
            "stdio_allowed_destructive_capabilities": (
                list(self._settings.stdio_allowed_destructive_capabilities)
                if not self._settings.streamable_http
                else None
            ),
            "http_max_request_body_bytes": (
                self._settings.http_max_request_body_bytes if self._settings.streamable_http else None
            ),
            "supported_component_count": len(tools),
            "active_component_count": len(active_tools),
            "detail": "full" if verbose else "compact",
            "tools": tools if verbose else self._compact_tools(projected),
            "active_tools": active_tools if verbose else sorted(active_tools),
            "verbose": bool(verbose),
        }

    @staticmethod
    def _compact_tools(projected: dict[str, ToolManifest]) -> dict[str, dict[str, Any]]:
        compact: dict[str, dict[str, Any]] = {}
        for name, manifest_value in projected.items():
            compact[name] = {
                "risk": manifest_value.risk,
                "side_effects": manifest_value.side_effects,
                "active_state": manifest_value.active_state,
                "idempotent": manifest_value.idempotent,
                "retryable": manifest_value.retryable,
                "concurrent_safe": manifest_value.concurrent_safe,
                "concurrency_scope": manifest_value.concurrency_scope,
            }
        return compact

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
            audit.saturated = exc.code is ErrorCode.RATE_LIMITED and exc.message == _CAPACITY_FULL_MESSAGE
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
            # The reason states the failing server-owned policy (e.g. which capability
            # class or resource allowlist denied access) without secrets or arguments.
            raise ApplicationError(
                ErrorCode.AUTHORIZATION_FAILED,
                f"Calling principal is not authorized for this capability: {decision.reason}",
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
        executed_decision = decision
        async with self._admission_slot():
            timeout_scope = asyncio.timeout(manifest.timeout_seconds)
            try:
                async with timeout_scope:
                    async with self._execution_slot(manifest):
                        revalidated = self._authorization.revalidate(decision, invocation_context, manifest, arguments)
                        self._bind_authorization_audit(audit, revalidated, phase="pre-io")
                        if not revalidated.allowed:
                            raise ApplicationError(
                                ErrorCode.AUTHORIZATION_FAILED,
                                "Authorization binding changed before operation I/O",
                            )
                        executed_decision = revalidated
                        operation_started = True
                        data = (
                            self.capability_document(invocation_context, verbose=arguments.get("verbose") is True)
                            if tool_name == _CAPABILITY_TOOL
                            else await self._run(operation, arguments)
                        )
            except TimeoutError as exc:
                if not timeout_scope.expired():
                    raise
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
                if operation_started and manifest.side_effects in {"write", "destructive"}:
                    audit.ambiguous = True
                raise
            except ApplicationError as exc:
                normalized = self._normalize_error(manifest, exc)
                if normalized is exc:
                    raise
                raise normalized from exc
            except Exception as exc:
                _logger.exception("Unhandled operation failure request_id=%s tool=%s", request_id, tool_name)
                raise ApplicationError(ErrorCode.INTERNAL_ERROR, "The operation failed unexpectedly") from exc

        metadata = {
            "request_id": request_id,
            "tool_name": tool_name,
            "duration_ms": int((time.monotonic() - started_at) * 1000),
            "tool_version": manifest.version,
            "target_scope": manifest.target_scope,
            "target_ref": AuthorizationPolicy.public_target_ref(executed_decision.target_identity),
            "transport": invocation_context.transport,
        }
        return self._bounded_result(manifest, data, metadata)

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
        audit.resource_identity = decision.resource_identity
        audit.argument_digest = decision.argument_digest
        audit.policy_version = decision.policy_version
        audit.authorization_decision = f"{phase}:{'allowed' if decision.allowed else 'denied'}"
        audit.authorization_reason = decision.reason

    async def close(self) -> None:
        """Stop new admissions, drain bounded in-flight work, then close the dependency once."""
        async with self._close_lock:
            if self._dependency_closed:
                return
            async with self._admission_lock:
                self._closed = True
                if self._admitted_invocations == 0:
                    self._drained.set()

            longest_deadline = max((manifest.timeout_seconds for manifest in TOOL_MANIFESTS.values()), default=0.0)
            try:
                await asyncio.wait_for(self._drained.wait(), timeout=longest_deadline + _SHUTDOWN_GRACE_SECONDS)
            except TimeoutError:
                _logger.warning("Timed out draining in-flight invocations before dependency close")

            close = getattr(self._dependency, "close", None)
            if callable(close):
                value = close()
                if inspect.isawaitable(value):
                    await value
            self._dependency_closed = True
