import os
import asyncpg
import psycopg2
from contextlib import contextmanager
from typing import Optional
import asyncio

_pool = None

async def get_connection_pool():
    """ Get or crewate the database connection pool

    Returns:
        asyncpg connection pool
    """
    global _pool
    if _pool is None:
        db_host = os.environ.get("POSTGRES_HOST", "localhost")
        db_port = os.environ.get("POSTGRES_PORT", "5432")
        db_name = os.environ.get("POSTGRES_DB", "solo_db")
        db_user = os.environ.get("POSTGRES_USER", "solo_app")
        db_password = os.environ.get("POSTGRES_APPPASSWORD", "")

        _pool = await asyncpg.create_pool(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        return _pool
    else:
        return _pool

@contextmanager
def get_sync_connection():
    """ Get a synchronous database connection

    Yields:
        psycopg2 connection object
    """
    db_host = os.environ.get("POSTGRES_HOST", "localhost")
    db_port = os.environ.get("POSTGRES_PORT", "5432")
    db_name = os.environ.get("POSTGRES_DB", "solo_db")
    db_user = os.environ.get("POSTGRES_USER", "solo_app")
    db_password = os.environ.get("POSTGRES_PASSWORD", "")

    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password
    )

    try:
        yield conn
    finally:
        conn.close()

async def close_pool():
    """ Close the database connection pool """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
