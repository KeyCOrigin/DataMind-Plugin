from __future__ import annotations

import re
import uuid
from pydantic import BaseModel, Field, field_validator

_SAFE = re.compile(r"^[A-Za-z0-9_.:@/-]{1,128}$")


class RequestContext(BaseModel):
    tenant_id: str
    user_id: str | None = None
    profile_id: str = "default"
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    agent_run_id: str | None = None
    policy_version: str = "1"

    @field_validator("tenant_id", "profile_id", "session_id")
    @classmethod
    def safe_identifier(cls, value: str) -> str:
        if not _SAFE.fullmatch(str(value)):
            raise ValueError("unsafe context identifier")
        return str(value)
