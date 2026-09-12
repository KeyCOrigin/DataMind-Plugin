"""DataPlane MCP JSON-RPC dispatch used by the local stdio server."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from .authorization import authorize
from .context import DataPlaneContext, validate_context
from .receipts import receipt
from .services import DataPlaneServiceFactory
from .tools import catalog
from .guards import guard_args


_services = DataPlaneServiceFactory()


async def close_services() -> None:
    """Close the process-local DataPlane service factory."""
    await _services.aclose()


def _verify_token(value: str | None) -> dict[str, Any]:
    if not value or not value.startswith("Bearer "):
        raise ValueError("bearer token required")
    token = value[7:]
    try:
        head, body, sig = token.split(".")
        header = json.loads(base64.urlsafe_b64decode(head + "=" * (-len(head) % 4)))
        if header.get("alg") != "HS256":
            raise ValueError("algorithm")
        secret = os.environ.get("DATAMIND_SERVICE_JWT_SECRET", "development-only-change-me")
        expected = hmac.new(secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(base64.urlsafe_b64encode(expected).rstrip(b"=").decode(), sig):
            raise ValueError("signature")
        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if (
            claims.get("exp", 0) < time.time()
            or claims.get("aud") != "datamind-dataplane"
            or claims.get("iss") != "datamind-gateway"
            or claims.get("service") != "datamind-gateway"
            or not claims.get("tenant_id")
            or not claims.get("profile")
        ):
            raise ValueError("claims")
        return claims
    except Exception as exc:
        raise ValueError("invalid delegated service token") from exc


async def dispatch(message: dict[str, Any], *, authorization: str | None) -> dict[str, Any]:
    try:
        claims = _verify_token(authorization)
        method, request_id = message.get("method"), message.get("id")
        if method == "initialize":
            result: Any = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "datamind-dataplane", "version": "1.0.0"},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            tenant = str(claims.get("tenant_id") or "")
            profile = str(claims.get("profile") or "default")
            services = await _services.get(tenant, profile)
            scopes = frozenset(str(claims.get("scope") or "").split())
            result = {"tools": catalog(services.registry, set(scopes))}
        elif method == "tools/call":
            params = message.get("params") or {}
            name = str(params.get("name") or "")
            arguments = dict(params.get("arguments") or {})
            context = validate_context(arguments.pop("_context", {}))
            dp = DataPlaneContext.from_claims(claims, context)
            authorize(name, set(dp.scopes))
            services = await _services.get(context.tenant_id, context.profile_id)
            from .services import data_root

            root = data_root() / "tenants" / context.tenant_id / "data" / "profiles" / context.profile_id
            guard_args(
                name,
                arguments,
                profile_root=root.resolve(),
            )
            # `confirm` authorizes the DataPlane boundary; it is not part of
            # the underlying DataMind capability tool schemas.
            arguments.pop("confirm", None)
            value = await services.call(name, arguments)
            result = {
                "content": [{"type": "text", "text": json.dumps(value, default=str)}],
                "structuredContent": value,
            }
            if name in {
                "kb_add_text", "kb_add_file", "kb_add_path", "kb_reindex",
                "kb_ingest_document", "kb_ingest_path",
                "db_import_records", "db_import_csv", "graph_upsert_triples",
                "graph_add_triples_from_text", "memory_save", "memory_forget", "skill_upsert",
                "memory_record_interaction", "memory_record_feedback", "wiki_upsert_source",
            }:
                result["structuredContent"] = receipt(name, context.model_dump(), value)
        else:
            raise ValueError(f"method not found: {method}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {"code": -32000, "message": str(exc)},
        }
