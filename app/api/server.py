"""
Module Name: app/api/server.py
Purpose   : HTTP server for Solo API.
Params    : None
History   :
    Date            Notes
    2025-06-08      Init

"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from typing import Dict, List, Optional, Any
import asyncio, time, logging, os
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.utils.events import EventBus, EventType, LLMRequestEvent, LLMResponseEvent
from app.utils.logger import get_logger
from app.config import AppConfig, get_config
from app.core.model_manager import ModelManager
from app.core.prompt_templates import PromptLibrary

from app.api.routes.models_endpoint import router as models_router
from app.api.routes.llm_endpoint import router as llm_router
from app.api.routes.config_endpoint import router as config_router
from app.api.routes.metrics_endpoint import router as metrics_router

app = FastAPI(
    title="Solo API",
    description="API for Solo AI Assistant",
    version="0.1.0"
)

app.include_router(models_router)
app.include_router(llm_router)
app.include_router(config_router)
app.include_router(metrics_router)

# CORS middleware to allow requests from the dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # this can be adjusted in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = get_config()
logger = get_logger(name = "API", json_format=False)
event_bus = None
model_manager = None
prompt_library = None
start_time = time.time()

metrics = {
    "total_requests": 0,
    "total_tokens_generated": 0,
    "cache_hits": 0,
    "cache_misses": [],
    "tokens_per_second": []
}

@app.on_event("startup")
async def startup_event():
    global event_bus, model_manager, prompt_library

    logger.info("Initialising API server components")
    event_bus = EventBus()
    model_manager = ModelManager(
        models_dir=config.get_models_dir(),
        default_model=config.llm.model_path
    )

    models = model_manager.scan_models()
    logger.info(F"Found {len(models)} models")

    logger.info("API server initialized successfully")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down API server")

@app.get("/status")
async def get_status():
    """ Return the current system status"""
    uptime = time.time() - start_time

    return {
        "status": "online",
        "uptime": uptime,
        "version": "0.1.0",
        "components": {
            "event_bus": event_bus is not None,
            "model_manager": model_manager is not None,
            "prompt_library": prompt_library is not None
        }
    }
@app.get("/")
async def root():
    return {
        "name": "Solo API",
        "version": "0.1.0",
        "description": "API for Solo Ai Assistant",
        "status": "online"
    }

@app.excpetion_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "message": str(exc)}
    )

def start_server(): # figure out how to nicely start and integrate into main.py
    uvicorn.run(app, host="0.0.0.0", port=config.api_port)

if __name__ == "__main__":
    start_server()
