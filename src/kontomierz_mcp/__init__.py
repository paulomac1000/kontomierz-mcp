"""Secure MCP access to the Kontomierz personal-finance API."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("kontomierz-mcp")
except PackageNotFoundError:  # source checkout
    __version__ = "1.2.dev0"

__all__ = ["__version__"]
