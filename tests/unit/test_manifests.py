from kontomierz_mcp.manifests import TOOL_MANIFESTS


def test_catalog_is_complete_and_explicit() -> None:
    assert len(TOOL_MANIFESTS) == 27
    assert all(name == manifest.name for name, manifest in TOOL_MANIFESTS.items())


def test_financial_reads_are_not_public() -> None:
    for name in ("list_accounts", "list_transactions", "list_wealth_points"):
        assert TOOL_MANIFESTS[name].confidentiality == "financial"


def test_mutations_never_auto_retry() -> None:
    for manifest in TOOL_MANIFESTS.values():
        if manifest.side_effects in {"write", "destructive"}:
            assert manifest.automatic_retry is False
            assert manifest.requires_operator_write_gate is True


def test_idempotency_is_operation_specific() -> None:
    assert TOOL_MANIFESTS["create_transaction"].idempotent is True
    assert TOOL_MANIFESTS["create_wallet"].idempotent is False
    assert TOOL_MANIFESTS["copy_budgets_from_last_month"].idempotent is False
