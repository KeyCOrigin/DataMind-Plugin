from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StoreBatchItem(BaseModel):
    """One independent item in a StoreAgent batch."""

    source: str = Field(min_length=1, max_length=512)
    text: str = ""
    kind: Literal["text", "table"] = "text"
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoreBatchRequest(BaseModel):
    """Gateway-facing request for one StoreAgent batch session."""

    items: list[StoreBatchItem] = Field(min_length=1, max_length=500)
    confirm: bool = False
    source_trust: Literal["internal", "external"] = "internal"


class StoreBatchItemResult(BaseModel):
    source: str
    status: Literal["completed", "failed"]
    receipts: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class StoreBatchResult(BaseModel):
    status: Literal["completed", "partial", "failed"]
    items: list[StoreBatchItemResult]
    receipts: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


__all__ = [
    "StoreBatchItem",
    "StoreBatchRequest",
    "StoreBatchItemResult",
    "StoreBatchResult",
]
