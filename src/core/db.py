"""非同步 SQLAlchemy engine / session 工廠。

deployment.md §3：資料庫直連、無 pooler；listener（LISTEN/NOTIFY，見 realtime-quotes.md §3）
必須走 direct connection，這裡的 engine 沒有插入任何 pgbouncer 之類的中介層。

用 psycopg（v3）而非 asyncpg：psycopg3 原生支援 async，`postgresql+psycopg://`
這同一個 URL 同時餵給 Alembic（sync 風格的 script 產生）與這裡的 async engine，
不需要為了 async 另外維護一份 URL 轉換規則。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from core.settings import settings

engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
