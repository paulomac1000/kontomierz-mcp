from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_ai_skills_authority_has_one_canonical_immutable_source_lock() -> None:
    document = yaml.safe_load((ROOT / "trusted-executable-sources.lock.yaml").read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    assert len(document["sources"]) == 1
    source = document["sources"][0]
    assert source["id"] == "ai-skills-authority"
    assert source["repository"] == "paulomac1000/ai-skills"
    assert re.fullmatch(r"[0-9a-f]{40}", source["revision"])
    assert source["credential_access"] == "none"
    assert len(source["files"]) >= 8
    assert all(re.fullmatch(r"sha256:[0-9a-f]{64}", item["sha256"]) for item in source["files"])


def test_ci_resolves_ai_skills_revision_from_canonical_lock_not_a_second_constant() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "AI_SKILLS_REV:" not in workflow
    assert "Resolve trusted ai-skills coordinates from canonical lock" in workflow
    assert "validate_trusted_executable_sources.py" in workflow
