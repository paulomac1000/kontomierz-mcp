---
description: Defines public tool inputs, outputs, safety metadata, errors, retries, dates, money, and pagination.
doc_id: contract.kontomierz-tools
type: contract
status: evolving
rigor: normative
owners: [repository-maintainers]
verification: Run the manifest, operation, kernel, client, security, and MCP SDK contract tests.
---
# Kontomierz tool contract

## Inputs

Stable positive numeric IDs returned by list tools are accepted by detail and mutation tools. Money is a finite decimal string plus a three-letter currency. The server preserves the caller's finite decimal value without rounding or imposing a fixed scale; the upstream remains responsible for any accepted precision limit. Wallet balances may be zero or negative because the upstream contract has not established a positive-only restriction. Public dates accept only `YYYY-MM-DD`; months accept only `YYYY-MM`. Legacy `DD-MM-YYYY` values are rejected at the public operation boundary and are produced only internally for the localized upstream contract.

For update tools, `None` means not provided. An empty string is an explicit request to clear a text field where the upstream accepts it.

## Outputs

Successful tools return structured content with `data` and `_meta`. Metadata contains a request ID, duration, tool version, target scope, opaque `target_ref`, and authenticated transport class. `target_ref` is stable for the configured authorization target without exposing the internal credential-derived target identity. Empty lists are successful results. Principal identifiers, exact resource authorization, and authorization-policy internals are intentionally not echoed in tool output; the detailed decision is retained only in the server audit event.

When Kontomierz confirms a create with an empty body and therefore supplies no stable identity, the adapter returns `{"created": true, "reconciliation_required": true}`. It does not guess a resource ID by matching non-unique descriptions, categories, or other attributes after the write. The caller must use the corresponding list tool to reconcile state before any dependent mutation or retry.

## Errors

Tool failures return an explicit MCP `CallToolResult` with `is_error=true`, controlled text JSON, and `structured_content.error`. The error contains `code`, `message`, `retryable`, and optional `suggestion` or bounded details. SDK-added exception prefixes are not part of the contract.

## Safety, authorization, and retry

Each tool has one complete governed manifest containing risk, side effects, confidentiality, idempotency mechanism, retry conditions, concurrency scope, confirmation requirement, determinism, latency, cost, impact, reversibility, target binding, and active state. Authentication alone never grants tool access. The application policy binds a principal to the exact capability ID, capability class, immutable configured target, resolved resource identity, and normalized-argument digest, then revalidates that binding immediately before I/O.

Existing resource mutations bind stable identities such as `wallet:123`, `transaction:456`, `budget:789`, and `schedule:321`. Create operations use bounded `*:new` identities; `create_transaction` additionally binds a SHA-256-derived correlation identity when `client_assigned_id` is present. List and aggregate tools authorize explicit collection/namespace resources rather than relying on the argument digest as a substitute for resource identity.

Stdio destructive operations require both `MCP_STDIO_ALLOWED_DESTRUCTIVE_CAPABILITIES` and `MCP_STDIO_ALLOWED_DESTRUCTIVE_RESOURCES`; the global write gate alone is insufficient. HTTP principals are authorized for `read` by default. `write` and `destructive` are separate opt-in capability classes controlled by `MCP_HTTP_ALLOWED_CAPABILITIES`. HTTP destructive operations require an additional narrow capability ID allowlist and exact resource allowlist; enabling the broad `destructive` class without both lists is invalid configuration. Mutations on either transport additionally require the independent operator gate. `concurrent_safe=false` is enforced per target. `automatic_retry=false` for every tool because the runtime has no retry loop.

`requires_confirmation` is currently false for every mutation because no independent approval authority exists. This is intentional: the server does not claim a control it cannot verify. The kernel fails closed if a future manifest sets it true before a trusted approval-record verifier is installed.

A transient read error may be marked retryable for a caller-controlled retry. A write rejected before admission has not started. A started write with an ambiguous dependency outcome returns `AMBIGUOUS_OUTCOME`, `retryable=false`, and a reconciliation suggestion. If the invocation itself is cancelled after a mutation operation has started, cancellation still propagates, but the server-side audit event marks the outcome ambiguous so operators do not mistake cancellation for proof that the mutation did not happen.

## Transport identity and HTTP policy

Stdio uses a process-derived local principal. Streamable HTTP requires a server-owned Bearer token and principal mapping. Both values are bounded visible ASCII and are validated without silently trimming process-environment credentials. Authentication occurs before MCP handling and before any readiness request that may trigger dependency network I/O. `/health/live` is the only public HTTP route and performs no dependency call. Neither the write gate, principal, capability allowlist, destructive resource allowlist, target identity, nor any future approval record may be supplied as a tool argument.

Streamable HTTP is stateless and loopback-only. The application intentionally supplies Host and Origin allowlists to the official SDK and bounds the request body with `MCP_HTTP_MAX_REQUEST_BODY_BYTES`. Missing, duplicate, malformed, oversized, or incorrect Bearer credentials fail before tool dispatch. Invalid Host, cross-origin Origin, oversized bodies, and unauthenticated `/health/ready` requests are also rejected before operation/dependency I/O.

Because the legacy Kontomierz API requires `api_key` in the query string, application logging explicitly keeps `httpx` and `httpcore` below request-level INFO/DEBUG diagnostics even when `LOG_LEVEL=DEBUG`. This prevents dependency request logs from exposing the credential-bearing URL.

## Audit contract

Each invocation creates exactly one bounded structured server-side audit event. It contains request ID, principal, transport, exact capability, target identity, resource identity, argument digest, authorization decision, operator-gate decision, dependency state, result category, duration, and cancellation/saturation/ambiguous flags. Credentials, raw arguments, protected result bodies, and raw upstream bodies are excluded.

The audit logger owns an INFO-capable handler and does not inherit the ordinary application `LOG_LEVEL`, so `LOG_LEVEL=WARNING` or stricter does not suppress invocation audit records. Audit emission is result-preserving fail-open: a logger failure after operation I/O must not transform a completed mutation into an application error that could trigger a dangerous retry. A bounded stderr failure signal is attempted when audit emission itself raises.

## Pagination

The upstream has not provided a reliable total or continuation token. Results expose `items_in_page`, `may_have_more`, and `next_page_hint`. A full page is only a hint and never a claim that a next page exists.

## Versioning and compatibility

These breaking changes are released as `2.0.0` because this revision removes legacy SSE and the REST bridge, changes public date, response metadata, pagination, and update semantics, switches the HTTP adapter to native async I/O, and strengthens destructive authorization. The 1.x contract is not claimed to remain compatible.
