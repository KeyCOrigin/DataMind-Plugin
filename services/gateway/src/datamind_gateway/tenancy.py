from __future__ import annotations

from datamind_contracts import RequestContext
from .auth import allowed_profile


def context_from_claims(claims: dict, arguments: dict) -> RequestContext:
    requested = str((arguments.get("_context") or {}).get("profile_id") or "default")
    profile = allowed_profile(claims, requested)
    return RequestContext(tenant_id=str(claims["tenant_id"]), user_id=str(claims.get("sub")), profile_id=profile)
