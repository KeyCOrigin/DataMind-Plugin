#!/usr/bin/env python3
"""Run DataMind operations in an isolated process.

The MCP server starts this helper for each operation so DataMind's module-level
settings can be configured per profile without leaking across tool calls.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import pathlib
import shutil
import sys
import traceback
from typing import Any


PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]


def bundled_repo_root() -> pathlib.Path | None:
    for candidate in (
        PLUGIN_ROOT / "vendor" / "datamind",
        PLUGIN_ROOT / "vendor" / "DataMind",
    ):
        if (candidate / "config.py").is_file() and (candidate / "core").is_dir():
            return candidate.resolve()
    return None


def resolve_repo_root() -> pathlib.Path:
    env_root = os.environ.get("DATAMIND_REPO_ROOT")
    marker_path = PLUGIN_ROOT / ".datamind-repo-root"
    if env_root:
        return pathlib.Path(env_root).expanduser().resolve()
    if marker_path.is_file():
        marker = marker_path.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
        if marker:
            return pathlib.Path(marker).expanduser().resolve()
    bundled = bundled_repo_root()
    if bundled is not None:
        return bundled
    return PLUGIN_ROOT.parents[1].resolve()


REPO_ROOT = resolve_repo_root()


class TaskError(Exception):
    """Expected task-level error."""


def _read_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TaskError("Task payload must be a JSON object.")
    return payload


def _safe_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    return bool(value)


def _prepare_environment(payload: dict[str, Any]) -> None:
    profile = str(payload.get("profile") or os.environ.get("DATA_PROFILE") or "default")
    os.environ["DATA_PROFILE"] = profile

    data_dir = payload.get("data_dir") or payload.get("folder_path")
    if data_dir:
        data_path = pathlib.Path(os.path.expanduser(str(data_dir))).resolve()
        if not data_path.is_dir():
            raise TaskError(f"Data folder does not exist: {data_path}")
        os.environ["DATA_DIR_OVERRIDE"] = str(data_path)

    storage_dir = payload.get("storage_dir")
    if storage_dir:
        os.environ["STORAGE_DIR_OVERRIDE"] = str(pathlib.Path(os.path.expanduser(str(storage_dir))).resolve())

    similarity_top_k = payload.get("similarity_top_k")
    if similarity_top_k is not None:
        os.environ["SIMILARITY_TOP_K"] = str(int(similarity_top_k))

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


def _load_runtime():
    try:
        import config as config_mod
    except ModuleNotFoundError as exc:
        raise TaskError(
            f"DataMind dependency is missing: {exc.name}. "
            "Install the project dependencies with `pip install -r requirements.txt` "
            "in the DataMind repository environment."
        ) from exc

    env_file = REPO_ROOT / ".env"
    cfg = config_mod.Settings(_env_file=str(env_file) if env_file.exists() else None)
    config_mod.settings = cfg
    return cfg


def _init_models(cfg):
    from core.bootstrap import (
        _create_embed_model,
        _create_image_embed_model,
        _create_llm,
        _create_multimodal_llm,
    )
    from llama_index.core import Settings as LlamaSettings

    llm = _create_llm(cfg)
    embed_model = _create_embed_model(cfg)
    image_embed_model = _create_image_embed_model(cfg)
    multimodal_llm = _create_multimodal_llm(cfg)
    LlamaSettings.llm = llm
    LlamaSettings.embed_model = embed_model
    return llm, embed_model, image_embed_model, multimodal_llm


def _safe_rmtree(path: str) -> None:
    target = pathlib.Path(path).resolve()
    protected = {
        pathlib.Path("/").resolve(),
        pathlib.Path.home().resolve(),
        REPO_ROOT.resolve(),
        (REPO_ROOT / "data").resolve(),
        (REPO_ROOT / "plugins").resolve(),
    }
    if target in protected or len(target.parts) < 4:
        raise TaskError(f"Refusing to remove unsafe path: {target}")
    if target.exists():
        shutil.rmtree(target)


def _count_vectors(storage_dir: str) -> dict[str, int]:
    try:
        import chromadb

        client = chromadb.PersistentClient(path=storage_dir)
        counts: dict[str, int] = {}
        for name in ("rag_allinone", "rag_text", "rag_image", "skills_knowledge"):
            try:
                counts[name] = client.get_or_create_collection(name).count()
            except Exception:
                counts[name] = 0
        return counts
    except Exception:
        return {}


def _serialize_sources(response: Any, limit: int = 6) -> list[dict[str, Any]]:
    sources = []
    for node_with_score in list(getattr(response, "source_nodes", []) or [])[:limit]:
        node = getattr(node_with_score, "node", None)
        metadata = dict(getattr(node, "metadata", {}) or {}) if node is not None else {}
        text = ""
        if node is not None:
            try:
                text = node.get_content(metadata_mode="none")
            except Exception:
                text = str(getattr(node, "text", "") or "")
        sources.append(
            {
                "score": getattr(node_with_score, "score", None),
                "metadata": metadata,
                "text_preview": text[:700],
            }
        )
    return sources


def _read_optional_text(path_value: Any, max_chars: int = 12000) -> str:
    if not path_value:
        return ""
    path = pathlib.Path(os.path.expanduser(str(path_value))).resolve()
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:max_chars]


def _profile_payload(cfg) -> dict[str, Any]:
    return {
        "profile": cfg.data_profile,
        "data_dir": cfg.data_dir,
        "storage_dir": cfg.storage_dir,
    }


def _build_rag_index(cfg, image_embed_model) -> dict[str, Any]:
    from modules.rag.indexer import build_index, load_documents, load_pre_chunked

    result = load_pre_chunked(image_embed_model=image_embed_model)
    text_nodes = result.get("text_nodes", [])
    image_nodes = result.get("image_nodes", [])
    if text_nodes or image_nodes:
        build_index(
            text_nodes=text_nodes,
            image_nodes=image_nodes,
            image_embed_model=image_embed_model,
        )
        return {
            "mode": "pre_chunked",
            "text_nodes": len(text_nodes),
            "image_nodes": len(image_nodes),
        }

    docs = load_documents()
    if not docs:
        return {"mode": "empty", "documents": 0}
    build_index(documents=docs, image_embed_model=image_embed_model)
    return {"mode": "documents", "documents": len(docs)}


def _build_graph_index() -> dict[str, Any]:
    from modules.graphrag.graph_rag import (
        build_graph_from_triplets,
        build_graph_index,
        load_triplets_from_file,
    )

    entities, relations = load_triplets_from_file()
    if entities:
        build_graph_from_triplets(entities, relations)
        return {
            "mode": "triplets",
            "entity_count": len(entities),
            "relation_count": len(relations),
        }

    index = build_graph_index()
    if index is None:
        return {"mode": "empty", "entity_count": 0, "relation_count": 0}
    return {"mode": "documents"}


def refresh(payload: dict[str, Any]) -> dict[str, Any]:
    _prepare_environment(payload)
    cfg = _load_runtime()
    force_rebuild = _safe_bool(payload.get("force_rebuild"), True)
    rebuild_rag = _safe_bool(payload.get("rebuild_rag"), True)
    rebuild_graph = _safe_bool(payload.get("rebuild_graph"), True)

    if force_rebuild:
        _safe_rmtree(cfg.storage_dir)
    pathlib.Path(cfg.storage_dir).mkdir(parents=True, exist_ok=True)

    llm, _embed_model, image_embed_model, _multimodal_llm = _init_models(cfg)
    _ = llm

    result: dict[str, Any] = {
        **_profile_payload(cfg),
        "force_rebuild": force_rebuild,
        "rag": None,
        "graph": None,
    }
    if rebuild_rag:
        result["rag"] = _build_rag_index(cfg, image_embed_model)
    if rebuild_graph:
        result["graph"] = _build_graph_index()
    result["vector_counts"] = _count_vectors(cfg.storage_dir)
    return result


async def _rag_query_async(payload: dict[str, Any]) -> dict[str, Any]:
    _prepare_environment(payload)
    cfg = _load_runtime()
    llm, _embed_model, image_embed_model, multimodal_llm = _init_models(cfg)

    from modules.agent.agent import _build_rag_query_engine
    from modules.rag.indexer import get_or_create_index

    index = get_or_create_index(image_embed_model=image_embed_model)
    if index is None:
        raise TaskError(f"No RAG index or source documents found for profile {cfg.data_profile}.")

    query = str(payload.get("query") or "").strip()
    if not query:
        raise TaskError("query is required.")

    memory_context = _read_optional_text(payload.get("memory_context_path"))
    query_for_engine = query
    if memory_context:
        query_for_engine = (
            "以下是 DataMind 的可累积上下文，可能包含 LLM Wiki、用户长期记忆和偏好。"
            "请优先结合这些上下文，但事实性结论仍要受检索到的资料约束，不要编造未检索到的事实。\n"
            f"{memory_context}\n\n用户问题: {query}"
        )

    query_engine = _build_rag_query_engine(index, llm, multimodal_llm)
    response = await query_engine.aquery(query_for_engine)
    return {
        **_profile_payload(cfg),
        "query": query,
        "memory_context_used": bool(memory_context),
        "answer": str(response),
        "sources": _serialize_sources(response),
        "vector_counts": _count_vectors(cfg.storage_dir),
    }


def rag_query(payload: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(_rag_query_async(payload))


def graph_query(payload: dict[str, Any]) -> dict[str, Any]:
    _prepare_environment(payload)
    cfg = _load_runtime()
    _init_models(cfg)

    from modules.graphrag.graph_rag import create_graph_query_engine, get_or_create_graph_index

    query = str(payload.get("query") or "").strip()
    if not query:
        raise TaskError("query is required.")

    memory_context = _read_optional_text(payload.get("memory_context_path"))
    query_for_engine = query
    if memory_context:
        query_for_engine = (
            "以下是 DataMind 的可累积上下文，可能包含 LLM Wiki、用户长期记忆和偏好。"
            "请优先结合这些上下文，但关系事实必须来自知识图谱。\n"
            f"{memory_context}\n\n用户问题: {query}"
        )

    index = get_or_create_graph_index()
    if index is None:
        raise TaskError(f"No GraphRAG index or source documents found for profile {cfg.data_profile}.")

    engine = create_graph_query_engine(index)
    response = engine.query(query_for_engine)
    return {
        **_profile_payload(cfg),
        "query": query,
        "memory_context_used": bool(memory_context),
        "answer": str(response),
        "sources": _serialize_sources(response),
    }


def status(payload: dict[str, Any]) -> dict[str, Any]:
    _prepare_environment(payload)
    cfg = _load_runtime()
    graph_dir = pathlib.Path(cfg.storage_dir) / "graph"
    graph_visualization = graph_dir / "knowledge_graph.html"
    return {
        **_profile_payload(cfg),
        "data_dir_exists": pathlib.Path(cfg.data_dir).is_dir(),
        "storage_dir_exists": pathlib.Path(cfg.storage_dir).exists(),
        "vector_counts": _count_vectors(cfg.storage_dir),
        "graph_dir_exists": graph_dir.exists(),
        "graph_visualization": str(graph_visualization) if graph_visualization.is_file() else None,
    }


def consolidate_memory(payload: dict[str, Any]) -> dict[str, Any]:
    _prepare_environment(payload)
    cfg = _load_runtime()
    llm, _embed_model, _image_embed_model, _multimodal_llm = _init_models(cfg)

    events_path = pathlib.Path(os.path.expanduser(str(payload.get("events_path") or ""))).resolve()
    if not events_path.is_file():
        raise TaskError(f"events_path does not exist: {events_path}")

    max_events = int(payload.get("max_events") or 80)
    events = []
    with events_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    events = events[-max_events:]
    if not events:
        raise TaskError("No interaction events to consolidate.")

    transcript_lines = []
    for event in events:
        for msg in event.get("messages", []):
            role = msg.get("role", "unknown")
            content = str(msg.get("content", "")).strip()
            if content:
                transcript_lines.append(f"{role}: {content}")
    transcript = "\n".join(transcript_lines)[-24000:]

    prompt = f"""\
你是 DataMind 的长期记忆整理器。请从下面的 Codex 交互记录中提炼两份 Markdown:

1. MEMORY: 用户长期偏好、项目背景、术语、已做决定、重要路径、禁忌和未完成事项。
2. SKILL: 可以被 Codex 复用的操作流程、命令步骤、判断规则和工具使用习惯。

要求:
- 只记录有长期价值的信息，不要复述临时闲聊。
- 不要记录 API key、密码、token 或其他敏感明文。
- 用中文，条理清晰。
- 如果没有足够信息，也要返回简短占位。

请严格按如下格式输出:
## MEMORY
...

## SKILL
...

交互记录:
{transcript}
"""
    response = llm.complete(prompt)
    text = str(response).strip()

    if "## SKILL" in text:
        memory_text, skill_text = text.split("## SKILL", 1)
        memory_text = memory_text.replace("## MEMORY", "", 1).strip()
        skill_text = skill_text.strip()
    else:
        memory_text = text
        skill_text = "- 暂无可沉淀为技能的稳定流程。"

    session_id = str(payload.get("session_id") or "default")
    if not payload.get("memory_path"):
        raise TaskError("memory_path is required.")
    if not payload.get("skill_path"):
        raise TaskError("skill_path is required.")
    memory_path = pathlib.Path(os.path.expanduser(str(payload["memory_path"]))).resolve()
    skill_path = pathlib.Path(os.path.expanduser(str(payload["skill_path"]))).resolve()
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.parent.mkdir(parents=True, exist_ok=True)

    memory_doc = f"# DataMind Memory: {session_id}\n\n{memory_text}\n"
    skill_doc = f"# DataMind Skill: {session_id}\n\n{skill_text}\n"
    memory_path.write_text(memory_doc, encoding="utf-8")
    skill_path.write_text(skill_doc, encoding="utf-8")

    return {
        "profile": cfg.data_profile,
        "session_id": session_id,
        "events_used": len(events),
        "memory_path": str(memory_path),
        "skill_path": str(skill_path),
        "memory_preview": memory_doc[:1200],
        "skill_preview": skill_doc[:1200],
    }


TASKS = {
    "consolidate_memory": consolidate_memory,
    "refresh": refresh,
    "rag_query": rag_query,
    "graph_query": graph_query,
    "status": status,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=sorted(TASKS))
    args = parser.parse_args()

    try:
        payload = _read_payload()
        with contextlib.redirect_stdout(sys.stderr):
            result = TASKS[args.task](payload)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
        return 0
    except ModuleNotFoundError as exc:
        traceback.print_exc(file=sys.stderr)
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": (
                        f"Missing DataMind dependency: {exc.name}. "
                        "Install dependencies with `pip install -r requirements.txt`."
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 1
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
