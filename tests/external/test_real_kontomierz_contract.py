"""Real Kontomierz API evidence tests.

Executable contract evidence collected against a live account on 2026-08-08
(repository owner authorized real-instance e2e). These tests stay under the
``external`` marker, are excluded by default, and require TWO explicit opt-ins:
``KONTOMIERZ_EXTERNAL_TESTS=1`` and ``KONTOMIERZ_ALLOW_REAL_MUTATIONS=1``.
They also require ``KONTOMIERZ_API_KEY`` from the repository ``.env``. Cleanup
uses captured IDs plus bounded full pagination of unique ``MCP-E2E-TEST``
descriptions across both paid and unpaid schedule groups so a failure between a
successful write and normal reconciliation does not silently orphan data. The
autouse cleanup guard in ``tests/external/conftest.py`` fails the live run when
final resource cleanup cannot be confirmed.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.external

_BASE = "https://secure.kontomierz.pl/k4"
_PREFIX = "MCP-E2E-TEST"
_EVIDENCE_PAGE_SIZE = 100
_MAX_EVIDENCE_PAGES = 100
_SCHEDULE_GROUPS = ("unpaid", "paid")


def _require_live_test_opt_in() -> None:
    required = {
        "KONTOMIERZ_EXTERNAL_TESTS": os.environ.get("KONTOMIERZ_EXTERNAL_TESTS"),
        "KONTOMIERZ_ALLOW_REAL_MUTATIONS": os.environ.get("KONTOMIERZ_ALLOW_REAL_MUTATIONS"),
    }
    missing = [name for name, value in required.items() if value != "1"]
    if missing:
        pytest.fail(
            "Live Kontomierz evidence tests are disabled. Set BOTH "
            "KONTOMIERZ_EXTERNAL_TESTS=1 and KONTOMIERZ_ALLOW_REAL_MUTATIONS=1 "
            f"only for a deliberate disposable-account run; missing opt-in: {', '.join(missing)}"
        )


def _load_api_key() -> str:
    _require_live_test_opt_in()
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        pytest.fail("repository .env is required for external evidence tests")
    for line in env_path.read_text(encoding="utf-8").splitlines():
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


def _all_schedule_items(client: httpx.Client, key: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for group in _SCHEDULE_GROUPS:
        for page_number in range(1, _MAX_EVIDENCE_PAGES + 1):
            response = _get(
                client,
                key,
                "scheduled_transactions.json",
                schedule_group_name=group,
                page=page_number,
                per_page=_EVIDENCE_PAGE_SIZE,
            )
            if response.status_code != 200:
                break
            payload = response.json()
            page_items = payload.get("scheduled_transactions", []) if isinstance(payload, dict) else []
            if not isinstance(page_items, list):
                break
            typed = [item for item in page_items if isinstance(item, dict)]
            result.extend(typed)
            if len(page_items) < _EVIDENCE_PAGE_SIZE:
                break
    return result


def _schedule_ids_for_descriptions(client: httpx.Client, key: str, descriptions: set[str]) -> set[int]:
    result: set[int] = set()
    for item in _all_schedule_items(client, key):
        if item.get("description") not in descriptions:
            continue
        schedule_id = item.get("schedule_id")
        if isinstance(schedule_id, int) and schedule_id > 0:
            result.add(schedule_id)
    return result


def _cleanup_schedules(
    client: httpx.Client,
    key: str,
    *,
    captured_ids: set[int],
    descriptions: set[str],
) -> None:
    candidate_ids = set(captured_ids)
    try:
        candidate_ids.update(_schedule_ids_for_descriptions(client, key, descriptions))
    except (httpx.HTTPError, ValueError, TypeError):
        pass
    for schedule_id in sorted(candidate_ids):
        try:
            _delete(client, key, f"schedules/{schedule_id}.json")
        except httpx.HTTPError:
            pass


def _all_transaction_items(client: httpx.Client, key: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for page_number in range(1, _MAX_EVIDENCE_PAGES + 1):
        response = _get(
            client,
            key,
            "money_transactions.json",
            page=page_number,
            per_page=_EVIDENCE_PAGE_SIZE,
        )
        if response.status_code != 200:
            break
        payload = response.json()
        if not isinstance(payload, list):
            break
        typed = [item for item in payload if isinstance(item, dict)]
        result.extend(typed)
        if len(payload) < _EVIDENCE_PAGE_SIZE:
            break
    return result


def _transaction_ids_for_description(client: httpx.Client, key: str, description: str) -> set[int]:
    result: set[int] = set()
    for item in _all_transaction_items(client, key):
        candidate = item.get("money_transaction", item)
        if not isinstance(candidate, dict):
            continue
        if candidate.get("description") != description and candidate.get("name") != description:
            continue
        transaction_id = candidate.get("id")
        if isinstance(transaction_id, int) and transaction_id > 0:
            result.add(transaction_id)
    return result


def _cleanup_transactions(
    client: httpx.Client,
    key: str,
    *,
    captured_ids: set[int],
    description: str,
) -> None:
    candidate_ids = set(captured_ids)
    try:
        candidate_ids.update(_transaction_ids_for_description(client, key, description))
    except (httpx.HTTPError, ValueError, TypeError):
        pass
    for transaction_id in sorted(candidate_ids):
        try:
            _delete(client, key, f"money_transactions/{transaction_id}.json")
        except httpx.HTTPError:
            pass


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
    updated_description = f"{description}-updated"
    deadline = (date.today() + timedelta(days=7)).strftime("%d-%m-%Y")
    created_ids: set[int] = set()
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

            matches = _schedule_ids_for_descriptions(client, key, {description})
            assert matches, "created schedule must appear in the list"
            created_id = sorted(matches)[0]
            created_ids.add(created_id)

            updated = _put_form(
                client,
                key,
                f"schedules/{created_id}.json",
                {"schedule[description]": updated_description},
            )
            assert updated.status_code == 200, updated.text[:200]

            paid = _put_form(client, key, f"schedules/{created_id}/mark_as_payed/{deadline}.json", {})
            assert paid.status_code == 200, paid.text[:200]
            unpaid = _put_form(client, key, f"schedules/{created_id}/mark_as_unpayed/{deadline}.json", {})
            assert unpaid.status_code == 200, unpaid.text[:200]
        finally:
            _cleanup_schedules(
                client,
                key,
                captured_ids=created_ids,
                descriptions={description, updated_description},
            )


def test_real_transaction_write_round_trip() -> None:
    key = _load_api_key()
    description = f"{_PREFIX}-{uuid.uuid4().hex[:8]}"
    created_ids: set[int] = set()
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
            assert isinstance(created_id, int) and created_id > 0
            created_ids.add(created_id)
        finally:
            _cleanup_transactions(client, key, captured_ids=created_ids, description=description)


def test_real_budget_write_round_trip() -> None:
    key = _load_api_key()
    with _client() as client:
        groups = _get(client, key, "categories.json", direction="withdrawal", in_wallet="true").json()[
            "category_groups"
        ]
        group_id = groups[0]["id"]
        before = {item["id"] for item in _get(client, key, "budgets.json").json()["budgets"] if item.get("id")}
        created_ids: set[int] = set()
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
            created_ids.update(item["id"] for item in matches if item.get("id") and item["id"] not in before)
            assert created_ids, "budget create must produce a new identifiable budget"
        finally:
            try:
                budgets = _get(client, key, "budgets.json").json()["budgets"]
                created_ids.update(item["id"] for item in budgets if item.get("id") and item["id"] not in before)
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                pass
            for budget_id in sorted(created_ids):
                try:
                    _delete(client, key, f"budgets/{budget_id}.json")
                except httpx.HTTPError:
                    pass


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
        assert first_page[0]["schedule_id"] != second_page[0]["schedule_id"], "pages must differ"

        page_size = max(1, min(10, len(unfiltered) // 2))
        observed_ids: list[int] = []
        terminated = False
        for page_number in range(1, _MAX_EVIDENCE_PAGES + 1):
            page_items = _get(
                client,
                key,
                "scheduled_transactions.json",
                page=page_number,
                per_page=page_size,
            ).json()["scheduled_transactions"]
            if not page_items:
                terminated = True
                break
            observed_ids.extend(int(item["schedule_id"]) for item in page_items)
        expected_ids = [int(item["schedule_id"]) for item in unfiltered]
        assert terminated, "paginated schedule traversal must terminate with an empty page"
        assert observed_ids == expected_ids, "pagination must preserve the same stable ordering as the unfiltered list"

        transactions = _get(client, key, "money_transactions.json", page=1, per_page=3).json()
        assert isinstance(transactions, list)


def test_real_money_precision_normalization() -> None:
    key = _load_api_key()
    description = f"{_PREFIX}-{uuid.uuid4().hex[:8]}"
    deadline = (date.today() + timedelta(days=7)).strftime("%d-%m-%Y")
    created_ids: set[int] = set()
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
            matches = _schedule_ids_for_descriptions(client, key, {description})
            assert matches
            created_ids.update(matches)
            items = _all_schedule_items(client, key)
            matched_items = [item for item in items if item.get("schedule_id") in matches]
            assert matched_items and matched_items[0]["currency_amount"] == "-1.23", (
                "withdrawal amounts are normalized to negative strings"
            )
        finally:
            _cleanup_schedules(client, key, captured_ids=created_ids, descriptions={description})


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
    created_ids: set[int] = set()
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
            matches = _schedule_ids_for_descriptions(client, key, {description})
            assert matches, "the created schedule must be visible for cleanup"
            created_ids.update(matches)
        finally:
            _cleanup_schedules(client, key, captured_ids=created_ids, descriptions={description})


def test_real_form_encoding_is_required_for_writes() -> None:
    key = _load_api_key()
    description = f"{_PREFIX}-{uuid.uuid4().hex[:8]}"
    with _client() as client:
        try:
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
            assert not _schedule_ids_for_descriptions(client, key, {description}), "rejected write must not persist"
        finally:
            _cleanup_schedules(client, key, captured_ids=set(), descriptions={description})
