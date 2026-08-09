"""Real Kontomierz API evidence tests.

Executable contract evidence collected against a live account on 2026-08-08
(repository owner authorized real-instance e2e). These tests stay under the
``external`` marker: they are never part of normal CI, require
``KONTOMIERZ_API_KEY`` from the repository ``.env``, and FAIL (not skip) when
the credential is missing. Every created record is removed in ``finally``
blocks; matching is done by the unique ``MCP-E2E-TEST`` description prefix.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.external

_BASE = "https://secure.kontomierz.pl/k4"
_PREFIX = "MCP-E2E-TEST"


def _load_api_key() -> str:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("KONTOMIERZ_API_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key
    pytest.fail("KONTOMIERZ_API_KEY is required in the repository .env for external evidence tests")


def _client() -> httpx.Client:
    return httpx.Client(timeout=30)


def _get(client: httpx.Client, key: str, path: str, **params: object) -> httpx.Response:
    return client.get(f"{_BASE}/{path}", params={"api_key": key, **params})


def _post_form(client: httpx.Client, key: str, path: str, data: dict[str, object]) -> httpx.Response:
    return client.post(f"{_BASE}/{path}", params={"api_key": key}, data=data)


def _put_form(client: httpx.Client, key: str, path: str, data: dict[str, object]) -> httpx.Response:
    return client.put(f"{_BASE}/{path}", params={"api_key": key}, data=data)


def _delete(client: httpx.Client, key: str, path: str) -> httpx.Response:
    return client.delete(f"{_BASE}/{path}", params={"api_key": key})


def test_real_read_contract_shapes() -> None:
    key = _load_api_key()
    with _client() as client:
        currencies = _get(client, key, "currencies.json").json()["currencies"]
        assert isinstance(currencies, list) and len(currencies) > 0
        assert {"id", "name", "full_name", "importance"} <= set(currencies[0])

        accounts = _get(client, key, "user_accounts.json").json()
        assert isinstance(accounts, list) and len(accounts) > 0
        assert "user_account" in accounts[0]
        fields = {"id", "iban", "balance", "currency_balance", "display_name", "bank_name"}
        assert fields <= set(accounts[0]["user_account"])

        categories = _get(client, key, "categories.json", direction="withdrawal", in_wallet="true").json()
        assert "category_groups" in categories
        groups = categories["category_groups"]
        assert len(groups) > 0
        assert {"id", "name", "position", "color", "categories"} <= set(groups[0])
        assert {"category_group_id", "id", "name", "position", "color", "spending"} <= set(groups[0]["categories"][0])

        tags = _get(client, key, "tags.json").json()["tags"]
        assert isinstance(tags, list) and len(tags) > 0
        assert set(tags[0]) == {"name"}

        budgets = _get(client, key, "budgets.json").json()["budgets"]
        assert isinstance(budgets, list)

        schedules = _get(client, key, "scheduled_transactions.json").json()["scheduled_transactions"]
        assert isinstance(schedules, list) and len(schedules) > 0
        assert {"schedule_id", "transaction_on", "description", "currency_amount", "currency_name", "paid"} <= set(
            schedules[0]
        )

        single = _get(client, key, f"schedules/{schedules[0]['schedule_id']}.json").json()
        assert "schedule" in single
        assert {"id", "next_deadline_on", "description", "currency_amount", "currency_name", "repeat"} <= set(
            single["schedule"]
        )

        wealth = _get(client, key, "wealth_points.json").json()
        assert isinstance(wealth, list) and len(wealth) > 0
        assert "wealth_point" in wealth[0]
        assert {"id", "date_on", "amount", "notes"} <= set(wealth[0]["wealth_point"])

        chart = _get(client, key, "charts/money_transactions.json", chart_kind="pie").json()
        assert {"type", "data"} <= set(chart)


def test_real_schedule_write_round_trip() -> None:
    key = _load_api_key()
    description = f"{_PREFIX}-{uuid.uuid4().hex[:8]}"
    deadline = (date.today() + timedelta(days=7)).strftime("%d-%m-%Y")
    created_id: int | None = None
    with _client() as client:
        try:
            response = _post_form(
                client,
                key,
                "schedules.json",
                {
                    "schedule[description]": description,
                    "schedule[currency_amount]": "1.23",
                    "schedule[currency_name]": "PLN",
                    "schedule[direction]": "withdrawal",
                    "schedule[deadline_on]": deadline,
                    "schedule[repeat]": 1,
                    "schedule[holidays]": 0,
                },
            )
            assert response.status_code == 201, response.text[:200]

            items = _get(client, key, "scheduled_transactions.json").json()["scheduled_transactions"]
            matches = [item for item in items if item.get("description") == description]
            assert matches, "created schedule must appear in the list"
            created_id = matches[0]["schedule_id"]

            updated = _put_form(
                client,
                key,
                f"schedules/{created_id}.json",
                {"schedule[description]": f"{description}-updated"},
            )
            assert updated.status_code == 200, updated.text[:200]

            paid = _put_form(client, key, f"schedules/{created_id}/mark_as_payed/{deadline}.json", {})
            assert paid.status_code == 200, paid.text[:200]
            unpaid = _put_form(client, key, f"schedules/{created_id}/mark_as_unpayed/{deadline}.json", {})
            assert unpaid.status_code == 200, unpaid.text[:200]
        finally:
            if created_id is not None:
                _delete(client, key, f"schedules/{created_id}.json")
                gone = _get(client, key, f"schedules/{created_id}.json")
                assert gone.status_code == 404, "deleted schedule must be gone"


def test_real_transaction_write_round_trip() -> None:
    key = _load_api_key()
    description = f"{_PREFIX}-{uuid.uuid4().hex[:8]}"
    created_id: int | None = None
    with _client() as client:
        try:
            response = _post_form(
                client,
                key,
                "money_transactions.json",
                {
                    "money_transaction[currency_amount]": "0.01",
                    "money_transaction[currency_name]": "PLN",
                    "money_transaction[direction]": "withdrawal",
                    "money_transaction[description]": description,
                    "money_transaction[transaction_on]": date.today().strftime("%d-%m-%Y"),
                },
            )
            assert response.status_code == 201, response.text[:200]
            payload = response.json()
            assert "money_transaction" in payload
            created_id = payload["money_transaction"]["id"]
        finally:
            if created_id is not None:
                deleted = _delete(client, key, f"money_transactions/{created_id}.json")
                assert deleted.status_code == 200, deleted.text[:200]
                gone = _get(client, key, f"money_transactions/{created_id}.json")
                assert gone.status_code == 404, "deleted transaction must be gone"


def test_real_budget_write_round_trip() -> None:
    key = _load_api_key()
    with _client() as client:
        groups = _get(client, key, "categories.json", direction="withdrawal", in_wallet="true").json()[
            "category_groups"
        ]
        group_id = groups[0]["id"]
        before = {item["id"] for item in _get(client, key, "budgets.json").json()["budgets"] if item.get("id")}
        try:
            response = _post_form(
                client,
                key,
                "budgets.json",
                {"budget[limit]": 1.0, "budget[category_group_id]": group_id},
            )
            assert response.status_code == 201, response.text[:200]
            budgets = _get(client, key, "budgets.json").json()["budgets"]
            matches = [item for item in budgets if item.get("category_group_id") == group_id]
            assert matches, "created budget must appear in the current-month list"
            created_ids = [item["id"] for item in budgets if item.get("id") and item["id"] not in before]
        finally:
            for budget_id in created_ids:
                _delete(client, key, f"budgets/{budget_id}.json")


def test_real_pagination_evidence() -> None:
    key = _load_api_key()
    with _client() as client:
        unfiltered = _get(client, key, "scheduled_transactions.json").json()["scheduled_transactions"]
        assert len(unfiltered) >= 2, "pagination evidence needs at least two schedules"
        first_page = _get(client, key, "scheduled_transactions.json", page=1, per_page=1).json()[
            "scheduled_transactions"
        ]
        second_page = _get(client, key, "scheduled_transactions.json", page=2, per_page=1).json()[
            "scheduled_transactions"
        ]
        assert len(first_page) == 1 and len(second_page) == 1
        assert first_page[0]["schedule_id"] != second_page[0]["schedule_id"], "pages must differ (stable ordering)"
        last_page = _get(client, key, "scheduled_transactions.json", page=2, per_page=10).json()[
            "scheduled_transactions"
        ]
        assert last_page, "the second page of 11 items with per_page=10 holds the remainder"
        assert last_page[0]["schedule_id"] == unfiltered[-1]["schedule_id"], "ordering is stable across pages"
        beyond = _get(client, key, "scheduled_transactions.json", page=999, per_page=10).json()[
            "scheduled_transactions"
        ]
        assert beyond == [], "pages beyond the last one terminate with an empty list"
        transactions = _get(client, key, "money_transactions.json", page=1, per_page=3).json()
        assert isinstance(transactions, list)
        assert len(transactions) < 3, "pagination termination proven only with the schedule list"


def test_real_money_precision_normalization() -> None:
    key = _load_api_key()
    description = f"{_PREFIX}-{uuid.uuid4().hex[:8]}"
    deadline = (date.today() + timedelta(days=7)).strftime("%d-%m-%Y")
    created_id: int | None = None
    with _client() as client:
        try:
            response = _post_form(
                client,
                key,
                "schedules.json",
                {
                    "schedule[description]": description,
                    "schedule[currency_amount]": "1.23",
                    "schedule[currency_name]": "PLN",
                    "schedule[direction]": "withdrawal",
                    "schedule[deadline_on]": deadline,
                    "schedule[repeat]": 1,
                    "schedule[holidays]": 0,
                },
            )
            assert response.status_code == 201, response.text[:200]
            items = _get(client, key, "scheduled_transactions.json").json()["scheduled_transactions"]
            matches = [item for item in items if item.get("description") == description]
            assert matches
            created_id = matches[0]["schedule_id"]
            assert matches[0]["currency_amount"] == "-1.23", "withdrawal amounts are normalized to negative strings"
        finally:
            if created_id is not None:
                _delete(client, key, f"schedules/{created_id}.json")


def test_real_authentication_failure_and_success() -> None:
    key = _load_api_key()
    with _client() as client:
        bogus = _get(client, "invalid-key-value", "user_accounts.json")
        assert bogus.status_code in {401, 403}
        ok = _get(client, key, "user_accounts.json")
        assert ok.status_code == 200


def test_real_iso_dates_are_rejected_and_dd_mm_accepted() -> None:
    key = _load_api_key()
    description = f"{_PREFIX}-{uuid.uuid4().hex[:8]}"
    deadline = (date.today() + timedelta(days=7)).strftime("%d-%m-%Y")
    created_id: int | None = None
    with _client() as client:
        try:
            iso = _post_form(
                client,
                key,
                "schedules.json",
                {
                    "schedule[description]": description,
                    "schedule[currency_amount]": "1.00",
                    "schedule[currency_name]": "PLN",
                    "schedule[direction]": "withdrawal",
                    "schedule[deadline_on]": "2026-12-31",
                    "schedule[repeat]": 1,
                    "schedule[holidays]": 0,
                },
            )
            assert iso.status_code == 422, "ISO deadline must be rejected by the upstream"
            ok = _post_form(
                client,
                key,
                "schedules.json",
                {
                    "schedule[description]": description,
                    "schedule[currency_amount]": "1.00",
                    "schedule[currency_name]": "PLN",
                    "schedule[direction]": "withdrawal",
                    "schedule[deadline_on]": deadline,
                    "schedule[repeat]": 1,
                    "schedule[holidays]": 0,
                },
            )
            assert ok.status_code == 201, ok.text[:200]
            items = _get(client, key, "scheduled_transactions.json").json()["scheduled_transactions"]
            matches = [item for item in items if item.get("description") == description]
            assert matches, "the created schedule must be visible for cleanup"
            created_id = matches[0]["schedule_id"]
        finally:
            if created_id is not None:
                _delete(client, key, f"schedules/{created_id}.json")


def test_real_form_encoding_is_required_for_writes() -> None:
    key = _load_api_key()
    description = f"{_PREFIX}-{uuid.uuid4().hex[:8]}"
    with _client() as client:
        payload = {
            "schedule[description]": description,
            "schedule[currency_amount]": "1.00",
            "schedule[currency_name]": "PLN",
            "schedule[direction]": "withdrawal",
            "schedule[deadline_on]": "31-12-2026",
            "schedule[repeat]": 1,
            "schedule[holidays]": 0,
        }
        response = client.post(
            f"{_BASE}/schedules.json",
            params={"api_key": key},
            json=payload,
            timeout=30,
        )
        assert response.status_code in {401, 422}, "JSON-encoded write bodies are rejected by the upstream"
        items = _get(client, key, "scheduled_transactions.json").json()["scheduled_transactions"]
        assert not any(item.get("description") == description for item in items), "rejected write must not persist"
