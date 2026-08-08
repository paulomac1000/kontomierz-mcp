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
  -> explicit application authorization policy
  -> official MCP SDK registration
  -> InvocationKernel
  -> target/policy revalidation immediately before I/O
  -> domain validation and asynchronous KontomierzPort
  -> HTTP adapter or deterministic mock backend
```

No transport invokes an operation or dependency directly.

## Component ownership

`Settings` is created before dependencies. `security.py` owns process-derived stdio identity and the Streamable HTTP Bearer boundary. `authorization.py` owns the server-side principal/capability/target policy and exact pre-I/O revalidation. `audit.py` owns bounded structured invocation records. `InvocationKernel` owns enforcement order, bounded admission, running concurrency, per-target serialization, deadlines, readiness state, and dependency lifetime. `KontomierzClient` owns one cancellation-aware `httpx.AsyncClient`. The governed catalog owns every public signature, description, manifest, version, and discovery expectation. The SDK server projects that catalog into protocol registration and owns lifecycle entry.

## Security boundary

Stdio is the safe default and derives a principal from the local process boundary. Streamable HTTP is loopback-only and requires a bounded Bearer token plus a server-configured principal before an MCP request reaches the SDK application. A direct HTTP-kernel invocation without request-scoped authentication fails closed. Health endpoints intentionally remain outside the authentication boundary. The model cannot supply the principal, target, capability policy, or write-enable gate.

Authentication is not authorization. The application authorizes every invocation against the exact capability ID, its capability class, the immutable configured deployment target, and a digest of normalized arguments. HTTP defaults to `read` only; `write` and `destructive` are separate explicit server-owned capability classes. The same authorization binding is revalidated inside the execution slot immediately before operation I/O. Mutations additionally require the process-level `ENABLE_WRITE_OPERATIONS` gate.

The current server has no independent approval authority, therefore governed manifests deliberately set `requires_confirmation=false`. If confirmation is introduced later, the kernel fails closed for any manifest that requests it until a trusted server-side approval record can be verified.

Streamable HTTP explicitly configures the SDK transport security policy: intentional loopback Host values, same-loopback HTTP Origins, stateless mode, JSON request content, and `MCP_HTTP_MAX_REQUEST_BODY_BYTES` (1 MiB by default, 4 MiB hard maximum). Adversarial integration tests assert Host, Origin, credential, and oversized-body rejection before kernel I/O.

## Audit and observability

Every tool invocation emits one JSON audit event to the `kontomierz_mcp.audit` logger. The event records correlation/request ID, process- or request-derived principal, transport, exact capability ID/class, target identity, normalized-argument digest, authorization and operator-gate decisions, dependency state, result category, duration, cancellation, saturation, and ambiguous-write state. API keys, Bearer tokens, model-visible protected data, and raw upstream response bodies are never included. Principal identity stays server-side and is not echoed in tool `_meta`.

## Deadlines, cancellation, and concurrency

There is no worker pool or executor queue. The kernel limits total admitted invocations and separately limits operations actively running against the dependency. Calls above the admission bound fail before execution. `concurrent_safe=false` operations are serialized by `target_scope`, currently `kontomierz-account`.

Cancellation propagates through the async operation into `httpx`. If a write has started, a kernel deadline, transport loss, timeout, response loss, or ambiguous 5xx becomes `AMBIGUOUS_OUTCOME` with `retryable=false`. Callers reconcile state before any retry. The runtime performs no automatic retries.

## Health behavior

Liveness proves the ASGI process responds. Readiness requires the full operation catalog and a bounded, cached probe of the mandatory Kontomierz dependency. Failed credentials, an unavailable backend, a probe timeout, shutdown, or an incomplete registry returns not-ready.

## Failure modes

- Invalid input, unauthenticated requests, unauthorized capabilities, disabled writes, and admission rejection stop before dependency I/O.
- Authentication, authorization, not-found, conflict, rate-limit, timeout, dependency, and malformed-response failures retain distinct codes.
- Tool errors are explicit MCP `CallToolResult` documents with stable structured JSON.
- Unexpected exceptions are correlated in server logs and exposed only as sanitized internal errors.

## Non-goals

This revision does not provide public multi-tenant hosting, OAuth, per-resource authorization beyond the single configured Kontomierz target, durable background work, or a compatibility REST API.
