from __future__ import annotations

import inspect
from typing import Annotated

from pydantic import Field

from kontomierz_mcp.manifests import (
    TOOL_DEFINITIONS,
    TOOL_MANIFESTS,
    project_manifest,
)

_REQUIRED_FIELDS = {
    "name",
    "version",
    "risk",
    "side_effects",
    "confidentiality",
    "idempotent",
    "idempotency_mechanism",
    "retryable",
    "retry_conditions",
    "concurrent_safe",
    "concurrency_scope",
    "timeout_ms",
    "requires_confirmation",
    "determinism",
    "latency",
    "cost",
    "impact",
    "reversible",
    "target_binding",
    "active_state",
    "claim_evidence",
}


def test_governed_catalog_has_one_complete_definition_per_tool() -> None:
    assert len(TOOL_DEFINITIONS) == 27
    assert set(TOOL_DEFINITIONS) == set(TOOL_MANIFESTS)
    for name, definition in TOOL_DEFINITIONS.items():
        assert definition.name == name
        assert definition.manifest is TOOL_MANIFESTS[name]
        assert _REQUIRED_FIELDS <= definition.manifest.as_dict().keys()
        assert definition.description.startswith(definition.summary)
        assert "side effects" in definition.description
        assert "confidentiality" in definition.description
        assert len(definition.description) >= 80


def test_manifest_claims_are_conservative_and_internally_consistent() -> None:
    for manifest in TOOL_MANIFESTS.values():
        assert manifest.version.startswith("2.0.0")
        assert manifest.timeout_ms > 0
        assert manifest.target_binding.fallback == "forbidden"
        assert manifest.automatic_retry is False
        assert all(
            value.strip()
            for value in (
                manifest.claim_evidence.idempotency,
                manifest.claim_evidence.retry,
                manifest.claim_evidence.concurrency,
                manifest.claim_evidence.reversibility,
            )
        )
        if manifest.retryable:
            assert manifest.idempotent is True
            assert manifest.retry_conditions.attempt_limit > 0
            assert manifest.retry_conditions.eligible_error_codes
        else:
            assert manifest.retry_conditions.attempt_limit == 0
            assert manifest.retry_conditions.eligible_error_codes == ()
        if manifest.idempotent:
            assert manifest.idempotency_mechanism != "none"
        else:
            assert manifest.idempotency_mechanism == "none"
        if manifest.side_effects in {"write", "destructive"}:
            assert manifest.requires_confirmation is True
            assert manifest.requires_operator_write_gate is True
            assert manifest.concurrent_safe is False
            assert manifest.reversible is False
            assert manifest.retryable is False


def test_parameter_contract_generates_stable_python_signatures() -> None:
    namespace: dict[str, object] = {"Annotated": Annotated, "Field": Field}
    for definition in TOOL_DEFINITIONS.values():
        exec(  # nosec B102 - immutable repository-owned signatures
            f"def {definition.name}({definition.signature}):\n    return None",
            namespace,
        )
        signature = inspect.signature(namespace[definition.name])
        assert tuple(signature.parameters) == tuple(parameter.name for parameter in definition.parameters)
        assert tuple(
            name for name, parameter in signature.parameters.items() if parameter.default is inspect.Parameter.empty
        ) == definition.required_parameters
        for parameter in definition.parameters:
            generated = signature.parameters[parameter.name]
            if not parameter.required:
                assert generated.default == parameter.default
            assert parameter.description.strip()


def test_active_projection_matches_dependency_and_operator_policy() -> None:
    read = TOOL_MANIFESTS["list_accounts"]
    write = TOOL_MANIFESTS["create_wallet"]
    local = TOOL_MANIFESTS["describe_kontomierz_capabilities"]

    assert project_manifest(write, writes_enabled=False, dependency_ready=True).active_state == "disabled"
    assert project_manifest(read, writes_enabled=True, dependency_ready=False).active_state == "unavailable"
    assert project_manifest(read, writes_enabled=True, dependency_ready=None).active_state == "degraded"
    assert project_manifest(read, writes_enabled=True, dependency_ready=True).active_state == "active"
    assert project_manifest(local, writes_enabled=False, dependency_ready=False).active_state == "active"
