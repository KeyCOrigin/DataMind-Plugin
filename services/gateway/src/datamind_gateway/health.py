"""Local process health check for stdio deployments."""
from __future__ import annotations

import os
def main() -> int:
    if os.environ.get("DATAMIND_ENV", "development").lower() == "production":
        required = ("DATAMIND_CONTROL_DATABASE_URL", "DATAMIND_SERVICE_JWT_SECRET", "DATAMIND_GATEWAY_JWT_SECRET")
        if any(not os.environ.get(name, "").strip() for name in required):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
