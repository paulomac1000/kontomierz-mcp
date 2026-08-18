from __future__ import annotations

import pytest

from kontomierz_mcp.authorization import AuthorizationPolicy
from kontomierz_mcp.config import Settings
from kontomierz_mcp.errors import ApplicationError, ErrorCode
from kontomierz_mcp.manifests import TOOL_MANIFESTS
from kontomierz_mcp.security import InvocationContext


@pytest.mark.parametrize("invalid_id", [None, False, 0, -1, 1.0, "1"])
def test_id_bound_capability_rejects_unresolved_resource_before_authorization(invalid_id: object) -> None:
    policy = AuthorizationPolicy(Settings(api_key="", mock_data=True))

    with pytest.raises(ApplicationError) as captured:
        policy.authorize(
            InvocationContext.local_stdio(),
            TOOL_MANIFESTS["update_wallet"],
            {"wallet_id": invalid_id},
        )

    assert captured.value.code is ErrorCode.INVALID_PARAMETER
    assert captured.value.message == "wallet_id must be a positive integer"


def test_id_bound_capability_authorizes_exact_positive_integer_resource() -> None:
    policy = AuthorizationPolicy(Settings(api_key="", mock_data=True))

    decision = policy.authorize(
        InvocationContext.local_stdio(),
        TOOL_MANIFESTS["update_wallet"],
        {"wallet_id": 7},
    )

    assert decision.allowed is True
    assert decision.resource_identity == "wallet:7"
