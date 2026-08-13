from __future__ import annotations

import pytest

from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.mock_backend import MockKontomierzClient


def test_mock_transaction_create_does_not_invent_client_assigned_id_deduplication() -> None:
    backend = MockKontomierzClient()
    first = backend.create_money_transaction(client_assigned_id="same", description="first")
    second = backend.create_money_transaction(client_assigned_id="same", description="second")

    assert first["id"] != second["id"]
    assert first["client_assigned_id"] == second["client_assigned_id"] == "same"
    assert len([item for item in backend.transactions if item.get("client_assigned_id") == "same"]) == 2


@pytest.mark.parametrize("field", ["page", "per_page"])
@pytest.mark.parametrize("value", [0.0, 1.0, 1.5])
def test_mock_schedule_pagination_rejects_floats(field: str, value: float) -> None:
    backend = MockKontomierzClient()

    with pytest.raises(ApplicationError) as captured:
        backend.get_scheduled_transactions(**{field: value})

    assert captured.value.code is ErrorCode.INVALID_PARAMETER
    assert captured.value.message == f"{field} must be a positive integer"
