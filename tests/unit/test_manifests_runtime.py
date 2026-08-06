from kontomierz_mcp.manifests import TOOL_MANIFESTS


def test_manifest_does_not_claim_unimplemented_automatic_retry() -> None:
    assert all(manifest.automatic_retry is False for manifest in TOOL_MANIFESTS.values())


def test_non_concurrent_safe_tools_have_a_target_scope() -> None:
    unsafe = [manifest for manifest in TOOL_MANIFESTS.values() if not manifest.concurrent_safe]
    assert unsafe
    assert all(manifest.target_scope == "kontomierz-account" for manifest in unsafe)
