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


def test_mock_schedule_listing_honors_explicit_date_bounds() -> None:
    backend = MockKontomierzClient()

    inside = backend.get_scheduled_transactions(
        schedule_group_name="unpaid", start_on="2026-09-01", end_on="2026-09-30"
    )
    before = backend.get_scheduled_transactions(
        schedule_group_name="unpaid", start_on="2026-01-01", end_on="2026-08-31"
    )
    after = backend.get_scheduled_transactions(schedule_group_name="unpaid", start_on="2026-10-01", end_on="2027-12-31")

    assert [row["schedule_id"] for row in inside] == [301]
    assert before == []
    assert after == []


def test_schedule_tooling_documents_window_and_reconcile_contract() -> None:
    from kontomierz_mcp.manifests import TOOL_DEFINITIONS

    listing_notes = TOOL_DEFINITIONS["list_scheduled_transactions"].usage_notes
    create_notes = TOOL_DEFINITIONS["create_schedule"].usage_notes

    assert "current scheduling window" in listing_notes
    assert "start_on/end_on" in create_notes
    assert "deadline_on" in create_notes
    assert "stay invisible" in create_notes


@pytest.mark.asyncio
async def test_schedule_listing_marks_default_and_explicit_window() -> None:
    from kontomierz_mcp.config import Settings
    from kontomierz_mcp.operations import build_operations

    settings = Settings(api_key="", mock_data=True, enable_write_operations=True)
    settings.validate()
    ops = build_operations(MockKontomierzClient(), settings)

    default = await ops["list_scheduled_transactions"](schedule_group_name="unpaid")
    explicit = await ops["list_scheduled_transactions"](
        schedule_group_name="unpaid", start_on="2026-08-01", end_on="2026-12-31"
    )

    assert default["window"] == "default"
    assert explicit["window"] == "explicit"
