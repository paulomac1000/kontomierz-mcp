"""Compliance tests — Risk Consistency Matrix verification (L3+)."""

from __future__ import annotations

from kontomierz_mcp.tools.constants import TOOL_MANIFESTS

RISK_MATRIX = {
    "READ": {
        "side_effects": {"none", "read"},
        "idempotent": True,
        "retryable": True,
        "reversible": True,
        "requires_confirmation": False,
    },
    "WRITE": {
        "side_effects": {"write"},
        "idempotent": True,
        "retryable": True,
        "reversible": True,
        "requires_confirmation": True,
    },
    "DESTRUCTIVE": {
        "side_effects": {"destructive"},
        "idempotent": False,
        "retryable": False,
        "reversible": False,
        "requires_confirmation": True,
    },
    "SENSITIVE": {
        "side_effects": {"none", "read"},
        "idempotent": True,
        "retryable": True,
        "reversible": True,
        "requires_confirmation": False,
    },
}


class TestRiskConsistencyMatrix:
    """Verify every tool manifest satisfies the Risk Consistency Matrix (L3+)."""

    def test_all_manifests_exist(self) -> None:
        assert len(TOOL_MANIFESTS) == 27, f"Expected 27 tools, got {len(TOOL_MANIFESTS)}"

    def test_each_manifest_matches_risk_matrix(self) -> None:
        for tool_name, manifest in TOOL_MANIFESTS.items():
            risk = manifest.get("risk")
            rule = RISK_MATRIX.get(risk)
            assert rule is not None, f"{tool_name}: unknown risk '{risk}'"

            side_effects = manifest.get("side_effects")
            assert side_effects in rule["side_effects"], (
                f"{tool_name}: side_effects '{side_effects}' not in allowed {rule['side_effects']}"
            )

            idempotent = manifest.get("idempotent")
            assert idempotent is rule["idempotent"], f"{tool_name}: idempotent={idempotent}, expected {rule['idempotent']}"

            retryable = manifest.get("retryable")
            assert retryable is rule["retryable"], f"{tool_name}: retryable={retryable}, expected {rule['retryable']}"

            reversible = manifest.get("reversible")
            assert reversible is rule["reversible"], f"{tool_name}: reversible={reversible}, expected {rule['reversible']}"

            requires_confirmation = manifest.get("requires_confirmation")
            assert requires_confirmation is rule["requires_confirmation"], (
                f"{tool_name}: requires_confirmation={requires_confirmation}, expected {rule['requires_confirmation']}"
            )

    def test_destructive_not_mislabeled_as_write(self) -> None:
        """Irreversible ops must use DESTRUCTIVE, not WRITE."""
        for tool_name, manifest in TOOL_MANIFESTS.items():
            if manifest.get("reversible") is False:
                assert manifest["risk"] == "DESTRUCTIVE", (
                    f"{tool_name}: irreversible but risk is {manifest['risk']} (should be DESTRUCTIVE)"
                )
                assert manifest["retryable"] is False, f"{tool_name}: irreversible but retryable=true"
                assert manifest["idempotent"] is False, f"{tool_name}: irreversible but idempotent=true"

    def test_manifest_fields_present(self) -> None:
        required_fields = {
            "name",
            "version",
            "risk",
            "side_effects",
            "idempotent",
            "retryable",
            "concurrent_safe",
            "timeout_ms",
            "requires_confirmation",
            "determinism",
            "latency",
            "cost",
            "impact",
            "privacy",
            "reversible",
        }
        for tool_name, manifest in TOOL_MANIFESTS.items():
            for field in required_fields:
                assert field in manifest, f"{tool_name}: missing required field '{field}'"
