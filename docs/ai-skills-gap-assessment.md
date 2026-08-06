---
description: Assesses this revision against the pinned ai-skills standards without claiming formal approval.
doc_id: decision.ai-skills-gap-assessment
type: decision
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Compare the exact SHA with ai-skills revision `661ff01a5e70d58d6c94a12545b24647e52063ed`, run hosted CI, and complete provider-backed evidence.
---
# AI Skills gap assessment

## Decision

Target technical alignment with `ai-skills` 1.2.0 while withholding a formal L2+ claim.

## Closed gaps

- Configuration precedes dependency creation.
- One kernel owns policy, bounded admission, concurrency, deadlines, readiness, error mapping, and metadata.
- The dependency adapter is natively asynchronous; cancellation no longer leaves executor workers running.
- Unsafe writes are serialized per target scope.
- Started write timeout, connection loss, response loss, and ambiguous 5xx become non-retryable ambiguous outcomes.
- Runtime manifests no longer claim automatic retry that is not implemented.
- MCP errors are explicit stable `CallToolResult` documents.
- Readiness includes a bounded cached dependency probe.
- Optional IDs, date ranges, update omission/clearing, schedule integers, wallet balances, and pagination hints have explicit tests.

## Deferred gaps

- Hosted exact-SHA evidence and independent approval have not been produced for connector-authored commits.
- The local mirror does not provide MCP SDK v2 or the full quality toolchain; the SDK test is mandatory rather than skipped.
- Real upstream write, pagination, and reconciliation contracts require a disposable account.
- A reviewed hash-locked dependency graph has not been generated because the authoritative resolver and MCP package were unavailable locally.
- External trusted `ai-skills` AFDS, AGENTS, and workflow-policy validators are not yet wired into hosted CI.
- The release workflow now promotes the exact CI-tested image tarball, compares registry tag digests, and requests a provenance attestation; hosted evidence for those steps is still missing.
- Public remote hosting remains unsupported.

## Approval condition

Keep the PR draft until the official-client suite passes against the exact wheel and transport, hosted quality and container jobs pass on the exact SHA, real-system TODOs are completed, dependency locks and release evidence are reviewed, and an independent reviewer approves the immutable revision.
