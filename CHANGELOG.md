# Changelog

All notable changes to kontomierz-mcp are recorded here.

## 2.0.0 — Unreleased

### Breaking changes

- Replaced legacy HTTP+SSE and the unauthenticated REST bridge with stdio and loopback-only Streamable HTTP.
- Changed public dates to ISO `YYYY-MM-DD` and budget months to `YYYY-MM`, while retaining localized upstream conversion internally; legacy `DD-MM-YYYY` public inputs are rejected.
- Replaced pagination certainty fields with `may_have_more` and `next_page_hint` because the upstream continuation contract is unverified.
- Replaced SDK-generated exception text with explicit structured MCP error results.
- Changed update inputs so `None` means omission and an empty string can intentionally clear supported text fields.
- Replaced the synchronous dependency adapter with native asynchronous I/O.
- Streamable HTTP authorization is read-only by default; write/destructive capability classes require explicit server-side opt-in in addition to the operator write gate.
- Destructive stdio operations now require exact server-owned capability and resource allowlists in addition to the operator write gate.
- Streamable HTTP readiness now requires Bearer authentication because a readiness cache miss may perform upstream network I/O; `/health/live` remains public.
- Successful response metadata now reports `target_scope` plus an opaque `target_ref` instead of the internal authorization target identity.
- Production package metadata pins the tested MCP SDK lane to `mcp==2.0.0` instead of claiming unverified compatibility with all future 2.x releases.

### Fixed

- Write bodies use `application/x-www-form-urlencoded` encoding, matching the live Kontomierz API contract verified on 2026-08-08. JSON-encoded write bodies are rejected by the upstream, so real-backend configuration now rejects `KONTOMIERZ_BODY_MODE=json` instead of preserving a known-broken compatibility mode.
- Plain `pytest` excludes `external` tests by default. Live-account evidence additionally requires both `KONTOMIERZ_EXTERNAL_TESTS=1` and `KONTOMIERZ_ALLOW_REAL_MUTATIONS=1` before it can read credentials or mutate the real service.
- Live schedule, transaction, and budget evidence cleanup now uses captured IDs plus reconciliation fallbacks so failures between a successful create and normal ID discovery do not silently orphan test data.
- Empty-body success responses from schedule/budget create and update are no longer reported as ambiguous failures. The adapter reconciles by listing (schedule by description, budget by category/group) to return the created identity, falling back to a success marker when the record is not yet visible.
- Wealth points are unwrapped from their verified per-item `{"wealth_point": {...}}` upstream shape.
- Restored the full `repeat` (1=once … 6=biennial) and `holidays` (0/1/2) parameter descriptions for `create_schedule`/`update_schedule`; a regression test now locks the agent-facing ergonomics.
- Streamable HTTP smoke allows up to 60 seconds for server readiness on slow or heavily loaded machines.

### Changed

- Mock backend response shapes mirror the verified real API (account wrappers and fields, `schedule_id`-based schedule list items, budget `kind`/`name`/`amount`, tags without ids, `category_groups`, per-item wealth wrappers, realistic currencies).
- The real upstream write/date/pagination contract is documented in `docs/upstream-api.md` with live-account evidence from 2026-08-08.
- Standards CI is repinned to the reviewed `ai-skills` `fix/unified-contract-release-hardening` head used for this revision.

### Added

- One governed catalog for tool signatures, descriptions, schemas, versions, manifests, active state, and registration.
- Complete multi-axis capability manifests and supported-versus-active capability discovery.
- Explicit application-owned authorization binding principal, exact capability, immutable configured target, exact resource identity, and normalized arguments, with pre-I/O revalidation.
- Narrow destructive authorization on both transports with explicit capability and exact-resource allowlists; broad class access or the operator write gate alone is insufficient.
- One structured server-side audit event per invocation with principal, policy decision, target, resource identity, result category, and correlation data without credentials or protected response bodies.
- An audit-only INFO sink independent from ordinary `LOG_LEVEL`, with result-preserving fail-open behavior on sink failure.
- Intentional Streamable HTTP Host/Origin policy, stateless mode, bounded request bodies, authenticated readiness, and adversarial pre-I/O tests.
- Bounded admission, running concurrency, per-target write serialization, dependency-aware readiness, and conservative ambiguous-write handling.
- Deterministic mock backend, all-tool smoke, official-client tests, and intentionally failing external evidence placeholders for provider-only acceptance work.
- Exact Linux x64 runtime/development wheel locks for Python 3.11, 3.12, and 3.13 plus a separate build-tool lock; acceptance installs use exact SHA-256 wheel hashes without dependency resolution.
- Exact-wheel and exact-image CI promotion, locked runtime wheelhouse, protected release environment, default-branch ancestry proof, registry digest comparison, and promotion attestation.
- AFDS architecture, contract, upstream, migration, production-readiness, and standards-gap documentation plus root `AGENTS.md`.
- Real external evidence tests (`tests/external/test_real_kontomierz_contract.py`) proving read shapes, schedule/transaction/budget write round trips with cleanup, pagination ordering and termination, money precision normalization, ISO-date rejection, and form-encoding requirements against the live account.

### Security

- No control was weakened: form-encoding verification confirms the historical form-based contract; ambiguous-write handling still applies to timeout, transport loss, and malformed success responses.
- Non-loopback HTTP binding remains forbidden; loopback HTTP requires request-scoped Bearer authentication and explicit server-side capability/target/resource authorization.
- Financial reads are classified as confidential; every mutation requires the trusted operator write gate and HTTP writes require an independently allowed capability class.
- Destructive operations require an explicitly allowlisted capability ID and exact resource identity on both stdio and HTTP; wildcard resource grants are not accepted.
- Missing or invalid credentials, Host/Origin policy violations, oversized HTTP bodies, and unauthenticated readiness requests are rejected before operation/dependency I/O.
- Any uninterpretable successful response to a mutation is treated as a potentially completed write.
- No mutation is declared replay-safe or automatically retryable without real-system evidence.

## 1.0.1 — 2026-07-07

- Changed write request bodies from implicit form encoding to explicit JSON pending real-system contract verification.

## 1.0.0 — 2026-06-01

- Initial MCP server release.
