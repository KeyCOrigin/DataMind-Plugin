from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _gateway_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "packages/contracts/src"), str(ROOT / "packages/mcp-tool-provider/src"),
         str(ROOT / "services/gateway/src"), str(ROOT / "services/dataplane/src"),
         str(ROOT / "plugins/datamind-context/vendor/datamind-0.3.2-py3-none-any.whl"),
    ])
    return env


def test_gateway_stdio_exposes_only_public_tools() -> None:
    process = subprocess.Popen(
        [sys.executable, "-m", "datamind_gateway.stdio_server"],
        cwd=ROOT, env=_gateway_env(), stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert process.stdin and process.stdout
    process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n")
    process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n")
    process.stdin.flush()
    initialize = json.loads(process.stdout.readline())
    listing = json.loads(process.stdout.readline())
    process.stdin.close()
    process.wait(timeout=5)

    assert initialize["result"]["serverInfo"]["name"] == "datamind"
    names = {tool["name"] for tool in listing["result"]["tools"]}
    assert len(names) == 9
    assert not any(name.startswith(("kb_", "db_", "graph_", "memory_", "skill_")) for name in names)
