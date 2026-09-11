from __future__ import annotations

from typing import Any
from datamind.core.contracts import ToolAccess
from datamind.core.tools import ToolRegistry
from .client import McpClient
from .tool_adapter import registry_from_tools

_READ = {"kb_search", "kb_list_documents", "kb_count", "db_list_tables", "db_describe_table", "db_query_sql", "db_query_nl",
         "graph_search_entities", "graph_traverse", "graph_neighbors", "skill_search", "skill_get", "skill_list",
         "memory_recall", "memory_list_profiles"}
_WRITE = {"kb_add_text", "kb_add_file", "kb_add_path", "kb_reindex", "db_import_records", "db_import_csv",
          "graph_upsert_triples", "graph_add_triples_from_text", "memory_save", "memory_forget", "skill_upsert",
          "pdf_extract_text"}


class McpToolProvider:
    def __init__(self, client: McpClient, *, context: dict[str, Any], store_client: McpClient | None = None) -> None:
        self.client = client
        self.store_client = store_client or client
        self.context = context
        self._tools: dict[int, list[dict[str, Any]]] = {}

    async def _catalog(self, client: McpClient) -> list[dict[str, Any]]:
        key = id(client)
        if key not in self._tools:
            self._tools[key] = await client.list_tools()
        return self._tools[key]

    async def retrieve_tools(self, context: Any) -> ToolRegistry:
        registry = registry_from_tools(await self._catalog(self.client), self.client, context=self.context, allowed=_READ)
        registry.assert_access({ToolAccess.READ, ToolAccess.UTILITY})
        return registry

    async def store_tools(self, context: Any) -> ToolRegistry:
        registry = registry_from_tools(await self._catalog(self.store_client), self.store_client, context=self.context, allowed=_WRITE)
        registry.assert_access({ToolAccess.WRITE})
        return registry

    async def close(self) -> None:
        await self.client.close()
        if self.store_client is not self.client:
            await self.store_client.close()
