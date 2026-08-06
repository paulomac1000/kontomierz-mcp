"""Smoke an installed kontomierz-mcp executable through official MCP transports."""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import subprocess
import time
from contextlib import closing
from pathlib import Path
from urllib.request import urlopen


def _free_port() -> int:
    with closing(socket.socket()) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


async def _assert_contract(client) -> None:
    listing = await client.list_tools()
    names = {tool.name for tool in listing.tools}
    assert len(names) == 27
    assert "list_accounts" in names
    result = await client.call_tool("list_accounts", {})
    assert result.is_error is False
    denied = await client.call_tool(
        "create_wallet",
        {"currency_balance": "1.00", "currency_name": "PLN"},
    )
    assert denied.is_error is True


async def smoke_stdio(executable: Path) -> None:
    from mcp import Client, StdioServerParameters
    from mcp.client.stdio import stdio_client

    parameters = StdioServerParameters(
        command=str(executable),
        args=[],
        env={
            **os.environ,
            "KONTOMIERZ_MOCK_DATA": "1",
            "ENABLE_WRITE_OPERATIONS": "0",
            "MCP_TRANSPORT": "stdio",
        },
    )
    async with Client(stdio_client(parameters)) as client:
        await _assert_contract(client)


async def smoke_http(executable: Path) -> None:
    from mcp import Client

    port = _free_port()
    environment = {
        **os.environ,
        "KONTOMIERZ_MOCK_DATA": "1",
        "ENABLE_WRITE_OPERATIONS": "0",
        "MCP_TRANSPORT": "streamable-http",
        "MCP_HOST": "127.0.0.1",
        "MCP_PORT": str(port),
    }
    process = subprocess.Popen(
        [str(executable)],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 15
        ready_url = f"http://127.0.0.1:{port}/health/ready"
        while time.monotonic() < deadline:
            if process.poll() is not None:
                diagnostics = process.stderr.read() if process.stderr else ""
                raise RuntimeError(f"HTTP server exited early: {diagnostics}")
            try:
                with urlopen(ready_url, timeout=1) as response:  # noqa: S310 - fixed loopback URL
                    if response.status == 200:
                        break
            except OSError:
                await asyncio.sleep(0.1)
        else:
            raise TimeoutError("HTTP server did not become ready")

        async with Client(f"http://127.0.0.1:{port}/mcp") as client:
            await _assert_contract(client)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("transport", choices=("stdio", "streamable-http"))
    parser.add_argument("--executable", type=Path, required=True)
    args = parser.parse_args()
    if args.transport == "stdio":
        await smoke_stdio(args.executable)
    else:
        await smoke_http(args.executable)
    print(f"{args.transport} official-client smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
