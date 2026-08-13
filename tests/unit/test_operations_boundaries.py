from __future__ import annotations

import pytest

from kontomierz_mcp.config import Settings
from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.mock_backend import MockKontomierzClient
from kontomierz_mcp.operations import build_operations


@pytest.fixture
def operations():
    backend = MockKontomierzClient()
    settings = Settings(api_key="", mock_data=True, enable_write_operations=True)
    settings.validate()
    return build_operations(backend, settings), backend


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["user_account_id", "category_id", "category_group_id"])
async def test_negative_optional_ids_are_rejected(operations, field: str) -> None:
    ops, _ = operations
    with pytest.raises(ApplicationError) as captured:
        await ops["list_transactions"](**{field: -1})
    assert captured.value.code is ErrorCode.INVALID_PARAMETER


@pytest.mark.asyncio
async def test_negative_budget_category_is_rejected(operations) -> None:
    ops, _ = operations
    with pytest.raises(ApplicationError) as captured:
        await ops["create_budget"](limit="10", category_id=-1)
    assert captured.value.code is ErrorCode.INVALID_PARAMETER


@pytest.mark.asyncio
async def test_missing_required_parameter_is_invalid_parameter(operations) -> None:
    ops, _ = operations
    with pytest.raises(ApplicationError) as captured:
        await ops["create_budget"](category_id=1)
    assert captured.value.code is ErrorCode.INVALID_PARAMETER
    assert captured.value.message == "Missing required parameter(s): limit"


@pytest.mark.asyncio
async def test_internal_key_error_from_known_dispatcher_is_not_misreported_as_unknown_tool(
    operations,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ops, _ = operations

    async def broken_dispatch(_name, _arguments, _client):
        raise KeyError("domain-data")

    monkeypatch.setattr("kontomierz_mcp.operations.dispatch_primary", broken_dispatch)
    with pytest.raises(KeyError, match="domain-data"):
        await ops["list_accounts"]()


@pytest.mark.asyncio
async def test_date_range_order_is_validated(operations) -> None:
    ops, _ = operations
    with pytest.raises(ApplicationError) as captured:
        await ops["list_transactions"](start_on="2026-08-02", end_on="2026-08-01")
    assert captured.value.message == "start_on must be on or before end_on"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("list_transactions", {"start_on": "02-08-2026"}, "start_on must be YYYY-MM-DD"),
        (
            "create_schedule",
            {
                "direction": "withdrawal",
                "deadline_on": "31-12-2026",
                "holidays": 0,
                "description": "x",
                "currency_amount": "1",
                "currency_name": "PLN",
                "repeat": 1,
            },
            "deadline_on must be YYYY-MM-DD",
        ),
        ("list_budgets", {"month": "01-08-2026"}, "month must be YYYY-MM"),
    ],
)
async def test_legacy_public_date_formats_are_rejected(
    operations,
    tool: str,
    arguments: dict[str, object],
    message: str,
) -> None:
    ops, _ = operations
    with pytest.raises(ApplicationError) as captured:
        await ops[tool](**arguments)
    assert captured.value.code is ErrorCode.INVALID_PARAMETER
    assert captured.value.message == message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("list_transactions", {"q": "ą" * 129}, "q must not exceed 256 UTF-8 bytes"),
        (
            "create_transaction",
            {"client_assigned_id": "x" * 129},
            "client_assigned_id must not exceed 128 UTF-8 bytes",
        ),
        (
            "create_schedule",
            {
                "direction": "withdrawal",
                "deadline_on": "2026-12-31",
                "holidays": 0,
                "description": "x" * 513,
                "currency_amount": "1",
                "currency_name": "PLN",
                "repeat": 1,
            },
            "description must not exceed 512 UTF-8 bytes",
        ),
        (
            "create_budget",
            {"limit": "1" * 65, "category_id": 1},
            "limit must not exceed 64 UTF-8 bytes",
        ),
    ],
)
async def test_public_text_and_money_inputs_have_utf8_byte_bounds(
    operations,
    tool: str,
    arguments: dict[str, object],
    message: str,
) -> None:
    ops, _ = operations
    with pytest.raises(ApplicationError) as captured:
        await ops[tool](**arguments)
    assert captured.value.code is ErrorCode.INVALID_PARAMETER
    assert captured.value.message == message


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", ["1E+999999999", "1E+20", "0.000000001"])
async def test_money_rejects_values_that_expand_beyond_decimal_bounds(operations, amount: str) -> None:
    ops, _ = operations
    with pytest.raises(ApplicationError) as captured:
        await ops["create_budget"](limit=amount, category_id=1)
    assert captured.value.code is ErrorCode.INVALID_PARAMETER
    assert captured.value.message == "limit must have at most 20 digits and 8 decimal places"


@pytest.mark.asyncio
@pytest.mark.parametrize("balance", ["0", "-100.25"])
async def test_wallet_balance_allows_zero_and_debt(operations, balance: str) -> None:
    ops, _ = operations
    result = await ops["create_wallet"](currency_balance=balance, currency_name="pln")
    assert result["currency_balance"] == balance


@pytest.mark.asyncio
async def test_empty_text_is_an_explicit_clear_value(operations) -> None:
    ops, backend = operations
    result = await ops["update_wallet"](wallet_id=101, user_name="")
    assert result["user_name"] == ""
    assert backend.accounts[0]["user_name"] == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("holidays", "x"), ("repeat", "x")])
async def test_schedule_numeric_validation_never_leaks_value_error(operations, field: str, value: str) -> None:
    ops, _ = operations
    with pytest.raises(ApplicationError) as captured:
        await ops["update_schedule"](schedule_id=301, **{field: value})
    assert captured.value.code is ErrorCode.INVALID_PARAMETER


@pytest.mark.asyncio
async def test_pagination_is_explicitly_a_hint(operations) -> None:
    ops, _ = operations
    result = await ops["list_transactions"](per_page=2)
    assert result["may_have_more"] is True
    assert result["next_page_hint"] == 2
    assert "has_more" not in result
    assert "next_page" not in result
