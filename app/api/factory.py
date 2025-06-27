"""
Module Name: app/api/factory.py
Purpose    : Factory for creating and configuring the FastAPI application
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cores import CORSMiddleware
from fastapi.responses import JSONResponse
import time
from typing import Dict, Optional

from app.utils.events import EventBus
from app.utils.logger import get_logger
from app.config import get_config
from app.core.model_manager import ModelManager
from app.core.prompt_templates import PromptLibrary

logger = get_logger(name="API_Factory", json_format=False)

def create_app() -> FastAPI:
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

    # store application state
    app.state.config = config
    app.state.event_bus = event_bus
    app.state.model_manager = model_manager
    app.state.prompt_library = prompt_library
    app.state.start_time = time.time()
    app.state.metrics = {
        "total_request": 0,
        "total_tokens_generated": 0,
        "cache_hits": 0,
        "cache_misses": []
    }

    @app.on_event("startup")
    async def startup_event():
        logger.info("Initializing API server components")

        models = app.state.model_manager.scan_models()
        logger.info(f"Found {len(models)} models")

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
        """ Retrun the current system metrics """
        uptime = time.time() - app.state.start_time

        return  {
            "status": "online",
            "uptime": uptime,
            "version": "0.1.0",
            "components": {
                "event_bus": app.state.event_bus is not None,
                "model_manager": app.state.model_manager is not None,
                "prompt_library": app.state.prompt_library is not None
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
