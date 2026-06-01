# Kontomierz-MCP

[![CI](https://github.com/paulomac1000/kontomierz-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/paulomac1000/kontomierz-mcp/actions/workflows/ci.yml)
[![Docker](https://github.com/paulomac1000/kontomierz-mcp/actions/workflows/publish.yml/badge.svg)](https://github.com/paulomac1000/kontomierz-mcp/actions/workflows/publish.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

MCP (Model Context Protocol) server for Kontomierz.pl — a Polish personal finance platform.
Enables AI assistants (Claude Desktop, LibreChat, Cline) to read and manage your bank accounts,
transactions, budgets, and scheduled payments — all through a single API. Built in Python, runs
locally or in Docker.

## Requirements

- Python 3.11+ (for local use) or Docker
- Kontomierz.pl account with [API key](https://kontomierz.pl/profil/api)

## Quick Start

### 1. Configure

```bash
cp .env.example .env
# Edit .env with your KONTOMIERZ_API_KEY
```

### 2. Run with Docker

**Option A — Build local image:**

```bash
docker build -t kontomierz-mcp .
docker run -d \
  --name kontomierz-mcp \
  -p 9100:9100 -p 9101:9101 -p 9102:9102 \
  --env-file .env \
  -e MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED=1 \
  kontomierz-mcp
```

**Option B — From GitHub Container Registry (after publish):**

```bash
docker run -d \
  --name kontomierz-mcp \
  -p 9100:9100 -p 9101:9101 -p 9102:9102 \
  --env-file .env \
  -e MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED=1 \
  ghcr.io/paulomac1000/kontomierz-mcp:latest
```

### 3. Run locally (Python 3.11+)

```bash
pip install -e ".[dev]"
kontomierz-mcp
```

## Ports

| Port | Protocol | Purpose | Endpoint |
|------|----------|---------|----------|
| 9100 | HTTP | Health check | `GET /health` |
| 9101 | SSE | MCP transport (SSE) | `/sse` |
| 9102 | HTTP | REST API bridge | `/api/*` |

### Verify

```bash
# Health check
curl http://localhost:9100/health

# List all 27 MCP tools
curl http://localhost:9102/api/tools

# Call a tool via REST API
curl -X POST http://localhost:9102/api/tools/list_accounts \
  -H "Content-Type: application/json" \
  -d '{"params":{}}'

# Get tool capability manifest
curl http://localhost:9102/api/tools/list_tags/manifest
```

## Available Tools (27)

### Accounts
| Tool | Risk | Description |
|------|------|-------------|
| `list_accounts` | [READ] | List all bank accounts and wallets with balances |
| `create_wallet` | [WRITE] | Create a new cash wallet |
| `update_wallet` | [WRITE] | Update a cash wallet |
| `destroy_wallet` | [DESTRUCTIVE] | Delete a cash wallet |

### Transactions
| Tool | Risk | Description |
|------|------|-------------|
| `list_transactions` | [READ] | List money transactions with pagination and filters |
| `get_transaction` | [READ] | Get details of a single transaction |
| `create_transaction` | [WRITE] | Create a new transaction in a wallet |
| `update_transaction` | [WRITE] | Update an existing transaction |
| `delete_transaction` | [DESTRUCTIVE] | Delete a transaction |

### Budgets
| Tool | Risk | Description |
|------|------|-------------|
| `list_budgets` | [READ] | List budgets for a given month |
| `create_budget` | [WRITE] | Create a budget for a category or group |
| `update_budget` | [WRITE] | Update a budget limit |
| `delete_budget` | [DESTRUCTIVE] | Delete a budget |
| `copy_budgets_from_last_month` | [WRITE] | Copy last month's budgets to current month |

### Schedules
| Tool | Risk | Description |
|------|------|-------------|
| `list_scheduled_transactions` | [READ] | List scheduled payments (unpaid/paid) with pagination |
| `get_schedule` | [READ] | Get details of a payment schedule |
| `create_schedule` | [WRITE] | Create a new payment schedule |
| `update_schedule` | [WRITE] | Update a payment schedule |
| `delete_schedule` | [DESTRUCTIVE] | Delete a payment schedule |
| `mark_schedule_paid` | [WRITE] | Mark a scheduled payment as paid |
| `mark_schedule_unpaid` | [WRITE] | Mark a scheduled payment as unpaid |

### Reference
| Tool | Risk | Description |
|------|------|-------------|
| `list_categories` | [READ] | List category tree (withdrawal/deposit) |
| `list_tags` | [READ] | List user tags sorted by recent usage |
| `list_currencies` | [READ] | List currency dictionary (major/minor/trivial) |

### Charts & Wealth
| Tool | Risk | Description |
|------|------|-------------|
| `get_pie_chart` | [READ] | Get pie chart data for transaction breakdown |
| `list_wealth_points` | [READ] | List net worth history points |

### Introspection
| Tool | Risk | Description |
|------|------|-------------|
| `describe_kontomierz_capabilities` | [READ] | Return full tool catalog with manifests and schema version |

## Configuration

All configuration is via environment variables. See `.env.example` for a complete template.

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `KONTOMIERZ_API_KEY` | API key from kontomierz.pl/profil/api | `hz4Z8NY...` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_PORT` | `9101` | MCP SSE transport port |
| `REST_API_PORT` | `9102` | REST API bridge port |
| `HEALTH_PORT` | `9100` | Health check HTTP port |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `ENABLE_WRITE_OPERATIONS` | `false` | Set to `1`/`true`/`yes`/`on` to enable write/destructive tools |
| `MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED` | — | Set to `1` for Docker port forwarding (binds to `0.0.0.0`) |
| `KONTOMIERZ_API_TIMEOUT` | `30` | API request timeout in seconds |

## REST API

The REST API on port 9102 provides HTTP access to all tools, health checks, and tool manifests.

```bash
# List tools
curl http://localhost:9102/api/tools

# Get tool manifest
curl http://localhost:9102/api/tools/create_wallet/manifest

# Invoke a tool
curl -X POST http://localhost:9102/api/tools/list_transactions \
  -H "Content-Type: application/json" \
  -d '{"params":{"page":"1","start_on":"01-05-2026"}}'
```

## Security

- **Read-only by default** — `ENABLE_WRITE_OPERATIONS=false`. All write/destructive tools return `AUTH_FAILED` until explicitly enabled.
- **Structured errors** — every error includes `code`, `message`, and `retryable` fields so AI agents can branch programmatically.
- **Credential protection** — API key is never logged or returned in responses. Log formatter sanitizes Bearer tokens, API keys, and IP addresses.
- **Response sanitization** — response payloads are recursively sanitized before being sent to AI clients.
- **Localhost binding** — all ports bind to `127.0.0.1` by default. Set `MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED=1` for Docker.

## Standards Compliance

| Standard | Document | Level | Description |
|----------|----------|-------|-------------|
| **MCP Core** | [`mcp-server-standards.md`](https://github.com/paulomac1000/ai-skills/blob/main/skills/mcp-server-architect/mcp-server-standards.md) | L2+ | Tool design, response contracts, testing hierarchy, security |
| **CI/CD** | [`ci-cd-standard.md`](https://github.com/paulomac1000/ai-skills/blob/main/skills/ci-cd-architect/ci-cd-standard.md) | v2.0.0 | Workflows, quality gates, security scanning, dependency management |

Compliance level: **L2+** (Tool Manifests, structured errors, write guard, three-port, SanitizingFormatter,
Risk Consistency Matrix, cleanup tests, Semgrep + Dependabot).

## Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kontomierz": {
      "url": "http://localhost:9101/sse"
    }
  }
}
```

## Testing

```bash
pip install -e ".[dev]"

# Unit tests (zero I/O, fast, 150 tests)
pytest tests/unit/ -q

# Integration tests (mocked client, full pipeline, 19 tests)
pytest tests/integration/ -q

# Coverage (unit + integration, requires ≥80%)
pytest tests/unit/ tests/integration/ --cov=kontomierz_mcp --cov-report=term

# Smoke tests (requires running server on port 9102)
pytest tests/smoke/ -q

# E2E tests (requires running server on port 9102)
pytest tests/e2e/ -q

# Lint, type check, security
ruff check . && ruff format --check .
mypy src/kontomierz_mcp/
bandit -c pyproject.toml -r src/ -ll
```

## Quick Reference

| Metric | Value |
|--------|-------|
| Python | 3.11+ (CI: 3.14) |
| Tools | 27 (14 READ + 10 WRITE + 3 DESTRUCTIVE) |
| Tests | 169 (150 unit + 19 integration) |
| Coverage | 91% |
| Lint | 0 errors (ruff + mypy + bandit) |
| Docker | `ghcr.io/paulomac1000/kontomierz-mcp:latest` |
| Standards | MCP Core L2+ + CI/CD v2.0.0 |
| License | MIT |
