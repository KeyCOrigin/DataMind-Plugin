"""Gateway MCP JSON-RPC dispatch used by the local stdio server."""
from __future__ import annotations

import json
from typing import Any

from datamind_contracts import ExternalBatch

from .agent_runtime import AgentRuntime
from .auth import verify_bearer
from .external_ingest import ExternalIngestService
from .schemas import GATEWAY_TOOLS
from .tenancy import context_from_claims
from .tools import retrieve, store


async def dispatch(
    message: dict[str, Any],
    *,
    authorization: str | None,
    runtime: AgentRuntime,
    external: ExternalIngestService,
) -> dict[str, Any]:
    """Handle one MCP JSON-RPC request without a transport dependency."""
    try:
        claims = verify_bearer(authorization)
        method, request_id = message.get("method"), message.get("id")
        if method == "initialize":
            result: Any = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "datamind", "version": "1.0.0"},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": GATEWAY_TOOLS}
        elif method == "tools/call":
            from .auth import require_scope

            params = message.get("params") or {}
            name, args = str(params.get("name") or ""), dict(params.get("arguments") or {})
            if name == "datamind_agent_retrieve":
                value = await retrieve(runtime, claims, args)
            elif name == "datamind_agent_store":
                value = await store(runtime, claims, args)
            elif name == "datamind_agent_status":
                value = {"status": "ready", "cached_bundles": len(runtime._bundles)}
            elif name == "datamind_profile_list":
                value = {"profiles": claims.get("profiles") or []}
            elif name == "datamind_profile_status":
                profile = str(args.get("profile_id") or "default")
                context_from_claims(claims, {"_context": {"profile_id": profile}})
                value = {"profile_id": profile, "allowed": True}
            elif name == "datamind_external_ingest_submit":
                require_scope(claims, "datamind:store")
                value = await external.submit(
                    ExternalBatch.model_validate(args.get("batch") or {}),
                    context_from_claims(claims, args),
                )
            elif name in {"datamind_external_job_status", "datamind_external_receipt_get"}:
                value = await external.status(
                    str(args.get("job_id") or ""), context_from_claims(claims, args)
                )
            elif name == "datamind_external_source_status":
                value = {"source_key": args.get("source_key"), "status": "independent_external_mcp"}
            else:
                raise ValueError(f"unknown gateway tool: {name}")
            if name not in {"datamind_profile_list", "datamind_profile_status"}:
                try:
                    audit_context = context_from_claims(claims, args)
                    await external.state.append_audit(
                        context=audit_context.model_dump(), event_type=f"tool:{name}"
                    )
                except Exception:
                    pass
            result = {
                "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, default=str)}],
                "structuredContent": value,
            }
        else:
            raise ValueError(f"method not found: {method}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {"code": -32000, "message": str(exc)},
        }
