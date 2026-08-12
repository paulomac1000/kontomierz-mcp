"""External/provider acceptance placeholders that require repository or release authority.

These tests deliberately fail when the external evidence suite is selected. Replace the
placeholder body with provider-backed assertions once the required access exists. Do not
weaken normal CI or fabricate provider IDs/digests/reviewer identities to make them pass.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.external, pytest.mark.evidence]


def _not_implemented(requirement: str) -> None:
    pytest.fail(f"NOT IMPLEMENTED — provider-backed evidence required: {requirement}")


def test_release_environment_is_administratively_protected() -> None:
    _not_implemented(
        "GitHub release environment must exist with required reviewers, prevent-self-review, "
        "and protected-branch policy"
    )


def test_quarantine_registry_credentials_are_isolated_from_production() -> None:
    _not_implemented(
        "repository administrators must provision QUARANTINE_REGISTRY/QUARANTINE_REPOSITORY and a "
        "QUARANTINE_TOKEN whose authority can mutate only the isolated quarantine registry/repository "
        "and cannot mutate the production GHCR package"
    )


def test_provider_backed_migration_assessment_has_independent_review() -> None:
    _not_implemented(
        "after an independent GitHub review exists for the immutable candidate SHA, generate migration-assessment.yaml "
        "and pass provider-backed ai-skills validation without fabricated identities or evidence"
    )


def test_provider_verifiable_build_provenance() -> None:
    _not_implemented(
        "bind the exact read-only CI build artifact/image digest to provider-verifiable provenance "
        "and verify it before promotion"
    )
