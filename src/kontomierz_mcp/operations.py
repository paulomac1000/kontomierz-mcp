"""Transport-independent Kontomierz operations and domain validation."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from .config import Settings
from .errors import ApplicationError, ErrorCode
from .manifests import TOOL_MANIFESTS

Operation = Callable[..., Any]


class KontomierzPort(Protocol):
    def close(self) -> None: ...


def _required_text(value: str, name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER, f"{name} is required")
    return normalized


def _positive_id(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER, f"{name} must be a positive integer")
    return value


def _positive_decimal(value: str, name: str) -> str:
    normalized = _required_text(value, name)
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER, f"{name} must be a decimal number") from exc
    if not amount.is_finite() or amount <= 0:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER, f"{name} must be positive")
    return format(amount, "f")


def _currency(value: str) -> str:
    normalized = _required_text(value, "currency_name").upper()
    if re.fullmatch(r"[A-Z]{3}", normalized) is None:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER, "currency_name must be a three-letter code")
    return normalized


def _direction(value: str, *, allow_all: bool = False, upstream_plural: bool = False) -> str:
    normalized = str(value).strip().lower()
    allowed = {"withdrawal", "deposit"} | ({"all"} if allow_all else set())
    if normalized not in allowed:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER, f"direction must be one of {sorted(allowed)}")
    if upstream_plural and normalized != "all":
        return f"{normalized}s"
    return normalized


def _date(value: str, name: str, *, optional: bool = False) -> str:
    normalized = str(value).strip()
    if not normalized and optional:
        return ""
    if not normalized:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER, f"{name} is required")
    parsed = None
    for pattern in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            parsed = datetime.strptime(normalized, pattern)
            break
        except ValueError:
            continue
    if parsed is None:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER, f"{name} must be YYYY-MM-DD")
    return parsed.strftime("%d-%m-%Y")


def _month(value: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        return ""
    for pattern in ("%Y-%m", "%d-%m-%Y"):
        try:
            parsed = datetime.strptime(normalized, pattern)
            return parsed.strftime("01-%m-%Y")
        except ValueError:
            continue
    raise ApplicationError(ErrorCode.INVALID_PARAMETER, "month must be YYYY-MM")


def _page(value: int) -> int:
    return _positive_id(value, "page")


def _per_page(value: int) -> int | None:
    if value == 0:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 100:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER, "per_page must be between 1 and 100")
    return value


def _nonempty_update(fields: dict[str, Any]) -> dict[str, Any]:
    present = {key: value for key, value in fields.items() if value not in {None, ""}}
    if not present:
        raise ApplicationError(ErrorCode.INVALID_PARAMETER, "at least one field must be provided")
    return present


def build_operations(client: Any, settings: Settings) -> dict[str, Operation]:
    """Bind validated application operations to one dependency port."""

    def list_accounts() -> list[dict[str, Any]]:
        return client.get_user_accounts()

    def create_wallet(currency_balance: str, currency_name: str, user_name: str = "", liquid: str = "1") -> dict[str, Any]:
        if liquid not in {"0", "1"}:
            raise ApplicationError(ErrorCode.INVALID_PARAMETER, "liquid must be 0 or 1")
        return client.create_wallet(_positive_decimal(currency_balance, "currency_balance"), _currency(currency_name), user_name.strip(), liquid)

    def update_wallet(wallet_id: int, currency_balance: str = "", currency_name: str = "", user_name: str = "", liquid: str = "") -> dict[str, Any]:
        fields: dict[str, Any] = {"currency_balance": currency_balance, "currency_name": currency_name, "user_name": user_name, "liquid": liquid}
        fields = _nonempty_update(fields)
        if "currency_balance" in fields:
            fields["currency_balance"] = _positive_decimal(fields["currency_balance"], "currency_balance")
        if "currency_name" in fields:
            fields["currency_name"] = _currency(fields["currency_name"])
        if "liquid" in fields and fields["liquid"] not in {"0", "1"}:
            raise ApplicationError(ErrorCode.INVALID_PARAMETER, "liquid must be 0 or 1")
        return client.update_wallet(_positive_id(wallet_id, "wallet_id"), **fields)

    def destroy_wallet(wallet_id: int) -> dict[str, Any]:
        identifier = _positive_id(wallet_id, "wallet_id")
        client.destroy_wallet(identifier)
        return {"deleted": True, "wallet_id": identifier}

    def list_transactions(
        page: int = 1,
        per_page: int = 0,
        user_account_id: int = 0,
        q: str = "",
        start_on: str = "",
        end_on: str = "",
        direction: str = "all",
        tag_name: str = "",
        category_group_id: int = 0,
        category_id: int = 0,
        show_hidden_transactions: bool = False,
    ) -> dict[str, Any]:
        page_value = _page(page)
        limit = _per_page(per_page)
        transactions = client.get_money_transactions(
            page=page_value,
            per_page=limit,
            user_account_id=user_account_id or None,
            q=q.strip() or None,
            start_on=_date(start_on, "start_on", optional=True) or None,
            end_on=_date(end_on, "end_on", optional=True) or None,
            direction=_direction(direction, allow_all=True, upstream_plural=True),
            tag_name=tag_name.strip() or None,
            category_group_id=category_group_id or None,
            category_id=category_id or None,
            show_hidden_transactions="true" if show_hidden_transactions else "false",
        )
        has_more = limit is not None and len(transactions) == limit
        return {
            "items": transactions,
            "page": page_value,
            "page_size": limit,
            "items_in_page": len(transactions),
            "has_more": has_more,
            "next_page": page_value + 1 if has_more else None,
        }

    def get_transaction(transaction_id: int) -> dict[str, Any]:
        return client.get_money_transaction(_positive_id(transaction_id, "transaction_id"))

    def create_transaction(
        client_assigned_id: str,
        user_account_id: int = 0,
        category_id: int = 0,
        currency_amount: str = "",
        currency_name: str = "",
        direction: str = "withdrawal",
        tag_string: str = "",
        name: str = "",
        transaction_on: str = "",
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "client_assigned_id": _required_text(client_assigned_id, "client_assigned_id"),
            "user_account_id": user_account_id or None,
            "category_id": category_id or None,
            "direction": _direction(direction),
            "tag_string": tag_string.strip(),
            "name": name.strip(),
        }
        if currency_amount:
            fields["currency_amount"] = _positive_decimal(currency_amount, "currency_amount")
        if currency_name:
            fields["currency_name"] = _currency(currency_name)
        if transaction_on:
            fields["transaction_on"] = _date(transaction_on, "transaction_on")
        return client.create_money_transaction(**fields)

    def update_transaction(transaction_id: int, **fields: Any) -> dict[str, Any]:
        fields = _nonempty_update(fields)
        if "currency_amount" in fields:
            fields["currency_amount"] = _positive_decimal(fields["currency_amount"], "currency_amount")
        if "currency_name" in fields:
            fields["currency_name"] = _currency(fields["currency_name"])
        if "direction" in fields:
            fields["direction"] = _direction(fields["direction"])
        if "transaction_on" in fields:
            fields["transaction_on"] = _date(fields["transaction_on"], "transaction_on")
        return client.update_money_transaction(_positive_id(transaction_id, "transaction_id"), **fields)

    def delete_transaction(transaction_id: int) -> dict[str, Any]:
        identifier = _positive_id(transaction_id, "transaction_id")
        client.delete_money_transaction(identifier)
        return {"deleted": True, "transaction_id": identifier}

    def list_categories(direction: str = "withdrawal") -> list[dict[str, Any]]:
        return client.get_categories(_direction(direction))

    def list_tags() -> list[dict[str, Any]]:
        return client.get_tags()

    def list_currencies() -> list[dict[str, Any]]:
        return client.get_currencies()

    def list_budgets(month: str = "") -> dict[str, Any]:
        items = client.get_budgets(_month(month) or None)
        return {"items": items, "items_in_page": len(items), "month": month or None}

    def create_budget(limit: str, category_id: int = 0, category_group_id: int = 0, month: str = "") -> dict[str, Any]:
        if bool(category_id) == bool(category_group_id):
            raise ApplicationError(ErrorCode.INVALID_PARAMETER, "provide exactly one of category_id or category_group_id")
        return client.create_budget(
            _positive_decimal(limit, "limit"),
            category_id or None,
            category_group_id or None,
            _month(month),
        )

    def update_budget(budget_id: int, limit: str) -> dict[str, Any]:
        return client.update_budget(_positive_id(budget_id, "budget_id"), _positive_decimal(limit, "limit"))

    def delete_budget(budget_id: int) -> dict[str, Any]:
        identifier = _positive_id(budget_id, "budget_id")
        client.delete_budget(identifier)
        return {"deleted": True, "budget_id": identifier}

    def copy_budgets_from_last_month() -> dict[str, Any]:
        client.copy_budgets_from_last_month()
        return {"copied": True}

    def list_scheduled_transactions(schedule_group_name: str = "unpaid", page: int = 1, per_page: int = 0, start_on: str = "", end_on: str = "", direction: str = "all") -> dict[str, Any]:
        if schedule_group_name not in {"paid", "unpaid"}:
            raise ApplicationError(ErrorCode.INVALID_PARAMETER, "schedule_group_name must be paid or unpaid")
        page_value = _page(page)
        limit = _per_page(per_page)
        items = client.get_scheduled_transactions(
            schedule_group_name=schedule_group_name,
            page=page_value,
            per_page=limit,
            start_on=_date(start_on, "start_on", optional=True) or None,
            end_on=_date(end_on, "end_on", optional=True) or None,
            direction=_direction(direction, allow_all=True, upstream_plural=True),
        )
        has_more = limit is not None and len(items) == limit
        return {"items": items, "page": page_value, "page_size": limit, "items_in_page": len(items), "has_more": has_more, "next_page": page_value + 1 if has_more else None}

    def get_schedule(schedule_id: int) -> dict[str, Any]:
        return client.get_schedule(_positive_id(schedule_id, "schedule_id"))

    def create_schedule(direction: str, deadline_on: str, holidays: int, description: str, currency_amount: str, currency_name: str, repeat: int) -> dict[str, Any]:
        if holidays not in {0, 1, 2}:
            raise ApplicationError(ErrorCode.INVALID_PARAMETER, "holidays must be 0, 1, or 2")
        if repeat not in set(range(1, 10)):
            raise ApplicationError(ErrorCode.INVALID_PARAMETER, "repeat must be between 1 and 9")
        return client.create_schedule(
            direction=_direction(direction),
            deadline_on=_date(deadline_on, "deadline_on"),
            holidays=str(holidays),
            description=_required_text(description, "description"),
            currency_amount=_positive_decimal(currency_amount, "currency_amount"),
            currency_name=_currency(currency_name),
            repeat=str(repeat),
        )

    def update_schedule(schedule_id: int, **fields: Any) -> dict[str, Any]:
        fields = _nonempty_update(fields)
        if "direction" in fields:
            fields["direction"] = _direction(fields["direction"])
        if "deadline_on" in fields:
            fields["deadline_on"] = _date(fields["deadline_on"], "deadline_on")
        if "holidays" in fields:
            holidays = int(fields["holidays"])
            if holidays not in {0, 1, 2}:
                raise ApplicationError(ErrorCode.INVALID_PARAMETER, "holidays must be 0, 1, or 2")
            fields["holidays"] = str(holidays)
        if "currency_amount" in fields:
            fields["currency_amount"] = _positive_decimal(fields["currency_amount"], "currency_amount")
        if "currency_name" in fields:
            fields["currency_name"] = _currency(fields["currency_name"])
        if "repeat" in fields:
            repeat = int(fields["repeat"])
            if repeat not in set(range(1, 10)):
                raise ApplicationError(ErrorCode.INVALID_PARAMETER, "repeat must be between 1 and 9")
            fields["repeat"] = str(repeat)
        return client.update_schedule(_positive_id(schedule_id, "schedule_id"), **fields)

    def delete_schedule(schedule_id: int) -> dict[str, Any]:
        identifier = _positive_id(schedule_id, "schedule_id")
        client.delete_schedule(identifier)
        return {"deleted": True, "schedule_id": identifier}

    def mark_schedule_paid(schedule_id: int, payment_date: str) -> dict[str, Any]:
        identifier = _positive_id(schedule_id, "schedule_id")
        normalized = _date(payment_date, "payment_date")
        client.mark_schedule_paid(identifier, normalized)
        return {"schedule_id": identifier, "payment_date": payment_date, "paid": True}

    def mark_schedule_unpaid(schedule_id: int, payment_date: str) -> dict[str, Any]:
        identifier = _positive_id(schedule_id, "schedule_id")
        normalized = _date(payment_date, "payment_date")
        client.mark_schedule_unpaid(identifier, normalized)
        return {"schedule_id": identifier, "payment_date": payment_date, "paid": False}

    def get_pie_chart(chart_kind: str = "pie", start_on: str = "", end_on: str = "", direction: str = "all", category_group_id: int = 0, category_id: int = 0, user_account_id: int = 0, q: str = "", tag_name: str = "") -> dict[str, Any]:
        if chart_kind != "pie":
            raise ApplicationError(ErrorCode.INVALID_PARAMETER, "chart_kind must be pie")
        return client.get_pie_chart(
            chart_kind=chart_kind,
            start_on=_date(start_on, "start_on", optional=True) or None,
            end_on=_date(end_on, "end_on", optional=True) or None,
            direction=_direction(direction, allow_all=True, upstream_plural=True),
            category_group_id=category_group_id or None,
            category_id=category_id or None,
            user_account_id=user_account_id or None,
            q=q.strip() or None,
            tag_name=tag_name.strip() or None,
        )

    def list_wealth_points(start_on: str = "", end_on: str = "") -> list[dict[str, Any]]:
        return client.get_wealth_points(_date(start_on, "start_on", optional=True) or None, _date(end_on, "end_on", optional=True) or None)

    def describe_kontomierz_capabilities() -> dict[str, Any]:
        return {
            "schema_version": "2.0.0",
            "supported_transports": ["stdio", "streamable-http"],
            "active_transport": "streamable-http" if settings.transport in {"http", "streamable-http"} else "stdio",
            "write_operations_enabled": settings.enable_write_operations,
            "tools": {name: manifest.as_dict() for name, manifest in TOOL_MANIFESTS.items()},
        }

    return {
        "list_accounts": list_accounts,
        "create_wallet": create_wallet,
        "update_wallet": update_wallet,
        "destroy_wallet": destroy_wallet,
        "list_transactions": list_transactions,
        "get_transaction": get_transaction,
        "create_transaction": create_transaction,
        "update_transaction": update_transaction,
        "delete_transaction": delete_transaction,
        "list_categories": list_categories,
        "list_tags": list_tags,
        "list_currencies": list_currencies,
        "list_budgets": list_budgets,
        "create_budget": create_budget,
        "update_budget": update_budget,
        "delete_budget": delete_budget,
        "copy_budgets_from_last_month": copy_budgets_from_last_month,
        "list_scheduled_transactions": list_scheduled_transactions,
        "get_schedule": get_schedule,
        "create_schedule": create_schedule,
        "update_schedule": update_schedule,
        "delete_schedule": delete_schedule,
        "mark_schedule_paid": mark_schedule_paid,
        "mark_schedule_unpaid": mark_schedule_unpaid,
        "get_pie_chart": get_pie_chart,
        "list_wealth_points": list_wealth_points,
        "describe_kontomierz_capabilities": describe_kontomierz_capabilities,
    }
