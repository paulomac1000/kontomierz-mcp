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

- Configuration precedes dependency creation and rejects invalid TCP ports.
- One kernel owns policy, bounded admission, concurrency, deadlines, readiness, error mapping, and metadata.
- The dependency adapter is natively asynchronous; cancellation no longer leaves executor workers running.
- Unsafe writes are serialized per target scope.
- Started write timeout, connection loss, response loss, malformed success shape, and ambiguous 5xx become non-retryable ambiguous outcomes.
- One governed catalog owns signatures, descriptions, schema expectations, manifests, registration, versions, and active-state discovery.
- Runtime manifests no longer claim automatic retry, replay-safe writes, or confirmation without executable enforcement.
- Streamable HTTP now authenticates a server-configured principal with a bounded Bearer token before MCP handling; local stdio uses a process-derived principal.
- Breaking transport, error, pagination, and input changes are versioned as `2.0.0`.
- MCP errors are explicit stable `CallToolResult` documents.
- Readiness includes a bounded cached dependency probe.
- Workflow policy profiles are explicit and trusted validators are pinned to the current assessed ai-skills revision.
- Protected publishing no longer checks out or runs candidate code after release write permissions are granted; it promotes a closed image archive under a full 40-character SHA tag.
- The Docker build verifies the exact wheel/wheelhouse checksum manifest before installation.

## Deferred gaps

- Reviewed runtime and development dependency locks with hashes are still missing. Current exact-artifact CI closes and verifies the resolved wheelhouse after resolution, but resolution itself is not reproducible yet.
- A provider-backed `migration-assessment.yaml` is not fabricated before final hosted run, artifact, digest, and independent-review identifiers exist.
- Real upstream write method/body, pagination termination, and `client_assigned_id` reconciliation contracts require a disposable Kontomierz account.
- Independent approval for the final immutable revision is still required.
- Repository administrators must configure the `release` environment with required reviewers; workflow source alone cannot enforce repository environment policy.
- The current protected publish step emits a promotion attestation. A stronger provider-verifiable build provenance statement for the read-only CI build remains a separate evidence item.
- Public non-loopback hosting remains unsupported.

## Approval condition

Keep the PR draft until hosted quality, standards, Python compatibility, exact-wheel, authenticated stdio/HTTP smoke, and Docker gates pass on the same exact SHA; real-system TODOs are completed; dependency locks and release evidence are reviewed; a provider-backed migration assessment is populated from real evidence; and an independent reviewer approves the immutable revision.
