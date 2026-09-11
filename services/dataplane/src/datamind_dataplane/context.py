from __future__ import annotations

import os
import re
from dataclasses import dataclass

from datamind_contracts import RequestContext


@dataclass(frozen=True)
class DataPlaneContext:
    request: RequestContext
    role: str
    scopes: frozenset[str]

    @classmethod
    def from_claims(cls, claims: dict, request: RequestContext) -> "DataPlaneContext":
        tenant = str(claims.get("tenant_id") or "")
        profile = str(claims.get("profile") or "")
        if tenant != request.tenant_id or profile != request.profile_id:
            raise PermissionError("delegated token tenant/profile mismatch")
        scopes = frozenset(str(claims.get("scope") or "").split())
        role = str(claims.get("agent_role") or "")
        expected = {
            "retrieve": {frozenset({"datamind.dataplane.read"})},
            # StoreAgent uses the narrower external_write delegation when the
            # source is an untrusted external channel. The tool authorizer
            # still limits that scope to additive KB/DB/Graph operations.
            "store": {
                frozenset({"datamind.dataplane.write"}),
                frozenset({"datamind.dataplane.external_write"}),
            },
            "admin": {frozenset({"datamind.dataplane.admin"})},
        }
        if role not in expected or scopes not in expected[role]:
            raise PermissionError("delegated token role/scope mismatch")
        return cls(request, role, scopes)


def validate_context(payload: dict) -> RequestContext:
    return RequestContext.model_validate(payload)
