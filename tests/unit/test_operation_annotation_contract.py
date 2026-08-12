from __future__ import annotations

from kontomierz_mcp.manifests import TOOL_DEFINITIONS


def test_governed_operation_annotations_use_supported_scalar_vocabulary() -> None:
    annotations = {
        parameter.annotation for definition in TOOL_DEFINITIONS.values() for parameter in definition.parameters
    }
    assert annotations <= {"str", "str | None", "int", "int | None", "bool"}
