---
description: Records the verified Kontomierz HTTP contract with evidence collected from a live account.
doc_id: reference.kontomierz-upstream-api
type: reference
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Run the explicitly opted-in external evidence suite against a disposable live account; repeat write round trips before claiming contract stability.
---
# Kontomierz upstream API contract

## Verified contract (live-account evidence, 2026-08-08)

The following was proven against a live account (`https://secure.kontomierz.pl/k4`) with read probes and minimal, cleaned-up write round trips. The executable evidence lives in `tests/external/test_real_kontomierz_contract.py` and its autouse cleanup guard in `tests/external/conftest.py`; endpoint behavior that is only retained as a recorded historical observation is marked `confidence: recorded` in `upstream-contract.yaml`. The live suite is excluded by default. Mutation-capable runs require both `KONTOMIERZ_EXTERNAL_TESTS=1` and `KONTOMIERZ_ALLOW_REAL_MUTATIONS=1`, plus `KONTOMIERZ_EXCLUSIVE_DISPOSABLE_ACCOUNT=1` and an expected `KONTOMIERZ_DISPOSABLE_WALLET_ID` that must be verified against the authenticated account before cleanup or mutation.

### Authentication

Every request carries the credential as the `api_key` query parameter. Invalid credentials return 401/403. Because that legacy transport puts the secret in the URL, production logging suppresses `httpx`/`httpcore` request diagnostics that could otherwise emit the credential-bearing query string.

### Body encoding

**All verified write endpoints require `application/x-www-form-urlencoded` bodies.** JSON-encoded bodies are rejected (observed: `POST schedules.json` JSON -> 401/422, `POST money_transactions.json` JSON -> 404). The adapter therefore uses form encoding for the real backend, and validated real-backend configuration rejects `KONTOMIERZ_BODY_MODE=json` rather than retaining a known-broken compatibility mode.

### Dates

Write payload dates use `DD-MM-YYYY` (schedule `deadline_on`, `mark_as_payed` / `mark_as_unpayed` path dates, transaction `transaction_on`). ISO `YYYY-MM-DD` is rejected with `422 Nieprawidłowy parametr - termin płatności`. Responses contain ISO dates (for example `next_deadline_on`, and `transaction_on` in a created transaction). The public server surface accepts ISO dates only; conversion to `DD-MM-YYYY` happens internally after public validation.

### Response bounds

The adapter streams successful JSON responses and caps the decoded body at 4 MiB before JSON decoding. A declared `Content-Length` above the limit is rejected immediately, and chunked/streamed bodies are aborted as soon as accumulated decoded bytes would cross the same limit. Error status mapping is performed before reading a response body, so raw upstream error pages are not buffered or surfaced. An oversized read response is a non-retryable bounded upstream failure; an oversized response after a successful mutation is conservatively marked as a potentially completed write and normalized by the kernel to `AMBIGUOUS_OUTCOME`.

### Verified endpoints

| Endpoint | Method | Notes |
|---|---|---|
| `currencies.json` | GET | `{"currencies": [{id, name, full_name, importance}]}` |
| `user_accounts.json` | GET | list of `{"user_account": {...}}` with `balance`/`currency_balance` as decimal strings |
| `money_transactions.json` | GET | JSON list; accepts `page`/`per_page` parameters; termination with populated transaction data remains unverified |
| `money_transactions.json` | POST | form body `money_transaction[...]`; 201 with the created object |
| `money_transactions/{id}.json` | GET/PUT/DELETE | GET/PUT status behavior is retained as recorded upstream evidence; the current live cleanup guard verifies deletion of test-owned transactions by absence from subsequent bounded listings |
| `categories.json` | GET | requires `direction` **and** `in_wallet=true`; returns `{"category_groups": [{id, name, position, color, categories: [...]}]}`; missing `in_wallet` yields plain-text `missing in_wallet=true parameter` |
| `tags.json` | GET | `{"tags": [{"name": ...}]}` — tags have **no id** |
| `budgets.json` | GET/POST | `{"budgets": [...]}` wrapper; `month_on` is unreliable on create (budgets landed in the current month in evidence runs); ISO month queries for far-future months can return 500 when only a virtual `other` row remains |
| `budgets/{id}.json` | PUT/DELETE | 200 empty body |
| `budgets/copy_from_last_to_present_month.json` | POST | 200 empty |
| `scheduled_transactions.json` | GET | `{"scheduled_transactions": [{schedule_id, transaction_on, description, currency_amount, currency_name, paid}]}`; **honors `page`/`per_page` with stable ordering**; pages beyond the end return an empty list |
| `schedules.json` | POST | form body `schedule[...]` with `deadline_on` DD-MM-YYYY; 201 **empty body** |
| `schedules/{id}.json` | GET/PUT/DELETE | `{"schedule": {...}}`; 200 empty body for PUT/DELETE |
| `schedules/{id}/mark_as_payed/{date}.json` | PUT | date DD-MM-YYYY; 200 empty |
| `schedules/{id}/mark_as_unpayed/{date}.json` | PUT | date DD-MM-YYYY; 200 empty |
| `wealth_points.json` | GET | `[{"wealth_point": {id, date_on, amount, notes}}]` — per-item wrapper |
| `charts/money_transactions.json` | GET | requires parameters (e.g. `chart_kind=pie`); returns `{"type": ..., "data": [...]}`; 204 without parameters |

### Empty-body success handling

Observed schedule and budget creates return HTTP 201 with an **empty body**. That status confirms the create succeeded, but the upstream does not identify the new resource. The adapter therefore returns `{"created": true, "reconciliation_required": true}` rather than inventing a stable ID or misclassifying the confirmed 201 as an uncertain write. Consumers must reconcile through `list_scheduled_transactions` or `list_budgets` before a dependent mutation. Schedule reconciliation must use an explicit date range covering the submitted deadline because the range-less listing exposes only the current scheduling window, and identical schedule creates are not deduplicated.

A timeout, transport loss, oversized/malformed successful mutation response, 5xx after mutation start, or other condition where the server cannot know whether the write completed remains `AMBIGUOUS_OUTCOME` and must not be retried automatically. Transaction creates normally return the created object; an unexpected empty transaction-create response remains fail-closed and ambiguous because that shape is not observed. Empty updates can return an update marker because the stable target ID was supplied by the caller. The wallet-create response-body shape remains unverified; if the service returns a confirmed empty 201, the runtime's generic confirmed-create policy returns the reconciliation-required marker, but this document does not claim that shape has been observed.

### Failure classification

Read timeout, transport loss, 429, and 5xx errors may be retry-eligible for the caller. The server itself does not retry. For a started write, timeout, transport loss, invalid JSON, a missing response wrapper, a wrong response shape after success status, an oversized successful response body, and ambiguous 5xx are marked as potentially completed and normalized by the kernel to `AMBIGUOUS_OUTCOME`. A cancellation after mutation execution starts also remains ambiguous in the server-side audit record. Explicit 4xx rejections are not ambiguous.

## Remaining unverified

- Wallet create/update (`user_accounts/create_wallet.json`, `.../update_wallet.json`) response bodies are not represented by executable live evidence in this repository.
- `client_assigned_id` uniqueness/retention semantics for transactions.
- Reconciliation after an intentionally interrupted create (post-timeout state checks).
- Rate-limit behavior was deliberately not hammered on a personal account.
- Transaction pagination termination with a non-empty transaction list.
