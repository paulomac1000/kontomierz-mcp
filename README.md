# Kontomierz MCP

A loopback-first MCP server for the Kontomierz personal-finance API. The server exposes 27 governed tools for accounts, transactions, budgets, schedules, reference data, charts, and wealth history.

## Security and migration status

The current candidate is **2.0.0** because it intentionally removes legacy HTTP+SSE and the unauthenticated REST bridge and changes public date, error, pagination, and update semantics. It is not presented as formally L2+ compliant yet. Formal adoption remains blocked on reviewed hash locks, a provider-backed migration assessment, independent approval, and contract tests against a disposable real Kontomierz account.

Financial reads are confidential. Mutations are denied unless `ENABLE_WRITE_OPERATIONS=1` is set by the trusted server operator. A model argument cannot enable writes. The server does **not** advertise `requires_confirmation=true` because no independent server-side approval authority exists yet; any future confirmation claim must be backed by a trusted approval record rather than a model-controlled argument. A started mutation with an uninterpretable outcome is never declared safely retryable.

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

## Authenticated loopback Streamable HTTP

```bash
export MCP_HTTP_AUTH_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export MCP_HTTP_PRINCIPAL="local-operator"
KONTOMIERZ_MOCK_DATA=1 \
MCP_TRANSPORT=streamable-http \
MCP_HOST=127.0.0.1 \
MCP_PORT=9101 \
.venv/bin/kontomierz-mcp
```

Every request to the MCP application must send `Authorization: Bearer <MCP_HTTP_AUTH_TOKEN>`. The token is mapped server-side to `MCP_HTTP_PRINCIPAL`, so the model cannot choose its own principal. The MCP endpoint is `/mcp`; liveness and readiness remain unauthenticated at `/health/live` and `/health/ready`. Non-loopback binding is rejected.

## Docker

Docker consumes an already-built wheel and wheelhouse rather than resolving dependencies during the image build. The build verifies `dist/SHA256SUMS` before installing the wheel:

```bash
.venv/bin/python -m pip wheel --no-deps --no-build-isolation . --wheel-dir dist
mkdir -p dist/wheelhouse
.venv/bin/python -m pip download --dest dist/wheelhouse dist/kontomierz_mcp-*.whl
(cd dist && find . -type f -name '*.whl' -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
docker build -t kontomierz-mcp:local .
```

The image runs as a non-root user and defaults to stdio. Hosted CI builds and smoke-tests the exact image archive under read-only permissions. The protected publish workflow only verifies, loads, tags, and pushes that closed archive; it does not checkout or run candidate source after release write permissions are granted.

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
