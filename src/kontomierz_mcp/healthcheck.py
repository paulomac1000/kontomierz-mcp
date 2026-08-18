"""Container healthcheck entry point with no protected output."""

from __future__ import annotations

import os
from urllib.request import Request, urlopen

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _http_ready() -> bool:
    host = os.environ.get("MCP_HOST", "127.0.0.1").strip()
    if host not in _LOOPBACK_HOSTS:
        return False
    try:
        port = int(os.environ.get("MCP_PORT", "9101"))
    except ValueError:
        return False
    if not 1 <= port <= 65535:
        return False
    token = os.environ.get("MCP_HTTP_AUTH_TOKEN", "")
    if not token:
        return False
    host_literal = f"[{host}]" if ":" in host else host
    request = Request(
        f"http://{host_literal}:{port}/health/ready",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        # Host is restricted to the closed loopback allowlist above.
        with urlopen(request, timeout=2) as response:  # noqa: S310  # nosec B310
            status = getattr(response, "status", None)
            return isinstance(status, int) and status == 200
    except (OSError, ValueError):
        return False


def main() -> int:
    """Return a Docker-compatible health status for the configured transport."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "stdio":
        # Docker already treats a dead PID 1 as a stopped container. Stdio has no
        # independent in-band readiness endpoint, so process liveness is sufficient.
        return 0
    if transport in {"http", "streamable-http"}:
        return 0 if _http_ready() else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
