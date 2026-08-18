from __future__ import annotations

import copy
import pickle

from kontomierz_mcp.errors import ApplicationError, ErrorCode, UpstreamError


def test_application_error_keeps_identity_equality_and_is_hashable() -> None:
    first = ApplicationError(ErrorCode.CONFLICT, "conflict", retryable=True)
    second = ApplicationError(ErrorCode.CONFLICT, "conflict", retryable=True)

    assert first is not second
    assert first != second
    assert isinstance(hash(first), int)


def test_application_error_copy_and_pickle_preserve_all_fields() -> None:
    original = ApplicationError(
        ErrorCode.RATE_LIMITED,
        "later",
        retryable=True,
        suggestion="Retry later.",
        details={"retry_after": "3"},
    )

    for restored in (copy.copy(original), pickle.loads(pickle.dumps(original))):
        assert type(restored) is ApplicationError
        assert restored.code is original.code
        assert restored.message == original.message
        assert restored.retryable is True
        assert restored.suggestion == original.suggestion
        assert restored.details == original.details


def test_upstream_error_pickle_preserves_ambiguity() -> None:
    original = UpstreamError(
        ErrorCode.TIMEOUT,
        "late",
        retryable=False,
        suggestion="Reconcile.",
        details={"status": 504},
        write_outcome_ambiguous=True,
    )

    restored = pickle.loads(pickle.dumps(original))
    assert type(restored) is UpstreamError
    assert restored.code is ErrorCode.TIMEOUT
    assert restored.retryable is False
    assert restored.suggestion == "Reconcile."
    assert restored.details == {"status": 504}
    assert restored.write_outcome_ambiguous is True
