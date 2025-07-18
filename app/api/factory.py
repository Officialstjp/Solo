"""
Module Name: app/api/factory.py
Purpose    : Factory for creating and configuring the FastAPI application
Due to circle import issues, a seperate factory with dependencies file was chosen to manage imports more cleanly.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cores import CORSMiddleware
from fastapi.responses import JSONResponse
import time
from typing import Dict, Optional
import os

from app.utils.events import EventBus
from app.utils.logger import get_logger
from app.config import get_config
from app.core.model_manager import ModelManager
from app.core.model_service import ModelService
from app.core.prompt_templates import PromptLibrary
from app.core.db_service import DatabaseService

logger = get_logger(name="API_Factory", json_format=False)

def create_app(db_service=None) -> FastAPI:
    """
    Create and configure a FastAPI application instance

    Returns:
        FastAPI: Configured application instance
    """
    config = get_config()

    app = FastAPI(
        title="Solo API",
        description="API for Solo AI Assistnatn",
        version="0.1.0"
    )

    # CORS middleware to allow requests from the dashboard
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # this can be adjusted in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    event_bus = EventBus()
    model_manager = ModelManager(
        models_dir=config.get_models_dir(),
        default_model=config.llm.model_path
    )
    prompt_library = PromptLibrary()

    # Default model ID is the basename of the model path
    default_model_id = os.path.basename(config.llm.model_path)

    # Create model service (but don't initialize yet - that happens in startup event)
    model_service = ModelService(
        event_bus=event_bus,
        model_manager=model_manager,
        default_model_id=default_model_id,
        max_models=config.llm.max_loaded_models if hasattr(config.llm, 'max_loaded_models') else 2
    )

    # Store application state
    app = FastAPI()
    app.state.config = config
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
        "cache_misses": [],
        "tokens_per_second": [],
        "response_times": []
    },
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

        return {
            "status": "online",
            "uptime": uptime,
            "version": "0.1.0",
            "components": {
                "event_bus": app.state.event_bus is not None,
                "model_manager": app.state.model_manager is not None,
                "model_service": app.state.model_service is not None,
                "prompt_library": app.state.prompt_library is not None
            },
            "models": {
                "loaded": loaded_models,
                "loading": loading_models,
                "default": model_service.default_model_id if model_service else None
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
    from app.api.routes.metrics_endpoint import create_router as create_metrics_router

    app.include_router(create_models_router(app))
    app.include_router(create_llm_router(app))
    app.include_router(create_config_router(app))
    app.include_router(create_metrics_router(app))

    return app
