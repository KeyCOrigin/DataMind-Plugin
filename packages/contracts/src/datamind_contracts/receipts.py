from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ReceiptStatus(str, Enum):
    accepted = "accepted"
    unchanged = "unchanged"
    stored = "stored"
    failed = "failed"


class Receipt(BaseModel):
    receipt_id: str
    tenant_id: str
    profile_id: str
    status: ReceiptStatus
    operation: str
    external_id: str | None = None
    content_hash: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
