from __future__ import annotations

import asyncio
import itertools
import json
from typing import Any, Callable, Sequence


class McpClient:
    """Local stdio JSON-RPC client used by Gateway agents.

    The child process is an internal DataPlane MCP.  Claims are carried in
    the private JSON-RPC params field because no network bearer token is
    needed between two local processes.
    """

    def __init__(self, command: str, args: Sequence[str] = (), *,
                 token_factory: Callable[[], str] | None = None) -> None:
        self.command = command
        self.args = list(args)
        self._token_factory = token_factory
        self._ids = itertools.count(1)
        self._process: asyncio.subprocess.Process | None = None
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._write_lock = asyncio.Lock()
        self._closed = False
        self._initialized = False

    async def _start(self) -> None:
        if self._closed:
            raise RuntimeError("MCP client is closed")
        if self._process is not None and self._process.returncode is None:
            return
        # A crashed DataPlane is replaced lazily on the next request. The
        # failed request receives an error, while subsequent Agent calls can
        # recover without rebuilding the whole Gateway process.
        if self._process is not None:
            if self._reader_task and not self._reader_task.done():
                self._reader_task.cancel()
            self._process = None
            self._reader_task = None
            self._initialized = False
        self._process = await asyncio.create_subprocess_exec(
            self.command, *self.args, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        self._reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        assert self._process and self._process.stdout
        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            try:
                payload = json.loads(line.decode())
                request_id = payload.get("id")
                future = self._pending.pop(request_id, None)
                if future and not future.done():
                    future.set_result(payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        error = RuntimeError("DataPlane stdio process exited")
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()

    async def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        await self._start()
        assert self._process and self._process.stdin
        request_id = next(self._ids)
        payload = dict(params or {})
        if self._token_factory:
            payload["_delegated_token"] = self._token_factory()
        message = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": payload}
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[request_id] = future
        async with self._write_lock:
            self._process.stdin.write((json.dumps(message, separators=(",", ":")) + "\n").encode())
            await self._process.stdin.drain()
        response = await future
        if "error" in response:
            raise RuntimeError(str(response["error"]))
        return response.get("result")

    async def list_tools(self) -> list[dict[str, Any]]:
        if not self._initialized:
            await self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                            "clientInfo": {"name": "datamind", "version": "1.0.0"}})
            self._initialized = True
        result = await self._rpc("tools/list")
        return list((result or {}).get("tools") or [])

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        return (result or {}).get("structuredContent", result)

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            if self._process and self._process.stdin:
                self._process.stdin.close()
            if self._reader_task:
                await self._reader_task
            if self._process:
                await self._process.wait()
