"""
Database connection management for ARIA.
Handles async SQLAlchemy connection pooling and session management.
"""

import os
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncEngine,
    async_sessionmaker
)
from sqlalchemy.pool import NullPool
from aria.config import get_settings


# Global engine and session factory
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Get or create the async SQLAlchemy engine.
    
    Returns:
        AsyncEngine: The database engine instance
    """
    global _engine
    
    if _engine is None:
        settings = get_settings()
        
        # Extract project reference from Supabase URL
        supabase_url = str(settings.supabase_url).rstrip("/")
        db_password = settings.supabase_db_password
        host = supabase_url.replace("https://", "").replace("http://", "")
        project_ref = host.split(".")[0]
        
        # Check if user wants to use pooler (set USE_POOLER=true in .env)
        # Force to True for now since direct connection doesn't work
        use_pooler = True  # Always use pooler
        
        if use_pooler:
            # Use Connection Pooler (better for production, requires pooler to be enabled)
            # Get pooler region from env or default to ap-southeast-1
            pooler_region = os.getenv("POOLER_REGION", "ap-southeast-1")
            pooler_host = f"aws-0-{pooler_region}.pooler.supabase.com"
            pooler_port = 6543
            db_url = f"postgresql+asyncpg://postgres.{project_ref}:{db_password}@{pooler_host}:{pooler_port}/postgres"
            
            if settings.debug:
                print(f"[DEBUG] Connecting to database via Supabase Pooler:")
                print(f"[DEBUG] Project ref: {project_ref}")
                print(f"[DEBUG] Pooler host: {pooler_host}")
                print(f"[DEBUG] Pooler port: {pooler_port}")
                print(f"[DEBUG] Username: postgres.{project_ref}")
        else:
            # Use Direct Connection (default, works out of the box)
            db_host = f"db.{project_ref}.supabase.co"
            db_port = 5432
            db_url = f"postgresql+asyncpg://postgres:{db_password}@{db_host}:{db_port}/postgres"
            
            if settings.debug:
                print(f"[DEBUG] Connecting to database directly:")
                print(f"[DEBUG] Project ref: {project_ref}")
                print(f"[DEBUG] DB host: {db_host}")
                print(f"[DEBUG] DB port: {db_port}")
        
        _engine = create_async_engine(
            db_url,
            echo=False,  # Don't log SQL queries (too verbose)
            pool_size=5,  # Maximum number of connections in the pool
            max_overflow=10,  # Maximum overflow connections
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,  # Recycle connections after 1 hour
            connect_args={
                "ssl": "prefer",  # Use SSL if available
                "timeout": 10,  # Connection timeout in seconds
            }
        )
    
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Get or create the async session factory.
    
    Returns:
        async_sessionmaker: The session factory
    """
    global _async_session_factory
    
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
            autocommit=False,
            autoflush=False,
        )
    
    return _async_session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session.
    
    Usage:
        async with get_session() as session:
            result = await session.execute(query)
    
    Yields:
        AsyncSession: Database session
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_connection() -> bool:
    """
    Check if database connection is healthy.
    
    Returns:
        bool: True if connection is healthy, False otherwise
    """
    import socket
    
    # First, check basic internet connectivity
    try:
        settings = get_settings()
        supabase_url = str(settings.supabase_url).rstrip("/")
        host = supabase_url.replace("https://", "").replace("http://", "")
        project_ref = host.split(".")[0]
        
        # Use Supabase Pooler endpoint — read region from env
        pooler_region = os.getenv("POOLER_REGION", "ap-southeast-1")
        pooler_host = f"aws-0-{pooler_region}.pooler.supabase.com"
        pooler_port = 6543
        
        # Try to resolve the hostname
        socket.getaddrinfo(pooler_host, pooler_port, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror:
        print(f"\n❌ Cannot resolve database pooler hostname: {pooler_host}")
        print(f"   This usually means:")
        print(f"   1. ❌ No internet connection")
        print(f"   2. ❌ DNS resolution is not working")
        print(f"   3. ❌ Firewall is blocking DNS queries")
        print(f"\n   💡 Please check your internet connection and try again.")
        return False
    except Exception as e:
        print(f"\n❌ Network check failed: {e}")
        return False
    
    # Now try actual database connection
    try:
        from sqlalchemy import text
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        error_msg = str(e)
        
        # Provide helpful error messages for common issues
        if "timeout" in error_msg.lower():
            print(f"\n❌ Database connection failed: Connection timeout")
            print(f"   The database pooler is not responding.")
            print(f"   Please check if Supabase is accessible.")
        elif "password" in error_msg.lower() or "authentication" in error_msg.lower():
            print(f"\n❌ Database connection failed: Authentication error")
            print(f"   Please check your database password in .env file")
        else:
            print(f"\n❌ Database connection check failed: {e}")
        
        return False


async def close_engine():
    """
    Close the database engine and cleanup connections.
    Should be called on application shutdown.
    """
    global _engine, _async_session_factory
    
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for getting a database session.
    
    Usage in FastAPI:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db_session)):
            # Use db session here
            pass
    
    Yields:
        AsyncSession: Database session
    """
    async with get_session() as session:
        yield session
