"""Governed public Kontomierz tool definitions."""

from __future__ import annotations

from .manifest_core import ToolDefinition, p, read_manifest, write_manifest

SECONDARY_TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    "list_budgets": ToolDefinition(
        read_manifest("list_budgets", confidentiality="financial"),
        "List budgets, optionally for one month.",
        (p("month", "str", "Optional month in YYYY-MM format.", ""),),
    ),
    "create_budget": ToolDefinition(
        write_manifest("create_budget"),
        "Create a category or category-group budget.",
        (
            p("limit", "str", "Positive finite decimal budget limit."),
            p("category_id", "int | None", "Positive category ID; exactly one category selector is required.", None),
            p(
                "category_group_id",
                "int | None",
                "Positive category-group ID; exactly one category selector is required.",
                None,
            ),
            p("month", "str", "Optional month in YYYY-MM format.", ""),
        ),
    ),
    "update_budget": ToolDefinition(
        write_manifest("update_budget"),
        "Update a budget limit.",
        (
            p("budget_id", "int", "Stable positive budget ID."),
            p("limit", "str", "Positive finite decimal budget limit."),
        ),
    ),
    "delete_budget": ToolDefinition(
        write_manifest("delete_budget", destructive=True),
        "Delete a budget by stable numeric ID.",
        (p("budget_id", "int", "Stable positive budget ID."),),
    ),
    "copy_budgets_from_last_month": ToolDefinition(
        write_manifest("copy_budgets_from_last_month"),
        "Copy the previous month's budgets into the current month.",
        usage_notes="No idempotency is claimed; reconcile the resulting budget set before any retry",
    ),
    "list_scheduled_transactions": ToolDefinition(
        read_manifest("list_scheduled_transactions", confidentiality="financial"),
        "List paid or unpaid scheduled transactions with pagination hints.",
        (
            p("schedule_group_name", "str", "paid or unpaid.", "unpaid"),
            p("page", "int", "One-based page number.", 1),
            p("per_page", "int", "Page size from 1 to 100; 0 uses the upstream default.", 0),
            p("start_on", "str", "Optional ISO date YYYY-MM-DD.", ""),
            p("end_on", "str", "Optional ISO date YYYY-MM-DD; must not precede start_on.", ""),
            p("direction", "str", "withdrawal, deposit, or all.", "all"),
        ),
        usage_notes="A full page only sets may_have_more and next_page_hint",
    ),
    "get_schedule": ToolDefinition(
        read_manifest("get_schedule", confidentiality="financial"),
        "Get one scheduled payment by stable numeric ID.",
        (p("schedule_id", "int", "Stable positive schedule ID."),),
    ),
}
