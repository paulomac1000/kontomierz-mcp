---
doc_id: guide.kontomierz-agent-instructions
type: guide
status: evolving
rigor: operational
owners:
  - repository-maintainers
description: Repository workflow, safety boundaries, and completion rules for agents changing Kontomierz MCP.
verification:
  - Run the completion gate in this file from an activated virtual environment.
  - Confirm hosted CI belongs to the exact final revision.
---
# Repository instructions

## Scope and risk contract

This repository is a financial MCP server. Reads can expose confidential financial or personal data. Writes can create, change, or delete persistent financial records. Treat target selection, authentication, write enablement, ambiguous outcomes, release permissions, and dependency identity as safety boundaries. Never weaken a fail-closed control merely to satisfy a test or validator.

These instructions use the single-repository MCP-server profile. The root file is the only AGENTS.md for the candidate tree.

## Architecture ownership

- `src/kontomierz_mcp/config.py` owns immutable startup configuration and unsafe-configuration rejection.
- `src/kontomierz_mcp/security.py` owns process-derived stdio identity and Streamable HTTP authentication context.
- `src/kontomierz_mcp/client.py` owns upstream HTTP behavior and typed dependency failures.
- `src/kontomierz_mcp/operation_support.py` owns shared domain validation.
- `src/kontomierz_mcp/operation_primary.py` and `src/kontomierz_mcp/operation_secondary.py` own transport-independent handlers.
- `src/kontomierz_mcp/operations.py` binds the operation catalog to the dependency port.
- `src/kontomierz_mcp/manifest_types.py` owns governed manifest and tool-definition types.
- `src/kontomierz_mcp/manifest_policy.py` owns manifest construction and runtime active-state projection.
- `src/kontomierz_mcp/tool_definitions_primary.py`, `src/kontomierz_mcp/tool_definitions_secondary.py`, and `src/kontomierz_mcp/tool_definitions_tertiary.py` own the public tool catalog.
- `src/kontomierz_mcp/manifests.py` is the public catalog facade.
- `src/kontomierz_mcp/kernel.py` is the only invocation policy/execution kernel.
- `src/kontomierz_mcp/server.py` is the composition root and official MCP transport adapter.
- `src/kontomierz_mcp/mock_backend.py` is deterministic test data only and must not silently become production behavior.

Keep transports thin. Do not call the Kontomierz adapter directly from an MCP wrapper. Public names, signatures, parameter descriptions, versions, and safety metadata must remain discoverable from the governed catalog.

## Safety invariants

Stdio may use a process-derived local principal. Streamable HTTP must authenticate a request-scoped principal before MCP handling and remains loopback-only. Do not accept a principal, write-enable flag, approval, target override, or credential from model-controlled tool arguments.

Mutations require the trusted operator write gate. The current server has no independent approval authority, so manifests must not claim confirmation. If a future manifest requires confirmation, invocation must remain fail-closed until a trusted approval record bound to principal, capability, target, and argument digest is verified server-side.

Never automatically retry mutations. A timeout, transport loss, malformed response after a successful HTTP mutation, or other ambiguous post-start failure must stay `AMBIGUOUS_OUTCOME` until exact target state is reconciled. Preserve per-target serialization for capabilities that are not concurrency-safe.

Do not expose API keys, Bearer tokens, raw upstream bodies, or principal secrets in tool results or logs. Health endpoints may report bounded status only.

## Change discipline

Update tests whenever behavior, manifests, public schemas, authentication, retry semantics, target binding, or release policy changes. Keep external Kontomierz assumptions conservative until a disposable real-account test proves them. Do not convert a deferred evidence item into a positive claim merely because the mock backend passes.

GitHub Actions must use immutable action revisions, explicit permissions, concrete runners, job timeouts, and the workflow profile declared in `.github/workflow-policy.yaml`. Trusted `ai-skills` validators must be checked out at the pinned immutable revision and moved outside the candidate tree before auditing it.

## Completion gate

Create and activate a virtual environment before running repository commands. The commands below mirror executable CI gates and are the completion contract:

```bash
python -m pip install -e ".[dev]"
python -m pip check
python -m ruff check .
python -m ruff format --check .
python -m mypy src/kontomierz_mcp
python -m bandit -q -r src/kontomierz_mcp
python -m pip_audit
python -m pytest -m "not external" --cov=kontomierz_mcp --cov-branch --cov-report=term-missing --cov-report=xml
python scripts/mock_smoke.py
```

The hosted exact-artifact job additionally builds one application wheel, installs it without network access from the closed wheelhouse, runs official-client stdio and authenticated Streamable HTTP smoke tests, verifies Docker installation checksums, and smoke-tests the exact container before preserving the release archive.

Tests that require a disposable real Kontomierz account remain explicit external evidence. Do not run them against a personal or non-disposable account.

## Documentation and release

When public behavior changes, update README, changelog when release-visible, system architecture, tool contract, upstream assumptions, and the ai-skills gap assessment as appropriate. Do not claim formal L2+ adoption until the exact immutable revision has the required hosted evidence, reviewed dependency locks, provider-backed migration assessment, real-system evidence, protected release configuration, and independent approval.
