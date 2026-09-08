"""Small retrieval-quality adapter for the DataMind KB tool.

The underlying KB returns chunks, while mailbox users usually expect one
result per message.  This adapter keeps the DataMind retriever unchanged and
normalizes its result at the DataPlane boundary.
"""
from __future__ import annotations

import re
from typing import Any, Awaitable, Callable, Iterable


_UID_RE = re.compile(r"\buid[-_ :]*(\d+)\b", re.IGNORECASE)


def _uid_values(value: str) -> set[str]:
    return set(_UID_RE.findall(value))


def _identity(chunk: dict[str, Any]) -> str:
    source = str(chunk.get("source") or "")
    text = str(chunk.get("text") or "")
    match = _UID_RE.search(source) or _UID_RE.search(text)
    if match:
        return f"uid:{match.group(1)}"
    # Non-mail documents still need deterministic de-duplication.  A source
    # is the stable document identity; chunk ordinal is intentionally ignored.
    return f"source:{source}" if source else f"chunk:{chunk.get('id', '')}"


def normalize_results(results: list[dict[str, Any]], query: str, top_k: int) -> list[dict[str, Any]]:
    """Filter an exact UID query and return at most one best chunk per item."""
    exact_uids = _uid_values(query)
    candidates = results
    if exact_uids:
        candidates = [
            chunk for chunk in results
            if _uid_values(_identity(chunk)) & exact_uids
        ]

    best: dict[str, dict[str, Any]] = {}
    for chunk in candidates:
        key = _identity(chunk)
        previous = best.get(key)
        if previous is None or float(chunk.get("score") or 0) > float(previous.get("score") or 0):
            best[key] = chunk
    return sorted(best.values(), key=lambda item: -float(item.get("score") or 0))[:top_k]


def exact_uid_results(records: Iterable[tuple[str, str, dict[str, Any]]], uids: set[str]) -> list[dict[str, Any]]:
    """Build deterministic results for an exact UID lookup.

    This avoids relying on semantic similarity to rank an opaque numeric UID.
    """
    results: list[dict[str, Any]] = []
    for record_id, text, metadata in records:
        source = str((metadata or {}).get("source") or "")
        if not (_uid_values(text) | _uid_values(source)) & uids:
            continue
        results.append({
            "id": record_id,
            "text": text,
            "score": 1.0,
            "source": source,
            "metadata": metadata or {},
        })
    return normalize_results(results, " ".join(f"UID-{uid}" for uid in uids), len(results))


def make_search_handler(
    original: Callable[..., Awaitable[dict[str, Any]]],
    exact_lookup: Callable[[set[str]], Awaitable[list[dict[str, Any]]]] | None = None,
) -> Callable[..., Awaitable[dict[str, Any]]]:
    async def _search(query: str, top_k: int = 5, filters: dict | None = None) -> dict[str, Any]:
        # A larger candidate window is necessary before UID filtering and
        # message-level de-duplication; the public result remains top_k.
        candidate_k = min(50, max(top_k, top_k * 10))
        # Agents commonly emit an empty JSON object for "no filters".  Chroma
        # rejects that shape, so normalize it before reaching the provider.
        effective_filters = dict(filters or {}) or None
        # UID is encoded in the normalized mail text/source, not guaranteed to
        # be a vector-store metadata field.  Apply it after retrieval so an
        # exact UID query cannot be filtered out before the adapter sees it.
        uid_filter = None
        if effective_filters and "uid" in effective_filters:
            uid_filter = _uid_values(str(effective_filters.pop("uid")))
            effective_filters = effective_filters or None
        requested_uids = _uid_values(query) | (uid_filter or set())
        if requested_uids and exact_lookup is not None:
            exact = await exact_lookup(requested_uids)
            normalized = exact[:top_k]
            return {
                "query": query,
                "top_k": top_k,
                "results": normalized,
                "count": len(normalized),
                "total_count": len(exact),
                "truncated": len(exact) > top_k,
                "next_cursor": None,
            }
        raw = await original(query=query, top_k=candidate_k, filters=effective_filters)
        normalized = normalize_results(list(raw.get("results") or []), query, top_k)
        if uid_filter:
            normalized = [chunk for chunk in normalized if _uid_values(_identity(chunk)) & uid_filter]
        return {
            "query": query,
            "top_k": top_k,
            "results": normalized,
            "count": len(normalized),
            "total_count": None,
            "truncated": len(normalized) >= top_k,
            "next_cursor": None,
        }

    return _search


__all__ = ["make_search_handler", "normalize_results"]
