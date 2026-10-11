import asyncpg

from app.config import settings

_pool: asyncpg.Pool | None = None


async def init_db_pool() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=10,
    )
    return _pool


async def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_db_pool() first")
    return _pool


# ── Schema ────────────────────────────────────────────────────────────────────

USERS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    age         INT,
    -- memberships stored as a JSON array of membership IDs
    -- e.g. ["asos_student", "jack_kuba_club"]
    memberships JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS users_email_idx ON users (email);
"""


async def create_tables() -> None:
    """Create all application tables if they don't exist. Safe to call on every startup."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(USERS_SCHEMA_SQL)
