---
description: Defines public tool inputs, outputs, safety metadata, errors, retries, dates, money, and pagination.
doc_id: contract.kontomierz-tools
type: contract
status: evolving
rigor: normative
owners: [repository-maintainers]
verification: Run the manifest, operation, kernel, client, and MCP SDK contract tests.
---
# Kontomierz tool contract

## Inputs

Stable positive numeric IDs returned by list tools are accepted by detail and mutation tools. Money is a finite decimal string plus a three-letter currency. Wallet balances may be zero or negative because the upstream contract has not established a positive-only restriction. Public dates use `YYYY-MM-DD`; months use `YYYY-MM`.

For update tools, `None` means not provided. An empty string is an explicit request to clear a text field where the upstream accepts it.

## Outputs

Successful tools return structured content with `data` and `_meta`. Metadata contains a request ID, duration, tool version, and target scope. Empty lists are successful results.

## Errors

Tool failures return an explicit MCP `CallToolResult` with `is_error=true`, controlled text JSON, and `structured_content.error`. The error contains `code`, `message`, `retryable`, and optional `suggestion` or bounded details. SDK-added exception prefixes are not part of the contract.

## Safety and retry

Each tool has an explicit manifest. Mutations require the operator gate. `concurrent_safe=false` is enforced per target. `automatic_retry=false` for every tool because the runtime has no retry loop.

A transient read error may be marked retryable for a caller-controlled retry. A write rejected before admission has not started. A started write with an ambiguous dependency outcome returns `AMBIGUOUS_OUTCOME`, `retryable=false`, and a reconciliation suggestion.

## Pagination

The upstream has not provided a reliable total or continuation token. Results expose `items_in_page`, `may_have_more`, and `next_page_hint`. A full page is only a hint and never a claim that a next page exists.

## Compatibility changes

This revision removes legacy SSE and the REST bridge, uses ISO public dates, switches the HTTP adapter to native async I/O, and makes clearing versus omission explicit.
