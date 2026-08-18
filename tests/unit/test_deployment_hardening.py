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


@pytest.mark.parametrize("port", ["not-a-port", "0", "65536", "-1"])
def test_http_container_healthcheck_rejects_invalid_ports(monkeypatch: pytest.MonkeyPatch, port: str) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", port)
    monkeypatch.setenv("MCP_HTTP_AUTH_TOKEN", "t" * 32)
    assert healthcheck.main() == 1


def test_http_container_healthcheck_requires_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.delenv("MCP_HTTP_AUTH_TOKEN", raising=False)
    assert healthcheck.main() == 1


def test_http_container_healthcheck_fails_when_readiness_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unreachable(request: Any, timeout: int) -> Any:
        raise OSError("connection refused")

    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_HTTP_AUTH_TOKEN", "t" * 32)
    monkeypatch.setattr(healthcheck, "urlopen", unreachable)
    assert healthcheck.main() == 1


def test_http_container_healthcheck_fails_when_readiness_is_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    class NotReadyResponse:
        status = 503

        def __enter__(self) -> NotReadyResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def not_ready(request: Any, timeout: int) -> NotReadyResponse:
        return NotReadyResponse()

    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HOST", "localhost")
    monkeypatch.setenv("MCP_PORT", "9191")
    monkeypatch.setenv("MCP_HTTP_AUTH_TOKEN", "t" * 32)
    monkeypatch.setattr(healthcheck, "urlopen", not_ready)
    assert healthcheck.main() == 1


def test_http_container_healthcheck_formats_ipv6_loopback_literal(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, Any] = {}

    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def fake_urlopen(request: Any, timeout: int) -> Response:
        observed["url"] = request.full_url
        return Response()

    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_HOST", "::1")
    monkeypatch.setenv("MCP_PORT", "9191")
    monkeypatch.setenv("MCP_HTTP_AUTH_TOKEN", "t" * 32)
    monkeypatch.setattr(healthcheck, "urlopen", fake_urlopen)
    assert healthcheck.main() == 0
    assert observed["url"] == "http://[::1]:9191/health/ready"


def test_unknown_transport_is_treated_as_unhealthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "grpc")
    assert healthcheck.main() == 1


def test_container_build_is_bound_to_source_revision_and_exposes_healthcheck() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "AS verified-artifacts" in dockerfile
    assert dockerfile.count("ARG EXPECTED_SOURCE_REVISION") == 2
    assert 'SHELL ["/bin/sh", "-c"]' in dockerfile
    assert "read -r ACTUAL_SOURCE_REVISION < /tmp/dist/SOURCE_REVISION" in dockerfile
    assert 'test "$ACTUAL_SOURCE_REVISION" = "$EXPECTED_SOURCE_REVISION"' in dockerfile
    assert "COPY --from=verified-artifacts /tmp/dist/ /tmp/dist/" in dockerfile
    assert "$(cat SOURCE_REVISION)" not in dockerfile
    assert "org.opencontainers.image.revision=$EXPECTED_SOURCE_REVISION" in dockerfile
    assert "kontomierz_mcp.healthcheck" in dockerfile
    assert "dist/SOURCE_REVISION" in ci
    assert '--build-arg "EXPECTED_SOURCE_REVISION=${SOURCE_SHA}"' in ci


def test_exact_artifact_wheel_builds_are_pinned_to_commit_timestamp() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    local_gate = (ROOT / "scripts/local_exact_gate.py").read_text(encoding="utf-8")

    assert 'SOURCE_DATE_EPOCH="$(git log -1 --format=%ct HEAD)"' in ci
    assert "export SOURCE_DATE_EPOCH" in ci
    assert "SOURCE_DATE_EPOCH" in ci.split("Build exact application wheel", 1)[1].split("Materialize", 1)[0]
    assert '"SOURCE_DATE_EPOCH": _source_date_epoch()' in local_gate
