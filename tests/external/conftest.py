from __future__ import annotations

import os
from collections.abc import Iterator

import httpx
import pytest

from tests.external import test_real_kontomierz_contract as live

_LIVE_MODULE = "test_real_kontomierz_contract.py"
_DELETE_OK = {200, 404}


def _live_opted_in() -> bool:
    return (
        os.environ.get("KONTOMIERZ_EXTERNAL_TESTS") == "1" and os.environ.get("KONTOMIERZ_ALLOW_REAL_MUTATIONS") == "1"
    )


def _budget_ids(client: httpx.Client, key: str) -> set[int]:
    response = live._get(client, key, "budgets.json")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("budgets"), list):
        raise ValueError("unexpected budget cleanup response")
    return {
        item["id"]
        for item in payload["budgets"]
        if isinstance(item, dict) and type(item.get("id")) is int and item["id"] > 0
    }


def _prefixed_schedule_ids(client: httpx.Client, key: str) -> set[int]:
    result: set[int] = set()
    for group in live._SCHEDULE_GROUPS:
        terminated = False
        for page_number in range(1, live._MAX_EVIDENCE_PAGES + 1):
            response = live._get(
                client,
                key,
                "scheduled_transactions.json",
                schedule_group_name=group,
                page=page_number,
                per_page=live._EVIDENCE_PAGE_SIZE,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("scheduled_transactions"), list):
                raise ValueError(f"unexpected {group} schedule cleanup response")
            items = payload["scheduled_transactions"]
            for item in items:
                if not isinstance(item, dict):
                    continue
                description = item.get("description")
                schedule_id = item.get("schedule_id")
                if (
                    isinstance(description, str)
                    and description.startswith(live._PREFIX)
                    and type(schedule_id) is int
                    and schedule_id > 0
                ):
                    result.add(schedule_id)
            if len(items) < live._EVIDENCE_PAGE_SIZE:
                terminated = True
                break
        if not terminated:
            raise RuntimeError(f"{group} schedule cleanup scan exceeded its page bound")
    return result


def _prefixed_transaction_ids(client: httpx.Client, key: str) -> set[int]:
    result: set[int] = set()
    terminated = False
    for page_number in range(1, live._MAX_EVIDENCE_PAGES + 1):
        response = live._get(
            client,
            key,
            "money_transactions.json",
            page=page_number,
            per_page=live._EVIDENCE_PAGE_SIZE,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("unexpected transaction cleanup response")
        for item in payload:
            if not isinstance(item, dict):
                continue
            candidate = item.get("money_transaction", item)
            if not isinstance(candidate, dict):
                continue
            description = candidate.get("description") or candidate.get("name")
            transaction_id = candidate.get("id")
            if (
                isinstance(description, str)
                and description.startswith(live._PREFIX)
                and type(transaction_id) is int
                and transaction_id > 0
            ):
                result.add(transaction_id)
        if len(payload) < live._EVIDENCE_PAGE_SIZE:
            terminated = True
            break
    if not terminated:
        raise RuntimeError("transaction cleanup scan exceeded its page bound")
    return result


def _delete_ids(client: httpx.Client, key: str, *, kind: str, ids: set[int], issues: list[str]) -> None:
    endpoint = {
        "schedule": lambda item_id: f"schedules/{item_id}.json",
        "transaction": lambda item_id: f"money_transactions/{item_id}.json",
        "budget": lambda item_id: f"budgets/{item_id}.json",
    }[kind]
    for item_id in sorted(ids):
        try:
            response = live._delete(client, key, endpoint(item_id))
        except httpx.HTTPError as exc:
            issues.append(f"{kind}:{item_id} delete transport failure: {type(exc).__name__}")
            continue
        if response.status_code not in _DELETE_OK:
            issues.append(f"{kind}:{item_id} delete returned HTTP {response.status_code}")


def _cleanup_marked_resources(client: httpx.Client, key: str) -> list[str]:
    issues: list[str] = []
    try:
        schedule_ids = _prefixed_schedule_ids(client, key)
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        issues.append(f"schedule marker scan failed: {type(exc).__name__}: {exc}")
        schedule_ids = set()
    _delete_ids(client, key, kind="schedule", ids=schedule_ids, issues=issues)

    try:
        transaction_ids = _prefixed_transaction_ids(client, key)
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        issues.append(f"transaction marker scan failed: {type(exc).__name__}: {exc}")
        transaction_ids = set()
    _delete_ids(client, key, kind="transaction", ids=transaction_ids, issues=issues)

    try:
        remaining_schedules = _prefixed_schedule_ids(client, key)
        if remaining_schedules:
            issues.append(f"unreconciled schedules: {sorted(remaining_schedules)}")
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        issues.append(f"schedule cleanup verification failed: {type(exc).__name__}: {exc}")
    try:
        remaining_transactions = _prefixed_transaction_ids(client, key)
        if remaining_transactions:
            issues.append(f"unreconciled transactions: {sorted(remaining_transactions)}")
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        issues.append(f"transaction cleanup verification failed: {type(exc).__name__}: {exc}")
    return issues


def _cleanup_new_budgets(client: httpx.Client, key: str, baseline: set[int]) -> list[str]:
    issues: list[str] = []
    try:
        created = _budget_ids(client, key) - baseline
    except (httpx.HTTPError, ValueError) as exc:
        return [f"budget reconciliation scan failed: {type(exc).__name__}: {exc}"]
    _delete_ids(client, key, kind="budget", ids=created, issues=issues)
    try:
        remaining = _budget_ids(client, key) - baseline
        if remaining:
            issues.append(f"unreconciled budgets: {sorted(remaining)}")
    except (httpx.HTTPError, ValueError) as exc:
        issues.append(f"budget cleanup verification failed: {type(exc).__name__}: {exc}")
    return issues


@pytest.fixture(autouse=True)
def live_backend_cleanup_guard(request: pytest.FixtureRequest) -> Iterator[None]:
    """Pre-clean the unique namespace and verify post-test cleanup for deliberate live runs."""
    if request.node.path.name != _LIVE_MODULE or not _live_opted_in():
        yield
        return

    key = live._load_api_key()
    with live._client() as client:
        setup_issues = _cleanup_marked_resources(client, key)
        if setup_issues:
            pytest.fail("Live-backend pre-clean could not be confirmed: " + "; ".join(setup_issues))
        try:
            budget_baseline = _budget_ids(client, key)
        except (httpx.HTTPError, ValueError) as exc:
            pytest.fail(f"Live-backend budget baseline could not be captured: {type(exc).__name__}: {exc}")

    try:
        yield
    finally:
        with live._client() as client:
            cleanup_issues = _cleanup_marked_resources(client, key)
            cleanup_issues.extend(_cleanup_new_budgets(client, key, budget_baseline))
        if cleanup_issues:
            pytest.fail("Live-backend cleanup could not be confirmed: " + "; ".join(cleanup_issues))
