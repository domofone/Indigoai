"""
Database connection and session management.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
import os

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Determine if we're using async or sync based on URL
if settings.database_url.startswith("postgresql+asyncpg"):
    # Async engine
    engine = create_async_engine(
        settings.database_url,
        echo=False,  # Set to True for SQL logging
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    
    AsyncSessionLocal = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )
    
    async def get_db() -> AsyncGenerator[AsyncSession, None]:
        """Dependency for FastAPI to get DB session."""
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
else:
    # Synchronous engine (for migrations)
    engine = create_engine(
        settings.database_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    
    SessionLocal = sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False
    )


async def init_db():
    """Initialize database tables (for development only)."""
    async with engine.begin() as conn:
        # Create all tables
        from app.models.models import Base
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections (for shutdown)."""
    if hasattr(engine, 'dispose'):
        await engine.dispose()