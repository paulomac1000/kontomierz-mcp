"""Request-scoped principal and Streamable HTTP authentication boundary."""

from __future__ import annotations

import getpass
import hmac
import os
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Literal

from starlette.types import ASGIApp, Receive, Scope, Send

from .config import Settings

Transport = Literal["stdio", "streamable-http"]


@dataclass(frozen=True, slots=True)
class InvocationContext:
    principal: str
    transport: Transport
    authenticated: bool

    @classmethod
    def local_stdio(cls) -> InvocationContext:
        user = getpass.getuser() or "unknown"
        uid = str(os.geteuid()) if hasattr(os, "geteuid") else "unknown"
        return cls(principal=f"local-user:{user}:uid:{uid}", transport="stdio", authenticated=True)

    @classmethod
    def authenticated_http(cls, principal: str) -> InvocationContext:
        return cls(principal=principal, transport="streamable-http", authenticated=True)

    @classmethod
    def configured_http(cls, settings: Settings) -> InvocationContext:
        authenticated = bool(settings.http_auth_token and settings.http_principal)
        principal = settings.http_principal if authenticated else "unbound-http-principal"
        return cls(principal=principal, transport="streamable-http", authenticated=authenticated)


_context: ContextVar[InvocationContext | None] = ContextVar("kontomierz_invocation_context", default=None)


def current_invocation_context() -> InvocationContext | None:
    return _context.get()


def bind_invocation_context(context: InvocationContext) -> Token[InvocationContext | None]:
    return _context.set(context)


def reset_invocation_context(token: Token[InvocationContext | None]) -> None:
    _context.reset(token)


class BearerPrincipalMiddleware:
    """Authenticate every MCP HTTP request before it reaches the SDK application."""

    _MAX_AUTHORIZATION_BYTES = 1024

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self._app = app
        self._token = settings.http_auth_token.encode("ascii")
        self._principal = settings.http_principal

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        values = [value for name, value in scope.get("headers", ()) if name.lower() == b"authorization"]
        if len(values) != 1 or len(values[0]) > self._MAX_AUTHORIZATION_BYTES:
            await self._reject(send)
            return
        try:
            header = values[0].decode("ascii")
        except UnicodeDecodeError:
            await self._reject(send)
            return
        scheme, separator, supplied = header.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not supplied:
            await self._reject(send)
            return
        try:
            supplied_bytes = supplied.encode("ascii")
        except UnicodeEncodeError:
            await self._reject(send)
            return
        if not hmac.compare_digest(supplied_bytes, self._token):
            await self._reject(send)
            return

        token = bind_invocation_context(
            InvocationContext.authenticated_http(self._principal)
        )
        try:
            await self._app(scope, receive, send)
        finally:
            reset_invocation_context(token)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = b'{"error":{"code":"AUTHENTICATION_FAILED","message":"HTTP authentication failed","retryable":false}}'
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
