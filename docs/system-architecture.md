---
description: Defines the server's components, ownership, data flow, lifecycle, and safe failure behavior.
doc_id: system.kontomierz-mcp-architecture
type: system
status: evolving
rigor: normative
owners: [repository-maintainers]
verification: Run `.venv/bin/python -m pytest tests/unit tests/integration -m "not external"` and the exact-wheel CI job.
---
# Kontomierz MCP system architecture

## Operational answer

Every tool invocation follows one path:

```text
stdio or loopback Streamable HTTP
  -> official MCP SDK registration
  -> InvocationKernel
  -> domain validation and policy
  -> KontomierzPort
  -> HTTP adapter or deterministic mock backend
```

No transport may invoke an operation or HTTP client directly.

## Component ownership

`Settings` is created once before dependencies. `InvocationKernel` owns the bounded worker pool and dependency lifetime. The official MCP SDK server owns protocol registration and enters the kernel lifecycle once. The HTTP adapter owns its `requests.Session`. Shutdown closes the worker pool and session exactly once.

## Security boundary

The current supported deployment boundary is one trusted local user. Stdio is the default. Streamable HTTP is limited to loopback and relies on the official SDK's Host/Origin protection. Public or LAN binding is rejected during configuration because the project does not yet authenticate a principal or authorize resources.

The API key is a process secret. It enters only the HTTP adapter and query parameters sent to the configured HTTPS origin. Errors expose a bounded application code and message, never raw bodies or credentials.

## Configuration and identity

`.env` is loaded before the immutable settings snapshot. Explicit process environment values override the file. The target is one configured Kontomierz account; operations never substitute another account after failure.

## Deadlines and concurrency

The kernel applies a per-manifest deadline and a bounded executor/semaphore. Read timeouts are retryable only where the manifest says so. A timeout during a write or destructive operation becomes `AMBIGUOUS_OUTCOME`; callers must reconcile resource state before any retry.

Python threads cannot forcibly terminate a running `requests` call. The adapter therefore also supplies an upstream socket timeout. The remaining residual risk is documented in the gap assessment.

## Health behavior

Liveness proves that the ASGI process responds. Readiness proves that configuration, registry, kernel, and dependency object are initialized. It does not claim that the remote Kontomierz service is currently healthy; dependency failures are reported by tool calls with typed errors.

## Failure modes

- Invalid input stops before dependency I/O.
- Disabled writes stop before dependency I/O.
- Authentication, not-found, conflict, rate-limit, timeout, dependency, and malformed-response failures retain distinct codes.
- Unexpected exceptions are logged with a request identifier and returned as a sanitized internal error.
- Partial or ambiguous writes are never automatically retried.

## Non-goals

This revision does not provide public multi-tenant hosting, OAuth, per-resource caller authorization, durable background tasks, or a compatibility REST API.
