from __future__ import annotations

import pytest

from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.operations import build_operations


def test_dates_are_public_iso_and_converted_for_upstream(write_settings, mock_client) -> None:
    operations = build_operations(mock_client, write_settings)
    created = operations["create_transaction"](
        client_assigned_id="iso-date",
        currency_amount="10.00",
        currency_name="pln",
        transaction_on="2026-08-06",
    )
    assert created["transaction_on"] == "06-08-2026"
    assert created["currency_name"] == "PLN"


def test_budget_requires_exactly_one_target(write_settings, mock_client) -> None:
    operations = build_operations(mock_client, write_settings)
    with pytest.raises(ApplicationError) as raised:
        operations["create_budget"]("100")
    assert raised.value.code == ErrorCode.INVALID_PARAMETER
    with pytest.raises(ApplicationError):
        operations["create_budget"]("100", category_id=1, category_group_id=2)


def test_nonempty_page_does_not_always_claim_more(readonly_settings, mock_client) -> None:
    operations = build_operations(mock_client, readonly_settings)
    result = operations["list_transactions"](page=1, per_page=100)
    assert result["items_in_page"] == 2
    assert result["has_more"] is False
    assert result["next_page"] is None


def test_full_page_can_expose_bounded_continuation(readonly_settings, mock_client) -> None:
    operations = build_operations(mock_client, readonly_settings)
    result = operations["list_transactions"](page=1, per_page=1)
    assert result["has_more"] is True
    assert result["next_page"] == 2


def test_updates_require_a_field(write_settings, mock_client) -> None:
    operations = build_operations(mock_client, write_settings)
    with pytest.raises(ApplicationError, match="at least one field"):
        operations["update_transaction"](1001)


def test_decimal_rejects_nan_and_negative(write_settings, mock_client) -> None:
    operations = build_operations(mock_client, write_settings)
    for value in ("NaN", "-1", "0"):
        with pytest.raises(ApplicationError):
            operations["create_budget"](value, category_id=1)


def test_domain_validation_rejects_malformed_identifiers_dates_and_enums(write_settings, mock_client) -> None:
    operations = build_operations(mock_client, write_settings)
    invalid_calls = [
        lambda: operations["get_transaction"](True),
        lambda: operations["list_transactions"](page=0),
        lambda: operations["list_transactions"](per_page=101),
        lambda: operations["list_transactions"](direction="out"),
        lambda: operations["create_wallet"]("1", "PL"),
        lambda: operations["create_transaction"]("", transaction_on="not-a-date"),
        lambda: operations["list_budgets"]("2026/08"),
        lambda: operations["list_scheduled_transactions"](schedule_group_name="future"),
        lambda: operations["create_schedule"]("withdrawal", "2026-09-01", 3, "x", "1", "PLN", 1),
        lambda: operations["create_schedule"]("withdrawal", "2026-09-01", 0, "x", "1", "PLN", 10),
        lambda: operations["get_pie_chart"](chart_kind="bar"),
    ]
    for call in invalid_calls:
        with pytest.raises(ApplicationError):
            call()


def test_partial_updates_validate_each_supplied_domain_value(write_settings, mock_client) -> None:
    operations = build_operations(mock_client, write_settings)
    updated = operations["update_transaction"](
        1001,
        currency_amount="12.50",
        currency_name="eur",
        direction="deposit",
        transaction_on="2026-08-05",
    )
    assert updated["currency_amount"] == "12.50"
    assert updated["currency_name"] == "EUR"
    assert updated["transaction_on"] == "05-08-2026"

    schedule = operations["update_schedule"](
        301,
        direction="deposit",
        deadline_on="2026-09-02",
        holidays=1,
        currency_amount="2.50",
        currency_name="eur",
        repeat=3,
    )
    assert schedule["holidays"] == "1"
    assert schedule["repeat"] == "3"

    for fields in ({"holidays": 3}, {"repeat": 10}):
        with pytest.raises(ApplicationError):
            operations["update_schedule"](301, **fields)
