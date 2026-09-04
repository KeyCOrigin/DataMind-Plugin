from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any


def receipt(tool: str, context: dict[str, Any], result: Any, *, status: str = "stored") -> dict[str, Any]:
    body = json.dumps(result, sort_keys=True, default=str, ensure_ascii=False)
    return {"receipt_id": uuid.uuid4().hex, "tool": tool, "status": status,
            "tenant_id": context["tenant_id"], "profile_id": context["profile_id"],
            "result_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "created_at": datetime.now(timezone.utc).isoformat(), "result": result}
