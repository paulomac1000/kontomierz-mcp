from __future__ import annotations

from tests.external.test_real_kontomierz_contract import _SCHEDULE_GROUPS


def test_live_schedule_cleanup_scans_paid_and_unpaid_groups() -> None:
    assert _SCHEDULE_GROUPS == ("unpaid", "paid")
