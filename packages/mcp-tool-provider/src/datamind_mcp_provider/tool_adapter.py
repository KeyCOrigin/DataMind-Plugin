from __future__ import annotations

from typing import Any
from datamind.core.tools import ToolSpec, ToolRegistry


def registry_from_tools(tools: list[dict[str, Any]], client: Any, *, context: dict[str, Any], allowed: set[str]) -> ToolRegistry:
    registry = ToolRegistry()
    for item in tools:
        name = str(item.get("name") or "")
        if name not in allowed:
            continue
        schema = item.get("inputSchema") or item.get("input_schema") or {"type": "object"}

        access = "write" if name in {
            "kb_add_text", "kb_add_file", "kb_add_path", "kb_reindex",
            "db_import_records", "db_import_csv", "graph_upsert_triples",
            "graph_add_triples_from_text", "memory_save", "memory_forget", "skill_upsert",
            "pdf_extract_text"
        } else "read"

        async def invoke(_name: str = name, _access: str = access, **kwargs: Any) -> Any:
            # Gateway's public StoreAgent call already required explicit
            # confirmation. Carry that decision across the local MCP
            # boundary so DataPlane can enforce its own write guard without
            # exposing an internal confirmation parameter to the model.
            if _access == "write":
                kwargs.setdefault("confirm", True)
            return await client.call_tool(_name, {**kwargs, "_context": context})

        registry.add(ToolSpec(name=name, description=str(item.get("description") or name),
                              input_schema=schema, handler=invoke,
                              metadata={"access": access}))
    return registry
