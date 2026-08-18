from __future__ import annotations

import pytest

from kontomierz_mcp.config import Settings
from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.mock_backend import MockKontomierzClient
from kontomierz_mcp.operations import build_operations


@pytest.fixture
def operations():
    return build_operations(
        MockKontomierzClient(),
        Settings(api_key="", mock_data=True, enable_write_operations=True),
    )


@pytest.mark.asyncio
async def test_missing_required_parameter_is_invalid_parameter_not_resource_not_found(operations) -> None:
    with pytest.raises(ApplicationError) as captured:
        await operations["get_transaction"]()
    assert captured.value.code is ErrorCode.INVALID_PARAMETER
    assert captured.value.message == "Missing required parameter(s): transaction_id"


@pytest.mark.asyncio
async def test_unexpected_parameter_is_rejected_before_domain_dispatch(operations) -> None:
    with pytest.raises(ApplicationError) as captured:
        await operations["list_accounts"](surprise=True)
    assert captured.value.code is ErrorCode.INVALID_PARAMETER
    assert captured.value.message == "Unexpected parameter(s): surprise"
