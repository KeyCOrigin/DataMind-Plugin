from __future__ import annotations

from typing import Any
from datamind.core.contracts import ToolAccess
from datamind.core.tools import ToolRegistry
from .client import McpClient
from .tool_adapter import registry_from_tools

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
        registry = registry_from_tools(
            await self._catalog(self.client), self.client,
            context=self.context, allowed_access={"read", "utility"},
        )
        registry.assert_access({ToolAccess.READ, ToolAccess.UTILITY})
        return registry

    async def store_tools(self, context: Any) -> ToolRegistry:
        registry = registry_from_tools(
            await self._catalog(self.store_client), self.store_client,
            context=self.context, allowed_access={"write"},
        )
        registry.assert_access({ToolAccess.WRITE})
        return registry

    async def close(self) -> None:
        # A retrieve/store pair may be two ScopedMcpClient views over one
        # physical transport. Close each underlying transport once.
        transports: dict[int, Any] = {}
        for client in (self.client, self.store_client):
            transport = getattr(client, "_client", client)
            transports[id(transport)] = transport
        for transport in transports.values():
            await transport.close()
