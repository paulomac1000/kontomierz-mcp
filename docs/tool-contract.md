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

Stable positive numeric IDs returned by list tools are accepted by detail and mutation tools. Money is a finite decimal string plus a three-letter currency. The server preserves the caller's finite decimal value without rounding or imposing a fixed scale; the upstream remains responsible for any accepted precision limit. Wallet balances may be zero or negative because the upstream contract has not established a positive-only restriction. Public dates use `YYYY-MM-DD`; months use `YYYY-MM`.

For update tools, `None` means not provided. An empty string is an explicit request to clear a text field where the upstream accepts it.

## Outputs

Successful tools return structured content with `data` and `_meta`. Metadata contains a request ID, duration, tool version, target scope, and authenticated transport class. Empty lists are successful results. Principal identifiers and authorization-policy internals are intentionally not echoed in tool output; the detailed decision is retained only in the server audit event.

## Errors

Tool failures return an explicit MCP `CallToolResult` with `is_error=true`, controlled text JSON, and `structured_content.error`. The error contains `code`, `message`, `retryable`, and optional `suggestion` or bounded details. SDK-added exception prefixes are not part of the contract.

## Safety, authorization, and retry

Each tool has one complete governed manifest containing risk, side effects, confidentiality, idempotency mechanism, retry conditions, concurrency scope, confirmation requirement, determinism, latency, cost, impact, reversibility, target binding, and active state. Authentication alone never grants tool access. The application policy binds a principal to the exact capability ID, capability class, immutable configured target, and normalized-argument digest, then revalidates that binding immediately before I/O.

HTTP principals are authorized for `read` by default. `write` and `destructive` are separate opt-in capability classes controlled by `MCP_HTTP_ALLOWED_CAPABILITIES`. Mutations additionally require the independent operator gate. `concurrent_safe=false` is enforced per target. `automatic_retry=false` for every tool because the runtime has no retry loop.

`requires_confirmation` is currently false for every mutation because no independent approval authority exists. This is intentional: the server does not claim a control it cannot verify. The kernel fails closed if a future manifest sets it true before a trusted approval-record verifier is installed.

A transient read error may be marked retryable for a caller-controlled retry. A write rejected before admission has not started. A started write with an ambiguous dependency outcome returns `AMBIGUOUS_OUTCOME`, `retryable=false`, and a reconciliation suggestion.

## Transport identity and HTTP policy

Stdio uses a process-derived local principal. Streamable HTTP requires a server-owned Bearer token and principal mapping; authentication occurs before MCP request handling. Neither the write gate, HTTP principal, capability allowlist, target identity, nor any future approval record may be supplied as a tool argument.

Streamable HTTP is stateless and loopback-only. The application intentionally supplies Host and Origin allowlists to the official SDK and bounds the request body with `MCP_HTTP_MAX_REQUEST_BODY_BYTES`. Missing, duplicate, malformed, oversized, or incorrect Bearer credentials fail before tool dispatch. Invalid Host, cross-origin Origin, and oversized bodies are also rejected before operation I/O.

## Audit contract

Each invocation creates exactly one bounded structured server-side audit event. It contains request ID, principal, transport, exact capability, target identity, argument digest, authorization decision, operator-gate decision, dependency state, result category, duration, and cancellation/saturation/ambiguous flags. Credentials, raw arguments, protected result bodies, and raw upstream bodies are excluded.

## Pagination

The upstream has not provided a reliable total or continuation token. Results expose `items_in_page`, `may_have_more`, and `next_page_hint`. A full page is only a hint and never a claim that a next page exists.

## Versioning and compatibility

These changes are released as `2.0.0` because this revision removes legacy SSE and the REST bridge, uses ISO public dates, switches the HTTP adapter to native async I/O, and makes clearing versus omission explicit.
