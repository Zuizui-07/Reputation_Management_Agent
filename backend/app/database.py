"""
================================================
  Database — async SQLAlchemy engine and session
================================================
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


# ── Async engine ──
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)

# ── Session factory ──
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative base ──
class Base(DeclarativeBase):
    pass


# ── Dependency for FastAPI routes ──
async def get_db():
    """Yield an async DB session, auto-close on exit."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
