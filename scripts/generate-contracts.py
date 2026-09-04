#!/usr/bin/env python3
"""Print the versioned enterprise contract names for CI tooling."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/contracts/src"))
from datamind_contracts import ExternalBatch, RequestContext, Receipt

print({"schema_version": "1.0", "models": [RequestContext.__name__, ExternalBatch.__name__, Receipt.__name__]})
