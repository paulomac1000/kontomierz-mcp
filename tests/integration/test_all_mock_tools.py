from __future__ import annotations

import pytest

from kontomierz_mcp.config import Settings
from kontomierz_mcp.manifests import TOOL_MANIFESTS
from kontomierz_mcp.mock_backend import MockKontomierzClient
from kontomierz_mcp.mock_samples import SMOKE_SAMPLES
from kontomierz_mcp.server import build_kernel


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", sorted(TOOL_MANIFESTS))
async def test_every_tool_through_one_kernel(tool_name: str, write_settings: Settings) -> None:
    kernel = build_kernel(write_settings, MockKontomierzClient())
    result = await kernel.invoke(tool_name, SMOKE_SAMPLES[tool_name])
    assert "data" in result
    assert result["_meta"]["tool_name"] == tool_name
    await kernel.close()
