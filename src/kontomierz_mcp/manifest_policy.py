"""Construction and runtime projection policy for governed capability manifests."""

from __future__ import annotations

from dataclasses import replace

from . import __version__
from .manifest_types import (
    _MISSING,
    ActiveState,
    ClaimEvidence,
    Confidentiality,
    Cost,
    Determinism,
    IdempotencyMechanism,
    Impact,
    Latency,
    RetryConditions,
    Risk,
    SideEffects,
    TargetBinding,
    ToolManifest,
    ToolParameter,
)

_DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024
_READ_RETRY = RetryConditions(
    eligible_error_codes=("TIMEOUT", "DEPENDENCY_UNAVAILABLE", "RATE_LIMITED"),
    attempt_limit=2,
    backoff="exponential-jitter; honor Retry-After when present",
    deadline_ms=60_000,
    reconciliation_rule="Preserve the exact target and arguments; never convert a write outcome into a read retry.",
)
_NO_RETRY = RetryConditions(
    eligible_error_codes=(),
    attempt_limit=0,
    backoff="none",
    deadline_ms=30_000,
    reconciliation_rule="Reconcile resource state before any retry after AMBIGUOUS_OUTCOME.",
)
_LOCAL_RETRY = RetryConditions(
    eligible_error_codes=(),
    attempt_limit=0,
    backoff="none",
    deadline_ms=5_000,
    reconciliation_rule="No external side effect exists.",
)
_ACCOUNT_TARGET = TargetBinding(
    identity="single process-owned Kontomierz account selected by immutable startup settings",
    revalidation=(
        "Reuse the configured base URL and credential scope immediately before I/O; never substitute a target."
    ),
)
_LOCAL_TARGET = TargetBinding(
    identity="local kontomierz-mcp process",
    revalidation="Use the current immutable settings snapshot and registered catalog.",
)


def p(name: str, annotation: str, description: str, default: object = _MISSING) -> ToolParameter:
    return ToolParameter(name, annotation, description, default)


def manifest(
    name: str,
    *,
    risk: Risk,
    side_effects: SideEffects,
    confidentiality: Confidentiality,
    idempotent: bool,
    idempotency_mechanism: IdempotencyMechanism,
    retryable: bool,
    retry_conditions: RetryConditions,
    concurrent_safe: bool,
    concurrency_scope: str,
    timeout_ms: int,
    requires_confirmation: bool,
    determinism: Determinism,
    latency: Latency,
    cost: Cost,
    impact: Impact,
    reversible: bool,
    target_binding: TargetBinding = _ACCOUNT_TARGET,
    claim_evidence: ClaimEvidence,
    requires_operator_write_gate: bool = False,
    target_scope: str = "kontomierz-account",
    max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
) -> ToolManifest:
    return ToolManifest(
        name=name,
        version=__version__,
        risk=risk,
        side_effects=side_effects,
        confidentiality=confidentiality,
        idempotent=idempotent,
        idempotency_mechanism=idempotency_mechanism,
        retryable=retryable,
        retry_conditions=retry_conditions,
        concurrent_safe=concurrent_safe,
        concurrency_scope=concurrency_scope,
        timeout_ms=timeout_ms,
        max_response_bytes=max_response_bytes,
        requires_confirmation=requires_confirmation,
        determinism=determinism,
        latency=latency,
        cost=cost,
        impact=impact,
        reversible=reversible,
        target_binding=target_binding,
        active_state="active",
        claim_evidence=claim_evidence,
        requires_operator_write_gate=requires_operator_write_gate,
        target_scope=target_scope,
    )


def read_manifest(
    name: str,
    *,
    confidentiality: Confidentiality,
    risk: Risk | None = None,
    cost: Cost = "low",
    timeout_ms: int = 30_000,
) -> ToolManifest:
    return manifest(
        name,
        risk=risk or ("SENSITIVE" if confidentiality != "public" else "READ"),
        side_effects="read",
        confidentiality=confidentiality,
        idempotent=True,
        idempotency_mechanism="natural",
        retryable=True,
        retry_conditions=_READ_RETRY,
        concurrent_safe=True,
        concurrency_scope="shared-client:kontomierz-account",
        timeout_ms=timeout_ms,
        requires_confirmation=False,
        determinism="env-dependent",
        latency="interactive",
        cost=cost,
        impact="none",
        reversible=True,
        claim_evidence=ClaimEvidence(
            idempotency=(
                "tests/unit/test_manifests_runtime.py::test_manifest_claims_are_conservative_and_internally_consistent"
            ),
            retry="tests/unit/test_kernel_runtime.py::test_read_dependency_timeout_is_not_ambiguous",
            concurrency="tests/unit/test_kernel_runtime.py::test_concurrency_limit_applies_to_running_async_operations",
            reversibility=(
                "tests/unit/test_manifests_runtime.py::test_manifest_claims_are_conservative_and_internally_consistent"
            ),
        ),
    )


def write_manifest(name: str, *, destructive: bool = False, impact: Impact = "financial") -> ToolManifest:
    return manifest(
        name,
        risk="DESTRUCTIVE" if destructive else "WRITE",
        side_effects="destructive" if destructive else "write",
        confidentiality="financial",
        idempotent=False,
        idempotency_mechanism="none",
        retryable=False,
        retry_conditions=_NO_RETRY,
        concurrent_safe=False,
        concurrency_scope="exclusive-target:kontomierz-account",
        timeout_ms=30_000,
        requires_confirmation=False,
        determinism="eventually-consistent",
        latency="interactive",
        cost="low",
        impact=impact,
        reversible=False,
        claim_evidence=ClaimEvidence(
            idempotency=(
                "tests/unit/test_manifests_runtime.py::test_manifest_claims_are_conservative_and_internally_consistent"
            ),
            retry="tests/unit/test_kernel_runtime.py::test_started_write_deadline_is_ambiguous",
            concurrency="tests/unit/test_kernel_runtime.py::test_non_concurrent_safe_writes_are_serialized_per_target",
            reversibility=(
                "tests/unit/test_manifests_runtime.py::test_manifest_claims_are_conservative_and_internally_consistent"
            ),
        ),
        requires_operator_write_gate=True,
    )


def project_manifest(
    manifest_value: ToolManifest,
    *,
    writes_enabled: bool,
    dependency_ready: bool | None,
) -> ToolManifest:
    state: ActiveState = "active"
    if manifest_value.requires_operator_write_gate and not writes_enabled:
        state = "disabled"
    elif manifest_value.name != "describe_kontomierz_capabilities" and dependency_ready is False:
        state = "unavailable"
    elif manifest_value.name != "describe_kontomierz_capabilities" and dependency_ready is None:
        state = "degraded"
    return replace(manifest_value, active_state=state)
