---
description: Assesses the repository against the pinned ai-skills standards without equating merge status with formal provider-backed approval.
doc_id: decision.ai-skills-gap-assessment
type: decision
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Compare the exact repository revision with the repository-side authority declaration, run hosted structural CI, then complete externally anchored provider-backed acceptance.
---
# AI Skills gap assessment

## Decision

The 2.0.0 migration has been merged to `main`. Repository-owned runtime, schema, security, packaging, exact-artifact, and structural standards gates are part of the merged implementation.

Technical alignment targets the immutable `ai-skills` revision declared in `trusted-executable-sources.lock.yaml` and the `mcp-server-architect` 1.3.0 contract. The lock is the repository-side executable-provenance declaration used by structural CI: it identifies the exact authority checkout and verifier bytes that repository-owned CI is expected to execute.

Merge status does **not** imply formal L2+ or `adopted` status. A repository can modify its own lock, workflows, tests, and evidence, so provider-backed acceptance must remain anchored outside the repository being evaluated.

Provider-backed approval starts in the authority repository from a protected authority ref through `.github/workflows/consumer-acceptance-dispatch.yml`. The authority-owned dispatcher supplies the exact repository and revision and calls the same-revision local `consumer-acceptance.yml`. That workflow verifies the authority workflow identity, protected authority ref, repository trust-lock equality, provider controls, exact-revision evidence, and independent review. A direct call initiated by this repository is useful diagnostic evidence but is not provider-backed approval.

A fresh provider check after the 2.0.0 merge still reports `main` as unprotected. Formal adoption therefore remains **`provider-preflight-blocked`** until the required provider/admin controls are observable and the external acceptance path succeeds.

## Repository-side gaps closed or materially reduced

- Startup configuration is validated before dependency construction and rejects unsafe transport, credential, URL, request-size, and real-backend body-mode values.
- `upstream-contract.yaml` records observed Kontomierz method, endpoint, encoding, date, pagination, success-body, credential-placement, and identity semantics without storing credential values.
- `live-backend-test-policy.yaml` and the external-test guard require explicit mutation opt-ins, a verified exclusive disposable account, pre-clean, captured identities/baselines, bounded reconciliation, deletion verification, and failure on unconfirmed cleanup.
- One invocation kernel owns policy, bounded admission/concurrency, deadlines, readiness, error mapping, response-size enforcement, target metadata, and audit emission.
- Public MCP input schemas are closed and scalar types are strict. Unknown fields and invalid cross-type coercions are rejected before operation I/O.
- Public strings, decimals, request bodies, upstream responses, final tool results, and audit events are bounded.
- Authentication and authorization are distinct. Every application-dispatched invocation binds principal, exact capability, immutable target, explicit resource identity, and normalized-argument digest, then revalidates immediately before I/O.
- Streamable HTTP is Bearer-authenticated, loopback-only, and read-only by default. HTTP writes require explicit capability policy plus the independent operator write gate.
- Destructive access on both transports requires exact server-owned capability and resource allowlists; the global write gate alone never authorizes deletion.
- Each application-dispatched invocation emits one bounded server-side audit event without credentials, raw arguments, or protected result bodies.
- Started mutation timeouts, transport loss, malformed/oversized successful mutation responses, and other completion-uncertain failures preserve non-retryable reconciliation semantics.
- Confirmed empty-body create success does not guess identity from non-unique fields; observed budget/schedule cases return a reconciliation-required success marker.
- Public dates are ISO `YYYY-MM-DD` and budget months are `YYYY-MM`; localized upstream date conversion remains inside the adapter.
- Production metadata pins the tested MCP SDK lane to `mcp==2.0.0`.
- Exact Linux x64 wheel locks cover runtime/development Python 3.11–3.13 plus build tooling.
- Exact-artifact CI installs and tests the built wheel outside the source tree, exercises official MCP clients over stdio and authenticated Streamable HTTP, and builds the non-root revision-bound image from verified inputs.
- The MCP public-contract snapshot is captured from the same exact installed wheel that is tested, smoke-tested, bundled, and released.
- Structural standards CI validates the repository trust lock against the immutable authority checkout before executing governed validation tools.
- Release privilege is structurally separated into read-only artifact verification, unprivileged quarantine, and protected production promotion that does not execute repository content.

## Remaining external or intentionally unclaimed evidence

- `main` must be protected by observable provider policy with the intended required checks and merge restrictions before provider-backed acceptance can pass.
- The required `release` environment and its reviewer/deployment protections must exist and pass the authority-owned provider preflight; repository source cannot prove those settings by itself.
- The authority repository must run its protected acceptance dispatcher for the exact repository revision under evaluation.
- Independent review must be bound to that exact immutable revision rather than inferred from repository-owned CI or historical PR comments.
- Administrators must provide an isolated quarantine registry and provider-verifiable evidence that its credential cannot mutate the production package.
- Provider-verifiable provenance for the original build remains separate from repository-owned checksum and promotion attestations.
- Historical 1.x public-contract evidence is incomplete because no authoritative immutable 1.0.1 release wheel is available for exact comparison.
- Real Kontomierz evidence still does not prove `client_assigned_id` uniqueness/replay semantics, post-send interrupted-create reconciliation, real 429/`Retry-After`, wallet create response-body behavior, populated transaction pagination termination, or budget-copy semantics.
- Public non-loopback hosting and multi-tenant authorization remain unsupported and are not claimed.

## Post-merge adoption condition

The 2.0.0 merge closed the repository-owned implementation migration; it did not close the external adoption process.

To advance from `provider-preflight-blocked` to a formal `adopted` decision, all of the following must refer to one exact repository revision:

1. repository-owned quality, compatibility, structural standards, exact-artifact, official-client, and security gates pass;
2. claimed real-backend behavior is supported by the authorized disposable-account evidence suite;
3. provider branch/environment/credential controls are observable and pass the trusted external preflight;
4. the protected `ai-skills` authority dispatcher launches same-revision provider-backed acceptance for the exact repository revision;
5. independent review and provider-verifiable build provenance bind to that same revision/artifact;
6. the final decision is produced by the external acceptance path rather than inferred from merge status or repository-owned CI.

Until then, describe the implementation as technically aligned with the pinned standards and repository-owned gates, but do not claim formal L2+ adoption.
