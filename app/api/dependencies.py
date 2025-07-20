"""
Module Name : app/api/dependencies.py
Purpose     : Dependency injection functions for FastAPI routes
              created to avoid circular imports and manage dependencies cleanly.
History     :
    Date            Notes
    20.07.2025      Add history
"""
from fastapi import Depends, Request
from app.utils.events import EventBus
from app.core.model_manager import ModelManager
from app.core.model_service import ModelService
from app.core.prompt_templates import PromptLibrary
from app.core.db_service import DatabaseService
from app.config import AppConfig

async def get_config(request: Request) -> AppConfig:
    """ Get the application Config forom app state """
    return request.app.state.config

async def get_event_bus(request: Request) -> EventBus:
    """ Get the event bus instance from app state """
    return request.app.state.event_bus

async def get_model_manager(request: Request) -> ModelManager:
    """ Get the model manager instance from app state """
    return request.app.state.model_manager

async def get_model_service(request: Request) -> ModelService:
    """Get the model service instance from app state"""
    return request.app.state.model_service

async def get_prompt_library(request: Request) -> PromptLibrary:
    """ Get the prompt library instance from app state """
    return request.app.state.prompt_library

async def get_metrics(request: Request) -> dict:
    """ Get the metrics dictionary from app state """
    return request.app.state.metrics

async def get_db_service(request: Request) -> DatabaseService:
    """ Get the DatabaseService instance from app state """
    return request.app.state.db_service
