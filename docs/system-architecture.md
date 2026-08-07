---
description: Defines the server's components, ownership, data flow, lifecycle, and safe failure behavior.
doc_id: system.kontomierz-mcp-architecture
type: system
status: evolving
rigor: normative
owners: [repository-maintainers]
verification: Run `python -m pytest -m "not external"` and the exact-artifact CI job.
---
# Kontomierz MCP system architecture

## Operational answer

```text
local stdio process principal OR authenticated loopback Streamable HTTP principal
  -> official MCP SDK registration
  -> InvocationKernel
  -> domain validation and policy
  -> asynchronous KontomierzPort
  -> HTTP adapter or deterministic mock backend
```

No transport invokes an operation or dependency directly.

## Component ownership

`Settings` is created before dependencies. `security.py` owns process-derived stdio identity and the Streamable HTTP Bearer boundary. `InvocationKernel` owns authenticated-context enforcement, bounded admission, running concurrency, per-target serialization, deadlines, readiness state, and dependency lifetime. `KontomierzClient` owns one cancellation-aware `httpx.AsyncClient`. The governed catalog owns every public signature, description, manifest, version, and discovery expectation. The SDK server projects that catalog into protocol registration and owns lifecycle entry.

## Security boundary

Stdio is the safe default and derives a principal from the local process boundary. Streamable HTTP is loopback-only and requires a bounded Bearer token plus a server-configured principal before an MCP request reaches the SDK application. Health endpoints intentionally remain outside that authentication boundary. The model cannot supply the principal or enable writes.

Mutations additionally require the process-level `ENABLE_WRITE_OPERATIONS` gate. The current server has no independent approval authority, therefore governed manifests deliberately set `requires_confirmation=false`. If confirmation is introduced later, the kernel already fails closed for any manifest that requests it until a trusted server-side approval record can be verified.

## Deadlines, cancellation, and concurrency

There is no worker pool or executor queue. The kernel limits total admitted invocations and separately limits operations actively running against the dependency. Calls above the admission bound fail before execution. `concurrent_safe=false` operations are serialized by `target_scope`, currently `kontomierz-account`.

Cancellation propagates through the async operation into `httpx`. If a write has started, a kernel deadline, transport loss, timeout, response loss, or ambiguous 5xx becomes `AMBIGUOUS_OUTCOME` with `retryable=false`. Callers reconcile state before any retry. The runtime performs no automatic retries.

## Health behavior

Liveness proves the ASGI process responds. Readiness requires the full operation catalog and a bounded, cached probe of the mandatory Kontomierz dependency. Failed credentials, an unavailable backend, a probe timeout, shutdown, or an incomplete registry returns not-ready.

## Failure modes

- Invalid input, unauthenticated HTTP requests, disabled writes, and admission rejection stop before dependency I/O.
- Authentication, authorization, not-found, conflict, rate-limit, timeout, dependency, and malformed-response failures retain distinct codes.
- Tool errors are explicit MCP `CallToolResult` documents with stable structured JSON.
- Unexpected exceptions are logged with a request ID and exposed only as sanitized internal errors.

## Non-goals

This revision does not provide public multi-tenant hosting, OAuth, per-resource authorization beyond the single configured Kontomierz target, durable background work, or a compatibility REST API.
