"""Unit tests for validators.py — bring module coverage to ≥80%."""

from __future__ import annotations

import pytest

from kontomierz_mcp.validators import (
    ValidationError,
    check_write_enabled,
    validate_currency_name,
    validate_date,
    validate_direction,
    validate_holidays,
    validate_page,
    validate_per_page,
    validate_positive_number,
    validate_repeat,
    validate_required,
)


class TestValidateRequired:
    def test_present_value(self) -> None:
        assert validate_required("hello", "test") == "hello"

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValidationError, match="required"):
            validate_required("", "test")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValidationError, match="required"):
            validate_required("   ", "test")

    def test_strips_whitespace(self) -> None:
        assert validate_required("  hello  ", "test") == "hello"


class TestValidatePositiveNumber:
    def test_positive_int(self) -> None:
        assert validate_positive_number(5, "test") == 5.0

    def test_positive_float(self) -> None:
        assert validate_positive_number("3.14", "test") == 3.14

    def test_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="positive"):
            validate_positive_number(0, "test")

    def test_negative_raises(self) -> None:
        with pytest.raises(ValidationError, match="positive"):
            validate_positive_number(-5, "test")

    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValidationError, match="valid number"):
            validate_positive_number("abc", "test")


class TestValidateDirection:
    def test_withdrawal(self) -> None:
        assert validate_direction("withdrawal") == "withdrawal"

    def test_deposit(self) -> None:
        assert validate_direction("DEPOSIT") == "deposit"

    def test_all(self) -> None:
        assert validate_direction("all") == "all"

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValidationError, match="must be one of"):
            validate_direction("invalid")


class TestValidateDate:
    def test_valid_date(self) -> None:
        assert validate_date("15-06-2026") == "15-06-2026"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValidationError, match="required"):
            validate_date("", "date")

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValidationError, match="DD-MM-YYYY"):
            validate_date("2026-06-15")


class TestValidatePage:
    def test_valid(self) -> None:
        assert validate_page(1) == 1

    def test_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match=">= 1"):
            validate_page(0)

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValidationError, match="integer"):
            validate_page("abc")


class TestValidatePerPage:
    def test_valid(self) -> None:
        assert validate_per_page(50) == 50

    def test_too_low_raises(self) -> None:
        with pytest.raises(ValidationError, match="between 1 and 100"):
            validate_per_page(0)

    def test_too_high_raises(self) -> None:
        with pytest.raises(ValidationError, match="between 1 and 100"):
            validate_per_page(101)


class TestValidateCurrencyName:
    def test_valid(self) -> None:
        assert validate_currency_name("PLN") == "PLN"

    def test_lowercase(self) -> None:
        assert validate_currency_name("eur") == "EUR"

    def test_too_short(self) -> None:
        with pytest.raises(ValidationError, match="3-letter"):
            validate_currency_name("PL")

    def test_too_long(self) -> None:
        with pytest.raises(ValidationError, match="3-letter"):
            validate_currency_name("PLNC")


class TestValidateRepeat:
    def test_valid_monthly(self) -> None:
        assert validate_repeat(2) == 2

    def test_invalid(self) -> None:
        with pytest.raises(ValidationError, match="must be one of"):
            validate_repeat(99)


class TestValidateHolidays:
    def test_valid(self) -> None:
        assert validate_holidays(1) == 1

    def test_invalid(self) -> None:
        with pytest.raises(ValidationError, match="must be 0, 1, or 2"):
            validate_holidays(5)


class TestCheckWriteEnabled:
    def test_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("kontomierz_mcp.tools.constants.ENABLE_WRITE_OPERATIONS", True)
        check_write_enabled()

    def test_disabled_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("kontomierz_mcp.tools.constants.ENABLE_WRITE_OPERATIONS", False)
        with pytest.raises(ValidationError, match="Write operations are disabled"):
            check_write_enabled()
