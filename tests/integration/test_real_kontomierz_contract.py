"""Placeholders for contract tests requiring a disposable real Kontomierz account."""

import pytest


@pytest.mark.external
@pytest.mark.skip(reason="TODO(real-system-agent): verify JSON vs form body and all documented HTTP verbs against a disposable account")
def test_real_write_contract() -> None:
    pass


@pytest.mark.external
@pytest.mark.skip(reason="TODO(real-system-agent): reconcile ambiguous write timeout using client_assigned_id and resource reads")
def test_real_ambiguous_write_reconciliation() -> None:
    pass
