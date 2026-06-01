"""Shared pytest fixtures for kontomierz-mcp tests.

Loads .env files and provides mock MCP client fixtures.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Canonical Template 3 — load .env files (setdefault to avoid overwriting already-set vars)
_env_paths = [
    PROJECT_ROOT / ".env",
    Path("/app/.env"),
]
for _env_path in _env_paths:
    if _env_path.exists():
        with open(_env_path) as f:
            for _line in f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _key, _value = _line.split("=", 1)
                    os.environ.setdefault(_key.strip(), _value.strip().strip('"').strip("'"))


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a MagicMock standing in for KontomierzClient (no real I/O)."""
    return MagicMock()


@pytest.fixture
def mock_mcp() -> MagicMock:
    """Mock FastMCP instance with working tool() decorator and lifespan context."""
    mcp = MagicMock()
    mcp._tools = {}

    def tool_decorator(*args, **kwargs):
        def wrapper(func):
            tool_name = kwargs.get("name", func.__name__)
            mcp._tools[tool_name] = func
            return func

        if len(args) == 1 and callable(args[0]) and not kwargs:
            mcp._tools[args[0].__name__] = args[0]
            return args[0]
        return wrapper

    mcp.tool = tool_decorator
    mcp.get_tool = lambda name: mcp._tools.get(name)
    return mcp


@pytest.fixture
def mcp_context(mock_client: MagicMock) -> MagicMock:
    """Mock MCP context with lifespan data containing the mock client."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"client": mock_client}
    return ctx
