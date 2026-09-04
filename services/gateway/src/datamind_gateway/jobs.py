from __future__ import annotations

from typing import Any


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}

    def get(self, job_id: str) -> dict[str, Any]:
        return self._jobs.get(job_id, {"job_id": job_id, "status": "failed", "error": "job_not_found"})
