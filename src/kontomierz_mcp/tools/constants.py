"""SSOT constants + Tool Manifests with factory functions (Template 5c)."""

import os
from typing import Any

KONTOMIERZ_API_KEY = os.getenv("KONTOMIERZ_API_KEY", "")

API_BASE_URL = "https://secure.kontomierz.pl/k4"
API_TIMEOUT = int(os.getenv("KONTOMIERZ_API_TIMEOUT", "30"))

MCP_PORT = int(os.getenv("MCP_PORT", "9101"))
REST_API_PORT = int(os.getenv("REST_API_PORT", "9102"))
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "9100"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENABLE_WRITE_OPERATIONS = os.getenv("ENABLE_WRITE_OPERATIONS", "false").lower() in (
    "true",
    "1",
    "yes",
    "on",
)

TOOLS_VERSION = "1.0.0"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# ------------------------------------------------------------------
# Tool Manifest — Single Source of Truth for capability descriptors
# ------------------------------------------------------------------

KNOWN_RISK_PREFIXES = frozenset({"[READ]", "[WRITE]", "[DANGEROUS]", "[DESTRUCTIVE]", "[SENSITIVE]"})


def _make_read_manifest(name: str, timeout_ms: int = 15000, latency: str = "moderate") -> dict[str, Any]:
    return {
        "name": name,
        "version": TOOLS_VERSION,
        "risk": "READ",
        "side_effects": "read",
        "idempotent": True,
        "retryable": True,
        "concurrent_safe": True,
        "timeout_ms": timeout_ms,
        "requires_confirmation": False,
        "determinism": "env-dependent",
        "latency": latency,
        "cost": "cheap",
        "impact": "none",
        "privacy": "none",
        "reversible": True,
    }


def _make_write_manifest(name: str, timeout_ms: int = 15000, latency: str = "moderate") -> dict[str, Any]:
    return {
        "name": name,
        "version": TOOLS_VERSION,
        "risk": "WRITE",
        "side_effects": "write",
        "idempotent": True,
        "retryable": True,
        "concurrent_safe": False,
        "timeout_ms": timeout_ms,
        "requires_confirmation": True,
        "determinism": "env-dependent",
        "latency": latency,
        "cost": "moderate",
        "impact": "persistent",
        "privacy": "none",
        "reversible": True,
    }


def _make_destructive_manifest(name: str, timeout_ms: int = 30000, latency: str = "slow") -> dict[str, Any]:
    """Manifest for irreversible operations: reboot, factory reset, delete."""
    return {
        "name": name,
        "version": TOOLS_VERSION,
        "risk": "DESTRUCTIVE",
        "side_effects": "destructive",
        "idempotent": False,
        "retryable": False,
        "concurrent_safe": False,
        "timeout_ms": timeout_ms,
        "requires_confirmation": True,
        "determinism": "env-dependent",
        "latency": latency,
        "cost": "expensive",
        "impact": "service_outage",
        "privacy": "none",
        "reversible": False,
    }


TOOL_MANIFESTS: dict[str, dict[str, Any]] = {
    # Accounts
    "list_accounts": _make_read_manifest("list_accounts"),
    "create_wallet": _make_write_manifest("create_wallet"),
    "update_wallet": _make_write_manifest("update_wallet"),
    "destroy_wallet": _make_destructive_manifest("destroy_wallet"),
    # Transactions
    "list_transactions": _make_read_manifest("list_transactions"),
    "get_transaction": _make_read_manifest("get_transaction", latency="fast"),
    "create_transaction": _make_write_manifest("create_transaction"),
    "update_transaction": _make_write_manifest("update_transaction"),
    "delete_transaction": _make_destructive_manifest("delete_transaction"),
    # Reference
    "list_categories": _make_read_manifest("list_categories", latency="fast"),
    "list_tags": _make_read_manifest("list_tags", latency="fast"),
    "list_currencies": _make_read_manifest("list_currencies", latency="fast"),
    # Budgets
    "list_budgets": _make_read_manifest("list_budgets"),
    "create_budget": _make_write_manifest("create_budget"),
    "update_budget": _make_write_manifest("update_budget"),
    "delete_budget": _make_destructive_manifest("delete_budget"),
    "copy_budgets_from_last_month": _make_write_manifest("copy_budgets_from_last_month"),
    # Schedules
    "list_scheduled_transactions": _make_read_manifest("list_scheduled_transactions"),
    "get_schedule": _make_read_manifest("get_schedule", latency="fast"),
    "create_schedule": _make_write_manifest("create_schedule"),
    "update_schedule": _make_write_manifest("update_schedule"),
    "delete_schedule": _make_destructive_manifest("delete_schedule"),
    "mark_schedule_paid": _make_write_manifest("mark_schedule_paid"),
    "mark_schedule_unpaid": _make_write_manifest("mark_schedule_unpaid"),
    # Charts / Wealth
    "get_pie_chart": _make_read_manifest("get_pie_chart"),
    "list_wealth_points": _make_read_manifest("list_wealth_points"),
    # Capabilities
    "describe_kontomierz_capabilities": _make_read_manifest("describe_kontomierz_capabilities", latency="instant"),
}
