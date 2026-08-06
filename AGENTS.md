---
doc_id: guide.repository-agent-instructions
type: guide
status: active
rigor: operational
owners: [repository-maintainers]
description: Operating modes, architecture boundaries, and verification commands for agents changing kontomierz-mcp.
verification:
  - Run `.venv/bin/python -m pytest -m "not external"`.
  - Run the quality and exact-wheel commands in this file.
---
# Repository instructions for agents

## Scope and precedence

These instructions apply to the complete repository. Direct user instructions and platform safety requirements have higher authority. Read [`docs/system-architecture.md`](docs/system-architecture.md) before changing lifecycle, transport, concurrency, security, or dependency code. Read [`docs/tool-contract.md`](docs/tool-contract.md) before changing a public tool, manifest, error, retry, date, money, or pagination contract.

## Operating modes

- **Read-only audit:** do not modify files, branches, remote state, credentials, or external systems.
- **Implementation:** write only to the requested branch and repository. Use mock data by default.
- **Real-system verification:** requires a disposable Kontomierz account and explicit authorization.
- **Release:** requires green hosted CI on the exact SHA and promotion of the tested wheel.

## Architecture boundaries

- `config.py` owns the immutable process configuration.
- `client.py` is the only module that speaks the Kontomierz HTTP protocol and must remain natively asynchronous.
- `operations.py` owns domain validation and upstream-format conversion.
- `manifests.py` owns safety, confidentiality, retry, idempotency, and concurrency claims.
- `kernel.py` is the only execution path. It owns bounded admission, running concurrency, per-target serialization, deadlines, readiness, and error normalization.
- `server.py` owns official MCP SDK registration and explicit `CallToolResult` shaping.
- `mock_backend.py` contains synthetic data only.

Legacy HTTP+SSE and the unauthenticated REST bridge are removed. Stdio and loopback Streamable HTTP are the only current transports.

## Safety contracts

Financial data is confidential. Writes require the trusted operator gate. A started write that times out or loses a response is an ambiguous outcome and must not be retried before reconciliation. A write rejected before admission has not started. Secrets and raw upstream bodies must not enter logs or model-visible errors.

`concurrent_safe=false` is enforced per `target_scope`; it is not documentation-only. Automatic retries are currently disabled for every tool. Read retry eligibility may be reported by typed errors, but the server itself does not retry.

## Setup and completion gate

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src/kontomierz_mcp
.venv/bin/python -m bandit -q -r src/kontomierz_mcp
.venv/bin/python -m pytest -m "not external" \
  --cov=kontomierz_mcp --cov-branch --cov-report=term-missing --cov-report=xml
.venv/bin/python scripts/mock_smoke.py
.venv/bin/python -m build
```

The official MCP SDK test is mandatory. Do not replace its import with `pytest.importorskip`. If the local package mirror cannot supply `mcp` v2, record that limitation and rely on hosted CI before review readiness.

Build an isolated environment, install `dist/*.whl`, and rerun the non-external suite. Tests requiring a real account must use `external` and retain a concrete `TODO(real-system-agent)`.

## Completion report

Report the exact revision, commands, pass/skip/fail counts, unavailable checks, mock-versus-real evidence, behavior changes, and residual risks. A local pass is not a formal `ai-skills` adoption approval.
