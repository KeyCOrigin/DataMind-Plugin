"""Local stdio MCP entrypoint for the DataMind DataPlane."""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any


async def _dispatch(message: dict[str, Any]) -> dict[str, Any] | None:
    from .dispatch import dispatch

    method = message.get("method")
    if method == "notifications/initialized" or method == "notifications/cancelled":
        return None
    params = dict(message.get("params") or {})
    token = str(params.pop("_delegated_token", ""))
    message = {**message, "params": params}
    if not token:
        return {"jsonrpc": "2.0", "id": message.get("id"),
                "error": {"code": -32001, "message": "delegated token required"}}
    try:
        return await dispatch(message, authorization=f"Bearer {token}")
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": message.get("id"),
                "error": {"code": -32000, "message": str(exc)}}


async def main() -> None:
    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            break
        try:
            message = json.loads(line)
            response = await _dispatch(message)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": str(exc)}}
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
