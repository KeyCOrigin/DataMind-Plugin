from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from .authorization import authorize
from .context import validate_context, DataPlaneContext
from .health import router as health_router
from .receipts import receipt
from .services import DataPlaneServices
from .tools import catalog
from .guards import guard_args

app = FastAPI(title="datamind-dataplane-mcp", docs_url=None, redoc_url=None)
app.include_router(health_router)
_services: dict[tuple[str, str], DataPlaneServices] = {}


def _verify_token(value: str | None) -> dict[str, Any]:
    if not value or not value.startswith("Bearer "):
        raise HTTPException(401, "bearer token required")
    token = value[7:]
    try:
        head, body, sig = token.split(".")
        header = json.loads(base64.urlsafe_b64decode(head + "=" * (-len(head) % 4)))
        if header.get("alg") != "HS256":
            raise ValueError
        expected = hmac.new(os.environ["DATAMIND_SERVICE_JWT_SECRET"].encode(), f"{head}.{body}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(base64.urlsafe_b64encode(expected).rstrip(b"=").decode(), sig):
            raise ValueError
        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if (claims.get("exp", 0) < time.time() or claims.get("aud") != "datamind-dataplane"
                or claims.get("iss") != "datamind-gateway" or claims.get("service") != "datamind-gateway"
                or not claims.get("tenant_id") or not claims.get("profile")):
            raise ValueError
        return claims
    except Exception as exc:
        raise HTTPException(401, "invalid delegated service token") from exc


@app.post("/mcp")
async def mcp(message: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    claims = _verify_token(authorization)
    try:
        method = message.get("method")
        request_id = message.get("id")
        if method == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "datamind-dataplane-mcp", "version": "1.0.0"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            tenant = str(claims.get("tenant_id") or "")
            profile = str(claims.get("profile") or "default")
            RequestContext = __import__("datamind_contracts", fromlist=["RequestContext"]).RequestContext
            RequestContext(tenant_id=tenant, profile_id=profile)
            services = _services.setdefault((tenant, profile), DataPlaneServices(tenant, profile))
            scopes = frozenset(str(claims.get("scope") or "").split())
            result = {"tools": catalog(services.registry, set(scopes))}
        elif method == "tools/call":
            params = message.get("params") or {}
            name = str(params.get("name") or "")
            arguments = dict(params.get("arguments") or {})
            context = validate_context(arguments.pop("_context", {}))
            dp = DataPlaneContext.from_claims(claims, context)
            authorize(name, set(dp.scopes))
            services = _services.setdefault((context.tenant_id, context.profile_id),
                                             DataPlaneServices(context.tenant_id, context.profile_id))
            # DataMind service handlers enforce their own storage locations; this
            # boundary additionally prevents arbitrary host file access.
            root = (__import__("pathlib").Path(os.environ.get("DATAMIND_DATA_ROOT", "/var/lib/datamind"))
                    / "tenants" / context.tenant_id / "data" / "profiles" / context.profile_id)
            guard_args(name, arguments, profile_root=root.resolve(), external="datamind.dataplane.external_write" in dp.scopes)
            value = await services.call(name, arguments)
            result = {"content": [{"type": "text", "text": json.dumps(value, default=str)}],
                      "structuredContent": value}
            if name in {"kb_add_text", "kb_add_file", "kb_add_path", "kb_reindex", "db_import_records", "db_import_csv",
                        "graph_upsert_triples", "graph_add_triples_from_text", "memory_save", "memory_forget", "skill_upsert"}:
                result["structuredContent"] = receipt(name, context.model_dump(), result["structuredContent"])
        else:
            raise HTTPException(404, "method not found")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except HTTPException:
        raise
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32000, "message": str(exc)}}
