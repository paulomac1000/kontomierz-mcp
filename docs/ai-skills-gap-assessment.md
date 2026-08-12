---
description: Assesses this revision against the pinned ai-skills standards without claiming formal approval.
doc_id: decision.ai-skills-gap-assessment
type: decision
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Compare the exact candidate SHA with the authority in `trusted-executable-sources.lock.yaml`, run hosted CI, and complete provider-backed evidence.
---
# AI Skills gap assessment

## Decision

Target technical alignment with the immutable `ai-skills` authority declared in `trusted-executable-sources.lock.yaml` and `mcp-server-architect` 1.3.0 while withholding a formal L2+ claim. The exact authority revision is intentionally declared only in the canonical lock, not duplicated in workflows or prose. CI resolves repository/revision from that lock, independently checks out the authority, verifies trusted executable SHA-256 values, and then runs the standards checks. Any authority update requires review of the branch delta, a lock update, and a new exact-revision evidence run.

## Closed or materially reduced gaps

- Configuration is validated before dependency creation and rejects unsafe transport, credential, URL, request-size, and real-backend body-mode values.
- A trusted read-only `ai-skills` inspector classifies the repository before formal adoption checks. Standards CI asserts the official Python MCP SDK profile, external-upstream discovery, default exclusion of external tests, observed upstream contract, declared live-backend policy, and no unresolved discovery unknowns.
- `upstream-contract.yaml` records observed/recorded Kontomierz method, endpoint, encoding, date, pagination, success-body, credential-placement, and identity semantics without credential values.
- `live-backend-test-policy.yaml` declares two independent mutation opt-ins, credential access only after opt-in, unique namespace, ID capture, marker reconciliation, and mandatory reporting of unconfirmed cleanup. The final guard pre-cleans, snapshots budgets, traverses paid/unpaid schedules, reconciles transactions, and fails when cleanup cannot be verified.
- One kernel owns policy, bounded admission/concurrency, deadlines, readiness, error mapping, response-size enforcement, and metadata.
- Public model-controlled strings and decimals have UTF-8 byte budgets before upstream I/O. Successful upstream JSON is bounded before decoding, and manifests enforce final response budgets.
- Authentication and authorization are distinct. Every invocation binds principal, exact capability, immutable target, explicit resource identity, and normalized-argument digest, then revalidates immediately before I/O.
- Streamable HTTP is authenticated, loopback-only, read-only by default, and applies independent HTTP capability policy plus the operator write gate.
- Destructive access on both transports requires exact server-owned capability and resource allowlists; the global write gate alone never authorizes deletion.
- Each invocation emits one bounded server-side audit event without credentials/protected result bodies. HTTP dependency request logging is held at WARNING+ to avoid query-string API-key leakage.
- Started mutation timeout, transport loss, malformed/oversized success, cancellation-after-start audit state, and ambiguous 5xx preserve non-retryable reconciliation semantics.
- Empty-body create success does not guess an identity from non-unique fields.
- Public dates are ISO-only (`YYYY-MM-DD`) and budget months `YYYY-MM`; `DD-MM-YYYY` is internal upstream representation.
- Production metadata pins `mcp==2.0.0`, matching the exact tested SDK lane.
- Exact Linux x64 wheel locks cover runtime/development Python 3.11–3.13 plus build tools; exact artifact CI tests the installed wheel outside the source tree and official MCP clients on stdio/authenticated HTTP.
- `trusted-executable-sources.lock.yaml` is the single authority coordinate and binds every trusted executable used by acceptance to a SHA-256 digest. The trusted validator checks that lock before the other standards tools execute, and consumer-trust hygiene detects candidate-controlled trust bypasses.
- The exact image is built with the full source revision as an OCI label and smoke-tested before it enters release handling.
- Release privilege is separated into three stages: read-only artifact verification; an unprivileged quarantine lane that loads/smokes then pushes to an isolated non-GHCR registry and re-smokes an immutable digest; and a protected production publisher that performs registry-to-registry promotion only. The privileged publisher does not checkout, download, load, or run candidate content.

## Deferred gaps

- A provider-backed, independently reviewed migration/adoption assessment for the final immutable candidate is missing. No reviewer identity, provider review ID, or approval evidence is fabricated while PR #7 lacks an independent submitted review.
- Repository administrators must configure the protected GitHub `release` environment with required reviewers, self-review prevention, and protected-branch policy.
- Repository administrators must provision `QUARANTINE_REGISTRY`, `QUARANTINE_REPOSITORY`, `QUARANTINE_USERNAME`, and `QUARANTINE_TOKEN`. The workflow structurally rejects production GHCR as the quarantine registry, but provider-backed evidence must still prove the real quarantine credential cannot mutate the production package.
- Provider-verifiable provenance for the original read-only CI build remains separate from the promotion attestation.
- Real evidence still does not prove `client_assigned_id` uniqueness/replay/reconciliation, post-send interrupted-create reconciliation, real 429/`Retry-After`, wallet mutation response behavior, populated transaction pagination termination, or budget-copy semantics.
- Public non-loopback hosting and multi-tenant authorization remain unsupported and are not claimed.

## Approval condition

Keep PR #7 draft until quality, exact-artifact, latest-reviewed standards, Python compatibility, official stdio/HTTP smoke, adversarial security, and Docker gates all pass on one immutable implementation SHA; live evidence supports every claimed real-backend behavior; the provider/repository placeholders are implemented from real authority; release and quarantine administration is verified; provider-backed migration/adoption and build-provenance evidence matches the same SHA; and an independent reviewer approves it. Formal L2+ adoption is intentionally not claimed before those conditions hold.
