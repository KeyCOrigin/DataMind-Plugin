#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages/contracts/src"), str(ROOT / "services/gateway/src"), str(ROOT / "services/dataplane/src")]


def main() -> int:
    from datamind_gateway.schemas import GATEWAY_TOOLS
    names = {item["name"] for item in GATEWAY_TOOLS}
    assert "datamind_agent_retrieve" in names and "datamind_external_ingest_submit" in names
    assert not any(name.startswith("datamind_kb_") for name in names)
    print(json.dumps({"status": "ok", "gateway_tools": len(names), "dataplane_public": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
