"""
Module Name: app/api/middleware/__init__.py
Purpose   : Export authentication middleware from the middleware package.
History   :
    Date            Notes
    20.07.2025      Init
"""

from app.api.middleware.auth_middleware import AuthMiddleware

def auth_middleware(db_service=None):
    """
    Create an authentication middleware instance

    Args:
        db_service (DatabaseService, optional): Database service instance

    Returns:
        AuthMiddleware: Configured middleware instance
    """
    return AuthMiddleware(db_service=db_service).__call__
