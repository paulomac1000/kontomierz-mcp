import json

from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.server import _error_document


def test_protocol_error_document_is_stable_and_safe() -> None:
    document = _error_document(
        ApplicationError(
            ErrorCode.AMBIGUOUS_OUTCOME,
            "The write may have completed",
            retryable=False,
            suggestion="Reconcile resource state before any retry.",
        )
    )
    assert document == {
        "error": {
            "code": "AMBIGUOUS_OUTCOME",
            "message": "The write may have completed",
            "retryable": False,
            "suggestion": "Reconcile resource state before any retry.",
        }
    }
    serialized = json.dumps(document)
    assert "api_key" not in serialized.lower()
    assert "secret" not in serialized.lower()
