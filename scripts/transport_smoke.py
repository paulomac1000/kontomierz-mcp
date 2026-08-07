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

from kontomierz_mcp.manifests import TOOL_DEFINITIONS

_HTTP_TOKEN = "transport-smoke-auth-token-0000000000000000"
_HTTP_PRINCIPAL = "ci:transport-smoke"


def _free_port() -> int:
    with closing(socket.socket()) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _input_schema(tool) -> dict[str, object]:
    schema = getattr(tool, "inputSchema", None)
    if schema is None:
        schema = tool.input_schema
    return schema


async def _assert_contract(client) -> None:
    listing = await client.list_tools()
    discovered = {tool.name: tool for tool in listing.tools}
    assert set(discovered) == set(TOOL_DEFINITIONS)
    for name, definition in TOOL_DEFINITIONS.items():
        tool = discovered[name]
        assert tool.description == definition.description
        schema = _input_schema(tool)
        assert set(schema.get("properties", {})) == {parameter.name for parameter in definition.parameters}
        assert tuple(schema.get("required", ())) == definition.required_parameters
        for parameter in definition.parameters:
            assert schema["properties"][parameter.name]["description"] == parameter.description

    capabilities = await client.call_tool("describe_kontomierz_capabilities", {})
    assert capabilities.is_error is False
    document = capabilities.structured_content["data"]
    assert document["schema_version"] == "3.0.0"
    assert set(document["tools"]) == set(TOOL_DEFINITIONS)
    assert document["tools"]["create_wallet"]["manifest"]["active_state"] == "disabled"

    result = await client.call_tool("list_accounts", {})
    assert result.is_error is False
    denied = await client.call_tool(
        "create_wallet",
        {"currency_balance": "1.00", "currency_name": "PLN"},
    )
    assert denied.is_error is True
    assert denied.structured_content["error"]["code"] == "AUTHORIZATION_FAILED"


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
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    port = _free_port()
    environment = {
        **os.environ,
        "KONTOMIERZ_MOCK_DATA": "1",
        "ENABLE_WRITE_OPERATIONS": "0",
        "MCP_TRANSPORT": "streamable-http",
        "MCP_HOST": "127.0.0.1",
        "MCP_PORT": str(port),
        "MCP_HTTP_AUTH_TOKEN": _HTTP_TOKEN,
        "MCP_HTTP_PRINCIPAL": _HTTP_PRINCIPAL,
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

        http_client = httpx2.AsyncClient(headers={"Authorization": f"Bearer {_HTTP_TOKEN}"})
        async with http_client:
            transport = streamable_http_client(
                f"http://127.0.0.1:{port}/mcp",
                http_client=http_client,
            )
            async with Client(transport) as client:
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
