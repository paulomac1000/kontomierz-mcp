---
description: Assesses this revision against the pinned ai-skills MCP, AFDS, AGENTS, and CI/CD standards without claiming formal approval.
doc_id: decision.ai-skills-gap-assessment
type: decision
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Compare the exact branch SHA with ai-skills revision `661ff01a5e70d58d6c94a12545b24647e52063ed`, run hosted CI, and complete provider-backed adoption evidence.
---
# AI Skills gap assessment

## Decision

Target technical alignment with `ai-skills` 1.2.0 while withholding the formal L2+ claim. The assessed standard revision is `661ff01a5e70d58d6c94a12545b24647e52063ed`.

## Closed gaps

- Configuration precedes dependency creation.
- One kernel owns validation, policy, deadline, execution, error mapping, and metadata.
- Legacy HTTP+SSE and the raw REST fallback are removed.
- Streamable HTTP fails closed outside loopback.
- Tool manifests use independent safety axes and classify financial reads correctly.
- Mutation retries are conservative and write timeouts are ambiguous outcomes.
- Mock data, domain tests, HTTP contract fakes, and official-client test scaffolding are separated.
- CI is designed to test and publish the same wheel.
- Root AGENTS instructions and governed AFDS documents have canonical ownership.

## Deferred gaps

- Provider-backed exact-SHA evidence and independent approval require the hosted run after this branch is pushed.
- Official MCP SDK tests could not execute locally because the environment's package mirror did not provide `mcp` v2.
- Real upstream write contracts require a disposable account.
- Public remote hosting remains unsupported rather than weakly authenticated.
- Forced cancellation cannot terminate an already-running synchronous socket call; both kernel and socket deadlines bound the impact.

## Approval condition

Do not mark the project L2+ until the official-client suite passes against the exact wheel and container, the real upstream contract TODOs are completed, all applicable catalog rules are recorded, and an independent reviewer approves the immutable revision.
