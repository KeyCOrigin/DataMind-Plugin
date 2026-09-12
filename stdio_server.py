"""Local stdio MCP entrypoint exposed to Codex."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import sys
from typing import Any


def _local_token() -> str:
    """Create the local process identity used by the stdio Gateway."""
    claims = {
        "iss": os.environ.get("DATAMIND_OIDC_ISSUER", "datamind-local"),
        "sub": os.environ.get("DATAMIND_LOCAL_USER", "local-user"),
        "tenant_id": os.environ.get("DATAMIND_LOCAL_TENANT", "local"),
        "profiles": [p for p in os.environ.get("DATAMIND_LOCAL_PROFILES", "default").split(",") if p],
        "scopes": ["datamind:retrieve", "datamind:store"],
        "exp": 4102444800,
    }
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(claims, separators=(",", ":")).encode()).rstrip(b"=").decode()
    secret_value = os.environ.get("DATAMIND_GATEWAY_JWT_SECRET", "").strip()
    if not secret_value:
        if os.environ.get("DATAMIND_ENV", "development").lower() == "production":
            raise RuntimeError("DATAMIND_GATEWAY_JWT_SECRET is required in production")
        secret_value = "development-only-change-me"
    secret = secret_value.encode()
    signature = hmac.new(secret, f"{header}.{body}".encode(), hashlib.sha256).digest()
    return ".".join((header, body, base64.urlsafe_b64encode(signature).rstrip(b"=").decode()))


async def _dispatch(message: dict[str, Any]) -> dict[str, Any] | None:
    from .dispatch import dispatch
    from .state import default_state
    from .agent_runtime import AgentRuntime
    from .external_ingest import ExternalIngestService

    runtime = getattr(_dispatch, "runtime", None)
    if runtime is None:
        runtime = _dispatch.runtime = AgentRuntime()
        _dispatch.external = ExternalIngestService(runtime, default_state())

    if message.get("method") in {"notifications/initialized", "notifications/cancelled"}:
        return None
    try:
        return await dispatch(message, authorization=f"Bearer {_local_token()}",
                              runtime=runtime, external=_dispatch.external)
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": message.get("id"),
                "error": {"code": -32000, "message": str(exc)}}


async def main() -> None:
    from .migrations import run_migrations
    await run_migrations()
    write_lock = asyncio.Lock()

    async def handle(message: dict[str, Any]) -> None:
        try:
            response = await _dispatch(message)
            if response is not None:
                async with write_lock:
                    sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                    sys.stdout.flush()
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": message.get("id"),
                        "error": {"code": -32000, "message": str(exc)}}
            async with write_lock:
                sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()

    tasks: set[asyncio.Task[None]] = set()
    try:
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                async with write_lock:
                    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                                 "error": {"code": -32700, "message": "invalid JSON"}}) + "\n")
                    sys.stdout.flush()
                continue
            task = asyncio.create_task(handle(message))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    runtime = getattr(_dispatch, "runtime", None)
    if runtime is not None:
        await _dispatch.external.close()
        await runtime.close()
        await _dispatch.external.state.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
