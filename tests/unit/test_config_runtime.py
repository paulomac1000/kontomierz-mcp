from pathlib import Path

import pytest

from kontomierz_mcp.config import ConfigurationError, Settings, load_env_file

HTTP_TOKEN = "a" * 32


def test_settings_load_all_runtime_limits_from_environment() -> None:
    settings = Settings.from_env(
        {
            "KONTOMIERZ_MOCK_DATA": "1",
            "MCP_MAX_CONCURRENCY": "3",
            "MCP_MAX_PENDING_INVOCATIONS": "5",
            "MCP_READINESS_TIMEOUT": "2",
            "MCP_READINESS_CACHE_SECONDS": "7",
        },
        env_file=None,
    )
    assert settings.max_concurrency == 3
    assert settings.max_pending_invocations == 5
    assert settings.readiness_timeout_seconds == 2
    assert settings.readiness_cache_seconds == 7


def test_http_settings_load_authenticated_principal() -> None:
    settings = Settings.from_env(
        {
            "KONTOMIERZ_MOCK_DATA": "1",
            "MCP_TRANSPORT": "streamable-http",
            "MCP_HTTP_AUTH_TOKEN": HTTP_TOKEN,
            "MCP_HTTP_PRINCIPAL": "operator:test",
            "MCP_HTTP_ALLOWED_CAPABILITIES": "read,write",
            "MCP_HTTP_MAX_REQUEST_BODY_BYTES": "2048",
        },
        env_file=None,
    )
    assert settings.streamable_http is True
    assert settings.http_principal == "operator:test"
    assert settings.http_allowed_capabilities == ("read", "write")
    assert settings.http_max_request_body_bytes == 2048


def test_http_destructive_settings_load_exact_allowlists() -> None:
    settings = Settings.from_env(
        {
            "KONTOMIERZ_MOCK_DATA": "1",
            "MCP_TRANSPORT": "streamable-http",
            "MCP_HTTP_AUTH_TOKEN": HTTP_TOKEN,
            "MCP_HTTP_PRINCIPAL": "operator:test",
            "MCP_HTTP_ALLOWED_CAPABILITIES": "read,destructive",
            "MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES": "destroy_wallet,delete_transaction",
            "MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES": "wallet:123,transaction:456",
        },
        env_file=None,
    )
    assert settings.http_allowed_destructive_capabilities == ("destroy_wallet", "delete_transaction")
    assert settings.http_allowed_destructive_resources == ("wallet:123", "transaction:456")


def test_stdio_destructive_settings_load_exact_allowlists() -> None:
    settings = Settings.from_env(
        {
            "KONTOMIERZ_MOCK_DATA": "1",
            "MCP_STDIO_ALLOWED_DESTRUCTIVE_CAPABILITIES": "destroy_wallet,delete_budget",
            "MCP_STDIO_ALLOWED_DESTRUCTIVE_RESOURCES": "wallet:123,budget:456",
        },
        env_file=None,
    )
    assert settings.stdio_allowed_destructive_capabilities == ("destroy_wallet", "delete_budget")
    assert settings.stdio_allowed_destructive_resources == ("wallet:123", "budget:456")


def test_pending_limit_cannot_be_smaller_than_running_limit() -> None:
    with pytest.raises(ConfigurationError, match="MCP_MAX_PENDING_INVOCATIONS"):
        Settings(api_key="", mock_data=True, max_concurrency=4, max_pending_invocations=3).validate()


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({}, "KONTOMIERZ_API_KEY"),
        ({"KONTOMIERZ_MOCK_DATA": "1", "MCP_TRANSPORT": "sse"}, "MCP_TRANSPORT"),
        (
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_TRANSPORT": "http",
                "MCP_HOST": "0.0.0.0",
                "MCP_HTTP_AUTH_TOKEN": HTTP_TOKEN,
                "MCP_HTTP_PRINCIPAL": "operator:test",
            },
            "Remote HTTP",
        ),
        ({"KONTOMIERZ_MOCK_DATA": "1", "KONTOMIERZ_BODY_MODE": "xml"}, "KONTOMIERZ_BODY_MODE"),
        ({"KONTOMIERZ_API_KEY": "real-key", "KONTOMIERZ_BODY_MODE": "json"}, "requires KONTOMIERZ_BODY_MODE=form"),
        ({"KONTOMIERZ_MOCK_DATA": "1", "LOG_LEVEL": "TRACE"}, "LOG_LEVEL"),
        ({"KONTOMIERZ_MOCK_DATA": "1", "MCP_PORT": "x"}, "MCP_PORT"),
        ({"KONTOMIERZ_MOCK_DATA": "1", "MCP_PORT": "0"}, "MCP_PORT"),
        ({"KONTOMIERZ_MOCK_DATA": "1", "MCP_PORT": "65536"}, "MCP_PORT"),
        ({"KONTOMIERZ_MOCK_DATA": "1", "MCP_TRANSPORT": "http"}, "MCP_HTTP_AUTH_TOKEN"),
        (
            {"KONTOMIERZ_MOCK_DATA": "1", "MCP_TRANSPORT": "http", "MCP_HTTP_AUTH_TOKEN": HTTP_TOKEN},
            "MCP_HTTP_PRINCIPAL",
        ),
        (
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_TRANSPORT": "http",
                "MCP_HTTP_AUTH_TOKEN": "a" * 31 + "\x7f",
                "MCP_HTTP_PRINCIPAL": "operator:test",
            },
            "visible ASCII",
        ),
        (
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_TRANSPORT": "http",
                "MCP_HTTP_AUTH_TOKEN": HTTP_TOKEN,
                "MCP_HTTP_PRINCIPAL": "operator:\x7f",
            },
            "visible ASCII",
        ),
        (
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_TRANSPORT": "http",
                "MCP_HTTP_AUTH_TOKEN": HTTP_TOKEN,
                "MCP_HTTP_PRINCIPAL": "operator:test",
                "MCP_HTTP_ALLOWED_CAPABILITIES": "read,admin",
            },
            "MCP_HTTP_ALLOWED_CAPABILITIES",
        ),
        (
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_TRANSPORT": "http",
                "MCP_HTTP_AUTH_TOKEN": HTTP_TOKEN,
                "MCP_HTTP_PRINCIPAL": "operator:test",
                "MCP_HTTP_ALLOWED_CAPABILITIES": "read,destructive",
            },
            "destructive access",
        ),
        (
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_TRANSPORT": "http",
                "MCP_HTTP_AUTH_TOKEN": HTTP_TOKEN,
                "MCP_HTTP_PRINCIPAL": "operator:test",
                "MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES": "list_accounts",
            },
            "MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES",
        ),
        (
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_TRANSPORT": "http",
                "MCP_HTTP_AUTH_TOKEN": HTTP_TOKEN,
                "MCP_HTTP_PRINCIPAL": "operator:test",
                "MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES": "wallet:0",
            },
            "MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES",
        ),
        (
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_TRANSPORT": "http",
                "MCP_HTTP_AUTH_TOKEN": HTTP_TOKEN,
                "MCP_HTTP_PRINCIPAL": "operator:test",
                "MCP_HTTP_MAX_REQUEST_BODY_BYTES": str(4 * 1024 * 1024 + 1),
            },
            "MCP_HTTP_MAX_REQUEST_BODY_BYTES",
        ),
        (
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_STDIO_ALLOWED_DESTRUCTIVE_CAPABILITIES": "destroy_wallet",
            },
            "Destructive access requires both",
        ),
        (
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_STDIO_ALLOWED_DESTRUCTIVE_RESOURCES": "wallet:123",
            },
            "Destructive access requires both",
        ),
    ],
)
def test_invalid_settings_fail_closed(environment: dict[str, str], message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        Settings.from_env(environment, env_file=None)


def test_env_file_does_not_override_explicit_values(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("KONTOMIERZ_MOCK_DATA=1\nMCP_PORT=9000\n", encoding="utf-8")
    environment = {"MCP_PORT": "9101"}
    load_env_file(path, environment)
    assert environment == {"MCP_PORT": "9101", "KONTOMIERZ_MOCK_DATA": "1"}


def test_invalid_env_file_line_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("NOT_AN_ASSIGNMENT\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="expected KEY=VALUE"):
        load_env_file(path, {})


def test_destructive_capability_and_resource_allowlists_must_match() -> None:
    base = {
        "KONTOMIERZ_MOCK_DATA": "1",
        "MCP_TRANSPORT": "streamable-http",
        "MCP_HTTP_AUTH_TOKEN": HTTP_TOKEN,
        "MCP_HTTP_PRINCIPAL": "operator:test",
        "MCP_HTTP_ALLOWED_CAPABILITIES": "read,destructive",
    }
    with pytest.raises(ConfigurationError, match="matching exact resource"):
        Settings.from_env(
            {
                **base,
                "MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES": "destroy_wallet",
                "MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES": "transaction:123",
            },
            env_file=None,
        )
    with pytest.raises(ConfigurationError, match="match an explicitly allowed"):
        Settings.from_env(
            {
                **base,
                "MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES": "destroy_wallet",
                "MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES": "wallet:123,transaction:456",
            },
            env_file=None,
        )
