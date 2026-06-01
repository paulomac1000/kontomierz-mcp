# kontomierz-mcp

MCP server providing AI agents with access to Kontomierz.pl personal finance data.

## Requirements

- Python 3.11+
- Kontomierz.pl account with API key

## Quick Start

```bash
cp .env.example .env
# Edit .env and set KONTOMIERZ_API_KEY

python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m kontomierz_mcp
```

## Configuration

| Variable             | Required | Default | Description                          |
|----------------------|----------|---------|--------------------------------------|
| `KONTOMIERZ_API_KEY` | Yes      | —       | API key from kontomierz.pl/profil/api |

## Available Tools

| Tool                    | Risk  | Description                        |
|-------------------------|-------|------------------------------------|
| *(to be implemented)*   | —     | —                                  |

## Testing

```bash
pytest tests/unit/
```
