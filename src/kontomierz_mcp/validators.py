"""Input validation for the Kontomierz MCP server."""


class ValidationError(Exception):
    """Raised when input fails validation."""


def check_write_enabled() -> None:
    """Raise ValidationError if write operations are disabled."""
    from .tools.constants import ENABLE_WRITE_OPERATIONS

    if not ENABLE_WRITE_OPERATIONS:
        raise ValidationError("Write operations are disabled. Set ENABLE_WRITE_OPERATIONS=1 to enable.")


def validate_required(value: str, name: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"'{name}' is required and must not be empty.")
    return str(value).strip()


def validate_positive_number(value: str | float | int, name: str) -> float:
    try:
        num = float(value)
    except (ValueError, TypeError):
        raise ValidationError(f"'{name}' must be a valid number, got: {value}")
    if num <= 0:
        raise ValidationError(f"'{name}' must be positive, got: {num}")
    return num


def validate_direction(value: str, name: str = "direction") -> str:
    allowed = {"withdrawal", "deposit", "all"}
    normalized = str(value).lower().strip()
    if normalized not in allowed:
        raise ValidationError(f"'{name}' must be one of {allowed}, got: '{value}'")
    return normalized


def validate_date(value: str, name: str = "date") -> str:
    from datetime import datetime

    if not value or not str(value).strip():
        raise ValidationError(f"'{name}' is required.")
    value = str(value).strip()
    try:
        datetime.strptime(value, "%d-%m-%Y")
    except ValueError:
        raise ValidationError(f"'{name}' must be in DD-MM-YYYY format, got: '{value}'")
    return value


def validate_page(value: int | str, name: str = "page") -> int:
    try:
        page = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"'{name}' must be an integer, got: {value}")
    if page < 1:
        raise ValidationError(f"'{name}' must be >= 1, got: {page}")
    return page


def validate_per_page(value: int | str, name: str = "per_page") -> int:
    try:
        pp = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"'{name}' must be an integer, got: {value}")
    if pp < 1 or pp > 100:
        raise ValidationError(f"'{name}' must be between 1 and 100, got: {pp}")
    return pp


def validate_currency_name(value: str, name: str = "currency_name") -> str:
    import re

    value = str(value).strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", value):
        raise ValidationError(f"'{name}' must be a 3-letter currency code, got: '{value}'")
    return value


def validate_repeat(value: int | str, name: str = "repeat") -> int:
    allowed = {1, 2, 3, 4, 5, 6, 7, 8, 9}
    try:
        r = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"'{name}' must be an integer, got: {value}")
    if r not in allowed:
        raise ValidationError(f"'{name}' must be one of {sorted(allowed)}, got: {r}")
    return r


def validate_holidays(value: int | str, name: str = "holidays") -> int:
    try:
        h = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"'{name}' must be an integer, got: {value}")
    if h not in (0, 1, 2):
        raise ValidationError(f"'{name}' must be 0, 1, or 2, got: {h}")
    return h
