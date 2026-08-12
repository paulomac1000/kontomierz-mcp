from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import yaml

from tests.external import test_real_kontomierz_contract as live

ROOT = Path(__file__).resolve().parents[2]


def test_live_backend_policy_matches_executable_test_boundaries() -> None:
    policy = yaml.safe_load((ROOT / "live-backend-test-policy.yaml").read_text(encoding="utf-8"))
    assert policy == {
        "schema_version": 1,
        "default_execution": "excluded",
        "mutations": {
            "enabled_by_default": False,
            "independent_opt_ins": 2,
            "credential_access": "after-opt-in",
            "unique_namespace": True,
            "cleanup": {
                "capture_created_ids": True,
                "reconcile_by_marker": True,
                "report_unreconciled": True,
            },
        },
    }
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "not external" in pyproject["tool"]["pytest"]["ini_options"]["addopts"]
    assert live._PREFIX == "MCP-E2E-TEST"
    assert live._SCHEDULE_GROUPS == ("unpaid", "paid")


def test_live_backend_requires_two_independent_opt_ins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KONTOMIERZ_EXTERNAL_TESTS", raising=False)
    monkeypatch.delenv("KONTOMIERZ_ALLOW_REAL_MUTATIONS", raising=False)
    with pytest.raises(pytest.fail.Exception, match="BOTH"):
        live._require_live_test_opt_in()

    monkeypatch.setenv("KONTOMIERZ_EXTERNAL_TESTS", "1")
    with pytest.raises(pytest.fail.Exception, match="KONTOMIERZ_ALLOW_REAL_MUTATIONS"):
        live._require_live_test_opt_in()

    monkeypatch.setenv("KONTOMIERZ_ALLOW_REAL_MUTATIONS", "1")
    live._require_live_test_opt_in()
