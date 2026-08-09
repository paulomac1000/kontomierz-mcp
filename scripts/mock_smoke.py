from __future__ import annotations

import asyncio

from kontomierz_mcp.config import Settings
from kontomierz_mcp.mock_backend import MockKontomierzClient
from kontomierz_mcp.mock_samples import SMOKE_SAMPLES
from kontomierz_mcp.server import build_kernel

_MOCK_DESTRUCTIVE_CAPABILITIES = (
    "destroy_wallet",
    "delete_transaction",
    "delete_budget",
    "delete_schedule",
)
_MOCK_DESTRUCTIVE_RESOURCES = (
    "wallet:102",
    "transaction:1002",
    "budget:201",
    "schedule:301",
)


async def main() -> None:
    settings = Settings(
        api_key="",
        mock_data=True,
        enable_write_operations=True,
        stdio_allowed_destructive_capabilities=_MOCK_DESTRUCTIVE_CAPABILITIES,
        stdio_allowed_destructive_resources=_MOCK_DESTRUCTIVE_RESOURCES,
    )
    settings.validate()
    for name, arguments in SMOKE_SAMPLES.items():
        kernel = build_kernel(settings, MockKontomierzClient())
        await kernel.invoke(name, arguments)
        await kernel.close()
    print(f"mock smoke passed: {len(SMOKE_SAMPLES)} tools")


if __name__ == "__main__":
    asyncio.run(main())
