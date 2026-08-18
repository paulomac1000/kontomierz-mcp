from __future__ import annotations

import pytest

from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.manifests import TOOL_DEFINITIONS
from kontomierz_mcp.operation_support import bounded, bounded_text, date_value, identifier, month, page_limit


@pytest.mark.parametrize("value", [[], {}, 1, True, None])
def test_bounded_text_rejects_non_strings(value: object) -> None:
    with pytest.raises(ApplicationError) as captured:
        bounded_text(value, "q", max_bytes=32)
    assert captured.value.code is ErrorCode.INVALID_PARAMETER
    assert captured.value.message == "q must be a string"


@pytest.mark.parametrize("value", [[], {}, True, "1", 1.0])
def test_optional_identifier_rejects_wrong_types_without_typeerror(value: object) -> None:
    with pytest.raises(ApplicationError) as captured:
        identifier(value, "category_id", optional=True)
    assert captured.value.code is ErrorCode.INVALID_PARAMETER


@pytest.mark.parametrize("value", [True, "1", 1.0, []])
def test_page_limit_rejects_non_integer_types(value: object) -> None:
    with pytest.raises(ApplicationError) as captured:
        page_limit(value)
    assert captured.value.code is ErrorCode.INVALID_PARAMETER


def test_bounded_integer_does_not_coerce_strings() -> None:
    with pytest.raises(ApplicationError, match="must be an integer"):
        bounded("1", "repeat", {1, 2})


@pytest.mark.parametrize(
    "value",
    ["2026-8-1", "2026-08-1", "2026-8-01", " 2026-08-01", "2026-08-01 "],
)
def test_date_value_rejects_noncanonical_iso_spelling(value: str) -> None:
    with pytest.raises(ApplicationError) as captured:
        date_value(value, "deadline_on")
    assert captured.value.code is ErrorCode.INVALID_PARAMETER


def test_date_value_preserves_canonical_iso_date() -> None:
    assert date_value("2026-08-01", "deadline_on") == "2026-08-01"


@pytest.mark.parametrize("value", ["2026-8", "2026-00", "2026-13", " 2026-08", "2026-08 "])
def test_month_rejects_noncanonical_spelling(value: str) -> None:
    with pytest.raises(ApplicationError) as captured:
        month(value)
    assert captured.value.code is ErrorCode.INVALID_PARAMETER


def test_month_preserves_canonical_value_and_empty_sentinel() -> None:
    assert month("2026-08") == "2026-08"
    assert month("") == ""
    assert month(None) == ""


def test_create_schedule_usage_note_preserves_empty_success_contract() -> None:
    usage_notes = TOOL_DEFINITIONS["create_schedule"].usage_notes
    assert "created=true" in usage_notes
    assert "reconciliation_required=true" in usage_notes
    assert "does not deduplicate" in usage_notes
    assert "widen the date range" in usage_notes
