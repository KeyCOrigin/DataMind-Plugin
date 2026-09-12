from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/dataplane/src"))
sys.path.insert(0, str(ROOT / "services/gateway/src"))
sys.path.insert(0, str(ROOT / "packages/contracts/src"))
sys.path.insert(0, str(ROOT / "packages/mcp-tool-provider/src"))
sys.path.insert(0, str(ROOT / "plugins/datamind-context/vendor/datamind-0.3.2-py3-none-any.whl"))

from datamind_dataplane.services import DataPlaneServiceFactory
from datamind_mcp_provider import McpClient, McpToolProvider
from datamind_gateway.agent_runtime import AgentRuntime


class _FakeService:
    def __init__(self, tenant: str, profile: str) -> None:
        self.key = (tenant, profile)
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def test_factory_constructs_one_service_for_repeated_and_concurrent_gets() -> None:
    calls: list[tuple[str, str]] = []

    def build(tenant: str, profile: str) -> _FakeService:
        calls.append((tenant, profile))
        return _FakeService(tenant, profile)

    async def run() -> None:
        factory = DataPlaneServiceFactory(builder=build)
        values = await asyncio.gather(*[
            factory.get("tenant-a", "default") for _ in range(8)
        ])
        assert len({id(value) for value in values}) == 1
        assert calls == [("tenant-a", "default")]
        assert len(factory) == 1
        service = values[0]
        await factory.aclose()
        assert service.closed is True
        assert len(factory) == 0
        await factory.aclose()
        try:
            await factory.get("tenant-a", "default")
        except RuntimeError as exc:
            assert "closed" in str(exc)
        else:
            raise AssertionError("closed factory accepted a new service")

    asyncio.run(run())


def test_scoped_clients_share_one_physical_mcp_transport() -> None:
    async def run() -> None:
        transport = McpClient("unused")
        retrieve = transport.scoped(lambda: "retrieve-token")
        store = transport.scoped(lambda: "store-token")
        provider = McpToolProvider(retrieve, store_client=store, context={})
        closed: list[int] = []
        async def close() -> None:
            closed.append(1)
        transport.close = close  # type: ignore[method-assign]
        await provider.close()
        assert closed == [1]

    asyncio.run(run())


def test_mcp_client_single_flight_initialization_and_restart(tmp_path: Path) -> None:
    starts = tmp_path / "starts"
    child = (
        "import json, os, pathlib, sys\n"
        f"p=pathlib.Path({str(starts)!r}); p.open('a').write(str(os.getpid())+'\\n')\n"
        "for line in sys.stdin:\n"
        " m=json.loads(line); method=m.get('method'); rid=m.get('id')\n"
        " if method == 'initialize': r={'protocolVersion':'2025-06-18'}\n"
        " elif method == 'tools/list':\n"
        "  n=len(p.read_text().splitlines())\n"
        "  if n == 1: os._exit(0)\n"
        "  r={'tools':[{'name':'ok'}]}\n"
        " else: r={}\n"
        " print(json.dumps({'jsonrpc':'2.0','id':rid,'result':r}), flush=True)\n"
    )

    async def run() -> None:
        client = McpClient(sys.executable, ("-c", child))
        # The first process deliberately exits during tools/list.  All
        # concurrent callers must nevertheless share one physical process.
        results = await asyncio.gather(
            *(client.list_tools() for _ in range(5)), return_exceptions=True
        )
        assert len(starts.read_text().splitlines()) == 1
        assert any(isinstance(value, RuntimeError) for value in results)
        recovered = await client.list_tools()
        assert recovered == [{"name": "ok"}]
        assert len(starts.read_text().splitlines()) == 2
        await client.close()

    asyncio.run(run())


def test_agent_runtime_key_locks_are_released() -> None:
    async def run() -> None:
        runtime = AgentRuntime()
        key = ("tenant", "profile", "policy")
        entry = await runtime._acquire_key_lock(key)
        await runtime._release_key_lock(key, entry)
        assert runtime._locks == {}

    asyncio.run(run())
