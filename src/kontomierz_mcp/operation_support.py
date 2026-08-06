"""Shared domain validation for public Kontomierz operations."""

from __future__ import annotations

import inspect
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .errors import ApplicationError, ErrorCode


async def resolve(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def fail(message: str) -> None:
    raise ApplicationError(ErrorCode.INVALID_PARAMETER, message)


def text(value: Any, name: str) -> str:
    result = str(value).strip()
    if not result:
        fail(f"{name} is required")
    return result


def identifier(value: Any, name: str, *, optional: bool = False) -> int | None:
    if optional and value in {None, 0}:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        fail(f"{name} must be a positive integer")
    return value


def money(value: Any, name: str, *, positive: bool) -> str:
    raw = text(value, name)
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        fail(f"{name} must be a decimal number")
    if not amount.is_finite() or (positive and amount <= 0):
        fail(f"{name} must be {'positive' if positive else 'finite'}")
    return format(amount, "f")


def currency(value: Any) -> str:
    result = text(value, "currency_name").upper()
    if re.fullmatch(r"[A-Z]{3}", result) is None:
        fail("currency_name must be a three-letter code")
    return result


def direction(value: Any, *, allow_all: bool = False, plural: bool = False) -> str:
    result = str(value).strip().lower()
    allowed = {"withdrawal", "deposit"} | ({"all"} if allow_all else set())
    if result not in allowed:
        fail(f"direction must be one of {sorted(allowed)}")
    return f"{result}s" if plural and result != "all" else result


def parse_date(value: Any, name: str, *, optional: bool = False) -> date | None:
    raw = str(value or "").strip()
    if not raw and optional:
        return None
    if not raw:
        fail(f"{name} is required")
    for pattern in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, pattern).date()
        except ValueError:
            pass
    fail(f"{name} must be YYYY-MM-DD")


def date_value(value: Any, name: str, *, optional: bool = False) -> str | None:
    parsed = parse_date(value, name, optional=optional)
    return None if parsed is None else parsed.strftime("%d-%m-%Y")


def date_range(start: Any, end: Any) -> tuple[str | None, str | None]:
    left = parse_date(start, "start_on", optional=True)
    right = parse_date(end, "end_on", optional=True)
    if left and right and left > right:
        fail("start_on must be on or before end_on")
    return (
        None if left is None else left.strftime("%d-%m-%Y"),
        None if right is None else right.strftime("%d-%m-%Y"),
    )


def month(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    for pattern in ("%Y-%m", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, pattern).strftime("01-%m-%Y")
        except ValueError:
            pass
    fail("month must be YYYY-MM")


def page(value: Any) -> int:
    return int(identifier(value, "page"))


def page_limit(value: Any) -> int | None:
    if value == 0:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        fail("per_page must be between 1 and 100")
    return value


def provided(arguments: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    result = {name: arguments.get(name) for name in names if arguments.get(name) is not None}
    if not result:
        fail("at least one field must be provided")
    return result


def bounded(value: Any, name: str, allowed: set[int]) -> int:
    if isinstance(value, bool):
        fail(f"{name} is invalid")
    try:
        result = int(value)
    except (TypeError, ValueError):
        fail(f"{name} must be an integer")
    if result not in allowed:
        fail(f"{name} must be one of {', '.join(map(str, sorted(allowed)))}")
    return result


def paging(items: list[dict[str, Any]], page_number: int, limit: int | None) -> dict[str, Any]:
    hint = limit is not None and len(items) == limit
    return {
        "items": items,
        "page": page_number,
        "page_size": limit,
        "items_in_page": len(items),
        "may_have_more": hint,
        "next_page_hint": page_number + 1 if hint else None,
    }
