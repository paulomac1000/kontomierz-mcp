"""External acceptance placeholders for a disposable real Kontomierz account.

These tests are intentionally excluded from normal CI by the ``external`` marker and
intentionally FAIL when selected. An agent with disposable-account access must replace
each placeholder with executable evidence instead of changing it to ``skip``/``xfail``.
Never run the completed mutation tests against a personal or non-disposable account.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.external


def _not_implemented(requirement: str) -> None:
    pytest.fail(f"NOT IMPLEMENTED — real-system evidence required: {requirement}")


@pytest.mark.parametrize(
    "resource",
    ("wallet", "transaction", "budget", "schedule"),
)
def test_real_mutation_round_trip_contract(resource: str) -> None:
    _not_implemented(
        f"{resource}: create/update/delete using a disposable record; record HTTP method, path, media type, "
        "request-body encoding, success status, response wrapper/type, stable ID flow, and cleanup"
    )


def test_real_schedule_state_transition_contract() -> None:
    _not_implemented(
        "schedule paid/unpaid transitions: verify request contract, resulting state, repeated-call behavior, "
        "and cleanup"
    )


def test_real_copy_budgets_contract_and_duplicate_behavior() -> None:
    _not_implemented(
        "copy-budgets mutation: verify method/body/response and behavior when the target month already contains budgets"
    )


def test_real_pagination_has_stable_order_and_terminating_condition() -> None:
    _not_implemented(
        "transactions/schedules pagination: prove stable ordering, final-page termination, "
        "and no false continuation claim"
    )


def test_real_client_assigned_id_reconciliation() -> None:
    _not_implemented(
        "transaction client_assigned_id: prove uniqueness scope, retention/replay semantics, "
        "lookup/reconciliation path, "
        "and behavior after an ambiguous response"
    )


def test_real_post_send_timeout_reconciliation() -> None:
    _not_implemented(
        "inject or proxy a timeout after the request may have reached Kontomierz; "
        "reconcile exact resource state before "
        "any retry and prove the server never reports false success or safe retry"
    )


def test_real_rate_limit_and_retry_after_contract() -> None:
    _not_implemented(
        "controlled 429/rate-limit evidence: verify Retry-After parsing, status preservation, "
        "and bounded read-only retry guidance"
    )


def test_real_money_precision_and_rounding_contract() -> None:
    _not_implemented(
        "verify accepted Decimal precision/scale and rounding/rejection behavior for wallet, transaction, "
        "and budget values"
    )


def test_real_readiness_probe_authentication_failure_and_recovery() -> None:
    _not_implemented(
        "with disposable credentials, prove readiness becomes unavailable on invalid/revoked credentials and recovers "
        "after valid credentials are restored without leaking protected upstream details"
    )
