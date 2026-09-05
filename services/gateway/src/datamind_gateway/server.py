from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from .agent_runtime import AgentRuntime
from .auth import verify_bearer
from .external_ingest import ExternalIngestService
from .schemas import GATEWAY_TOOLS
from .tenancy import context_from_claims
from .tools import retrieve, store
from .state import default_state
from datamind_contracts import ExternalBatch

app = FastAPI(title="datamind-gateway-mcp", docs_url=None, redoc_url=None)
runtime = AgentRuntime()
external = ExternalIngestService(runtime, default_state())


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "datamind-gateway-mcp"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready", "service": "datamind-gateway-mcp"}


@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource() -> dict[str, Any]:
    issuer = os.environ.get("DATAMIND_OIDC_ISSUER", "")
    return {"resource": os.environ.get("DATAMIND_GATEWAY_RESOURCE", "https://datamind.company.com/mcp"),
            "authorization_servers": [issuer] if issuer else [],
            "scopes_supported": ["datamind:retrieve", "datamind:store"]}


@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server() -> dict[str, Any]:
    issuer = os.environ.get("DATAMIND_OIDC_ISSUER", "")
    return {"issuer": issuer, "authorization_endpoint": os.environ.get("DATAMIND_OIDC_AUTHORIZATION_ENDPOINT", ""),
            "token_endpoint": os.environ.get("DATAMIND_OIDC_TOKEN_ENDPOINT", ""),
            "response_types_supported": ["code"], "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"]}


@app.post("/mcp")
async def mcp(message: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        claims = verify_bearer(authorization)
        method, request_id = message.get("method"), message.get("id")
        if method == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "datamind-gateway-mcp", "version": "1.0.0"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": GATEWAY_TOOLS}
        elif method == "tools/call":
            params = message.get("params") or {}
            name, args = str(params.get("name") or ""), dict(params.get("arguments") or {})
            if name == "datamind_agent_retrieve": value = await retrieve(runtime, claims, args)
            elif name == "datamind_agent_store": value = await store(runtime, claims, args)
            elif name == "datamind_agent_status": value = {"status": "ready", "cached_bundles": len(runtime._bundles)}
            elif name == "datamind_profile_list": value = {"profiles": claims.get("profiles") or []}
            elif name == "datamind_profile_status":
                profile = str(args.get("profile_id") or "default"); context_from_claims(claims, {"_context": {"profile_id": profile}}); value = {"profile_id": profile, "allowed": True}
            elif name == "datamind_external_ingest_submit":
                from .auth import require_scope
                require_scope(claims, "datamind:store")
                value = await external.submit(ExternalBatch.model_validate(args.get("batch") or {}), context_from_claims(claims, args))
            elif name in {"datamind_external_job_status", "datamind_external_receipt_get"}:
                context = context_from_claims(claims, args)
                value = await external.status(str(args.get("job_id") or ""), context)
            elif name == "datamind_external_source_status": value = {"source_key": args.get("source_key"), "status": "independent_external_mcp"}
            elif name == "datamind_agent_store_external":
                from .auth import require_scope
                require_scope(claims, "datamind:store")
                value = await external.submit(ExternalBatch.model_validate(args.get("batch") or {}), context_from_claims(claims, args))
            else: raise HTTPException(404, "unknown gateway tool")
            if name not in {"datamind_profile_list", "datamind_profile_status"}:
                try:
                    audit_context = context_from_claims(claims, args)
                    await external.state.append_audit(context=audit_context.model_dump(), event_type=f"tool:{name}")
                except Exception:
                    # The primary tool result must not be lost if audit storage
                    # is temporarily unavailable; the deployment can alert on
                    # this error through its audit backend.
                    pass
            result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, default=str)}], "structuredContent": value}
        else: raise HTTPException(404, "method not found")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except HTTPException: raise
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32000, "message": str(exc)}}


@app.on_event("shutdown")
async def shutdown() -> None:
    await external.close()
    await runtime.close()
    await external.state.close()
