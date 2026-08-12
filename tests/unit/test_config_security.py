from __future__ import annotations

import pytest

from kontomierz_mcp.config import ConfigurationError, Settings


@pytest.mark.parametrize(
    "base_url",
    [
        "http://secure.kontomierz.pl/k4",
        "https://user:pass@secure.kontomierz.pl/k4",
        "https://secure.kontomierz.pl/k4?token=x",
        "https://secure.kontomierz.pl/k4#fragment",
        "secure.kontomierz.pl/k4",
    ],
)
def test_real_backend_requires_plain_absolute_https_base_url(base_url: str) -> None:
    with pytest.raises(ConfigurationError, match="absolute HTTPS URL"):
        Settings(api_key="secret", api_base_url=base_url).validate()


def test_mock_backend_does_not_require_network_base_url() -> None:
    Settings(api_key="", api_base_url="mock://local", mock_data=True).validate()
