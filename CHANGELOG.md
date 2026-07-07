# Changelog

All notable changes to the kontomierz-mcp project.

## [1.0.1] — 2026-07-07

### Fixed
- **POST/PUT requests now send JSON body** instead of form-encoded data.
  `_post()` and `_put()` in `client.py` used `data=data` which sent
  `application/x-www-form-urlencoded` despite `Content-Type: application/json`
  in headers. This caused 400 Bad Request from Kontomierz API on all write
  operations (create/update wallet, transaction, budget, schedule).
  Fixed by using `json=data` which correctly serializes dict as JSON and
  sets the matching Content-Type header.

## [1.0.0] — 2026-06-01

### Added
- Initial release with 27 MCP tools covering all Kontomierz.pl API endpoints
- **Accounts**: list, create, update, destroy wallets
- **Transactions**: list (with pagination), get, create, update, delete
- **Budgets**: list, create, update, delete, copy_from_last_month
- **Schedules**: list (with pagination), get, create, update, delete, mark_paid, mark_unpaid
- **Reference**: categories, tags, currencies
- **Charts/Wealth**: pie_chart, wealth_points
- **Capabilities**: describe_kontomierz_capabilities introspection tool
- Three-port architecture (health:9100, SSE:9101, REST API:9102)
- Tool manifests with Risk Consistency Matrix (L2+)
- Structured error responses (code, message, retryable, suggestion)
- Dynamic risk prefix injection from manifests
- SanitizingFormatter + RequestIdFilter in logging
- Write guard (ENABLE_WRITE_OPERATIONS=false default)
- Pagination metadata (page, limit, has_more, next_offset, total)
- SSE safety check (MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED)
- Client connection validation at startup
- ReuseHTTPServer with SO_REUSEADDR
- Per-tool invocation counter on health endpoint
- Response payload sanitization
- GET /api/tools/{name}/manifest REST endpoint
- 169 tests (unit + integration + compliance), ≥92% coverage
- Smoke + E2E tests with dynamic skip
- Docker support
