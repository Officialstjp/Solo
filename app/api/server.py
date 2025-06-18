"""
Module Name: app/api/server.py
Purpose   : HTTP server for Solo API.
Params    : None
History   :
    Date            Notes
    2025-06-08      Init

"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cores import CORSMiddleware
from fastapi.responses import JSONREsponse
from typing import Dict, List, Optional, Any
import asnycio, time, logging, os
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.utils.events import EventBus, EventType, LLMRequestEvent, LLMResponseEvent
from app.utils.logger import setup_logger
from app.config import AppConfig, get_config
from app.core.model_manager import ModelManager
from app.core.prompt_templates import PromptLibrary

app = FastAPI(
    title="Solo API",
    description="API for Solo AI Assistant",
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

config = get_config()
logger = setup_logger(json_format=False)
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
async def get_statu():
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
