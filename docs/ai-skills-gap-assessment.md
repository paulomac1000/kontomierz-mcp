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

Target technical alignment with the immutable `ai-skills` revision `c6dc6b13b2dd40b6e087140cd071b45067d75b39` while withholding a formal L2+ claim.

## Closed or materially reduced gaps

- Configuration precedes dependency creation and rejects invalid TCP ports and unsafe HTTP policy values.
- One kernel owns policy, bounded admission, concurrency, deadlines, readiness, error mapping, and metadata.
- Authentication and authorization are separate: every invocation is bound server-side to an exact capability ID, capability class, immutable configured target, and normalized-argument digest, then revalidated immediately before I/O.
- Streamable HTTP is fail-closed without request-scoped Bearer authentication and defaults to read-only authorization; write/destructive capability classes require explicit server-owned policy in addition to the operator write gate.
- Local stdio uses a process-derived principal and the principal is included in structured server-side audit records rather than model-visible output.
- Each invocation emits one bounded JSON audit event containing correlation, principal, capability/target policy decision, operator-gate decision, dependency state, result category, duration, cancellation, saturation, and ambiguous state without credentials or protected result bodies.
- Streamable HTTP now has intentional SDK Host and Origin allowlists, explicit stateless mode, and an application-configured request-body bound; adversarial tests prove rejection before kernel I/O.
- The dependency adapter is natively asynchronous; cancellation no longer leaves executor workers running.
- Unsafe writes are serialized per target scope.
- Started write timeout, connection loss, response loss, malformed success shape, and ambiguous 5xx become non-retryable ambiguous outcomes.
- One governed catalog owns signatures, descriptions, schema expectations, manifests, registration, versions, and active-state discovery.
- Runtime manifests no longer claim automatic retry, replay-safe writes, or confirmation without executable enforcement.
- Breaking transport, error, pagination, and input changes are versioned as `2.0.0`.
- MCP errors are explicit stable `CallToolResult` documents.
- Readiness includes a bounded cached dependency probe.
- Workflow policy profiles are explicit and trusted validators are pinned to the current assessed ai-skills revision.
- Read-only release validation proves the source SHA is reachable from the trusted default branch before accepting the closed CI artifact.
- Protected publishing does not execute candidate source after release write permissions are granted and uses a full 40-character SHA tag.
- The Docker build verifies the exact wheel/wheelhouse checksum manifest before installation.

## Deferred gaps

- Reviewed runtime and development dependency locks with hashes are still missing. Current exact-artifact CI closes and verifies the resolved wheelhouse after resolution, but resolution itself is not reproducible yet.
- The structural migration assessment records current real evidence and explicit blockers but cannot become an approval until provider-backed evidence and an independent review are bound to the final immutable revision.
- Real upstream write method/body, pagination termination, and `client_assigned_id` reconciliation contracts require a disposable Kontomierz account.
- Independent approval for the final immutable revision is still required.
- Repository administrators must configure the `release` environment with required reviewers, self-review prevention, and protected-branch deployment policy. The publish verifier now fails closed when that environment is missing or insufficiently protected, but repository administration still requires an external privileged action.
- The current protected publish step emits a promotion attestation. A stronger provider-verifiable build provenance statement for the read-only CI build remains a separate evidence item.
- Public non-loopback hosting and multi-tenant authorization remain unsupported.

## Approval condition

Keep the PR draft until hosted quality, standards, Python compatibility, exact-wheel, authenticated stdio/HTTP smoke, adversarial HTTP security, and Docker gates pass on the same exact implementation SHA; real-system evidence is completed; dependency locks and release evidence are reviewed; the migration assessment is switched to provider-backed mode with real final evidence; the `release` environment is administratively protected; and an independent reviewer approves the immutable revision.
