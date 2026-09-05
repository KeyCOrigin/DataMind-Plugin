from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, HttpUrl


class ExternalSource(BaseModel):
    provider: str
    connection_id: str
    resource_type: str
    stream: str
    interface: str | None = None
    format: str = "records"
    source_url: HttpUrl | None = None


class ExternalItem(BaseModel):
    external_id: str
    event_type: str = "record"
    updated_at: datetime | None = None
    text: str = ""
    structured: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Checkpoint(BaseModel):
    before: str | None = None
    after: str | None = None
    expected_version: int = Field(default=0, ge=0)


class ExternalBatch(BaseModel):
    schema_version: str = "1.0"
    source: ExternalSource
    items: list[ExternalItem] = Field(min_length=1, max_length=10000)
    checkpoint: Checkpoint = Field(default_factory=Checkpoint)
    confirm: bool = False
