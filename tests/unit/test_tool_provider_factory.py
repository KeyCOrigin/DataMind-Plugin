from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/contracts/src"))
sys.path.insert(0, str(ROOT / "packages/mcp-tool-provider/src"))
sys.path.insert(0, str(ROOT / "plugins/datamind-context/vendor/datamind-0.3.2-py3-none-any.whl"))

from datamind_mcp_provider.tool_adapter import registry_from_tools


class _Client:
    async def call_tool(self, name, arguments):
        return {"name": name, "arguments": arguments}


def test_provider_filters_by_declared_access_not_tool_name() -> None:
    catalogue = [
        {"name": "new_read_tool", "access": "read", "surface": "kb"},
        {"name": "new_utility_tool", "access": "utility"},
        {"name": "new_write_tool", "access": "write", "surface": "kb"},
    ]
    retrieve = registry_from_tools(
        catalogue, _Client(), context={}, allowed_access={"read", "utility"}
    )
    store = registry_from_tools(
        catalogue, _Client(), context={}, allowed_access={"write"}
    )
    assert retrieve.names() == ["new_read_tool", "new_utility_tool"]
    assert store.names() == ["new_write_tool"]


def test_provider_handler_remains_async() -> None:
    async def run() -> None:
        registry = registry_from_tools(
            [{"name": "utility", "access": "utility"}],
            _Client(), context={}, allowed_access={"utility"},
        )
        result = await registry.get("utility").handler(value=1)
        assert result["name"] == "utility"

    asyncio.run(run())
