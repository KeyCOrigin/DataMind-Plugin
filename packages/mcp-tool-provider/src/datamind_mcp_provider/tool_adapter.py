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

        async def invoke(_name: str = name, **kwargs: Any) -> Any:
            return await client.call_tool(_name, {**kwargs, "_context": context})

        registry.add(ToolSpec(name=name, description=str(item.get("description") or name),
                              input_schema=schema, handler=invoke,
                              metadata={"access": "write" if name in {
                                  "kb_add_text", "kb_add_file", "kb_add_path", "kb_reindex",
                                  "db_import_records", "db_import_csv", "graph_upsert_triples",
                                  "graph_add_triples_from_text", "memory_save", "memory_forget", "skill_upsert"
                              } else "read"}))
    return registry
