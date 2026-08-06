"""Validated, immutable process configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

_DEFAULT_API_BASE_URL = "https://secure.kontomierz.pl/k4"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class ConfigurationError(ValueError):
    """Configuration is missing, malformed, or unsafe."""


def load_env_file(path: Path, environ: dict[str, str] | None = None) -> None:
    """Load a small dotenv file without overriding explicit environment values."""
    target = os.environ if environ is None else environ
    if not path.is_file():
        return
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigurationError(f"{path}:{number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or any(character.isspace() for character in key):
            raise ConfigurationError(f"{path}:{number}: invalid environment key")
        target.setdefault(key, value.strip().strip('"').strip("'"))


def _bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = env.get(name)
    return default if raw is None else raw.strip().lower() in _TRUE_VALUES


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """One validated settings snapshot owned by the composition root."""

    api_key: str
    api_base_url: str = _DEFAULT_API_BASE_URL
    api_timeout_seconds: int = 30
    body_mode: str = "json"
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 9101
    log_level: str = "INFO"
    enable_write_operations: bool = False
    mock_data: bool = False
    max_concurrency: int = 8
    max_pending_invocations: int = 16
    readiness_timeout_seconds: int = 5
    readiness_cache_seconds: int = 10

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        env_file: Path | None = Path(".env"),
    ) -> "Settings":
        if environ is None:
            if env_file is not None:
                load_env_file(env_file)
            env: Mapping[str, str] = os.environ
        else:
            copied = dict(environ)
            if env_file is not None:
                load_env_file(env_file, copied)
            env = copied

        settings = cls(
            api_key=env.get("KONTOMIERZ_API_KEY", "").strip(),
            api_base_url=env.get("KONTOMIERZ_API_BASE_URL", _DEFAULT_API_BASE_URL).rstrip("/"),
            api_timeout_seconds=_positive_int(env, "KONTOMIERZ_API_TIMEOUT", 30),
            body_mode=env.get("KONTOMIERZ_BODY_MODE", "json").strip().lower(),
            transport=env.get("MCP_TRANSPORT", "stdio").strip().lower(),
            host=env.get("MCP_HOST", "127.0.0.1").strip(),
            port=_positive_int(env, "MCP_PORT", 9101),
            log_level=env.get("LOG_LEVEL", "INFO").strip().upper(),
            enable_write_operations=_bool(env, "ENABLE_WRITE_OPERATIONS"),
            mock_data=_bool(env, "KONTOMIERZ_MOCK_DATA"),
            max_concurrency=_positive_int(env, "MCP_MAX_CONCURRENCY", 8),
            max_pending_invocations=_positive_int(env, "MCP_MAX_PENDING_INVOCATIONS", 16),
            readiness_timeout_seconds=_positive_int(env, "MCP_READINESS_TIMEOUT", 5),
            readiness_cache_seconds=_positive_int(env, "MCP_READINESS_CACHE_SECONDS", 10),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.api_key and not self.mock_data:
            raise ConfigurationError("KONTOMIERZ_API_KEY is required unless KONTOMIERZ_MOCK_DATA=1")
        if self.transport not in {"stdio", "http", "streamable-http"}:
            raise ConfigurationError("MCP_TRANSPORT must be stdio or http")
        if self.transport in {"http", "streamable-http"} and self.host not in _LOOPBACK_HOSTS:
            raise ConfigurationError(
                "Remote HTTP is disabled until authenticated principal and authorization policy are configured; "
                "use a loopback MCP_HOST"
            )
        if self.max_pending_invocations < self.max_concurrency:
            raise ConfigurationError("MCP_MAX_PENDING_INVOCATIONS must be at least MCP_MAX_CONCURRENCY")
        if self.body_mode not in {"json", "form"}:
            raise ConfigurationError("KONTOMIERZ_BODY_MODE must be json or form")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("LOG_LEVEL is invalid")
