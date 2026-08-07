"""Governed public Kontomierz tool definitions."""

from __future__ import annotations

from .manifest_core import ToolDefinition, p, read_manifest, write_manifest

PRIMARY_TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    "list_accounts": ToolDefinition(
        read_manifest("list_accounts", confidentiality="financial"),
        "List configured accounts and wallets with balances.",
        usage_notes="Use stable numeric IDs from this result for wallet operations",
    ),
    "create_wallet": ToolDefinition(
        write_manifest("create_wallet"),
        "Create a wallet in the configured Kontomierz account.",
        (
            p(
                "currency_balance",
                "str",
                "Finite decimal starting balance; zero and negative debt balances are allowed.",
            ),
            p("currency_name", "str", "Three-letter currency code such as PLN."),
            p("user_name", "str | None", "Optional wallet label; an empty string is an explicit empty label.", None),
            p("liquid", "str", "Kontomierz liquidity flag: '0' or '1'.", "1"),
        ),
    ),
    "update_wallet": ToolDefinition(
        write_manifest("update_wallet"),
        "Update selected wallet fields.",
        (
            p("wallet_id", "int", "Stable positive wallet ID."),
            p("currency_balance", "str | None", "Finite decimal balance; None omits the field.", None),
            p("currency_name", "str | None", "Three-letter currency code; None omits the field.", None),
            p("user_name", "str | None", "Wallet label; empty string clears it and None omits it.", None),
            p("liquid", "str | None", "Kontomierz liquidity flag '0' or '1'; None omits it.", None),
        ),
    ),
    "destroy_wallet": ToolDefinition(
        write_manifest("destroy_wallet", destructive=True),
        "Delete a wallet by stable numeric ID.",
        (p("wallet_id", "int", "Stable positive wallet ID."),),
    ),
    "list_transactions": ToolDefinition(
        read_manifest("list_transactions", confidentiality="financial", cost="medium"),
        "List transactions with bounded filters and pagination hints.",
        (
            p("page", "int", "One-based page number.", 1),
            p("per_page", "int", "Page size from 1 to 100; 0 uses the upstream default.", 0),
            p("user_account_id", "int | None", "Optional positive account ID.", None),
            p("q", "str", "Optional free-text query.", ""),
            p("start_on", "str", "Optional ISO date YYYY-MM-DD.", ""),
            p("end_on", "str", "Optional ISO date YYYY-MM-DD; must not precede start_on.", ""),
            p("direction", "str", "withdrawal, deposit, or all.", "all"),
            p("tag_name", "str", "Optional exact tag name.", ""),
            p("category_group_id", "int | None", "Optional positive category-group ID.", None),
            p("category_id", "int | None", "Optional positive category ID.", None),
            p("show_hidden_transactions", "bool", "Include hidden transactions when true.", False),
        ),
        usage_notes="A full page only sets may_have_more and next_page_hint; it never proves continuation",
    ),
    "get_transaction": ToolDefinition(
        read_manifest("get_transaction", confidentiality="financial"),
        "Get one transaction by stable numeric ID.",
        (p("transaction_id", "int", "Stable positive transaction ID."),),
    ),
    "create_transaction": ToolDefinition(
        write_manifest("create_transaction"),
        "Create a transaction in the configured account.",
        (
            p("client_assigned_id", "str", "Required caller correlation ID used for reconciliation."),
            p("user_account_id", "int | None", "Optional positive account ID.", None),
            p("category_id", "int | None", "Optional positive category ID.", None),
            p("currency_amount", "str", "Optional positive finite decimal amount.", ""),
            p("currency_name", "str", "Optional three-letter currency code.", ""),
            p("direction", "str", "withdrawal or deposit.", "withdrawal"),
            p("tag_string", "str", "Optional tag string.", ""),
            p("name", "str", "Optional transaction name.", ""),
            p("transaction_on", "str", "Optional ISO date YYYY-MM-DD.", ""),
        ),
        usage_notes=(
            "client_assigned_id is required for reconciliation but replay-safe idempotency is not claimed "
            "until verified against a disposable real account"
        ),
    ),
    "update_transaction": ToolDefinition(
        write_manifest("update_transaction"),
        "Update selected transaction fields.",
        (
            p("transaction_id", "int", "Stable positive transaction ID."),
            p("user_account_id", "int | None", "Positive account ID; None omits the field.", None),
            p("category_id", "int | None", "Positive category ID; None omits the field.", None),
            p("currency_amount", "str | None", "Positive finite decimal; None omits the field.", None),
            p("currency_name", "str | None", "Three-letter currency code; None omits the field.", None),
            p("direction", "str | None", "withdrawal or deposit; None omits the field.", None),
            p("tag_string", "str | None", "Tag string; empty string clears it and None omits it.", None),
            p("name", "str | None", "Name; empty string clears it and None omits it.", None),
            p("transaction_on", "str | None", "ISO date YYYY-MM-DD; None omits the field.", None),
        ),
    ),
    "delete_transaction": ToolDefinition(
        write_manifest("delete_transaction", destructive=True),
        "Delete a transaction by stable numeric ID.",
        (p("transaction_id", "int", "Stable positive transaction ID."),),
    ),
    "list_categories": ToolDefinition(
        read_manifest("list_categories", confidentiality="personal"),
        "List the category hierarchy for one transaction direction.",
        (p("direction", "str", "withdrawal or deposit.", "withdrawal"),),
    ),
    "list_tags": ToolDefinition(
        read_manifest("list_tags", confidentiality="personal"),
        "List tags configured in the account.",
    ),
    "list_currencies": ToolDefinition(
        read_manifest("list_currencies", confidentiality="public"),
        "List currencies supported by the Kontomierz backend.",
    ),
}
