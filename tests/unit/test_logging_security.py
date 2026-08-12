from __future__ import annotations

import logging

from kontomierz_mcp.config import Settings
from kontomierz_mcp.server import configure_application_logging


def test_http_dependency_loggers_do_not_inherit_debug_or_info_verbosity() -> None:
    httpx_logger = logging.getLogger("httpx")
    httpcore_logger = logging.getLogger("httpcore")
    previous = (httpx_logger.level, httpcore_logger.level)
    try:
        httpx_logger.setLevel(logging.NOTSET)
        httpcore_logger.setLevel(logging.NOTSET)
        configure_application_logging(Settings(api_key="", mock_data=True, log_level="DEBUG"))
        assert httpx_logger.level >= logging.WARNING
        assert httpcore_logger.level >= logging.WARNING
    finally:
        httpx_logger.setLevel(previous[0])
        httpcore_logger.setLevel(previous[1])
