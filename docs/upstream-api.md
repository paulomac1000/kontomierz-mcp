---
description: Records the currently implemented Kontomierz HTTP contract and the evidence still required from a disposable real account.
doc_id: reference.kontomierz-upstream-api
type: reference
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Run `.venv/bin/python -m pytest tests/unit/test_client.py`; complete the external contract TODOs before claiming real write support.
---
# Kontomierz upstream API contract

## Current adapter contract

The adapter uses `GET` for reads, `POST` for creates and copy operations, `PUT` for updates and payment-state changes, and `DELETE` for removals. API authentication is the historical `api_key` query parameter. Bodies default to JSON, with an explicit `form` compatibility setting.

The implementation source is `src/kontomierz_mcp/client.py`; this document does not duplicate every field.

## Evidence status

Read and write shapes are covered with controlled fake HTTP sessions. No disposable real account was available in this execution environment. Therefore the project does not yet claim that JSON is correct for every write endpoint or that every historical endpoint remains active.

## Required real-system checks

A separate authorized agent must use a disposable account to verify:

1. method and content type for every create and update family;
2. 401, 404, 422, 429, and 5xx behavior without storing raw protected bodies;
3. `client_assigned_id` reconciliation after an intentionally interrupted create;
4. pagination termination and ordering;
5. deletion and payment-state behavior with reversible disposable fixtures.

The placeholders are in `tests/integration/test_real_kontomierz_contract.py` and are excluded from normal CI.
