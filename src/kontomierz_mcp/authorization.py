"""Application-owned authorization policy for principals, capabilities, and targets."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Literal

from .config import Settings
from .manifest_types import ToolManifest
from .security import InvocationContext

CapabilityClass = Literal["read", "write", "destructive"]
_POLICY_VERSION = "single-account-v1"


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """One server-side authorization decision bound to an exact target."""

    allowed: bool
    reason: str
    policy_version: str
    capability_id: str
    capability_class: CapabilityClass
    target_identity: str
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
    def _argument_digest(arguments: dict[str, Any]) -> str:
        encoded = json.dumps(
            arguments,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=repr,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    def authorize(
        self,
        context: InvocationContext,
        manifest: ToolManifest,
        arguments: dict[str, Any],
    ) -> AuthorizationDecision:
        capability_class = self.capability_class(manifest)
        target_identity = self.target_identity(manifest)
        digest = self._argument_digest(arguments)

        if not context.authenticated:
            return AuthorizationDecision(
                False,
                "principal is not authenticated",
                _POLICY_VERSION,
                manifest.name,
                capability_class,
                target_identity,
                digest,
            )

        expected_transport = "streamable-http" if self._settings.streamable_http else "stdio"
        if context.transport != expected_transport:
            return AuthorizationDecision(
                False,
                "principal transport does not match the active deployment transport",
                _POLICY_VERSION,
                manifest.name,
                capability_class,
                target_identity,
                digest,
            )

        if context.transport == "streamable-http":
            if not hmac.compare_digest(context.principal, self._settings.http_principal):
                return AuthorizationDecision(
                    False,
                    "HTTP principal is not bound to this deployment",
                    _POLICY_VERSION,
                    manifest.name,
                    capability_class,
                    target_identity,
                    digest,
                )
            if capability_class not in self._settings.http_allowed_capabilities:
                return AuthorizationDecision(
                    False,
                    f"capability class {capability_class} is not allowed for the HTTP principal",
                    _POLICY_VERSION,
                    manifest.name,
                    capability_class,
                    target_identity,
                    digest,
                )
        elif not context.principal.startswith("local-user:"):
            return AuthorizationDecision(
                False,
                "stdio principal is not process-derived",
                _POLICY_VERSION,
                manifest.name,
                capability_class,
                target_identity,
                digest,
            )

        return AuthorizationDecision(
            True,
            "principal, capability class, and configured target are authorized",
            _POLICY_VERSION,
            manifest.name,
            capability_class,
            target_identity,
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
            or current.capability_class != decision.capability_class
            or current.argument_digest != decision.argument_digest
        ):
            return AuthorizationDecision(
                False,
                "authorization binding changed before I/O",
                _POLICY_VERSION,
                current.capability_id,
                current.capability_class,
                current.target_identity,
                current.argument_digest,
            )
        return current
