from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

_log = logging.getLogger("datamind.gateway.audit")


def event(name: str, *, context: dict[str, Any], payload: Any = None, **fields: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) if payload is not None else ""
    _log.info(json.dumps({"event": name, **fields, "tenant_id": context.get("tenant_id"),
                          "profile_id": context.get("profile_id"), "trace_id": context.get("trace_id"),
                          "payload_sha256": hashlib.sha256(body.encode()).hexdigest() if body else None,
                          "payload_size": len(body)}))
