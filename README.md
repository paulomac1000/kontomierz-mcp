# Kontomierz MCP

A loopback-first MCP server for the Kontomierz personal-finance API. The server exposes 27 governed tools for accounts, transactions, budgets, schedules, reference data, charts, and wealth history.

## Security and migration status

The current candidate is **2.0.0** because it intentionally removes legacy HTTP+SSE and the unauthenticated REST bridge and changes public date, error, pagination, and update semantics. It is not presented as formally L2+ compliant yet. Formal adoption remains blocked on hosted exact-revision evidence, reviewed hash locks, a provider-backed migration assessment, and contract tests against a disposable real Kontomierz account.

Financial reads are confidential. Mutations are denied unless `ENABLE_WRITE_OPERATIONS=1` is set by the trusted server operator. A model argument cannot enable writes. A started mutation with an uninterpretable outcome is never declared safely retryable.

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
MCP_TRANSPORT=streamable-http \
MCP_HOST=127.0.0.1 \
MCP_PORT=9101 \
.venv/bin/kontomierz-mcp
```

The MCP endpoint is `/mcp`; liveness and readiness are `/health/live` and `/health/ready`. `0.0.0.0` is rejected until principal authentication and resource authorization are implemented.

## Docker

Docker consumes an already-built wheel and wheelhouse rather than resolving dependencies during the image build:

```bash
.venv/bin/python -m build
mkdir -p dist/wheelhouse
.venv/bin/python -m pip download --dest dist/wheelhouse dist/kontomierz_mcp-*.whl
docker build -t kontomierz-mcp:local .
docker run --rm -i --env-file .env kontomierz-mcp:local
```

The image runs as a non-root user and defaults to stdio. Hosted CI preserves the exact tested image archive; protected release promotion loads that archive rather than rebuilding it.

## Tests

```bash
.venv/bin/python -m pytest -m "not external"
```

The default suite uses synthetic data. The official MCP SDK test is mandatory and fails collection when the SDK is absent; it is not silently skipped. Tests marked `external` describe evidence still needed from a disposable real account. See [`AGENTS.md`](AGENTS.md) for the full gate.

## Contracts and architecture

- [`docs/system-architecture.md`](docs/system-architecture.md)
- [`docs/tool-contract.md`](docs/tool-contract.md)
- [`docs/upstream-api.md`](docs/upstream-api.md)
- [`docs/ai-skills-gap-assessment.md`](docs/ai-skills-gap-assessment.md)

## Compatibility note

Version 2.0.0 is intentionally incompatible with the 1.x transport and response surface. Public dates use ISO `YYYY-MM-DD`; budget months use `YYYY-MM`; pagination exposes only continuation hints; and update tools distinguish omission (`None`) from an explicit empty text value.
