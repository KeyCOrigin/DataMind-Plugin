from __future__ import annotations

import asyncio
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from datamind_contracts import RequestContext
from datamind_mcp_provider import McpClient, McpToolProvider
from .auth import issue_service_token


@dataclass
class AgentBundle:
    system: Any
    provider: McpToolProvider

    async def close(self) -> None:
        await self.system.aclose()
        await self.provider.close()


class AgentRuntime:
    def __init__(self) -> None:
        self._bundles: OrderedDict[tuple[str, str, str], tuple[AgentBundle, float]] = OrderedDict()
        self._locks: dict[tuple[str, str, str], asyncio.Lock] = {}
        self._max_bundles = max(1, int(os.environ.get("DATAMIND_AGENT_CACHE_SIZE", "128")))
        self._idle_timeout = max(0, int(os.environ.get("DATAMIND_AGENT_IDLE_TIMEOUT", "1800")))

    async def get(self, context: RequestContext, *, external: bool = False) -> AgentBundle:
        key = (context.tenant_id, context.profile_id, context.policy_version + (":external" if external else ""))
        await self._evict_idle()
        if key in self._bundles:
            bundle, _ = self._bundles.pop(key)
            self._bundles[key] = (bundle, time.monotonic())
            return bundle
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            if key not in self._bundles:
                from datamind.agent import build_datamind_agents
                url = os.environ["DATAMIND_DATAPLANE_MCP_URL"]
                retrieve_client = McpClient(url, token_factory=lambda: issue_service_token(
                    context, role="retrieve", scope="datamind.dataplane.read"))
                scope = "datamind.dataplane.external_write" if external else "datamind.dataplane.write"
                store_client = McpClient(url, token_factory=lambda: issue_service_token(
                    context, role="store_external" if external else "store", scope=scope))
                allowed = {"kb_add_text", "kb_add_file", "db_import_records", "db_import_csv", "graph_upsert_triples"} if external else None
                provider = McpToolProvider(retrieve_client, store_client=store_client, context=context.model_dump(), store_allowed=allowed)
                system = await build_datamind_agents(_settings(), tool_provider=provider, context=context)
                self._bundles[key] = (AgentBundle(system, provider), time.monotonic())
                while len(self._bundles) > self._max_bundles:
                    _, (old, _) = self._bundles.popitem(last=False)
                    await old.close()
        return self._bundles[key][0]

    async def _evict_idle(self) -> None:
        if not self._idle_timeout:
            return
        now = time.monotonic()
        expired = [key for key, (_, touched) in self._bundles.items() if now - touched >= self._idle_timeout]
        for key in expired:
            bundle, _ = self._bundles.pop(key)
            await bundle.close()

    async def close(self) -> None:
        bundles = [bundle for bundle, _ in self._bundles.values()]
        self._bundles.clear()
        for bundle in bundles:
            await bundle.close()


def _settings() -> Any:
    from datamind.config import Settings
    return Settings()
