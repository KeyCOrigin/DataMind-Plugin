"""Tenant-scoped Wiki, interaction log and feedback helpers.

These helpers absorb the useful local-plugin experience layer without
reintroducing a second memory database or allowing Gateway to touch storage.
All files are kept below the active DataPlane profile directory.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value).strip("-._")
    return (text[:96] or "entry")


def build_experience_tools(*, profile_dir: Path, memory: Any) -> list[Any]:
    from datamind.core.tools import ToolSpec

    wiki_dir = profile_dir / "wiki"

    async def _record_interaction(session_id: str, role: str, content: str,
                                  metadata: dict | None = None) -> dict[str, Any]:
        if not content.strip():
            raise ValueError("content is required")
        path = wiki_dir / "interactions" / f"{_safe_name(session_id)}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {"timestamp": _now(), "role": role, "content": content.strip(), "metadata": metadata or {}}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return {"session_id": session_id, "events_path": str(path), "recorded": True}

    async def _record_feedback(query: str, feedback: str, score: int = 0,
                               session_id: str | None = None) -> dict[str, Any]:
        if not feedback.strip():
            raise ValueError("feedback is required")
        if score not in {-1, 0, 1}:
            raise ValueError("score must be -1, 0 or 1")
        event = {"timestamp": _now(), "query": query.strip(), "feedback": feedback.strip(),
                 "score": score, "session_id": session_id}
        path = wiki_dir / "feedback.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        # Keep feedback searchable through the existing scoped MemoryService.
        item_id = await memory.save(
            f"用户反馈：{feedback.strip()}\n原问题：{query.strip()}",
            scope="profile", kind="workflow", metadata={"source": "feedback", "score": score},
        )
        return {"feedback_path": str(path), "memory_id": item_id, "score": score}

    async def _wiki_upsert(title: str, content: str, source: str | None = None) -> dict[str, Any]:
        if not title.strip() or not content.strip():
            raise ValueError("title and content are required")
        digest = hashlib.sha1((source or title).encode("utf-8")).hexdigest()[:10]
        path = wiki_dir / "sources" / f"{_safe_name(title)}-{digest}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        document = f"# {title.strip()}\n\n"
        if source:
            document += f"来源: `{source}`\n\n"
        document += content.strip() + "\n"
        path.write_text(document, encoding="utf-8")
        return {"path": str(path), "title": title.strip(), "source": source}

    async def _wiki_search(query: str, limit: int = 8) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("query is required")
        hits = []
        if wiki_dir.exists():
            for path in sorted(wiki_dir.rglob("*.md")):
                text = path.read_text(encoding="utf-8", errors="replace")
                if query.casefold() in text.casefold():
                    hits.append({"path": str(path), "text": text[:1200]})
                    if len(hits) >= max(1, min(limit, 50)):
                        break
        return {"query": query, "count": len(hits), "results": hits}

    async def _wiki_status() -> dict[str, Any]:
        files = list(wiki_dir.rglob("*.md")) if wiki_dir.exists() else []
        interactions = wiki_dir / "interactions"
        feedback = wiki_dir / "feedback.jsonl"
        return {
            "wiki_dir": str(wiki_dir),
            "markdown_pages": len(files),
            "interaction_sessions": len(list(interactions.glob("*.jsonl"))) if interactions.is_dir() else 0,
            "feedback_events": sum(1 for _ in feedback.open(encoding="utf-8")) if feedback.is_file() else 0,
        }

    return [
        ToolSpec(
            name="memory_record_interaction",
            description="记录当前租户/profile 的交互事件，供后续记忆整理使用。不要记录密钥、密码或完整外部正文。",
            input_schema={"type": "object", "properties": {
                "session_id": {"type": "string"}, "role": {"type": "string"},
                "content": {"type": "string"}, "metadata": {"type": "object"}},
                "required": ["session_id", "role", "content"]},
            handler=_record_interaction,
            metadata={"group": "memory", "surface": "memory", "access": "write"},
        ),
        ToolSpec(
            name="memory_record_feedback",
            description="记录用户对回答的纠正或确认，并将反馈写入当前 profile 的长期记忆。",
            input_schema={"type": "object", "properties": {
                "query": {"type": "string"}, "feedback": {"type": "string"},
                "score": {"type": "integer", "enum": [-1, 0, 1], "default": 0},
                "session_id": {"type": "string"}},
                "required": ["query", "feedback"]},
            handler=_record_feedback,
            metadata={"group": "memory", "surface": "memory", "access": "write"},
        ),
        ToolSpec(
            name="wiki_upsert_source",
            description="在当前租户/profile 的 DataPlane Wiki 中写入来源页面。",
            input_schema={"type": "object", "properties": {
                "title": {"type": "string"}, "content": {"type": "string"},
                "source": {"type": "string"}}, "required": ["title", "content"]},
            handler=_wiki_upsert,
            metadata={"group": "wiki", "surface": "memory", "access": "write"},
        ),
        ToolSpec(
            name="wiki_search",
            description="搜索当前租户/profile 的 Wiki 页面。",
            input_schema={"type": "object", "properties": {
                "query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 8}},
                "required": ["query"]},
            handler=_wiki_search,
            metadata={"group": "wiki", "surface": "memory", "access": "read"},
        ),
        ToolSpec(
            name="wiki_status",
            description="查看当前租户/profile 的 Wiki、交互记录和反馈统计。",
            input_schema={"type": "object", "properties": {}},
            handler=_wiki_status,
            metadata={"group": "wiki", "surface": "memory", "access": "read"},
        ),
    ]
