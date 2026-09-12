from __future__ import annotations

import asyncio
import contextvars
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
        # A bundle owns a request-scoped DataMind context.  Include every
        # identity field that can affect memory/audit isolation in the cache
        # key; tenant/profile alone would leak the first user's session.
        self._bundles: OrderedDict[tuple[str, str, str, str, str, str, str, str], tuple[AgentBundle, float]] = OrderedDict()
        self._locks: dict[tuple[str, str, str, str, str, str, str, str], asyncio.Lock] = {}
        self._max_bundles = max(1, int(os.environ.get("DATAMIND_AGENT_CACHE_SIZE", "128")))
        self._idle_timeout = max(0, int(os.environ.get("DATAMIND_AGENT_IDLE_TIMEOUT", "1800")))
        self._store_scope: contextvars.ContextVar[str] = contextvars.ContextVar(
            "datamind_store_scope", default="datamind.dataplane.write"
        )

    async def get(self, context: RequestContext) -> AgentBundle:
        """Return the one StoreAgent/RetrieveAgent pair for a context."""
        key = (
            context.tenant_id,
            context.profile_id,
            context.user_id or "",
            context.session_id,
            context.trace_id,
            context.request_id,
            context.policy_version,
            context.agent_run_id or "",
        )
        await self._evict_idle()
        if key in self._bundles:
            bundle, _ = self._bundles.pop(key)
            self._bundles[key] = (bundle, time.monotonic())
            return bundle
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            if key not in self._bundles:
                from datamind.agent import build_datamind_agents
                from datamind.core.context import RequestContext as DataMindRequestContext
                command = os.environ.get("DATAMIND_DATAPLANE_COMMAND", sys.executable)
                args = tuple(filter(None, os.environ.get(
                    "DATAMIND_DATAPLANE_ARGS", "-m datamind_dataplane.stdio_server").split()))
                retrieve_client = McpClient(command, args, token_factory=lambda: issue_service_token(
                    context, role="retrieve", scope="datamind.dataplane.read"))
                store_client = McpClient(command, args, token_factory=lambda: issue_service_token(
                    context, role="store", scope=self._store_scope.get()))
                provider = McpToolProvider(retrieve_client, store_client=store_client, context=context.model_dump())
                settings = _settings()
                settings.data.profile = context.profile_id
                # DataMind's agent builder uses its in-process context type;
                # the provider keeps the enterprise contract context above
                # for tenant/profile propagation to DataPlane.
                agent_context = DataMindRequestContext(
                    session_id=context.session_id,
                    profile=context.profile_id,
                    user_id=context.user_id,
                    trace_id=context.trace_id,
                    extra={
                        "tenant_id": context.tenant_id,
                        "request_id": context.request_id,
                        "agent_run_id": context.agent_run_id,
                    },
                )
                system = await build_datamind_agents(
                    settings, tool_provider=provider, context=agent_context
                )
                self._bundles[key] = (AgentBundle(system, provider), time.monotonic())
                while len(self._bundles) > self._max_bundles:
                    _, (old, _) = self._bundles.popitem(last=False)
                    await old.close()
            self._locks.pop(key, None)
        return self._bundles[key][0]

    async def ingest(self, context: RequestContext, message: str, *, external: bool = False) -> Any:
        """Run the one StoreAgent with a request-scoped DataPlane delegation."""
        bundle = await self.get(context)
        scope = "datamind.dataplane.external_write" if external else "datamind.dataplane.write"
        marker = self._store_scope.set(scope)
        try:
            return await bundle.system.ingest(message)
        finally:
            self._store_scope.reset(marker)

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
    # Codex's local MCP host defaults to a 120-second tool deadline. Keep
    # model and agent budgets below it so Gateway returns a result/error before
    # the host drops the call and leaves an unobserved write running.
    settings.llm.timeout_s = min(
        settings.llm.timeout_s,
        float(os.environ.get("DATAMIND_GATEWAY_LLM_TIMEOUT_SEC", "60")),
    )
    settings.llm.connect_timeout_s = min(settings.llm.connect_timeout_s, 15.0)
    settings.agent.wall_clock_timeout_s = min(
        settings.agent.wall_clock_timeout_s,
        float(os.environ.get("DATAMIND_GATEWAY_AGENT_TIMEOUT_SEC", "100")),
    )
    settings.agent.max_turns = min(settings.agent.max_turns, 8)
    settings.agent.max_tool_calls = min(settings.agent.max_tool_calls, 16)
    configured = os.environ.get("DATAMIND_DATA_ROOT", "").strip()
    if configured:
        root = configured
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "").strip()
        root = os.path.join(xdg, "datamind") if xdg else os.path.join(
            os.path.expanduser("~"), ".local", "share", "datamind")
    settings.data.base_dir = __import__("pathlib").Path(root) / "gateway"
    return settings
