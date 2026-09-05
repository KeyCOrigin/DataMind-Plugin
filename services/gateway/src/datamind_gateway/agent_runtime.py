from __future__ import annotations

import asyncio
import os
import sys
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

    async def get(self, context: RequestContext) -> AgentBundle:
        """Return the one StoreAgent/RetrieveAgent pair for a context."""
        key = (context.tenant_id, context.profile_id, context.policy_version)
        await self._evict_idle()
        if key in self._bundles:
            bundle, _ = self._bundles.pop(key)
            self._bundles[key] = (bundle, time.monotonic())
            return bundle
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            if key not in self._bundles:
                from datamind.agent import build_datamind_agents
                command = os.environ.get("DATAMIND_DATAPLANE_COMMAND", sys.executable)
                args = tuple(filter(None, os.environ.get(
                    "DATAMIND_DATAPLANE_ARGS", "-m datamind_dataplane.stdio_server").split()))
                retrieve_client = McpClient(command, args, token_factory=lambda: issue_service_token(
                    context, role="retrieve", scope="datamind.dataplane.read"))
                store_client = McpClient(command, args, token_factory=lambda: issue_service_token(
                    context, role="store", scope="datamind.dataplane.write"))
                provider = McpToolProvider(retrieve_client, store_client=store_client, context=context.model_dump())
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
    settings = Settings()
    configured = os.environ.get("DATAMIND_DATA_ROOT", "").strip()
    if configured:
        root = configured
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "").strip()
        root = os.path.join(xdg, "datamind") if xdg else os.path.join(
            os.path.expanduser("~"), ".local", "share", "datamind")
    settings.data.base_dir = __import__("pathlib").Path(root) / "gateway"
    return settings
