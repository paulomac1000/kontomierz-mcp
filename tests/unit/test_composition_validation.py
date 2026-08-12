from __future__ import annotations

import pytest

from kontomierz_mcp.config import ConfigurationError, Settings
from kontomierz_mcp.server import build_kernel


def test_build_kernel_rejects_invalid_settings_before_dependency_construction() -> None:
    settings = Settings(
        api_key="secret",
        api_base_url="http://secure.kontomierz.pl/k4",
        mock_data=False,
    )
    with pytest.raises(ConfigurationError, match="absolute HTTPS URL"):
        build_kernel(settings)
