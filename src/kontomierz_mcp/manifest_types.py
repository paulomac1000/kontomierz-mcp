"""Application-owned public tool catalog and governed capability manifests."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Risk = Literal["READ", "WRITE", "DESTRUCTIVE", "DANGEROUS", "SENSITIVE"]
SideEffects = Literal["none", "read", "write", "destructive"]
Confidentiality = Literal["public", "internal", "personal", "financial", "credential"]
IdempotencyMechanism = Literal["natural", "idempotency_key", "precondition", "deduplication", "none"]
Determinism = Literal["deterministic", "probabilistic", "env-dependent", "eventually-consistent"]
Latency = Literal["local", "interactive", "slow"]
Cost = Literal["low", "medium", "high"]
Impact = Literal["none", "transient", "persistent", "service_outage", "financial"]
ActiveState = Literal["active", "disabled", "degraded", "unavailable", "deprecated"]


@dataclass(frozen=True, slots=True)
class RetryConditions:
    eligible_error_codes: tuple[str, ...]
    attempt_limit: int
    backoff: str
    deadline_ms: int
    reconciliation_rule: str


@dataclass(frozen=True, slots=True)
class TargetBinding:
    identity: str
    revalidation: str
    fallback: Literal["forbidden"] = "forbidden"


@dataclass(frozen=True, slots=True)
class ClaimEvidence:
    idempotency: str
    retry: str
    concurrency: str
    reversibility: str


@dataclass(frozen=True, slots=True)
class ToolManifest:
    name: str
    version: str
    risk: Risk
    side_effects: SideEffects
    confidentiality: Confidentiality
    idempotent: bool
    idempotency_mechanism: IdempotencyMechanism
    retryable: bool
    retry_conditions: RetryConditions
    concurrent_safe: bool
    concurrency_scope: str
    timeout_ms: int
    requires_confirmation: bool
    determinism: Determinism
    latency: Latency
    cost: Cost
    impact: Impact
    reversible: bool
    target_binding: TargetBinding
    active_state: ActiveState
    claim_evidence: ClaimEvidence
    requires_operator_write_gate: bool
    target_scope: str = "kontomierz-account"
    automatic_retry: bool = False

    @property
    def timeout_seconds(self) -> float:
        return self.timeout_ms / 1000

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        retry = result["retry_conditions"]
        retry["eligible_error_codes"] = list(retry["eligible_error_codes"])
        return result


_MISSING = object()


@dataclass(frozen=True, slots=True)
class ToolParameter:
    name: str
    annotation: str
    description: str
    default: object = _MISSING

    @property
    def required(self) -> bool:
        return self.default is _MISSING

    @property
    def signature_fragment(self) -> str:
        annotation = f"Annotated[{self.annotation}, Field(description={self.description!r})]"
        fragment = f"{self.name}: {annotation}"
        return fragment if self.required else f"{fragment} = {self.default!r}"

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "type": self.annotation,
            "description": self.description,
            "required": self.required,
        }
        if not self.required:
            result["default"] = self.default
        return result


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    manifest: ToolManifest
    summary: str
    parameters: tuple[ToolParameter, ...] = ()
    usage_notes: str = ""

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def signature(self) -> str:
        return ", ".join(parameter.signature_fragment for parameter in self.parameters)

    @property
    def required_parameters(self) -> tuple[str, ...]:
        return tuple(parameter.name for parameter in self.parameters if parameter.required)

    @property
    def description(self) -> str:
        policy = (
            f"Risk {self.manifest.risk}; side effects {self.manifest.side_effects}; "
            f"confidentiality {self.manifest.confidentiality}."
        )
        controls: list[str] = []
        if self.manifest.requires_operator_write_gate:
            controls.append("Requires the trusted operator write gate")
        if self.manifest.requires_confirmation:
            controls.append("Requires a server-verified approval record")
        if self.manifest.side_effects in {"write", "destructive"}:
            controls.append("Never retry after an ambiguous outcome before reconciliation")
        elif self.manifest.retryable:
            controls.append("Only named transient read failures are caller-retryable")
        if self.usage_notes:
            controls.append(self.usage_notes.rstrip("."))
        suffix = ". ".join(controls)
        return f"{self.summary} {policy}" + (f" {suffix}." if suffix else "")

    def as_dict(self, *, manifest: ToolManifest | None = None) -> dict[str, Any]:
        selected = manifest or self.manifest
        return {
            "name": self.name,
            "version": selected.version,
            "description": self.description,
            "parameters": [parameter.as_dict() for parameter in self.parameters],
            "manifest": selected.as_dict(),
        }
