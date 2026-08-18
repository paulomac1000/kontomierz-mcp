from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _job_text(name: str) -> str:
    workflow = yaml.safe_load((ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8"))
    return yaml.safe_dump(workflow["jobs"][name], sort_keys=True)


def test_privileged_publisher_never_loads_or_executes_candidate_artifact() -> None:
    publish = _job_text("publish")
    assert "actions/checkout" not in publish
    assert "actions/download-artifact" not in publish
    assert "docker load" not in publish
    assert "docker run" not in publish
    assert "environment: release" in publish
    assert "docker buildx imagetools create" in publish


def test_quarantine_stage_is_unprivileged_and_smokes_exact_registry_digest() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8"))
    quarantine = workflow["jobs"]["quarantine"]
    text = yaml.safe_dump(quarantine, sort_keys=True)
    assert quarantine["permissions"] == {"actions": "read", "contents": "read"}
    assert "docker load" in text
    assert "docker run" in text
    assert "docker pull" in text
    assert "QUARANTINE_TOKEN" in text
    assert "org.opencontainers.image.revision" in text


def test_release_gate_requires_release_sha_to_be_default_branch_tip() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8"))
    text = yaml.safe_dump(workflow, sort_keys=True)
    assert 'test "$(git rev-parse HEAD)" = "$HEAD_SHA"' in text
    assert "merge-base" not in text


def test_exact_artifact_build_binds_image_to_full_source_revision() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "printf '%s\\n' \"$SOURCE_SHA\" > dist/SOURCE_REVISION" in ci
    assert '--build-arg "EXPECTED_SOURCE_REVISION=${SOURCE_SHA}"' in ci
    assert "AS verified-artifacts" in dockerfile
    assert dockerfile.count("ARG EXPECTED_SOURCE_REVISION") == 2
    assert 'SHELL ["/bin/sh", "-c"]' in dockerfile
    assert "read -r ACTUAL_SOURCE_REVISION < /tmp/dist/SOURCE_REVISION" in dockerfile
    assert 'test "$ACTUAL_SOURCE_REVISION" = "$EXPECTED_SOURCE_REVISION"' in dockerfile
    assert "COPY --from=verified-artifacts /tmp/dist/ /tmp/dist/" in dockerfile
    assert "org.opencontainers.image.revision=$EXPECTED_SOURCE_REVISION" in dockerfile
    assert "trusted-executable-sources.lock.yaml" in ci
