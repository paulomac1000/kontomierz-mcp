"""Remaining governed public Kontomierz tool definitions."""

from __future__ import annotations

from .manifest_core import (
    _LOCAL_RETRY,
    _LOCAL_TARGET,
    ClaimEvidence,
    ToolDefinition,
    manifest,
    p,
    read_manifest,
    write_manifest,
)

TERTIARY_TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    "create_schedule": ToolDefinition(
        write_manifest("create_schedule"),
        "Create a scheduled payment.",
        (
            p("direction", "str", "withdrawal or deposit."),
            p("deadline_on", "str", "ISO date YYYY-MM-DD."),
            p(
                "holidays",
                "int",
                "Holiday behavior: 0=no shift, 1=before weekend, 2=after weekend.",
            ),
            p("description", "str", "Non-empty schedule description."),
            p("currency_amount", "str", "Positive finite decimal amount."),
            p("currency_name", "str", "Three-letter currency code."),
            p(
                "repeat",
                "int",
                "Repeat code: 1=once, 8=weekly, 9=biweekly, 2=monthly, 7=bimonthly, "
                "3=quarterly, 4=semiannual, 5=yearly, 6=biennial.",
            ),
        ),
        usage_notes=(
            "The verified upstream returns an empty success body; the result therefore marks reconciliation_required "
            "and list_scheduled_transactions must be used to obtain the created stable ID"
        ),
    ),
    "update_schedule": ToolDefinition(
        write_manifest("update_schedule"),
        "Update selected scheduled-payment fields.",
        (
            p("schedule_id", "int", "Stable positive schedule ID."),
            p("direction", "str | None", "withdrawal or deposit; None omits the field.", None),
            p("deadline_on", "str | None", "ISO date YYYY-MM-DD; None omits the field.", None),
            p(
                "holidays",
                "int | None",
                "Holiday behavior: 0=no shift, 1=before weekend, 2=after weekend; None omits it.",
                None,
            ),
            p("description", "str | None", "Description; empty string clears it and None omits it.", None),
            p("currency_amount", "str | None", "Positive finite decimal; None omits the field.", None),
            p("currency_name", "str | None", "Three-letter currency code; None omits the field.", None),
            p(
                "repeat",
                "int | None",
                "Repeat code: 1=once, 8=weekly, 9=biweekly, 2=monthly, 7=bimonthly, "
                "3=quarterly, 4=semiannual, 5=yearly, 6=biennial; None omits the field.",
                None,
            ),
        ),
    ),
    "delete_schedule": ToolDefinition(
        write_manifest("delete_schedule", destructive=True),
        "Delete a scheduled payment by stable numeric ID.",
        (p("schedule_id", "int", "Stable positive schedule ID."),),
    ),
    "mark_schedule_paid": ToolDefinition(
        write_manifest("mark_schedule_paid"),
        "Mark a scheduled payment as paid on a specified date.",
        (
            p("schedule_id", "int", "Stable positive schedule ID."),
            p("payment_date", "str", "Payment date in ISO YYYY-MM-DD format."),
        ),
    ),
    "mark_schedule_unpaid": ToolDefinition(
        write_manifest("mark_schedule_unpaid"),
        "Mark a scheduled payment as unpaid for a specified date.",
        (
            p("schedule_id", "int", "Stable positive schedule ID."),
            p("payment_date", "str", "Payment date in ISO YYYY-MM-DD format."),
        ),
    ),
    "get_pie_chart": ToolDefinition(
        read_manifest("get_pie_chart", confidentiality="financial", cost="medium"),
        "Get bounded transaction chart data.",
        (
            p("chart_kind", "str", "Currently only pie is supported.", "pie"),
            p("start_on", "str", "Optional ISO date YYYY-MM-DD.", ""),
            p("end_on", "str", "Optional ISO date YYYY-MM-DD; must not precede start_on.", ""),
            p("direction", "str", "withdrawal, deposit, or all.", "all"),
            p("category_group_id", "int | None", "Optional positive category-group ID.", None),
            p("category_id", "int | None", "Optional positive category ID.", None),
            p("user_account_id", "int | None", "Optional positive account ID.", None),
            p("q", "str", "Optional free-text query.", ""),
            p("tag_name", "str", "Optional exact tag name.", ""),
        ),
    ),
    "list_wealth_points": ToolDefinition(
        read_manifest("list_wealth_points", confidentiality="financial"),
        "List net-worth history for an optional date range.",
        (
            p("start_on", "str", "Optional ISO date YYYY-MM-DD.", ""),
            p("end_on", "str", "Optional ISO date YYYY-MM-DD; must not precede start_on.", ""),
        ),
    ),
    "describe_kontomierz_capabilities": ToolDefinition(
        manifest(
            "describe_kontomierz_capabilities",
            risk="READ",
            side_effects="none",
            confidentiality="public",
            idempotent=True,
            idempotency_mechanism="natural",
            retryable=False,
            retry_conditions=_LOCAL_RETRY,
            concurrent_safe=True,
            concurrency_scope="process-catalog",
            timeout_ms=5_000,
            requires_confirmation=False,
            determinism="deterministic",
            latency="local",
            cost="low",
            impact="none",
            reversible=True,
            claim_evidence=ClaimEvidence(
                idempotency=(
                    "tests/integration/test_mcp_sdk_contract.py::"
                    "test_official_in_memory_capability_document_has_full_active_state"
                ),
                retry="No external I/O is performed by capability discovery, so retry is not part of the contract.",
                concurrency=(
                    "tests/unit/test_kernel_runtime.py::test_concurrency_limit_applies_to_running_async_operations"
                ),
                reversibility="Capability discovery has no application side effect to compensate.",
            ),
            target_binding=_LOCAL_TARGET,
            target_scope="kontomierz-server",
        ),
        "Describe supported and active capabilities without contacting the upstream service.",
        usage_notes="Returns schema, server and SDK identity, transport profile, tool definitions, and active states",
    ),
}
