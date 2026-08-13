"""Compatibility facade for governed manifest types and construction policy."""

from .manifest_policy import (
    _LOCAL_RETRY,
    _LOCAL_TARGET,
    manifest,
    p,
    project_manifest,
    read_manifest,
    write_manifest,
)
from .manifest_types import (
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
    ToolDefinition,
    ToolManifest,
    ToolParameter,
)

LOCAL_RETRY = _LOCAL_RETRY
LOCAL_TARGET = _LOCAL_TARGET

__all__ = [
    "ActiveState",
    "ClaimEvidence",
    "Confidentiality",
    "Cost",
    "Determinism",
    "IdempotencyMechanism",
    "Impact",
    "Latency",
    "LOCAL_RETRY",
    "LOCAL_TARGET",
    "RetryConditions",
    "Risk",
    "SideEffects",
    "TargetBinding",
    "ToolDefinition",
    "ToolManifest",
    "ToolParameter",
    "manifest",
    "p",
    "project_manifest",
    "read_manifest",
    "write_manifest",
]
