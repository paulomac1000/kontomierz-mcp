from __future__ import annotations

import pytest

from kontomierz_mcp.mock_backend import MockKontomierzClient


@pytest.mark.asyncio
async def test_mock_transaction_create_does_not_invent_client_assigned_id_deduplication() -> None:
    backend = MockKontomierzClient()
    first = await backend.create_money_transaction(client_assigned_id="same", description="first")
    second = await backend.create_money_transaction(client_assigned_id="same", description="second")

    assert first["id"] != second["id"]
    assert first["client_assigned_id"] == second["client_assigned_id"] == "same"
    assert len([item for item in backend.transactions if item.get("client_assigned_id") == "same"]) == 2
