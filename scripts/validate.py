#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for source in root.rglob("*.py"):
        if any(part in {".venv", "__pycache__", "dist"} for part in source.parts):
            continue
        ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    json.loads((root / "plugins/datamind-context/.mcp.json").read_text(encoding="utf-8"))
    mcp = json.loads((root / "plugins/datamind-context/.mcp.json").read_text(encoding="utf-8"))
    servers = mcp.get("mcpServers") or {}
    assert set(servers) == {"datamind"}
    assert servers["datamind"].get("command") == "datamind-mcp"
    assert not any("http://" in json.dumps(value) or "https://" in json.dumps(value)
                   for value in servers.values())
    assert not (root / "integrations").exists()
    assert (root / "services/gateway").is_dir() and (root / "services/dataplane").is_dir()
    assert not (root / "services/gateway/src/datamind_gateway/server.py").exists()
    assert not (root / "services/dataplane/src/datamind_dataplane/server.py").exists()
    forbidden = (
        "datamind_dataplane.server", "datamind_gateway.server", "dataplaneUrl",
        "datamind-dataplane:8080", "datamind.company.com/mcp",
    )
    for source in root.rglob("*"):
        if source == Path(__file__) or not source.is_file() or any(part in {".git", ".venv", "__pycache__", "dist"}
                                       for part in source.parts):
            continue
        if source.suffix.lower() not in {".py", ".toml", ".yaml", ".yml", ".json", ".md"}:
            continue
        text = source.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in forbidden), f"stale HTTP reference in {source}"
    print("enterprise layout and Python syntax validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
