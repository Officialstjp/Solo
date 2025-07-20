"""
Module Name: app/core/db_service.py
Purpose: The mian entry point for database access in the applicaion.
It coordinates access to all specialized database services.
"""

from typing import Dict, List, Optional, Any, Union
from contextlib import asynccontextmanager
import asyncio
import functools

from core.db.connection import get_connection_pool, get_sync_connection
from core.db.metrics_db import MetricsDatabase
from core.db.models_db import ModelsDatabase
from core.db.users_db import UsersDatabase
#from core.db.rag_db import RAGDatabase
#from core.db.cache_db import CacheDatabase
from core.db.big_brother import BigBrother
from utils.logger import get_logger

class DatabaseService:
    """
    Central database service that provides access to all database-releated functionality
    """
    def __init__(self, connection_string=None, config=None):
        """ Initialize the database service with configuration

        Args:
            config: Configuration object or dict
        """
        self.logger = get_logger("db_service")
        self.connection_string = connection_string or "postgresql://solo_app:changeme@localhost:5432/solo"
        self.config = config

        self.metrics = MetricsDatabase()
        self.models = ModelsDatabase()
        self.users = UsersDatabase()
        #self.rag = RAGDatabase()
        #self.cache = CacheDatabase()
        self.bigBrother = BigBrother()

        self.logger.info("Database service initialized")

    async def initialize(self):
        """ Initialize the database connection pool"""
        try:
            self.logger.info("Initializing database connection pool")
            # Create pool with the connection string from init
            if self.connection_string:
                # Use the provided connection string
                await get_connection_pool(self.connection_string)
            else:
                # No connection string provided, use default
                self.logger.warning("No connection string provided, using environment variables")
                await get_connection_pool()

            await self.metrics.initialize()
            await self.models.initialize()
            await self.users.initialize()
            #await self.rag.initialize()
            #await self.cache.initialize()
            await self.bigBrother.initialize()

            self.logger.info("Database connection pool initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize database connection pool: {str(e)}")
            return False

    async def close(self):
        """ shutdown the database connection pool"""
        try:
            self.logger.info("Closing database connection pool")
            pool = await get_connection_pool()
            await pool.close()
            self.logger.info("Database connection pool closed")
            return True
        except Exception as e:
            self.logger.warning(f"Failed to close database connection pool: {str(e)}")
            return False

    @asynccontextmanager
    async def transaction(self):
        """ Context manager for database transactions """
        pool = await get_connection_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def execute(self, query, *args, fetch=False):
        """ Execute a database query

        Args:
            query: SQL query string
            *args: Query parameters
            fetch: Whether to fetch results

        Returns:
            Query results if fetch=True, otherwise None
        """
        pool = await get_connection_pool()
        async with pool.acquire() as conn:
            if fetch:
                return await conn.fetch(query, *args)
            else:
                await conn.execute(query, *args)

    def execute_sync(self, query, *args, fetch=False):
        """ Syncrhonous version of execute """
        with get_sync_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, args)
                if fetch:
                    return cur.fetchall()

    async def test_connection(self) -> bool:
        """ Test database connectivity

        Returns:
            True if connection successful, False otherwise
        """
        try:
            await self.execute("SELECT 1", fetch=True)
            self.logger.info("Database connection test successful")
            return True
        except Exception as e:
            self.logger.error(f"Database connection test failed: {e}")
            return False
