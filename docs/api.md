# Kontomierz API Documentation

> Source: kontomierz.pl (site no longer active). Saved 2026-06-01.

## Overview

HTTPS RESTful API. Responses in JSON or XML (`.json` / `.xml` extension on every URL).
Stateless — authenticated per-request via `api_key` query parameter.

Status codes: `200` success, `201` created, `422` invalid params, `401` unauthorized.

## Authentication

API key passed as `api_key` query parameter on every request.
Obtain via `POST /k4/session` (email + password) or copy from user profile page.

---

## Endpoints

### User Accounts & Wallets

**`GET /k4/user_accounts.:format`** — List all bank accounts and wallets with balances.

Response fields: `id`, `currency-balance`, `currency-name`, `balance` (PLN), `iban-checksum`, `iban`, `display-name`, `bank-name`, `bank-plugin-name` (`"Wallets"` for wallets), `is-default-wallet`, `apy`.

**`POST /k4/user_accounts/create_wallet.:format`** — Create cash wallet.

| Param | Required | Notes |
|---|---|---|
| `user_account[user_name]` | No | Display name |
| `user_account[currency_balance]` | **Yes** | Balance |
| `user_account[currency_name]` | **Yes** | 3-letter code, e.g. `GBP` |
| `user_account[liquid]` | No | `1`=current funds, `0`=savings (default `1`) |

**`PUT /k4/user_accounts/:id/update_wallet.:format`** — Update wallet.

**`DELETE /k4/user_accounts/:id/destroy_wallet.:format`** — Delete wallet (fails if main or has bank accounts).

---

### Transactions

**`GET /k4/money_transactions.:format`** — Paginated, filtered transaction list.

| Param | Default | Notes |
|---|---|---|
| `page` | `1` | |
| `per_page` | user setting | 1–100 |
| `user_account_id` | — | Filter by account |
| `q` | — | Search text |
| `start_on` | 1st of current month | `DD-MM-YYYY` |
| `end_on` | last of current month | `DD-MM-YYYY` |
| `direction` | `all` | `all` / `withdrawals` / `deposits` |
| `tag_name` | — | Filter by tag |
| `category_group_id` | — | Filter by category group |
| `category_id` | — | Filter by category |
| `show_hidden_transactions` | `false` | `true` / `false` |
| `order_by` | — | Not implemented |

**`GET /k4/money_transactions/:id.:format`** — Transaction details.

Response: `id`, `user-account-id`, `currency-amount`, `currency-name`, `amount` (PLN), `transaction-on`, `booked-on`, `description`, `category-name`, `category-id`, `tag-string`.

**`POST /k4/money_transactions.:format`** — Create transaction in a wallet.

| Param | Default | Notes |
|---|---|---|
| `money_transaction[user_account_id]` | default wallet | |
| `money_transaction[category_id]` | previous tx category | |
| `money_transaction[currency_amount]` | previous tx amount | Positive amount |
| `money_transaction[currency_name]` | wallet currency | |
| `money_transaction[direction]` | `withdrawal` | `withdrawal` / `deposit` |
| `money_transaction[tag_string]` | — | Comma-separated tags |
| `money_transaction[name]` | previous tx name | Description |
| `money_transaction[transaction_on]` | today | `DD-MM-YYYY` |
| `money_transaction[client_assigned_id]` | **Yes** | Unique client-side idempotency key |

**`PUT /k4/money_transactions/:id.:format`** — Update transaction (no `client_assigned_id`).

**`DELETE /k4/money_transactions/:id.:format`** — Delete transaction.

---

### Categories

**`GET /k4/categories.:format`** — Category tree.

| Param | Notes |
|---|---|
| `direction` | **Required.** `withdrawal` or `deposit` |
| `in_wallet` | **Required.** `true` (future: `false` for non-wallet) |

---

### Tags

**`GET /k4/tags.:format`** — User tags sorted by recent usage.

Response: `id`, `name`.

---

### Budgets

**`GET /k4/budgets.:format`** — Budget list for a given month.

| Param | Default |
|---|---|
| `month_on` | current month (`01-MM-YYYY`) |

Response: `id`, `limit`, `amount`, `kind` (`total`/`ordinary`/`other`), `name`, `category-id`, `category-group-id`.

**`POST /k4/budgets.:format`** — Create budget.

| Param | Required |
|---|---|
| `budget[limit]` | **Yes** |
| `budget[category_id]` | category OR group (not both) |
| `budget[category_group_id]` | category OR group (not both) |
| `budget[month_on]` | No (default current) |

**`PUT /k4/budgets/:id.:format`** — Update budget (`budget[limit]` required).

**`DELETE /k4/budgets/:id.:format`** — Delete budget.

**`POST /k4/budgets/copy_from_last_to_present_month.:format`** — Copy last month's budgets to current month.

---

### Scheduled Transactions (Payment Planner)

**`GET /k4/scheduled_transactions.:format`** — List scheduled payments.

| Param | Default | Notes |
|---|---|---|
| `page` | `1` | |
| `per_page` | user setting | 1–100 |
| `start_on` | 1st of current month | `DD-MM-YYYY` |
| `end_on` | last of current month | `DD-MM-YYYY` |
| `direction` | `all` | `all` / `withdrawals` / `deposits` |
| `schedule_group_name` | **Required** | `unpaid` or `paid` |

Response: `schedule-id`, `transaction-on`, `description`, `currency-amount`, `currency-name`, `paid`.

**`GET /k4/schedules/:id.:format`** — Schedule details.

Response: `id`, `next-deadline-on`, `description`, `currency-amount`, `currency-name`, `repeat`, `repeat-description`, `holidays`, `holidays-description`.

**`POST /k4/schedules.:format`** — Create schedule.

| Param | Required | Notes |
|---|---|---|
| `schedule[direction]` | **Yes** | `withdrawal` / `deposit` |
| `schedule[deadline_on]` | **Yes** | `DD-MM-YYYY` |
| `schedule[holidays]` | **Yes** | `0`=no shift, `1`=before weekend, `2`=after weekend |
| `schedule[description]` | **Yes** | |
| `schedule[currency_amount]` | **Yes** | |
| `schedule[currency_name]` | **Yes** | currently only `PLN` |
| `schedule[repeat]` | **Yes** | `1`=once, `8`=weekly, `9`=biweekly, `2`=monthly, `7`=bimonthly, `3`=quarterly, `4`=semiannual, `5`=yearly, `6`=biennial |

**`PUT /k4/schedules/:id.:format`** — Update schedule.

**`PUT /k4/schedules/:id/mark_as_payed/:date.:format`** — Mark as paid. `:date` = `DD-MM-YYYY`.

**`PUT /k4/schedules/:id/mark_as_unpayed/:date.:format`** — Mark as unpaid.

**`DELETE /k4/schedules/:id.:format`** — Delete schedule.

---

### Wealth History

**`GET /k4/wealth_points.:format`** — Net worth history points (one per month).

| Param | Default |
|---|---|
| `start_on` | 1st of current month (`DD-MM-YYYY`) |
| `end_on` | last of current month (`DD-MM-YYYY`) |

Response: `id`, `date-on`, `amount`, `notes`.

---

### Pie Charts

**`GET /k4/charts/money_transactions.:format`** — Pie chart data.

Same params as transaction search, plus `chart_kind` (required, value `"pie"`).

Chart types: `incomes-vs-spendings`, `spendings-in-category-groups`, `spendings-in-categories`, `incomes-in-categories`.

Response per slice: `name`, `y` (PLN), `color`, `z` (drill-down criteria).

---

### Currencies

**`GET /k4/currencies.:format`** — Currency dictionary.

Response: `id`, `name`, `importance` (`major`/`minor`/`trivial`), `full-name`.

---

### User Registration

**`POST /k4/users.:format`**

| Param | Required |
|---|---|
| `user[email]` | **Yes** |
| `user[password]` | **Yes** |
| `user[password_confirmation]` | **Yes** |
| `user[terms_of_service]` | **Yes** (`1` or `0`) |

---

## Base URL

```
https://secure.kontomierz.pl/k4/
```
