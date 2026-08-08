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
  -> target/resource/policy revalidation immediately before I/O
  -> domain validation and asynchronous KontomierzPort
  -> HTTP adapter or deterministic mock backend
```

No transport invokes an operation or dependency directly.

## Component ownership

`Settings` is created before dependencies. `security.py` owns process-derived stdio identity and the Streamable HTTP Bearer boundary. `authorization.py` owns the server-side principal/capability/target/resource policy and exact pre-I/O revalidation. `audit.py` owns bounded structured invocation records and its independent audit-only sink. `InvocationKernel` owns enforcement order, bounded admission, running concurrency, per-target serialization, deadlines, readiness state, and dependency lifetime. `KontomierzClient` owns one cancellation-aware `httpx.AsyncClient`. The governed catalog owns every public signature, description, manifest, version, and discovery expectation. The SDK server projects that catalog into protocol registration and owns lifecycle entry.

## Security boundary

Stdio is the safe default and derives a principal from the local process boundary. Streamable HTTP is loopback-only and requires a bounded Bearer token plus a server-configured principal before a remote request reaches MCP or readiness behavior. `/health/live` is the only public HTTP route and performs no dependency I/O. A direct HTTP-kernel invocation without request-scoped authentication fails closed. The model cannot supply the principal, target, capability policy, resource allowlist, or write-enable gate.

Authentication is not authorization. The application authorizes every invocation against the exact capability ID, its capability class, the immutable configured deployment target, an explicit primary resource identity, and a digest of normalized arguments. Existing resources are bound as stable identities such as `wallet:123`, `transaction:456`, `budget:789`, or `schedule:321`; create and collection operations receive bounded namespace identities, and transaction creation additionally binds a digest of `client_assigned_id` when present. The same authorization binding is revalidated inside the execution slot immediately before operation I/O.

HTTP defaults to `read` only. Ordinary `write` requires explicit class policy plus the process-level `ENABLE_WRITE_OPERATIONS` gate. Remote `destructive` access is narrower: enabling the class is insufficient unless the exact capability ID is present in `MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES` and the exact resource identity is present in `MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES`. Wildcard destructive resources are not supported.

The current server has no independent approval authority, therefore governed manifests deliberately set `requires_confirmation=false`. If confirmation is introduced later, the kernel fails closed for any manifest that requests it until a trusted server-side approval record can be verified.

Streamable HTTP explicitly configures the SDK transport security policy: intentional loopback Host values, same-loopback HTTP Origins, stateless mode, JSON request content, and `MCP_HTTP_MAX_REQUEST_BODY_BYTES` (1 MiB by default, 4 MiB hard maximum). Adversarial integration tests assert Host, Origin, credential, oversized-body, and readiness-authentication rejection before kernel or dependency I/O.

## Audit and observability

Every tool invocation emits one JSON audit event through the `kontomierz_mcp.audit` channel. That logger owns an INFO-capable handler and does not inherit application `LOG_LEVEL`, so raising ordinary verbosity to `WARNING`, `ERROR`, or `CRITICAL` does not suppress invocation audit events. The event records correlation/request ID, process- or request-derived principal, transport, exact capability ID/class, target identity, resource identity, normalized-argument digest, authorization and operator-gate decisions, dependency state, result category, duration, cancellation, saturation, and ambiguous-write state. API keys, Bearer tokens, model-visible protected data, and raw upstream response bodies are never included. Principal identity stays server-side and is not echoed in tool `_meta`.

Audit emission uses a result-preserving fail-open policy. This is intentional because the event is emitted after invocation outcome is known; turning a successfully completed mutation into an application error because the audit sink failed could cause a dangerous retry or false ambiguity. A minimal `mcp_audit_emission_failure` signal is attempted on stderr when logger emission itself raises.

## Deadlines, cancellation, and concurrency

There is no worker pool or executor queue. The kernel limits total admitted invocations and separately limits operations actively running against the dependency. Calls above the admission bound fail before execution. `concurrent_safe=false` operations are serialized by `target_scope`, currently `kontomierz-account`.

Cancellation propagates through the async operation into `httpx`. If a write has started, a kernel deadline, transport loss, timeout, response loss, or ambiguous 5xx becomes `AMBIGUOUS_OUTCOME` with `retryable=false`. Callers reconcile state before any retry. The runtime performs no automatic retries.

## Health behavior

Liveness proves the ASGI process responds and is public because it performs no dependency work. Readiness requires Bearer authentication on Streamable HTTP, then checks the full operation catalog and a bounded, cached probe of the mandatory Kontomierz dependency. An unauthenticated `/health/ready` request returns 401 before `InvocationKernel.readiness()` and therefore cannot cause upstream network I/O. Failed credentials, an unavailable backend, a probe timeout, shutdown, or an incomplete registry returns not-ready to an authenticated readiness caller.

## Failure modes

- Invalid input, unauthenticated requests, unauthorized capabilities/resources, disabled writes, and admission rejection stop before dependency I/O.
- Authentication, authorization, not-found, conflict, rate-limit, timeout, dependency, and malformed-response failures retain distinct codes.
- Tool errors are explicit MCP `CallToolResult` documents with stable structured JSON.
- Unexpected exceptions are correlated in server logs and exposed only as sanitized internal errors.

## Non-goals

This revision does not provide public multi-tenant hosting, OAuth, cross-account target selection, durable background work, or a compatibility REST API. Resource authorization is explicit within the one immutable configured Kontomierz credential scope; multi-tenant resource isolation remains out of scope.
