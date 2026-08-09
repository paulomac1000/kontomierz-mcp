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

The following was proven against a live account (`https://secure.kontomierz.pl/k4`) with read probes and minimal, cleaned-up write round trips. The evidence lives in `tests/external/test_real_kontomierz_contract.py`. That suite is excluded by default and requires both `KONTOMIERZ_EXTERNAL_TESTS=1` and `KONTOMIERZ_ALLOW_REAL_MUTATIONS=1` before it reads credentials or mutates the real service.

### Authentication

Every request carries the credential as the `api_key` query parameter. Invalid credentials return 401/403.

### Body encoding

**All verified write endpoints require `application/x-www-form-urlencoded` bodies.** JSON-encoded bodies are rejected (observed: `POST schedules.json` JSON -> 401/422, `POST money_transactions.json` JSON -> 404). The adapter therefore uses form encoding for the real backend, and validated real-backend configuration rejects `KONTOMIERZ_BODY_MODE=json` rather than retaining a known-broken compatibility mode.

### Dates

Write payload dates use `DD-MM-YYYY` (schedule `deadline_on`, `mark_as_payed` / `mark_as_unpayed` path dates, transaction `transaction_on`). ISO `YYYY-MM-DD` is rejected with `422 Nieprawidłowy parametr - termin płatności`. Responses contain ISO dates (for example `next_deadline_on`, and `transaction_on` in a created transaction). The public server surface accepts ISO dates only; conversion to `DD-MM-YYYY` happens internally after public validation.

### Verified endpoints

| Endpoint | Method | Notes |
|---|---|---|
| `currencies.json` | GET | `{"currencies": [{id, name, full_name, importance}]}` |
| `user_accounts.json` | GET | list of `{"user_account": {...}}` with `balance`/`currency_balance` as decimal strings |
| `money_transactions.json` | GET | JSON list; honors `page`/`per_page` |
| `money_transactions.json` | POST | form body `money_transaction[...]`; 201 with the created object; deleted records return 404 afterwards |
| `money_transactions/{id}.json` | GET/PUT/DELETE | 200/200/200 |
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

Schedule and budget create/update responses are 201/200 with an **empty body** — the server does not return the created object (unlike transactions). The adapter treats an empty-body 200/201 as success, then best-effort reconciles by listing (schedule matched by description, budget by category/group) to return the created identity; when the record is not yet visible it returns a success marker (`{"created": True}`) instead of a false ambiguous failure.

### Failure classification

Read timeout, transport loss, 429, and 5xx errors may be retry-eligible for the caller. The server itself does not retry. For a started write, timeout, transport loss, invalid JSON, a missing response wrapper, or a wrong response shape after success status, and ambiguous 5xx are marked as potentially completed and normalized by the kernel to `AMBIGUOUS_OUTCOME`. Explicit 4xx rejections are not ambiguous.

## Remaining unverified

- Wallet create/update (`user_accounts/create_wallet.json`, `.../update_wallet.json`) response bodies were not exercised because they would mutate the evidence account.
- `client_assigned_id` uniqueness/retention semantics for transactions.
- Reconciliation after an intentionally interrupted create (post-timeout state checks).
- Rate-limit behavior was deliberately not hammered on a personal account.
- Transaction pagination termination with a non-empty transaction list.
