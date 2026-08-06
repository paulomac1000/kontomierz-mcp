---
description: Defines the server's components, ownership, data flow, lifecycle, and safe failure behavior.
doc_id: system.kontomierz-mcp-architecture
type: system
status: evolving
rigor: normative
owners: [repository-maintainers]
verification: Run `.venv/bin/python -m pytest -m "not external"` and the exact-wheel CI job.
---
# Kontomierz MCP system architecture

## Operational answer

```text
stdio or loopback Streamable HTTP
  -> official MCP SDK registration
  -> InvocationKernel
  -> domain validation and policy
  -> asynchronous KontomierzPort
  -> HTTP adapter or deterministic mock backend
```

No transport invokes an operation or dependency directly.

## Component ownership

`Settings` is created before dependencies. `InvocationKernel` owns bounded admission, running concurrency, per-target serialization, deadlines, readiness state, and dependency lifetime. `KontomierzClient` owns one cancellation-aware `httpx.AsyncClient`. The governed catalog owns every public signature, description, manifest, version, and discovery expectation. The SDK server projects that catalog into protocol registration and owns lifecycle entry.

## Security boundary

The current deployment boundary is one trusted local user. Stdio is the default. Streamable HTTP is loopback-only. Public or LAN binding is rejected because principal authentication and resource authorization are not implemented. The API key enters only the HTTP adapter and is never returned in errors.

## Deadlines, cancellation, and concurrency

There is no worker pool or executor queue. The kernel limits total admitted invocations and separately limits operations actively running against the dependency. Calls above the admission bound fail before execution. `concurrent_safe=false` operations are serialized by `target_scope`, currently `kontomierz-account`.

Cancellation propagates through the async operation into `httpx`. If a write has started, a kernel deadline, transport loss, timeout, response loss, or ambiguous 5xx becomes `AMBIGUOUS_OUTCOME` with `retryable=false`. Callers reconcile state before any retry. The runtime performs no automatic retries.

## Health behavior

Liveness proves the ASGI process responds. Readiness requires the full operation catalog and a bounded, cached probe of the mandatory Kontomierz dependency. Failed credentials, an unavailable backend, a probe timeout, shutdown, or an incomplete registry returns not-ready.

## Failure modes

- Invalid input, disabled writes, and admission rejection stop before dependency I/O.
- Authentication, not-found, conflict, rate-limit, timeout, dependency, and malformed-response failures retain distinct codes.
- Tool errors are explicit MCP `CallToolResult` documents with stable structured JSON.
- Unexpected exceptions are logged with a request ID and exposed only as sanitized internal errors.

## Non-goals

This revision does not provide public multi-tenant hosting, OAuth, per-resource caller authorization, durable background work, or a compatibility REST API.
