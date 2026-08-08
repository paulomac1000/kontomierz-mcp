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
- Streamable HTTP authorization is read-only by default; write/destructive capability classes require explicit server-side opt-in in addition to the operator write gate.
- Streamable HTTP readiness now requires Bearer authentication because a readiness cache miss may perform upstream network I/O; `/health/live` remains public.

### Added

- One governed catalog for tool signatures, descriptions, schemas, versions, manifests, active state, and registration.
- Complete multi-axis capability manifests and supported-versus-active capability discovery.
- Explicit application-owned authorization binding principal, exact capability, immutable configured target, exact resource identity, and normalized arguments, with pre-I/O revalidation.
- Narrow remote destructive authorization with explicit capability and exact-resource allowlists; broad `destructive` class access alone is rejected.
- One structured server-side audit event per invocation with principal, policy decision, target, resource identity, result category, and correlation data without credentials or protected response bodies.
- An audit-only INFO sink independent from ordinary `LOG_LEVEL`, with result-preserving fail-open behavior on sink failure.
- Intentional Streamable HTTP Host/Origin policy, stateless mode, bounded request bodies, authenticated readiness, and adversarial pre-I/O tests.
- Bounded admission, running concurrency, per-target write serialization, dependency-aware readiness, and conservative ambiguous-write handling.
- Deterministic mock backend, all-tool smoke, official-client tests, and intentionally failing external evidence placeholders for real-system and provider-only acceptance work.
- Exact Linux x64 runtime/development wheel locks for Python 3.11, 3.12, and 3.13 plus a separate build-tool lock; acceptance installs use exact SHA-256 wheel hashes without dependency resolution.
- Exact-wheel and exact-image CI promotion, locked runtime wheelhouse, protected release environment, default-branch ancestry proof, registry digest comparison, and promotion attestation.
- AFDS architecture, contract, upstream, migration, production-readiness, and standards-gap documentation plus root `AGENTS.md`.

### Security

- Non-loopback HTTP binding remains forbidden; loopback HTTP requires request-scoped Bearer authentication and explicit server-side capability/target/resource authorization.
- Financial reads are classified as confidential; every mutation requires the trusted operator write gate and HTTP writes require an independently allowed capability class.
- HTTP destructive operations require both an explicitly allowlisted capability ID and the exact resource identity; wildcard resource grants are not accepted.
- Missing or invalid credentials, Host/Origin policy violations, oversized HTTP bodies, and unauthenticated readiness requests are rejected before operation/dependency I/O.
- Any uninterpretable successful response to a mutation is treated as a potentially completed write.
- No mutation is declared replay-safe or automatically retryable without real-system evidence.

## 1.0.1 — 2026-07-07

- Changed write request bodies from implicit form encoding to explicit JSON pending real-system contract verification.

## 1.0.0 — 2026-06-01

- Initial MCP server release.
