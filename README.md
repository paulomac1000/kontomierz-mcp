# Kontomierz MCP

A loopback-first MCP server for the Kontomierz personal-finance API. The server exposes 27 governed tools for accounts, transactions, budgets, schedules, reference data, charts, and wealth history.

## Security and migration status

The current candidate is **2.0.0** because it removes legacy HTTP+SSE and the unauthenticated REST bridge, changes public date, error, pagination, response-bound, authorization, and update semantics, and switches writes to the form encoding verified against the live Kontomierz API on 2026-08-08. It is not presented as formally L2+ compliant yet. Formal adoption remains blocked on provider-backed migration assessment with independent review, repository/release administration, quarantine-credential isolation evidence, and provider-verifiable build provenance.

Financial reads are confidential. Every invocation is authenticated and then authorized server-side against the exact capability, immutable configured target, and invocation resource identity. HTTP principals are read-only by default through `MCP_HTTP_ALLOWED_CAPABILITIES=read`. Mutations require both an explicitly allowed HTTP capability class (for HTTP callers) and `ENABLE_WRITE_OPERATIONS=1` from the trusted server operator. Destructive operations are narrower on both transports: stdio requires exact capability IDs in `MCP_STDIO_ALLOWED_DESTRUCTIVE_CAPABILITIES` and exact resource IDs in `MCP_STDIO_ALLOWED_DESTRUCTIVE_RESOURCES`; HTTP additionally requires the corresponding `MCP_HTTP_ALLOWED_DESTRUCTIVE_*` allowlists. A model argument cannot establish identity, authorization, or write enablement.

The server does **not** advertise `requires_confirmation=true` because no independent server-side approval authority exists yet. A started mutation with an uninterpretable outcome is never declared safely retryable. Each invocation emits one structured server-side audit record containing principal, exact capability, target identity, resource identity, policy decision, operator-gate decision, dependency state, result category, cancellation/saturation state, and correlation ID; credentials and protected response bodies are excluded. The audit logger owns an INFO-capable sink independent from `LOG_LEVEL` and follows an explicit result-preserving fail-open policy.

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

Ordinary stdio writes require `ENABLE_WRITE_OPERATIONS=1`. Destructive stdio operations additionally require exact capability and resource allowlists:

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

Every remote HTTP request except `/health/live` must send `Authorization: Bearer <MCP_HTTP_AUTH_TOKEN>`. The token is mapped server-side to `MCP_HTTP_PRINCIPAL`, so the model cannot choose its own principal. The principal is authorized against the exact tool, configured target, resolved resource identity, normalized argument digest, and capability policy, then revalidated immediately before operation I/O.

The MCP endpoint is `/mcp`; liveness remains public at `/health/live`. Readiness at `/health/ready` requires the same Bearer authentication because a cache miss may trigger a bounded upstream probe. Non-loopback binding is rejected. The HTTP adapter explicitly configures Host and Origin policy, stateless mode, and a bounded request body.

To permit ordinary HTTP writes, add `write` to `MCP_HTTP_ALLOWED_CAPABILITIES` **and** enable `ENABLE_WRITE_OPERATIONS=1`. To permit destructive HTTP operations, also add `destructive`, then explicitly allow each destructive capability and exact resource:

```bash
export MCP_HTTP_ALLOWED_CAPABILITIES=read,destructive
export MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES=destroy_wallet
export MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES=wallet:123
export ENABLE_WRITE_OPERATIONS=1
```

Wildcards are not accepted for destructive resources. Authentication alone never grants write access.

Write bodies use `application/x-www-form-urlencoded`, matching the live API contract verified on 2026-08-08; JSON-encoded writes are rejected upstream. Public tool dates accept ISO `YYYY-MM-DD` only and budget months accept `YYYY-MM` only. Localized upstream `DD-MM-YYYY` values are produced internally after public validation. Real-backend configuration rejects `KONTOMIERZ_BODY_MODE=json`. A non-mock API target must be an absolute HTTPS URL without embedded credentials, query, or fragment.

Successful MCP responses expose an opaque `target_ref` plus `target_scope` in `_meta`; the internal credential-derived target identity is retained only for authorization and audit.

## Reproducible dependency graphs

`requirements/` contains exact Linux x64 wheel locks for runtime and development on Python 3.11, 3.12, and 3.13, plus a shared build-tool lock. Each requirement is pinned to an exact version and SHA-256 wheel digest. CI installs these files with `--require-hashes --no-deps --only-binary=:all:` and runs `pip check`.

The exact release artifact uses the Python 3.12 runtime lock. That lock and the build lock are included in the checksummed release bundle. Package metadata pins the production MCP SDK to the tested `mcp==2.0.0` lane instead of claiming compatibility with untested future 2.x releases.

## Docker and release promotion

Docker consumes the already-built application wheel, hash-locked runtime wheelhouse, and copied runtime lock that CI verifies before the image build. The image runs as non-root and is built with `org.opencontainers.image.revision=<full source SHA>`; CI verifies that label and smokes the exact image before archiving it.

Release publication uses three distinct trust stages:

1. `verify-artifact` is read-only. It proves default-branch ancestry, checks the protected `release` environment configuration, downloads the closed CI bundle, and verifies checksums/source identity without executing candidate content.
2. `quarantine` remains unprivileged with respect to production. It loads and smokes the exact CI image, then pushes it to an **isolated non-GHCR quarantine registry**, resolves an immutable digest, pulls that exact digest, rechecks the source-revision label, and smokes it again.
3. `publish` runs behind the protected `release` environment. It does not checkout candidate code, download the CI archive, `docker load`, or `docker run` candidate content. It promotes only the immutable quarantine digest to production GHCR with registry tooling, verifies the production digest, and emits a promotion attestation.

Repository administrators must provide `QUARANTINE_REGISTRY` and `QUARANTINE_REPOSITORY` variables plus `QUARANTINE_USERNAME`/`QUARANTINE_TOKEN` secrets. The quarantine registry must not be `ghcr.io`, and its credential must be scoped so it cannot mutate the production package. That last credential-scope property requires provider/administrator evidence and remains an explicit external gate rather than a source-code assertion.

## Tests

A plain pytest run excludes live/provider evidence by default:

```bash
.venv/bin/python -m pytest
```

The default suite uses synthetic data. The official MCP SDK test is mandatory and fails collection when the SDK is absent.

The live Kontomierz contract suite requires a repository `.env` containing the real API key **and both** explicit opt-ins, and should be run only against a disposable account:

```bash
KONTOMIERZ_EXTERNAL_TESTS=1 \
KONTOMIERZ_ALLOW_REAL_MUTATIONS=1 \
.venv/bin/python -m pytest -o addopts='' -m external tests/external/test_real_kontomierz_contract.py
```

Those tests use unique descriptions, captured IDs, bounded reconciliation over both paid and unpaid schedule groups, and a final cleanup guard. The run fails if schedule/transaction namespace cleanup or budget snapshot cleanup cannot be confirmed. Provider/repository acceptance placeholders in `tests/external/test_production_evidence.py` remain intentionally failing until the corresponding external authority exists.

## Standards authority and contracts

The trusted standards authority is declared once in [`trusted-executable-sources.lock.yaml`](trusted-executable-sources.lock.yaml), currently at exact `paulomac1000/ai-skills` revision `32b699c75eaf4edac00982fea181daebaba40114`. The lock also binds every trusted executable used by CI to a SHA-256 digest. CI resolves the authority from this canonical lock, validates the lock from the trusted checkout, runs consumer-trust hygiene, and then executes the pinned AFDS/AGENTS/CI/MCP validators.

- [`trusted-executable-sources.lock.yaml`](trusted-executable-sources.lock.yaml) — immutable authority coordinates and trusted executable digests
- [`upstream-contract.yaml`](upstream-contract.yaml) — machine-readable observed Kontomierz boundary
- [`live-backend-test-policy.yaml`](live-backend-test-policy.yaml) — fail-closed live-test safety floor
- [`docs/system-architecture.md`](docs/system-architecture.md)
- [`docs/tool-contract.md`](docs/tool-contract.md)
- [`docs/upstream-api.md`](docs/upstream-api.md)
- [`docs/ai-skills-gap-assessment.md`](docs/ai-skills-gap-assessment.md)
- [`docs/production-readiness.md`](docs/production-readiness.md)

## Compatibility note

Version 2.0.0 is intentionally incompatible with the legacy 1.0.x transport and response surface. Public dates use ISO `YYYY-MM-DD`; budget months use `YYYY-MM`; pagination exposes only continuation hints; update tools distinguish omission (`None`) from an explicit empty text value; destructive stdio calls require exact server-owned allowlists; and successful `_meta` identifies the authorized target through an opaque `target_ref` rather than exposing internal target identity.
