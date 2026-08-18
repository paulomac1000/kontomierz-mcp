from __future__ import annotations

from typing import Any

from starlette.testclient import TestClient

from kontomierz_mcp.config import Settings
from kontomierz_mcp.server import create_http_app

TOKEN = "b" * 32


class SpyKernel:
    def __init__(self) -> None:
        self.invoke_calls = 0
        self.readiness_calls = 0
        self.closed = False

    async def invoke(self, name: str, arguments: dict[str, Any], *, context: Any = None) -> dict[str, Any]:
        del name, arguments, context
        self.invoke_calls += 1
        return {"data": {}, "_meta": {}}

    async def readiness(self) -> bool:
        self.readiness_calls += 1
        return True

    async def close(self) -> None:
        self.closed = True


def settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "api_key": "",
        "mock_data": True,
        "transport": "streamable-http",
        "host": "127.0.0.1",
        "port": 9101,
        "http_auth_token": TOKEN,
        "http_principal": "operator:http-security-test",
        "http_max_request_body_bytes": 256,
    }
    values.update(overrides)
    result = Settings(**values)
    result.validate()
    return result


def request_headers(**extra: str) -> dict[str, str]:
    headers = {
        "authorization": f"Bearer {TOKEN}",
        "content-type": "application/json",
        "accept": "application/json",
    }
    headers.update(extra)
    return headers


def test_final_http_app_rejects_bad_host_origin_and_oversized_body_before_kernel_io() -> None:
    kernel = SpyKernel()
    app = create_http_app(settings(), kernel=kernel)  # type: ignore[arg-type]

    with TestClient(app, base_url="http://127.0.0.1:9101") as client:
        bad_host = client.post(
            "/mcp",
            headers=request_headers(host="evil.example"),
            content=b"{}",
        )
        assert bad_host.status_code == 421
        assert kernel.invoke_calls == 0

        bad_origin = client.post(
            "/mcp",
            headers=request_headers(origin="https://evil.example"),
            content=b"{}",
        )
        assert bad_origin.status_code == 403
        assert kernel.invoke_calls == 0

        oversized = client.post(
            "/mcp",
            headers=request_headers(),
            content=b"x" * 257,
        )
        assert oversized.status_code == 413
        assert kernel.invoke_calls == 0


def test_final_http_app_rejects_missing_wrong_or_duplicate_bearer_before_kernel_io() -> None:
    kernel = SpyKernel()
    app = create_http_app(settings(), kernel=kernel)  # type: ignore[arg-type]

    with TestClient(app, base_url="http://127.0.0.1:9101") as client:
        missing = client.post(
            "/mcp",
            headers={"content-type": "application/json", "accept": "application/json"},
            content=b"{}",
        )
        assert missing.status_code == 401
        assert kernel.invoke_calls == 0

        wrong = client.post(
            "/mcp",
            headers={
                "authorization": f"Bearer {'c' * 32}",
                "content-type": "application/json",
                "accept": "application/json",
            },
            content=b"{}",
        )
        assert wrong.status_code == 401
        assert kernel.invoke_calls == 0

        duplicate = client.post(
            "/mcp",
            headers=[
                ("authorization", f"Bearer {TOKEN}"),
                ("authorization", f"Bearer {TOKEN}"),
                ("content-type", "application/json"),
                ("accept", "application/json"),
            ],
            content=b"{}",
        )
        assert duplicate.status_code == 401
        assert kernel.invoke_calls == 0


def test_unknown_paths_return_404_without_authentication_or_kernel_io() -> None:
    kernel = SpyKernel()
    app = create_http_app(settings(), kernel=kernel)  # type: ignore[arg-type]

    with TestClient(app, base_url="http://127.0.0.1:9101") as client:
        root = client.get("/")
        assert root.status_code == 404

        unknown = client.get("/no/such/route")
        assert unknown.status_code == 404

        assert kernel.invoke_calls == 0
        assert kernel.readiness_calls == 0

        assert client.get("/health/ready").status_code == 401
        missing = client.post(
            "/mcp",
            headers={"content-type": "application/json", "accept": "application/json"},
            content=b"{}",
        )
        assert missing.status_code == 401
        assert kernel.invoke_calls == 0
        assert kernel.readiness_calls == 0


def test_live_is_public_but_ready_authenticates_before_dependency_probe() -> None:
    kernel = SpyKernel()
    app = create_http_app(settings(), kernel=kernel)  # type: ignore[arg-type]

    with TestClient(app, base_url="http://127.0.0.1:9101") as client:
        live = client.get("/health/live")
        assert live.status_code == 200
        assert kernel.readiness_calls == 0

        missing = client.get("/health/ready")
        assert missing.status_code == 401
        assert kernel.readiness_calls == 0

        wrong = client.get("/health/ready", headers={"authorization": f"Bearer {'c' * 32}"})
        assert wrong.status_code == 401
        assert kernel.readiness_calls == 0

        ready = client.get("/health/ready", headers={"authorization": f"Bearer {TOKEN}"})
        assert ready.status_code == 200
        assert kernel.readiness_calls == 1
