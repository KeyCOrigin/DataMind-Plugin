"""Small, explicit PostgreSQL migration runner for the Gateway ledger."""
from __future__ import annotations

import os
from pathlib import Path


async def run_migrations(dsn: str | None = None, directory: str | None = None) -> int:
    dsn = (dsn or os.environ.get("DATAMIND_CONTROL_DATABASE_URL", "")).strip()
    if not dsn:
        if os.environ.get("DATAMIND_ENV", "development").lower() == "production":
            raise RuntimeError("DATAMIND_CONTROL_DATABASE_URL is required in production")
        return 0
    import asyncpg

    configured_dir = directory or os.environ.get("DATAMIND_MIGRATIONS_DIR", "").strip()
    migration_dir = Path(configured_dir).expanduser() if configured_dir else None
    if migration_dir is None:
        migration_dir = Path(__file__).resolve().parents[2] / "migrations"
    files = sorted(migration_dir.glob("*.sql"))
    if not files:
        raise RuntimeError(f"no Gateway migrations found in {migration_dir}")
    connection = await asyncpg.connect(dsn)
    try:
        await connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        applied = {row["version"] for row in await connection.fetch("SELECT version FROM schema_migrations")}
        count = 0
        for path in files:
            version = path.name
            if version in applied:
                continue
            async with connection.transaction():
                # The checked-in migrations contain DDL only. Executing each
                # statement separately keeps compatibility with asyncpg and
                # makes a failed migration atomic.
                for statement in path.read_text(encoding="utf-8").split(";"):
                    statement = statement.strip()
                    if statement:
                        await connection.execute(statement)
                await connection.execute("INSERT INTO schema_migrations(version) VALUES($1)", version)
            count += 1
        return count
    finally:
        await connection.close()
