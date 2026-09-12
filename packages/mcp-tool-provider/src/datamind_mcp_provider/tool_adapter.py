from __future__ import annotations

from typing import Any
from datamind.core.tools import ToolSpec, ToolRegistry


def registry_from_tools(
    tools: list[dict[str, Any]],
    client: Any,
    *,
    context: dict[str, Any],
    allowed: set[str] | None = None,
    allowed_access: set[str] | None = None,
) -> ToolRegistry:
    """Convert a DataPlane catalogue into a role-scoped registry.

    New DataPlane catalogues declare ``access`` explicitly.  ``allowed`` is
    retained only for compatibility with older callers; production providers
    should use ``allowed_access`` so adding a tool does not require editing a
    second name whitelist.
    """
    registry = ToolRegistry()
    for item in tools:
        name = str(item.get("name") or "")
        if allowed is not None and name not in allowed:
            continue
        schema = item.get("inputSchema") or item.get("input_schema") or {"type": "object"}

        declared_access = str(
            item.get("access")
            or (item.get("annotations") or {}).get("access")
            or ""
        )
        access = declared_access if declared_access in {"read", "write", "utility"} else "write" if name in {
            "kb_add_text", "kb_add_file", "kb_add_path", "kb_reindex",
            "kb_ingest_document", "kb_ingest_path",
            "db_import_records", "db_import_csv", "graph_upsert_triples",
            "graph_add_triples_from_text", "memory_save", "memory_forget", "memory_record_interaction",
            "memory_record_feedback", "skill_upsert", "wiki_upsert_source"
        } else "utility" if name in {"utility_calculate", "utility_current_time"} else "read"
        if allowed_access is not None and access not in allowed_access:
            continue

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
                              metadata={"access": access, "surface": item.get("surface")}))
    return registry
