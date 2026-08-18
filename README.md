# Kontomierz-MCP

[![CI](https://github.com/paulomac1000/kontomierz-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/paulomac1000/kontomierz-mcp/actions/workflows/ci.yml)
[![Docker](https://github.com/paulomac1000/kontomierz-mcp/actions/workflows/publish.yml/badge.svg)](https://github.com/paulomac1000/kontomierz-mcp/actions/workflows/publish.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

MCP (Model Context Protocol) server for [Kontomierz.pl](https://kontomierz.pl/) — a Polish personal-finance platform. It exposes 27 tools for accounts, transactions, budgets, scheduled payments, reference data, charts, and wealth history so MCP-compatible assistants can work with Kontomierz through one local server.

Version **2.0.0** replaces the old SSE/REST bridge with **stdio** and authenticated, loopback-only **Streamable HTTP**. Public dates are ISO `YYYY-MM-DD`, budget months are `YYYY-MM`, and write operations are disabled unless the server operator explicitly enables them.

## Requirements

- Python 3.11+ for local use. The repository's exact Linux x64 dependency locks cover Python 3.11, 3.12, and 3.13.
- A Kontomierz.pl account with an [API key](https://kontomierz.pl/profil/api), unless using the deterministic mock backend.
- Docker only if you want to reproduce or run the exact container artifact.

## Quick Start

### 1. Install and configure

```bash
git clone https://github.com/paulomac1000/kontomierz-mcp.git
cd kontomierz-mcp

python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .

cp .env.example .env
# Edit .env and set KONTOMIERZ_API_KEY
```

The server reads `.env` from the current working directory without overriding variables already present in the process environment.

For a zero-I/O local demo, no real API key is needed:

```bash
KONTOMIERZ_MOCK_DATA=1 kontomierz-mcp
```

### 2. Run with stdio

Stdio is the default and recommended transport for a local MCP client:

```bash
kontomierz-mcp
```

Read tools are available immediately. Ordinary writes require the independent operator gate:

```bash
export ENABLE_WRITE_OPERATIONS=1
kontomierz-mcp
```

Destructive tools require the write gate **and** exact server-owned capability/resource allowlists. For example:

```bash
export ENABLE_WRITE_OPERATIONS=1
export MCP_STDIO_ALLOWED_DESTRUCTIVE_CAPABILITIES=destroy_wallet
export MCP_STDIO_ALLOWED_DESTRUCTIVE_RESOURCES=wallet:123
kontomierz-mcp
```

Wildcards are not accepted for destructive resources.

### 3. Connect an MCP client

A stdio client can start the executable directly. For example, a Claude Desktop-style configuration is:

```json
{
  "mcpServers": {
    "kontomierz": {
      "command": "/absolute/path/to/kontomierz-mcp/.venv/bin/kontomierz-mcp",
      "env": {
        "KONTOMIERZ_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

Use your client's trusted environment/secret mechanism where available. Do not expose the API key through tool arguments. Add `ENABLE_WRITE_OPERATIONS=1` to the trusted process environment only when writes are intended.

## Streamable HTTP

HTTP mode is optional. It is deliberately restricted to loopback and requires Bearer authentication.

```bash
export MCP_TRANSPORT=streamable-http
export MCP_HOST=127.0.0.1
export MCP_PORT=9101
export MCP_HTTP_AUTH_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export MCP_HTTP_PRINCIPAL=local-operator
export MCP_HTTP_ALLOWED_CAPABILITIES=read

kontomierz-mcp
```

Endpoints:

| Endpoint | Authentication | Purpose |
|---|---|---|
| `POST /mcp` | Bearer token required | Streamable HTTP MCP endpoint |
| `GET /health/live` | Public | Process liveness only; no upstream I/O |
| `GET /health/ready` | Bearer token required | Bounded dependency-aware readiness |

Verify health:

```bash
curl http://127.0.0.1:9101/health/live
curl -H "Authorization: Bearer $MCP_HTTP_AUTH_TOKEN" \
  http://127.0.0.1:9101/health/ready
```

HTTP principals are read-only by default. To allow ordinary writes, both the HTTP capability policy and the global write gate must allow them:

```bash
export MCP_HTTP_ALLOWED_CAPABILITIES=read,write
export ENABLE_WRITE_OPERATIONS=1
```

Destructive HTTP calls additionally require `destructive` plus exact capability and resource allowlists:

```bash
export MCP_HTTP_ALLOWED_CAPABILITIES=read,write,destructive
export MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES=destroy_wallet
export MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES=wallet:123
export ENABLE_WRITE_OPERATIONS=1
```

Authentication never grants write access by itself.

## Docker

The Dockerfile intentionally does **not** rebuild the project from arbitrary source. It consumes the verified `dist/` wheel, runtime wheelhouse, runtime lock, checksums, and `SOURCE_REVISION` produced by the exact-artifact path, then runs the server as a non-root user.

To reproduce the CI image locally, use Python 3.12 and the repository helper with an `ai-skills` checkout at the exact revision recorded in `trusted-executable-sources.lock.yaml`:

```bash
.venv/bin/python scripts/local_exact_gate.py --ai-skills-root ../ai-skills
```

That command runs the repository-owned standards/quality checks, materializes the exact artifact set, and builds `kontomierz-mcp:<git-sha>`. See [Production readiness](docs/production-readiness.md) for the complete reproducible path.

For Streamable HTTP inside Docker, ordinary `-p` publishing is not sufficient because the server is required to bind loopback. On Linux, use host networking or an equivalent loopback bridge. Stdio needs no network exposure.

## Available Tools (27)

### Accounts

| Tool | Risk | Description |
|---|---|---|
| `list_accounts` | READ | List bank accounts and wallets with balances |
| `create_wallet` | WRITE | Create a cash wallet |
| `update_wallet` | WRITE | Update a cash wallet |
| `destroy_wallet` | DESTRUCTIVE | Delete a cash wallet |

### Transactions

| Tool | Risk | Description |
|---|---|---|
| `list_transactions` | READ | List transactions with pagination and filters |
| `get_transaction` | READ | Get one transaction |
| `create_transaction` | WRITE | Create a transaction |
| `update_transaction` | WRITE | Update a transaction |
| `delete_transaction` | DESTRUCTIVE | Delete a transaction |

### Budgets

| Tool | Risk | Description |
|---|---|---|
| `list_budgets` | READ | List budgets for a month |
| `create_budget` | WRITE | Create a category or category-group budget |
| `update_budget` | WRITE | Update a budget limit |
| `delete_budget` | DESTRUCTIVE | Delete a budget |
| `copy_budgets_from_last_month` | WRITE | Copy the previous month's budgets |

### Schedules

| Tool | Risk | Description |
|---|---|---|
| `list_scheduled_transactions` | READ | List scheduled payment occurrences |
| `get_schedule` | READ | Get one schedule definition |
| `create_schedule` | WRITE | Create a payment schedule |
| `update_schedule` | WRITE | Update a payment schedule |
| `delete_schedule` | DESTRUCTIVE | Delete a payment schedule |
| `mark_schedule_paid` | WRITE | Mark an occurrence as paid |
| `mark_schedule_unpaid` | WRITE | Mark an occurrence as unpaid |

### Reference data

| Tool | Risk | Description |
|---|---|---|
| `list_categories` | READ | List the category tree |
| `list_tags` | READ | List user tags |
| `list_currencies` | READ | List currencies |

### Charts & wealth

| Tool | Risk | Description |
|---|---|---|
| `get_pie_chart` | READ | Get transaction breakdown data |
| `list_wealth_points` | READ | List wealth-history points |

### Introspection

| Tool | Risk | Description |
|---|---|---|
| `describe_kontomierz_capabilities` | READ | Describe the governed tool catalog and active policy state |

The governed catalog in `src/kontomierz_mcp/tool_definitions*.py` is the source of truth for signatures and descriptions. `tools/list` exposes the public schemas.

## Public Contract

Version 2.0.0 intentionally tightens the MCP surface:

- tool input objects are closed (`additionalProperties: false`);
- scalar types are strict rather than cross-coerced;
- public dates use `YYYY-MM-DD` and budget months use `YYYY-MM`;
- localized Kontomierz `DD-MM-YYYY` conversion is adapter-internal;
- public result metadata exposes an opaque `target_ref`, not the internal credential-derived target identity;
- response and upstream-body sizes are bounded;
- mutation failures are classified conservatively.

A confirmed HTTP 201 create that returns no stable identity is not guessed from non-unique fields. Observed budget/schedule cases return:

```json
{"created": true, "reconciliation_required": true}
```

The caller must reconcile before a dependent mutation. If completion itself is uncertain — for example after a timeout, transport loss, ambiguous server failure, or malformed/oversized successful mutation response — the operation returns `AMBIGUOUS_OUTCOME` and is not automatically retried.

See [Tool contract](docs/tool-contract.md) and [Upstream API](docs/upstream-api.md) for the detailed behavior.

## Configuration

All configuration is via environment variables; `.env.example` is the complete template.

### Core

| Variable | Default | Description |
|---|---:|---|
| `KONTOMIERZ_API_KEY` | — | Required for the real backend |
| `KONTOMIERZ_MOCK_DATA` | `0` | Use deterministic in-memory data instead of Kontomierz |
| `KONTOMIERZ_API_BASE_URL` | `https://secure.kontomierz.pl/k4` | Upstream API base URL; real targets must be HTTPS |
| `KONTOMIERZ_API_TIMEOUT` | `30` | Upstream request timeout in seconds |
| `KONTOMIERZ_BODY_MODE` | `form` | Real writes are form-encoded; real `json` mode is rejected |
| `MCP_TRANSPORT` | `stdio` | `stdio`, `http`, or `streamable-http` |
| `MCP_HOST` | `127.0.0.1` | HTTP bind host; non-loopback HTTP is rejected |
| `MCP_PORT` | `9101` | Streamable HTTP port |
| `ENABLE_WRITE_OPERATIONS` | `0` | Independent operator gate for mutations |
| `LOG_LEVEL` | `INFO` | Application log verbosity |

### Runtime bounds

| Variable | Default | Description |
|---|---:|---|
| `MCP_MAX_CONCURRENCY` | `8` | Maximum running dependency calls |
| `MCP_MAX_PENDING_INVOCATIONS` | `16` | Maximum admitted running + queued invocations |
| `MCP_READINESS_TIMEOUT` | `5` | Readiness dependency-probe timeout |
| `MCP_READINESS_CACHE_SECONDS` | `10` | Readiness cache duration |
| `MCP_HTTP_MAX_REQUEST_BODY_BYTES` | `1048576` | HTTP request-body limit; hard maximum is 4 MiB |

### Authorization

| Variable | Purpose |
|---|---|
| `MCP_STDIO_ALLOWED_DESTRUCTIVE_CAPABILITIES` | Exact destructive capability IDs allowed over stdio |
| `MCP_STDIO_ALLOWED_DESTRUCTIVE_RESOURCES` | Exact destructive resource IDs allowed over stdio |
| `MCP_HTTP_AUTH_TOKEN` | Required high-entropy Bearer token for HTTP |
| `MCP_HTTP_PRINCIPAL` | Stable server-owned identity mapped to the HTTP token |
| `MCP_HTTP_ALLOWED_CAPABILITIES` | HTTP capability classes; defaults to `read` |
| `MCP_HTTP_ALLOWED_DESTRUCTIVE_CAPABILITIES` | Exact destructive capability IDs allowed over HTTP |
| `MCP_HTTP_ALLOWED_DESTRUCTIVE_RESOURCES` | Exact destructive resource IDs allowed over HTTP |

## Security

- **Read-only by default.** Writes require `ENABLE_WRITE_OPERATIONS=1`; HTTP also requires the corresponding capability class.
- **Exact destructive authorization.** Destructive operations need explicit capability and resource allowlists; wildcard resources are rejected.
- **Loopback-only HTTP.** Remote HTTP binding is rejected. `/mcp` and `/health/ready` require Bearer authentication.
- **Server-owned identity.** Principals, target identity, capability policy, resource allowlists, and write enablement cannot come from model-controlled tool arguments.
- **No automatic mutation retries.** Completion-uncertain writes remain `AMBIGUOUS_OUTCOME` until reconciled.
- **Bounded data.** Inputs, request bodies, upstream responses, tool responses, and audit events are bounded.
- **Protected audit.** Invocation audit records exclude API keys, Bearer tokens, raw protected results, and raw arguments.

The project is designed for a single configured Kontomierz account. Public multi-tenant hosting and cross-account target selection are not supported.

## Testing and Development

For ordinary development:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src/kontomierz_mcp
python -m bandit -q -r src/kontomierz_mcp
```

Plain `pytest` excludes the `external` evidence suite. Coverage is enforced at 85%.

Hosted CI also exercises the exact locked Linux x64 dependency graphs on Python 3.11, 3.12, and 3.13, official MCP clients over stdio and authenticated Streamable HTTP, exact-wheel installation outside the source tree, and the non-root revision-bound image.

The live Kontomierz mutation suite is deliberately hard to start and must only run against a verified **exclusive disposable account**. Do not run it against a normal personal account. See [Production readiness](docs/production-readiness.md) for its explicit safety gates and cleanup requirements.

## Standards and Evidence

The repository uses the immutable `ai-skills` authority revision recorded in [`trusted-executable-sources.lock.yaml`](trusted-executable-sources.lock.yaml) for repository-owned structural verification. That proves which verifier bytes CI executed; it is not, by itself, provider-backed approval.

Formal L2+/`adopted` status is intentionally separate from merge status and requires external provider controls and independent evidence. The current evidence and remaining administrative work are documented in:

- [AI Skills gap assessment](docs/ai-skills-gap-assessment.md)
- [Production readiness](docs/production-readiness.md)
- [System architecture](docs/system-architecture.md)
- [Tool contract](docs/tool-contract.md)
- [Upstream API](docs/upstream-api.md)
- [`upstream-contract.yaml`](upstream-contract.yaml)
- [`live-backend-test-policy.yaml`](live-backend-test-policy.yaml)

## Compatibility

Version 2.0.0 is intentionally incompatible with the legacy 1.x transport and public contract. In particular, SSE and the unauthenticated REST bridge are gone, dates/months are canonicalized, pagination semantics are conservative, update omission differs from an explicit empty string, destructive operations have exact allowlists, and result metadata no longer exposes internal target identity.

## Quick Reference

| Metric | Value |
|---|---|
| Version | 2.0.0 |
| Python | 3.11+; exact Linux x64 CI locks for 3.11–3.13 |
| MCP SDK | `mcp==2.0.0` |
| Tools | 27: 12 READ, 11 WRITE, 4 DESTRUCTIVE |
| Transports | stdio; authenticated loopback Streamable HTTP |
| Default mode | read-only stdio |
| License | MIT |

## License

[MIT](LICENSE)
