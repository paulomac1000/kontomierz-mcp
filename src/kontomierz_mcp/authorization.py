"""Application-owned authorization policy for principals, capabilities, targets, and resources."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Literal

from .config import Settings
from .errors import ApplicationError, ErrorCode
from .manifest_types import ToolManifest
from .security import InvocationContext

CapabilityClass = Literal["read", "write", "destructive"]
AUTHORIZATION_POLICY_VERSION = "single-account-resource-v3"

_RESOURCE_BINDINGS: dict[str, tuple[str, str | None]] = {
    "list_accounts": ("account", None),
    "create_wallet": ("wallet", None),
    "update_wallet": ("wallet", "wallet_id"),
    "destroy_wallet": ("wallet", "wallet_id"),
    "list_transactions": ("transaction", None),
    "get_transaction": ("transaction", "transaction_id"),
    "create_transaction": ("transaction", None),
    "update_transaction": ("transaction", "transaction_id"),
    "delete_transaction": ("transaction", "transaction_id"),
    "list_categories": ("category", None),
    "list_tags": ("tag", None),
    "list_currencies": ("currency", None),
    "list_budgets": ("budget", None),
    "create_budget": ("budget", None),
    "update_budget": ("budget", "budget_id"),
    "delete_budget": ("budget", "budget_id"),
    "copy_budgets_from_last_month": ("budget", None),
    "list_scheduled_transactions": ("schedule", None),
    "get_schedule": ("schedule", "schedule_id"),
    "create_schedule": ("schedule", None),
    "update_schedule": ("schedule", "schedule_id"),
    "delete_schedule": ("schedule", "schedule_id"),
    "mark_schedule_paid": ("schedule", "schedule_id"),
    "mark_schedule_unpaid": ("schedule", "schedule_id"),
    "get_pie_chart": ("chart", None),
    "list_wealth_points": ("wealth", None),
    "describe_kontomierz_capabilities": ("server", None),
}
_CREATE_CAPABILITIES = frozenset({"create_wallet", "create_transaction", "create_budget", "create_schedule"})


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """One server-side authorization decision bound to an exact target and resource."""

    allowed: bool
    reason: str
    policy_version: str
    capability_id: str
    capability_class: CapabilityClass
    target_identity: str
    resource_identity: str
    argument_digest: str


class AuthorizationPolicy:
    """Authorize one authenticated principal against the configured deployment target."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @staticmethod
    def capability_class(manifest: ToolManifest) -> CapabilityClass:
        if manifest.side_effects == "destructive":
            return "destructive"
        if manifest.side_effects == "write":
            return "write"
        return "read"

    def target_identity(self, manifest: ToolManifest) -> str:
        if manifest.target_scope == "kontomierz-server":
            return "kontomierz-mcp:local-process"
        if self._settings.mock_data:
            return "kontomierz:mock-account"
        fingerprint = hashlib.sha256(self._settings.api_key.encode("utf-8")).hexdigest()[:16]
        return f"kontomierz:{self._settings.api_base_url}:credential-sha256:{fingerprint}"

    @staticmethod
    def public_target_ref(target_identity: str) -> str:
        digest = hashlib.sha256(target_identity.encode("utf-8")).hexdigest()[:16]
        return f"target:sha256:{digest}"

    @staticmethod
    def resource_identity(manifest: ToolManifest, arguments: dict[str, Any]) -> str:
        """Resolve the exact governed resource before authorization can succeed."""
        resource_kind, id_field = _RESOURCE_BINDINGS.get(manifest.name, ("capability", None))
        if id_field is not None:
            raw_id = arguments.get(id_field)
            if type(raw_id) is not int or raw_id <= 0:
                raise ApplicationError(ErrorCode.INVALID_PARAMETER, f"{id_field} must be a positive integer")
            return f"{resource_kind}:{raw_id}"
        if manifest.name == "describe_kontomierz_capabilities":
            return "server:catalog"
        if manifest.name == "create_transaction":
            correlation = arguments.get("client_assigned_id")
            if isinstance(correlation, str) and correlation:
                digest = hashlib.sha256(correlation.encode("utf-8")).hexdigest()[:16]
                return f"transaction:new:client-assigned-sha256:{digest}"
            return "transaction:new"
        if manifest.name in _CREATE_CAPABILITIES:
            return f"{resource_kind}:new"
        return f"{resource_kind}:collection"

    @staticmethod
    def _argument_digest(arguments: dict[str, Any]) -> str:
        encoded = json.dumps(
            arguments,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=repr,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    @staticmethod
    def _decision(
        allowed: bool,
        reason: str,
        manifest: ToolManifest,
        capability_class: CapabilityClass,
        target_identity: str,
        resource_identity: str,
        digest: str,
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed,
            reason,
            AUTHORIZATION_POLICY_VERSION,
            manifest.name,
            capability_class,
            target_identity,
            resource_identity,
            digest,
        )

    def _capability_policy(self, context: InvocationContext, manifest: ToolManifest) -> tuple[bool, str]:
        capability_class = self.capability_class(manifest)
        if manifest.name not in _RESOURCE_BINDINGS:
            return False, "capability has no governed resource binding"
        if not context.authenticated:
            return False, "principal is not authenticated"

        expected_transport = "streamable-http" if self._settings.streamable_http else "stdio"
        if context.transport != expected_transport:
            return False, "principal transport does not match the active deployment transport"

        if context.transport == "streamable-http":
            if not hmac.compare_digest(context.principal, self._settings.http_principal):
                return False, "HTTP principal is not bound to this deployment"
            if capability_class not in self._settings.http_allowed_capabilities:
                return False, f"capability class {capability_class} is not allowed for the HTTP principal"
            if (
                capability_class == "destructive"
                and manifest.name not in self._settings.http_allowed_destructive_capabilities
            ):
                return False, "destructive capability is not explicitly allowlisted for the HTTP principal"
            return True, "principal and exact capability are authorized"

        if not context.principal.startswith("local-process:"):
            return False, "stdio principal is not process-derived"
        if (
            capability_class == "destructive"
            and manifest.name not in self._settings.stdio_allowed_destructive_capabilities
        ):
            return False, "destructive capability is not explicitly allowlisted for the stdio principal"
        return True, "local process principal and exact capability are authorized"

    def capability_allowed(self, context: InvocationContext, manifest: ToolManifest) -> bool:
        """Return whether the capability is discoverable before resource arguments are known."""
        allowed, _reason = self._capability_policy(context, manifest)
        return allowed

    def authorize(
        self,
        context: InvocationContext,
        manifest: ToolManifest,
        arguments: dict[str, Any],
    ) -> AuthorizationDecision:
        capability_class = self.capability_class(manifest)
        target_identity = self.target_identity(manifest)
        resource_identity = self.resource_identity(manifest, arguments)
        digest = self._argument_digest(arguments)

        capability_allowed, reason = self._capability_policy(context, manifest)
        if not capability_allowed:
            return self._decision(
                False,
                reason,
                manifest,
                capability_class,
                target_identity,
                resource_identity,
                digest,
            )

        if (
            context.transport == "streamable-http"
            and capability_class == "destructive"
            and resource_identity not in self._settings.http_allowed_destructive_resources
        ):
            return self._decision(
                False,
                "destructive resource is not explicitly allowlisted for the HTTP principal",
                manifest,
                capability_class,
                target_identity,
                resource_identity,
                digest,
            )
        if (
            context.transport == "stdio"
            and capability_class == "destructive"
            and resource_identity not in self._settings.stdio_allowed_destructive_resources
        ):
            return self._decision(
                False,
                "destructive resource is not explicitly allowlisted for the stdio principal",
                manifest,
                capability_class,
                target_identity,
                resource_identity,
                digest,
            )

        return self._decision(
            True,
            "principal, capability, target, and exact resource are authorized",
            manifest,
            capability_class,
            target_identity,
            resource_identity,
            digest,
        )

    def revalidate(
        self,
        decision: AuthorizationDecision,
        context: InvocationContext,
        manifest: ToolManifest,
        arguments: dict[str, Any],
    ) -> AuthorizationDecision:
        """Repeat the policy decision immediately before operation I/O."""
        current = self.authorize(context, manifest, arguments)
        if not current.allowed:
            return current
        if (
            current.capability_id != decision.capability_id
            or current.target_identity != decision.target_identity
            or current.resource_identity != decision.resource_identity
            or current.capability_class != decision.capability_class
            or current.argument_digest != decision.argument_digest
        ):
            return AuthorizationDecision(
                False,
                "authorization binding changed before I/O",
                AUTHORIZATION_POLICY_VERSION,
                current.capability_id,
                current.capability_class,
                current.target_identity,
                current.resource_identity,
                current.argument_digest,
            )
        return current
