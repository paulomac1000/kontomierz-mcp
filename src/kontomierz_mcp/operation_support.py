"""Shared domain validation for public Kontomierz operations."""

from __future__ import annotations

import inspect
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, NoReturn, overload

from .errors import ApplicationError, ErrorCode


async def resolve(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def fail(message: str) -> NoReturn:
    raise ApplicationError(ErrorCode.INVALID_PARAMETER, message)


def bounded_text(
    value: Any,
    name: str,
    *,
    max_bytes: int,
    allow_empty: bool = True,
    strip: bool = False,
) -> str:
    """Validate one public string value and enforce its UTF-8 byte budget."""
    if not isinstance(value, str):
        fail(f"{name} must be a string")
    result = value.strip() if strip else value
    if not result and not allow_empty:
        fail(f"{name} is required")
    if len(result.encode("utf-8")) > max_bytes:
        fail(f"{name} must not exceed {max_bytes} UTF-8 bytes")
    return result


def text(value: Any, name: str, *, max_bytes: int = 512) -> str:
    return bounded_text(value, name, max_bytes=max_bytes, allow_empty=False, strip=True)


def boolean(value: Any, name: str) -> bool:
    if type(value) is not bool:
        fail(f"{name} must be a boolean")
    return value


@overload
def identifier(value: Any, name: str, *, optional: Literal[False] = False) -> int: ...


@overload
def identifier(value: Any, name: str, *, optional: Literal[True]) -> int | None: ...


def identifier(value: Any, name: str, *, optional: bool = False) -> int | None:
    if optional and value is None:
        return None
    if type(value) is not int or value <= 0:
        fail(f"{name} must be a positive integer")
    return value


def money(value: Any, name: str, *, positive: bool) -> str:
    raw = text(value, name, max_bytes=64)
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        fail(f"{name} must be a decimal number")
    if not amount.is_finite() or (positive and amount <= 0):
        fail(f"{name} must be {'positive' if positive else 'finite'}")
    _sign, digits, exponent = amount.as_tuple()
    if not isinstance(exponent, int):
        fail(f"{name} must be a finite decimal number")
    integer_digits = max(len(digits) + exponent, 0)
    decimal_places = max(-exponent, 0)
    if len(digits) > 20 or integer_digits > 20 or decimal_places > 8:
        fail(f"{name} must have at most 20 digits and 8 decimal places")
    return format(amount, "f")


def currency(value: Any) -> str:
    result = text(value, "currency_name", max_bytes=16).upper()
    if re.fullmatch(r"[A-Z]{3}", result) is None:
        fail("currency_name must be a three-letter code")
    return result


def direction(value: Any, *, allow_all: bool = False, plural: bool = False) -> str:
    result = bounded_text(value, "direction", max_bytes=16, allow_empty=False, strip=True).lower()
    allowed = {"withdrawal", "deposit"} | ({"all"} if allow_all else set())
    if result not in allowed:
        fail(f"direction must be one of {sorted(allowed)}")
    return f"{result}s" if plural and result != "all" else result


def parse_date(value: Any, name: str, *, optional: bool = False) -> date | None:
    if value is None and optional:
        return None
    raw = bounded_text(value, name, max_bytes=10, allow_empty=optional, strip=False)
    if not raw and optional:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) is None:
        fail(f"{name} must be YYYY-MM-DD")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        fail(f"{name} must be YYYY-MM-DD")


def date_value(value: Any, name: str, *, optional: bool = False) -> str | None:
    parsed = parse_date(value, name, optional=optional)
    return None if parsed is None else parsed.isoformat()


def date_range(start: Any, end: Any) -> tuple[str | None, str | None]:
    left = parse_date(start, "start_on", optional=True)
    right = parse_date(end, "end_on", optional=True)
    if left and right and left > right:
        fail("start_on must be on or before end_on")
    return (
        None if left is None else left.isoformat(),
        None if right is None else right.isoformat(),
    )


def month(value: Any) -> str:
    if value is None:
        return ""
    raw = bounded_text(value, "month", max_bytes=32, allow_empty=True, strip=False)
    if not raw:
        return ""
    if re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", raw) is None:
        fail("month must be YYYY-MM")
    return raw


def page(value: Any) -> int:
    return identifier(value, "page")


def page_limit(value: Any) -> int | None:
    if type(value) is int and value == 0:
        return None
    if type(value) is not int or not 1 <= value <= 100:
        fail("per_page must be between 1 and 100")
    return value


def provided(arguments: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    result = {name: arguments.get(name) for name in names if arguments.get(name) is not None}
    if not result:
        fail("at least one field must be provided")
    return result


def bounded(value: Any, name: str, allowed: set[int]) -> int:
    if type(value) is not int:
        fail(f"{name} must be an integer")
    if value not in allowed:
        fail(f"{name} must be one of {', '.join(map(str, sorted(allowed)))}")
    return value


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
