---
description: Assesses this revision against the pinned ai-skills standards without claiming formal approval.
doc_id: decision.ai-skills-gap-assessment
type: decision
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Compare the exact SHA with ai-skills revision `c6dc6b13b2dd40b6e087140cd071b45067d75b39`, run hosted CI, and complete provider-backed evidence.
---
# AI Skills gap assessment

## Decision

Target technical alignment with the immutable `ai-skills` revision `c6dc6b13b2dd40b6e087140cd071b45067d75b39` while withholding a formal L2+ claim. A newer branch head may exist in `ai-skills`, but this assessment remains intentionally pinned to the immutable revision whose normative MCP contract, adoption schema, validator, rule catalog, and AFDS validator were previously verified for this migration. Updating that authority requires a separate exact-revision evidence run rather than a floating branch reference.

## Closed or materially reduced gaps

- Configuration precedes dependency creation and rejects invalid TCP ports and unsafe HTTP policy values.
- One kernel owns policy, bounded admission, concurrency, deadlines, readiness, error mapping, and metadata.
- Authentication and authorization are separate: every invocation is bound server-side to an exact capability ID, capability class, immutable configured target, explicit resource identity, and normalized-argument digest, then revalidated immediately before I/O.
- Streamable HTTP is fail-closed without request-scoped Bearer authentication and defaults to read-only authorization; write capability classes require explicit server-owned policy in addition to the operator write gate.
- Remote destructive access is narrower than a capability class: `destructive` is rejected unless exact capability IDs and exact resource identities are configured in independent allowlists.
- Local stdio uses a process-derived principal and the principal is included in structured server-side audit records rather than model-visible output.
- Each invocation emits one bounded JSON audit event containing correlation, principal, capability/target/resource policy decision, operator-gate decision, dependency state, result category, duration, cancellation, saturation, and ambiguous state without credentials or protected result bodies.
- The audit channel owns an INFO-capable sink independent from ordinary `LOG_LEVEL`; sink failure is explicitly result-preserving fail-open to avoid turning a completed mutation into a misleading post-I/O application failure.
- Streamable HTTP has intentional SDK Host and Origin allowlists, explicit stateless mode, and an application-configured request-body bound; adversarial tests prove rejection before kernel I/O.
- `/health/live` is public and dependency-free. `/health/ready` requires Bearer authentication before `InvocationKernel.readiness()` can run, so an unauthenticated remote request cannot cause upstream network I/O.
- The dependency adapter is natively asynchronous; cancellation no longer leaves executor workers running.
- Unsafe writes are serialized per target scope.
- Started write timeout, connection loss, response loss, malformed success shape, and ambiguous 5xx become non-retryable ambiguous outcomes.
- One governed catalog owns signatures, descriptions, schema expectations, manifests, registration, versions, and active-state discovery.
- Runtime manifests no longer claim automatic retry, replay-safe writes, or confirmation without executable enforcement.
- Breaking transport, error, pagination, and input changes are versioned as `2.0.0`.
- MCP errors are explicit stable `CallToolResult` documents.
- Readiness includes a bounded cached dependency probe behind the authenticated HTTP readiness boundary.
- Linux x64 runtime and development dependency graphs are exact-wheel hash-locked separately for Python 3.11, 3.12, and 3.13; build tooling has its own hash lock. Acceptance paths install them with `--require-hashes --no-deps --only-binary=:all:` and verify completeness with `pip check`.
- Exact-artifact CI materializes the Python 3.12 runtime wheelhouse from the committed lock, tests a runtime-only installed wheel without network resolution, and includes the runtime/build locks in the checksummed release bundle.
- Workflow policy profiles are explicit and trusted validators are pinned to the reviewed assessed ai-skills revision.
- Read-only release validation proves the source SHA is reachable from the trusted default branch before accepting the closed CI artifact.
- Protected publishing does not execute candidate source after release write permissions are granted and uses a full 40-character SHA tag.
- The Docker build verifies the exact wheel/wheelhouse checksum manifest and installs the committed runtime lock with `--require-hashes` before the application wheel.

## Deferred gaps

- A schema-valid `migration-assessment.yaml` is still missing. The pinned schema requires a concrete GitHub `decision.reviewer` even for `request-changes`, and the validator requires that reviewer to be independent from every `prepared_by` identity. PR #7 currently has no submitted GitHub review, so no reviewer identity or review ID is fabricated.
- Real upstream write method/body, pagination termination, `client_assigned_id` reconciliation, money precision, rate-limit, and credential-recovery contracts require a disposable Kontomierz account. These gaps are encoded as intentionally failing `external` tests rather than passing skips.
- Independent approval for the final immutable revision is still required.
- Repository administrators must configure the `release` environment with required reviewers, self-review prevention, and protected-branch deployment policy. The publish verifier fails closed when that environment is missing or insufficiently protected, but repository administration still requires an external privileged action.
- The current protected publish step emits a promotion attestation. A stronger provider-verifiable build provenance statement for the read-only CI build remains a separate evidence item.
- Public non-loopback hosting and multi-tenant authorization remain unsupported. Resource decisions are explicit only inside the one immutable configured credential scope; L4-style cross-tenant isolation is not claimed.

## Approval condition

Keep the PR draft until hosted quality, standards, Python compatibility, locked exact-wheel, authenticated stdio/HTTP smoke, adversarial HTTP security, and Docker gates pass on the same exact implementation SHA; real-system evidence is completed; release evidence is reviewed; the migration assessment is switched to provider-backed mode with real final evidence; the `release` environment is administratively protected; and an independent reviewer approves the immutable revision.
