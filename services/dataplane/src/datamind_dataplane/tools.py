from __future__ import annotations

from typing import Any
from datamind.core.tools import ToolRegistry


def catalog(registry: ToolRegistry, scopes: set[str] | None = None) -> list[dict[str, Any]]:
    from .authorization import authorize
    result = []
    for name in registry.names():
        if scopes is not None:
            try:
                authorize(name, scopes)
            except Exception:
                continue
        spec = registry.get(name)
        result.append({"name": name, "description": spec.description,
                       "inputSchema": spec.input_schema,
                       "annotations": {"readOnlyHint": spec.access.value == "read"}})
    return result
