from __future__ import annotations

import httpx
import pytest

from kontomierz_mcp.client import KontomierzClient
from kontomierz_mcp.errors import ErrorCode, UpstreamError


@pytest.mark.asyncio
async def test_wealth_point_wrapper_must_contain_an_object() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=[{"wealth_point": []}]))
    http_client = httpx.AsyncClient(transport=transport)
    client = KontomierzClient(
        api_key="secret",
        base_url="https://example.test/k4",
        timeout_seconds=1,
        client=http_client,
    )
    try:
        with pytest.raises(UpstreamError) as captured:
            await client.get_wealth_points()
        assert captured.value.code is ErrorCode.UPSTREAM_FAILURE
        assert captured.value.write_outcome_ambiguous is False
    finally:
        await http_client.aclose()
