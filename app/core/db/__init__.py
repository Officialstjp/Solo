"""
Module: app/core/db/__init__.py
Purpose: Database package initialization
"""

# Import main classes for easier access
from core.db.connection import get_connection_pool, get_sync_connection, close_pool
