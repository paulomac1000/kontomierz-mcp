---
description: Records the implemented Kontomierz HTTP contract and evidence still required from a disposable real account.
doc_id: reference.kontomierz-upstream-api
type: reference
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Run the asynchronous client contract tests; complete the external TODOs before claiming real write support.
---
# Kontomierz upstream API contract

## Current adapter contract

The adapter uses `GET` for reads, `POST` for creates and copy operations, `PUT` for updates and payment-state changes, and `DELETE` for removals. Authentication is the historical `api_key` query parameter. Bodies default to JSON, with an explicit form compatibility setting. One shared `httpx.AsyncClient` owns connection pooling and supports cancellation propagation.

## Failure classification

Read timeout, transport loss, 429, and 5xx errors may be retry-eligible for the caller. The server itself does not retry. For a started write, timeout, transport loss, invalid JSON, a missing response wrapper, or a wrong response shape after success status, and ambiguous 5xx are marked as potentially completed and normalized by the kernel to `AMBIGUOUS_OUTCOME`. Explicit 4xx rejections are not ambiguous.

## Evidence status

Method, path, body mode, response shape, and failure mapping are covered with `httpx.MockTransport`. No disposable real account was available, so the project does not claim that JSON is correct for every historical write endpoint or that pagination behavior is fully known.

## Required real-system checks

An authorized agent must use a disposable account to verify:

1. method and content type for every write family;
2. 401, 404, 422, 429, and 5xx behavior without storing protected bodies;
3. reconciliation after an intentionally interrupted create;
4. pagination termination and ordering;
5. deletion and payment-state behavior with disposable fixtures.

The placeholders are in `tests/integration/test_real_kontomierz_contract.py` and are excluded from normal CI.
