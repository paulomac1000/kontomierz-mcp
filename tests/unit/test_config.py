from pathlib import Path

import pytest

from kontomierz_mcp.config import ConfigurationError, Settings


def test_env_file_is_loaded_before_snapshot(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KONTOMIERZ_MOCK_DATA=1\nMCP_TRANSPORT=http\nMCP_PORT=9999\n", encoding="utf-8")
    settings = Settings.from_env({}, env_file=env_file)
    assert settings.mock_data is True
    assert settings.transport == "http"
    assert settings.port == 9999


def test_explicit_environment_wins_over_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("MCP_PORT=9999\nKONTOMIERZ_MOCK_DATA=1\n", encoding="utf-8")
    settings = Settings.from_env({"MCP_PORT": "9101", "KONTOMIERZ_MOCK_DATA": "1"}, env_file=env_file)
    assert settings.port == 9101


def test_remote_http_fails_closed() -> None:
    with pytest.raises(ConfigurationError, match="Remote HTTP is disabled"):
        Settings.from_env(
            {"KONTOMIERZ_MOCK_DATA": "1", "MCP_TRANSPORT": "http", "MCP_HOST": "0.0.0.0"},
            env_file=None,
        )


def test_api_key_required_without_mock() -> None:
    with pytest.raises(ConfigurationError, match="KONTOMIERZ_API_KEY"):
        Settings.from_env({}, env_file=None)


def test_body_mode_is_explicit() -> None:
    settings = Settings.from_env(
        {"KONTOMIERZ_MOCK_DATA": "1", "KONTOMIERZ_BODY_MODE": "form"},
        env_file=None,
    )
    assert settings.body_mode == "form"


def test_invalid_dotenv_lines_fail_with_stable_error(tmp_path: Path) -> None:
    missing_equals = tmp_path / "missing-equals.env"
    missing_equals.write_text("BROKEN\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="expected KEY=VALUE"):
        Settings.from_env({"KONTOMIERZ_MOCK_DATA": "1"}, env_file=missing_equals)

    invalid_key = tmp_path / "invalid-key.env"
    invalid_key.write_text("BAD KEY=value\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="invalid environment key"):
        Settings.from_env({"KONTOMIERZ_MOCK_DATA": "1"}, env_file=invalid_key)


def test_invalid_typed_settings_fail_closed() -> None:
    base = {"KONTOMIERZ_MOCK_DATA": "1"}
    for name, value, message in (
        ("MCP_PORT", "zero", "must be an integer"),
        ("MCP_PORT", "0", "must be positive"),
        ("MCP_TRANSPORT", "sse", "MCP_TRANSPORT"),
        ("KONTOMIERZ_BODY_MODE", "xml", "KONTOMIERZ_BODY_MODE"),
        ("LOG_LEVEL", "TRACE", "LOG_LEVEL"),
    ):
        with pytest.raises(ConfigurationError, match=message):
            Settings.from_env({**base, name: value}, env_file=None)
