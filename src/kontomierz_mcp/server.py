"""MCP server entry point — FastMCP + health endpoint + REST bridge.

Three-port architecture (L2+): health(9100), SSE(9101), REST API(9102).
"""

import json
import logging
import sys
import time
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .client import KontomierzClient
from .response import (
    RequestIdFilter,
    SanitizingFormatter,
    get_invocation_counts,
    start_tool_context,
)
from .tools.accounts import register_accounts_tools
from .tools.budgets import register_budgets_tools
from .tools.charts_wealth import register_charts_wealth_tools
from .tools.constants import (
    HEALTH_PORT,
    KNOWN_RISK_PREFIXES,
    KONTOMIERZ_API_KEY,
    KONTOMIERZ_PASSWORD,
    KONTOMIERZ_USERNAME,
    LOG_LEVEL,
    MCP_PORT,
    REST_API_PORT,
    TOOL_MANIFESTS,
    TOOLS_VERSION,
)
from .tools.reference import register_reference_tools
from .tools.schedules import register_schedules_tools
from .tools.transactions import register_transactions_tools


def _setup_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(SanitizingFormatter("%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s"))
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)


_setup_logging()
_logger = logging.getLogger(__name__)

mcp = FastMCP("kontomierz-mcp")

_TOOL_REGISTRY: dict = {}
_CLIENT: KontomierzClient | None = None


def _get_or_create_client() -> KontomierzClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = KontomierzClient(
            api_key=KONTOMIERZ_API_KEY,
            username=KONTOMIERZ_USERNAME,
            password=KONTOMIERZ_PASSWORD,
        )
        if KONTOMIERZ_API_KEY:
            try:
                accounts = _CLIENT.get_user_accounts()
                if accounts is not None:
                    _logger.info("Kontomierz client connection validated (%d accounts)", len(accounts))
                else:
                    _logger.warning("Kontomierz client created but could not validate connection — API may be unreachable.")
            except Exception as exc:
                _logger.warning("Kontomierz client created but connection validation failed: %s", exc)
        else:
            _logger.warning("KONTOMIERZ_API_KEY not set — client will not authenticate.")
    return _CLIENT


def _resolve_bind_host() -> str:
    """Determine the bind host based on MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED."""
    import os as _os

    unsafe = _os.getenv("MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED", "").strip() == "1"
    if unsafe:
        _logger.critical(
            "UNSAFE: Binding to 0.0.0.0 — tools exposed to all network interfaces. "
            "MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED=1 acknowledged."
        )
        return "0.0.0.0"
    return "127.0.0.1"


@asynccontextmanager
async def lifespan(server: FastMCP):
    client = _get_or_create_client()
    server._lifespan_data = {"client": client}
    _logger.info("Kontomierz client initialized")
    try:
        yield server._lifespan_data
    finally:
        _logger.info("Shutting down")


mcp.lifespan = lifespan

register_accounts_tools(mcp)
register_transactions_tools(mcp)
register_budgets_tools(mcp)
register_schedules_tools(mcp)
register_reference_tools(mcp)
register_charts_wealth_tools(mcp)


def _populate_tool_registry() -> None:
    for loc_attr in ("_mcp_server", "_tool_manager", "_tools"):
        loc = getattr(mcp, loc_attr, None)
        if loc is None:
            continue
        for tools_attr in ("_tools", "_tool_cache"):
            tools = getattr(loc, tools_attr, None)
            if isinstance(tools, dict) and tools:
                _TOOL_REGISTRY.update(tools)
                return
    if hasattr(mcp, "_tools") and isinstance(mcp._tools, dict) and mcp._tools:
        _TOOL_REGISTRY.update(mcp._tools)
        return
    for name in sorted(TOOL_MANIFESTS.keys()):
        _TOOL_REGISTRY[name] = name
    _logger.info("Tool registry populated from manifests (%d tools)", len(_TOOL_REGISTRY))


def _inject_risk_prefixes() -> None:
    for name, fn in _TOOL_REGISTRY.items():
        if not callable(fn):
            continue
        manifest = TOOL_MANIFESTS.get(name, {})
        risk = manifest.get("risk", "READ")
        raw_fn = fn
        for attr in ("fn", "func", "_func", "function"):
            if hasattr(fn, attr):
                inner = getattr(fn, attr)
                if callable(inner):
                    raw_fn = inner
                    break
        doc = (raw_fn.__doc__ or "").strip()
        for prefix in KNOWN_RISK_PREFIXES:
            if doc.startswith(prefix):
                doc = doc[len(prefix) :].lstrip()
                break
        raw_fn.__doc__ = f"[{risk}] {doc}"
        if hasattr(fn, "description"):
            fn.description = raw_fn.__doc__.split("\n")[0].rstrip(".")


def _build_health_payload() -> dict:
    return {
        "status": "healthy",
        "tool_count": len(_TOOL_REGISTRY),
        "tools_version": TOOLS_VERSION,
        "invocation_counts": get_invocation_counts(),
    }


def _start_health_server() -> None:
    import socket
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            body = json.dumps(_build_health_payload())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode())

    class ReuseHTTPServer(HTTPServer):
        allow_reuse_address = True

        def server_bind(self):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            HTTPServer.server_bind(self)

    bind_host = _resolve_bind_host()
    server = ReuseHTTPServer((bind_host, HEALTH_PORT), HealthHandler)
    _logger.info("Health server on http://%s:%d/health", bind_host, HEALTH_PORT)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def _start_rest_bridge() -> None:
    import asyncio
    import threading

    try:
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
    except ImportError:
        _logger.warning("Starlette not installed")
        return

    async def health(_r):
        return JSONResponse(_build_health_payload())

    async def list_tools(_r):
        tools = sorted(_TOOL_REGISTRY.keys())
        t = len(tools)
        return JSONResponse({"total": t, "tool_count": t, "tools": tools})

    async def call_tool(request):
        tool_name = request.path_params["name"]
        body = await request.json()
        params = body.get("params", {})

        client = _get_or_create_client()
        if getattr(mcp, "_lifespan_data", None) is None:
            mcp._lifespan_data = {"client": client}

        start_tool_context()
        t0 = time.monotonic()

        try:
            result = await mcp.call_tool(tool_name, params)
        except (AttributeError, TypeError):
            fn = _TOOL_REGISTRY.get(tool_name)
            if fn is None or not callable(fn):
                return JSONResponse(
                    {
                        "success": False,
                        "error": {"code": "UNKNOWN_TOOL", "message": f"Unknown tool: {tool_name}", "retryable": False},
                    },
                    status_code=404,
                )
            try:
                result_str = await fn(**params) if asyncio.iscoroutinefunction(fn) else fn(**params)
                elapsed = int((time.monotonic() - t0) * 1000)
                data = json.loads(result_str)
                data.setdefault("_meta", {})["duration_ms"] = elapsed
                return JSONResponse(data)
            except Exception as exc:
                return JSONResponse(
                    {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(exc), "retryable": False}},
                    status_code=500,
                )
        except Exception as exc:
            _logger.error("call_tool error: %s", exc)
            return JSONResponse(
                {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(exc), "retryable": False}}, status_code=500
            )

        elapsed = int((time.monotonic() - t0) * 1000)
        try:
            for block in result.content:
                if hasattr(block, "text"):
                    data = json.loads(block.text)
                    data.setdefault("_meta", {})["duration_ms"] = elapsed
                    return JSONResponse(data)
        except Exception:
            pass
        return JSONResponse({"success": True, "data": str(result), "_meta": {"duration_ms": elapsed}})

    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/api/health", health, methods=["GET"]),
            Route("/api/tools", list_tools, methods=["GET"]),
            Route("/api/tools/{name}", call_tool, methods=["POST"]),
        ]
    )

    import uvicorn

    def _run():
        uvicorn.run(app, host=_resolve_bind_host(), port=REST_API_PORT, log_level="warning")

    _logger.info("REST bridge on http://%s:%d", _resolve_bind_host(), REST_API_PORT)
    threading.Thread(target=_run, daemon=True).start()


def main() -> None:
    _populate_tool_registry()
    _inject_risk_prefixes()
    _get_or_create_client()  # pre-initialize for REST bridge
    _start_health_server()
    _start_rest_bridge()
    bind_host = _resolve_bind_host()
    _logger.info("Starting Kontomierz MCP server (SSE on %s:%d, %d tools)", bind_host, MCP_PORT, len(_TOOL_REGISTRY))
    mcp.run(transport="sse", host=bind_host, port=MCP_PORT)


if __name__ == "__main__":
    main()
