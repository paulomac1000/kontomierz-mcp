# Kontomierz MCP

A loopback-first MCP server for the Kontomierz personal-finance API. The server exposes 27 tools for accounts, transactions, budgets, schedules, reference data, charts, and wealth history.

## Security status

The server is **not presented as formally L2+ compliant yet**. This branch removes legacy SSE and the unauthenticated REST bridge, centralizes all execution in one kernel, and defaults to stdio. Streamable HTTP is accepted only on loopback. Formal adoption remains blocked on hosted exact-artifact evidence and contract tests against a disposable real Kontomierz account.

Financial reads are confidential. Mutations are denied unless `ENABLE_WRITE_OPERATIONS=1` is set by the trusted server operator. A model argument cannot enable writes.

## Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
```

For synthetic local development:

```bash
KONTOMIERZ_MOCK_DATA=1 .venv/bin/kontomierz-mcp
```

The default transport is stdio. Configure an MCP host to execute `.venv/bin/kontomierz-mcp` with `KONTOMIERZ_API_KEY` in its trusted environment.

## Loopback Streamable HTTP

```bash
KONTOMIERZ_MOCK_DATA=1 \
MCP_TRANSPORT=http \
MCP_HOST=127.0.0.1 \
MCP_PORT=9101 \
.venv/bin/kontomierz-mcp
```

The MCP endpoint is `/mcp`; liveness and readiness are `/health/live` and `/health/ready`. `0.0.0.0` is rejected until real authentication and authorization are implemented.

## Docker

Docker consumes an already-built wheel rather than rebuilding the package:

```bash
.venv/bin/python -m build
mkdir -p dist/wheelhouse
.venv/bin/python -m pip download --dest dist/wheelhouse dist/kontomierz_mcp-*.whl
docker build -t kontomierz-mcp:local .
docker run --rm -i --env-file .env kontomierz-mcp:local
```

The image runs as a non-root user and defaults to stdio.

## Tests

```bash
.venv/bin/python -m pytest -m "not external"
```

The default suite uses only synthetic data. Tests marked `external` describe the evidence still needed from a disposable real account. See [`AGENTS.md`](AGENTS.md) for the full gate.

## Contracts and architecture

- [`docs/system-architecture.md`](docs/system-architecture.md)
- [`docs/tool-contract.md`](docs/tool-contract.md)
- [`docs/upstream-api.md`](docs/upstream-api.md)
- [`docs/ai-skills-gap-assessment.md`](docs/ai-skills-gap-assessment.md)

## Compatibility note

Public dates use ISO `YYYY-MM-DD` and budget months use `YYYY-MM`. The upstream adapter converts them to Kontomierz's historical `DD-MM-YYYY` representation. The legacy `/sse` and `/api/tools/*` endpoints are intentionally removed.
