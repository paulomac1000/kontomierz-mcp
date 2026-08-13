"""Request-scoped principal and Streamable HTTP authentication boundary."""

from __future__ import annotations

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
        """Bind stdio trust to process-owned OS identity, never spoofable username environment."""
        if hasattr(os, "geteuid"):
            principal = f"local-process:uid:{os.geteuid()}"
        else:  # Windows has no geteuid; stdio trust is the spawned local process boundary.
            principal = f"local-process:pid:{os.getpid()}"
        return cls(principal=principal, transport="stdio", authenticated=True)

    @classmethod
    def authenticated_http(cls, principal: str) -> InvocationContext:
        return cls(principal=principal, transport="streamable-http", authenticated=True)

    @classmethod
    def unauthenticated_http(cls) -> InvocationContext:
        return cls(principal="unbound-http-principal", transport="streamable-http", authenticated=False)


_context: ContextVar[InvocationContext | None] = ContextVar("kontomierz_invocation_context", default=None)


def current_invocation_context() -> InvocationContext | None:
    return _context.get()


def bind_invocation_context(context: InvocationContext) -> Token[InvocationContext | None]:
    return _context.set(context)


def reset_invocation_context(token: Token[InvocationContext | None]) -> None:
    _context.reset(token)


class BearerPrincipalMiddleware:
    """Authenticate protected HTTP routes and reject unknown routes before SDK handling."""

    _MAX_AUTHORIZATION_BYTES = 1024

    def __init__(
        self,
        app: ASGIApp,
        settings: Settings,
        *,
        public_paths: frozenset[str] = frozenset(),
        protected_paths: frozenset[str] | None = None,
    ) -> None:
        self._app = app
        self._token = settings.http_auth_token.encode("ascii")
        self._principal = settings.http_principal
        self._public_paths = public_paths
        # None = fail-closed default: every non-public path authenticates.
        self._protected_paths = protected_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        if scope.get("path") in self._public_paths:
            await self._app(scope, receive, send)
            return
        if self._protected_paths is not None and scope.get("path") not in self._protected_paths:
            # Do not pass an unauthenticated request into the mounted SDK app: future SDK routes
            # must not silently become public merely because the outer router has a catch-all mount.
            await self._not_found(send)
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

        token = bind_invocation_context(InvocationContext.authenticated_http(self._principal))
        try:
            await self._app(scope, receive, send)
        finally:
            reset_invocation_context(token)

    @staticmethod
    async def _not_found(send: Send) -> None:
        body = b'{"error":{"code":"NOT_FOUND","message":"Not found","retryable":false}}'
        await send(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

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
