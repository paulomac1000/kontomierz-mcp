from __future__ import annotations

import tomllib
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
import yaml

from tests.external import conftest as external_guard
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


def test_disposable_target_requires_exclusive_account_and_expected_wallet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KONTOMIERZ_EXCLUSIVE_DISPOSABLE_ACCOUNT", raising=False)
    monkeypatch.delenv("KONTOMIERZ_DISPOSABLE_WALLET_ID", raising=False)
    with pytest.raises(pytest.fail.Exception, match="EXCLUSIVE_DISPOSABLE_ACCOUNT"):
        external_guard._required_disposable_wallet_id()

    monkeypatch.setenv("KONTOMIERZ_EXCLUSIVE_DISPOSABLE_ACCOUNT", "1")
    with pytest.raises(pytest.fail.Exception, match="DISPOSABLE_WALLET_ID"):
        external_guard._required_disposable_wallet_id()

    monkeypatch.setenv("KONTOMIERZ_DISPOSABLE_WALLET_ID", "77")
    assert external_guard._required_disposable_wallet_id() == 77


def test_disposable_target_is_verified_against_authenticated_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KONTOMIERZ_EXCLUSIVE_DISPOSABLE_ACCOUNT", "1")
    monkeypatch.setenv("KONTOMIERZ_DISPOSABLE_WALLET_ID", "77")
    request = httpx.Request("GET", "https://secure.kontomierz.pl/k4/user_accounts.json")
    response = httpx.Response(200, request=request, json=[{"user_account": {"id": 77}}])
    monkeypatch.setattr(live, "_get", lambda *_args, **_kwargs: response)
    assert external_guard._verify_disposable_target(Mock(spec=httpx.Client), "secret") == 77

    mismatch = httpx.Response(200, request=request, json=[{"user_account": {"id": 88}}])
    monkeypatch.setattr(live, "_get", lambda *_args, **_kwargs: mismatch)
    with pytest.raises(pytest.fail.Exception, match="does not contain expected disposable wallet"):
        external_guard._verify_disposable_target(Mock(spec=httpx.Client), "secret")


def test_budget_cleanup_refuses_baseline_difference_without_verified_disposable_target() -> None:
    issues = external_guard._cleanup_new_budgets(
        Mock(spec=httpx.Client),
        "secret",
        {1, 2},
        verified_disposable_wallet_id=None,
    )
    assert issues == ["budget cleanup refused: exclusive disposable target was not verified"]
