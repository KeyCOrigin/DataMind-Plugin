"""Lightweight structured memory store for the DataMind Codex plugin.

This module intentionally keeps the MVP local and dependency-free:
SQLite is the durable store, FTS5 is used when available, and callers
must treat every failure as non-fatal so the legacy Markdown memory path
continues to work.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


STATUSES = {"active", "archived", "deleted"}
SCOPES = {"global", "profile", "session"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_items (
          id TEXT PRIMARY KEY,
          scope TEXT NOT NULL DEFAULT 'global',
          profile TEXT,
          session_id TEXT,
          kind TEXT NOT NULL DEFAULT 'memory',
          title TEXT NOT NULL DEFAULT '',
          content TEXT NOT NULL,
          tags_json TEXT NOT NULL DEFAULT '[]',
          source TEXT NOT NULL DEFAULT '',
          source_ref TEXT NOT NULL DEFAULT '',
          metadata_json TEXT NOT NULL DEFAULT '{}',
          confidence REAL NOT NULL DEFAULT 0.7,
          status TEXT NOT NULL DEFAULT 'active',
          version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          last_used_at TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory_items(scope, profile, session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_status ON memory_items(status, updated_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_kind ON memory_items(kind, updated_at)")
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts USING fts5(
              item_id UNINDEXED,
              title,
              content,
              tags,
              tokenize = 'unicode61'
            )
            """
        )
    except sqlite3.OperationalError:
        # Some SQLite builds omit FTS5. Search falls back to LIKE.
        pass
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_traces (
          id TEXT PRIMARY KEY,
          profile TEXT,
          session_id TEXT,
          mode TEXT NOT NULL DEFAULT '',
          query TEXT NOT NULL DEFAULT '',
          answer TEXT NOT NULL DEFAULT '',
          sources_json TEXT NOT NULL DEFAULT '[]',
          query_context_json TEXT NOT NULL DEFAULT '{}',
          metadata_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_traces_scope ON feedback_traces(profile, session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_traces_updated ON feedback_traces(updated_at)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_events (
          id TEXT PRIMARY KEY,
          trace_id TEXT,
          profile TEXT,
          session_id TEXT,
          next_state_role TEXT NOT NULL DEFAULT 'user',
          next_state TEXT NOT NULL DEFAULT '',
          score INTEGER NOT NULL DEFAULT 0,
          label TEXT NOT NULL DEFAULT 'neutral',
          hint TEXT NOT NULL DEFAULT '',
          metadata_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_events_trace ON feedback_events(trace_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_events_scope ON feedback_events(profile, session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_events_score ON feedback_events(score, updated_at)")
    conn.commit()


def fts_available(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_items_fts'"
    ).fetchone()
    return row is not None


def stable_id(
    *,
    scope: str,
    profile: str | None,
    session_id: str | None,
    kind: str,
    content: str,
    source_ref: str | None = None,
) -> str:
    digest = hashlib.sha1(
        "\n".join(
            [
                scope,
                profile or "",
                session_id or "",
                kind,
                content.strip(),
                source_ref or "",
            ]
        ).encode("utf-8")
    ).hexdigest()[:20]
    return f"mem_{digest}"


def normalize_tags(tags: Any) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        values = re.split(r"[,，\s]+", tags)
    elif isinstance(tags, list):
        values = [str(value) for value in tags]
    else:
        return []
    out: list[str] = []
    seen = set()
    for value in values:
        tag = re.sub(r"\s+", "-", value.strip().lower())
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag[:48])
    return out[:16]


def title_from_content(content: str, fallback: str = "Memory") -> str:
    first = next((line.strip(" -#\t") for line in content.splitlines() if line.strip()), "")
    first = re.sub(r"\s+", " ", first).strip()
    return (first[:120] if first else fallback) or fallback


def infer_kind(metadata: dict[str, Any] | None, default: str = "memory") -> str:
    metadata = metadata or {}
    raw = str(metadata.get("kind") or metadata.get("type") or default).strip().lower()
    raw = re.sub(r"[^a-z0-9_.-]+", "_", raw).strip("._-")
    if not raw:
        return default
    if "preference" in raw or "habit" in raw:
        return "preference"
    if "decision" in raw:
        return "decision"
    if "workflow" in raw or "skill" in raw:
        return "workflow" if "workflow" in raw else "skill"
    if "profile_binding" in raw:
        return "profile_binding"
    return raw[:48]


def add_item(
    conn: sqlite3.Connection,
    *,
    content: str,
    scope: str = "global",
    profile: str | None = None,
    session_id: str | None = None,
    kind: str = "memory",
    title: str | None = None,
    tags: Any = None,
    source: str = "",
    source_ref: str = "",
    metadata: dict[str, Any] | None = None,
    confidence: float = 0.7,
    status: str = "active",
    item_id: str | None = None,
) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise ValueError("content is required")
    if scope not in SCOPES:
        scope = "global"
    if status not in STATUSES:
        status = "active"
    metadata = metadata or {}
    tag_list = normalize_tags(tags if tags is not None else metadata.get("tags"))
    now = utc_now()
    mid = item_id or stable_id(
        scope=scope,
        profile=profile,
        session_id=session_id,
        kind=kind,
        content=text,
        source_ref=source_ref,
    )
    existing = conn.execute("SELECT created_at, version FROM memory_items WHERE id=?", (mid,)).fetchone()
    created_at = existing["created_at"] if existing else now
    version = int(existing["version"]) + 1 if existing else 1
    row = {
        "id": mid,
        "scope": scope,
        "profile": profile,
        "session_id": session_id,
        "kind": kind,
        "title": title or title_from_content(text, fallback=kind.replace("_", " ").title()),
        "content": text,
        "tags_json": json.dumps(tag_list, ensure_ascii=False),
        "source": source,
        "source_ref": source_ref,
        "metadata_json": json.dumps(metadata, ensure_ascii=False, sort_keys=True),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "status": status,
        "version": version,
        "created_at": created_at,
        "updated_at": now,
        "last_used_at": None,
    }
    conn.execute(
        """
        INSERT INTO memory_items (
          id, scope, profile, session_id, kind, title, content, tags_json,
          source, source_ref, metadata_json, confidence, status, version,
          created_at, updated_at, last_used_at
        ) VALUES (
          :id, :scope, :profile, :session_id, :kind, :title, :content, :tags_json,
          :source, :source_ref, :metadata_json, :confidence, :status, :version,
          :created_at, :updated_at, :last_used_at
        )
        ON CONFLICT(id) DO UPDATE SET
          scope=excluded.scope,
          profile=excluded.profile,
          session_id=excluded.session_id,
          kind=excluded.kind,
          title=excluded.title,
          content=excluded.content,
          tags_json=excluded.tags_json,
          source=excluded.source,
          source_ref=excluded.source_ref,
          metadata_json=excluded.metadata_json,
          confidence=excluded.confidence,
          status=excluded.status,
          version=excluded.version,
          updated_at=excluded.updated_at
        """,
        row,
    )
    sync_fts(conn, row)
    conn.commit()
    return serialize_row(row)


def sync_fts(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    if not fts_available(conn):
        return
    conn.execute("DELETE FROM memory_items_fts WHERE item_id=?", (row["id"],))
    conn.execute(
        "INSERT INTO memory_items_fts(item_id, title, content, tags) VALUES (?, ?, ?, ?)",
        (row["id"], row["title"], row["content"], " ".join(json.loads(row["tags_json"]))),
    )


def serialize_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    for key in ("tags_json", "metadata_json"):
        try:
            data[key.replace("_json", "")] = json.loads(data.get(key) or "[]" if key == "tags_json" else data.get(key) or "{}")
        except json.JSONDecodeError:
            data[key.replace("_json", "")] = [] if key == "tags_json" else {}
    return data


def scope_sql(profile: str | None, session_id: str | None) -> tuple[str, list[Any]]:
    clauses = ["scope='global'"]
    params: list[Any] = []
    if profile:
        clauses.append("(scope='profile' AND profile=?)")
        params.append(profile)
    if session_id:
        clauses.append("(scope='session' AND session_id=?)")
        params.append(session_id)
    return "(" + " OR ".join(clauses) + ")", params


def tokenize_query(query: str) -> list[str]:
    raw = re.findall(r"[A-Za-z0-9_.:/-]{2,}|[\u4e00-\u9fff]{1,}", query.lower())
    tokens: list[str] = []
    seen = set()
    for item in raw:
        parts = [item]
        if re.fullmatch(r"[\u4e00-\u9fff]+", item) and len(item) > 2:
            parts.extend(item[i : i + 2] for i in range(len(item) - 1))
        for part in parts:
            part = part.strip("-_.:/")
            if len(part) >= 2 and part not in seen:
                seen.add(part)
                tokens.append(part[:64])
    return tokens[:12]


def fts_query(tokens: list[str]) -> str:
    safe = []
    for token in tokens:
        cleaned = re.sub(r'["\']', "", token)
        if cleaned:
            safe.append(f'"{cleaned}"')
    return " OR ".join(safe)


def search_items(
    conn: sqlite3.Connection,
    *,
    query: str,
    profile: str | None = None,
    session_id: str | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    terms = tokenize_query(query)
    if not terms:
        return []
    scope_clause, scope_params = scope_sql(profile, session_id)
    rows: list[sqlite3.Row] = []
    if fts_available(conn):
        match = fts_query(terms)
        if match:
            try:
                rows = conn.execute(
                    f"""
                    SELECT m.*, bm25(memory_items_fts) AS rank
                    FROM memory_items_fts
                    JOIN memory_items m ON m.id = memory_items_fts.item_id
                    WHERE memory_items_fts MATCH ?
                      AND m.status='active'
                      AND {scope_clause}
                    ORDER BY rank ASC, m.updated_at DESC
                    LIMIT ?
                    """,
                    [match, *scope_params, limit],
                ).fetchall()
            except sqlite3.Error:
                rows = []
    if not rows:
        rows = fallback_like_search(
            conn,
            terms=terms,
            scope_clause=scope_clause,
            scope_params=scope_params,
            limit=limit,
        )
    ids = [row["id"] for row in rows]
    if ids:
        now = utc_now()
        conn.executemany("UPDATE memory_items SET last_used_at=? WHERE id=?", [(now, mid) for mid in ids])
        conn.commit()
    return [serialize_row(row) for row in rows]


def fallback_like_search(
    conn: sqlite3.Connection,
    *,
    terms: list[str],
    scope_clause: str,
    scope_params: list[Any],
    limit: int,
) -> list[sqlite3.Row]:
    like_clause = " OR ".join(["lower(title || ' ' || content || ' ' || tags_json) LIKE ?"] * len(terms))
    params = [f"%{term.lower()}%" for term in terms]
    rows = conn.execute(
        f"""
        SELECT *
        FROM memory_items
        WHERE status='active'
          AND {scope_clause}
          AND ({like_clause})
        ORDER BY
          CASE kind
            WHEN 'preference' THEN 0
            WHEN 'decision' THEN 1
            WHEN 'feedback_hint' THEN 2
            WHEN 'workflow' THEN 3
            WHEN 'skill' THEN 4
            ELSE 5
          END,
          updated_at DESC
        LIMIT ?
        """,
        [*scope_params, *params, limit * 4],
    ).fetchall()
    scored = []
    for row in rows:
        haystack = f"{row['title']} {row['content']} {row['tags_json']}".lower()
        score = sum(1 for term in terms if term.lower() in haystack)
        scored.append((score, row["updated_at"], row))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row for _score, _updated, row in scored[:limit]]


def serialize_feedback_trace(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    for key, fallback in (("sources_json", []), ("query_context_json", {}), ("metadata_json", {})):
        try:
            data[key.replace("_json", "")] = json.loads(data.get(key) or json.dumps(fallback))
        except json.JSONDecodeError:
            data[key.replace("_json", "")] = fallback
    return data


def serialize_feedback_event(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    try:
        data["metadata"] = json.loads(data.get("metadata_json") or "{}")
    except json.JSONDecodeError:
        data["metadata"] = {}
    return data


def add_feedback_trace(
    conn: sqlite3.Connection,
    *,
    profile: str | None,
    session_id: str | None,
    mode: str,
    query: str,
    answer: str,
    sources: Any = None,
    query_context: Any = None,
    metadata: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    now = utc_now()
    tid = trace_id or "trace_" + hashlib.sha1(
        "\n".join(
            [
                now,
                profile or "",
                session_id or "",
                mode,
                query.strip(),
                answer.strip()[:1000],
            ]
        ).encode("utf-8")
    ).hexdigest()[:20]
    row = {
        "id": tid,
        "profile": profile,
        "session_id": session_id,
        "mode": mode[:32],
        "query": query.strip()[:4000],
        "answer": answer.strip()[:12000],
        "sources_json": json.dumps(sources or [], ensure_ascii=False),
        "query_context_json": json.dumps(query_context or {}, ensure_ascii=False, sort_keys=True),
        "metadata_json": json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
        "created_at": now,
        "updated_at": now,
    }
    existing = conn.execute("SELECT created_at FROM feedback_traces WHERE id=?", (tid,)).fetchone()
    if existing:
        row["created_at"] = existing["created_at"]
    conn.execute(
        """
        INSERT INTO feedback_traces (
          id, profile, session_id, mode, query, answer, sources_json,
          query_context_json, metadata_json, created_at, updated_at
        ) VALUES (
          :id, :profile, :session_id, :mode, :query, :answer, :sources_json,
          :query_context_json, :metadata_json, :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
          profile=excluded.profile,
          session_id=excluded.session_id,
          mode=excluded.mode,
          query=excluded.query,
          answer=excluded.answer,
          sources_json=excluded.sources_json,
          query_context_json=excluded.query_context_json,
          metadata_json=excluded.metadata_json,
          updated_at=excluded.updated_at
        """,
        row,
    )
    conn.commit()
    return serialize_feedback_trace(row)


def get_feedback_trace(conn: sqlite3.Connection, trace_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM feedback_traces WHERE id=?", (trace_id,)).fetchone()
    return serialize_feedback_trace(row) if row else None


def latest_feedback_trace(
    conn: sqlite3.Connection,
    *,
    profile: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    clauses = []
    params: list[Any] = []
    if profile:
        clauses.append("profile=?")
        params.append(profile)
    if session_id:
        clauses.append("session_id=?")
        params.append(session_id)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    row = conn.execute(
        f"SELECT * FROM feedback_traces {where} ORDER BY updated_at DESC LIMIT 1",
        params,
    ).fetchone()
    return serialize_feedback_trace(row) if row else None


def add_feedback_event(
    conn: sqlite3.Connection,
    *,
    trace_id: str | None,
    profile: str | None,
    session_id: str | None,
    next_state: str,
    next_state_role: str = "user",
    score: int = 0,
    label: str = "neutral",
    hint: str = "",
    metadata: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    now = utc_now()
    if score not in (-1, 0, 1):
        score = 0
    eid = event_id or "fb_" + hashlib.sha1(
        "\n".join(
            [
                now,
                trace_id or "",
                profile or "",
                session_id or "",
                str(score),
                next_state.strip()[:1000],
            ]
        ).encode("utf-8")
    ).hexdigest()[:20]
    row = {
        "id": eid,
        "trace_id": trace_id,
        "profile": profile,
        "session_id": session_id,
        "next_state_role": (next_state_role or "user")[:32],
        "next_state": next_state.strip()[:8000],
        "score": score,
        "label": (label or "neutral")[:64],
        "hint": hint.strip()[:4000],
        "metadata_json": json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
        "created_at": now,
        "updated_at": now,
    }
    conn.execute(
        """
        INSERT INTO feedback_events (
          id, trace_id, profile, session_id, next_state_role, next_state,
          score, label, hint, metadata_json, created_at, updated_at
        ) VALUES (
          :id, :trace_id, :profile, :session_id, :next_state_role, :next_state,
          :score, :label, :hint, :metadata_json, :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
          trace_id=excluded.trace_id,
          profile=excluded.profile,
          session_id=excluded.session_id,
          next_state_role=excluded.next_state_role,
          next_state=excluded.next_state,
          score=excluded.score,
          label=excluded.label,
          hint=excluded.hint,
          metadata_json=excluded.metadata_json,
          updated_at=excluded.updated_at
        """,
        row,
    )
    conn.commit()
    return serialize_feedback_event(row)


def list_feedback_events(
    conn: sqlite3.Connection,
    *,
    profile: str | None = None,
    session_id: str | None = None,
    limit: int = 20,
    score: int | None = None,
) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []
    if profile:
        clauses.append("e.profile=?")
        params.append(profile)
    if session_id:
        clauses.append("e.session_id=?")
        params.append(session_id)
    if score in (-1, 0, 1):
        clauses.append("e.score=?")
        params.append(score)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = conn.execute(
        f"""
        SELECT e.*, t.query AS trace_query, t.mode AS trace_mode
        FROM feedback_events e
        LEFT JOIN feedback_traces t ON t.id=e.trace_id
        {where}
        ORDER BY e.updated_at DESC
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    return [serialize_feedback_event(row) for row in rows]


def feedback_stats(
    conn: sqlite3.Connection,
    *,
    profile: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    trace_clauses = []
    event_clauses = []
    trace_params: list[Any] = []
    event_params: list[Any] = []
    if profile:
        trace_clauses.append("profile=?")
        event_clauses.append("profile=?")
        trace_params.append(profile)
        event_params.append(profile)
    if session_id:
        trace_clauses.append("session_id=?")
        event_clauses.append("session_id=?")
        trace_params.append(session_id)
        event_params.append(session_id)
    trace_where = "WHERE " + " AND ".join(trace_clauses) if trace_clauses else ""
    event_where = "WHERE " + " AND ".join(event_clauses) if event_clauses else ""
    trace_total = conn.execute(
        f"SELECT count(*) AS c FROM feedback_traces {trace_where}",
        trace_params,
    ).fetchone()["c"]
    event_total = conn.execute(
        f"SELECT count(*) AS c FROM feedback_events {event_where}",
        event_params,
    ).fetchone()["c"]
    by_score = {
        str(row["score"]): row["c"]
        for row in conn.execute(
            f"SELECT score, count(*) AS c FROM feedback_events {event_where} GROUP BY score ORDER BY score",
            event_params,
        ).fetchall()
    }
    pending_total = conn.execute(
        f"""
        SELECT count(*) AS c
        FROM feedback_traces t
        {trace_where}
        {"AND" if trace_where else "WHERE"} NOT EXISTS (
          SELECT 1 FROM feedback_events e WHERE e.trace_id=t.id
        )
        """,
        trace_params,
    ).fetchone()["c"]
    return {
        "traces": trace_total,
        "feedback_events": event_total,
        "pending_traces": pending_total,
        "by_score": by_score,
    }


def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    total = conn.execute("SELECT count(*) AS c FROM memory_items").fetchone()["c"]
    active = conn.execute("SELECT count(*) AS c FROM memory_items WHERE status='active'").fetchone()["c"]
    by_kind = {
        row["kind"]: row["c"]
        for row in conn.execute(
            "SELECT kind, count(*) AS c FROM memory_items GROUP BY kind ORDER BY c DESC"
        ).fetchall()
    }
    return {
        "total": total,
        "active": active,
        "by_kind": by_kind,
        "fts_available": fts_available(conn),
        "feedback": feedback_stats(conn),
    }


def render_items_markdown(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    lines = ["# DataMind Structured Memory Context", ""]
    for idx, item in enumerate(items, 1):
        tags = item.get("tags") or []
        scope_bits = [str(item.get("scope") or "global")]
        if item.get("profile"):
            scope_bits.append(f"profile={item['profile']}")
        if item.get("session_id"):
            scope_bits.append(f"session={item['session_id']}")
        meta = ", ".join(scope_bits)
        lines.append(f"{idx}. {item.get('title') or item.get('kind')}")
        lines.append(f"   - kind: `{item.get('kind')}`; scope: `{meta}`; confidence: `{item.get('confidence')}`")
        if tags:
            lines.append(f"   - tags: {', '.join(f'`{tag}`' for tag in tags[:8])}")
        content = str(item.get("content") or "").strip()
        if content:
            preview = content if len(content) <= 700 else content[:680] + "\n...[truncated]"
            lines.append("   - content: " + preview.replace("\n", "\n     "))
        lines.append("")
    return "\n".join(lines).strip()
