from __future__ import annotations

import json
import os
import asyncio
from typing import Any, Protocol


class GatewayState(Protocol):
    async def create_job(self, job: dict[str, Any]) -> None: ...
    async def update_job(self, job_id: str, patch: dict[str, Any]) -> None: ...
    async def get_job(self, job_id: str) -> dict[str, Any] | None: ...
    async def reserve_events(self, *, tenant_id: str, profile_id: str, source_key: str,
                             events: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    async def add_receipts(self, job_id: str, receipts: list[dict[str, Any]]) -> None: ...
    async def get_receipts(self, job_id: str) -> list[dict[str, Any]]: ...
    async def commit_checkpoint(self, *, tenant_id: str, profile_id: str, source_key: str,
                                checkpoint: str | None, expected_version: int) -> bool: ...
    async def append_audit(self, *, context: dict[str, Any], event_type: str,
                           payload_hash: str | None = None) -> None: ...
    async def close(self) -> None: ...


class InMemoryGatewayState:
    """Development-only state backend; production deployments must use Postgres."""

    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self.events: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
        self.receipts: dict[str, list[dict[str, Any]]] = {}
        self.checkpoints: dict[tuple[str, str, str], tuple[str | None, int]] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, job: dict[str, Any]) -> None:
        self.jobs.setdefault(job["job_id"], dict(job))

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self.jobs.get(job_id)

    async def update_job(self, job_id: str, patch: dict[str, Any]) -> None:
        if job_id in self.jobs:
            self.jobs[job_id].update(patch)

    async def reserve_events(self, *, tenant_id: str, profile_id: str, source_key: str,
                             events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        async with self._lock:
            fresh = []
            for item in events:
                key = (tenant_id, profile_id, source_key, item["external_id"], item["content_hash"])
                if key in self.events:
                    continue
                self.events[key] = {**item, "status": "accepted"}
                fresh.append(item)
            return fresh

    async def add_receipts(self, job_id: str, receipts: list[dict[str, Any]]) -> None:
        self.receipts.setdefault(job_id, []).extend(receipts)

    async def get_receipts(self, job_id: str) -> list[dict[str, Any]]:
        return list(self.receipts.get(job_id, []))

    async def commit_checkpoint(self, *, tenant_id: str, profile_id: str, source_key: str,
                                checkpoint: str | None, expected_version: int) -> bool:
        async with self._lock:
            key = (tenant_id, profile_id, source_key)
            current = self.checkpoints.get(key, (None, 0))
            if current[1] != expected_version:
                return False
            self.checkpoints[key] = (checkpoint, expected_version + 1)
            return True

    async def append_audit(self, *, context: dict[str, Any], event_type: str,
                           payload_hash: str | None = None) -> None:
        return None

    async def close(self) -> None:
        return None


class PostgresGatewayState:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg
            self._pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=10)
        return self._pool

    async def create_job(self, job: dict[str, Any]) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO ingest_batches(job_id, tenant_id, profile_id, status, payload_json)
                   VALUES($1,$2,$3,$4,$5) ON CONFLICT(job_id) DO NOTHING""",
                job["job_id"], job["tenant_id"], job["profile_id"], job["status"], json.dumps(job),
            )

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow("SELECT payload_json FROM ingest_batches WHERE job_id=$1", job_id)
        return json.loads(row["payload_json"]) if row else None

    async def update_job(self, job_id: str, patch: dict[str, Any]) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "UPDATE ingest_batches SET status=COALESCE($2, status), payload_json=payload_json || $3::jsonb WHERE job_id=$1",
                job_id, patch.get("status"), json.dumps(patch),
            )

    async def reserve_events(self, *, tenant_id: str, profile_id: str, source_key: str,
                             events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        fresh = []
        async with pool.acquire() as connection:
            for item in events:
                result = await connection.execute(
                    """INSERT INTO ingest_events(tenant_id, profile_id, source_key, external_id,
                       content_hash, status) VALUES($1,$2,$3,$4,$5,'accepted')
                       ON CONFLICT (tenant_id, profile_id, source_key, external_id, content_hash) DO NOTHING""",
                    tenant_id, profile_id, source_key, item["external_id"], item["content_hash"],
                )
                if result.endswith("1"):
                    fresh.append(item)
        return fresh

    async def add_receipts(self, job_id: str, receipts: list[dict[str, Any]]) -> None:
        if not receipts:
            return
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            await connection.executemany(
                "INSERT INTO ingest_receipts(receipt_id, job_id, payload_json) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
                [(str(r["receipt_id"]), job_id, json.dumps(r, default=str)) for r in receipts],
            )

    async def get_receipts(self, job_id: str) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch("SELECT payload_json FROM ingest_receipts WHERE job_id=$1 ORDER BY created_at", job_id)
        return [json.loads(row["payload_json"]) for row in rows]

    async def commit_checkpoint(self, *, tenant_id: str, profile_id: str, source_key: str,
                                checkpoint: str | None, expected_version: int) -> bool:
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            result = await connection.execute(
                """INSERT INTO source_states(tenant_id, profile_id, source_key, checkpoint_json, version)
                   VALUES($1,$2,$3,$4,1)
                   ON CONFLICT (tenant_id, profile_id, source_key) DO UPDATE
                   SET checkpoint_json=$4, version=source_states.version+1
                   WHERE source_states.version=$5""",
                tenant_id, profile_id, source_key, json.dumps(checkpoint), expected_version,
            )
        return result.endswith("1")

    async def append_audit(self, *, context: dict[str, Any], event_type: str,
                           payload_hash: str | None = None) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO audit_events(tenant_id, profile_id, trace_id, request_id,
                   agent_run_id, batch_id, event_type, payload_hash)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",
                context.get("tenant_id"), context.get("profile_id"), context.get("trace_id"),
                context.get("request_id"), context.get("agent_run_id"), context.get("batch_id"),
                event_type, payload_hash,
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


def default_state() -> GatewayState:
    dsn = os.environ.get("DATAMIND_CONTROL_DATABASE_URL", "").strip()
    if dsn:
        return PostgresGatewayState(dsn)
    if os.environ.get("DATAMIND_ENV", "development").lower() == "production":
        raise RuntimeError("DATAMIND_CONTROL_DATABASE_URL is required in production")
    return InMemoryGatewayState()
