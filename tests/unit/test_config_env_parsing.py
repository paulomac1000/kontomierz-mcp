from __future__ import annotations

from pathlib import Path

import pytest

from kontomierz_mcp.config import ConfigurationError, Settings, load_env_file


def test_env_file_removes_only_one_matching_surrounding_quote_pair(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        'DOUBLE="quoted-value"\nSINGLE=\'single-value\'\nTRAILING=kept"\nMISMATCH="kept\'\n',
        encoding="utf-8",
    )
    environment: dict[str, str] = {}

    load_env_file(path, environment)

    assert environment == {
        "DOUBLE": "quoted-value",
        "SINGLE": "single-value",
        "TRAILING": 'kept"',
        "MISMATCH": '"kept\'',
    }


def test_short_http_bearer_token_is_rejected_by_length_floor() -> None:
    with pytest.raises(ConfigurationError, match="at least 32 ASCII bytes"):
        Settings.from_env(
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_TRANSPORT": "streamable-http",
                "MCP_HTTP_AUTH_TOKEN": "a" * 31,
                "MCP_HTTP_PRINCIPAL": "operator:test",
            },
            env_file=None,
        )
