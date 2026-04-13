"""
Async SQLAlchemy database setup (SQLite via aiosqlite).
Swap DATABASE_URL in .env to point at Azure SQL or Postgres when scaling up.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # needed for SQLite
    echo=False,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields a database session per request."""
    async with AsyncSessionLocal() as session:
        yield session


async def create_all_tables() -> None:
    """Called once at startup to create tables if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
