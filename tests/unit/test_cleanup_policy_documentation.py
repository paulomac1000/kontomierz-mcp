from __future__ import annotations

from pathlib import Path


def test_live_schedule_cleanup_scans_paid_and_unpaid_groups() -> None:
    source = (Path(__file__).parents[1] / "external" / "test_real_kontomierz_contract.py").read_text(encoding="utf-8")
    assert 'schedule_group_name="unpaid"' in source
    assert 'schedule_group_name="paid"' in source
