from __future__ import annotations

import itertools
import os
import json
from typing import Any, Callable
import httpx


class McpClient:
    """Small Streamable-HTTP JSON-RPC client used only by Gateway agents."""

    def __init__(self, url: str, *, token: str | None = None,
                 token_factory: Callable[[], str] | None = None,
                 client: httpx.AsyncClient | None = None) -> None:
        self.url = url
        if not token and not token_factory:
            raise ValueError("token or token_factory is required")
        self._token = token
        self._token_factory = token_factory
        if client is not None:
            self._client = client
        else:
            cert = None
            cert_path = os.environ.get("DATAMIND_MCP_CLIENT_CERT")
            key_path = os.environ.get("DATAMIND_MCP_CLIENT_KEY")
            if cert_path and key_path:
                cert = (cert_path, key_path)
            verify: str | bool = os.environ.get("DATAMIND_MCP_CA_FILE", "") or True
            self._client = httpx.AsyncClient(timeout=30, cert=cert, verify=verify)
        self._ids = itertools.count(1)
        self._closed = False
        self._initialized = False
        self._session_id: str | None = None

    async def _rpc(self, method: str, params: dict[str, Any] | None = None, *, _retry: bool = True) -> Any:
        request_id = next(self._ids)
        if method != "initialize" and not self._initialized:
            await self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                             "clientInfo": {"name": "datamind-gateway", "version": "1.0.0"}})
            self._initialized = True
        token = self._token_factory() if self._token_factory else self._token
        headers = {"Authorization": f"Bearer {token}",
                   "Accept": "application/json, text/event-stream",
                   "MCP-Protocol-Version": "2025-06-18"}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        try:
            response = await self._client.post(self.url, headers=headers,
                json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        except (httpx.TransportError, httpx.TimeoutException):
            if not _retry:
                raise
            await self.reconnect()
            if method != "initialize":
                await self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                 "clientInfo": {"name": "datamind-gateway", "version": "1.0.0"}})
                self._initialized = True
            response = await self._client.post(self.url, headers=headers,
                json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        if response.status_code in {502, 503, 504} and _retry:
            await self.reconnect()
            return await self._rpc(method, params, _retry=False)
        response.raise_for_status()
        self._session_id = response.headers.get("Mcp-Session-Id", self._session_id)
        if "text/event-stream" in response.headers.get("content-type", ""):
            payload = None
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    payload = json.loads(line[5:].strip())
                    break
            if payload is None:
                raise RuntimeError("MCP stream contained no JSON-RPC response")
        else:
            payload = response.json()
        if "error" in payload:
            raise RuntimeError(str(payload["error"]))
        return payload.get("result")

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._rpc("tools/list")
        return list((result or {}).get("tools") or [])

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        return (result or {}).get("structuredContent", result)

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._client.aclose()

    async def reconnect(self) -> None:
        """Drop the HTTP session so the next call performs a fresh initialize."""
        if self._closed:
            return
        self._initialized = False
        self._session_id = None
