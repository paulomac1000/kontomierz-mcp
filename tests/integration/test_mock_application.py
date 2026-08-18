from __future__ import annotations

import pytest

from kontomierz_mcp.manifests import TOOL_MANIFESTS


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_workflow_uses_stable_ids(readonly_kernel) -> None:
    listing = await readonly_kernel.invoke("list_transactions", {"page": 1, "per_page": 10})
    transaction_id = listing["data"]["items"][0]["id"]
    detail = await readonly_kernel.invoke("get_transaction", {"transaction_id": transaction_id})
    assert detail["data"]["id"] == transaction_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_write_plan_execute_verify(write_kernel) -> None:
    created = await write_kernel.invoke(
        "create_transaction",
        {
            "client_assigned_id": "workflow-1",
            "currency_amount": "25.50",
            "currency_name": "PLN",
            "direction": "withdrawal",
            "name": "Mock workflow",
            "transaction_on": "2026-08-06",
        },
    )
    identifier = created["data"]["id"]
    verified = await write_kernel.invoke("get_transaction", {"transaction_id": identifier})
    assert verified["data"]["client_assigned_id"] == "workflow-1"
    deleted = await write_kernel.invoke("delete_transaction", {"transaction_id": identifier})
    assert deleted["data"]["deleted"] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_capability_discovery_matches_kernel_catalog(readonly_kernel) -> None:
    result = await readonly_kernel.invoke("describe_kontomierz_capabilities", {"verbose": True})
    assert set(result["data"]["tools"]) == set(TOOL_MANIFESTS)
    assert result["data"]["supported_transports"] == ["stdio", "streamable-http"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_capability_discovery_defaults_to_compact_tool_summaries(readonly_kernel) -> None:
    import json

    result = await readonly_kernel.invoke("describe_kontomierz_capabilities", {})
    data = result["data"]

    assert data["detail"] == "compact"
    assert data["verbose"] is False
    assert set(data["tools"]) == set(TOOL_MANIFESTS)
    summary = data["tools"]["create_wallet"]
    assert summary["active_state"] in {"active", "disabled"}
    assert "manifest" not in summary
    assert "claim_evidence" not in json.dumps(data)
    assert len(json.dumps(data, ensure_ascii=False)) < 20_000
    assert all(isinstance(tool, str) for tool in data["active_tools"])
