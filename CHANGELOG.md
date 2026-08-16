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

- Official MCP tool inputs now use strict scalar validation and closed object schemas: numeric strings/booleans are not coerced, undeclared arguments are rejected before SDK normalization can drop them, explicit zero is rejected for optional positive IDs, and invalid falsey optional create values are not silently omitted.
- Write bodies use `application/x-www-form-urlencoded`, matching the live Kontomierz API contract verified on 2026-08-08; known-broken JSON write mode is rejected for the real backend.
- Plain `pytest` excludes `external` tests by default. Live-account mutation evidence requires both explicit mutation opt-ins plus `KONTOMIERZ_EXCLUSIVE_DISPOSABLE_ACCOUNT=1` and an expected `KONTOMIERZ_DISPOSABLE_WALLET_ID` that is verified against the authenticated account before cleanup or mutation.
- Live cleanup traverses paid and unpaid schedule groups, reconciles the unique test namespace and budget snapshot only inside the verified exclusive disposable account, verifies deletion, and fails instead of swallowing unconfirmed cleanup.
- Empty-body create success never guesses a stable ID from non-unique descriptions/categories and is surfaced as a non-retryable ambiguous outcome that requires reconciliation.
- Upstream redirects are rejected explicitly; redirects observed after a mutation request are treated as potentially ambiguous rather than successful.
- Readiness uses an explicit never-checked sentinel rather than a numeric monotonic-time sentinel, so a process started near a monotonic epoch cannot cache a false initial state.
- Audit events enforce closed categorical values, field-specific safe identities/digests, 256-byte free-form field bounds, and a hard 8 KiB serialized-event ceiling; short protected values are never emitted verbatim.
- Decimal inputs are bounded before fixed-point formatting so scientific notation cannot expand into an unbounded request value.
- HTTP application lifespan owns and closes the shared kernel exactly once.
- Wealth points are unwrapped from their verified per-item `{"wealth_point": {...}}` upstream shape.
- Restored full schedule `repeat`/`holidays` descriptions and locked them with regression tests.
- Streamable HTTP smoke allows slow startup without weakening its bounded timeout.
- Composition validates frozen settings before constructing a real dependency client; unsafe base URLs fail before dependency creation.
- Logging tests restore global logger state and real request diagnostics stay at WARNING+ to protect the query-string API key.
- Mock transaction contract tests call the synchronous mock API synchronously.
- Exact-artifact Docker source-label verification uses a valid Docker Go-template expression.
- ID-bound capabilities reject missing, boolean, floating-point, zero, negative, or string identifiers before authorization can claim an exact resource binding.
- Mock schedule pagination rejects floating-point page/per-page values instead of silently truncating them with `int()`.
- MCP public-contract evidence is generated from the same exact wheel that is tested, smoke-tested, image-bundled, and released; the snapshot is no longer produced from a separately rebuilt wheel with a different digest.

### Changed

- Mock backend response shapes mirror verified real API shapes rather than convenient synthetic substitutes.
- The real upstream write/date/pagination contract is documented in `docs/upstream-api.md` and machine-readable `upstream-contract.yaml` with live-account evidence from 2026-08-08.
- Candidate-owned structural standards CI declares its immutable `ai-skills` executable provenance in `trusted-executable-sources.lock.yaml`; `mcp-server-architect` 1.3.0 governs this migration and the lock contains the reviewed exact revision plus SHA-256 bindings for the trusted entrypoints it executes. Provider-backed acceptance remains externally anchored and does not trust the candidate lock as its root of authority.
- Standards CI validates the canonical trust lock and runs consumer-trust hygiene, repository discovery, upstream/live-backend contracts, AFDS, AGENTS, and workflow-policy checks from the trusted checkout.
- Release promotion is split into read-only artifact verification, unprivileged isolated-registry quarantine/smoke, and protected registry-to-registry production promotion. The privileged publisher never loads or executes candidate content.

### Added

- One governed catalog for tool signatures, descriptions, schemas, versions, manifests, active state, and registration.
- Complete multi-axis capability manifests and supported-versus-active capability discovery.
- Explicit application-owned authorization binding principal, exact capability, immutable target, exact resource identity, and normalized arguments, with pre-I/O revalidation.
- Narrow destructive authorization on both transports with explicit capability and exact-resource allowlists.
- One structured server-side audit event per invocation without credentials or protected result bodies.
- Intentional Streamable HTTP Host/Origin policy, stateless mode, bounded request bodies, authenticated readiness, and adversarial pre-I/O tests.
- Bounded admission/concurrency, per-target write serialization, dependency-aware readiness, response-size enforcement, and conservative ambiguous-write handling.
- Exact Linux x64 runtime/development wheel locks for Python 3.11–3.13 and separate build-tool lock; acceptance installs use exact SHA-256 wheel hashes without dependency resolution.
- Exact-wheel and exact-image CI artifact path with source-revision OCI label, non-root smoke, checksummed closed bundle, protected promotion attestation, and a trusted MCP public-contract snapshot captured from that same wheel and included in the release checksum closure.
- Real external evidence tests plus `live-backend-test-policy.yaml` and `upstream-contract.yaml`.
- `trusted-executable-sources.lock.yaml` as the canonical candidate-side executable-provenance declaration, with provider-backed acceptance required to compare it against authority coordinates supplied outside the candidate repository.
- Structural tests proving the privileged publisher cannot checkout/download/load/run candidate content and the quarantine lane remains unprivileged to production.

### Security

- Non-loopback HTTP binding remains forbidden; loopback HTTP requires request-scoped Bearer authentication and explicit server-side capability/target/resource authorization.
- Financial reads are confidential; every mutation requires the trusted operator write gate and HTTP writes require an independently allowed capability class.
- Destructive operations require an explicitly allowlisted capability ID and exact resource identity on both stdio and HTTP; wildcard resources are rejected.
- Missing/invalid credentials, Host/Origin violations, oversized HTTP bodies, and unauthenticated readiness requests stop before operation/dependency I/O.
- Any uninterpretable successful mutation response is treated as potentially completed; no mutation is declared replay-safe or automatically retryable without evidence.
- Quarantine credentials are separated from production coordinates in workflow design. Provider-backed proof that their actual configured scope cannot mutate production remains an external administrative evidence gate.

## 1.0.1 — 2026-07-07

- Changed write request bodies from implicit form encoding to explicit JSON pending real-system contract verification.

## 1.0.0 — 2026-06-01

- Initial MCP server release.
