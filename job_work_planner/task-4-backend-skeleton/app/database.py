"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: database.py
 * 
 * 1) Purpose: Backend core functionality.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
import os
import ssl
from pathlib import Path
from typing import Any, AsyncGenerator

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_ROOT / ".env")

LOCAL_DEVELOPMENT_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/roodhamaster"
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL and os.getenv("ENV", "").lower() == "development":
    SQLALCHEMY_DATABASE_URL = LOCAL_DEVELOPMENT_DATABASE_URL

if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Configure it in task-4-backend-skeleton/.env or your environment before starting the backend."
    )

DATABASE_URL_INFO = make_url(SQLALCHEMY_DATABASE_URL)

# 1. Utility to transform URL for Async support
def get_async_url(url: str) -> str:
    """Swaps for Async support as requested."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url

# 2. Async Configuration (Primary for Digital Nervous System)
ASYNC_DATABASE_URL = get_async_url(SQLALCHEMY_DATABASE_URL)
engine_options: dict[str, Any] = {
    "pool_pre_ping": True,
}
if ASYNC_DATABASE_URL.startswith("postgresql+asyncpg://"):
    rds_ssl_context = ssl.create_default_context()
    rds_ssl_context.check_hostname = False
    rds_ssl_context.verify_mode = ssl.CERT_NONE
    engine_options["pool_timeout"] = 5
    engine_options["connect_args"] = {"timeout": 5, "ssl": rds_ssl_context}

async_engine = create_async_engine(ASYNC_DATABASE_URL, **engine_options)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 3. Async Dependency
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        # 4. Apply RLS Context for the Session (Digital Handshake)
        from app.core.tenant_context import tenant_id_context
        tid = tenant_id_context.get()
        if tid and not async_engine.url.drivername.startswith("sqlite"):
            await db.execute(text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=tid))
        try:
            yield db
        finally:
            await db.close()


async def refresh_engine_pools() -> None:
    """Drop pooled connections so the app does not keep stale DB sessions across restarts."""
    await async_engine.dispose()


async def fetch_db_runtime_snapshot() -> dict[str, Any]:
    """
    Returns the active database target plus a live runtime query from Aurora.
    Uses a fresh async connection from the shared engine.
    """
    async with async_engine.connect() as conn:
        runtime_result = await conn.execute(
            text(
                """
                SELECT
                    current_database() AS current_database,
                    current_schema() AS current_schema,
                    current_setting('search_path') AS search_path,
                    now() AS now_utc,
                    inet_server_addr()::text AS server_addr,
                    inet_server_port() AS server_port
                """
            )
        )
        row = runtime_result.mappings().one()

        tables_result = await conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                ORDER BY table_name
                """
            )
        )
        table_names = [item["table_name"] for item in tables_result.mappings().all()]

        table_counts = {}
        for table_name in ("operations_master", "job_operations", "tenants"):
            if table_name not in table_names:
                table_counts[table_name] = "missing"
                continue
            count_result = await conn.execute(text(f'SELECT count(*) AS row_count FROM "{table_name}"'))
            table_counts[table_name] = count_result.mappings().one()["row_count"]

    return {
        "configured_host": DATABASE_URL_INFO.host,
        "configured_port": DATABASE_URL_INFO.port,
        "configured_database": DATABASE_URL_INFO.database,
        "current_database": row["current_database"],
        "current_schema": row["current_schema"],
        "search_path": row["search_path"],
        "now": row["now_utc"].isoformat(),
        "server_addr": row["server_addr"],
        "server_port": row["server_port"],
        "tables": table_names,
        "table_counts": table_counts,
        "pool_pre_ping": {
            "sync_engine": True,
            "async_engine": True,
        },
    }

