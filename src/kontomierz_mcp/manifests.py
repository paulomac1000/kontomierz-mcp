"""Explicit capability manifests; no risk claim is inferred from a factory."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from . import __version__

SideEffects = Literal["none", "read", "write", "destructive"]
Confidentiality = Literal["public", "internal", "personal", "financial", "credential"]
Impact = Literal["none", "transient", "persistent", "financial"]
ManifestRow = tuple[
    str,
    SideEffects,
    Confidentiality,
    Impact,
    bool,
    bool,
    bool,
    bool,
    bool,
]


@dataclass(frozen=True, slots=True)
class ToolManifest:
    name: str
    side_effects: SideEffects
    confidentiality: Confidentiality
    impact: Impact
    idempotent: bool
    automatic_retry: bool
    reversible: bool
    concurrent_safe: bool
    requires_operator_write_gate: bool
    timeout_seconds: int = 30
    target_scope: str = "kontomierz-account"
    version: str = __version__

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


# Every positive retry/idempotency statement is operation-specific.
_MANIFEST_ROWS: tuple[ManifestRow, ...] = (
    ("list_accounts", "read", "financial", "none", True, True, True, True, False),
    ("create_wallet", "write", "financial", "financial", False, False, False, False, True),
    ("update_wallet", "write", "financial", "financial", True, False, False, False, True),
    ("destroy_wallet", "destructive", "financial", "financial", False, False, False, False, True),
    ("list_transactions", "read", "financial", "none", True, True, True, True, False),
    ("get_transaction", "read", "financial", "none", True, True, True, True, False),
    ("create_transaction", "write", "financial", "financial", True, False, False, False, True),
    ("update_transaction", "write", "financial", "financial", True, False, False, False, True),
    ("delete_transaction", "destructive", "financial", "financial", False, False, False, False, True),
    ("list_categories", "read", "personal", "none", True, True, True, True, False),
    ("list_tags", "read", "personal", "none", True, True, True, True, False),
    ("list_currencies", "read", "public", "none", True, True, True, True, False),
    ("list_budgets", "read", "financial", "none", True, True, True, True, False),
    ("create_budget", "write", "financial", "financial", False, False, False, False, True),
    ("update_budget", "write", "financial", "financial", True, False, False, False, True),
    ("delete_budget", "destructive", "financial", "financial", False, False, False, False, True),
    ("copy_budgets_from_last_month", "write", "financial", "financial", False, False, False, False, True),
    ("list_scheduled_transactions", "read", "financial", "none", True, True, True, True, False),
    ("get_schedule", "read", "financial", "none", True, True, True, True, False),
    ("create_schedule", "write", "financial", "financial", False, False, False, False, True),
    ("update_schedule", "write", "financial", "financial", True, False, False, False, True),
    ("delete_schedule", "destructive", "financial", "financial", False, False, False, False, True),
    ("mark_schedule_paid", "write", "financial", "financial", False, False, False, False, True),
    ("mark_schedule_unpaid", "write", "financial", "financial", False, False, False, False, True),
    ("get_pie_chart", "read", "financial", "none", True, True, True, True, False),
    ("list_wealth_points", "read", "financial", "none", True, True, True, True, False),
    ("describe_kontomierz_capabilities", "none", "public", "none", True, True, True, True, False),
)

TOOL_MANIFESTS: dict[str, ToolManifest] = {
    row[0]: ToolManifest(*row)
    for row in _MANIFEST_ROWS
}
