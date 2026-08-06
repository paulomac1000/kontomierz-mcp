---
doc_id: guide.repository-agent-instructions
type: guide
status: active
rigor: operational
owners: [repository-maintainers]
description: Operating modes, architecture boundaries, and verification commands for agents changing kontomierz-mcp.
verification:
  - Run `.venv/bin/python -m pytest`.
  - Run the quality commands in this file.
---
# Repository instructions for agents

## Scope and precedence

These instructions apply to the complete repository. Direct user instructions and platform safety requirements have higher authority. When this file conflicts with a normative document under `docs/`, stop and identify the conflict rather than selecting the easier rule.

The selected layout is `single`; the domain profile is `mcp-server`. Read [`docs/system-architecture.md`](docs/system-architecture.md) before changing composition, lifecycle, transport, security, or dependency code. Read [`docs/tool-contract.md`](docs/tool-contract.md) before changing a public tool, manifest, error, date, money, retry, or pagination contract.

## Operating modes

- **Read-only audit:** do not modify files, branches, remote state, credentials, or external systems.
- **Implementation:** write only to the requested branch and repository. Use mock data by default.
- **Real-system verification:** requires a disposable Kontomierz account and explicit authorization. Never use personal production data for fixtures.
- **Release:** requires green hosted CI on the exact SHA and promotion of the already-tested wheel. Do not rebuild the package in the publish workflow.

## Architecture boundaries

- `config.py` is the canonical owner of process configuration. Load and validate settings before creating clients, kernels, servers, or listeners.
- `client.py` is the only module that speaks the Kontomierz HTTP protocol.
- `operations.py` owns domain validation and upstream-format conversion.
- `manifests.py` owns safety, confidentiality, retry, and idempotency claims.
- `kernel.py` is the only execution path for public tools. Transports must never call raw operations directly.
- `server.py` owns composition and official MCP SDK registration. Do not depend on private SDK fields or ambient global clients.
- `mock_backend.py` contains synthetic data only. Do not copy real account exports into the repository.

Legacy HTTP+SSE and the unauthenticated REST bridge are removed. New remote transports are forbidden until principal authentication, resource authorization, Host/Origin policy, and transport tests are implemented. Loopback Streamable HTTP and stdio are the only current transports.

## Safety contracts

Financial data is confidential even for read-only tools. Writes require the trusted operator environment gate; model-supplied arguments cannot enable or approve writes. A write timeout is an ambiguous outcome and must not be retried before reconciliation. Secrets and raw upstream bodies must not enter logs or model-visible errors.

## Setup and focused checks

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest tests/unit/test_config.py tests/unit/test_kernel.py
```

Mocked application check:

```bash
KONTOMIERZ_MOCK_DATA=1 ENABLE_WRITE_OPERATIONS=1 \
  .venv/bin/python -m pytest tests/unit tests/integration -m "not external"
```

## Full completion gate

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src/kontomierz_mcp
.venv/bin/python -m bandit -q -r src/kontomierz_mcp
.venv/bin/python -m pytest --cov=kontomierz_mcp --cov-report=term-missing --cov-report=xml
.venv/bin/python -m build
```

Build an isolated environment, install `dist/*.whl`, and rerun the non-external suite before release. Hosted CI is the authority for MCP SDK, quality-tool, exact-wheel, and container claims when the local package mirror cannot supply those dependencies.

## Test integrity

Do not weaken, skip, or delete a failing test merely to obtain green output. A test that requires a real system must use the `external` marker, remain skipped by default, and contain a concrete `TODO(real-system-agent)` describing the missing account, action, and expected evidence.

## Completion report

Report the exact revision, commands executed, passed/skipped/failed counts, checks that were unavailable, mock-versus-real evidence, behavior changes, residual risks, and any rule that remains deferred. A local pass is not a formal `ai-skills` adoption approval.
