# Changelog

All notable changes to kontomierz-mcp are recorded here.

## 2.0.0 — Unreleased

### Breaking changes

- Replaced legacy HTTP+SSE and the unauthenticated REST bridge with stdio and loopback-only Streamable HTTP.
- Changed public dates to ISO `YYYY-MM-DD` while retaining upstream conversion internally.
- Replaced pagination certainty fields with `may_have_more` and `next_page_hint` because the upstream continuation contract is unverified.
- Replaced SDK-generated exception text with explicit structured MCP error results.
- Changed update inputs so `None` means omission and an empty string can intentionally clear supported text fields.
- Replaced the synchronous dependency adapter with native asynchronous I/O.

### Added

- One governed catalog for tool signatures, descriptions, schemas, versions, manifests, active state, and registration.
- Complete multi-axis capability manifests and supported-versus-active capability discovery.
- Bounded admission, running concurrency, per-target write serialization, dependency-aware readiness, and conservative ambiguous-write handling.
- Deterministic mock backend, all-tool smoke, official-client test scaffolding, and explicit real-system TODOs.
- Exact-wheel and exact-image CI promotion, protected release environment, registry digest comparison, and promotion attestation.
- AFDS architecture, contract, upstream, migration, and standards-gap documentation plus root `AGENTS.md`.

### Security

- Public network binding fails closed until principal authentication and resource authorization exist.
- Financial reads are classified as confidential; every mutation requires the trusted operator write gate.
- Any uninterpretable successful response to a mutation is treated as a potentially completed write.
- No mutation is declared replay-safe or automatically retryable without real-system evidence.

## 1.0.1 — 2026-07-07

- Changed write request bodies from implicit form encoding to explicit JSON pending real-system contract verification.

## 1.0.0 — 2026-06-01

- Initial MCP server release.
