# kontomierz-mcp

MCP server providing AI agents with access to Kontomierz.pl personal finance data.
27 tools covering all documented API endpoints. Built to the [MCP Server Core Standard](https://github.com/anomalyco/opencode) (L2+ compliance).

## Architecture

Three-port design (L2+):

| Port | Protocol | Purpose |
|------|----------|---------|
| 9100 | HTTP | Health endpoint (`/health`). No framework dependency. |
| 9101 | SSE | MCP transport for AI clients (FastMCP). |
| 9102 | HTTP | REST API bridge for smoke/E2E testing (Starlette). |

All responses follow the contract: `{"success": true/false, "data"/"error": ..., "_meta": {request_id, duration_ms, tool_version}}`.
Errors are structured: `{"code": "API_ERROR", "message": "...", "retryable": true/false, "suggestion": "..."}`.

## Requirements

- Python 3.11+
- Kontomierz.pl account with API key

## Quick Start

```bash
cp .env.example .env
# Edit .env and set KONTOMIERZ_API_KEY

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python3 -m kontomierz_mcp
```

### Docker

```bash
docker build -t kontomierz-mcp .
docker run -d --name kontomierz-mcp \
  -p 9100:9100 -p 9101:9101 -p 9102:9102 \
  -v $(pwd)/.env:/app/.env:ro \
  kontomierz-mcp

# Verify
curl http://localhost:9100/health
```

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `KONTOMIERZ_API_KEY` | Yes | — | API key from kontomierz.pl/profil/api |
| `MCP_PORT` | No | `9101` | MCP SSE transport port |
| `REST_API_PORT` | No | `9102` | REST API bridge port |
| `HEALTH_PORT` | No | `9100` | Health check HTTP port |
| `LOG_LEVEL` | No | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `ENABLE_WRITE_OPERATIONS` | No | `false` | Set to `"1"` to allow write/destructive tools |
| `MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED` | No | — | Set to `"1"` to bind to `0.0.0.0` (Docker). Logs CRITICAL warning. |

## Available Tools

### Accounts
| Tool | Risk | Description |
|---|---|---|
| `list_accounts` | READ | List all bank accounts and wallets with balances |
| `create_wallet` | WRITE | Create a new cash wallet |
| `update_wallet` | WRITE | Update a cash wallet |
| `destroy_wallet` | DESTRUCTIVE | Delete a cash wallet |

### Transactions
| Tool | Risk | Description |
|---|---|---|
| `list_transactions` | READ | List money transactions with pagination and filters |
| `get_transaction` | READ | Get details of a single transaction |
| `create_transaction` | WRITE | Create a new transaction in a wallet |
| `update_transaction` | WRITE | Update an existing transaction |
| `delete_transaction` | DESTRUCTIVE | Delete a transaction |

### Budgets
| Tool | Risk | Description |
|---|---|---|
| `list_budgets` | READ | List budgets for a given month |
| `create_budget` | WRITE | Create a budget for a category or group |
| `update_budget` | WRITE | Update a budget limit |
| `delete_budget` | DESTRUCTIVE | Delete a budget |
| `copy_budgets_from_last_month` | WRITE | Copy last month's budgets to current month |

### Schedules
| Tool | Risk | Description |
|---|---|---|
| `list_scheduled_transactions` | READ | List scheduled payments (unpaid/paid) with pagination |
| `get_schedule` | READ | Get details of a payment schedule |
| `create_schedule` | WRITE | Create a new payment schedule |
| `update_schedule` | WRITE | Update a payment schedule |
| `delete_schedule` | DESTRUCTIVE | Delete a payment schedule |
| `mark_schedule_paid` | WRITE | Mark a scheduled payment as paid |
| `mark_schedule_unpaid` | WRITE | Mark a scheduled payment as unpaid |

### Reference
| Tool | Risk | Description |
|---|---|---|
| `list_categories` | READ | List category tree (withdrawal/deposit) |
| `list_tags` | READ | List user tags sorted by recent usage |
| `list_currencies` | READ | List currency dictionary (major/minor/trivial) |

### Charts & Wealth
| Tool | Risk | Description |
|---|---|---|
| `get_pie_chart` | READ | Get pie chart data for transaction breakdown |
| `list_wealth_points` | READ | List net worth history points |

### Capabilities
| Tool | Risk | Description |
|---|---|---|
| `describe_kontomierz_capabilities` | READ | Return full tool catalog with manifests and schema version |

## REST API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/health` | Health check |
| GET | `/api/tools` | List all tools |
| POST | `/api/tools/{name}` | Invoke a tool |
| GET | `/api/tools/{name}/manifest` | Get tool capability manifest |

## Testing

```bash
# Unit tests (zero I/O, fast)
pytest tests/unit/ -v

# Integration tests (mocked client, full pipeline)
pytest tests/integration/ -v

# Coverage (requires ≥80%)
pytest tests/unit/ tests/integration/ --cov=src/kontomierz_mcp --cov-report=term

# Smoke tests (requires running server on port 9102)
pytest tests/smoke/ -v

# E2E tests (requires running server on port 9102)
pytest tests/e2e/ -v

# Lint
ruff check src/

# Type check
mypy src/

# Security scan
bandit -c pyproject.toml -r src/
```
