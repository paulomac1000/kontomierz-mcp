from __future__ import annotations

import pytest

from kontomierz_mcp.config import Settings
from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.mock_backend import MockKontomierzClient
from kontomierz_mcp.operation_support import boolean
from kontomierz_mcp.operations import build_operations


def test_boolean_rejects_non_boolean_values() -> None:
    for value in ("false", "true", 0, 1, None, []):
        with pytest.raises(ApplicationError) as captured:
            boolean(value, "show_hidden_transactions")
        assert captured.value.code is ErrorCode.INVALID_PARAMETER
        assert captured.value.message == "show_hidden_transactions must be a boolean"


@pytest.mark.asyncio
async def test_direct_operation_rejects_truthy_string_for_boolean_parameter() -> None:
    settings = Settings(api_key="", mock_data=True)
    operations = build_operations(MockKontomierzClient(), settings)

    with pytest.raises(ApplicationError) as captured:
        await operations["list_transactions"](show_hidden_transactions="false")

    assert captured.value.code is ErrorCode.INVALID_PARAMETER
    assert captured.value.message == "show_hidden_transactions must be a boolean"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("currency_amount", 0, "currency_amount must be a string"),
        ("currency_name", False, "currency_name must be a string"),
        ("transaction_on", None, "transaction_on must be a string"),
    ],
)
async def test_create_transaction_does_not_silently_omit_invalid_falsey_optionals(
    field: str,
    value: object,
    message: str,
) -> None:
    settings = Settings(api_key="", mock_data=True)
    operations = build_operations(MockKontomierzClient(), settings)

    with pytest.raises(ApplicationError) as captured:
        await operations["create_transaction"](client_assigned_id="strictness-test", **{field: value})

    assert captured.value.code is ErrorCode.INVALID_PARAMETER
    assert captured.value.message == message


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["user_account_id", "category_id", "category_group_id"])
async def test_explicit_zero_optional_ids_are_rejected(field: str) -> None:
    settings = Settings(api_key="", mock_data=True)
    operations = build_operations(MockKontomierzClient(), settings)

    with pytest.raises(ApplicationError) as captured:
        await operations["list_transactions"](**{field: 0})

    assert captured.value.code is ErrorCode.INVALID_PARAMETER
    assert captured.value.message == f"{field} must be a positive integer"
