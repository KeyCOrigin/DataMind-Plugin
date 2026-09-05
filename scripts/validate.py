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
    assert not (root / "integrations").exists()
    assert (root / "services/gateway").is_dir() and (root / "services/dataplane").is_dir()
    print("enterprise layout and Python syntax validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
