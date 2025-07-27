"""
Module Name: app/api/factory.py
Purpose    : Factory for creating and configuring the FastAPI application
Due to circle import issues, a seperate factory with dependencies file was chosen to manage imports more cleanly.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import asyncio
from typing import Dict, Optional
import os

from app.utils.events import EventBus
from app.utils.logger import get_logger
from app.config import get_config
from app.core.model_manager import ModelManager
from app.core.prompt_templates import PromptLibrary
from app.core.db_service import DatabaseService
from app.api.middleware import auth_middleware

logger = get_logger(name="API_Factory", json_format=False)

def create_app(
    db_service=None,
    existing_model_service=None,
    existing_event_bus=None,
    existing_model_manager=None
) -> FastAPI:
    """
    Create and configure a FastAPI application instance

    Args:
        db_service (DatabaseService): Database service instance
        existing_model_service (ModelService, optional): Existing model service to use
        existing_event_bus (EventBus, optional): Existing event bus to use
        existing_model_manager (ModelManager, optional): Existing model manager to use

    Returns:
        FastAPI: Configured application instance
    """
    config = get_config()

    app = FastAPI(
        title="Solo API",
        description="API for Solo AI Assistant",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # CORS middleware to allow requests from the dashboard
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # this can be adjusted in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if db_service:
        app.middleware("http")(auth_middleware(db_service=db_service))
    else:
        logger.warning("No database service provided, authentication middleware will not be active")

    # Use existing services if provided, otherwise create new ones
    event_bus = existing_event_bus if existing_event_bus else EventBus()
    model_manager = existing_model_manager if existing_model_manager else ModelManager(
        models_dir=config.get_models_dir(),
        default_model=config.llm.model_path
    )
    prompt_library = PromptLibrary()

    # Default model ID is the basename of the model path or use first available model
    default_model_id = None
    if config.llm.model_path:
        default_model_id = os.path.basename(config.llm.model_path)
    else:
        # Try to get first available model
        available_models = model_manager.list_available_models()
        if available_models:
            default_model_id = os.path.basename(available_models[0].path)
            logger.info(f"No default model specified, using first available: {default_model_id}")

    if not default_model_id:
        logger.warning("No models found, model service will be initialized without a default model")
        default_model_id = "default"  # Placeholder to avoid NoneType errors

    # Use existing model service if provided, otherwise create a new one
    model_service = existing_model_service
    if not model_service:
        logger.warning("No existing model service provided, features requiring model service may not work")

    # Store application state
    app.state.config = config
    app.state.event_bus = event_bus
    app.state.model_manager = model_manager
    app.state.model_service = model_service
    app.state.prompt_library = prompt_library
    app.state.start_time = time.time()
    app.state.metrics = {
        "total_requests": 0,
        "total_tokens_generated": 0,
        "cache_hits": 0,
        "cache_misses": 0,  # Changed from array to integer to match usage in llm_endpoint.py
        "tokens_per_second": [],
        "response_times": []
    }
    app.state.db_service = db_service

    # Register startup and shutdown events
    @app.on_event("startup")
    async def startup_event():
        logger.info("Initializing API server components")

        # Scan models
        models = app.state.model_manager.scan_models()
        logger.info(f"Found {len(models)} models")

        # Initialize model service but don't await it
        # The service will load the default model in the background
        app.state.model_service_task = asyncio.create_task(
            app.state.model_service.initialize()
        )

        # Test database connection if available
        if app.state.db_service:
            db_connected = await app.state.db_service.test_connection()
            if db_connected:
                logger.info("Database connection established")
            else:
                logger.warning("Database connection failed, some features may be unavailable")

        logger.info("API server initialized successfully")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Shutting down API server")

    @app.get("/")
    async def root():
        return {
            "name": "Solo API",
            "version": "0.1.0",
            "description": "API for Solo AI Assistant",
            "status": "online"
        }

    @app.get("/status")
    async def get_status():
        """Return the current system status"""
        uptime = time.time() - app.state.start_time

        # Get model service status
        model_service = app.state.model_service
        loaded_models = list(model_service.models.keys()) if model_service else []
        loading_models = list(model_service.loading_models) if model_service else []

        db_status = False
        if app.state.db_service:
            try:
                db_status = app.state.db_service.test_connection()
            except Exception as e:
                db_status = False

        return {
            "status": "online",
            "uptime": uptime,
            "version": "0.1.0",
            "components": {
                "event_bus": app.state.event_bus is not None,
                "model_manager": app.state.model_manager is not None,
                "model_service": app.state.model_service is not None,
                "prompt_library": app.state.prompt_library is not None,
                "db_service": db_status
            },
            "models": {
                "loaded": loaded_models,
                "loading": loading_models,
                "default": model_service.default_model_id if model_service else None,
                "db_service": db_status
            }
        }

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "message": str(exc)}
        )

    from app.api.routes.models_endpoint import create_router as create_models_router
    from app.api.routes.llm_endpoint import create_router as create_llm_router
    from app.api.routes.config_endpoint import create_router as create_config_router
    #from app.api.routes.metrics_endpoint import create_router as create_metrics_router
    from app.api.routes.users_endpoint import create_router as create_users_router
    from app.api.routes.conversations_endpoint import create_router as create_conversations_router

    app.include_router(create_models_router(app))
    app.include_router(create_llm_router(app))
    app.include_router(create_config_router(app))
    #app.include_router(create_metrics_router(app))
    app.include_router(create_conversations_router(app))
    app.include_router(create_users_router(app))

    return app
