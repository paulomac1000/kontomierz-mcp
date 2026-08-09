from __future__ import annotations

import sys
from pathlib import Path

import pytest

from kontomierz_mcp.config import Settings
from kontomierz_mcp.mock_backend import MockKontomierzClient
from kontomierz_mcp.server import build_kernel

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_MOCK_DESTRUCTIVE_CAPABILITIES = (
    "destroy_wallet",
    "delete_transaction",
    "delete_budget",
    "delete_schedule",
)
_MOCK_DESTRUCTIVE_RESOURCES = (
    "wallet:102",
    "transaction:1002",
    "transaction:1003",
    "budget:201",
    "schedule:301",
)


@pytest.fixture
def readonly_settings() -> Settings:
    return Settings(api_key="", mock_data=True, enable_write_operations=False)


@pytest.fixture
def write_settings() -> Settings:
    settings = Settings(
        api_key="",
        mock_data=True,
        enable_write_operations=True,
        stdio_allowed_destructive_capabilities=_MOCK_DESTRUCTIVE_CAPABILITIES,
        stdio_allowed_destructive_resources=_MOCK_DESTRUCTIVE_RESOURCES,
    )
    settings.validate()
    return settings


@pytest.fixture
def mock_client() -> MockKontomierzClient:
    return MockKontomierzClient()


@pytest.fixture
def readonly_kernel(readonly_settings: Settings, mock_client: MockKontomierzClient):
    return build_kernel(readonly_settings, mock_client)


@pytest.fixture
def write_kernel(write_settings: Settings, mock_client: MockKontomierzClient):
    return build_kernel(write_settings, mock_client)
