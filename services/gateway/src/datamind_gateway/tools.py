from __future__ import annotations

from datamind_contracts import ExternalBatch
from .auth import require_scope
from .tenancy import context_from_claims


async def retrieve(runtime, claims: dict, args: dict):
    require_scope(claims, "datamind:retrieve")
    context = context_from_claims(claims, args)
    return await (await runtime.get(context)).system.query(str(args.get("message") or ""))


async def store(runtime, claims: dict, args: dict):
    require_scope(claims, "datamind:store")
    if args.get("confirm") is not True:
        raise PermissionError("datamind_agent_store requires confirm=true")
    context = context_from_claims(claims, args)
    return await (await runtime.get(context)).system.ingest(str(args.get("message") or ""))
