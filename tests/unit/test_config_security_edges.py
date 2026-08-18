from __future__ import annotations

import pytest

from kontomierz_mcp.config import ConfigurationError, Settings


def test_streamable_http_rejects_31_byte_bearer_token() -> None:
    with pytest.raises(ConfigurationError, match="at least 32 ASCII bytes"):
        Settings.from_env(
            {
                "KONTOMIERZ_MOCK_DATA": "1",
                "MCP_TRANSPORT": "streamable-http",
                "MCP_HOST": "127.0.0.1",
                "MCP_HTTP_AUTH_TOKEN": "a" * 31,
                "MCP_HTTP_PRINCIPAL": "operator",
            },
            env_file=None,
        )
