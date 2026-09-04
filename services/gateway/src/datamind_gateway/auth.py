from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from datamind_contracts import AuthorizationError


def issue_service_token(context: Any, *, role: str, scope: str) -> str:
    """Issue a five-minute delegated token for exactly one Agent role."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    claims = {"iss": "datamind-gateway", "aud": "datamind-dataplane", "service": "datamind-gateway",
              "tenant_id": context.tenant_id, "profile": context.profile_id, "agent_role": role,
              "scope": scope, "exp": int(time.time()) + 300, "sub": context.user_id or "gateway"}
    body = base64.urlsafe_b64encode(json.dumps(claims, separators=(",", ":")).encode()).rstrip(b"=").decode()
    key = _secret("DATAMIND_SERVICE_JWT_SECRET").encode()
    signature = hmac.new(key, f"{header}.{body}".encode(), hashlib.sha256).digest()
    return ".".join((header, body, base64.urlsafe_b64encode(signature).rstrip(b"=").decode()))


def verify_bearer(value: str | None) -> dict[str, Any]:
    if not value or not value.startswith("Bearer "):
        raise AuthorizationError("OAuth bearer token required")
    raw = value[7:]
    jwks_url = os.environ.get("DATAMIND_OIDC_JWKS_URL", "").strip()
    if jwks_url:
        try:
            import jwt
            signing_key = jwt.PyJWKClient(jwks_url).get_signing_key_from_jwt(raw).key
            audience = os.environ.get("DATAMIND_OIDC_AUDIENCE") or None
            issuer = os.environ.get("DATAMIND_OIDC_ISSUER") or None
            claims = jwt.decode(raw, signing_key, algorithms=["RS256", "ES256"],
                                audience=audience, issuer=issuer,
                                options={"verify_aud": bool(audience), "verify_iss": bool(issuer)})
            if not claims.get("sub") or not claims.get("tenant_id"):
                raise ValueError("claims")
            return claims
        except Exception as exc:
            raise AuthorizationError("invalid OAuth token") from exc
    try:
        header, body, signature = raw.split(".")
        key = os.environ.get("DATAMIND_GATEWAY_JWT_SECRET", "development-only-change-me").encode()
        expected = hmac.new(key, f"{header}.{body}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(base64.urlsafe_b64encode(expected).rstrip(b"=").decode(), signature):
            raise ValueError("signature")
        header_claims = json.loads(base64.urlsafe_b64decode(header + "=" * (-len(header) % 4)))
        if header_claims.get("alg") != "HS256":
            raise ValueError("algorithm")
        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        expected_issuer = os.environ.get("DATAMIND_OIDC_ISSUER")
        expected_audience = os.environ.get("DATAMIND_OIDC_AUDIENCE")
        if (claims.get("exp", 0) < time.time() or not claims.get("sub") or not claims.get("tenant_id")
                or (expected_issuer and claims.get("iss") != expected_issuer)
                or (expected_audience and expected_audience not in (claims.get("aud") if isinstance(claims.get("aud"), list) else [claims.get("aud")]))):
            raise ValueError("claims")
        return claims
    except Exception as exc:
        raise AuthorizationError("invalid OAuth token") from exc


def allowed_profile(claims: dict[str, Any], profile: str) -> str:
    profiles = claims.get("profiles") or []
    if not isinstance(profiles, (list, tuple, set)) or profile not in {str(p) for p in profiles}:
        raise AuthorizationError("profile is not allowed for this user")
    return profile


def require_scope(claims: dict[str, Any], scope: str) -> None:
    if scope not in set(claims.get("scopes") or []):
        raise AuthorizationError(f"missing scope: {scope}")


def _secret(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    if os.environ.get("DATAMIND_ENV", "development").lower() == "production":
        raise RuntimeError(f"{name} is required in production")
    return "development-only-change-me"
