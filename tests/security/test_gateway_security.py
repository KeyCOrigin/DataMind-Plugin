import base64
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/contracts/src"))
sys.path.insert(0, str(ROOT / "services/gateway/src"))

from datamind_gateway.auth import allowed_profile, verify_bearer


def _token(claims):
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    sig = hmac.new(b"test", f"{header}.{body}".encode(), hashlib.sha256).digest()
    return "Bearer " + ".".join((header, body, base64.urlsafe_b64encode(sig).rstrip(b"=").decode()))


def test_gateway_rejects_invalid_and_expired_tokens(monkeypatch):
    monkeypatch.setenv("DATAMIND_GATEWAY_JWT_SECRET", "test")
    claims = {"sub": "u", "tenant_id": "t", "profiles": ["default"], "exp": time.time() + 60}
    assert verify_bearer(_token(claims))["tenant_id"] == "t"
    with pytest.raises(Exception):
        verify_bearer(_token({**claims, "exp": 0}))


def test_profile_must_be_token_allowed():
    with pytest.raises(Exception):
        allowed_profile({"profiles": ["default"]}, "admin")
