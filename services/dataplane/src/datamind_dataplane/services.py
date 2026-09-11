from __future__ import annotations

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
from .rag import exact_uid_results, make_search_handler
from .pdf import build_pdf_tools


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
        if (os.environ.get("DATAMIND_ENV", "development").lower() == "production"
                and settings.embedding.provider in {"openai", "openai_compatible"}
                and (settings.embedding.api_base is None or settings.embedding.api_key is None)):
            raise RuntimeError(
                "production DataPlane requires DATAMIND__EMBEDDING__API_BASE and "
                "DATAMIND__EMBEDDING__API_KEY"
            )
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
        kb = build_kb_service(settings, llm_client=client, embedding=embedding)
        db = build_db_service(settings, llm_client=client)
        graph = build_graph_service(settings)
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
        self.registry.extend(build_graph_tools(graph))
        self.registry.extend(build_memory_tools(build_memory_service(settings, llm_client=client, embedding=embedding)))
        skills = build_skills_service(settings, embedding=embedding)
        self.registry.extend(build_skills_tools(skills))
        self.registry.extend(build_skills_store_tools(skills))
        self.registry.extend(build_ingest_tools(build_ingest_service(settings=settings, kb=kb, db=db, graph=graph, llm_client=client)))
        # PDF extraction is an internal StoreAgent capability.  It is kept in
        # the DataPlane so every ingress path follows the same text/OCR flow.
        self.registry.extend(build_pdf_tools())

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        spec = self.registry.get(name)
        return await spec.handler(**arguments)
