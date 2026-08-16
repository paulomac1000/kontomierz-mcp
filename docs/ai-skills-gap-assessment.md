---
description: Assesses this revision against the pinned ai-skills standards without claiming formal approval.
doc_id: decision.ai-skills-gap-assessment
type: decision
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Compare the exact candidate SHA with the candidate-side authority declaration, run hosted structural CI, then complete externally anchored provider-backed acceptance.
---
# AI Skills gap assessment

## Decision

Target technical alignment with the immutable `ai-skills` revision declared in `trusted-executable-sources.lock.yaml` and `mcp-server-architect` 1.3.0 while withholding a formal L2+ or `adopted` claim. The lock is the canonical candidate-side executable-provenance declaration for structural CI; it is **not** a root of provider-backed trust because the candidate can edit its own lock and workflows.

Provider-backed approval must begin in the authority repository from a protected authority ref through `.github/workflows/consumer-acceptance-dispatch.yml`. That authority-owned dispatcher supplies the exact candidate repository/SHA and calls the same-revision local `consumer-acceptance.yml`. The acceptance workflow verifies that its caller/workflow repository and SHA are the intended authority identity, requires a protected authority ref, compares the candidate lock with those externally supplied authority coordinates, verifies real GitHub provider controls and exact-SHA provider evidence, and requires independent review. A candidate-owned direct cross-repository call to `consumer-acceptance.yml` is useful diagnostic evidence but is **not** provider-backed acceptance.

The current migration state is **`provider-preflight-blocked`**. GitHub currently reports the default branch `main` as unprotected and reports no repository environments, while the release workflow declares a protected `release` environment. Those provider controls cannot be created or simulated by repository source changes and must be established by an administrator before provider-backed acceptance can advance.

## Repository-side gaps closed or materially reduced

- Configuration is validated before dependency creation and rejects unsafe transport, credential, URL, request-size, and real-backend body-mode values.
- A trusted read-only `ai-skills` inspector classifies the repository before formal adoption checks. Structural standards CI asserts the official Python MCP SDK profile, external-upstream discovery, default exclusion of external tests, observed upstream contract, declared live-backend policy, and no unresolved discovery unknowns.
- `upstream-contract.yaml` records observed/recorded Kontomierz method, endpoint, encoding, date, pagination, success-body, credential-placement, and identity semantics without credential values.
- `live-backend-test-policy.yaml` and the external-test guard require independent mutation opt-ins, a verified exclusive disposable account, pre-clean, captured identities/baselines, bounded reconciliation, deletion verification, and failure on unconfirmed cleanup.
- One invocation kernel owns policy, bounded admission/concurrency, deadlines, readiness, error mapping, response-size enforcement, target metadata, and audit emission.
- Official MCP tool schemas are closed and public scalar types are strict. Unknown arguments are rejected before SDK normalization can silently drop them; numeric strings/booleans are not coerced into integer/boolean values; optional IDs reject explicit zero; falsey values of the wrong type are not silently treated as omission.
- Public strings and decimals have UTF-8 byte budgets before upstream I/O. Successful upstream JSON is bounded before decoding, and manifests enforce final response budgets.
- Authentication and authorization are distinct. Every application-dispatched invocation binds principal, exact capability, immutable target, explicit resource identity, and normalized-argument digest, then revalidates immediately before I/O.
- Streamable HTTP is authenticated, loopback-only, read-only by default, and applies independent HTTP capability policy plus the operator write gate.
- Destructive access on both transports requires exact server-owned capability and resource allowlists; the global write gate alone never authorizes deletion.
- Each application-dispatched invocation emits one bounded server-side audit event without credentials/protected result bodies. Protocol/schema failures rejected before application dispatch do not claim a kernel audit record.
- Started mutation timeout, transport loss, malformed/oversized success, cancellation-after-start audit state, and ambiguous 5xx preserve non-retryable reconciliation semantics.
- Empty-body create success does not guess an identity from non-unique fields.
- Public dates are ISO-only (`YYYY-MM-DD`) and budget months `YYYY-MM`; the real HTTP adapter alone owns localized upstream conversion.
- Production metadata pins `mcp==2.0.0`, matching the exact tested SDK lane.
- Exact Linux x64 wheel locks cover runtime/development Python 3.11–3.13 plus build tools; exact-artifact CI tests the installed wheel outside the source tree and official MCP clients on stdio/authenticated HTTP.
- The exact-artifact lane captures the MCP public contract from the same installed wheel that is tested and smoke-tested and includes it in the same release checksum closure.
- Candidate-owned structural CI validates the candidate trust lock against an immutable external checkout before executing the pinned AFDS, AGENTS, workflow, MCP discovery, upstream-contract, and live-backend-policy tools.
- Release privilege is structurally separated into read-only artifact verification, an unprivileged quarantine lane, and a protected production publisher that does not execute candidate content.

## Remaining external or intentionally unclaimed evidence

- Provider-backed adoption cannot start successfully until `main` is protected and the required `release` environment exists with reviewed protection/deployment policy. Current provider state is therefore `provider-preflight-blocked`, not merely unknown.
- An authority-owned protected dispatch of provider-backed adoption plus independent review bound to the final immutable candidate SHA are still missing. No reviewer or approval evidence is fabricated.
- Repository administrators must configure the `release` environment with required reviewers/self-review prevention as applicable and establish the required branch/deployment restrictions.
- Repository administrators must provision an isolated quarantine registry and prove that its credentials cannot mutate the production package.
- Provider-verifiable provenance for the original read-only build remains separate from the repository's structural promotion attestation.
- The exact historical `v1.0.1` public-contract baseline cannot currently be captured as authoritative artifact evidence because no immutable release wheel was published and rebuilding today would resolve a different dependency graph.
- Real evidence still does not prove `client_assigned_id` uniqueness/replay/reconciliation, post-send interrupted-create reconciliation, real 429/`Retry-After`, wallet mutation response behavior, populated transaction pagination termination, or budget-copy semantics.
- Public non-loopback hosting and multi-tenant authorization remain unsupported and are not claimed.

## Approval condition

Keep PR #7 draft until repository-owned quality, latest-reviewed structural standards, Python compatibility, exact-artifact, official stdio/HTTP smoke, and security gates all pass on one immutable implementation SHA. Then complete the remaining live evidence that supports claimed real-backend behavior. Separately, administrators must establish observable provider controls and the authority repository must launch its protected `consumer-acceptance-dispatch.yml` on the intended immutable authority revision for that exact candidate SHA; the same-revision acceptance workflow must validate provider evidence and independent review. Only then may the migration state advance through provider validation/review to `adopted`; repository-owned green CI or a candidate-owned direct reusable-workflow call by itself is not that decision.
