"""Secure MCP access to the Kontomierz personal-finance API."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("kontomierz-mcp")
except PackageNotFoundError:  # source checkout
    __version__ = "2.0.1.dev0"

__all__ = ["__version__"]
