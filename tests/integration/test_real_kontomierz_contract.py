import pytest

pytestmark = pytest.mark.external


def test_real_write_method_and_body_contract() -> None:
    # TODO(real-system-agent): use a disposable account and verify method, media type,
    # response schema, and cleanup for each write endpoint.
    pytest.skip("requires disposable real Kontomierz account")


def test_real_write_timeout_reconciliation() -> None:
    # TODO(real-system-agent): inject a post-send timeout and reconcile by stable ID
    # before deciding whether any retry is safe.
    pytest.skip("requires controlled real-system fault injection")
