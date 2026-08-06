from pathlib import Path

import pytest

from kontomierz_mcp.config import ConfigurationError, Settings, load_env_file


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


def test_pending_limit_cannot_be_smaller_than_running_limit() -> None:
    with pytest.raises(ConfigurationError, match="MCP_MAX_PENDING_INVOCATIONS"):
        Settings(api_key="", mock_data=True, max_concurrency=4, max_pending_invocations=3).validate()


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({}, "KONTOMIERZ_API_KEY"),
        ({"KONTOMIERZ_MOCK_DATA": "1", "MCP_TRANSPORT": "sse"}, "MCP_TRANSPORT"),
        (
            {"KONTOMIERZ_MOCK_DATA": "1", "MCP_TRANSPORT": "http", "MCP_HOST": "0.0.0.0"},
            "Remote HTTP",
        ),
        ({"KONTOMIERZ_MOCK_DATA": "1", "KONTOMIERZ_BODY_MODE": "xml"}, "KONTOMIERZ_BODY_MODE"),
        ({"KONTOMIERZ_MOCK_DATA": "1", "LOG_LEVEL": "TRACE"}, "LOG_LEVEL"),
        ({"KONTOMIERZ_MOCK_DATA": "1", "MCP_PORT": "x"}, "MCP_PORT"),
        ({"KONTOMIERZ_MOCK_DATA": "1", "MCP_PORT": "0"}, "MCP_PORT"),
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
