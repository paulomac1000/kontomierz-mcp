# Kontomierz MCP

A loopback-first MCP server for the Kontomierz personal-finance API. The server exposes 27 governed tools for accounts, transactions, budgets, schedules, reference data, charts, and wealth history.

## Security and migration status

The current candidate is **2.0.0** because it removes legacy HTTP+SSE and the unauthenticated REST bridge, changes public date, error, pagination, response-bound, and update semantics, and switches write bodies to the form encoding verified against the live Kontomierz API on 2026-08-08. It is not presented as formally L2+ compliant yet. Formal adoption remains blocked on provider-backed migration assessment with independent approval, protected release-environment administration, provider-verifiable build provenance, and independent approval of the immutable revision.

Financial reads are confidential. Every invocation is authenticated and then authorized server-side against the exact capability, immutable configured target, and invocation resource identity. HTTP principals are read-only by default through `MCP_HTTP_ALLOWED_CAPABILITIES=read`. Mutations require both an explicitly allowed HTTP capability class (for HTTP callers) and `ENABLE_WRITE_OPERATIONS=1` from the trusted server operator. Destructive operations are narrower on both transports: stdio requires exact capability IDs in `MCP_STDIO_ALLOWED_DESTRUCTIVE_CAPABILITIES` and exact resource IDs in `MCP_STDIO_ALLOWED_DESTRUCTIVE_RESOURCES`; HTTP additionally requires the corresponding `MCP_HTTP_ALLOWED_DESTRUCTIVE_*` allowlists. A model argument cannot establish identity, authorization, or write enablement.

The server does **not** advertise `requires_confirmation=true` because no independent server-side approval authority exists yet; any future confirmation claim must be backed by a trusted approval record rather than a model-controlled argument. A started mutation with an uninterpretable outcome is never declared safely retryable. Each invocation emits one structured server-side audit record with principal, exact capability, target identity, resource identity, policy decision, operator-gate decision, dependency state, result category, cancellation/saturation state, and correlation ID; credentials and protected response bodies are excluded. The audit logger owns an INFO-capable sink independent from `LOG_LEVEL`. Audit sink failures are result-preserving fail-open because an audit failure after a started mutation must not turn a completed write into a misleading retryable application failure; a minimal stderr failure signal is attempted instead.

Public text inputs have UTF-8 byte limits before upstream I/O. Successful upstream bodies are streamed with a 4 MiB decoded-body limit, and every tool manifest has a final response budget (1 MiB by default). Oversized reads fail closed; a completed mutation whose representation exceeds the tool budget returns a small reconciliation marker instead of a retry-provoking error.

## Install

The production/tested dependency locks target Linux x64 and Python 3.11, 3.12, or 3.13. Create a virtual environment and install the matching exact-wheel development graph plus the shared build graph before installing the project without dependency resolution:

```bash
python3 -m venv .venv
PYTAG="$(.venv/bin/python -c 'import sys; print(f"py{sys.version_info.major}{sys.version_info.minor}")')"
.venv/bin/python -m pip install --no-deps --only-binary=:all: --require-hashes -r "requirements/dev-linux-x64-${PYTAG}.lock"
.venv/bin/python -m pip install --no-deps --only-binary=:all: --require-hashes -r requirements/build-linux-x64.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m pip check
cp .env.example .env
```

For synthetic local development:

```bash
KONTOMIERZ_MOCK_DATA=1 .venv/bin/kontomierz-mcp
```

The default transport is stdio. Configure an MCP host to execute `.venv/bin/kontomierz-mcp` with `KONTOMIERZ_API_KEY` in its trusted environment.

Ordinary stdio writes still require `ENABLE_WRITE_OPERATIONS=1`. Destructive stdio operations additionally require an exact capability and exact resource allowlist. For shell setup before starting the server, export the policy variables so the child process inherits them:

```bash
export MCP_STDIO_ALLOWED_DESTRUCTIVE_CAPABILITIES=destroy_wallet
export MCP_STDIO_ALLOWED_DESTRUCTIVE_RESOURCES=wallet:123
export ENABLE_WRITE_OPERATIONS=1
```

Without both stdio destructive allowlists, destructive tools remain denied even when the global write gate is enabled.

## Authenticated loopback Streamable HTTP

```bash
export MCP_HTTP_AUTH_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export MCP_HTTP_PRINCIPAL="local-operator"
KONTOMIERZ_MOCK_DATA=1 \
MCP_TRANSPORT=streamable-http \
MCP_HOST=127.0.0.1 \
MCP_PORT=9101 \
MCP_HTTP_ALLOWED_CAPABILITIES=read \
MCP_HTTP_MAX_REQUEST_BODY_BYTES=1048576 \
.venv/bin/kontomierz-mcp
```

Every remote HTTP request except `/health/live` must send `Authorization: Bearer <MCP_HTTP_AUTH_TOKEN>`. The token is mapped server-side to `MCP_HTTP_PRINCIPAL`, so the model cannot choose its own principal. The principal is then authorized against the exact tool, configured target, resolved resource identity, normalized argument digest, and capability policy. The policy is revalidated immediately before operation I/O.

The MCP endpoint is `/mcp`; liveness remains public at `/health/live`. Readiness at `/health/ready` requires the same Bearer authentication because a cache miss may trigger a bounded upstream Kontomierz probe. Non-loopback binding is rejected. The HTTP adapter explicitly configures Host and Origin policy, stateless mode, and a bounded request body instead of relying on SDK defaults.

To permit ordinary HTTP writes, add `write` to `MCP_HTTP_ALLOWED_CAPABILITIES` **and** enable `ENABLE_WRITE_OPERATIONS=1`. To permit destructive HTTP operations, also add `destructive`, then explicitly allow each destructive capability and exact resource, for example:

```bash
export MCP_HTTP_ALLOWED_CAPABILITIES=read,destructive
export MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES=destroy_wallet
export MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES=wallet:123
export ENABLE_WRITE_OPERATIONS=1
```

Wildcards are not accepted for destructive resources. Authentication alone never grants write access.

Write bodies use `application/x-www-form-urlencoded` encoding, matching the live API contract verified on 2026-08-08; JSON-encoded write bodies are rejected upstream. Public tool dates accept ISO `YYYY-MM-DD` only and budget months accept `YYYY-MM` only. Localized upstream `DD-MM-YYYY` values are produced internally after public validation. Real-backend configuration rejects `KONTOMIERZ_BODY_MODE=json` instead of preserving a known-broken compatibility mode. A non-mock API target must be an absolute HTTPS URL.

Successful MCP responses expose an opaque `target_ref` plus `target_scope` in `_meta`; the internal credential-derived target identity is retained only for authorization and audit, not returned to the model.

## Reproducible dependency graphs

`requirements/` contains exact Linux x64 wheel locks for runtime and development on Python 3.11, 3.12, and 3.13, plus a shared build-tool lock. Each requirement is pinned to an exact version and SHA-256 wheel digest. CI installs these files with `--require-hashes --no-deps --only-binary=:all:` and then runs `pip check`, so acceptance paths cannot silently resolve undeclared transitive dependencies.

The exact release artifact uses the Python 3.12 runtime lock. That lock and the build lock are copied into the release bundle and covered by its checksum manifest. Package metadata pins the production MCP SDK to the tested `mcp==2.0.0` lane rather than claiming compatibility with untested future 2.x releases.

## Docker

Docker consumes an already-built wheel, the hash-locked runtime wheelhouse, and the same copied runtime lock that CI verifies before the image build. `dist/SHA256SUMS` covers the wheelhouse, application wheel, and `dist/runtime-linux-x64-py312.lock`; the Dockerfile verifies that manifest and installs that exact copied lock with `--require-hashes` before installing the application wheel:

```bash
.venv/bin/python -m pip wheel --no-deps --no-build-isolation . --wheel-dir dist
mkdir -p dist/wheelhouse
.venv/bin/python -m pip download --no-deps --only-binary=:all: --require-hashes \
  --dest dist/wheelhouse -r requirements/runtime-linux-x64-py312.lock
cp requirements/runtime-linux-x64-py312.lock dist/
(
  cd dist
  find . -type f \( -name '*.whl' -o -name 'runtime-linux-x64-py312.lock' \) \
    -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS
)
docker build -t kontomierz-mcp:local .
```

The image runs as a non-root user and defaults to stdio. Hosted CI builds and smoke-tests the exact image archive under read-only permissions. The protected publish workflow verifies that the candidate SHA is reachable from the trusted default branch and refuses to continue unless the repository `release` environment already has required deployment reviewers, self-review prevention, and protected-branch deployment policy. It then only verifies, loads, tags, and pushes the closed archive; it does not execute candidate source after release write permissions are granted.

## Tests

A plain pytest run excludes live/provider evidence by default:

```bash
.venv/bin/python -m pytest
```

The default suite uses synthetic data. The official MCP SDK test is mandatory and fails collection when the SDK is absent; it is not silently skipped.

The live Kontomierz contract suite is intentionally harder to start. It requires a repository `.env` containing the real API key **and both** explicit opt-ins, and should be run only against a disposable account after reviewing its write/delete behavior:

```bash
KONTOMIERZ_EXTERNAL_TESTS=1 \
KONTOMIERZ_ALLOW_REAL_MUTATIONS=1 \
.venv/bin/python -m pytest -o addopts='' -m external tests/external/test_real_kontomierz_contract.py
```

Those tests use unique descriptions, captured IDs, bounded reconciliation over both paid and unpaid schedule groups, and a final safety guard. The run fails if schedule/transaction namespace cleanup or the budget ID-snapshot cleanup cannot be confirmed; an unverified cleanup is never silently converted into success. Provider/repository acceptance placeholders in `tests/external/test_production_evidence.py` remain intentionally failing until the corresponding external authority exists; they are not fabricated or silently skipped. See [`docs/production-readiness.md`](docs/production-readiness.md) and [`AGENTS.md`](AGENTS.md) for the handoff and full gate.

## Contracts and architecture

- [`upstream-contract.yaml`](upstream-contract.yaml) — machine-readable observed Kontomierz boundary
- [`live-backend-test-policy.yaml`](live-backend-test-policy.yaml) — fail-closed live-test safety floor
- [`docs/system-architecture.md`](docs/system-architecture.md)
- [`docs/tool-contract.md`](docs/tool-contract.md)
- [`docs/upstream-api.md`](docs/upstream-api.md)
- [`docs/ai-skills-gap-assessment.md`](docs/ai-skills-gap-assessment.md)

## Compatibility note

Version 2.0.0 is intentionally incompatible with the legacy 1.0.x transport and response surface. Public dates use ISO `YYYY-MM-DD`; budget months use `YYYY-MM`; pagination exposes only continuation hints; update tools distinguish omission (`None`) from an explicit empty text value; destructive stdio calls now require exact server-owned allowlists; and successful `_meta` identifies the authorized target through an opaque `target_ref` rather than exposing internal target identity.
