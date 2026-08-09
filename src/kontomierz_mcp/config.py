"""Validated, immutable process configuration."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_API_BASE_URL = "https://secure.kontomierz.pl/k4"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_MAX_HTTP_CREDENTIAL_BYTES = 512
_MAX_HTTP_REQUEST_BODY_BYTES = 4 * 1024 * 1024
_HTTP_CAPABILITY_CLASSES = frozenset({"read", "write", "destructive"})
_DESTRUCTIVE_RESOURCE_PREFIX = {
    "destroy_wallet": "wallet:",
    "delete_transaction": "transaction:",
    "delete_budget": "budget:",
    "delete_schedule": "schedule:",
}
_DESTRUCTIVE_CAPABILITIES = frozenset(_DESTRUCTIVE_RESOURCE_PREFIX)
_DESTRUCTIVE_RESOURCE = re.compile(r"^(?:wallet|transaction|budget|schedule):[1-9][0-9]*$")
_CAPABILITY_ID = re.compile(r"^[a-z][a-z0-9_]{0,127}$")


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


def _http_capabilities(env: Mapping[str, str]) -> tuple[str, ...]:
    raw = env.get("MCP_HTTP_ALLOWED_CAPABILITIES", "read")
    values = tuple(dict.fromkeys(part.strip().lower() for part in raw.split(",") if part.strip()))
    if not values:
        raise ConfigurationError("MCP_HTTP_ALLOWED_CAPABILITIES must contain at least one capability class")
    invalid = sorted(set(values) - _HTTP_CAPABILITY_CLASSES)
    if invalid:
        raise ConfigurationError(
            "MCP_HTTP_ALLOWED_CAPABILITIES contains invalid capability classes: " + ", ".join(invalid)
        )
    return values


def _csv_values(env: Mapping[str, str], name: str) -> tuple[str, ...]:
    raw = env.get(name, "")
    return tuple(dict.fromkeys(part.strip() for part in raw.split(",") if part.strip()))


def _destructive_capabilities(env: Mapping[str, str]) -> tuple[str, ...]:
    values = _csv_values(env, "MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES")
    invalid = [
        value for value in values if _CAPABILITY_ID.fullmatch(value) is None or value not in _DESTRUCTIVE_CAPABILITIES
    ]
    if invalid:
        raise ConfigurationError(
            "MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES contains invalid capability IDs: " + ", ".join(sorted(invalid))
        )
    return values


def _destructive_resources(env: Mapping[str, str]) -> tuple[str, ...]:
    values = _csv_values(env, "MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES")
    invalid = [value for value in values if _DESTRUCTIVE_RESOURCE.fullmatch(value) is None]
    if invalid:
        raise ConfigurationError(
            "MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES must contain exact resource IDs such as wallet:123"
        )
    return values


def _bounded_ascii_secret(value: str, name: str) -> str:
    if not value:
        raise ConfigurationError(f"{name} is required for Streamable HTTP")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ConfigurationError(f"{name} must contain ASCII characters only") from exc
    if len(encoded) < 32:
        raise ConfigurationError(f"{name} must contain at least 32 ASCII bytes")
    if len(encoded) > _MAX_HTTP_CREDENTIAL_BYTES:
        raise ConfigurationError(f"{name} must not exceed {_MAX_HTTP_CREDENTIAL_BYTES} ASCII bytes")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """One validated settings snapshot owned by the composition root."""

    api_key: str
    api_base_url: str = _DEFAULT_API_BASE_URL
    api_timeout_seconds: int = 30
    body_mode: str = "form"
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
    http_auth_token: str = ""
    http_principal: str = ""
    http_allowed_capabilities: tuple[str, ...] = ("read",)
    http_allowed_destructive_capabilities: tuple[str, ...] = ()
    http_allowed_destructive_resources: tuple[str, ...] = ()
    http_max_request_body_bytes: int = 1024 * 1024

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        env_file: Path | None = Path(".env"),
    ) -> Settings:
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
            body_mode=env.get("KONTOMIERZ_BODY_MODE", "form").strip().lower(),
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
            http_auth_token=env.get("MCP_HTTP_AUTH_TOKEN", "").strip(),
            http_principal=env.get("MCP_HTTP_PRINCIPAL", "").strip(),
            http_allowed_capabilities=_http_capabilities(env),
            http_allowed_destructive_capabilities=_destructive_capabilities(env),
            http_allowed_destructive_resources=_destructive_resources(env),
            http_max_request_body_bytes=_positive_int(env, "MCP_HTTP_MAX_REQUEST_BODY_BYTES", 1024 * 1024),
        )
        settings.validate()
        return settings

    @property
    def streamable_http(self) -> bool:
        return self.transport in {"http", "streamable-http"}

    def validate(self) -> None:
        if not self.api_key and not self.mock_data:
            raise ConfigurationError("KONTOMIERZ_API_KEY is required unless KONTOMIERZ_MOCK_DATA=1")
        if self.transport not in {"stdio", "http", "streamable-http"}:
            raise ConfigurationError("MCP_TRANSPORT must be stdio, http, or streamable-http")
        if not 1 <= self.port <= 65535:
            raise ConfigurationError("MCP_PORT must be between 1 and 65535")
        if self.streamable_http:
            if self.host not in _LOOPBACK_HOSTS:
                raise ConfigurationError("Remote HTTP is disabled; Streamable HTTP must use a loopback MCP_HOST")
            _bounded_ascii_secret(self.http_auth_token, "MCP_HTTP_AUTH_TOKEN")
            if not self.http_principal:
                raise ConfigurationError("MCP_HTTP_PRINCIPAL is required for Streamable HTTP")
            try:
                principal_bytes = self.http_principal.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ConfigurationError("MCP_HTTP_PRINCIPAL must contain ASCII characters only") from exc
            if len(principal_bytes) > 128:
                raise ConfigurationError("MCP_HTTP_PRINCIPAL must not exceed 128 ASCII bytes")
            invalid_capabilities = sorted(set(self.http_allowed_capabilities) - _HTTP_CAPABILITY_CLASSES)
            if not self.http_allowed_capabilities or invalid_capabilities:
                raise ConfigurationError("MCP_HTTP_ALLOWED_CAPABILITIES must contain only read, write, destructive")
            invalid_destructive_capabilities = sorted(
                set(self.http_allowed_destructive_capabilities) - _DESTRUCTIVE_CAPABILITIES
            )
            invalid_destructive_resources = [
                resource
                for resource in self.http_allowed_destructive_resources
                if _DESTRUCTIVE_RESOURCE.fullmatch(resource) is None
            ]
            if invalid_destructive_capabilities:
                raise ConfigurationError("MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES contains invalid capability IDs")
            if invalid_destructive_resources:
                raise ConfigurationError("MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES must use exact resource IDs")
            if "destructive" in self.http_allowed_capabilities and (
                not self.http_allowed_destructive_capabilities or not self.http_allowed_destructive_resources
            ):
                raise ConfigurationError(
                    "HTTP destructive access requires explicit capability and exact resource allowlists"
                )
            if "destructive" in self.http_allowed_capabilities:
                resources = self.http_allowed_destructive_resources
                for capability in self.http_allowed_destructive_capabilities:
                    prefix = _DESTRUCTIVE_RESOURCE_PREFIX[capability]
                    if not any(resource.startswith(prefix) for resource in resources):
                        raise ConfigurationError(
                            "Each destructive capability must have at least one matching exact resource ID"
                        )
                allowed_prefixes = {
                    _DESTRUCTIVE_RESOURCE_PREFIX[capability]
                    for capability in self.http_allowed_destructive_capabilities
                }
                if any(not any(resource.startswith(prefix) for prefix in allowed_prefixes) for resource in resources):
                    raise ConfigurationError(
                        "Each destructive resource must match an explicitly allowed destructive capability"
                    )
            if self.http_max_request_body_bytes > _MAX_HTTP_REQUEST_BODY_BYTES:
                raise ConfigurationError(
                    f"MCP_HTTP_MAX_REQUEST_BODY_BYTES must not exceed {_MAX_HTTP_REQUEST_BODY_BYTES}"
                )
        if self.max_pending_invocations < self.max_concurrency:
            raise ConfigurationError("MCP_MAX_PENDING_INVOCATIONS must be at least MCP_MAX_CONCURRENCY")
        if self.body_mode not in {"json", "form"}:
            raise ConfigurationError("KONTOMIERZ_BODY_MODE must be json or form")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("LOG_LEVEL is invalid")
