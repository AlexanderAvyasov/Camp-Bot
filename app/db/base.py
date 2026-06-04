from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings

_db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://").replace("postgres://", "postgresql+asyncpg://")

# NullPool: no connection is ever reused across calls.
# Required because the bot and uvicorn run in different event loops (different threads).
# Supabase Session Pooler (PgBouncer) handles pooling on its side, so this is safe.
engine = create_async_engine(_db_url, echo=False, poolclass=NullPool)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
