---
description: Defines public tool inputs, outputs, safety metadata, errors, retries, dates, money, and pagination.
doc_id: contract.kontomierz-tools
type: contract
status: evolving
rigor: normative
owners: [repository-maintainers]
verification: Run `.venv/bin/python -m pytest tests/unit/test_manifests.py tests/unit/test_operations.py tests/unit/test_kernel.py`.
---
# Kontomierz tool contract

## Inputs

Stable numeric IDs returned by list tools are accepted by detail and mutation tools. Money is passed as a decimal string plus a three-letter currency. Public dates use `YYYY-MM-DD`; months use `YYYY-MM`. Empty optional strings mean omitted values, not deletion.

## Outputs

Successful tools return structured content with `data` and `_meta`. Metadata contains a request ID, duration, tool version, and stable target namespace. Empty lists are successful results.

## Errors

Tool failures are MCP-native error results produced by the official SDK from an application-owned exception. The visible text is a compact JSON object containing `code`, `message`, `retryable`, and optional `suggestion` or bounded details.

Supported application codes distinguish invalid input, authentication, authorization, not found, conflict, rate limiting, timeout, cancellation, dependency unavailability, upstream failure, ambiguous outcome, and internal failure.

## Safety and confidentiality

Each of the 27 tools has an explicit manifest. Risk is not inferred from a single READ/WRITE label. The manifest independently records side effects, confidentiality, operational impact, idempotency, automatic retry, reversibility, concurrency, operator gate, deadline, and target scope.

All account, transaction, budget, schedule, chart, and wealth data is `financial`. Mutations require the operator write gate. Tool descriptions are discovery hints, not authorization.

## Retry contract

Automatic retry is disabled for every mutation. `create_transaction` is idempotent only when the caller preserves a unique `client_assigned_id`; that fact does not authorize blind retry after an ambiguous network outcome. Reads may be retried after eligible transient errors within the caller's deadline.

## Pagination

A page is not evidence of the global total. Results report `items_in_page`, not `total`. `has_more` is true only when the upstream returns a full explicitly requested page; `next_page` is then the next page number. The contract does not call it an offset.

## Compatibility changes

This revision removes legacy SSE and the convenience REST bridge. It replaces localized public date inputs with ISO dates while retaining conversion inside the upstream adapter. These are intentional breaking changes requiring a minor version increase before release.
