"""Emit an observed MCP public-contract document through the official stdio client."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

_GENERIC_ERROR_CODES = {
    "AMBIGUOUS_OUTCOME",
    "AUTHENTICATION_FAILED",
    "AUTHORIZATION_FAILED",
    "CANCELLED",
    "DEPENDENCY_UNAVAILABLE",
    "INTERNAL_ERROR",
    "INVALID_PARAMETER",
    "RATE_LIMITED",
    "RESOURCE_NOT_FOUND",
    "TIMEOUT",
    "UPSTREAM_FAILURE",
}


def _schema(tool: Any, snake_name: str, wire_name: str) -> dict[str, Any]:
    value = getattr(tool, snake_name, None)
    if value is None:
        value = getattr(tool, wire_name, None)
    return dict(value) if isinstance(value, dict) else {}


def _pagination(input_schema: dict[str, Any]) -> str:
    properties = input_schema.get("properties", {})
    if isinstance(properties, dict) and {"page", "per_page"} <= properties.keys():
        return "page/per_page; conservative may_have_more and next_page_hint continuation"
    return "none"


def _retry_semantics(manifest: dict[str, Any]) -> str:
    retry = manifest.get("retry_conditions", {})
    if not isinstance(retry, dict):
        retry = {}
    eligible = retry.get("eligible_error_codes", [])
    if not isinstance(eligible, list):
        eligible = []
    codes = ",".join(sorted(str(item) for item in eligible)) or "none"
    return (
        f"automatic={bool(manifest.get('automatic_retry', False))};"
        f"caller_retryable={bool(manifest.get('retryable', False))};"
        f"attempt_limit={int(retry.get('attempt_limit', 0))};eligible={codes}"
    )


def _target_selection(manifest: dict[str, Any]) -> str:
    binding = manifest.get("target_binding", {})
    identity = binding.get("identity", "configured-target") if isinstance(binding, dict) else "configured-target"
    scope = manifest.get("target_scope", "kontomierz-account")
    return f"server-configured {scope}; identity={identity}; caller target substitution forbidden"


def _error_contract(manifest: dict[str, Any]) -> list[str]:
    retry = manifest.get("retry_conditions", {})
    eligible = retry.get("eligible_error_codes", []) if isinstance(retry, dict) else []
    extra = {str(item) for item in eligible} if isinstance(eligible, list) else set()
    return sorted(_GENERIC_ERROR_CODES | extra)


async def _capture(args: argparse.Namespace) -> dict[str, Any]:
    from mcp import Client, StdioServerParameters
    from mcp.client.stdio import stdio_client

    parameters = StdioServerParameters(
        command=str(args.executable),
        args=[],
        env={
            **os.environ,
            "KONTOMIERZ_MOCK_DATA": "1",
            "ENABLE_WRITE_OPERATIONS": "0",
            "MCP_TRANSPORT": "stdio",
        },
    )
    async with Client(stdio_client(parameters)) as client:
        listing = await client.list_tools()
        discovered = {tool.name: tool for tool in listing.tools}
        capability_result = await client.call_tool("describe_kontomierz_capabilities", {})
        if capability_result.is_error:
            raise RuntimeError("capability discovery failed during public-contract probe")
        structured = capability_result.structured_content
        if not isinstance(structured, dict) or not isinstance(structured.get("data"), dict):
            raise RuntimeError("capability discovery returned an invalid structured document")
        capabilities = structured["data"]
        contracts = capabilities.get("tools")
        if not isinstance(contracts, dict) or set(contracts) != set(discovered):
            raise RuntimeError("official tool listing and governed capability catalog disagree")

        tools: list[dict[str, Any]] = []
        for name in sorted(discovered):
            public_tool = discovered[name]
            contract = contracts[name]
            if not isinstance(contract, dict) or not isinstance(contract.get("manifest"), dict):
                raise RuntimeError(f"governed manifest is missing for {name}")
            manifest = contract["manifest"]
            input_schema = _schema(public_tool, "input_schema", "inputSchema")
            tools.append(
                {
                    "name": name,
                    "version": str(contract["version"]),
                    "input_schema": input_schema,
                    "output_schema": _schema(public_tool, "output_schema", "outputSchema"),
                    "error_contract": _error_contract(manifest),
                    "pagination": _pagination(input_schema),
                    "retry_semantics": _retry_semantics(manifest),
                    "target_selection": _target_selection(manifest),
                }
            )

        supported = capabilities.get("supported_transports")
        if not isinstance(supported, list):
            raise RuntimeError("capability discovery did not expose supported transports")
        transports = ["streamable_http" if item == "streamable-http" else str(item) for item in supported]
        return {
            "format": "ai-skills-mcp-public-contract",
            "schema_version": 1,
            "source_revision": args.source_revision,
            "artifact": {
                "kind": "wheel",
                "identity": args.artifact_identity,
                "digest": args.artifact_digest,
            },
            "server": {"name": "kontomierz-mcp", "version": str(capabilities["server_version"])},
            "sdk": {"profile": "python-official-mcp", "version": str(capabilities["sdk_version"])},
            "transports": transports,
            "authentication": {
                "required": True,
                "mechanism": "stdio=local-process-principal;streamable_http=bearer",
                "target_selection": "server-configured Kontomierz account; caller target selection is forbidden",
            },
            "tools": tools,
        }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--artifact-identity", required=True)
    parser.add_argument("--artifact-digest", required=True)
    args = parser.parse_args()
    if not args.executable.is_file():
        parser.error("--executable must identify the installed MCP server executable")
    if len(args.source_revision) != 40 or any(
        character not in "0123456789abcdef" for character in args.source_revision
    ):
        parser.error("--source-revision must be a lowercase 40-character Git SHA")
    digest = args.artifact_digest.removeprefix("sha256:")
    if (
        not args.artifact_digest.startswith("sha256:")
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        parser.error("--artifact-digest must be sha256:<64 lowercase hex>")
    print(json.dumps(await _capture(args), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    asyncio.run(main())
