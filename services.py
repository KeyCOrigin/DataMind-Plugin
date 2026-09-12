from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from datamind.config import Settings
from datamind.capabilities.embedding import build_embedding
from datamind.capabilities.kb import build_kb_service, build_kb_tools
from datamind.capabilities.db import build_db_service, build_db_tools
from datamind.capabilities.graph import build_graph_service, build_graph_tools
from datamind.capabilities.memory import build_memory_service, build_memory_tools
from datamind.capabilities.skills import build_skills_service, build_skills_tools, build_skills_store_tools
from datamind.capabilities.ingest import build_ingest_service, build_ingest_tools
from datamind.core.tools import ToolRegistry, ToolSpec
from dataclasses import replace
from .rag import exact_uid_results, make_search_handler
from .pdf import build_pdf_tools


_log = logging.getLogger(__name__)


def data_root() -> Path:
    """Resolve local data without tying the service to a checkout path."""
    configured = os.environ.get("DATAMIND_DATA_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / "datamind"
    return Path.home() / ".local" / "share" / "datamind"


class DataPlaneServices:
    def __init__(self, tenant_id: str, profile: str) -> None:
        settings = Settings()
        if os.environ.get("DATAMIND_ENV", "development").lower() == "production":
            missing: list[str] = []
            if settings.llm.protocol not in {"local", "ollama"} and not settings.llm.api_key:
                missing.append("DATAMIND__LLM__API_KEY")
            if settings.embedding.provider in {"openai", "openai_compatible"}:
                if not settings.embedding.api_base:
                    missing.append("DATAMIND__EMBEDDING__API_BASE")
                if not settings.embedding.api_key:
                    missing.append("DATAMIND__EMBEDDING__API_KEY")
            if missing:
                raise RuntimeError("production DataPlane missing required settings: " + ", ".join(missing))
        settings.data.profile = profile
        # Every tenant/profile receives a distinct DataMind namespace.  The
        # tenant is never taken from a tool argument; the server derives it
        # from the verified delegated token.
        root = data_root()
        settings.data.base_dir = root / "tenants" / tenant_id
        settings.ensure_dirs()
        client = __import__("datamind.core.model_clients", fromlist=["build_model_client"]).build_model_client(settings.llm)
        embedding = build_embedding(settings.embedding, fallback_llm=settings.llm)
        self.registry = ToolRegistry()
        self._ready = False
        self._ready_lock = asyncio.Lock()
        self._graph_refresh_lock = asyncio.Lock()
        self._model_client = client
        self._embedding = embedding
        kb = self.kb = build_kb_service(settings, llm_client=client, embedding=embedding)
        db = self.db = build_db_service(settings, llm_client=client)
        graph = self.graph = build_graph_service(settings)
        kb_tools = build_kb_tools(kb)
        # Keep DataMind's KB implementation as the source of truth, while
        # presenting message-level, UID-aware results to RetrieveAgent.
        search_spec = next(spec for spec in kb_tools if spec.name == "kb_search")
        kb_tools = [spec for spec in kb_tools if spec.name != "kb_search"]
        async def _exact_uid_lookup(uids: set[str]) -> list[dict[str, Any]]:
            records = await kb.vector_store.get_all_texts()
            return exact_uid_results(records, uids)

        kb_tools.append(ToolSpec(
            name=search_spec.name,
            description=search_spec.description + " Results are de-duplicated by document/message UID.",
            input_schema=search_spec.input_schema,
            handler=make_search_handler(search_spec.handler, exact_lookup=_exact_uid_lookup),
            metadata=search_spec.metadata,
        ))
        self.registry.extend(kb_tools)
        self.registry.extend(build_db_tools(db))
        graph_tools = build_graph_tools(graph)
        for spec in graph_tools:
            if spec.name in {"graph_search_entities", "graph_traverse", "graph_neighbors"}:
                original = spec.handler

                async def _read_with_refresh(*args: Any, _handler=original, **kwargs: Any) -> Any:
                    await self._refresh_graph()
                    return await _handler(*args, **kwargs)

                spec = replace(spec, handler=_read_with_refresh)
            self.registry.add(spec)
        self.memory = build_memory_service(settings, llm_client=client, embedding=embedding)
        self.registry.extend(build_memory_tools(self.memory))
        self.skills = build_skills_service(settings, embedding=embedding)
        self.registry.extend(build_skills_tools(self.skills))
        self.registry.extend(build_skills_store_tools(self.skills))
        self.registry.extend(build_ingest_tools(build_ingest_service(settings=settings, kb=kb, db=db, graph=graph, llm_client=client)))
        # PDF extraction is an internal StoreAgent capability.  It is kept in
        # the DataPlane so every ingress path follows the same text/OCR flow.
        self.registry.extend(build_pdf_tools())

    async def warmup(self) -> None:
        """Load profile skills exactly once before exposing the registry."""
        if self._ready:
            return
        async with self._ready_lock:
            if not self._ready:
                try:
                    await self.skills.load()
                except Exception as exc:  # noqa: BLE001
                    # Tool discovery must remain available during a transient
                    # embedding outage. SkillsService keeps its exact-name
                    # catalogue even when semantic indexing cannot be built.
                    _log.warning("skills semantic index unavailable: %s", exc)
                self._ready = True

    async def _refresh_graph(self) -> None:
        """Refresh the file-backed graph before reads from another MCP process."""
        store = self.graph.store
        loader = getattr(store, "_load", None)
        if not callable(loader) or not hasattr(store, "_g") or not hasattr(store, "_path"):
            return
        if getattr(store, "_dirty", False):
            return
        async with self._graph_refresh_lock:
            if getattr(store, "_dirty", False):
                return
            try:
                import networkx as nx

                def reload() -> None:
                    store._g = nx.MultiDiGraph()
                    loader()

                await asyncio.to_thread(reload)
            except Exception as exc:  # noqa: BLE001
                _log.warning("graph_refresh_failed: %s", exc)

    async def aclose(self) -> None:
        """Release every long-lived DataMind capability owned by this scope."""
        resources = (
            self.kb,
            self.db,
            self.graph,
            self.memory,
            getattr(self.skills, "_store", None),
            self._embedding,
            self._model_client,
        )
        seen: set[int] = set()
        for resource in resources:
            if resource is None or id(resource) in seen:
                continue
            seen.add(id(resource))
            close = getattr(resource, "aclose", None) or getattr(resource, "close", None)
            if callable(close):
                result = close()
                if hasattr(result, "__await__"):
                    await result

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        spec = self.registry.get(name)
        return await spec.handler(**arguments)
