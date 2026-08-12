from __future__ import annotations

import pytest

from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.operation_support import bounded, bounded_text, identifier, page_limit


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
