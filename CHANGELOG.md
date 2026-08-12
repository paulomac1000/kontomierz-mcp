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

- Write bodies use `application/x-www-form-urlencoded`, matching the live Kontomierz API contract verified on 2026-08-08; known-broken JSON write mode is rejected for the real backend.
- Plain `pytest` excludes `external` tests by default. Live-account evidence additionally requires both `KONTOMIERZ_EXTERNAL_TESTS=1` and `KONTOMIERZ_ALLOW_REAL_MUTATIONS=1` before credential access or mutation.
- Live cleanup traverses paid and unpaid schedule groups, reconciles the unique test namespace and budget snapshot, verifies deletion, and fails instead of swallowing unconfirmed cleanup.
- Empty-body create success never guesses a stable ID from non-unique descriptions/categories and returns a reconciliation-required marker.
- Wealth points are unwrapped from their verified per-item `{"wealth_point": {...}}` upstream shape.
- Restored full schedule `repeat`/`holidays` descriptions and locked them with regression tests.
- Streamable HTTP smoke allows slow startup without weakening its bounded timeout.
- Composition validates frozen settings before constructing a real dependency client; unsafe base URLs fail before dependency creation.
- Logging tests restore global logger state and real request diagnostics stay at WARNING+ to protect the query-string API key.
- Mock transaction contract tests call the synchronous mock API synchronously.
- Exact-artifact Docker source-label verification uses a valid Docker Go-template expression.

### Changed

- Mock backend response shapes mirror verified real API shapes rather than convenient synthetic substitutes.
- The real upstream write/date/pagination contract is documented in `docs/upstream-api.md` and machine-readable `upstream-contract.yaml` with live-account evidence from 2026-08-08.
- Standards authority is canonicalized in `trusted-executable-sources.lock.yaml` at exact `ai-skills` revision `32b699c75eaf4edac00982fea181daebaba40114` (`mcp-server-architect` 1.3.0), with SHA-256 bindings for every trusted executable used by CI.
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
- Exact-wheel and exact-image CI artifact path with source-revision OCI label, non-root smoke, checksummed closed bundle, and protected promotion attestation.
- Real external evidence tests plus `live-backend-test-policy.yaml` and `upstream-contract.yaml`.
- `trusted-executable-sources.lock.yaml` as the single immutable standards-authority coordinate and executable-integrity contract.
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
