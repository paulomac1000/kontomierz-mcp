from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from kontomierz_mcp import healthcheck
from kontomierz_mcp.config import ConfigurationError, Settings

ROOT = Path(__file__).resolve().parents[2]


def test_short_http_token_error_reports_actual_ascii_byte_count() -> None:
    with pytest.raises(ConfigurationError, match=r"at least 32 ASCII bytes \(got 31\)"):
        Settings.from_env(
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_TRANSPORT": "streamable-http",
                "MCP_HTTP_AUTH_TOKEN": "x" * 31,
                "MCP_HTTP_PRINCIPAL": "operator:test",
            },
            env_file=None,
        )


def test_stdio_container_healthcheck_uses_process_liveness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    assert healthcheck.main() == 0


def test_http_container_healthcheck_uses_authenticated_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, Any] = {}

    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def fake_urlopen(request: Any, timeout: int) -> Response:
        observed["url"] = request.full_url
        observed["authorization"] = request.get_header("Authorization")
        observed["timeout"] = timeout
        return Response()

    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "9191")
    monkeypatch.setenv("MCP_HTTP_AUTH_TOKEN", "t" * 32)
    monkeypatch.setattr(healthcheck, "urlopen", fake_urlopen)

    assert healthcheck.main() == 0
    assert observed == {
        "url": "http://127.0.0.1:9191/health/ready",
        "authorization": "Bearer " + "t" * 32,
        "timeout": 2,
    }


def test_http_container_healthcheck_fails_closed_for_non_loopback_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HOST", "example.test")
    monkeypatch.setenv("MCP_HTTP_AUTH_TOKEN", "t" * 32)
    assert healthcheck.main() == 1


def test_container_build_is_bound_to_source_revision_and_exposes_healthcheck() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "ARG EXPECTED_SOURCE_REVISION" in dockerfile
    assert 'test "$(cat SOURCE_REVISION)" = "$EXPECTED_SOURCE_REVISION"' in dockerfile
    assert "org.opencontainers.image.revision=$EXPECTED_SOURCE_REVISION" in dockerfile
    assert "kontomierz_mcp.healthcheck" in dockerfile
    assert "dist/SOURCE_REVISION" in ci
    assert '--build-arg "EXPECTED_SOURCE_REVISION=${SOURCE_SHA}"' in ci
