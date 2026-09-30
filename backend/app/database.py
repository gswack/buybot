import asyncpg
from pgvector.asyncpg import register_vector

from app.config import settings

# settings = Settings()
_pool: asyncpg.Pool | None = None


async def init_db_pool() -> asyncpg.Pool:
    """Create the connection pool and register the pgvector type.
    Call this once on app startup.
    """
    global _pool

    async def _init_connection(conn: asyncpg.Connection) -> None:
        await register_vector(conn)

    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=10,
        init=_init_connection,
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


# Run this once manually against your database before first use.
# Requires the pgvector extension to already be installed on the Postgres server.
SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    store TEXT NOT NULL,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    image_url TEXT,
    price NUMERIC(10, 2),
    currency TEXT DEFAULT 'GBP',
    -- CLIP ViT-B-32 produces 512-dim embeddings
    embedding VECTOR(512) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Approximate nearest-neighbor index for fast similarity search
CREATE INDEX IF NOT EXISTS products_embedding_idx
    ON products USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
"""