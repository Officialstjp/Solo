"""
Module Name: app/api/middleware/auth_middleware.py
Purpose   : Middleware for authentication and authorization in the API.
History   :
    Date            Notes
    20.07.2025      Init
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional, Callable, Awaitable, List, Union

from app.utils.logger import get_logger
from app.core.db_service import DatabaseService

logger = get_logger(name="Auth_Middleware", json_format=False)

class AuthMiddleware:
    """ Authentication middleware for the API """

    def __init__(self,
                db_service: DatabaseService,
                exclude_paths: Optional[List[str]] = None,
                exclude_prefixes: Optional[List[str]] = None):

        """
        Initialize the auth middleware

        Args:
            db_service (DatabaseService): Database service instance
            exclude_paths (List[str], optional): List of paths to exclude from auth
            exclude_methods (List[str], optional): List of HTTP methods to exclude from auth
        """
        # only allow the root currently, testing purposes
        self.db_service = db_service
        self.exclude_paths = exclude_paths or [
            "/",
            #"/status",
            #"/docs",
            #"/openapi.json",
            #"/redoc",
            #"/auth/login",
            #"/auth/register",
            #"/auth/forgot-password",
            #"/auth/reset-password",
        ]
        self.exclude_prefixes = exclude_prefixes or [
            #"/static/",
            #"/metrics/", # Exclude metrics endpoint - can be secured separately
            #"/auth/",     # Allow all authentication-related endpoints
            "/test/",  # Allow test endpoints for development
            "/llm/generate"  # allow the llm/generate endpoint
        ]
        logger.info("Auth middleware initialized")

    async def __call__(self, request: Request, call_next: Callable[[Request], Awaitable[JSONResponse]]) -> JSONResponse:
        """
        Process the request and validate authentication

        Args:
            request (Request): The incoming request
            call_next (Callable[[Request], Awaitable[JSONResponse]]): The next middleware or endpoint

        Returns:
            JSONResponse: The response from the next middleware or endpoint
        """
        # Skip excluded paths
        if any(request.url.path.startswith(prefix) for prefix in self.exclude_prefixes) or \
        request.url.path in self.exclude_paths:
            return await call_next(request)

        # get the auth token from header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authorization header missing"}
            )

        # Parse the token
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid authentication scheme"}
                )
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid authorization header format"}
            )

        # validate the token
        try:
            # get client info for rate limiting and security checks
            client_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("User-Agent", "unknown")

            # Validate the token with BigBrother
            user_info = await self.db_service.bigBrother.validate_token(token, client_ip, user_agent)
            if not user_info:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid or expired token"}
                )

            # Store user info in request state for handlers
            request.state.user = user_info
            request.state.token = token

            return await call_next(request)

        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Authentication failed"}
            )
