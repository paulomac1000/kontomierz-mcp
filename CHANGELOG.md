# Changelog

All notable changes to kontomierz-mcp are recorded here.

## 1.1.0 — Unreleased

### Changed

- Replaced legacy HTTP+SSE and the unauthenticated REST bridge with stdio and loopback-only Streamable HTTP.
- Added immutable startup configuration, one invocation kernel, explicit per-tool safety manifests, typed upstream failures, bounded deadlines, and conservative retry semantics.
- Changed public dates to ISO `YYYY-MM-DD` while keeping legacy conversion inside the upstream adapter.
- Corrected update operations to use the documented HTTP `PUT` method.
- Reworked pagination so a non-empty page no longer automatically claims that another page exists.
- Replaced global clients, private FastMCP internals, daemon listener threads, and raw-function fallbacks.

### Added

- Deterministic in-memory backend and all-tool mock smoke.
- Official MCP SDK in-memory, stdio, and Streamable HTTP contract tests.
- Exact-wheel and same-wheelhouse container promotion workflow.
- AFDS architecture, tool contract, upstream contract, and standards gap documents.
- Root `AGENTS.md` with safe operating modes and completion gates.

### Security

- Public network binding now fails closed instead of treating an acknowledgement variable as authentication.
- Financial reads are classified as confidential; every mutation requires the trusted operator write gate.
- Write timeouts return an ambiguous outcome and are not automatically retryable.

## 1.0.1 — 2026-07-07

- Changed write request bodies from implicit form encoding to explicit JSON pending real-system contract verification.

## 1.0.0 — 2026-06-01

- Initial MCP server release.
