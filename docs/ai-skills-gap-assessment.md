---
description: Assesses this revision against the pinned ai-skills standards without claiming formal approval.
doc_id: decision.ai-skills-gap-assessment
type: decision
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Compare the exact SHA with ai-skills revision `b359245d3a34fce90cfeb0fdab052e75b5b821f3`, run hosted CI, and complete provider-backed evidence.
---
# AI Skills gap assessment

## Decision

Target technical alignment with the immutable `ai-skills` revision `b359245d3a34fce90cfeb0fdab052e75b5b821f3`, the current head of `fix/unified-contract-release-hardening` used for this review, while withholding a formal L2+ claim. CI and this document pin the exact revision rather than a floating branch reference. Any later authority update requires a new exact-revision evidence run.

## Closed or materially reduced gaps

- Configuration precedes dependency creation and rejects invalid TCP ports, unsafe HTTP policy values, non-visible HTTP credential/principal bytes, and the known-broken JSON write mode for the real Kontomierz backend.
- One kernel owns policy, bounded admission, concurrency, deadlines, readiness, error mapping, response-size enforcement, and metadata.
- Public text and decimal-string values are bounded by UTF-8 byte budgets before upstream I/O, including multibyte input cases; dates, months, directions, chart kinds, search text, labels, descriptions, correlation IDs, and money strings all have explicit application limits.
- Every governed manifest declares `max_response_bytes`; the current default is 1 MiB and the final serialized `data` plus `_meta` document is measured before return. Oversized reads fail closed; a mutation whose operation completed but whose representation is too large returns a small completion/reconciliation marker instead of a retry-provoking error.
- Upstream successful JSON bodies are streamed and bounded to 4 MiB before decoding. Oversized read bodies fail safely; oversized successful mutation bodies preserve ambiguous-write classification. Error statuses are mapped before raw error bodies are read.
- Authentication and authorization are separate: every invocation is bound server-side to an exact capability ID, capability class, immutable configured target, explicit resource identity, and normalized-argument digest, then revalidated immediately before I/O.
- Streamable HTTP is fail-closed without request-scoped Bearer authentication and defaults to read-only authorization; write capability classes require explicit server-owned policy in addition to the operator write gate.
- Destructive access is narrower than a capability class on both transports. Stdio requires exact capability IDs and exact resource identities through `MCP_STDIO_ALLOWED_DESTRUCTIVE_*`; HTTP requires its own exact `MCP_HTTP_ALLOWED_DESTRUCTIVE_*` lists in addition to the HTTP capability class. The global write gate alone never authorizes deletion.
- Local stdio uses a process-derived principal and the principal is included in structured server-side audit records rather than model-visible output.
- Each invocation emits one bounded JSON audit event containing correlation, principal, capability/target/resource policy decision, operator-gate decision, dependency state, result category, duration, cancellation, saturation, and ambiguous state without credentials or protected result bodies.
- A cancellation after a mutation has entered its operation body remains a cancellation at the protocol/runtime boundary but is explicitly audited as an ambiguous write outcome, preserving the reconciliation requirement instead of implying the mutation is known not to have happened.
- The audit channel owns an INFO-capable sink independent from ordinary `LOG_LEVEL`; sink failure is explicitly result-preserving fail-open to avoid turning a completed mutation into a misleading post-I/O application failure.
- `httpx` and `httpcore` request diagnostics are held at WARNING or above even when application logging is DEBUG, preventing the query-string API credential required by Kontomierz from being emitted through dependency request logs.
- Streamable HTTP has intentional SDK Host and Origin allowlists, explicit stateless mode, and an application-configured request-body bound; adversarial tests prove rejection before kernel I/O.
- `/health/live` is public and dependency-free. `/health/ready` requires Bearer authentication before `InvocationKernel.readiness()` can run, so an unauthenticated remote request cannot cause upstream network I/O.
- The dependency adapter is natively asynchronous; cancellation no longer leaves executor workers running.
- Unsafe writes are serialized per target scope.
- Started write timeout, connection loss, response loss, malformed or oversized success shape, and ambiguous 5xx become non-retryable ambiguous outcomes.
- Empty-body create success never guesses an object identity by matching non-unique descriptions, categories, or groups. It returns a reconciliation-required marker and leaves stable-ID recovery to an explicit list/reconcile step.
- One governed catalog owns signatures, descriptions, schema expectations, manifests, registration, versions, and active-state discovery.
- Runtime manifests no longer claim automatic retry, replay-safe writes, or confirmation without executable enforcement.
- Breaking transport, error, pagination, metadata, authorization, and input changes are versioned as `2.0.0`, consistent with the current ai-skills major-version rule for incompatible tool contracts.
- Public dates accept ISO `YYYY-MM-DD` only and budget months accept `YYYY-MM` only; localized `DD-MM-YYYY` is an internal upstream representation rather than an undocumented public compatibility path.
- MCP errors are explicit stable `CallToolResult` documents.
- Successful response metadata exposes an opaque `target_ref` plus `target_scope`; credential-derived target identity remains internal to authorization and audit.
- Readiness includes a bounded cached dependency probe behind the authenticated HTTP readiness boundary.
- Linux x64 runtime and development dependency graphs are exact-wheel hash-locked separately for Python 3.11, 3.12, and 3.13; build tooling has its own hash lock. Acceptance paths install them with `--require-hashes --no-deps --only-binary=:all:` and verify completeness with `pip check`.
- Production package metadata pins `mcp==2.0.0`, matching the exact tested SDK lane instead of claiming unverified future 2.x compatibility.
- Exact-artifact CI materializes the Python 3.12 runtime wheelhouse from the committed lock, tests a runtime-only installed wheel without network resolution, and includes the runtime/build locks in the checksummed release bundle.
- Plain `pytest` excludes external/provider evidence by default. Live-account contract tests require two explicit opt-ins before credentials are read or mutations are attempted, and cleanup uses ID plus description/snapshot reconciliation fallbacks.
- Workflow policy profiles are explicit and trusted validators are pinned to the exact reviewed ai-skills revision above.
- Read-only release validation proves the source SHA is reachable from the trusted default branch before accepting the closed CI artifact.
- Protected publishing does not execute candidate source after release write permissions are granted and uses a full 40-character SHA tag.
- The Docker build verifies the exact wheel/wheelhouse checksum manifest and installs the committed runtime lock with `--require-hashes` before the application wheel.

## Deferred gaps

- A provider-backed, independently reviewed migration/adoption assessment for the final immutable candidate is still missing. No reviewer identity, provider review ID, or approval evidence is fabricated while PR #7 has no independent submitted review.
- Real upstream write method/body, pagination termination, money precision, and date contracts are verified with live-account evidence collected on 2026-08-08: writes require form-encoded bodies, upstream write dates use `DD-MM-YYYY`, schedule and budget creates return 201 with empty bodies, transactions return the created object, `scheduled_transactions` pagination honors `page`/`per_page` with stable ordering and terminates, and withdrawal amounts normalize to negative strings. The evidence lives in `tests/external/test_real_kontomierz_contract.py`. `client_assigned_id` uniqueness/reconciliation semantics and interrupted-create post-timeout reconciliation remain unproven and stay external evidence gates.
- Independent approval for the final immutable revision is still required.
- Repository administrators must configure the `release` environment with required reviewers, self-review prevention, and protected-branch deployment policy. The publish verifier fails closed when that environment is missing or insufficiently protected, but repository administration still requires an external privileged action.
- The current protected publish step emits a promotion attestation. A stronger provider-verifiable build provenance statement for the read-only CI build remains a separate evidence item.
- Public non-loopback hosting and multi-tenant authorization remain unsupported. Resource decisions are explicit only inside the one immutable configured credential scope; L4-style cross-tenant isolation is not claimed.

## Approval condition

Keep the PR draft until hosted quality, latest-pinned standards, Python compatibility, locked exact-wheel, authenticated stdio/HTTP smoke, adversarial HTTP security, and Docker gates pass on the same exact implementation SHA; release evidence is reviewed; the migration/adoption assessment is provider-backed with real final evidence; the `release` environment is administratively protected; and an independent reviewer approves the immutable revision. Real-system read/write contract evidence for this revision was supplied on 2026-08-08 against the repository owner's live account; formal L2+ adoption still requires the remaining provider-backed and administrative items.
