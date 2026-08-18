"""Complete governed definition catalog assembled from bounded modules."""

from .manifest_core import ToolDefinition
from .tool_definitions_primary import PRIMARY_TOOL_DEFINITIONS
from .tool_definitions_secondary import SECONDARY_TOOL_DEFINITIONS
from .tool_definitions_tertiary import TERTIARY_TOOL_DEFINITIONS

TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    **PRIMARY_TOOL_DEFINITIONS,
    **SECONDARY_TOOL_DEFINITIONS,
    **TERTIARY_TOOL_DEFINITIONS,
}

_EXPECTED = sum(len(part) for part in (PRIMARY_TOOL_DEFINITIONS, SECONDARY_TOOL_DEFINITIONS, TERTIARY_TOOL_DEFINITIONS))
if len(TOOL_DEFINITIONS) != _EXPECTED:
    raise RuntimeError("duplicate governed tool definition")
