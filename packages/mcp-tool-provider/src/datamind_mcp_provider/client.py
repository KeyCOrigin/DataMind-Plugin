from __future__ import annotations

import asyncio
import itertools
import json
from collections import deque
from contextlib import suppress
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
        self._stderr_task: asyncio.Task[None] | None = None
        self._write_lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        self._initialize_lock = asyncio.Lock()
        self._close_lock = asyncio.Lock()
        self._closed = False
        self._initialized = False
        self._stderr_tail: deque[str] = deque(maxlen=20)

    async def _start(self) -> None:
        async with self._start_lock:
            if self._closed:
                raise RuntimeError("MCP client is closed")
            if (self._process is not None and self._process.returncode is None
                    and self._reader_task is not None and not self._reader_task.done()):
                return
            # A crashed DataPlane is replaced lazily on the next request. The
            # failed request receives an error, while subsequent Agent calls can
            # recover without rebuilding the whole Gateway process.
            if self._process is not None:
                old_process = self._process
                for task in (self._reader_task, self._stderr_task):
                    if task and not task.done():
                        task.cancel()
                    if task:
                        with suppress(asyncio.CancelledError, Exception):
                            await task
                with suppress(Exception):
                    await old_process.wait()
                self._process = None
                self._reader_task = None
                self._stderr_task = None
                self._initialized = False
            self._stderr_tail.clear()
            self._process = await asyncio.create_subprocess_exec(
                self.command, *self.args, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            self._reader_task = asyncio.create_task(self._read_loop())
            self._stderr_task = asyncio.create_task(self._drain_stderr())

    async def _read_loop(self) -> None:
        process = self._process
        assert process and process.stdout
        while True:
            line = await process.stdout.readline()
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
        with suppress(Exception):
            await process.wait()
        if self._process is process:
            self._initialized = False
        detail = ""
        if self._stderr_tail:
            detail = ": " + " | ".join(self._stderr_tail)
        error = RuntimeError("DataPlane stdio process exited" + detail)
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()

    async def _drain_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        while True:
            line = await process.stderr.readline()
            if not line:
                return
            text = line.decode(errors="replace").strip()
            if text:
                self._stderr_tail.append(text[-1000:])

    async def _rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        token_factory: Callable[[], str] | None = None,
    ) -> Any:
        await self._start()
        process = self._process
        assert process and process.stdin
        request_id = next(self._ids)
        payload = dict(params or {})
        token_factory = token_factory or self._token_factory
        if token_factory:
            payload["_delegated_token"] = token_factory()
        message = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": payload}
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[request_id] = future
        async with self._write_lock:
            try:
                process.stdin.write((json.dumps(message, separators=(",", ":")) + "\n").encode())
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError) as exc:
                self._pending.pop(request_id, None)
                self._initialized = False
                raise RuntimeError("DataPlane stdio process is unavailable") from exc
        try:
            response = await future
        except asyncio.CancelledError:
            self._pending.pop(request_id, None)
            raise
        if "error" in response:
            raise RuntimeError(str(response["error"]))
        return response.get("result")

    async def list_tools(self, *, token_factory: Callable[[], str] | None = None) -> list[dict[str, Any]]:
        async with self._initialize_lock:
            if not self._initialized:
                await self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                "clientInfo": {"name": "datamind", "version": "1.0.0"}},
                              token_factory=token_factory)
                self._initialized = True
        result = await self._rpc("tools/list", token_factory=token_factory)
        return list((result or {}).get("tools") or [])

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        token_factory: Callable[[], str] | None = None,
    ) -> Any:
        result = await self._rpc("tools/call", {"name": name, "arguments": arguments}, token_factory=token_factory)
        return (result or {}).get("structuredContent", result)

    def scoped(self, token_factory: Callable[[], str]) -> "ScopedMcpClient":
        """Create a logical role client sharing this client's process."""
        return ScopedMcpClient(self, token_factory)

    async def close(self) -> None:
        async with self._close_lock:
            if self._closed:
                return
            self._closed = True
            process = self._process
            if process is None:
                return
            if process.stdin:
                process.stdin.close()
                with suppress(Exception):
                    await process.stdin.wait_closed()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                with suppress(ProcessLookupError):
                    process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except asyncio.TimeoutError:
                    with suppress(ProcessLookupError):
                        process.kill()
                    await process.wait()
            for task in (self._reader_task, self._stderr_task):
                if task and not task.done():
                    task.cancel()
                if task:
                    with suppress(asyncio.CancelledError, Exception):
                        await task
            self._process = None
            self._reader_task = None
            self._stderr_task = None
            self._initialized = False


class ScopedMcpClient:
    """Role-scoped view over one :class:`McpClient` transport.

    RetrieveAgent and StoreAgent need different delegated claims, but they do
    not need separate DataPlane server processes.  This view supplies the
    appropriate token per call while sharing the underlying stdio process.
    """

    def __init__(self, client: McpClient, token_factory: Callable[[], str]) -> None:
        self._client = client
        self._token_factory = token_factory

    async def list_tools(self) -> list[dict[str, Any]]:
        return await self._client.list_tools(token_factory=self._token_factory)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return await self._client.call_tool(name, arguments, token_factory=self._token_factory)

    async def close(self) -> None:
        # A scoped client is a borrowed view.  Its owner (McpToolProvider or
        # AgentRuntime) closes the physical transport exactly once.
        return None
